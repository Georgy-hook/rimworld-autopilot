using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class CombatPhysicianLineMath
    {
        private static bool Known(float n)=>n>=0 && !float.IsNaN(n) && !float.IsInfinity(n);
        // Reuse the existing finite TeamCoverReady/SupportHorizon ceiling;
        // an exposed gun must already have fired and retain its future lane.
        public static bool Cover(float exposure,bool observedSupport)
            =>Known(exposure) && (exposure<=.6f || exposure<=1.4f && observedSupport);
        public static bool Terminal(float exposure,bool physician)
            =>Known(exposure) && exposure<=(physician ? .6f : 1.4f);
        public static bool Rejoin(float peak,float terminal,float travel,float cycle)
            =>Known(peak) && Known(terminal) && Known(travel) && Known(cycle)
                && peak<=.6f && terminal<=.6f && travel>0 && travel<=240 && travel+cycle<=600;
    }
    public static partial class CombatControlHelper
    {
        private static bool TryPhysicianCoverPair(Plan mover,FallbackCohort cohort,Plan[] plans,List<Pawn> threats,
            out Plan gun,out Pawn enemy)
        {
            gun=null;enemy=null;int tick=Find.TickManager.TicksGame;
            foreach(var candidate in plans.Where(p=>p!=mover && CohortStationary(p,threats)))
            {
                CombatPathBudgetHelper.Checkpoint("physician_observed_cover_pair");
                var target=AimTarget(candidate.Pawn);
                if(target==null || !threats.Contains(target)
                    || !CombatFallbackMath.CoverObserved(cohort.Created,
                        CombatShotEvidenceHelper.LastTick(candidate.Pawn,target.thingIDNumber),tick,TeamCycle(candidate.Pawn))
                    || !CohortGunFreeFor(candidate.Pawn,mover.Pawn,target)
                    || !CohortCoverWindow(candidate.Pawn,target,threats)
                    || KeepCoverTurn(candidate.Pawn,target))continue;
                gun=candidate;enemy=target;return true;
            }
            return false;
        }
        private static bool CohortCoverWindow(Pawn p,Pawn enemy,List<Pawn> threats)
        {
            if(threats.All(MeleeThreat))return CoverGunWindow(p,enemy,threats);
            if(!Eligible(p) || TeamImmediateDanger(p) || CriticalRangedInjury(p) || MedicalFunctionWarning(p)
                || CombatNativeHelper.Protected(p) || CareTriageHelper.QueuedCare(p)
                || p.CurJobDef==JobDefOf.Goto || p.jobs.jobQueue.Any()
                || !Plans.TryGetValue(p.thingIDNumber,out var plan) || !CohortOwned(p)
                || !DoctorReserveStationary(plan) || !CombatInterceptHelper.CanShootNow(p,enemy))return false;
            float exposure=IncomingRangedExposure(p,p.Position);
            bool observed=CombatShotEvidenceHelper.LastTick(p,enemy.thingIDNumber)>=0
                && TeamCoverReady(p,enemy,threats);
            var v=p.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            float first=v.state==VerbState.Bursting?0:
                p.stances.curStance is Stance_Warmup w && w.focusTarg.Thing==enemy?w.ticksLeft:
                CombatInterceptHelper.MovementLockTicks(p)+v.verbProps.warmupTime*60*p.GetStatValue(StatDefOf.AimingDelayFactor);
            return CombatPhysicianLineMath.Cover(exposure,observed)
                && CombatCoverTurnMath.CoverBurstFits(EarliestContact(p,threats),first,
                    Math.Max(0,v.verbProps.burstShotCount-1)*v.verbProps.ticksBetweenBurstShots,8f/Math.Max(.1f,Speed(p))*60f);
        }
        private static bool PhysicianAtBlindPost(Plan plan,FallbackCohort cohort,List<Pawn> threats)
        {
            var p=plan.Pawn;
            // A later checked early bound may reach a second refuge while the
            // front group's old post remains unchanged. Read actual occupancy
            // of the finite native receipt; an assigned/unreached goal is not
            // arrival. Its long-horizon rally suitability is a separate test
            // from a new short measured firing-edge sortie.
            bool reached=cohort.Posts.TryGetValue(p,out var post) && p.Position==post
                || DoctorBounds.TryGetValue(p,out var bound) && DoctorBoundEligible(p,bound)
                    && p.Position==bound.Goal;
            return p==cohort.Doctor && NativeDoctor(p) && CohortOwned(p)
                && reached
                && p.CurJobDef!=JobDefOf.Goto && p.CurJobDef!=JobDefOf.Ingest
                && !p.jobs.jobQueue.Any() && !(p.carryTracker?.CarriedThing is Pawn)
                && !(p.stances.curStance is Stance_Warmup)
                && !CriticalRangedInjury(p) && p.health.hediffSet.BleedRateTotal==0
                && p.health.summaryHealth.SummaryHealthPercent>=.85f && !TeamImmediateDanger(p)
                && !threats.Any(t=>CombatInterceptHelper.CanShootNow(p,t));
        }
        // A post-arrival firing rejoin is a different purpose from the early
        // wholly-unexposed withdrawal. It never replaces that move in transit.
        // The caller also requires a real same-enemy cover projectile, future
        // native shot/FF, current clinical access and a finite owned move.
        private static bool CoveredPhysicianRejoin(Pawn p,CombatPathBudgetHelper.Observation path)
        {
            if(!path.Found || !NativeDoctor(p) || CriticalRangedInjury(p)
                || p.health.hediffSet.BleedRateTotal>0 || p.jobs.jobQueue.Any()
                || !CombatInterceptHelper.MovementSafe(p,path))return false;
            float ticks=CombatInterceptHelper.MovementLockTicks(p),peak=IncomingRangedExposure(p,p.Position);
            var previous=p.Position;
            foreach(var cell in path.NodesReversed.Reverse().Skip(1))
            {
                CombatPathBudgetHelper.Checkpoint("covered_physician_rejoin");
                ticks+=CombatInterceptHelper.PlannedJogStepTicks(p,previous,cell);
                peak=Math.Max(peak,IncomingRangedExposure(p,cell,ticks));previous=cell;
            }
            return CombatPhysicianLineMath.Rejoin(peak,IncomingRangedExposure(p,previous,ticks+TeamCycle(p)),ticks,TeamCycle(p));
        }
        private static bool RejoinRemainingSafe(Plan plan,CombatPathBudgetHelper.Observation path)
        {
            if(!path.Found || !NativeDoctor(plan.Pawn) || CriticalRangedInjury(plan.Pawn)
                || MedicalFunctionWarning(plan.Pawn) || !CombatInterceptHelper.MovementSafe(plan.Pawn,path))return false;
            // Remainder uses the real native cursor/step cost, not TotalCost.
            float ticks=0,peak=IncomingRangedExposure(plan.Pawn,plan.Pawn.Position);
            var p=plan.Pawn;var previous=p.Position;
            var cells=RemainingRangedCells(p,path).ToArray();if(cells.Length>40)return false;
            foreach(var cell in cells)
            {
                CombatPathBudgetHelper.Checkpoint("physician_rejoin_remaining");
                ticks+=previous==p.Position && p.pather.Moving && cell==p.pather.nextCell
                    ?Math.Max(1,p.pather.nextCellCostLeft):CombatInterceptHelper.PlannedJogStepTicks(p,previous,cell);
                peak=Math.Max(peak,IncomingRangedExposure(p,cell,ticks));previous=cell;
            }
            return CombatPhysicianLineMath.Rejoin(peak,IncomingRangedExposure(p,previous,ticks+TeamCycle(p)),Math.Max(1,ticks),TeamCycle(p));
        }
        private static bool CohortAnchorHasShot(Plan[] plans,IntVec3 cell,List<Pawn> threats)
        {
            foreach(var plan in plans)
            {
                var p=plan.Pawn;var v=p.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
                float horizon=Math.Min(600,TeamCycle(p)+p.Position.DistanceTo(cell)*p.TicksPerMoveCardinal);
                foreach(var t in threats)
                    if(CombatInterceptHelper.TryObservedFuturePosition(t,horizon,out var future)
                        && CombatExposureHelper.CanHitPawnAt(v,t,cell,future)==true
                        && CombatInterceptHelper.FutureFriendlyLaneClear(p,t,cell,future,"cohort_anchor_proposal"))return true;
            }
            return false;
        }
    }
}

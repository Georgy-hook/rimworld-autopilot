using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class CombatRangedScreenMath
    {
        private static bool Known(float x)=>x>=0 && !float.IsInfinity(x) && !float.IsNaN(x);
        // This is a new burst deadline, not a claim that already launched
        // projectiles disappear or that moving guarantees a miss.
        public static bool AllowsMedicalRotation(bool otherMoving,bool onlyReservedDoctorMoving,int actualSameTargetCover)
            =>!otherMoving || onlyReservedDoctorMoving && actualSameTargetCover>=2;
        public static bool BeforeNextBurst(float ownLock,float travel,float enemyFirst,float endpoint,bool improves)
            => Known(ownLock) && Known(travel) && Known(enemyFirst) && Known(endpoint)
                && travel>0 && travel<=90 && endpoint<=.1f && improves
                && ownLock+travel+15f<enemyFirst;
        public static bool BreakFocusedLane(float before,float after,float focused)
            =>Known(before) && Known(after) && Known(focused) && focused<=.1f && after<=before-.2f;
    }
    public static partial class CombatControlHelper
    {
        private static readonly Dictionary<Pawn,int> ScreenReviews=new Dictionary<Pawn,int>();
        private static bool AllowsRangedMedicalRotation(Pawn pawn,Pawn target)
        {
            var moving=SelectedMovingGuns(pawn).ToArray();
            // Avoid expensive lane/forecast reads on the unchanged no-mover
            // path. C# evaluates arguments before entering the pure predicate.
            if(moving.Length==0)return true;
            if(moving.Length!=1 || !IsReservedDoctor(moving[0]))return false;
            return target!=null && CombatRangedScreenMath.AllowsMedicalRotation(true,true,
                CombatInterceptHelper.ReadyCover(pawn,target).Count);
        }
        private static float NextRangedBurst(Pawn enemy)
        {
            var v=enemy.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(v==null)return float.PositiveInfinity;
            if(v.state==VerbState.Bursting)return 0f;
            if(enemy.stances.curStance is Stance_Warmup w && w.verb==v)return w.ticksLeft;
            return CombatInterceptHelper.MovementLockTicks(enemy)
                +v.verbProps.warmupTime*60f*enemy.GetStatValue(StatDefOf.AimingDelayFactor);
        }
        private static void ReviewShortRangedScreen()
        {
            int tick=Find.TickManager.TicksGame;
            foreach(var group in Plans.Values.Where(Valid).GroupBy(p=>p.Pawn.Map).ToArray())
            {
                var threats=group.Key.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
                var candidates=group.Where(OwnStationaryGun)
                    .Where(p=>!ScreenReviews.TryGetValue(p.Pawn,out int last) || tick-last>=45)
                    .Select(p=>new{Plan=p,Enemy=threats.Where(e=>FocusedRangedThreat(e,p.Pawn))
                        .OrderBy(NextRangedBurst).FirstOrDefault()})
                    .Where(x=>x.Enemy!=null).OrderBy(x=>NextRangedBurst(x.Enemy)).ThenBy(x=>x.Plan.Pawn.thingIDNumber);
                foreach(var candidate in candidates)
                {
                    var plan=candidate.Plan;var p=plan.Pawn;
                    if(KeepCoverTurnPlan(plan,threats) || TeamImmediateDanger(p)
                        || p.jobs.jobQueue.Any() || !CombatOrderHelper.Owned(p,p.CurJob))continue;
                    if(!AllowsRangedMedicalRotation(p,candidate.Enemy)
                        && !CriticalRangedInjury(p) && !MedicalFunctionWarning(p))continue;
                    ScreenReviews[p]=tick;
                    float first=threats.Where(e=>FocusedRangedThreat(e,p)).Min(NextRangedBurst);
                    float locked=p.stances.curStance is Stance_Warmup?0f:CombatInterceptHelper.MovementLockTicks(p);
                    if(first<=locked+15f)continue;
                    float before=IncomingRangedExposure(p,p.Position);
                    var cells=GenRadial.RadialCellsAround(p.Position,3f,false)
                        .Where(c=>c.InBounds(p.Map) && c.Standable(p.Map) && !c.Fogged(p.Map)
                            && !CellClaimed(p,c) && !c.GetThingList(p.Map).Any(t=>t is Pawn || t is Building_Trap)
                            && threats.All(e=>c.DistanceTo(e.Position)>=8f))
                        // Aimed-lane interruption is not immunity from every
                        // other enemy. Require that lane to be blocked AND
                        // lower total exposure; route comparison below also
                        // rejects crossing into worse crossfire.
                        .Where(c=>CombatRangedScreenMath.BreakFocusedLane(before,IncomingRangedExposure(p,c),
                            CombatExposureHelper.Lane(candidate.Enemy,p,c,candidate.Enemy.Position)))
                        .OrderBy(c=>c.DistanceToSquared(p.Position));
                    foreach(var cell in ReviewEscapeCells(p,candidate.Enemy,"short_ranged_screen",cells,2))
                    {
                        CombatPathBudgetHelper.Checkpoint("short_ranged_screen");
                        using(var path=CombatPathBudgetHelper.Query(p,p.Position,cell,PathEndMode.OnCell))
                        {
                            if(!path.Found || path.TotalCost>90f || !CombatInterceptHelper.MovementSafe(p,path))continue;
                            float horizon=locked+path.TotalCost+TeamCycle(p);
                            if(!CombatInterceptHelper.TryObservedFuturePosition(candidate.Enemy,horizon,out var future))continue;
                            float focused=CombatExposureHelper.Lane(candidate.Enemy,p,cell,future);
                            if(!CombatRangedScreenMath.BreakFocusedLane(IncomingRangedExposure(p,p.Position,horizon),
                                IncomingRangedExposure(p,cell,horizon),focused))continue;
                            if(!CombatRangedScreenMath.BeforeNextBurst(locked,path.TotalCost,first,focused,
                                SaferRangedRoute(p,path,false,out _)))continue;
                        }
                        // Every check, including protection of the finite
                        // arrival shot, precedes native job/stance mutation.
                        // An actual aimed firing lane is urgent safety, not an
                        // optional simultaneous formation move.
                        bool accepted;urgentTeamTransition=true;
                        try
                        {
                            if(KeepGroupPosition(p,cell))continue;
                            var move=JobMaker.MakeJob(JobDefOf.Goto,cell);move.playerForced=true;
                            move.locomotionUrgency=LocomotionUrgency.Jog;
                            // Take's ownership/queue boundary is unchanged.
                            // Do not end the current job first: a refusal must
                            // preserve the old selected shot, not leave idle.
                            accepted=CombatOrderHelper.Take(p,ref move);
                            if(!accepted)continue;
                            p.stances.CancelBusyStanceSoft();
                            move=RememberMove(p,move,null);RetreatJobs[p]=new CombatJobStamp(move);
                            plan.OwnedJob=move;plan.QueuedShot=null;plan.Mode="retreat";plan.LastMoveTick=tick;
                            plan.RecoveryCell=cell;plan.RecoveryUntilTick=tick+180;
                            plan.RangedWithdrawal=new CombatJobStamp(move);
                            TeamEvent("before_next_burst_checked_short_shelter",p,candidate.Enemy);
                        }
                        finally{urgentTeamTransition=false;}
                        return; // One checked short route transaction per pulse.
                    }
                    return; // A failed attempt cannot consume every gun's path budget.
                }
            }
        }
    }
}

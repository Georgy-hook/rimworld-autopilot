using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class CombatGroupCoordinationMath
    {
        // Only optional displacement is serialized. An endangered gun retains
        // its independently checked exit, even when another exit is underway.
        public static bool KeepFire(bool emergency,bool anotherMoving,bool forward,bool hasShot,
            bool improvesCover,bool leavesSupport)
            => !emergency && (anotherMoving || leavesSupport || forward && hasShot && !improvesCover);
        public static bool RejoinFits(bool wounded,bool realShot,bool hasShot,float contact,float first,float burst,float escape)
            => !wounded && !realShot && hasShot && CombatCoverTurnMath.CoverBurstFits(contact,first,burst,escape);
    }
    public static partial class CombatControlHelper
    {
        private sealed class GroupFire { public Pawn Target; public int Until; }
        private static readonly Dictionary<Map,GroupFire> GroupFires=new Dictionary<Map,GroupFire>();
        private sealed class Rejoin { public int Accepted,Started,Until; public Pawn Target; }
        private static readonly Dictionary<Pawn,Rejoin> Rejoins=new Dictionary<Pawn,Rejoin>();

        private static bool KeepArrivalShot(Pawn p)
        {
            if(!Plans.TryGetValue(p.thingIDNumber,out var plan) || !Valid(plan)
                || !SelectedMoves.TryGetValue(p,out var move) || move.Value==null
                || p.CurJob!=move.Value || p.CurJobDef!=JobDefOf.AttackStatic
                || !(p.CurJob.targetA.Thing is Pawn target) || !Threat(target))return false;
            int tick=Find.TickManager.TicksGame;
            if(!Rejoins.TryGetValue(p,out var rejoin) || rejoin.Accepted!=move.AcceptedTick)
            {
                rejoin=new Rejoin{Accepted=move.AcceptedTick,Started=tick,Until=tick+600,Target=target};Rejoins[p]=rejoin;
            }
            if(tick>rejoin.Until || rejoin.Target!=target || TeamImmediateDanger(p)
                || CareTriageHelper.QueuedCare(p) || CombatNativeHelper.Protected(p))return false;
            var v=p.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            float first=p.stances.curStance is Stance_Warmup warm && warm.focusTarg.Thing==target?warm.ticksLeft:
                CombatInterceptHelper.MovementLockTicks(p)+v.verbProps.warmupTime*60f*p.GetStatValue(StatDefOf.AimingDelayFactor);
            float burst=Math.Max(0,v.verbProps.burstShotCount-1)*v.verbProps.ticksBetweenBurstShots;
            var threats=p.Map.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
            float contact=threats.Where(MeleeThreat).Select(e=>Math.Min(CombatInterceptHelper.ContactTicks(e,p),
                CombatInterceptMath.StationaryContact(p.Position.DistanceTo(e.Position),Math.Max(1f,e.TicksPerMoveCardinal
                    *(e.CurJob?.locomotionUrgency==LocomotionUrgency.Sprint?.75f:1f)),CombatInterceptHelper.MovementLockTicks(e))))
                .DefaultIfEmpty(10000f).Min();
            bool keep=CombatGroupCoordinationMath.RejoinFits(CriticalRangedInjury(p) || MedicalFunctionWarning(p),
                CombatShotEvidenceHelper.LastTick(p,target.thingIDNumber)>=rejoin.Started,
                CombatInterceptHelper.CanShootNow(p,target),contact,first,burst,8f/Math.Max(.1f,Speed(p))*60f)
                && IncomingRangedExposure(p,p.Position,first+burst+15f)<=.6f;
            if(keep)TeamEvent("arrived_selected_shot_kept_before_next_exit",p,target);
            return keep;
        }

        private static bool OwnStationaryGun(Plan plan)
            => Valid(plan) && plan.Pawn.CurJobDef!=JobDefOf.Goto && plan.Pawn.CurJobDef!=JobDefOf.AttackMelee
                && (plan.Pawn.CurJob==null || CombatOrderHelper.Owned(plan.Pawn,plan.Pawn.CurJob)
                    || plan.Pawn.CurJobDef==JobDefOf.Wait_Combat && !plan.Pawn.CurJob.playerForced
                        && plan.Pawn.pather?.Moving!=true)
                && !plan.Pawn.jobs.jobQueue.Any() && !(plan.Pawn.carryTracker?.CarriedThing is Pawn);

        private static Pawn CoordinatedTarget(Pawn p,List<Pawn> threats)
        {
            var coverTarget=CohortCoverTarget(p);
            if(coverTarget!=null && CombatInterceptHelper.CanShootNow(p,coverTarget))return DefensiveTarget(p,coverTarget);
            var physicianTarget=DoctorCoverTarget(p,threats);
            if(physicianTarget!=null)return DefensiveTarget(p,physicianTarget);
            if(!GroupFires.TryGetValue(p.Map,out var fire) || Find.TickManager.TicksGame>fire.Until
                || !threats.Contains(fire.Target) || !CombatInterceptHelper.CanShootNow(p,fire.Target))return null;
            // Personal contact defence and a finite cover transaction remain
            // authoritative. No shared focus licenses ignoring one's pursuer.
            return DefensiveTarget(p,fire.Target);
        }

        // A bounded fire phase for the entire selected group precedes optional
        // path searches. Previously one eight-query support/escape search could
        // unwind the pulse before the other owned idle guns received any shot.
        // Only current geometry and detached observed motion are read here;
        // no owned PawnPath or larger quota is introduced.
        private static void ReviewCoordinatedFire()
        {
            int tick=Find.TickManager.TicksGame;
            foreach(var group in Plans.Values.Where(Valid).GroupBy(p=>p.Pawn.Map).ToArray())
            {
                var plans=group.Where(OwnStationaryGun).OrderBy(p=>p.Pawn.thingIDNumber).ToArray();
                var threats=group.Key.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
                if(plans.Length==0 || threats.Count==0){GroupFires.Remove(group.Key);continue;}
                var available=plans.ToDictionary(p=>p.Pawn,p=>threats.Where(t=>CombatInterceptHelper.CanShootNow(p.Pawn,t)).ToArray());
                var target=threats.Where(t=>plans.Any(p=>available[p.Pawn].Contains(t)))
                    .OrderByDescending(t=>
                    {
                        var victim=ObservedVictim(t);
                        float contact=victim==null?10000f:CombatInterceptMath.StationaryContact(
                            victim.Position.DistanceTo(t.Position),Math.Max(1,t.TicksPerMoveCardinal),CombatInterceptHelper.MovementLockTicks(t));
                        float urgency=CombatNativeHelper.AbductionThreat(t)?10000f:
                            MeleeThreat(t)?CombatInterceptMath.MeleePriority(contact):
                            // Use the existing forecast over observed native routes,
                            // once per target for the group, before the flank opens.
                            ObservedRangedPressure(t,group.Select(p=>p.Pawn).ToArray())*60f;
                        // Clinical actors are often no longer combat plans.
                        // Their actual attacker remains a group responsibility.
                        if(victim?.Faction==Faction.OfPlayer)
                        {
                            urgency+=CombatInterceptMath.VictimPressure(victim.health.summaryHealth.SummaryHealthPercent,
                                victim.health.capacities.GetLevel(PawnCapacityDefOf.Moving),victim.health.hediffSet.BleedRateTotal,
                                threats.Count(e=>ObservedVictim(e)==victim));
                            urgency+=CombatInterceptMath.MedicPressure(MedicalReady(victim),true,
                                group.Key.mapPawns.FreeColonistsSpawned.Count(MedicalReady));
                        }
                        return urgency+plans.Where(p=>available[p.Pawn].Contains(t)).Sum(p=>ShotQuality(p.Pawn,t,p.Pawn.Position))*16f
                            *CombatInterceptMath.TargetVulnerability(t.health.summaryHealth.SummaryHealthPercent,
                                t.GetStatValue(StatDefOf.IncomingDamageFactor),t.BodySize);
                    }).ThenBy(t=>t.thingIDNumber).FirstOrDefault();
                if(target==null){GroupFires.Remove(group.Key);continue;}
                GroupFires[group.Key]=new GroupFire{Target=target,Until=tick+30};
                foreach(var plan in plans)
                {
                    var p=plan.Pawn;var v=p.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
                    if(TeamImmediateDanger(p) || KeepArrivalShot(p) || KeepCoverTurnPlan(plan,threats) || HoldingRecovery(plan,plan.Tactic)
                        || p.stances.curStance is Stance_Warmup || v.state==VerbState.Bursting)continue;
                    var chosen=CoordinatedTarget(p,threats)
                        ?? available[p].OrderByDescending(t=>ShotQuality(p,t,p.Position)).FirstOrDefault();
                    if(chosen==null || !CombatInterceptHelper.CanShootNow(p,chosen))continue;
                    ObserveDoctorCover(p,chosen,threats);
                    if(p.CurJobDef==JobDefOf.AttackStatic && p.CurJob.targetA.Thing==chosen)continue;
                    var shot=JobMaker.MakeJob(JobDefOf.AttackStatic,chosen);shot.playerForced=true;
                    if(!CombatOrderHelper.Take(p,ref shot))continue;
                    plan.OwnedJob=shot;plan.QueuedShot=null;plan.Target=chosen;plan.Mode="shoot";
                    TeamEvent("group_fire_before_optional_paths",p,chosen);
                }
            }
        }

        private static bool KeepGroupPosition(Pawn p,IntVec3 goal)
        {
            if(!goal.InBounds(p.Map) || !Plans.TryGetValue(p.thingIDNumber,out var plan) || !Valid(plan))return false;
            if(!urgentTeamTransition && KeepCohortIntent(p,plan.Tactic,goal))return true;
            if(KeepObservedRangePost(p,plan.Tactic))return true;
            if(KeepArrivalShot(p))return true;
            var threats=p.Map.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
            if(threats.Count==0 || threats.Any(CombatNativeHelper.AbductionThreat))return false;
            bool emergency=urgentTeamTransition || TeamImmediateDanger(p) || CriticalRangedInjury(p) || MedicalFunctionWarning(p);
            if(!emergency)
                emergency=threats.Where(MeleeThreat).Any(e=>CombatInterceptHelper.Pursuing(e,p)
                    && goal.DistanceTo(e.Position)>p.Position.DistanceTo(e.Position)+1f
                    && CombatInterceptHelper.ContactTicks(e,p)<=TeamCycle(p)+CombatInterceptHelper.MovementLockTicks(p)
                        +6f/Math.Max(.1f,Speed(p))*60f+90f);
            if(emergency)return false;
            var peers=Plans.Values.Where(Valid).Select(x=>x.Pawn).Where(g=>g!=p && g.Map==p.Map).ToArray();
            if(peers.Length==0)return false;
            bool forward=threats.Any(e=>goal.DistanceTo(e.Position)+1f<p.Position.DistanceTo(e.Position));
            bool shot=threats.Any(e=>CombatInterceptHelper.CanShootNow(p,e));
            bool improves=IncomingRangedExposure(p,goal)+.1f<IncomingRangedExposure(p,p.Position);
            // Range is a bound on a possible supporting shot, not proof of it.
            // Do not send a healthy gun beyond every remaining gun's reach.
            bool isolated=peers.All(g=>goal.DistanceTo(g.Position)>Math.Max(6f,
                Math.Min(18f,g.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb.verbProps.range*.6f)));
            if(!CombatGroupCoordinationMath.KeepFire(emergency,OtherSelectedGunMoving(p),forward,shot,improves,isolated))return false;
            TeamEvent("group_optional_move_kept_fire_and_support",p);return true;
        }
    }
}

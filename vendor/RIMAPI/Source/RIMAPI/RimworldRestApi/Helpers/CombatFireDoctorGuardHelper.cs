using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static partial class CombatControlHelper
    {
        private static readonly Dictionary<Map,Pawn> ReservedDoctors=new Dictionary<Map,Pawn>();
        private static readonly Dictionary<Pawn,int> GuardReviews=new Dictionary<Pawn,int>();

        // One selected native doctor keeps the role while capable. This does
        // not undraft, treat, change priorities, or reserve a clinical job.
        private static Pawn ReservedDoctor(Map map)
        {
            if(ReservedDoctors.TryGetValue(map,out var doctor)
                && Plans.TryGetValue(doctor.thingIDNumber,out var retained) && Valid(retained)
                && NativeDoctor(doctor) && doctor.Map==map)return doctor;
            doctor=Plans.Values.Where(Valid).Select(p=>p.Pawn)
                .Where(p=>p.Map==map && NativeDoctor(p))
                .OrderBy(p=>IncomingRangedExposure(p,p.Position))
                .ThenByDescending(p=>p.GetStatValue(StatDefOf.MedicalTendSpeed))
                .ThenBy(p=>p.thingIDNumber).FirstOrDefault();
            if(doctor==null)ReservedDoctors.Remove(map);
            else {ReservedDoctors[map]=doctor;TeamEvent("capable_doctor_role_bound",doctor);}
            return doctor;
        }
        private static bool IsReservedDoctor(Pawn pawn)=>ReservedDoctor(pawn.Map)==pawn;

        // Optional forward placement must not spend the retained doctor's
        // safety margin. A safer withdrawal, an emergency and a kidnapping
        // interception still pass through their existing native checks.
        private static bool PreserveDoctorPosition(Pawn pawn,IntVec3 goal)
        {
            if(!NativeDoctor(pawn) || !IsReservedDoctor(pawn) || TeamImmediateDanger(pawn)
                || !goal.InBounds(pawn.Map))return false;
            var threats=pawn.Map.mapPawns.AllPawnsSpawned.Where(Threat).ToArray();
            if(threats.Any(CombatNativeHelper.AbductionThreat))return false;
            bool closer=threats.Where(MeleeThreat).Any(e=>
                goal.DistanceTo(e.Position)+1f<pawn.Position.DistanceTo(e.Position));
            bool moreExposed=CombatDoctorReserveMath.Worse(IncomingRangedExposure(pawn,pawn.Position),IncomingRangedExposure(pawn,goal));
            if(threats.Any(e=>e.equipment?.Primary?.def.IsRangedWeapon==true))
                moreExposed |= CombatDoctorReserveMath.Worse(DoctorProjectedExposure(pawn,pawn.Position,600f),DoctorProjectedExposure(pawn,goal,600f));
            if(!closer && !moreExposed)return false;
            TeamEvent("doctor_optional_forward_move_refused",pawn);return true;
        }

        // Native Wait_Combat can expose a gun without keeping a selected
        // victim in its current job. The reserved physician must not wait for
        // its first wound or an explicit target label before reviewing an exit.
        // This is a review trigger, never a route/arrival or covering-fire proof.
        private static bool DoctorObservedRangedDeadline(Pawn p)
        {
            float current=IncomingRangedExposure(p,p.Position);
            if(float.IsNaN(current) || float.IsInfinity(current) || current<.6f)return false;
            float horizon=Math.Min(600f,TeamCycle(p)+CombatInterceptHelper.MovementLockTicks(p)
                +8f/Math.Max(.1f,Speed(p))*60f+90f);
            float future=IncomingRangedExposure(p,p.Position,horizon);
            return !float.IsNaN(future) && !float.IsInfinity(future) && future>=.6f;
        }

        // Deadline safety precedes optional formation searches. At most one
        // route search transaction per pulse; failed/deferred reviews rotate
        // with a finite cooldown instead of starving the same later pawn.
        private static void ReviewFireDoctorGuard(bool physicianOnly=false)
        {
            ObserveTeamMoves();int tick=Find.TickManager.TicksGame;
            foreach(var group in Plans.Values.Where(Valid).GroupBy(p=>p.Pawn.Map).ToArray())
            {
                var doctor=ReservedDoctor(group.Key);
                var threats=group.Key.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
                if(!threats.Any())continue;
                if(physicianOnly && threats.Any(t=>t.equipment?.Primary?.def.IsRangedWeapon==true))continue;
                var reviews=group.Select(plan=>new{Plan=plan,Pawn=plan.Pawn,
                    Own=threats.Where(e=>MeleeThreat(e) && CombatInterceptHelper.Pursuing(e,plan.Pawn))
                        .OrderBy(e=>CombatInterceptHelper.ContactTicks(e,plan.Pawn)).FirstOrDefault()})
                    .Select(x=>new{ x.Plan,x.Pawn,x.Own,
                        Contact=x.Own==null?float.PositiveInfinity:CombatInterceptHelper.ContactTicks(x.Own,x.Pawn),
                        Medical=x.Pawn==doctor,
                        CoveredEnemy=physicianOnly?null:ProactiveCoveredEnemy(x.Pawn,threats),
                        Targeted=threats.Any(e=>FocusedRangedThreat(e,x.Pawn))
                            || x.Pawn==doctor && DoctorObservedRangedDeadline(x.Pawn)})
                    .Where(x=>!physicianOnly || x.Medical)
                    .Where(x=>!GuardReviews.TryGetValue(x.Pawn,out var last) || tick-last>=45)
                    .Where(x=>x.Contact<=TeamCycle(x.Pawn)+CombatInterceptHelper.MovementLockTicks(x.Pawn)
                            +8f/Math.Max(.1f,Speed(x.Pawn))*60f+90f
                        || x.Targeted && (x.Medical || TargetedWoundedRanged(x.Pawn,threats) || x.CoveredEnemy!=null))
                    .OrderBy(x=>x.Contact).ThenByDescending(x=>x.Medical).ToArray();
                foreach(var review in reviews)
                {
                    var plan=review.Plan;var p=review.Pawn;
                    if(KeepCheckedCohortCover(plan,threats) || KeepCoverTurnPlan(plan,threats))continue;
                    // A healthy useful gun does not start another long peel
                    // while selected peers are still moving. This finite
                    // remaining volley must fit before real contact; clinic,
                    // fire/gas, near contact and abduction never wait here.
                    if(!physicianOnly && MeleeCohort(p.Map,threats) && !threats.Any(CombatNativeHelper.AbductionThreat)
                        && CombatFallbackMath.WaitForMovingPeers(!TeamImmediateDanger(p)
                            && !CriticalRangedInjury(p) && !MedicalFunctionWarning(p),
                            OtherSelectedGunMoving(p),threats.Any(e=>CombatInterceptHelper.CanShootNow(p,e)),
                            EarliestContact(p,threats),TeamCycle(p)))
                    {TeamEvent("finite_group_bound_keeps_stationary_fire",p,review.Own);continue;}
                    if((!CombatOrderHelper.Owned(p,p.CurJob) && !(physicianOnly && DoctorReserveStationary(plan))) || CareTriageHelper.QueuedCare(p)
                        || CombatNativeHelper.Protected(p) || p.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(p,q.job)))continue;
                    // Do not restart a checked retreat during native cooldown,
                    // movement or pending start. New contact remains urgent.
                    if(plan.Mode=="retreat" && Present(p,plan.OwnedJob)
                        && PreserveEscape(p,plan.Tactic) && !TeamImmediateDanger(p))continue;
                    GuardReviews[p]=tick;
                    TeamEvent("deadline_safety_review",p,review.Own);
                    var coverEnemy=review.Own ?? review.CoveredEnemy ?? threats.FirstOrDefault(e=>FocusedRangedThreat(e,p)) ?? plan.Target;
                    var realCover=Plans.Values.Where(Valid).Select(x=>x.Pawn)
                        .Where(g=>g!=p && g.Map==p.Map && Threat(coverEnemy) && TeamCoverReady(g,coverEnemy,threats)).ToArray();
                    bool moved=false;urgentTeamTransition=true;
                    try
                    {
                        if(review.Own!=null && TryRangedRetreat(p,review.Own,plan.Anchor,out var move,false,physicianOnly))
                        {
                            plan.OwnedJob=move;plan.QueuedShot=SelectedMoves[p].Value;
                            plan.Target=review.Own;plan.Mode="retreat";plan.LastMoveTick=tick;moved=true;
                        }
                        else if(review.Own==null)moved=TryBreakRangedContact(plan,threats,true);
                        if(moved)
                        {
                            // Geometry was completed before the action. Binding
                            // accepted ownership cannot spend a new path budget.
                            foreach(var gun in realCover)
                            {
                                CoverTransfers[gun]=new CoverTransfer{Mover=p,Enemy=coverEnemy,Until=tick+600};
                                TeamEvent("real_same_enemy_cover_bound",gun,coverEnemy,p);
                            }
                            if(review.Medical)MedicalExits.Add(p);
                            TeamEvent(review.Medical?"reserved_doctor_checked_exit":"front_gun_checked_exit",p,review.Own);
                        }
                    }
                    catch(CombatReviewDeferredException)
                    {
                        if(physicianOnly)GuardReviews.Remove(p);
                        TeamEvent("deadline_review_deferred_without_route_proof",p,review.Own);throw;
                    }
                    finally{urgentTeamTransition=false;}
                    return;
                }
            }
        }
    }
}

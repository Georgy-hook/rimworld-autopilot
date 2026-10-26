using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class CombatRangePostMath
    {
        private static bool Known(float x)=>x>=0 && !float.IsNaN(x) && !float.IsInfinity(x);
        public static bool ContinuingNotWorse(float route,float holding,float peak,float holdingPeak,
            float terminal,float holdingTerminal,float duration)
            =>Known(route) && Known(holding) && Known(peak) && Known(holdingPeak)
                && Known(terminal) && Known(holdingTerminal) && Known(duration) && duration>0
                && terminal<=.1f && terminal<=holdingTerminal+.001f
                && route<=holding+.001f && peak<=holdingPeak+.001f;
        public static bool RecentShot(int shot,int now,float cycle)
            =>shot>=0 && now>=shot && cycle>=0 && !float.IsInfinity(cycle) && !float.IsNaN(cycle) && now-shot<=cycle+60f;
        public static bool Advantage(float ownRange,float enemyRange)
            => ownRange>0 && enemyRange>0 && !float.IsInfinity(ownRange) && !float.IsInfinity(enemyRange)
                && ownRange>=enemyRange+5f;
        public static bool Band(float ownRange,float enemyRange,float distance)
            => Advantage(ownRange,enemyRange) && distance>=enemyRange+2f && distance<=ownRange-1f;
        public static bool RemainingSupport(int otherActualGuns,float maximumObservedRisk)
            =>Known(maximumObservedRisk) && (maximumObservedRisk<.6f || otherActualGuns>=2);
    }
    public static partial class CombatControlHelper
    {
        private static readonly Dictionary<Pawn,int> RangePostReviews=new Dictionary<Pawn,int>();
        private sealed class RangePost {public IntVec3 Goal;public int Until;}
        private static readonly Dictionary<Pawn,RangePost> RangePosts=new Dictionary<Pawn,RangePost>();
        private static bool OwnedRangePostInTransit(Plan plan)
        {
            var p=plan.Pawn;
            return RangePosts.TryGetValue(p,out var post) && Find.TickManager.TicksGame<=post.Until
                && p.CurJobDef==JobDefOf.Goto && p.CurJob==plan.OwnedJob
                && plan.RangedWithdrawal?.Value==p.CurJob && p.CurJob.targetA.Cell==post.Goal
                && CombatOrderHelper.Owned(p,p.CurJob) && !CombatNativeHelper.Protected(p)
                && !CareTriageHelper.QueuedCare(p) && !p.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(p,q.job));
        }
        private static bool KeepObservedRangePost(Pawn p,string nextTactic)
        {
            if(!RangePosts.TryGetValue(p,out var post))return false;
            bool foreign=p.CurJob!=null && !CombatOrderHelper.Owned(p,p.CurJob)
                && !(p.CurJobDef==JobDefOf.Wait_Combat && !p.CurJob.playerForced);
            bool release=!Eligible(p) || !DefensivePlan(nextTactic) || nextTactic=="intercept_kidnapper"
                || Find.TickManager.TicksGame>post.Until || p.Position!=post.Goal
                || foreign || p.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(p,q.job))
                || TeamImmediateDanger(p);
            if(release){if(p.Position==post.Goal || foreign || !Eligible(p))RangePosts.Remove(p);return false;}
            var threats=p.Map.mapPawns.AllPawnsSpawned.Where(Threat).ToArray();
            if(!threats.Any() || threats.Any(CombatNativeHelper.AbductionThreat)
                || threats.Any(e=>MeleeThreat(e) && p.Position.DistanceTo(e.Position)<8f)
                || IncomingRangedExposure(p,p.Position,TeamCycle(p))>.2f)
            {RangePosts.Remove(p);return false;}
            return true; // Finite defensive role; current legal shots are still dispatched.
        }

        private static float LoadedRange(Pawn p)=>p.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb?.verbProps.range ?? 0;
        private static void ReviewObservedRangePosts()
        {
            int tick=Find.TickManager.TicksGame;
            foreach(var group in Plans.Values.Where(Valid).GroupBy(p=>p.Pawn.Map).ToArray())
            {
                var threats=group.Key.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
                var ranged=threats.Where(e=>e.equipment?.Primary?.def.IsRangedWeapon==true).ToArray();
                if(ranged.Length==0)continue; // No new melee formation/targeting policy.
                foreach(var plan in group.OrderBy(p=>RangePostReviews.TryGetValue(p.Pawn,out int last)?last:0))
                {
                    var p=plan.Pawn;var v=p.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
                    float range=LoadedRange(p),enemyRange=ranged.Max(LoadedRange);
                    if(!CombatRangePostMath.Advantage(range,enemyRange) || OtherSelectedGunMoving(p)
                        || p.CurJobDef==JobDefOf.Goto || p.CurJobDef==JobDefOf.AttackMelee || p.jobs.jobQueue.Any()
                        || p.CurJob==null || !CombatOrderHelper.Owned(p,p.CurJob)
                        || p.stances.curStance is Stance_Warmup || v.state==VerbState.Bursting
                        || CriticalRangedInjury(p) || MedicalFunctionWarning(p) || TeamImmediateDanger(p)
                        || RangePostReviews.TryGetValue(p,out var reviewed) && tick-reviewed<60)continue;
                    RangePostReviews[p]=tick;
                    TeamEvent("ranged_post_review_without_inert_cohort_veto",p);
                    float locked=CombatInterceptHelper.MovementLockTicks(p);
                    float horizon=Math.Min(600f,locked+TeamCycle(p)*2f+180f);
                    float now=IncomingRangedExposure(p,p.Position),forecast=IncomingRangedExposure(p,p.Position,horizon);
                    if(float.IsInfinity(forecast) || forecast<.6f)continue;
                    // Only observed finite native routes are projected. Enemy
                    // later jobs/retargets remain unknown and are re-reviewed.
                    var projected=new Dictionary<Pawn,IntVec3>();bool available=true;
                    foreach(var e in ranged)
                    {
                        if(!CombatInterceptHelper.TryObservedFuturePosition(e,horizon,out var future)){available=false;break;}
                        projected[e]=future;
                    }
                    if(!available)continue;
                    var targets=ranged.OrderByDescending(e=>ObservedRangedPressure(e,new[]{p})).Take(2).ToArray();
                    var cells=GenRadial.RadialCellsAround(p.Position,24f,false)
                        .Where(c=>c.InBounds(p.Map) && c.Standable(p.Map) && !c.Fogged(p.Map)
                            && c.DistanceTo(plan.Anchor)<=26f && !CellClaimed(p,c)
                            && !c.GetThingList(p.Map).Any(t=>t is Pawn || t is Building_Trap)
                            && ranged.All(e=>c.DistanceTo(e.Position)>LoadedRange(e)+2f
                                && c.DistanceTo(projected[e])>LoadedRange(e)+2f)
                            && threats.Where(MeleeThreat).All(e=>c.DistanceTo(e.Position)>=12f)
                            && targets.Any(e=>CombatRangePostMath.Band(range,LoadedRange(e),c.DistanceTo(projected[e]))))
                        .OrderBy(c=>c.DistanceToSquared(p.Position));
                    foreach(var cell in ReviewEscapeCells(p,targets.FirstOrDefault(),"observed_range_post",cells,2))
                    {
                        CombatPathBudgetHelper.Checkpoint("observed_range_post");
                        float travel;
                        using(var path=CombatPathBudgetHelper.Query(p,p.Position,cell,PathEndMode.OnCell))
                        {
                            travel=path.TotalCost;
                            if(!path.Found || travel>420f || !CombatInterceptHelper.MovementSafe(p,path)
                                || !SaferRangedRoute(p,path,false,out _)
                                || IncomingRangedExposure(p,cell,locked+travel+TeamCycle(p))>.1f)continue;
                        }
                        var target=targets.FirstOrDefault(e=>
                            CombatInterceptHelper.TryObservedFuturePosition(e,Math.Min(600f,locked+travel+TeamCycle(p)*2f),out var future)
                            && CombatRangePostMath.Band(range,LoadedRange(e),cell.DistanceTo(future))
                            && CombatExposureHelper.CanHitPawnAt(v,e,cell,future)==true
                            && CombatInterceptHelper.FutureFriendlyLaneClear(p,e,cell,future,"range_post_first_cycle"));
                        if(target==null)continue;
                        // Before current exposure, departure itself is safe;
                        // under fire require actual remaining selected support.
                        int cover=group.Count(other=>other!=plan && OwnStationaryGun(other)
                            && !CriticalRangedInjury(other.Pawn) && !MedicalFunctionWarning(other.Pawn)
                            && ranged.Any(e=>CombatInterceptHelper.CanShootNow(other.Pawn,e)
                                && AimTarget(other.Pawn)==e
                                && CombatRangePostMath.RecentShot(CombatShotEvidenceHelper.LastTick(other.Pawn,e.thingIDNumber),tick,TeamCycle(other.Pawn))));
                        float risk=group.Max(other=>Math.Max(IncomingRangedExposure(other.Pawn,other.Pawn.Position),
                            IncomingRangedExposure(other.Pawn,other.Pawn.Position,Math.Min(600f,locked+travel+TeamCycle(p)))));
                        if(!CombatRangePostMath.RemainingSupport(cover,risk))
                        {TeamEvent("range_advantage_move_waits_for_two_actual_guns",p,target);continue;}
                        bool accepted;urgentTeamTransition=true;
                        try
                        {
                            if(KeepGroupPosition(p,cell))continue;
                            var move=JobMaker.MakeJob(JobDefOf.Goto,cell);move.playerForced=true;
                            move.locomotionUrgency=LocomotionUrgency.Jog;
                            accepted=CombatOrderHelper.Take(p,ref move);if(!accepted)continue;
                            move=RememberMove(p,move,null);RetreatJobs[p]=new CombatJobStamp(move);
                            plan.OwnedJob=move;plan.QueuedShot=null;plan.Target=target;plan.Mode="retreat";plan.LastMoveTick=tick;
                            plan.RecoveryCell=cell;plan.RecoveryUntilTick=tick+(int)Math.Min(900f,locked+travel+TeamCycle(p)*2f);
                            plan.RangedWithdrawal=new CombatJobStamp(move);
                            RangePosts[p]=new RangePost{Goal=cell,Until=plan.RecoveryUntilTick};
                            TeamEvent("observed_range_advantage_post_accepted",p,target);
                        }
                        finally{urgentTeamTransition=false;}
                        return;
                    }
                    return;
                }
            }
        }
    }
}

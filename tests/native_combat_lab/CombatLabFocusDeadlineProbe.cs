#if LAYA_COMBAT_LAB
using System;
using System.Linq;
using System.Reflection;
using RIMAPI.Helpers;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Controllers
{
    // Held initial targeting contract only; no raid outcome or simulated hit.
    public static class CombatLabFocusDeadlineProbe
    {
        private static bool used;
        public static object Run()
        {
            if(used || !CombatLabState.Scenario.StartsWith("focus_deadline_",StringComparison.Ordinal)
                || !CombatLabState.HoldInitial || CombatLabState.StepTicks!=0
                || Find.TickManager.CurTimeSpeed!=TimeSpeed.Paused
                || CombatLabState.Allies.Count!=3 || CombatLabState.Enemies.Count!=2)
                throw new InvalidOperationException("Focus deadline requires its exact unused held fixture");
            used=true;
            var actor=CombatLabState.Allies[0];var buddy=CombatLabState.Allies[1];
            var earlier=CombatLabState.Enemies[0];var committed=CombatLabState.Enemies[1];
            bool self=CombatLabState.Scenario.StartsWith("focus_deadline_self_",StringComparison.Ordinal);
            bool covered=CombatLabState.Scenario=="focus_deadline_self_covered_contract";
            Pawn firstVictim=self?actor:buddy;
            if(!CombatInterceptHelper.Pursuing(earlier,firstVictim) || !CombatInterceptHelper.Pursuing(committed,buddy)
                || !CombatInterceptHelper.CanShootNow(actor,earlier) || !CombatInterceptHelper.CanShootNow(actor,committed))
                throw new InvalidOperationException("Declared actual pursuits or legal shots unavailable; preserve partial");
            var verb=actor.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            var stance=actor.stances.curStance;int beforeJob=actor.CurJob.loadID;
            var actorStamp=new CombatJobStamp(actor.CurJob);
            var queue=actor.jobs.jobQueue.Select(q=>q.job.loadID).ToArray();
            var enemyStamps=CombatLabState.Enemies.Select(e=>new CombatJobStamp(e.CurJob)).ToArray();
            var enemyQueues=CombatLabState.Enemies.Select(e=>e.jobs.jobQueue.Select(q=>q.job.loadID).ToArray()).ToArray();
            int tick=Find.TickManager.TicksGame;
            string rng=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            float earlierContact=CombatInterceptHelper.ContactTicks(earlier,firstVictim);
            float committedContact=CombatInterceptHelper.ContactTicks(committed,buddy);
            float aim=verb.verbProps.warmupTime*60f*actor.GetStatValue(StatDefOf.AimingDelayFactor);
            float burst=Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots;
            float cooldown=actor.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f;
            float locked=CombatInterceptHelper.MovementLockTicks(actor);
            float flight=CombatInterceptMath.NativeFlightTicks(actor.Position.DistanceTo(earlier.Position),
                verb.verbProps.defaultProjectile.projectile.SpeedTilesPerTick);
            var boundary=typeof(CombatControlHelper).GetMethod("EarlierPursuitOpportunity",BindingFlags.Static|BindingFlags.NonPublic);
            bool? explicitOpportunity=boundary==null?(bool?)null:(bool)boundary.Invoke(null,new object[]{actor,earlier,committed});
            var method=typeof(CombatControlHelper).GetMethod("GroupTarget",BindingFlags.Static|BindingFlags.NonPublic);
            var chosen=covered?CombatControlHelper.AvailableFiringTarget(actor,committed):
                (Pawn)method.Invoke(null,new object[]{actor,CombatLabState.Enemies.ToList(),committed});
            var math=typeof(CombatInterceptMath).GetMethod("ShareThenDefend",BindingFlags.Static|BindingFlags.Public);
            bool? ownResponseFits=math==null?(bool?)null:(bool)math.Invoke(null,new object[]{earlierContact,locked,aim,burst,cooldown,flight});
            var readyOwn=CombatInterceptHelper.ReadyCover(actor,earlier).Select(g=>new{pawn=g.thingIDNumber,
                stance=g.stances.curStance.GetType().Name,aimed=(g.stances.curStance as Stance_Busy)?.focusTarg.Thing?.thingIDNumber}).ToArray();
            bool requested=false,accepted=false;
            Job attack=null;
            if(chosen!=null && chosen!=committed)
            {
                requested=true;attack=JobMaker.MakeJob(JobDefOf.AttackStatic,chosen);attack.playerForced=true;
                accepted=CombatOrderHelper.Take(actor,ref attack);
            }
            bool observed=accepted && attack!=null && CombatOrderHelper.Owned(actor,attack)
                && (actor.CurJob==attack || actor.jobs.jobQueue.Any(q=>q.job==attack));
            string after=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            return new{native_process_id=CombatLabState.ProcessId,native_instance_id=CombatLabState.InstanceId,
                scenario=CombatLabState.Scenario,own_response_fits=ownResponseFits,actual_own_cover=readyOwn,self_pursuit=self,covered_fixture=covered,tick,actor=actor.thingIDNumber,buddy=buddy.thingIDNumber,explicit_earlier_opportunity=explicitOpportunity,
                earlier=earlier.thingIDNumber,committed=committed.thingIDNumber,chosen=chosen?.thingIDNumber,
                earlier_contact=earlierContact,committed_contact=committedContact,
                loaded_aim=aim,loaded_burst=burst,loaded_cooldown=cooldown,loaded_flight=flight,
                own_lock_before=locked,own_lock_after=CombatInterceptHelper.MovementLockTicks(actor),
                fresh_full_window=locked+aim+burst+flight+30f,
                deferred_full_window=locked+aim+burst+cooldown+aim+burst+flight+30f,
                warming_before=stance is Stance_Warmup,stance_preserved=actor.stances.curStance==stance,
                before_job_id=beforeJob,after_job_id=actor.CurJob?.loadID,
                actor_job_unchanged=actorStamp.Value!=null && actorStamp.Value==actor.CurJob,
                actor_queue_unchanged=queue.SequenceEqual(actor.jobs.jobQueue.Select(q=>q.job.loadID)),
                assignment_requested=requested,assignment_accepted=accepted,accepted_job_observed=observed,
                accepted_target=attack?.targetA.Thing?.thingIDNumber,
                enemy_jobs_unchanged=CombatLabState.Enemies.Select((e,i)=>enemyStamps[i].Value==e.CurJob).All(v=>v),
                enemy_queues_unchanged=CombatLabState.Enemies.Select((e,i)=>enemyQueues[i].SequenceEqual(e.jobs.jobQueue.Select(q=>q.job.loadID))).All(v=>v),
                group_reviews=CombatControlHelper.GroupFocusReviews.ToArray(),
                rng_before=rng,rng_after=after,rng_unchanged=rng==after,tick_unchanged=tick==Find.TickManager.TicksGame,
                meaning="Actual production target selection and optional normal native AttackStatic only. Initial jobs/stances declared before held baseline. Zero ticks during probe; no shot, hit, suppression or whole-raid credit."};
        }
    }
}
#endif

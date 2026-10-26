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
    // Only a declared held-clock target-selection contract, never raid credit.
    public static class CombatLabFocusRecoveryProbe
    {
        private static bool used;
        public static object Run()
        {
            if(used || !CombatLabState.Scenario.StartsWith("focus_recovery_ranged_",StringComparison.Ordinal)
                || !CombatLabState.HoldInitial || CombatLabState.StepTicks!=0
                || Find.TickManager.CurTimeSpeed!=TimeSpeed.Paused
                || CombatLabState.Allies.Count!=3 || CombatLabState.Enemies.Count!=2)
                throw new InvalidOperationException("Focus recovery requires the exact unused held fixture");
            used=true;
            var actor=CombatLabState.Allies[0];var buddy=CombatLabState.Allies[1];
            var earlier=CombatLabState.Enemies[0];var committed=CombatLabState.Enemies[1];
            bool warming=CombatLabState.Scenario.EndsWith("_warmup_contract",StringComparison.Ordinal);
            if(!CombatInterceptHelper.CanShootNow(actor,earlier) || !CombatInterceptHelper.CanShootNow(actor,committed)
                || CombatLabState.Enemies.Any(e=>e.CurJobDef!=JobDefOf.AttackStatic || e.CurJob.targetA.Thing!=buddy)
                || CombatLabState.Allies.Any(g=>g.CurJobDef!=JobDefOf.AttackStatic || g.CurJob.targetA.Thing!=committed
                    || (warming?!(g.stances.curStance is Stance_Warmup):!(g.stances.curStance is Stance_Cooldown))))
                throw new InvalidOperationException("Declared native jobs, stances or legal shots differ; preserve partial");
            var stance=actor.stances.curStance;int beforeJob=actor.CurJob.loadID;
            var actorStamp=new CombatJobStamp(actor.CurJob);
            var queue=actor.jobs.jobQueue.Select(q=>q.job.loadID).ToArray();
            var enemyStamps=CombatLabState.Enemies.Select(e=>new CombatJobStamp(e.CurJob)).ToArray();
            var enemyQueues=CombatLabState.Enemies.Select(e=>e.jobs.jobQueue.Select(q=>q.job.loadID).ToArray()).ToArray();
            int tick=Find.TickManager.TicksGame;
            string rng=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            float locked=CombatInterceptHelper.MovementLockTicks(actor);
            var method=typeof(CombatControlHelper).GetMethod("GroupTarget",BindingFlags.Static|BindingFlags.NonPublic);
            var chosen=(Pawn)method.Invoke(null,new object[]{actor,CombatLabState.Enemies.ToList(),committed});
            bool requested=false,accepted=false;Job attack=null;
            if(chosen!=null && chosen!=committed)
            {
                requested=true;attack=JobMaker.MakeJob(JobDefOf.AttackStatic,chosen);attack.playerForced=true;
                accepted=CombatOrderHelper.Take(actor,ref attack);
            }
            bool observed=accepted && attack!=null && CombatOrderHelper.Owned(actor,attack)
                && (actor.CurJob==attack || actor.jobs.jobQueue.Any(q=>q.job==attack));
            string after=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            return new{native_process_id=CombatLabState.ProcessId,native_instance_id=CombatLabState.InstanceId,
                scenario=CombatLabState.Scenario,tick,actor=actor.thingIDNumber,buddy=buddy.thingIDNumber,
                earlier=earlier.thingIDNumber,committed=committed.thingIDNumber,chosen=chosen?.thingIDNumber,
                own_lock_before=locked,own_lock_after=CombatInterceptHelper.MovementLockTicks(actor),
                warming_before=warming,stance_preserved=actor.stances.curStance==stance,
                before_job_id=beforeJob,after_job_id=actor.CurJob?.loadID,
                actor_job_unchanged=actorStamp.Value!=null && actorStamp.Value==actor.CurJob,
                actor_queue_unchanged=queue.SequenceEqual(actor.jobs.jobQueue.Select(q=>q.job.loadID)),
                assignment_requested=requested,assignment_accepted=accepted,accepted_job_observed=observed,
                accepted_target=attack?.targetA.Thing?.thingIDNumber,
                enemy_jobs_unchanged=CombatLabState.Enemies.Select((e,i)=>enemyStamps[i].Value==e.CurJob).All(v=>v),
                enemy_queues_unchanged=CombatLabState.Enemies.Select((e,i)=>enemyQueues[i].SequenceEqual(e.jobs.jobQueue.Select(q=>q.job.loadID))).All(v=>v),
                group_reviews=CombatControlHelper.GroupFocusReviews.ToArray(),
                rng_before=rng,rng_after=after,rng_unchanged=rng==after,tick_unchanged=tick==Find.TickManager.TicksGame,
                meaning="Actual production group selection and optional ordinary native AttackStatic. Declared initial jobs/stances before held baseline, zero ticks, no shot/hit/raid credit. Native cooldown must remain intact."};
        }
    }
}
#endif

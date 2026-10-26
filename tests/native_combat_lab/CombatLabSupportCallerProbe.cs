#if LAYA_COMBAT_LAB
using System;
using System.Linq;
using RIMAPI.Helpers;
using RimWorld;
using Verse;
using Verse.AI;
namespace RIMAPI.Controllers
{
    public static class CombatLabSupportCallerProbe
    {
        private static bool used;
        public static object Run()
        {
            if(used || (CombatLabState.Scenario!="support_window_safe_contract" && CombatLabState.Scenario!="support_window_unsafe_contract")
                || !CombatLabState.HoldInitial || CombatLabState.StepTicks!=0 || CombatLabState.Allies.Count!=2 || CombatLabState.Enemies.Count!=1
                || Find.TickManager.CurTimeSpeed!=TimeSpeed.Paused || Find.TickManager.TicksGame%15!=0)
                throw new InvalidOperationException("Exact unused held support caller fixture required");
            used=true;
            var actor=CombatLabState.Allies[0];var buddy=CombatLabState.Allies[1];var enemy=CombatLabState.Enemies[0];
            var verb=actor.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            if(enemy.CurJobDef!=JobDefOf.AttackMelee || enemy.CurJob.targetA.Thing!=buddy
                || CombatInterceptHelper.Pursuing(enemy,actor) || !verb.CanHitTargetFrom(actor.Position,enemy)
                || CombatInterceptHelper.FriendlyLaneClear(actor,enemy,actor.Position))
                throw new InvalidOperationException("Actual other-ally pursuit and blocked friendly lane required");
            int tick=Find.TickManager.TicksGame,jobId=actor.CurJob.loadID;
            var actorStamp=new CombatJobStamp(actor.CurJob);var actorQueue=actor.jobs.jobQueue.Select(q=>q.job.loadID).ToArray();
            var others=new[]{buddy,enemy};var stamps=others.Select(p=>new CombatJobStamp(p.CurJob)).ToArray();
            var queues=others.Select(p=>p.jobs.jobQueue.Select(q=>q.job.loadID).ToArray()).ToArray();
            string rng=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            // Actual ordinary controller entry, including earlier safety
            // guards. Do not call the successful private support method first.
            CombatControlHelper.Tick();
            bool moved=actor.CurJobDef==JobDefOf.Goto && CombatOrderHelper.Owned(actor,actor.CurJob)
                && CombatControlHelper.TestMode(actor)=="support";
            return new{native_process_id=CombatLabState.ProcessId,native_instance_id=CombatLabState.InstanceId,tick,
                scenario=CombatLabState.Scenario,actor=actor.thingIDNumber,buddy=buddy.thingIDNumber,enemy=enemy.thingIDNumber,
                production_tick_called=true,actual_other_ally_pursuit=CombatInterceptHelper.Pursuing(enemy,buddy),
                accepted=moved,accepted_job_observed=moved,actor_job=actor.CurJobDef?.defName,
                actor_job_owned=CombatOrderHelper.Owned(actor,actor.CurJob),mode=CombatControlHelper.TestMode(actor),
                goal_x=actor.CurJob?.targetA.Cell.x,goal_z=actor.CurJob?.targetA.Cell.z,
                queued_selected_target=actor.jobs.jobQueue.Any(q=>q.job.def==JobDefOf.AttackStatic && q.job.targetA.Thing==enemy),
                actor_job_unchanged=actorStamp.Value==actor.CurJob,actor_queue_unchanged=actorQueue.SequenceEqual(actor.jobs.jobQueue.Select(q=>q.job.loadID)),
                enemy_job_unchanged=stamps[1].Value==enemy.CurJob,enemy_queue_unchanged=queues[1].SequenceEqual(enemy.jobs.jobQueue.Select(q=>q.job.loadID)),
                buddy_job_unchanged=stamps[0].Value==buddy.CurJob,buddy_queue_unchanged=queues[0].SequenceEqual(buddy.jobs.jobQueue.Select(q=>q.job.loadID)),
                window_reviews=CombatControlHelper.SupportWindowReviews.ToArray(),
                rng_before=rng,rng_after=CombatLabState.RandomProperty.GetValue(null,null).ToString(),
                rng_unchanged=rng==CombatLabState.RandomProperty.GetValue(null,null).ToString(),tick_unchanged=tick==Find.TickManager.TicksGame,
                meaning="Ordinary production controller entry on existing held native geometry; no ticks, travel, shots or raid outcome credited. Enemy AI, physics and stats unchanged after baseline."};
        }
    }
}
#endif

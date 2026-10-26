#if LAYA_COMBAT_LAB
using System;
using System.Linq;
using RIMAPI.Helpers;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Controllers
{
    public static class CombatLabSupportWindowProbe
    {
        private static bool used;
        public static object Run()
        {
            bool continuing=CombatLabState.Scenario.Contains("_continue_") || CombatLabState.Scenario.Contains("_foreign_");
            if(used || !CombatLabState.Scenario.StartsWith("support_window_",StringComparison.Ordinal)
                || (continuing?CombatLabState.StepTicks!=7:!CombatLabState.HoldInitial || CombatLabState.StepTicks!=0)
                || Find.TickManager.CurTimeSpeed!=TimeSpeed.Paused
                || CombatLabState.Allies.Count!=2 || CombatLabState.Enemies.Count!=1)
                throw new InvalidOperationException("Support window requires its exact unused held native fixture");
            used=true;
            var actor=CombatLabState.Allies[0];var buddy=CombatLabState.Allies[1];var enemy=CombatLabState.Enemies[0];
            if(enemy.CurJobDef!=JobDefOf.AttackMelee || enemy.CurJob.targetA.Thing!=buddy || !enemy.pather.Moving
                || CombatInterceptHelper.Pursuing(enemy,actor) || !continuing && CombatInterceptHelper.CanShootNow(actor,enemy))
                throw new InvalidOperationException("Declared blocked support lane or actual other-ally pursuit unavailable; preserve partial");
            if(continuing && (actor.CurJobDef!=JobDefOf.Goto || !actor.pather.Moving || !CombatOrderHelper.Owned(actor,actor.CurJob)))
                throw new InvalidOperationException("Declared ongoing owned support move unavailable; preserve partial");
            int tick=Find.TickManager.TicksGame,jobId=actor.CurJob.loadID;
            int? beforeGoalX=continuing?(int?)actor.CurJob.targetA.Cell.x:null,beforeGoalZ=continuing?(int?)actor.CurJob.targetA.Cell.z:null;
            var actorPathBefore=actor.pather.curPath;bool actorPathFound=actorPathBefore?.Found==true;
            int actorNodes=actorPathBefore?.NodesLeftCount ?? 0;
            float actorNextCost=actor.pather.nextCellCostLeft,actorNextTotal=actor.pather.nextCellCostTotal;
            int foreignQueue=pawnForeignQueue(actor);
            var stamp=new CombatJobStamp(actor.CurJob);var queue=actor.jobs.jobQueue.Select(q=>q.job.loadID).ToArray();
            var enemyStamp=new CombatJobStamp(enemy.CurJob);var enemyQueue=enemy.jobs.jobQueue.Select(q=>q.job.loadID).ToArray();
            string rng=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            var verb=actor.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            float aim=verb.verbProps.warmupTime*60f*actor.GetStatValue(StatDefOf.AimingDelayFactor);
            float burst=Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots;
            float ownLock=CombatInterceptHelper.MovementLockTicks(actor),enemyLock=CombatInterceptHelper.MovementLockTicks(enemy);
            bool accepted=CombatControlHelper.TestContactSupport(actor,out var move);
            bool observed=accepted && move!=null && CombatOrderHelper.Owned(actor,move)
                && (actor.CurJob==move || actor.jobs.jobQueue.Any(q=>q.job==move));
            float? travel=null,potentialContact=null,flight=null,required=null;
            if(move!=null)
            {
                using(var actorPath=actor.Map.pathFinder.FindPathNow(actor.Position,move.targetA.Cell,actor,null,PathEndMode.OnCell))
                using(var enemyPath=actor.Map.pathFinder.FindPathNow(enemy.Position,move.targetA.Cell,enemy,null,PathEndMode.Touch))
                {
                    if(!actorPath.Found || !enemyPath.Found)throw new InvalidOperationException("Accepted support diagnostic path unavailable; preserve partial");
                    travel=actorPath.TotalCost;potentialContact=enemyPath.TotalCost+enemyLock;
                    flight=CombatInterceptMath.NativeFlightTicks(move.targetA.Cell.DistanceTo(enemy.Position),verb.verbProps.defaultProjectile.projectile.SpeedTilesPerTick);
                    required=travel+ownLock+aim+burst+flight+30f;
                }
            }
            string after=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            return new{native_process_id=CombatLabState.ProcessId,native_instance_id=CombatLabState.InstanceId,tick,
                scenario=CombatLabState.Scenario,actor=actor.thingIDNumber,buddy=buddy.thingIDNumber,enemy=enemy.thingIDNumber,
                actual_other_ally_pursuit=CombatInterceptHelper.Pursuing(enemy,buddy),actual_actor_pursuit=CombatInterceptHelper.Pursuing(enemy,actor),
                loaded_aim=aim,loaded_burst=burst,own_lock=ownLock,enemy_lock=enemyLock,
                accepted,accepted_job_observed=observed,goal_x=move?.targetA.Cell.x,goal_z=move?.targetA.Cell.z,
                continuing,declared_native_steps=CombatLabState.StepTicks,before_goal_x=beforeGoalX,before_goal_z=beforeGoalZ,
                before_actor_native_path_found=actorPathFound,before_actor_nodes_left=actorNodes,
                before_actor_next_cost=actorNextCost,before_actor_next_cost_total=actorNextTotal,
                before_foreign_queue_count=foreignQueue,
                old_owned_job_absent=actor.CurJob?.loadID!=jobId && !actor.jobs.jobQueue.Any(q=>q.job.loadID==jobId),
                move_job_id=move?.loadID,accepted_path_cost=travel,potential_native_contact=potentialContact,
                loaded_native_flight=flight,required_first_burst_window=required,
                potential_contact_precedes_window=potentialContact.HasValue && potentialContact<=required,
                before_actor_job_id=jobId,after_actor_job_id=actor.CurJob?.loadID,
                actor_job_unchanged=stamp.Value!=null && stamp.Value==actor.CurJob,
                actor_queue_unchanged=queue.SequenceEqual(actor.jobs.jobQueue.Select(q=>q.job.loadID)),
                enemy_job_unchanged=enemyStamp.Value==enemy.CurJob,
                enemy_queue_unchanged=enemyQueue.SequenceEqual(enemy.jobs.jobQueue.Select(q=>q.job.loadID)),
                window_reviews=CombatControlHelper.SupportWindowReviews.ToArray(),
                rng_before=rng,rng_after=after,rng_unchanged=rng==after,tick_unchanged=tick==Find.TickManager.TicksGame,
                meaning="Actual production support selection/job only. Native enemy-to-goal path is a potential retarget contact bound, not a forced enemy order. Zero ticks during probe. Declared earlier native physics steps are reported separately; no shot/outcome credit."};
        }
        private static int pawnForeignQueue(Pawn pawn)=>pawn.jobs.jobQueue.Count(q=>!CombatOrderHelper.Owned(pawn,q.job));
    }
}
#endif

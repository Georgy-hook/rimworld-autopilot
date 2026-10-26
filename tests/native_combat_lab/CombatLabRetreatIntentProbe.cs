#if LAYA_COMBAT_LAB
using System;
using System.Linq;
using RIMAPI.Helpers;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Controllers
{
    public static class CombatLabRetreatIntentProbe
    {
        private static bool used;
        public static object Run()
        {
            if(used || !CombatLabState.Scenario.StartsWith("retreat_intent_",StringComparison.Ordinal)
                || !CombatLabState.HoldInitial || CombatLabState.StepTicks!=0
                || CombatLabState.Allies.Count!=(CombatLabState.Scenario=="retreat_intent_uncovered_contract"?1:3) || CombatLabState.Enemies.Count!=1)
                throw new InvalidOperationException("Retreat intent requires its unused exact held native fixture");
            used=true;
            var actor=CombatLabState.Allies[0];var enemy=CombatLabState.Enemies[0];
            bool furniture=CombatLabState.Scenario=="retreat_intent_furniture_contract";
            bool window=CombatLabState.Scenario=="retreat_intent_uncovered_contract" || CombatLabState.Scenario=="retreat_intent_covered_contract";
            bool formation=CombatLabState.Scenario.StartsWith("retreat_intent_formation",StringComparison.Ordinal);
            if(enemy.CurJobDef!=JobDefOf.AttackMelee || actor.Position.DistanceTo(enemy.Position)!=(formation?12f:window?25f:4f)
                || furniture!=(enemy.CurJob.targetA.Thing is Building)
                || !furniture && enemy.CurJob.targetA.Thing!=actor)
                throw new InvalidOperationException("Native initial attack intent differs; preserve partial");
            int tick=Find.TickManager.TicksGame,actorJobId=actor.CurJob?.loadID ?? -1,enemyJobId=enemy.CurJob.loadID;
            var actorStamp=new CombatJobStamp(actor.CurJob);var enemyStamp=new CombatJobStamp(enemy.CurJob);
            var actorQueue=actor.jobs.jobQueue.Select(q=>q.job.loadID).ToArray();
            var enemyQueue=enemy.jobs.jobQueue.Select(q=>q.job.loadID).ToArray();
            var target=enemy.CurJob.targetA.Thing;
            var cover=CombatInterceptHelper.ReadyCover(actor,enemy).Select(p=>p.thingIDNumber).ToArray();
            if(CombatLabState.Scenario=="retreat_intent_uncovered_contract"?cover.Length!=0:cover.Length<2)
                throw new InvalidOperationException("Declared native supporting gun jobs unavailable; preserve partial");
            string rng=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            float before=CombatInterceptHelper.ContactTicks(enemy,actor);
            float ownLock=actor.stances.curStance is Stance_Warmup?0f:CombatInterceptHelper.MovementLockTicks(actor);
            float enemyLock=CombatInterceptHelper.MovementLockTicks(enemy);
            float stationaryPathContact;
            using(var stationaryPath=actor.Map.pathFinder.FindPathNow(enemy.Position,actor.Position,enemy,null,PathEndMode.Touch))
            {
                if(!stationaryPath.Found)throw new InvalidOperationException("Native stationary contact path unavailable; preserve partial");
                stationaryPathContact=stationaryPath.TotalCost+enemyLock;
            }
            var verb=actor.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            float cycle=verb.verbProps.warmupTime*60f*actor.GetStatValue(StatDefOf.AimingDelayFactor)
                +Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots
                +actor.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f;
            bool shotBefore=CombatInterceptHelper.CanShootNow(actor,enemy);
            bool accepted=CombatControlHelper.TryRangedRetreat(actor,enemy,actor.Position,out var move);
            bool observed=accepted && move!=null && CombatOrderHelper.Owned(actor,move)
                && (actor.CurJob==move || actor.jobs.jobQueue.Any(q=>q.job==move));
            float? travel=null,afterArrival=null,extension=null,net=null;
            int[] crossed=new int[0];
            if(move!=null)
            {
                using(var actorPath=actor.Map.pathFinder.FindPathNow(actor.Position,move.targetA.Cell,actor,null,PathEndMode.OnCell))
                using(var enemyPath=actor.Map.pathFinder.FindPathNow(enemy.Position,move.targetA.Cell,enemy,null,PathEndMode.Touch))
                {
                    if(!actorPath.Found || !enemyPath.Found)throw new InvalidOperationException("Accepted goal diagnostic path unavailable; preserve partial");
                    travel=actorPath.TotalCost;
                    afterArrival=enemyPath.TotalCost+enemyLock-actorPath.TotalCost-ownLock;
                    extension=afterArrival+actorPath.TotalCost+ownLock-before;net=afterArrival-before;
                    crossed=CombatLabState.Allies.Where(p=>p!=actor && p.Spawned && !p.Dead
                        && p.Position.DistanceTo(enemy.Position)>2.1f
                        && enemyPath.NodesReversed.Any(c=>c.InHorDistOf(p.Position,1.5f))).Select(p=>p.thingIDNumber).ToArray();
                }
            }
            string after=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            return new{native_process_id=CombatLabState.ProcessId,native_instance_id=CombatLabState.InstanceId,tick,
                scenario=CombatLabState.Scenario,actor=actor.thingIDNumber,enemy=enemy.thingIDNumber,
                enemy_job="AttackMelee",observed_target_id=target.thingIDNumber,observed_target_def=target.def.defName,
                actual_actor_pursuit=CombatInterceptHelper.Pursuing(enemy,actor),native_legal_supporting_guns=cover,
                native_current_shot_before=shotBefore,before_contact=before,own_movement_lock=ownLock,enemy_movement_lock=enemyLock,
                loaded_full_cycle=cycle,accepted_path_cost=travel,after_arrival_contact=afterArrival,
                total_contact_extension=extension,net_stationary_window_change=net,additional_diagnostic_paths=move!=null?3:1,
                enemy_route_contact_ally_ids=crossed,
                native_stationary_path_contact=stationaryPathContact,
                same_path_stationary_window_change=afterArrival-stationaryPathContact,
                diagnostic_stationary_path_calls=1,
                escape_window_reviews=CombatControlHelper.EscapeWindowRefusals.ToArray(),
                accepted,accepted_job_observed=observed,move_job_id=move?.loadID,goal_x=move?.targetA.Cell.x,goal_z=move?.targetA.Cell.z,
                before_actor_job_id=actorJobId,after_actor_job_id=actor.CurJob?.loadID,
                actor_job_unchanged=actorStamp.Value==actor.CurJob,
                actor_queue_unchanged=actorQueue.SequenceEqual(actor.jobs.jobQueue.Select(q=>q.job.loadID)),
                enemy_job_unchanged=enemyStamp.Value==enemy.CurJob && enemy.CurJob.loadID==enemyJobId,
                enemy_queue_unchanged=enemyQueue.SequenceEqual(enemy.jobs.jobQueue.Select(q=>q.job.loadID)),
                rng_before=rng,rng_after=after,rng_unchanged=rng==after,tick_unchanged=Find.TickManager.TicksGame==tick,
                meaning="Actual production retreat decision and native accepted job or unchanged job. Supporting gun jobs are legal, not proof of shots. No movement, arrival, injury avoidance or raid-win credit."};
        }
    }
}
#endif

#if LAYA_COMBAT_LAB
using System;
using System.Collections;
using System.Linq;
using System.Reflection;
using RIMAPI.Helpers;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Controllers
{
    // One production admission on an explicitly prepared held-clock cohort.
    // This diagnostic does not relocate targets or alter their paths/stats.
    public static class CombatLabCoverShotProbe
    {
        private static bool used;
        public static object Run()
        {
            bool prepared=CombatLabState.Scenario.StartsWith("cover_window_",StringComparison.Ordinal)
                && !CombatLabState.HoldInitial && CombatLabState.StepTicks==30;
            bool initial=CombatLabState.Scenario=="cover_handoff_contract" && CombatLabState.HoldInitial && CombatLabState.StepTicks==0;
            if(used || !(prepared || initial) || CombatLabState.Allies.Count!=2 || CombatLabState.Enemies.Count!=2)
                throw new InvalidOperationException("Cover shot probe needs its unused held fixture");
            used=true;
            var actor=CombatLabState.Allies[0];var target=CombatLabState.Enemies[1];
            var flags=BindingFlags.NonPublic|BindingFlags.Static;var type=typeof(CombatControlHelper);
            var plans=(IDictionary)type.GetField("Plans",flags).GetValue(null);var plan=plans[actor.thingIDNumber];
            if(plan==null)throw new InvalidOperationException("Initial selected plan absent");
            var job=new CombatJobStamp(actor.CurJob);var queue=actor.jobs.jobQueue.Select(q=>q.job.loadID).ToArray();
            var others=CombatLabState.Allies.Skip(1).Concat(CombatLabState.Enemies).ToArray();
            var jobs=others.Select(p=>new CombatJobStamp(p.CurJob)).ToArray();
            var queues=others.Select(p=>p.jobs.jobQueue.Select(q=>q.job.loadID).ToArray()).ToArray();
            int tick=Find.TickManager.TicksGame;var origin=actor.Position;
            string rng=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            var verb=actor.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            float initialLock=CombatInterceptHelper.MovementLockTicks(actor);
            float initialExposure=CombatControlHelper.IncomingRangedExposure(actor,actor.Position);
            var initialShots=CombatLabState.Enemies.Select(e=>new{pawn=e.thingIDNumber,x=e.Position.x,z=e.Position.z,weapon=e.equipment.Primary.def.defName,
                actual_hit=verb.CanHitTargetFrom(origin,e),can_shoot_now=CombatInterceptHelper.CanShootNow(actor,e),
                interior=CombatInterceptHelper.InteriorShotWindow(actor,e)}).ToArray();
            bool applied=(bool)type.GetMethod("TryTakeCoveredShot",flags).Invoke(null,new object[]{plan,target});
            bool admissionJobPreserved=job.Value==actor.CurJob;
            bool admissionQueuePreserved=queue.SequenceEqual(actor.jobs.jobQueue.Select(q=>q.job.loadID));
            string admissionRng=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            var goal=applied?actor.CurJob.targetA.Cell:origin;
            float travel=0;
            using(var path=actor.Map.pathFinder.FindPathNow(origin,goal,actor,null,PathEndMode.OnCell))travel=path.TotalCost;
            float aim=verb.verbProps.warmupTime*60f*actor.GetStatValue(StatDefOf.AimingDelayFactor);
            float burst=Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots;
            var projectile=verb.verbProps.defaultProjectile.projectile;
            float flight=CombatInterceptMath.NativeFlightTicks(verb.verbProps.range,projectile.SpeedTilesPerTick);
            float arrival=CombatInterceptHelper.MovementLockTicks(actor)+travel;
            var future=new[]{arrival,arrival+aim,arrival+aim+burst+flight+30f}.Select(h=>
            {
                bool available=CombatInterceptHelper.TryObservedFuturePosition(target,h,out var cell);
                return new{horizon=h,available,x=cell.x,z=cell.z,
                    origin_hit=available?CombatExposureHelper.CanHitPawnAt(verb,target,origin,cell):null,
                    goal_hit=available?CombatExposureHelper.CanHitPawnAt(verb,target,goal,cell):null,
                    goal_friendly_clear=available && CombatInterceptHelper.FutureFriendlyLaneClear(actor,target,goal,cell,"cover_shot_probe")};
            }).ToArray();
            var windowMethod=type.GetMethod("CoverShotWindow",flags);
            bool? checkedWindow=windowMethod==null?(bool?)null:(bool)windowMethod.Invoke(null,new object[]{actor,target,goal,travel});
            bool fallback=false;
            if(!applied && CombatLabState.Scenario=="cover_window_crossfire_contract")
            {
                // The ordinary selected-target AttackStatic fallback is the
                // same action used after a rejected cover admission. This
                // isolated contract does not claim to run the whole director.
                var attack=JobMaker.MakeJob(JobDefOf.AttackStatic,target);attack.playerForced=true;
                fallback=CombatOrderHelper.Take(actor,ref attack);
            }
            string after=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            return new{native_process_id=CombatLabState.ProcessId,native_instance_id=CombatLabState.InstanceId,
                tick,actor=actor.thingIDNumber,target=target.thingIDNumber,applied,origin_x=origin.x,origin_z=origin.z,
                goal_x=goal.x,goal_z=goal.z,travel,aim,burst,flight,checked_window=checkedWindow,initial_lock=initialLock,initial_exposure=initialExposure,initial=initialShots,future,
                actor_job=actor.CurJobDef.defName,actor_urgency=actor.CurJob.locomotionUrgency.ToString(),
                actor_queue=actor.jobs.jobQueue.Select(q=>new{job=q.job.def.defName,target=q.job.targetA.Thing?.thingIDNumber}).ToArray(),
                actor_job_preserved=admissionJobPreserved,actor_queue_preserved=admissionQueuePreserved,fallback_attack_applied=fallback,
                other_jobs_preserved=others.Select((p,i)=>jobs[i].Value==p.CurJob && queues[i].SequenceEqual(p.jobs.jobQueue.Select(q=>q.job.loadID))).All(x=>x),
                rng_before=rng,rng_after_admission=admissionRng,rng_after=after,rng_unchanged=rng==admissionRng,tick_unchanged=tick==Find.TickManager.TicksGame,
                limits="One actual production cover admission, observed native target route and future native Pawn geometry. Forecast is not arrival or a projectile; physics followup is recorded separately."};
        }
    }
}
#endif

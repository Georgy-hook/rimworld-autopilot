#if LAYA_COMBAT_LAB
using System;
using System.Linq;
using System.Collections;
using System.Reflection;
using RIMAPI.Helpers;
using RimWorld;
using Verse;
using Verse.AI;
namespace RIMAPI.Controllers
{
    public static class CombatLabFriendlySupportProbe
    {
        private static bool used;
        public static object Run()
        {
            if(used || CombatLabState.Scenario!="friendly_fan_support_contract" || !CombatLabState.HoldInitial || CombatLabState.StepTicks!=0)
                throw new InvalidOperationException("Unused held short support angle required");
            used=true;var actor=CombatLabState.Allies[0];var ally=CombatLabState.Allies[1];var target=CombatLabState.Enemies[0];
            var verb=actor.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            int tick=Find.TickManager.TicksGame;string rng=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            var others=CombatLabState.Allies.Skip(1).Concat(CombatLabState.Enemies).ToArray();
            var jobs=others.Select(p=>new CombatJobStamp(p.CurJob)).ToArray();
            bool direct=CombatInterceptHelper.CanShootNow(actor,target),lane=CombatInterceptHelper.FriendlyLaneClear(actor,target,actor.Position);
            bool alternate=CombatInterceptHelper.CanShootNow(actor,CombatLabState.Enemies[1]);
            var flags=BindingFlags.NonPublic|BindingFlags.Static;var type=typeof(CombatControlHelper);
            var plans=(IDictionary)type.GetField("Plans",flags).GetValue(null);var plan=plans[actor.thingIDNumber];
            if(plan==null)throw new InvalidOperationException("Declared selected gun plan missing");
            bool applied=(bool)type.GetMethod("ReviewUnsafeFriendlyLane",flags).Invoke(null,new object[]{plan,CombatLabState.Enemies.ToList()});
            bool positioned=applied && actor.CurJobDef==JobDefOf.Goto;
            var goal=positioned?actor.CurJob.targetA.Cell:actor.Position;
            return new{native_process_id=CombatLabState.ProcessId,native_instance_id=CombatLabState.InstanceId,tick,
                actor=actor.thingIDNumber,ally=ally.thingIDNumber,target=target.thingIDNumber,direct,lane,alternate_safe_shot=alternate,
                target_actual_victim=CombatControlHelper.ObservedVictim(target)?.thingIDNumber,
                positioned,ordered=applied,goal_x=goal.x,goal_z=goal.z,
                actor_job=actor.CurJobDef?.defName,actor_urgency=actor.CurJob?.locomotionUrgency.ToString(),
                queued_selected_target=actor.jobs.jobQueue.Any(q=>q.job.def==JobDefOf.AttackStatic && q.job.targetA.Thing==target),
                native_direct_los=verb.CanHitTargetFrom(actor.Position,target),
                other_jobs_preserved=others.Select((p,i)=>jobs[i].Value==p.CurJob).All(x=>x),
                rng_before=rng,rng_after=CombatLabState.RandomProperty.GetValue(null,null).ToString(),tick_unchanged=tick==Find.TickManager.TicksGame,
                limits="One production friendly-lane review; declared initial target attacks an ally. Ordinary native job/queue only, no forced projectile, hit, enemy AI or stat changes after baseline."};
        }
    }
}
#endif

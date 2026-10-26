#if LAYA_COMBAT_LAB
using System;
using System.Linq;
using RIMAPI.Helpers;
using RimWorld;
using Verse;
using Verse.AI;
namespace RIMAPI.Controllers
{
    public static class CombatLabFriendlyFanProbe
    {
        private static bool used;
        public static object Run()
        {
            if(CombatLabState.Scenario=="friendly_fan_support_contract")return CombatLabFriendlySupportProbe.Run();
            if(used || !CombatLabState.Scenario.StartsWith("friendly_fan_",StringComparison.Ordinal)
                || !CombatLabState.HoldInitial || CombatLabState.StepTicks!=0)
                throw new InvalidOperationException("Unused held friendly fan fixture required");
            used=true;
            var actor=CombatLabState.Allies[0];var ally=CombatLabState.Allies[1];var target=CombatLabState.Enemies[0];
            var verb=actor.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            int tick=Find.TickManager.TicksGame;string rng=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            var others=CombatLabState.Allies.Skip(1).Concat(CombatLabState.Enemies).ToArray();
            var jobs=others.Select(p=>new CombatJobStamp(p.CurJob)).ToArray();
            bool lane=CombatInterceptHelper.FriendlyLaneClear(actor,target,actor.Position);
            bool direct=CombatInterceptHelper.CanShootNow(actor,target);
            bool lineFound=verb.TryFindShootLineFromTo(actor.Position,target,out var line);
            var draw=actor.DrawPos;
            float? radius=lineFound?CombatFriendlyFireHelper.MissRadius(actor,verb,target,actor.Position,line,target):null;
            var goal=actor.Position;bool positioned=false,ordered=false;
            if(!direct)positioned=CombatInterceptHelper.TryPosition(actor,target,out goal);
            if(direct || positioned)
            {
                var attack=JobMaker.MakeJob(JobDefOf.AttackStatic,target);attack.playerForced=true;
                if(positioned)
                {
                    var move=JobMaker.MakeJob(JobDefOf.Goto,goal);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                    ordered=CombatOrderHelper.Take(actor,ref move);
                    if(ordered){actor.jobs.jobQueue.EnqueueLast(attack);CombatControlHelper.RememberMove(actor,move,attack);}
                }
                else ordered=CombatOrderHelper.Take(actor,ref attack);
            }
            return new{tick,actor=actor.thingIDNumber,ally=ally.thingIDNumber,target=target.thingIDNumber,
                native_process_id=CombatLabState.ProcessId,native_instance_id=CombatLabState.InstanceId,
                direct,lane,positioned,ordered,goal_x=goal.x,goal_z=goal.z,
                native_direct_los=verb.CanHitTargetFrom(actor.Position,target),
                line_found=lineFound,line_source_x=line.Source.x,line_source_z=line.Source.z,line_dest_x=line.Dest.x,line_dest_z=line.Dest.z,
                draw_x=draw.x,draw_z=draw.z,maximum_endpoint_radius=radius,
                near_shooter_intercept_factor=VerbUtility.InterceptChanceFactorFromDistance(actor.Position.ToVector3Shifted(),ally.Position),
                actual_origin_intercept_factor=VerbUtility.InterceptChanceFactorFromDistance(draw,ally.Position),
                actor_job=actor.CurJobDef.defName,actor_urgency=actor.CurJob.locomotionUrgency.ToString(),
                other_jobs_preserved=others.Select((p,i)=>jobs[i].Value==p.CurJob).All(x=>x),
                rng_before=rng,rng_after=CombatLabState.RandomProperty.GetValue(null,null).ToString(),tick_unchanged=tick==Find.TickManager.TicksGame,
                limits="One actual safety predicate and ordinary selected-target shot or checked Jog/queued shot; no altered projectile flags, physics, damage, RNG or pawn stats."};
        }
    }
}
#endif

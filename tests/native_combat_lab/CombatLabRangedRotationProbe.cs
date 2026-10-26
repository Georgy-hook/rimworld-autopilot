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
    public static class CombatLabRangedRotationProbe
    {
        private static bool used;
        public static object Run()
        {
            if(used || !CombatLabState.Scenario.StartsWith("ranged_rotation_",StringComparison.Ordinal)
                || CombatLabState.HoldInitial || CombatLabState.StepTicks!=74
                || Find.TickManager.CurTimeSpeed!=TimeSpeed.Paused
                || CombatLabState.Allies.Count!=3 || CombatLabState.Enemies.Count!=2)
                throw new InvalidOperationException("Targeted rotation requires unused paused native74 fixture");
            used=true;
            var actor=CombatLabState.Allies[1];var primary=CombatLabState.Enemies[0];
            var allies=CombatLabState.Allies.ToArray();
            var jobs=allies.Select(p=>new CombatJobStamp(p.CurJob)).ToArray();
            var queues=allies.Select(p=>p.jobs.jobQueue.Select(q=>q.job.loadID).ToArray()).ToArray();
            var stances=allies.Select(p=>p.stances.curStance).ToArray();
            var foeJobs=CombatLabState.Enemies.Select(p=>new CombatJobStamp(p.CurJob)).ToArray();
            var foeQueues=CombatLabState.Enemies.Select(p=>p.jobs.jobQueue.Select(q=>q.job.loadID).ToArray()).ToArray();
            int tick=Find.TickManager.TicksGame;
            string rng=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            var type=typeof(CombatControlHelper);var flags=BindingFlags.NonPublic|BindingFlags.Static;
            var plans=(IDictionary)type.GetField("Plans",flags).GetValue(null);
            var plan=plans[actor.thingIDNumber];
            if(plan==null)throw new InvalidOperationException("Declared selected actor plan absent");
            var targeted=type.GetMethod("ObservedTargetedRangedThreat",flags);
            bool? targetedBoundary=targeted==null?(bool?)null:(bool)targeted.Invoke(null,new object[]{actor,CombatLabState.Enemies.ToList()});
            float exposure=CombatControlHelper.IncomingRangedExposure(actor,actor.Position);
            var cover=CombatInterceptHelper.ReadyCover(actor,primary).Select(g=>new{pawn=g.thingIDNumber,
                shots=CombatLabState.Shots.TryGetValue(g.thingIDNumber,out int count)?count:0,
                target=g.CurJob?.targetA.Thing?.thingIDNumber,stance=g.stances.curStance.GetType().Name}).ToArray();
            bool prior=CombatControlHelper.TestDisabled;bool applied;
            try
            {
                CombatControlHelper.TestDisabled=false;
                applied=(bool)type.GetMethod("TryBreakRangedContact",flags).Invoke(null,new object[]{plan,CombatLabState.Enemies.ToList(),false});
            }
            finally{CombatControlHelper.TestDisabled=prior;}
            var valid=type.GetMethod("Valid",flags);
            var selected=plans.Values.Cast<object>().Where(p=>(bool)valid.Invoke(null,new[]{p}))
                .Select(p=>(Pawn)p.GetType().GetField("Pawn").GetValue(p)).ToArray();
            var anchorCandidates=selected.Where(p=>p.CurJobDef!=JobDefOf.Goto && CombatInterceptHelper.CanShootNow(p,primary))
                .OrderByDescending(p=>p.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb.verbProps.range)
                .ThenBy(p=>CombatControlHelper.IncomingRangedExposure(p,p.Position)).ThenBy(p=>p.thingIDNumber).ToArray();
            var nearCells=GenRadial.RadialCellsAround(actor.Position,4f,false)
                .Where(c=>c.InBounds(actor.Map) && c.Standable(actor.Map) && !c.Fogged(actor.Map)
                    && !c.GetThingList(actor.Map).Any(t=>t is Pawn || t is Building_Trap)
                    && CombatLabState.Enemies.All(e=>c.DistanceTo(e.Position)>=8f))
                .Select(c=>new{x=c.x,z=c.z,exposure=CombatControlHelper.IncomingRangedExposure(actor,c),
                    edifice=c.GetEdifice(actor.Map)?.def.defName}).ToArray();
            var guardInfo=new{
                eligible=(bool)type.GetMethod("Eligible",flags).Invoke(null,new object[]{actor}),
                wounded=(bool)type.GetMethod("CriticalRangedInjury",flags).Invoke(null,new object[]{actor}),
                other_moving=(bool)type.GetMethod("OtherSelectedGunMoving",flags).Invoke(null,new object[]{actor}),
                plan_valid=(bool)valid.Invoke(null,new[]{plan}),
                review_tick=(int)plan.GetType().GetField("RangedCoverReviewTick").GetValue(plan),
                own_stamped_job=plan.GetType().GetProperty("OwnedJob").GetValue(plan,null)==actor.CurJob,
                anchor=anchorCandidates.FirstOrDefault()?.thingIDNumber,
                anchors=anchorCandidates.Select(p=>new{pawn=p.thingIDNumber,exposure=CombatControlHelper.IncomingRangedExposure(p,p.Position)}).ToArray(),
                nearby_melee=CombatLabState.Enemies.Where(e=>(bool)type.GetMethod("MeleeThreat",flags).Invoke(null,new object[]{e}) && e.Position.DistanceTo(actor.Position)<8f).Select(e=>e.thingIDNumber).ToArray()};
            var move=actor.CurJob;
            string after=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            return new{native_process_id=CombatLabState.ProcessId,native_instance_id=CombatLabState.InstanceId,
                scenario=CombatLabState.Scenario,actor=actor.thingIDNumber,primary=primary.thingIDNumber,secondary=CombatLabState.Enemies[1].thingIDNumber,tick,applied,
                current_exposure=exposure,targeted_boundary=targetedBoundary,
                actual_foe_aim=(primary.stances.curStance as Stance_Busy)?.focusTarg.Thing?.thingIDNumber,
                foe_stance=primary.stances.curStance.GetType().Name,
                actor_job=move?.def.defName,actor_urgency=move?.locomotionUrgency.ToString(),
                goal_x=move?.targetA.Cell.x,goal_z=move?.targetA.Cell.z,
                destination_exposure=move?.def==JobDefOf.Goto?(float?)CombatControlHelper.IncomingRangedExposure(actor,move.targetA.Cell):null,
                actor_queue=actor.jobs.jobQueue.Select(q=>new{job=q.job.def.defName,target=q.job.targetA.Thing?.thingIDNumber}).ToArray(),
                cover_before=cover,guardInfo,nearCells,
                actor_job_unchanged=jobs[1].Value==actor.CurJob,actor_queue_unchanged=queues[1].SequenceEqual(actor.jobs.jobQueue.Select(q=>q.job.loadID)),
                actor_stance_preserved=stances[1]==actor.stances.curStance,
                other_jobs_preserved=allies.Select((p,i)=>i==1 || jobs[i].Value==p.CurJob && queues[i].SequenceEqual(p.jobs.jobQueue.Select(q=>q.job.loadID)) && stances[i]==p.stances.curStance).All(v=>v),
                enemy_jobs_preserved=CombatLabState.Enemies.Select((p,i)=>foeJobs[i].Value==p.CurJob && foeQueues[i].SequenceEqual(p.jobs.jobQueue.Select(q=>q.job.loadID))).All(v=>v),
                rng_before=rng,rng_after=after,rng_unchanged=rng==after,tick_unchanged=tick==Find.TickManager.TicksGame,
                withdrawals=CombatControlHelper.RangedWithdrawals.ToArray(),routes=CombatControlHelper.RangedRouteChecks.ToArray(),
                meaning="Native74tick ordinary gun warmup, one production ranged-withdrawal decision and separately observed Jog arrival/queued shot. No movement-stat/urgency/AI/RNG alterations afterbaseline. No raid/model credit."};
        }
    }
}
#endif

#if LAYA_COMBAT_LAB
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RIMAPI.Helpers;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Controllers
{
    public static class CombatLabObservedRouteProbe
    {
        private static bool used;
        public static object Run()
        {
            if(used || !CombatLabState.Scenario.StartsWith("support_window_",StringComparison.Ordinal)
                || (CombatLabState.StepTicks!=0 && CombatLabState.StepTicks!=7)
                || Find.TickManager.CurTimeSpeed!=TimeSpeed.Paused || CombatLabState.Enemies.Count!=1)
                throw new InvalidOperationException("Observed-route read requires exact unused held native fixture");
            used=true;
            var actor=CombatLabState.Allies[0];var enemy=CombatLabState.Enemies[0];
            if(enemy.CurJobDef!=JobDefOf.AttackMelee || !enemy.pather.Moving)
                throw new InvalidOperationException("No declared native moving melee path; preserve partial");
            int tick=Find.TickManager.TicksGame,actorId=actor.CurJob.loadID,enemyId=enemy.CurJob.loadID;
            var actorQueue=actor.jobs.jobQueue.Select(q=>q.job.loadID).ToArray();
            var enemyQueue=enemy.jobs.jobQueue.Select(q=>q.job.loadID).ToArray();
            var path=enemy.pather.curPath;
            int left=path?.NodesLeftCount ?? 0;
            var cells=path?.Found==true?path.NodesReversed.Take(left).Reverse().SkipWhile(c=>c==enemy.Position).ToList():new List<IntVec3>();
            var next=enemy.pather.nextCell;
            if(path?.Found==true && next.IsValid && next!=enemy.Position && (cells.Count==0 || cells[0]!=next))cells.Insert(0,next);
            var actual=cells.ToArray();
            string rng=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            var method=typeof(CombatInterceptHelper).GetMethod("TargetRoute",BindingFlags.NonPublic|BindingFlags.Static);
            var forecast=(List<Tuple<IntVec3,float>>)method.Invoke(null,new object[]{enemy});
            var predicted=forecast?.Skip(1).Select(p=>p.Item1).ToArray() ?? new IntVec3[0];
            bool matches=actual.SequenceEqual(predicted);
            string after=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            return new{native_process_id=CombatLabState.ProcessId,native_instance_id=CombatLabState.InstanceId,tick,
                scenario=CombatLabState.Scenario,enemy=enemy.thingIDNumber,job=enemy.CurJobDef.defName,
                declared_native_steps=CombatLabState.StepTicks,
                native_path_found=path?.Found==true,native_nodes_left=left,
                native_next_x=enemy.pather.nextCell.x,native_next_z=enemy.pather.nextCell.z,
                native_next_cost=enemy.pather.nextCellCostLeft,destination_x=enemy.pather.Destination.Cell.x,destination_z=enemy.pather.Destination.Cell.z,
                native_route=actual.Select(c=>new{x=c.x,z=c.z}).ToArray(),
                forecast_route=forecast?.Select(p=>new{x=p.Item1.x,z=p.Item1.z,ticks=p.Item2}).ToArray(),
                forecast_matches_native=matches,forecast_native_path_differs=!matches,
                actor_job_unchanged=actor.CurJob.loadID==actorId,
                actor_queue_unchanged=actorQueue.SequenceEqual(actor.jobs.jobQueue.Select(q=>q.job.loadID)),
                enemy_job_unchanged=enemy.CurJob.loadID==enemyId,
                enemy_queue_unchanged=enemyQueue.SequenceEqual(enemy.jobs.jobQueue.Select(q=>q.job.loadID)),
                native_path_cursor_unchanged=path==enemy.pather.curPath && left==(enemy.pather.curPath?.NodesLeftCount ?? 0),
                rng_before=rng,rng_after=after,rng_unchanged=rng==after,tick_unchanged=tick==Find.TickManager.TicksGame,
                meaning="Read-only actual native remaining path versus actual production TargetRoute. Native path is neither consumed nor disposed. No orders, movement, shots or raid credit."};
        }
    }
}
#endif

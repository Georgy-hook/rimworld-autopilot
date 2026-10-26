#if LAYA_COMBAT_LAB
// Read-only prospective algorithm probe; no movement, job, stat or RNG changes.
using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;
using RIMAPI.Helpers;
namespace RIMAPI.Controllers
{
    public static class CombatLabLongInterceptProbe
    {
        private static List<Tuple<IntVec3,float>> KnownRoute(Pawn target)
        {
            var rows = new List<Tuple<IntVec3,float>> { Tuple.Create(target.Position, 0f) };
            if (target.pather?.Moving != true || !target.pather.Destination.IsValid) return rows;
            IntVec3 goal = target.pather.Destination.Cell;
            if (!goal.InBounds(target.Map)) return null;
            using (var path = target.Map.pathFinder.FindPathNow(target.Position, goal, target, null, PathEndMode.OnCell))
            {
                if (!path.Found) return null;
                var previous = target.Position; float ticks = 0;
                foreach (var cell in path.NodesReversed.AsEnumerable().Reverse().Skip(1))
                {
                    if (cell.Fogged(target.Map)) break; // Do not forecast an unseen escape route.
                    float step = cell.x != previous.x && cell.z != previous.z ? target.TicksPerMoveDiagonal : target.TicksPerMoveCardinal;
                    step += target.Map.pathing.For(target).pathGrid.CalculatedCostAt(cell, false, previous);
                    step += (float)(cell.GetEdifice(target.Map)?.PathWalkCostFor(target) ?? 0);
                    var terrain = cell.GetTerrain(target.Map);
                    foreach (var tag in terrain.tags ?? new List<string>())
                        if (target.kindDef.moveSpeedFactorByTerrainTag.TryGetValue(tag, out float factor) && factor > 0) step /= factor;
                    step = Math.Min(450f, step);
                    switch (target.CurJob?.locomotionUrgency ?? LocomotionUrgency.Jog)
                    {
                        case LocomotionUrgency.Amble: step = Math.Max(60f, step * 3f); break;
                        case LocomotionUrgency.Walk: step = Math.Max(50f, step * 2f); break;
                        case LocomotionUrgency.Sprint: step *= .75f; break;
                    }
                    // Remaining current-step time is observed; subsequent terrain/door waits are estimates.
                    if (rows.Count == 1) step = Math.Max(1, target.pather.nextCellCostLeft);
                    ticks += Math.Max(1, step); rows.Add(Tuple.Create(cell, ticks)); previous = cell;
                    if(ticks>=3600 || rows.Count>=257)break;
                }
            }
            return rows;
        }

        private static IntVec3 Future(List<Tuple<IntVec3,float>> route,float ticks)
            =>route.LastOrDefault(r=>r.Item2<=ticks)?.Item1 ?? route[0].Item1;
        private static List<CombatTimedPoint> ActorRoute(Pawn actor,PawnPath path,float total,float ownLock)
        {
            var result=new List<CombatTimedPoint>{new CombatTimedPoint(actor.Position.x,actor.Position.z,0f)};
            var raw=new List<CombatTimedPoint>();var previous=actor.Position;float elapsed=0f;
            foreach(var c in path.NodesReversed.AsEnumerable().Reverse().Skip(1))
            {elapsed+=CombatInterceptHelper.PlannedJogStepTicks(actor,previous,c);raw.Add(new CombatTimedPoint(c.x,c.z,elapsed));previous=c;}
            if(ownLock>0)result.Add(new CombatTimedPoint(actor.Position.x,actor.Position.z,ownLock));
            if(total>0 && elapsed<=0)return new List<CombatTimedPoint>();
            foreach(var point in raw)result.Add(new CombatTimedPoint(point.X,point.Z,ownLock+point.Tick*total/elapsed));
            return result;
        }
        public static object Read()
        {
            var actor=CombatLabState.Allies.Single();var target=CombatLabState.Enemies.Single();var map=actor.Map;
            if(CombatLabState.Scenario!="intercept_perpendicular_exit_contract" || !CombatLabState.HoldInitial || CombatLabState.StepTicks!=0
                || !CombatNativeHelper.Kidnapper(target))throw new InvalidOperationException("Only the original held perpendicular carrier contract is eligible");
            var clock=System.Diagnostics.Stopwatch.StartNew();
            string before=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            var route=KnownRoute(target);
            if(route==null || route.Count<2)throw new InvalidOperationException("Native known exit path unavailable; no guessed route");
            var verb=actor.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            float range=verb.verbProps.range,minimum=verb.verbProps.minRange,until=route.Last().Item2;
            float aim=verb.verbProps.warmupTime*60f*actor.GetStatValue(StatDefOf.AimingDelayFactor);
            float engagement=CombatInterceptMath.EngagementTicks(true,false,aim,
                Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots,
                actor.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f);
            float flight=CombatInterceptMath.NativeFlightTicks(range,verb.verbProps.defaultProjectile.projectile.SpeedTilesPerTick);
            Func<float,float> horizonFor=travel=>CombatInterceptMath.ShotHorizon(travel+CombatInterceptHelper.MovementLockTicks(actor),aim+engagement,flight);
            Func<float,bool> window=distance=>CombatInterceptMath.CarrierWindow(range,minimum,distance);
            var cells=new HashSet<IntVec3>();
            foreach(var c in GenRadial.RadialCellsAround(actor.Position,36f,true).Where((c,i)=>i%8==0))cells.Add(c);
            foreach(float horizon in new[]{120f,240f,480f,720f,960f,1440f,1920f,2400f,3000f})
            {
                var lead=Future(route,Math.Min(horizon,until));int offset=(int)Math.Max(7f,range*.55f);
                foreach(var direction in GenAdj.CardinalDirections)
                    foreach(var c in GenRadial.RadialCellsAround(lead+direction*offset,3f,true))cells.Add(c);
            }
            // A straight ETA is only a lower bound. Do not reject a later
            // native path because the carrier was outside a narrow window at
            // that one optimistic timestamp. Sample distinct observed windows.
            float moveCardinal=actor.TicksPerMoveCardinal,moveDiagonal=actor.TicksPerMoveDiagonal;
            float minWindowSq=(float)Math.Pow(Math.Max(6f,minimum+1f),2),maxWindowSq=range*range*.36f;
            var coarse=cells.Where(c=>c.InBounds(map) && c.Standable(map) && !c.Fogged(map)
                && actor.CanReserve(c) && !CombatControlHelper.CellClaimed(actor,c)
                && !c.GetThingList(map).OfType<Pawn>().Any(p=>p!=actor))
                .Select(c=>new{cell=c,arrival=CombatInterceptMath.StraightTravelTicks(
                    c.x-actor.Position.x,c.z-actor.Position.z,moveCardinal,moveDiagonal)})
                // Avoid spending scarce native path queries on a firing cell
                // lying directly on this observed future escape corridor.
                .Where(c=>route.Where(r=>r.Item2>=c.arrival+CombatInterceptHelper.MovementLockTicks(actor))
                    .All(r=>c.cell.DistanceToSquared(r.Item1)>=6.5f*6.5f))
                .Select(c=>new{cell=c.cell,lower=horizonFor(c.arrival)})
                .Select(c=>new{cell=c.cell,first=route.Where(r=>r.Item2>=c.lower
                    && c.cell.DistanceToSquared(r.Item1)>=minWindowSq-.01f && c.cell.DistanceToSquared(r.Item1)<=maxWindowSq+.01f)
                    .Select(r=>r.Item2).DefaultIfEmpty(float.PositiveInfinity).First()})
                .Where(r=>!float.IsInfinity(r.first)).ToList();
            var diverse=coarse.GroupBy(r=>(int)(r.first/300f)).OrderBy(g=>g.Key)
                .SelectMany(g=>g.OrderBy(r=>r.cell.DistanceToSquared(actor.Position)).Take(4)).Select(r=>r.cell);
            var shortlist=diverse.Concat(coarse.OrderBy(r=>r.cell.DistanceToSquared(actor.Position)).Select(r=>r.cell))
                .Distinct().Take(48).ToList();
            var timedTarget=route.Select(r=>new CombatTimedPoint(r.Item1.x,r.Item1.z,r.Item2)).ToList();
            float ownLock=CombatInterceptHelper.MovementLockTicks(actor),fireRange=range-Math.Max(3f,range*.12f);
            var rows=new List<object>();int queries=0;float best=float.MaxValue;var bestCell=IntVec3.Invalid;float bestTravel=0f,bestHorizon=0f;var bestActorRoute=new List<object>();
            foreach(var cell in shortlist)
            {
                queries++;
                using(var path=map.pathFinder.FindPathNow(actor.Position,cell,actor,null,PathEndMode.OnCell))
                {
                    bool safe=CombatInterceptHelper.MovementSafe(actor,path);float travel=path.Found?path.TotalCost:float.PositiveInfinity;
                    float h=horizonFor(travel);var future=Future(route,h);
                    bool hit=CombatExposureHelper.CanHitPawnAt(verb,target,cell,future)==true;
                    bool body=CombatInterceptHelper.FutureFriendlyLaneClear(actor,target,cell,future,"long_probe_actual");
                    bool oldCurrent=CombatInterceptHelper.FriendlyLaneClear(actor,target,cell);
                    bool endpointLegal=safe && h<=until && window(cell.DistanceTo(future)) && hit && body;
                    var timedActor=endpointLegal?ActorRoute(actor,path,travel,ownLock):new List<CombatTimedPoint>();
                    float arrival=travel+ownLock;
                    var movement=endpointLegal?CombatTimedRouteMath.Separation(timedActor,timedTarget,0f,arrival):new CombatTimedRange();
                    var volley=endpointLegal?CombatTimedRouteMath.Separation(timedActor,timedTarget,arrival,h):new CombatTimedRange();
                    bool legal=endpointLegal && movement.Valid && volley.Valid && movement.Minimum>=3.5f
                        && volley.Minimum>=6f && volley.Maximum<=fireRange;
                    float score=h*.3f+cell.DistanceTo(future)*12f-CoverUtility.CalculateOverallBlockChance(new LocalTargetInfo(cell),target.Position,map)*100f;
                    if(legal && score<best)
                    {
                        best=score;bestCell=cell;bestTravel=travel;bestHorizon=h;
                        bestActorRoute=timedActor.Select(r=>(object)new{x=r.X,z=r.Z,tick=r.Tick}).ToList();
                    }
                    rows.Add(new{x=cell.x,z=cell.z,path_found=path.Found,path_safe=safe,reservable=true,travel,horizon=h,
                        observed_until=until,observed_future=h<=until,future_x=future.x,future_z=future.z,
                        future_window=window(cell.DistanceTo(future)),future_pawn_hit=hit,future_lane_clear=body,current_lane_clear=oldCurrent,
                        endpoint_legal=endpointLegal,timed_approach_known=movement.Valid,timed_volley_known=volley.Valid,
                        movement_min_separation=movement.Valid?(float?)movement.Minimum:null,volley_min_separation=volley.Valid?(float?)volley.Minimum:null,
                        volley_max_separation=volley.Valid?(float?)volley.Maximum:null,
                        candidate_legal=legal,future_legal_but_current_filter_rejects=legal && !oldCurrent});
                }
            }
            bool productionSelected=CombatInterceptHelper.TryPosition(actor,target,out var productionCell);
            string after=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            return new{native_process_id=CombatLabState.ProcessId,native_instance_id=CombatLabState.InstanceId,tick=Find.TickManager.TicksGame,
                scenario=CombatLabState.Scenario,route_nodes=route.Count,observed_until=until,observed_exit_x=route.Last().Item1.x,observed_exit_z=route.Last().Item1.z,
                actor_id=actor.thingIDNumber,target_id=target.thingIDNumber,range,aim,engagement,flight,
                native_algorithm_selected=productionSelected,native_algorithm_x=productionCell.x,native_algorithm_z=productionCell.z,native_algorithm_prediction=CombatInterceptHelper.LastPrediction,
                new_candidate_selected=bestCell.IsValid,new_x=bestCell.x,new_z=bestCell.z,selected_travel=bestTravel,selected_horizon=bestHorizon,
                selected_actor_route=bestActorRoute,known_target_route=route.Select(r=>new{x=r.Item1.x,z=r.Item1.z,tick=r.Item2}).ToArray(),path_queries=queries,path_query_cap=48,
                coarse_candidates=coarse.Count,coarse_time_buckets=coarse.Select(r=>(int)(r.first/300f)).Distinct().Count(),
                node_timing="Loaded edge costs distributed over native path.TotalCost; estimates, not guaranteed arrival",probe_ms=clock.Elapsed.TotalMilliseconds,rng_before=before,rng_after=after,rng_unchanged=before==after,rows,
                limits="V128 geometry/cohort/seed unchanged; one declared initial native exitMapOnArrival flag added, no later changes. LAB-only candidate generator and full known exit route, no production change, motion, shot, hit or rescue outcome"};
        }
    }
}
#endif

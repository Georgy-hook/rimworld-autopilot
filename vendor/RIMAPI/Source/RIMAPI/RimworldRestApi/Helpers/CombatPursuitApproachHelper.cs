using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public struct CombatApproachReview
    {
        public bool Clear;public string Reason;public int? Pursuer;
        public float? Minimum,KnownUntil;public float Horizon;public IntVec3 Goal;
    }
    // Read-only finite observed trajectories. No new enemy path, AI order,
    // native RNG, weapon or movement-stat change is made here.
    public static class CombatPursuitApproachHelper
    {
        private static IEnumerable<Pawn> Pursuers(Pawn actor)=>actor.Map.mapPawns.AllPawnsSpawned.Where(e=>e!=actor
            && !e.Dead && !e.Downed && !e.Position.Fogged(actor.Map) && CombatNativeHelper.IsPlayerThreat(e)
            && (e.CurJobDef==JobDefOf.AttackMelee || e.CurJobDef?.defName=="PredatorHunt")
            && e.CurJob.targetA.Thing==actor).Take(5);
        public static Pawn ObservedOwnPursuer(Pawn actor)=>Pursuers(actor)
            .OrderBy(e=>e.Position.DistanceToSquared(actor.Position)).FirstOrDefault();

        public static CombatApproachReview Check(Pawn actor,Pawn target,PawnPath path,float declaredTravel,bool continuing=false)
            =>Check(actor,target,CombatPathBudgetHelper.Borrowed(path),declaredTravel,continuing);
        public static CombatApproachReview Check(Pawn actor,Pawn target,CombatPathBudgetHelper.Observation path,float declaredTravel,bool continuing=false)
        {
            CombatPathBudgetHelper.Checkpoint("pursuit_window");
            var answer=new CombatApproachReview{Clear=true,Reason="no_observed_own_melee_pursuer",Goal=actor.Position};
            var pursuers=Pursuers(actor).ToArray();
            if(pursuers.Length==0)return answer;
            answer.Clear=false;
            if(pursuers.Length>4){answer.Reason="pursuer_budget_exceeded";return answer;}
            if(path==null || !path.Found){answer.Reason="actor_path_unavailable";return answer;}
            var verb=actor.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            var projectile=verb?.verbProps.defaultProjectile?.projectile;
            if(verb==null || projectile==null || target==null){answer.Reason="firing_window_unavailable";return answer;}
            var cells=(continuing?path.NodesReversed.Take(path.NodesLeftCount).Reverse():path.NodesReversed.AsEnumerable().Reverse())
                .SkipWhile(c=>c==actor.Position).ToList();
            if(continuing && actor.pather.nextCell.IsValid && actor.pather.nextCell!=actor.Position
                && (cells.Count==0 || cells[0]!=actor.pather.nextCell))cells.Insert(0,actor.pather.nextCell);
            if(cells.Count>256){answer.Reason="actor_route_budget_exceeded";return answer;}
            float ownLock=actor.stances.curStance is Stance_Warmup?0f:CombatInterceptHelper.MovementLockTicks(actor);
            float elapsed=0f;var previous=actor.Position;var raw=new List<CombatTimedPoint>();
            foreach(var cell in cells)
            {
                CombatPathBudgetHelper.Checkpoint("pursuit_route");
                if(!cell.InBounds(actor.Map) || cell.Fogged(actor.Map)){answer.Reason="actor_route_unobserved";return answer;}
                elapsed+=continuing && previous==actor.Position && cell==actor.pather.nextCell
                    ?Math.Max(1f,actor.pather.nextCellCostLeft):CombatInterceptHelper.PlannedJogStepTicks(actor,previous,cell);
                raw.Add(new CombatTimedPoint(cell.x,cell.z,elapsed));previous=cell;
            }
            float travel=continuing?elapsed:declaredTravel;
            if(!(travel>=0f) || float.IsInfinity(travel) || elapsed<=0f && travel>0f)
            {answer.Reason="actor_timing_unavailable";return answer;}
            var actorRoute=new List<CombatTimedPoint>{new CombatTimedPoint(actor.Position.x,actor.Position.z,0f)};
            if(ownLock>0f)actorRoute.Add(new CombatTimedPoint(actor.Position.x,actor.Position.z,ownLock));
            foreach(var point in raw)actorRoute.Add(new CombatTimedPoint(point.X,point.Z,ownLock+point.Tick*travel/Math.Max(.001f,elapsed)));
            answer.Goal=previous;
            float aim=verb.verbProps.warmupTime*60f*actor.GetStatValue(StatDefOf.AimingDelayFactor);
            float engagement=CombatInterceptMath.EngagementTicks(CombatNativeHelper.Kidnapper(target),CombatNativeHelper.AbductionThreat(target),aim,
                Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots,
                actor.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f);
            float flight=CombatInterceptMath.NativeFlightTicks(verb.verbProps.range,projectile.SpeedTilesPerTick);
            float end=CombatInterceptMath.ShotHorizon(travel+ownLock,aim+engagement,flight);answer.Horizon=end;
            if(float.IsInfinity(end) || float.IsNaN(end)){answer.Reason="firing_timing_unavailable";return answer;}
            foreach(var enemy in pursuers)
            {
                CombatPathBudgetHelper.Checkpoint("pursuer");
                answer.Pursuer=enemy.thingIDNumber;
                var observed=CombatInterceptHelper.ReadObservedRoute(enemy);
                if(observed==null || observed.Count<2){answer.Reason="pursuer_route_unavailable";return answer;}
                float enemyLock=CombatInterceptHelper.MovementLockTicks(enemy);
                var route=new List<CombatTimedPoint>{new CombatTimedPoint(enemy.Position.x,enemy.Position.z,0f)};
                if(enemyLock>0f)route.Add(new CombatTimedPoint(enemy.Position.x,enemy.Position.z,enemyLock));
                route.AddRange(observed.Skip(1).Select(r=>new CombatTimedPoint(r.Item1.x,r.Item1.z,r.Item2+enemyLock)));
                float until=route[route.Count-1].Tick;answer.KnownUntil=until;
                var separation=CombatTimedRouteMath.Separation(actorRoute,route,0f,Math.Min(end,until));
                if(!separation.Valid){answer.Reason="pursuit_geometry_unavailable";return answer;}
                answer.Minimum=separation.Minimum;
                if(separation.Minimum<3.5f){answer.Reason="observed_melee_route_intersection";return answer;}
                if(until<end){answer.Reason="pursuer_route_ends_before_firing_window";return answer;}
            }
            answer.Clear=true;answer.Reason="observed_pursuit_window_clear";return answer;
        }
#if LAYA_COMBAT_LAB
        private static readonly List<object> Stops=new List<object>();
        public static void Reset()=>Stops.Clear();
        public static void RecordStop(Pawn actor,Pawn target,CombatApproachReview r)
        {
            if(Stops.Count<64)Stops.Add(new{tick=Find.TickManager.TicksGame,actor=actor.thingIDNumber,target=target?.thingIDNumber,
                pursuer=r.Pursuer,reason=r.Reason,minimum=r.Minimum,known_until=r.KnownUntil,horizon=r.Horizon,
                job=actor.CurJobDef?.defName,job_id=actor.CurJob?.loadID,goal_x=r.Goal.x,goal_z=r.Goal.z,
                meaning="Stopped only an owned firing approach; finite observed own-pursuer route, not an enemy AI command or combat outcome"});
        }
        public static object Diagnostics(IEnumerable<Pawn> actors)=>new{available=true,stops=Stops.ToArray(),
            pending=actors.Where(a=>a.Spawned && !a.Dead && !a.Downed && a.CurJobDef==JobDefOf.Goto
                && CombatOrderHelper.Owned(a,a.CurJob)).Select(a=>
            {
                var target=a.jobs.jobQueue.Select(q=>q.job).FirstOrDefault(j=>CombatOrderHelper.Owned(a,j) && j.def==JobDefOf.AttackStatic)?.targetA.Thing as Pawn;
                var r=Check(a,target,a.pather.curPath,0f,true);
                return new{actor=a.thingIDNumber,target=target?.thingIDNumber,clear=r.Clear,reason=r.Reason,pursuer=r.Pursuer,
                    minimum=r.Minimum,known_until=r.KnownUntil,horizon=r.Horizon,goal_x=r.Goal.x,goal_z=r.Goal.z};
            }).ToArray()};
#endif
    }
}

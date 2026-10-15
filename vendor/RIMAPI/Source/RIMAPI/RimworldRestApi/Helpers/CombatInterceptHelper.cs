using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.CompilerServices;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class CombatInterceptMath
    {
        public static float ShotHorizon(float travelTicks, float warmupTicks, float flightTicks)
            => Math.Max(0, travelTicks) * 1.15f + Math.Max(0, warmupTicks) + Math.Max(0, flightTicks) + 90f;
        public static bool FiringWindow(float range, float minimumRange, float predictedDistance)
            => range > 6f && predictedDistance >= Math.Max(6f, minimumRange + 1f)
                && predictedDistance <= range - Math.Max(3f, range * .12f);
        public static bool ContactDefence(bool violent, float distance)
            => violent && distance >= 0f && distance <= 1.5f;
        public static bool SupportedLure(bool pursuit, int readySameTargetGuns, bool escapeRoute)
            => pursuit && readySameTargetGuns > 0 && escapeRoute;
        public static bool ImmediateWindow(bool hitNow, bool futureObserved, bool hitFuture)
            => hitNow && (!futureObserved || hitFuture);
        public static bool DefensiveAdvance(float travel, float separation, float nextSeparation, bool cover)
            => travel <= 8f && nextSeparation >= Math.Min(6f, separation)
                && (cover || nextSeparation >= separation - 1f);
        public static float StraightTravelTicks(int dx,int dz,float cardinal,float diagonal)
            => Math.Min(Math.Abs(dx),Math.Abs(dz))*diagonal + Math.Abs(Math.Abs(dx)-Math.Abs(dz))*cardinal;
        public static float ShotCommitment(float aim,float burst,float cooldown,float moveMargin,float locked)
            => Math.Max(Math.Max(0,locked),Math.Max(0,aim)+Math.Max(0,burst)+Math.Max(0,cooldown))+Math.Max(0,moveMargin);
        public static bool InterveningAlly(float sx,float sz,float tx,float tz,float fx,float fz,float radius)
        {
            float dx=tx-sx,dz=tz-sz,length=(float)Math.Sqrt(dx*dx+dz*dz);
            if(length<.1f)return false;
            float along=((fx-sx)*dx+(fz-sz)*dz)/length;
            return along>0 && along<=length+radius
                && Math.Abs((fx-sx)*dz-(fz-sz)*dx)/length<=radius;
        }
    }

    /// <summary>Ordinary movement toward an estimated future firing window, never a guaranteed hit.</summary>
    public static class CombatInterceptHelper
    {
        public static string LastPrediction;
        private sealed class RouteObservation
        {public int Tick=-1;public IntVec3 Position,Goal;public Job Job;public float Move,Next;public List<Tuple<IntVec3,float>> Rows;}
        private static readonly ConditionalWeakTable<Pawn,RouteObservation> Routes=new ConditionalWeakTable<Pawn,RouteObservation>();
        private static List<Tuple<IntVec3,float>> TargetRoute(Pawn target)
        {
            var entry=Routes.GetValue(target,_=>new RouteObservation());
            int tick=Find.TickManager.TicksGame;IntVec3 goal=target.pather?.Destination.Cell ?? IntVec3.Invalid;
            float move=target.TicksPerMoveCardinal,next=target.pather?.nextCellCostLeft ?? 0;
            if(entry.Tick==tick && entry.Position==target.Position && entry.Goal==goal && entry.Job==target.CurJob
                && entry.Move==move && entry.Next==next)return entry.Rows;
            entry.Rows=ReadTargetRoute(target);entry.Tick=tick;entry.Position=target.Position;entry.Goal=goal;entry.Job=target.CurJob;
            entry.Move=move;entry.Next=next;return entry.Rows;
        }
        private static List<Tuple<IntVec3,float>> ReadTargetRoute(Pawn target)
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
                    if (ticks >= 1200) break;
                }
            }
            return rows;
        }
        private static IntVec3 Future(List<Tuple<IntVec3,float>> route, float ticks)
            => route.LastOrDefault(r => r.Item2 <= ticks)?.Item1 ?? route[0].Item1;
        public static float ContactTicks(Pawn threat,Pawn actor)
        {
            float fallback=Math.Max(0,actor.Position.DistanceTo(threat.Position)-1.5f)*Math.Max(1,threat.TicksPerMoveCardinal);
            if(!Pursuing(threat,actor))return fallback;
            var route=TargetRoute(threat);
            var contact=route?.FirstOrDefault(r=>r.Item1.InHorDistOf(actor.Position,1.5f));
            if(contact!=null)return contact.Item2;
            return route!=null && route.Count>1 && route[route.Count-1].Item2>=1200 ? 1200:fallback;
        }
        public static bool DefendedApproach(Pawn actor,Pawn threat)
        {
            if(threat.equipment?.Primary?.def.IsRangedWeapon==true || !CanShootNow(actor,threat))return false;
            var route=TargetRoute(threat);if(route==null || route.Count<2)return false;
            Func<IntVec3,bool> wall=c=>c.InBounds(actor.Map) && c.GetEdifice(actor.Map) is Building b
                && !(b is Building_Door) && b.def.passability==Traversability.Impassable;
            return route.Skip(1).Any(r=>r.Item1.DistanceTo(actor.Position)>=3f && r.Item1.Standable(actor.Map)
                && (wall(r.Item1+IntVec3.North) && wall(r.Item1+IntVec3.South)
                    || wall(r.Item1+IntVec3.East) && wall(r.Item1+IntVec3.West)));
        }
        public static bool IncomingToRange(Pawn pawn,Pawn target,IntVec3 cell,out IntVec3 expected)
        {
            expected=target.Position;if(target.pather?.Moving!=true)return false;
            var route=TargetRoute(target);if(route==null || route.Count<2)return false;
            expected=Future(route,Math.Min(180,route[route.Count-1].Item2));
            var verb=pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            return verb!=null && cell.DistanceTo(expected)<=verb.verbProps.range-2f
                && verb.CanHitTargetFrom(cell,new LocalTargetInfo(expected));
        }
        public static bool MovementSafe(Pawn pawn, PawnPath path)
        {
            var map = pawn.Map;
            var enemies = map.mapPawns.AllPawnsSpawned.Where(p => !p.Dead && !p.Downed
                && !p.Position.Fogged(map) && CombatNativeHelper.IsPlayerThreat(p)).ToArray();
            return path.Found && path.NodesReversed.All(c => !c.Fogged(map) && !c.ContainsStaticFire(map)
                && !c.GetThingList(map).Any(t => t is Building_Trap && t.Faction == Faction.OfPlayer)
                && map.gasGrid.DensityAt(c, GasType.ToxGas) == 0 && map.gasGrid.DensityAt(c, GasType.DeadlifeDust) == 0
                && enemies.All(e => c == pawn.Position || c.DistanceToSquared(e.Position) >= 9));
        }
        public static bool FriendlyLaneClear(Pawn pawn,LocalTargetInfo target,IntVec3 from)
        {
            var verb=pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(verb==null || !verb.TryFindShootLineFromTo(from,target,out var line))return false;
            // Observe the native lean/source and near-shooter interception rule.
            // Do not change projectile flags, collision, damage or hit chances.
            return !pawn.Map.mapPawns.AllPawnsSpawned.Any(p=>p!=pawn && p!=target.Thing && !p.Dead
                && (!p.HostileTo(pawn) && !CombatNativeHelper.ActivePredation(p)
                    || pawn.Faction==Faction.OfPlayer && p.IsPrisonerOfColony)
                && VerbUtility.InterceptChanceFactorFromDistance(line.Source.ToVector3Shifted(),p.Position)>0f
                && CombatInterceptMath.InterveningAlly(line.Source.x,line.Source.z,line.Dest.x,line.Dest.z,p.Position.x,p.Position.z,1.5f));
        }
        public static bool CanShootNow(Pawn pawn, Thing thing)
        {
            if (!(thing is Pawn target) || target.Dead || target.Downed || pawn.WorkTagIsDisabled(WorkTags.Violent)) return false;
            var verb=pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(verb==null || verb.IsMeleeAttack || !verb.CanHitTargetFrom(pawn.Position,target)
                || !FriendlyLaneClear(pawn,target,pawn.Position))return false;
            var projectile=verb.verbProps.defaultProjectile?.projectile;
            if(target.carryTracker?.CarriedThing is Pawn carried && carried.Faction==Faction.OfPlayer
                && (projectile?.explosionRadius>0 || projectile?.damageDef==DamageDefOf.Flame))return false;
            if(target.pather?.Moving!=true || verb.state==VerbState.Bursting)return true;
            var route=TargetRoute(target);
            // Unknown future motion cannot justify cancelling an existing warmup.
            if(route==null || route.Count<2)return true;
            float aim=pawn.stances.curStance is Stance_Warmup active ? active.ticksLeft
                : verb.verbProps.warmupTime*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor);
            float flight=projectile?.speed>0 ? pawn.Position.DistanceTo(target.Position)/projectile.speed*60f : 0;
            float horizon=Math.Max(0,aim)+flight;
            // A short observed path is unknown beyond its end, not evidence
            // that a currently available shot is impossible.
            if(horizon>route[route.Count-1].Item2)
                return CombatInterceptMath.ImmediateWindow(true,false,false);
            var future=Future(route,horizon);
            return pawn.Position.DistanceTo(future)<=verb.verbProps.range-1f
                && verb.CanHitTargetFrom(pawn.Position,new LocalTargetInfo(future));
        }
        public static bool TryPosition(Pawn pawn, Pawn target, out IntVec3 result, bool defensive=false)
        {
            result = IntVec3.Invalid; LastPrediction = null;
            var verb = pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if (verb == null || verb.IsMeleeAttack || pawn.WorkTagIsDisabled(WorkTags.Violent)) return false;
            var projectile=verb.verbProps.defaultProjectile?.projectile;
            if(target.carryTracker?.CarriedThing is Pawn carried && carried.Faction==Faction.OfPlayer
                && (projectile?.explosionRadius>0 || projectile?.damageDef==DamageDefOf.Flame))return false;
            var route = TargetRoute(target); if (route == null) return false;
            float range = verb.verbProps.range, minimum = verb.verbProps.minRange;
            float warmup = verb.verbProps.warmupTime * 60f * pawn.GetStatValue(StatDefOf.AimingDelayFactor);
            float projectileSpeed = verb.verbProps.defaultProjectile?.projectile?.speed ?? 0;
            float flight = projectileSpeed > 0 ? range / projectileSpeed * 60f : 0;
            var map = pawn.Map; var candidates = new HashSet<IntVec3>();
            float currentCover=CoverUtility.CalculateOverallBlockChance(pawn,target.Position,map);
            // Current neighborhood plus points beside the observed escape path. Search is bounded.
            foreach (var c in GenRadial.RadialCellsAround(pawn.Position, 36f, true).Where((c,i) => i % 8 == 0)) candidates.Add(c);
            foreach (float horizon in new[] { 120f, 240f, 480f, 720f, 960f })
            {
                var lead = Future(route, horizon);
                int offset = (int)Math.Max(7f, range * .55f);
                foreach (var direction in GenAdj.CardinalDirections)
                    foreach (var c in GenRadial.RadialCellsAround(lead + direction * offset, 3f, true)) candidates.Add(c);
            }
            var committed=pawn.CurJobDef==JobDefOf.Goto ? pawn.CurJob.targetA.Cell : IntVec3.Invalid;
            if(committed.IsValid)candidates.Add(committed);
            var shortlist = candidates.Where(c => c.InBounds(map) && c.Standable(map) && !c.Fogged(map)
                && pawn.CanReserve(c) && !c.GetThingList(map).OfType<Pawn>().Any(p => p != pawn)
                && CombatInterceptMath.FiringWindow(range,minimum,c.DistanceTo(Future(route,CombatInterceptMath.ShotHorizon(
                    CombatInterceptMath.StraightTravelTicks(c.x-pawn.Position.x,c.z-pawn.Position.z,pawn.TicksPerMoveCardinal,pawn.TicksPerMoveDiagonal),warmup,flight)))))
                .OrderBy(c => c==committed ? -1 : c.DistanceToSquared(pawn.Position)).Take(48).ToList();
            float best = float.MaxValue, bestTravel = 0, bestHorizon = 0; var bestTarget = IntVec3.Invalid;
            foreach (var cell in shortlist)
            {
                using (var path = map.pathFinder.FindPathNow(pawn.Position, cell, pawn, null, PathEndMode.OnCell))
                {
                    if (!MovementSafe(pawn, path)) continue;
                    float travel = path.TotalCost; // Native path cost, loaded movement/terrain; not just straight distance.
                    float horizon = CombatInterceptMath.ShotHorizon(travel, warmup, flight);
                    if (route.Count > 1 && horizon > route[route.Count - 1].Item2) continue;
                    var predicted = Future(route, horizon);
                    if (!CombatInterceptMath.FiringWindow(range, minimum, cell.DistanceTo(predicted))
                        || !verb.CanHitTargetFrom(cell, new LocalTargetInfo(predicted))) continue;
                    float coverRating=CoverUtility.CalculateOverallBlockChance(new LocalTargetInfo(cell),target.Position,map);
                    bool cover=coverRating>=.4f;
                    if(defensive && currentCover>=.3f && coverRating<currentCover-.1f)continue;
                    if(defensive && (cell.DistanceTo(CombatControlHelper.DefensiveAnchor(pawn))>8f
                        || !CombatInterceptMath.DefensiveAdvance(cell.DistanceTo(pawn.Position),
                        pawn.Position.DistanceTo(target.Position),cell.DistanceTo(target.Position),cover)))continue;
                    // An actual escaping carrier needs an interior firing
                    // window. The very earliest edge shot can strand the only
                    // forward interceptor after one inaccurate volley.
                    bool carrier=CombatNativeHelper.Kidnapper(target);
                    float score = horizon*(carrier ? .3f : 1f) + cell.DistanceTo(predicted)*(carrier ? 12f : 2f) - coverRating*100f;
                    if (score >= best) continue;
                    best = score; result = cell; bestTravel = travel; bestHorizon = horizon; bestTarget = predicted;
                    if(cell==committed)break; // Keep a still timely route; replace it only when its window is invalid.
                }
            }
            if (!result.IsValid) return false;
            LastPrediction = $"{pawn.LabelShort}: estimated travel {bestTravel:0} ticks + aim {warmup:0} + flight/buffer -> {bestHorizon:0}; "
                + $"target {target.thingIDNumber} forecast ({bestTarget.x},{bestTarget.z}), firing cell ({result.x},{result.z}); "
                + "current path can change; arrival, sight, shot and hit require fresh verification";
            return true;
        }
        public static List<Pawn> ReadyCover(Pawn lure, Pawn target)
            => lure.Map.mapPawns.FreeColonistsSpawned.ToArray().Where(p => p != lure && !p.Dead && !p.Downed && !p.InMentalState
                && !p.WorkTagIsDisabled(WorkTags.Violent) && !CombatNativeHelper.Protected(p) && !CareTriageHelper.QueuedCare(p)
                && (p.CurJobDef == JobDefOf.AttackStatic && p.CurJob.targetA.Thing == target
                    || p.CurJobDef==JobDefOf.Wait_Combat && CombatControlHelper.AimTarget(p)==target)
                && p.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb is Verb v
                && !v.IsMeleeAttack && CanShootNow(p,target)).ToList();
        public static bool Pursuing(Pawn target, Pawn lure)
            => target != null && !target.Dead && !target.Downed && CombatNativeHelper.IsPlayerThreat(target)
                && target.CurJob?.targetA.Thing == lure && new[] {"AttackMelee","PredatorHunt"}.Contains(target.CurJobDef?.defName);
    }
}

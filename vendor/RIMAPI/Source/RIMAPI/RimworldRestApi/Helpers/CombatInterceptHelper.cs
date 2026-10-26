using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class CombatInterceptMath
    {
        public static float ShotHorizon(float travelTicks, float warmupTicks, float flightTicks)
            => Math.Max(0, travelTicks) * 1.15f + Math.Max(0, warmupTicks) + Math.Max(0, flightTicks) + 90f;
        public static float NativeFlightTicks(float distance,float speedTilesPerTick)
            => distance>=0f && !float.IsInfinity(distance) && speedTilesPerTick>0f
                && !float.IsInfinity(speedTilesPerTick)?Math.Max(.001f,distance/speedTilesPerTick):float.PositiveInfinity;
        public static float EngagementTicks(bool escapingCarrier,bool pickupAttempt,float warmup,float burst,float cooldown)
            => escapingCarrier?Math.Max(0,warmup)+Math.Max(0,burst)+Math.Max(0,cooldown):pickupAttempt?Math.Max(0,burst):0;
        public static bool FiringWindow(float range, float minimumRange, float predictedDistance)
            => range > 6f && predictedDistance >= Math.Max(6f, minimumRange + 1f)
                && predictedDistance <= range - Math.Max(3f, range * .12f);
        public static bool PendingCarrierRoute(bool carrier,bool hasJob,bool gotoJob,bool moving)
            =>carrier && !moving && (!hasJob || gotoJob);
        public static bool ContactDefence(bool violent, float distance)
            => violent && distance >= 0f && distance <= 1.5f;
        public static float StationaryContact(float distance,float moveTicks,float locked)
            => distance>=0 && !float.IsInfinity(distance) && moveTicks>0 && !float.IsInfinity(moveTicks)
                ?distance<=1.5f?0f:Math.Max(0f,locked)+(distance-1.5f)*moveTicks:0f;
        public static bool SupportedLure(bool pursuit, int readySameTargetGuns, bool escapeRoute)
            => pursuit && readySameTargetGuns > 0 && escapeRoute;
        public static bool ImmediateWindow(bool hitNow, bool futureObserved, bool hitFuture)
            => hitNow && (!futureObserved || hitFuture);
        public static float FirstShotDelay(float aim,float locked,bool warming)
            => Math.Max(0f,aim)+(warming?0f:Math.Max(0f,locked));
        public static bool SupportVolley(float contact,float aim,float burst,float locked,bool warming)
            => contact>0f && !float.IsInfinity(contact)
                && contact>FirstShotDelay(aim,locked,warming)+Math.Max(0f,burst)+30f;
        public static bool SupportApproachWindow(float contact,float travel,float locked,float aim,float burst,float flight)
            => contact>=0f && !float.IsInfinity(contact) && travel>=0f && !float.IsInfinity(travel)
                && locked>=0f && !float.IsInfinity(locked) && aim>=0f && !float.IsInfinity(aim)
                && burst>=0f && !float.IsInfinity(burst) && flight>=0f && !float.IsInfinity(flight)
                && contact>travel+locked+aim+burst+flight+30f;
        public static bool FocusDeadline(float contact,float committedContact,float locked,float aim,float burst,float cooldown,float flight)
            => contact>=0f && !float.IsInfinity(contact) && committedContact>=0f && !float.IsInfinity(committedContact)
                && locked>=0f && !float.IsInfinity(locked) && aim>=0f && !float.IsInfinity(aim)
                && burst>=0f && !float.IsInfinity(burst) && cooldown>=0f && !float.IsInfinity(cooldown)
                && flight>=0f && !float.IsInfinity(flight) && contact+30f<=committedContact
                && contact>locked+aim+burst+flight+30f
                && contact<=locked+aim+burst+cooldown+aim+burst+flight+30f;
        public static bool KeepCommittedFocus(int actualGuns,float focusUrgency,float nextUrgency,bool nextAbduction)
            => actualGuns>=2 && !nextAbduction && !float.IsInfinity(focusUrgency)
                && focusUrgency>=0f && nextUrgency>=0f && nextUrgency<=focusUrgency+80f
                && nextUrgency<=Math.Max(30f,focusUrgency*2f);
        public static bool DefensiveAdvance(float travel, float separation, float nextSeparation, bool cover)
            => travel <= 8f && nextSeparation >= Math.Min(6f, separation)
                && (cover || nextSeparation >= separation - 1f);
        public static float StraightTravelTicks(int dx,int dz,float cardinal,float diagonal)
            => Math.Min(Math.Abs(dx),Math.Abs(dz))*diagonal + Math.Abs(Math.Abs(dx)-Math.Abs(dz))*cardinal;
        public static float ShotCommitment(float aim,float burst,float cooldown,float moveMargin,float locked)
            => Math.Max(Math.Max(0,locked),Math.Max(0,aim)+Math.Max(0,burst)+Math.Max(0,cooldown))+Math.Max(0,moveMargin);
        public static bool FinishVolley(float contact,float aim,float burst,float cooldown,float locked,bool warming)
            => contact>0f && !float.IsInfinity(contact) && !float.IsNaN(contact)
                && contact>(warming?0f:Math.Max(0f,locked))+Math.Max(0f,aim)+Math.Max(0f,burst)
                    +Math.Max(0f,cooldown)+30f;
        public static bool MedicVolleyThenEscape(float contact,float aim,float burst,float cooldown,float locked,bool warming,float escapeMargin)
            => escapeMargin>=0f && !float.IsInfinity(escapeMargin)
                && FinishVolley(contact-escapeMargin,aim,burst,cooldown,locked,warming);
        public static bool DeferForMedicalTurn(bool pending,bool doctor,float contact,float aim,float burst,float cooldown,float locked,bool warming,
            float escapeMargin=0f)
            => pending && !doctor && escapeMargin>=0f && !float.IsInfinity(escapeMargin)
                && FinishVolley(contact-escapeMargin,aim,burst,cooldown,locked,warming);
        public static bool YieldLineWarmup(float contact,float aim,float burst,float cooldown,float escapeMargin,bool warming,bool bursting)
            => warming && !bursting && contact>0f && !float.IsInfinity(contact)
                && aim>=0f && !float.IsInfinity(aim) && burst>=0f && !float.IsInfinity(burst)
                && cooldown>=0f && !float.IsInfinity(cooldown) && escapeMargin>=0f && !float.IsInfinity(escapeMargin)
                && !FinishVolley(contact-escapeMargin,aim,burst,cooldown,0f,true);
        public static bool UsefulEscape(float before,float after,float cycle,bool actualCover,float arrivalTicks=0f)
            => !float.IsNaN(after) && !float.IsInfinity(after) && after>30f
                && arrivalTicks>=0f && !float.IsInfinity(arrivalTicks)
                && (actualCover || after>=Math.Max(0f,cycle)+30f && after+arrivalTicks>=before+30f);
        public static bool StationaryShotGain(float stationaryContact,float afterArrival,float movementLock=0f)
            => stationaryContact>=0f && !float.IsInfinity(stationaryContact)
                && !float.IsNaN(afterArrival) && !float.IsInfinity(afterArrival)
                && movementLock>=0f && !float.IsInfinity(movementLock)
                && afterArrival>=stationaryContact-movementLock+30f;
        public static bool CoverRotation(bool wounded,bool shotAvailable,bool otherGunMoving,float travel)
            => wounded || !shotAvailable || !otherGunMoving && travel>=0f && travel<=120f;
        public static float ExposureEnvelope(float current,float future)
            => current>=0f && future>=0f && !float.IsInfinity(current) && !float.IsInfinity(future)
                ?Math.Max(current,future):float.PositiveInfinity;
        public static bool CoverImproves(float baseline,float candidate)
            => baseline>=0f && candidate>=0f && !float.IsInfinity(baseline) && !float.IsInfinity(candidate)
                && candidate<=baseline-.2f;
        public static bool RangedRouteImproves(float exposureTicks,float holdingTicks,float peak,float holdingPeak,float duration)
            => duration>0f && exposureTicks>=0f && holdingTicks>=0f && peak>=0f && holdingPeak>=0f
                && !float.IsInfinity(exposureTicks) && !float.IsInfinity(holdingTicks)
                && !float.IsInfinity(peak) && !float.IsInfinity(holdingPeak)
                && peak<=holdingPeak+.25f && exposureTicks<=holdingTicks-duration*.1f;
        public static bool CriticalRangedInjury(float health,float bleeding,float pain,float consciousness,float moving,float manipulation,float sight)
            => !(health>=.65f && bleeding<1.5f && pain<.5f && consciousness>=.65f
                && moving>=.65f && manipulation>=.65f && sight>=.65f);
        public static float ForecastRangedPressure(float current,float projected,bool available)
            => available && projected>=0f && !float.IsInfinity(projected)?Math.Max(current,projected):current;
        public static bool FastCoveredBait(bool pursuit,float actorSpeed,float fastestObservedMelee,int actualCover)
            => pursuit && actualCover>0 && actorSpeed>0f && fastestObservedMelee>0f
                && !float.IsInfinity(actorSpeed) && !float.IsInfinity(fastestObservedMelee)
                && actorSpeed>fastestObservedMelee*1.03f;
        public static bool EarlyCoveredPeel(float contact,float cycle,float moveMargin,int readyCover,bool otherGunMoving,bool defendedApproach=false,
            bool warmingUp=false,bool ownShotReady=true)
            => readyCover>=2 && !otherGunMoving && !defendedApproach && !warmingUp && ownShotReady && contact>0 && !float.IsInfinity(contact)
                && cycle>=0 && !float.IsInfinity(cycle) && moveMargin>=0 && !float.IsInfinity(moveMargin)
                && contact<=Math.Max(0,cycle)+Math.Max(0,moveMargin)+90f;
        public static bool EarlyLineRotation(float contact,float cycle,float moveMargin,bool otherGunMoving,bool warmingUp,bool bursting,
            bool preserveMedic=false)
            => !otherGunMoving && (!warmingUp || preserveMedic) && !bursting && contact>0f && !float.IsInfinity(contact)
                && cycle>=0f && !float.IsInfinity(cycle) && moveMargin>=0f && !float.IsInfinity(moveMargin)
                && contact<=cycle*2f+moveMargin+30f;
        public static bool CoveredBait(bool actualPursuit,int readyCover,bool checkedCorridor)
            => actualPursuit && readyCover>=2 && checkedCorridor;
        public static float MedicPressure(bool workEnabled,bool ready,int capableCount)
            => workEnabled && ready && capableCount>0 ?120f/capableCount:0f;
        public static float TargetVulnerability(float health,float damageFactor,float bodySize)
            => health>=0 && damageFactor>=0 && bodySize>0 && !float.IsInfinity(health)
                && !float.IsInfinity(damageFactor) && !float.IsInfinity(bodySize)
                ?damageFactor/(Math.Max(.35f,health)*Math.Max(.25f,bodySize)):0f;
        public static float VictimPressure(float health,float moving,float bleeding,int attackers)
            => Math.Max(0f,1f-health)*100f+Math.Max(0f,1f-moving)*100f+Math.Max(0f,bleeding)*30f+Math.Max(0,attackers-1)*25f;
        public static float MeleePriority(float contactTicks)
            => contactTicks>=0f && contactTicks<=360f ? 160f+(360f-contactTicks)*.5f:0f;
        public static float FriendlyBodyRadius(float bodySize)
            => Math.Max(.5f,.75f*(float)Math.Sqrt(Math.Max(0f,bodySize)));
        public static bool LockedEscapeWindow(float ownLock,float enemyLock,float travel)
            => Math.Max(0,ownLock)+Math.Max(0,travel)+15f<=Math.Max(0,enemyLock);
        public static bool CarrierWindow(float range,float minimumRange,float distance)
            => distance>=Math.Max(6f,minimumRange+1f) && distance<=range*.6f;
        public static float MovingContactBound(float enemyX,float enemyZ,float moveTicks,float locked,
            float[] actorX,float[] actorZ,float[] actorTicks)
        {
            if(moveTicks<=0 || actorX.Length==0 || actorX.Length!=actorZ.Length || actorX.Length!=actorTicks.Length)return 0;
            int index=0;
            for(float tick=0;tick<=1200;tick+=15f)
            {
                while(index+1<actorTicks.Length && actorTicks[index+1]<=tick)index++;
                float dx=actorX[index]-enemyX,dz=actorZ[index]-enemyZ;
                float reach=1.5f+Math.Max(0,tick-locked)/moveTicks;
                if(dx*dx+dz*dz<=reach*reach)return Math.Max(0,tick-15f);
            }
            return 1200f;
        }
        public static bool InterveningAlly(float sx,float sz,float tx,float tz,float fx,float fz,float radius,float endpointExtension=0f)
        {
            float dx=tx-sx,dz=tz-sz,length=(float)Math.Sqrt(dx*dx+dz*dz);
            if(length<.1f)return false;
            float along=((fx-sx)*dx+(fz-sz)*dz)/length;
            return along>0 && along<=length+radius+Math.Max(0f,endpointExtension)
                && Math.Abs((fx-sx)*dz-(fz-sz)*dx)/length<=radius;
        }
        public static bool InterveningMissFan(float sx,float sz,float tx,float tz,float fx,float fz,float missRadius,float bodyRadius)
        {
            float dx=tx-sx,dz=tz-sz,length=(float)Math.Sqrt(dx*dx+dz*dz);
            float radius=missRadius,body=Math.Max(0f,bodyRadius);
            if(!(radius>=0f) || float.IsInfinity(radius) || float.IsNaN(body))return true;
            if(length<.1f)return false;
            float along=((fx-sx)*dx+(fz-sz)*dz)/length;
            if(along<=0f || along>length+radius+body)return false;
            float across=Math.Abs((fx-sx)*dz-(fz-sz)*dx)/length;
            float diskDistance=(float)Math.Sqrt((along-length)*(along-length)+across*across)-radius;
            if(diskDistance<=body)return true;
            if(radius>=length)return false; // The endpoint disk already contains the source.
            // The hull is a finite tangent triangle joined to the endpoint
            // disk, not an infinite wedge with a rectangular far end. Keep
            // the pawn's body clearance outside that hull separately.
            float root=(float)Math.Sqrt(length*length-radius*radius);
            float tangentX=root*root/length,tangentZ=radius*root/length;
            if(along<=tangentX && across<=along*radius/root)return true;
            float projection=Math.Max(0f,Math.Min(1f,(along*tangentX+across*tangentZ)/(tangentX*tangentX+tangentZ*tangentZ)));
            float ex=along-projection*tangentX,ez=across-projection*tangentZ;
            return ex*ex+ez*ez<=body*body;
        }
    }

    /// <summary>Ordinary movement toward an estimated future firing window, never a guaranteed hit.</summary>
    public static class CombatInterceptHelper
    {
        public static string LastPrediction;
        public static bool CarrierRoutePending(Pawn target)
            =>target!=null && CombatInterceptMath.PendingCarrierRoute(CombatNativeHelper.Kidnapper(target),
                target.CurJob!=null,target.CurJobDef==JobDefOf.Goto,target.pather?.Moving==true);
        private static List<Tuple<IntVec3,float>> TargetRoute(Pawn target)
            => ReadObservedNativeRoute(target,CombatCarrierInterceptHelper.Eligible(target));
        public static List<Tuple<IntVec3,float>> ReadObservedRoute(Pawn pawn)=>TargetRoute(pawn);
        private static List<Tuple<IntVec3,float>> ReadObservedNativeRoute(Pawn target,bool longRoute)
        {
            var rows = new List<Tuple<IntVec3,float>> { Tuple.Create(target.Position, 0f) };
            if (target.pather?.Moving != true || !target.pather.Destination.IsValid) return rows;
            // The path follower has already selected its route and endpoint
            // mode. A fresh OnCell path can invent a route while native path
            // construction is pending, or walk into an occupied Touch target.
            // Read the current cursor without consuming/discarding its path.
            var path=target.pather.curPath;
            if(path==null || !path.Found)return null;
            var cells=path.NodesReversed.Take(path.NodesLeftCount).Reverse().SkipWhile(c=>c==target.Position).ToList();
            var next=target.pather.nextCell;
            if(next.IsValid && next!=target.Position && (cells.Count==0 || cells[0]!=next))cells.Insert(0,next);
            if(cells.Count==0)return null;
            {
                var previous = target.Position; float ticks = 0;
                foreach (var cell in cells)
                {
                CombatPathBudgetHelper.Checkpoint();
                    if (!cell.InBounds(target.Map) || cell.Fogged(target.Map)) break; // Never extend beyond observed native nodes.
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
                    if (rows.Count == 1 && cell==next) step = Math.Max(1, target.pather.nextCellCostLeft);
                    ticks += Math.Max(1, step); rows.Add(Tuple.Create(cell, ticks)); previous = cell;
                    if(ticks>=(longRoute?3600f:1200f) || longRoute && rows.Count>=256)break;
                }
            }
            return rows;
        }
        private static IntVec3 Future(List<Tuple<IntVec3,float>> route, float ticks)
            => route.LastOrDefault(r => r.Item2 <= ticks)?.Item1 ?? route[0].Item1;
        public static bool TryObservedFuturePosition(Pawn target,float ticks,out IntVec3 cell)
        {
            CombatPathBudgetHelper.Checkpoint("TryObservedFuturePosition");
            cell=target.Position;
            if(ticks<0f || float.IsNaN(ticks) || float.IsInfinity(ticks))return false;
            if(target.pather?.Moving!=true)return true;
            var route=TargetRoute(target);
            if(route==null || route.Count<2)return false;
            // Stop at the end of this observed route. A later job/turn remains
            // unknown; no route is extrapolated through fog or beyond its end.
            cell=Future(route,Math.Max(0f,ticks-MovementLockTicks(target)));
            return true;
        }
        public static float ContactTicks(Pawn threat,Pawn actor)
        {
            float separation=actor.Position.DistanceTo(threat.Position);
            // Contact already exists during an adjacent attacker's cooldown.
            // Its next damage time is a separate fact from time to contact.
            if(CombatInterceptMath.ContactDefence(true,separation))return 0f;
            float locked=MovementLockTicks(threat);
            if(actor.CurJobDef==JobDefOf.Goto && actor.pather.Moving && !actor.stances.FullBodyBusy
                && CombatControlHelper.CurrentPlan(actor)!=null)
            {
                var escape=TargetRoute(actor);
                if(escape!=null && escape.Count>1)
                {
                    float previous=actor.Position.DistanceTo(threat.Position);bool away=true;
                    foreach(var step in escape.Skip(1))
                    {
                CombatPathBudgetHelper.Checkpoint();
                        float distance=step.Item1.DistanceTo(threat.Position);
                        if(distance+.1f<previous){away=false;break;}previous=distance;
                    }
                    if(away)
                    {
                        float fastest=threat.TicksPerMoveCardinal*(threat.CurJob?.locomotionUrgency==LocomotionUrgency.Sprint?.75f:1f);
                        // Earliest straight interception of the observed finite
                        // escape route. Terrain/walls can delay the pursuer;
                        // motion is not extrapolated after the current waypoint.
                        return CombatInterceptMath.MovingContactBound(threat.Position.x,threat.Position.z,Math.Max(1f,fastest),locked,
                            escape.Select(s=>(float)s.Item1.x).ToArray(),escape.Select(s=>(float)s.Item1.z).ToArray(),escape.Select(s=>s.Item2).ToArray());
                    }
                }
            }
            float fallback=CombatInterceptMath.StationaryContact(separation,Math.Max(1,threat.TicksPerMoveCardinal),locked);
            if(!Pursuing(threat,actor))return fallback;
            var route=TargetRoute(threat);
            var contact=route?.FirstOrDefault(r=>r.Item1.InHorDistOf(actor.Position,1.5f));
            if(contact!=null)return locked+contact.Item2;
            return route!=null && route.Count>1 && route[route.Count-1].Item2>=1200 ? 1200:fallback;
        }
        public static float MovementLockTicks(Pawn pawn) => pawn.stances?.FullBodyBusy==true
            ? Math.Max(0,(pawn.stances.curStance as Stance_Busy)?.ticksLeft ?? 0):0;
        public static bool DefendedApproach(Pawn actor,Pawn threat)
        {
            if(threat.equipment?.Primary?.def.IsRangedWeapon==true || !CanShootNow(actor,threat))return false;
            var route=TargetRoute(threat);if(route==null || route.Count<2)return false;
            Func<IntVec3,bool> wall=c=>c.InBounds(actor.Map) && c.GetEdifice(actor.Map) is Building b
                && !(b is Building_Door) && b.def.passability==Traversability.Impassable;
            int consecutive=0;
            foreach(var step in route.Skip(1))
            {
                CombatPathBudgetHelper.Checkpoint();
                var c=step.Item1;
                bool corridor=c.DistanceTo(actor.Position)>=3f && c.Standable(actor.Map)
                    && (wall(c+IntVec3.North) && wall(c+IntVec3.South)
                        || wall(c+IntVec3.East) && wall(c+IntVec3.West));
                consecutive=corridor?consecutive+1:0;
                if(consecutive>=4)return true;
            }
            return false;
        }
        public static bool IncomingToRange(Pawn pawn,Pawn target,IntVec3 cell,out IntVec3 expected)
        {
            expected=target.Position;if(target.pather?.Moving!=true)return false;
            var route=TargetRoute(target);if(route==null || route.Count<2)return false;
            expected=Future(route,Math.Min(180,route[route.Count-1].Item2));
            var verb=pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(verb==null || cell.DistanceTo(expected)>verb.verbProps.range-2f)return false;
            bool hit=CombatExposureHelper.CanHitPawnAt(verb,target,cell,expected)==true;
#if LAYA_COMBAT_LAB
            Controllers.CombatLabFutureGeometry.Record("incoming_to_range",pawn,target,verb,cell,expected,
                Math.Min(180,route[route.Count-1].Item2),route[route.Count-1].Item2,
                verb.CanHitTargetFrom(cell,new LocalTargetInfo(expected)),hit);
#endif
            return hit;
        }
        public static bool MovementSafe(Pawn pawn,CombatPathBudgetHelper.Observation path)
            =>path.Found && MovementCellsSafe(pawn,path.NodesReversed);
        public static bool MovementSafe(Pawn pawn, PawnPath path)
            => path.Found && MovementCellsSafe(pawn,path.NodesReversed);
        public static bool MovementCellsSafe(Pawn pawn,IEnumerable<IntVec3> cells)
        {
            CombatPathBudgetHelper.Checkpoint("MovementCellsSafe");
            var map = pawn.Map;
            var enemies = map.mapPawns.AllPawnsSpawned.Where(p => !p.Dead && !p.Downed
                && !p.Position.Fogged(map) && CombatNativeHelper.IsPlayerThreat(p)).ToArray();
            return cells.All(c => !c.Fogged(map) && !c.ContainsStaticFire(map)
                && !c.GetThingList(map).Any(t => t is Building_Trap && t.Faction == Faction.OfPlayer)
                && map.gasGrid.DensityAt(c, GasType.ToxGas) == 0 && map.gasGrid.DensityAt(c, GasType.DeadlifeDust) == 0
                && enemies.All(e => c == pawn.Position || c.DistanceToSquared(e.Position) >= 9));
        }
        public static float PlannedJogStepTicks(Pawn pawn,IntVec3 previous,IntVec3 cell)
        {
            float step=cell.x!=previous.x && cell.z!=previous.z?pawn.TicksPerMoveDiagonal:pawn.TicksPerMoveCardinal;
            step+=pawn.Map.pathing.For(pawn).pathGrid.CalculatedCostAt(cell,false,previous);
            step+=(float)(cell.GetEdifice(pawn.Map)?.PathWalkCostFor(pawn) ?? 0);
            foreach(var tag in cell.GetTerrain(pawn.Map).tags ?? new List<string>())
                if(pawn.kindDef.moveSpeedFactorByTerrainTag.TryGetValue(tag,out var factor) && factor>0)step/=factor;
            return Math.Max(1f,Math.Min(450f,step));
        }
        public static bool FriendlyLaneClear(Pawn pawn,LocalTargetInfo target,IntVec3 from)
        {
            var verb=pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            return verb!=null && verb.TryFindShootLineFromTo(from,target,out var line)
                && FriendlyLineClear(pawn,target.Thing,line);
        }
        public static bool FutureFriendlyLaneClear(Pawn pawn,Pawn target,IntVec3 from,IntVec3 future,string phase="future_friendly_lane")
        {
            CombatPathBudgetHelper.Checkpoint("FutureFriendlyLaneClear");
            var verb=pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            bool available=CombatExposureHelper.TryPawnShootLine(verb,target,from,future,out var line)==true;
            bool clear=available && FriendlyLineClear(pawn,target,line);
#if LAYA_COMBAT_LAB
            if(clear)Controllers.CombatLabFutureGeometry.RecordFutureFriendlyLine(phase,pawn,target,verb,from,future,line);
#endif
            return clear;
        }
        private static bool FriendlyLineClear(Pawn pawn,Thing target,ShootLine line)
        {
            // Observe the native lean/source and near-shooter interception rule.
            // Do not change projectile flags, collision, damage or hit chances.
            bool bodyClear=!pawn.Map.mapPawns.AllPawnsSpawned.Any(p=>p!=pawn && p!=target && !p.Dead
                && (!p.HostileTo(pawn) && !CombatNativeHelper.ActivePredation(p)
                    || pawn.Faction==Faction.OfPlayer && p.IsPrisonerOfColony)
                && VerbUtility.InterceptChanceFactorFromDistance(line.Source.ToVector3Shifted(),p.Position)>0f
                // Keep body-sized lateral clearance but extend the far end by
                // one cell: an observed native miss behind a melee target hit
                // a stationary ally just beyond the old segment. This does
                // not claim to bound every native miss or later ally motion.
                && CombatInterceptMath.InterveningAlly(line.Source.x,line.Source.z,line.Dest.x,line.Dest.z,p.Position.x,p.Position.z,
                    CombatInterceptMath.FriendlyBodyRadius(p.BodySize),1f));
            return bodyClear && (!(target is Pawn aimed) || CombatFriendlyFireHelper.LaneClear(pawn,aimed,line.Source,line));
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
            var active=pawn.stances.curStance as Stance_Warmup;
            bool warming=active!=null && active.verb==verb && active.focusTarg.Thing==target;
            float aim=warming?active.ticksLeft:verb.verbProps.warmupTime*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor);
            float flight=projectile==null?0f:CombatInterceptMath.NativeFlightTicks(pawn.Position.DistanceTo(target.Position),projectile.SpeedTilesPerTick);
            if(float.IsInfinity(flight))return false;
            float lockTicks=active!=null?0f:MovementLockTicks(pawn); // Warmup can be cancelled; native cooldown cannot.
            float horizon=CombatInterceptMath.FirstShotDelay(aim,lockTicks,warming)+flight;
            // A short observed path is unknown beyond its end, not evidence
            // that a currently available shot is impossible.
            if(horizon>route[route.Count-1].Item2)
                return CombatInterceptMath.ImmediateWindow(true,false,false);
            var future=Future(route,horizon);
            if(pawn.Position.DistanceTo(future)>verb.verbProps.range-1f)return false;
            // Unknown future geometry cannot erase a checked current shot.
            bool hit=CombatExposureHelper.CanHitPawnAt(verb,target,pawn.Position,future)
                ?? CombatInterceptMath.ImmediateWindow(true,false,false);
#if LAYA_COMBAT_LAB
            Controllers.CombatLabFutureGeometry.Record("can_shoot_now",pawn,target,verb,pawn.Position,future,
                horizon,route[route.Count-1].Item2,verb.CanHitTargetFrom(pawn.Position,new LocalTargetInfo(future)),hit);
#endif
            return hit;
        }
        public static bool InteriorShotWindow(Pawn pawn,Pawn target)
        {
            if(!CanShootNow(pawn,target))return false;
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            float range=verb.verbProps.range,minimum=verb.verbProps.minRange;
            if(!CombatInterceptMath.FiringWindow(range,minimum,pawn.Position.DistanceTo(target.Position)))return false;
            var route=TargetRoute(target);if(route==null || route.Count==0)return false;
            float aim=verb.verbProps.warmupTime*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor);
            var projectile=verb.verbProps.defaultProjectile?.projectile;
            float flight=projectile==null?0f:CombatInterceptMath.NativeFlightTicks(range,projectile.SpeedTilesPerTick);
            if(float.IsInfinity(flight))return false;
            float burst=Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots;
            float horizon=CombatInterceptMath.ShotHorizon(MovementLockTicks(pawn),aim+burst,flight);
            var future=Future(route,horizon);
            if(!CombatInterceptMath.FiringWindow(range,minimum,pawn.Position.DistanceTo(future)))return false;
            bool hit=CombatExposureHelper.CanHitPawnAt(verb,target,pawn.Position,future)==true;
#if LAYA_COMBAT_LAB
            Controllers.CombatLabFutureGeometry.Record("interior_shot_window",pawn,target,verb,pawn.Position,future,
                horizon,route[route.Count-1].Item2,hit);
#endif
            return hit && FutureFriendlyLaneClear(pawn,target,pawn.Position,future,"interior_shot_window");
        }
        public static bool TryPosition(Pawn pawn, Pawn target, out IntVec3 result, bool defensive=false)
        {
            result = IntVec3.Invalid; LastPrediction = null;
            var verb = pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if (verb == null || verb.IsMeleeAttack || pawn.WorkTagIsDisabled(WorkTags.Violent)) return false;
            var projectile=verb.verbProps.defaultProjectile?.projectile;
            if(target.carryTracker?.CarriedThing is Pawn carried && carried.Faction==Faction.OfPlayer
                && (projectile?.explosionRadius>0 || projectile?.damageDef==DamageDefOf.Flame))return false;
            // No native job/path at admission is an unknown departure, not a
            // stationary carrier for the entire travel/aim horizon. A selected
            // guard lets the engine establish its own route before replanning.
            if(CarrierRoutePending(target)){LastPrediction="native_carrier_route_pending";return false;}
            var route = TargetRoute(target); if (route == null) return false;
            if(route.Count>1 && CombatCarrierInterceptHelper.Eligible(target))
                return CombatCarrierInterceptHelper.TryPosition(pawn,target,route,out result,out LastPrediction);
            float range = verb.verbProps.range, minimum = verb.verbProps.minRange;
            float warmup = verb.verbProps.warmupTime * 60f * pawn.GetStatValue(StatDefOf.AimingDelayFactor);
            bool carrier=CombatNativeHelper.Kidnapper(target);
            float moveLock=pawn.stances.curStance is Stance_Warmup?0:MovementLockTicks(pawn);
            float engagement=CombatInterceptMath.EngagementTicks(carrier,CombatNativeHelper.AbductionThreat(target),warmup,
                Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots,
                pawn.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f);
            // Projectile speed has native units distinct from seconds. Use
            // the loaded per-tick property, as Projectile.StartingTicksToImpact does.
            float flight=projectile==null?0f:CombatInterceptMath.NativeFlightTicks(range,projectile.SpeedTilesPerTick);
            if(float.IsInfinity(flight)){LastPrediction="native_projectile_flight_unavailable";return false;}
            Func<float,float> horizonFor=travel=>CombatInterceptMath.ShotHorizon(travel+moveLock,warmup+engagement,flight);
            Func<float,bool> window=distance=>carrier?CombatInterceptMath.CarrierWindow(range,minimum,distance)
                :CombatInterceptMath.FiringWindow(range,minimum,distance);
            var map = pawn.Map; var candidates = new HashSet<IntVec3>();
            float currentCover=CoverUtility.CalculateOverallBlockChance(pawn,target.Position,map);
            // Current neighborhood plus points beside the observed escape path. Search is bounded.
            foreach (var c in GenRadial.RadialCellsAround(pawn.Position, 36f, true).Where((c,i) => i % 8 == 0)) candidates.Add(c);
            foreach (float horizon in new[] { 120f, 240f, 480f, 720f, 960f })
            {
                CombatPathBudgetHelper.Checkpoint();
                var lead = Future(route, horizon);
                int offset = (int)Math.Max(7f, range * .55f);
                foreach (var direction in GenAdj.CardinalDirections)
                    foreach (var c in GenRadial.RadialCellsAround(lead + direction * offset, 3f, true)) candidates.Add(c);
            }
            var committed=pawn.CurJobDef==JobDefOf.Goto ? pawn.CurJob.targetA.Cell : IntVec3.Invalid;
            if(committed.IsValid)candidates.Add(committed);
            var shortlist = candidates.Where(c => c.InBounds(map) && c.Standable(map) && !c.Fogged(map)
                && pawn.CanReserve(c) && !CombatControlHelper.CellClaimed(pawn,c)
                && !c.GetThingList(map).OfType<Pawn>().Any(p => p != pawn)
                && FriendlyLaneClear(pawn,target,c)
                && window(c.DistanceTo(Future(route,horizonFor(
                    CombatInterceptMath.StraightTravelTicks(c.x-pawn.Position.x,c.z-pawn.Position.z,pawn.TicksPerMoveCardinal,pawn.TicksPerMoveDiagonal))))))
                .OrderBy(c => c==committed ? -1 : c.DistanceToSquared(pawn.Position)).Take(48).ToList();
            float best = float.MaxValue, bestTravel = 0, bestHorizon = 0; var bestTarget = IntVec3.Invalid;
            foreach (var cell in shortlist)
            {
                CombatPathBudgetHelper.Checkpoint();
                using (var path = CombatPathBudgetHelper.Query(pawn,pawn.Position,cell,PathEndMode.OnCell))
                {
                    if (!MovementSafe(pawn, path)) continue;
                    float travel = path.TotalCost; // Native path cost, loaded movement/terrain; not just straight distance.
                    // An observed own melee pursuer can reach this gun while
                    // it walks toward a different target. Current-position
                    // clearance alone does not cover that firing approach.
                    if(!CombatPursuitApproachHelper.Check(pawn,target,path,travel).Clear)continue;
                    float horizon = horizonFor(travel);
                    if (route.Count > 1 && horizon > route[route.Count - 1].Item2) continue;
                    var predicted = Future(route, horizon);
                    if(!window(cell.DistanceTo(predicted)))continue;
                    bool hit=CombatExposureHelper.CanHitPawnAt(verb,target,cell,predicted)==true;
#if LAYA_COMBAT_LAB
                    Controllers.CombatLabFutureGeometry.Record("try_position",pawn,target,verb,cell,predicted,
                        horizon,route[route.Count-1].Item2,verb.CanHitTargetFrom(cell,new LocalTargetInfo(predicted)),hit);
#endif
                    if(!hit || !FutureFriendlyLaneClear(pawn,target,cell,predicted,"try_position"))continue;
                    float coverRating=CoverUtility.CalculateOverallBlockChance(new LocalTargetInfo(cell),target.Position,map);
                    bool cover=coverRating>=.4f;
                    if(defensive && currentCover>=.3f && coverRating<currentCover-.1f)continue;
                    if(defensive && (cell.DistanceTo(CombatControlHelper.DefensiveAnchor(pawn))>8f
                        || !CombatInterceptMath.DefensiveAdvance(cell.DistanceTo(pawn.Position),
                        pawn.Position.DistanceTo(target.Position),cell.DistanceTo(target.Position),cover)))continue;
                    // An actual escaping carrier needs an interior firing
                    // window. The very earliest edge shot can strand the only
                    // forward interceptor after one inaccurate volley.
                    float score = horizon*(carrier ? .3f : 1f) + cell.DistanceTo(predicted)*(carrier ? 12f : 2f) - coverRating*100f;
                    if (score >= best) continue;
                    best = score; result = cell; bestTravel = travel; bestHorizon = horizon; bestTarget = predicted;
                    if(cell==committed)break; // Keep a still timely route; replace it only when its window is invalid.
                }
            }
            if (!result.IsValid) return false;
            LastPrediction = $"{pawn.LabelShort}: estimated travel {bestTravel:0} ticks + move lock {moveLock:0} + aim {warmup:0} + engagement {engagement:0} + flight/buffer -> {bestHorizon:0}; "
                + $"target {target.thingIDNumber} forecast ({bestTarget.x},{bestTarget.z}), firing cell ({result.x},{result.z}); "
                + "current path can change; arrival, sight, shot and hit require fresh verification";
            return true;
        }
        public static bool CarrierWindowNeedsAdvance(Pawn pawn,Pawn target)
        {
            if(!CombatNativeHelper.AbductionThreat(target))return false;
            var verb=pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            var route=TargetRoute(target);if(verb==null || route==null || !route.Any())return false;
            if(CombatCarrierInterceptHelper.Eligible(target))
                return !CombatCarrierInterceptHelper.HasCurrentWindow(pawn,target,route);
            float cycle=verb.verbProps.warmupTime*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor)
                +Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots
                +pawn.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f;
            var future=Future(route,Math.Min(route.Last().Item2,MovementLockTicks(pawn)+cycle*2f+90f));
            return pawn.Position.DistanceTo(future)>verb.verbProps.range*.6f;
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

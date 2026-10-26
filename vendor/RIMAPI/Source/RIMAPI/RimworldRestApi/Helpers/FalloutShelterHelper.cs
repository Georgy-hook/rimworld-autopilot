using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;
using RIMAPI.Core;
using RIMAPI.Models;

namespace RIMAPI.Helpers
{
    public class ShelterAreaRecord : IExposable
    {
        public int PawnId, MapId, AreaId, PreviousAreaId = -1;
        public string Hazards;
        public void ExposeData()
        {
            Scribe_Values.Look(ref PawnId, "pawn"); Scribe_Values.Look(ref MapId, "map");
            Scribe_Values.Look(ref AreaId, "shelter"); Scribe_Values.Look(ref PreviousAreaId, "previous", -1);
            Scribe_Values.Look(ref Hazards, "hazards");
        }
    }
    public class ShelterAreaState : GameComponent
    {
        public List<ShelterAreaRecord> Records = new List<ShelterAreaRecord>();
        private float lastReview;
        private int lastTick;
        public ShelterAreaState(Game game) { }
        public override void ExposeData()
        {
            Scribe_Collections.Look(ref Records, "layaShelterAreas", LookMode.Deep);
            if (Scribe.mode == LoadSaveMode.PostLoadInit && Records == null) Records = new List<ShelterAreaRecord>();
        }
        public override void GameComponentTick()
        {
            // Bound expensive geometry/path work, while cleanup has an independent watchdog.
            if (Find.TickManager.TicksGame - lastTick < 2000 || UnityEngine.Time.realtimeSinceStartup - lastReview < 30f) return;
            lastTick = Find.TickManager.TicksGame; lastReview = UnityEngine.Time.realtimeSinceStartup;
            foreach (var record in Records.ToArray()) EnvironmentalAreaHelper.Review(this, record);
        }
    }
    public static class FalloutShelterHelper
    {
        public static bool Active(Map map) => map.gameConditionManager.ActiveConditions.Any(c => c.def.defName == "ToxicFallout");
        public static bool Susceptible(Pawn pawn)
        {
            var resistance = DefDatabase<StatDef>.GetNamedSilentFail("ToxicEnvironmentResistance");
            return resistance == null || pawn.GetStatValue(resistance) < .999f;
        }
        public static bool SafeCell(Pawn pawn, IntVec3 cell) => EnvironmentalAreaHelper.SafeCell(pawn, cell, "fallout", null);
        public static void AddOptions(Map map, ResilienceContextDto context) => EnvironmentalAreaHelper.AddOptions(map, context);
        public static ApiResult<CapabilityOrderResultDto> Execute(ResilienceOrderRequestDto request, Pawn pawn) => EnvironmentalAreaHelper.Execute(request, pawn);
    }
    /// <summary>Temporary ordinary allowed areas. They do not teleport, cure, or constrain drafted paths.</summary>
    public static class EnvironmentalAreaHelper
    {
        public static bool ColdRestrictionNeeded(float severity, float temperature, float comfortableMin) => severity > .03f || temperature < comfortableMin - 10f;
        public static bool HeatRestrictionNeeded(float severity, float temperature, float comfortableMax) => severity > .03f || temperature > comfortableMax + 10f;
        public static bool ExposureRouteAllowed(int cells, float toxin, bool transition) => cells == 0 || transition && cells <= (toxin >= .5f ? 12 : 40);
        private static int dangerFrame = -1, dangerMap = -1;
        private static Tuple<IntVec3, float>[] dangers = new Tuple<IntVec3, float>[0];
        private static Tuple<IntVec3, float>[] Dangers(Pawn p)
        {
            if (dangerFrame == UnityEngine.Time.frameCount && dangerMap == p.Map.uniqueID) return dangers;
            dangerFrame = UnityEngine.Time.frameCount; dangerMap = p.Map.uniqueID;
            dangers = p.Map.mapPawns.AllPawnsSpawned.Where(e => !e.Dead && !e.Downed && !e.Position.Fogged(p.Map)
                && (e.HostileTo(Faction.OfPlayer) || CombatNativeHelper.ActivePredation(e)))
                .Select(e => Tuple.Create(e.Position, Math.Max(20f, (e.equipment?.Primary?.def.Verbs?.FirstOrDefault()?.range ?? 0f) + 8f)))
                .Concat(p.Map.listerBuildings.allBuildingsNonColonist.Where(e=>!e.Position.Fogged(p.Map) && CombatNativeHelper.ActiveStructure(e))
                    .Select(e => Tuple.Create(e.Position, Math.Max(20f, (e as Building_Turret)?.AttackVerb?.EffectiveRange ?? 0f) + 8f))).ToArray();
            return dangers;
        }
        private static ShelterAreaState State => Current.Game.GetComponent<ShelterAreaState>();
        private static ShelterAreaRecord Record(Pawn p) => State.Records.FirstOrDefault(r => r.PawnId == p.thingIDNumber && r.MapId == p.Map.uniqueID);
        public static bool Managed(Pawn p) => Record(p) != null;
        private static float Injury(Pawn p, string name) => p.health.hediffSet.hediffs.Where(h => h.def.defName == name).Select(h => h.Severity).DefaultIfEmpty(0f).Max();
        private static bool Protected(Pawn p) => p.Dead || p.Downed || p.Drafted || p.InMentalState
            || CombatNativeHelper.HasCareJob(p) || CareTriageHelper.QueuedCare(p)
            || p.carryTracker?.CarriedThing != null || p.CurJobDef == JobDefOf.Ingest || p.IsBurning();
        private static bool Threat(Map m) => m.mapPawns.AllPawnsSpawned.Any(p => !p.Dead && !p.Downed && !p.Position.Fogged(m)
            && (p.HostileTo(Faction.OfPlayer) || CombatNativeHelper.ActivePredation(p)))
            || m.listerBuildings.allBuildingsNonColonist.Any(b=>!b.Position.Fogged(m) && CombatNativeHelper.ActiveStructure(b));
        private static string Hazards(Pawn p, ShelterAreaRecord record = null)
        {
            var kinds = new List<string>();
            if (FalloutShelterHelper.Active(p.Map) && FalloutShelterHelper.Susceptible(p)) kinds.Add("fallout");
            if (Threat(p.Map)) kinds.Add("threat");
            float temp = p.Position.GetTemperature(p.Map), low = p.GetStatValue(StatDefOf.ComfyTemperatureMin), high = p.GetStatValue(StatDefOf.ComfyTemperatureMax);
            if (ColdRestrictionNeeded(Injury(p, "Hypothermia"), temp, low)) kinds.Add("cold");
            if (HeatRestrictionNeeded(Injury(p, "Heatstroke"), temp, high)) kinds.Add("heat");
            // A local gas/fire restriction remains until the original work area has cleared.
            Area original = Original(p, record);
            if (record?.Hazards?.Contains("local") == true
                ? OriginalCells(p, original).Any(c => LocalDanger(p.Map, c)) : LocalDanger(p.Map, p.Position)) kinds.Add("local");
            return string.Join("+", kinds);
        }
        private static Area Original(Pawn p, ShelterAreaRecord r) => r == null ? p.playerSettings.AreaRestrictionInPawnCurrentMap
            : p.Map.areaManager.AllAreas.FirstOrDefault(a => a.ID == r.PreviousAreaId);
        private static bool OriginalKnown(Pawn p, ShelterAreaRecord r) => r == null || r.PreviousAreaId == -1 || Original(p, r) != null;
        private static IEnumerable<IntVec3> OriginalCells(Pawn p, Area original) => original?.ActiveCells ?? p.Map.areaManager.Home.ActiveCells;
        private static bool LocalDanger(Map map, IntVec3 c) => c.ContainsStaticFire(map)
            || map.gasGrid.DensityAt(c, GasType.ToxGas) > 0 || map.gasGrid.DensityAt(c, GasType.DeadlifeDust) > 0
            || map.gasGrid.DensityAt(c, GasType.RotStink) > 0;
        private static bool ThreatCellSafe(Pawn p, IntVec3 c) => !Dangers(p).Any(d => c.InHorDistOf(d.Item1, d.Item2));
        public static bool SafeCell(Pawn p, IntVec3 cell, string hazards, Area original)
        {
            // PassThroughOnly includes beds and doors: excluding them would block rest and split a roofed corridor.
            if (!cell.InBounds(p.Map) || cell.Fogged(p.Map) || !cell.Walkable(p.Map) || LocalDanger(p.Map, cell)
                || original != null && !original[cell] || !ThreatCellSafe(p, cell)) return false;
            if (hazards.Contains("fallout") && !cell.Roofed(p.Map)) return false;
            // Civilians use the completed home footprint, not arbitrary distant safe-looking corners.
            if (hazards.Contains("threat") && !p.Map.areaManager.Home[cell]) return false;
            float temp = cell.GetTemperature(p.Map), low = p.GetStatValue(StatDefOf.ComfyTemperatureMin), high = p.GetStatValue(StatDefOf.ComfyTemperatureMax);
            return temp >= low - (hazards.Contains("cold") ? 0 : 10f)
                && temp <= high + (hazards.Contains("heat") ? 0 : 10f);
        }
        public static bool PathSafe(Pawn p, IntVec3 destination, bool transition = false, PathEndMode endMode = PathEndMode.OnCell)
        {
            using (var path = p.Map.pathFinder.FindPathNow(p.Position, destination, p, null, endMode))
            {
                if (!path.Found) return false;
                int exposed = 0, thermalSteps = 0; Area current = p.playerSettings?.AreaRestrictionInPawnCurrentMap;
                var record = Record(p); Area prior = Original(p, record);
                foreach (var cell in path.NodesReversed)
                {
                    if (cell.Fogged(p.Map) || LocalDanger(p.Map, cell) && !(transition && cell==p.Position) || !ThreatCellSafe(p, cell)
                        || prior != null && !prior[cell] || !transition && current != null && !current[cell]) return false;
                    if (FalloutShelterHelper.Active(p.Map) && FalloutShelterHelper.Susceptible(p) && !cell.Roofed(p.Map)) exposed++;
                    float temp=cell.GetTemperature(p.Map);
                    if (temp<p.GetStatValue(StatDefOf.ComfyTemperatureMin)-10f || temp>p.GetStatValue(StatDefOf.ComfyTemperatureMax)+10f) thermalSteps++;
                }
                return ExposureRouteAllowed(exposed,Injury(p,"ToxicBuildup"),transition)
                    && (thermalSteps==0 || transition && thermalSteps<=40);
            }
        }
        private static List<IntVec3> Cells(Pawn p, ShelterAreaRecord record, string hazards) => p.Map.areaManager.Home.ActiveCells
            .Where(c => SafeCell(p, c, hazards, Original(p, record))).ToList();
        private static List<IntVec3> Connected(List<IntVec3> cells, IntVec3 start)
        {
            var allowed = new HashSet<IntVec3>(cells); var visited = new HashSet<IntVec3> { start }; var queue = new Queue<IntVec3>(); queue.Enqueue(start);
            while (queue.Count > 0) { var cell = queue.Dequeue(); foreach (var direction in GenAdj.CardinalDirections)
            { var next = cell + direction; if (allowed.Contains(next) && visited.Add(next)) queue.Enqueue(next); } }
            return visited.ToList();
        }
        private static List<IntVec3> DestinationArea(Pawn p, ShelterAreaRecord record, string hazards, out IntVec3 destination)
        {
            var cells = Cells(p, record, hazards);
            var allowed = new HashSet<IntVec3>(cells);
            var serviceCells = p.Map.listerThings.AllThings.Where(t => allowed.Contains(t.Position)
                && (t is Building_Bed || t is Building_WorkTable || t.def.IsIngestible)).Select(t => t.Position).Distinct();
            var candidates = serviceCells.Concat(cells.OrderBy(c => c.DistanceToSquared(p.Position)).Take(8))
                .OrderBy(c => c.DistanceToSquared(p.Position)).Take(24).ToList();
            List<IntVec3> best = null; int bestScore = -1; destination = IntVec3.Invalid;
            var visited = new HashSet<IntVec3>();
            foreach (var cell in candidates)
            {
                if (visited.Contains(cell)) continue;
                if (cell.Standable(p.Map) && p.CanReserveAndReach(cell, PathEndMode.OnCell, Danger.Some) && PathSafe(p, cell, true))
                {
                    var connected = Connected(cells, cell); visited.UnionWith(connected); var region = new HashSet<IntVec3>(connected);
                    int score = p.Map.listerThings.AllThings.Where(t => region.Contains(t.Position))
                        .Sum(t => t is Building_Bed ? 20 : t.def.IsIngestible && t.IngestibleNow && p.RaceProps.CanEverEat(t) ? 12 : t is Building_WorkTable ? 4 : 0);
                    if (score > bestScore) { best = connected; bestScore = score; destination = cell; }
                }
            }
            return best ?? new List<IntVec3>();
        }
        private static object Services(Pawn p, HashSet<IntVec3> cells)
        {
            var things = p.Map.listerThings.AllThings.Where(t => cells.Contains(t.Position) && !t.Position.Fogged(p.Map)).ToList();
            var beds = things.OfType<Building_Bed>().Where(b => b.Faction == Faction.OfPlayer && !b.ForPrisoners
                && RestUtility.CanUseBedEver(p, b.def) && !b.CurOccupants.Any(o => o != p)).Select(b => b.thingIDNumber).ToList();
            var food = things.Where(t => t.def.IsIngestible && t.IngestibleNow && p.RaceProps.CanEverEat(t)
                && (p.foodRestriction?.CurrentFoodPolicy?.filter.Allows(t.def) ?? true)
                && !t.IsForbidden(p) && p.CanReserve(t)).Select(t => t.thingIDNumber).ToList();
            return new { food_ids = food.Take(24).ToList(), usable_bed_ids = beds.Take(12).ToList(),
                food_urgent = p.needs?.food?.CurLevelPercentage < .3f && food.Count == 0,
                rest_urgent = p.needs?.rest?.CurLevelPercentage < .3f && beds.Count == 0,
                joy = p.needs?.joy?.CurLevelPercentage, mood = p.needs?.mood?.CurLevelPercentage,
                work_tables = things.OfType<Building_WorkTable>().Select(t => t.thingIDNumber).Take(12).ToList(),
                research_benches = things.Where(t => t.def.defName.Contains("ResearchBench")).Select(t => t.thingIDNumber).ToList(),
                note = "Food/bed in footprint is not arrival, a safe subsequent path, ingestion or sleep. Keep care, recreation and finite indoor jobs; unmet services require safe delivery/roofed connection, not indefinite idle confinement." };
        }
        public static void AddOptions(Map map, ResilienceContextDto context)
        {
            foreach (var p in map.mapPawns.AllPawnsSpawned.Where(p => !p.Dead && (p.IsColonistPlayerControlled || p.RaceProps.Animal && p.Faction == Faction.OfPlayer)
                && p.playerSettings?.SupportsAllowedAreas == true))
            {
                var r = Record(p); var hazards = Hazards(p, r); Area current = p.playerSettings.AreaRestrictionInPawnCurrentMap;
                bool overridden = r != null && current?.ID != r.AreaId;
                // Read-only context: active records are reviewed by the independent native watchdog.
                if (r != null && (hazards.Length == 0 || overridden))
                {
                    context.Options.Add(new ResilienceOptionDto { Kind = "area_release", WorkerId = p.thingIDNumber, TargetId = p.thingIDNumber,
                        Giver = r.AreaId.ToString(), Worker = p.LabelShort, Target = "Restore earlier area if still managed; preserve later override" });
                    continue;
                }
                if (hazards.Length == 0 || Protected(p) || !OriginalKnown(p, r)) continue;
                var cells = DestinationArea(p, r, hazards, out var destination);
                var set = new HashSet<IntVec3>(cells);
                context.AreaRestrictions.Add(new { pawn_id = p.thingIDNumber, hazards, current_area_id = current?.ID,
                    managed_area_id = r?.AreaId, previous_area_id = r?.PreviousAreaId, destination = destination.IsValid ? (object)new {x=destination.x,z=destination.z} : null,
                    safe_cells = cells.Count, services = Services(p, set),
                    blocked_reason = !destination.IsValid ? "no_existing_safe_connected_area_or_route" : null,
                    review_wall_seconds = 30, review_ticks = 2000, area_is_not_path_or_job_guarantee = true });
                if (!destination.IsValid || r != null && r.Hazards == hazards && current != null
                    && set.SetEquals(current.ActiveCells) && set.Contains(p.Position)) continue;
                context.Options.Add(new ResilienceOptionDto { Kind = "area_shelter", WorkerId = p.thingIDNumber, TargetId = p.thingIDNumber,
                    Giver = (current?.ID ?? -1) + ":" + hazards, Worker = p.LabelShort,
                    Target = hazards + " safe connected area; unmet food/sleep must be supplied; normal indoor work continues",
                    TravelDistance = p.Position.DistanceTo(destination), DestinationTemperature = destination.GetTemperature(map),
                    PrerequisiteReason = "Preserve prior area and care/ingestion. Actual route checked only for this transition; native watchdog expands/reopens when safe." });
            }
        }
        private static void Restore(ShelterAreaState state, ShelterAreaRecord r, Pawn p)
        {
            Area area = p.Map.areaManager.AllAreas.FirstOrDefault(a => a.ID == r.AreaId);
            if (p.playerSettings.AreaRestrictionInPawnCurrentMap == area)
            {
                if (!OriginalKnown(p, r)) return; // Unknown old restriction must not become unrestricted.
                p.playerSettings.AreaRestrictionInPawnCurrentMap = Original(p, r);
            }
            state.Records.Remove(r);
            if (area != null && !p.Map.mapPawns.AllPawnsSpawned.Any(o => o.playerSettings?.AreaRestrictionInPawnCurrentMap == area)) area.Delete();
        }
        public static void Review(ShelterAreaState state, ShelterAreaRecord r)
        {
            var map = Find.Maps.FirstOrDefault(m => m.uniqueID == r.MapId);
            var p = map?.mapPawns.AllPawnsSpawned.FirstOrDefault(o => o.thingIDNumber == r.PawnId);
            if (p == null || p.Dead)
            {
                var absent=PawnHelper.FindPawnById(r.PawnId);
                if (absent!=null && !absent.Dead) return; // A living caravan member may return to this map.
                var orphan=map?.areaManager.AllAreas.FirstOrDefault(a=>a.ID==r.AreaId);
                if (orphan!=null && !map.mapPawns.AllPawnsSpawned.Any(o=>o.playerSettings?.AreaRestrictionInPawnCurrentMap==orphan)) orphan.Delete();
                state.Records.Remove(r); return;
            }
            if (p.playerSettings.AreaRestrictionInPawnCurrentMap?.ID != r.AreaId || Hazards(p, r).Length == 0)
            { Restore(state, r, p); return; }
            if (!OriginalKnown(p, r) || Protected(p)) return;
            var hazards = Hazards(p, r); var cells = DestinationArea(p, r, hazards, out var destination);
            var area = map.areaManager.AllAreas.FirstOrDefault(a => a.ID == r.AreaId);
            if (area == null || cells.Count == 0) return;
            // Recompute the widest connected safe footprint inside the original restriction.
            // Newly completed roofs/doors and improving temperatures can restore food, sleep and work access.
            area.Clear(); foreach (var c in cells) area[c] = true; r.Hazards = hazards;
            if ((!cells.Contains(p.Position) || JobOutside(p,new HashSet<IntVec3>(cells))) && !Protected(p))
                p.jobs.TryTakeOrderedJob(JobMaker.MakeJob(JobDefOf.Goto, destination));
        }
        private static bool JobOutside(Pawn p,HashSet<IntVec3> cells) => p.CurJob != null
            && new[]{p.CurJob.targetA,p.CurJob.targetB,p.CurJob.targetC}.Any(t=>t.IsValid && !cells.Contains(t.Cell));
        public static ApiResult<CapabilityOrderResultDto> Execute(ResilienceOrderRequestDto request, Pawn p)
        {
            var result = new CapabilityOrderResultDto { TargetId = request.TargetId, Reason = "area_selection_no_longer_feasible" };
            if (p == null || p.Dead || !p.Spawned || !(p.IsColonistPlayerControlled || p.RaceProps.Animal && p.Faction == Faction.OfPlayer) || request.WorkerId != request.TargetId
                || p.playerSettings?.SupportsAllowedAreas != true) return ApiResult<CapabilityOrderResultDto>.Ok(result);
            var r = Record(p); var hazards = Hazards(p, r); var current = p.playerSettings.AreaRestrictionInPawnCurrentMap;
            if (request.Kind == "area_release")
            {
                if (r == null || request.Giver != r.AreaId.ToString() || hazards.Length != 0 && current?.ID == r.AreaId) return ApiResult<CapabilityOrderResultDto>.Ok(result);
                Restore(State, r, p); result.Applied = !State.Records.Contains(r); result.Reason = "previous_area_restored_or_later_override_preserved";
                return ApiResult<CapabilityOrderResultDto>.Ok(result);
            }
            if (hazards.Length == 0 || Protected(p) || !OriginalKnown(p, r)
                || r != null && current?.ID != r.AreaId || request.Giver != (current?.ID ?? -1) + ":" + hazards) return ApiResult<CapabilityOrderResultDto>.Ok(result);
            var cells = DestinationArea(p, r, hazards, out var destination);
            if (!destination.IsValid) return ApiResult<CapabilityOrderResultDto>.Ok(result);
            Area_Allowed area = r == null ? null : p.Map.areaManager.AllAreas.OfType<Area_Allowed>().FirstOrDefault(a => a.ID == r.AreaId);
            if (area == null && !p.Map.areaManager.TryMakeNewAllowed(out area)) { result.Reason = "allowed_area_capacity_exhausted"; return ApiResult<CapabilityOrderResultDto>.Ok(result); }
            if (r == null) { r = new ShelterAreaRecord { PawnId = p.thingIDNumber, MapId = p.Map.uniqueID, AreaId = area.ID,
                PreviousAreaId = current?.ID ?? -1 }; State.Records.Add(r); }
            r.Hazards = hazards; area.SetLabel("Laya safe " + p.thingIDNumber); area.Clear(); foreach (var c in cells) area[c] = true;
            p.playerSettings.AreaRestrictionInPawnCurrentMap = area;
            bool moved = cells.Contains(p.Position) && !JobOutside(p,new HashSet<IntVec3>(cells))
                || p.jobs.TryTakeOrderedJob(JobMaker.MakeJob(JobDefOf.Goto, destination));
            result.Applied = true; result.Reason = moved ? "temporary_area_assigned; walk_scheduled_or_already_inside; arrival_and_recovery_unverified"
                : "area_assigned_but_walk_rejected; actual_shelter_unverified";
            return ApiResult<CapabilityOrderResultDto>.Ok(result);
        }
    }
}

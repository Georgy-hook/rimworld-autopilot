using System;
using System.Collections.Generic;
using System.Linq;
using RIMAPI.Core;
using RIMAPI.Models;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class ProductionLogisticsHelper
    {
        public sealed class Choice
        {
            public string key;
            public string kind;
            public int target_id;
            public int worker_id;
            public string value;
            public string label;
            public string cost;
            public string risk;
            public IntVec3[] cells;
        }

        private static bool Material(Thing thing)
        {
            return thing.Spawned && thing.def.category == ThingCategory.Item && thing.def.ingestible == null
                && !thing.IsBurning() && !thing.Position.Fogged(thing.Map)
                && (thing.TryGetComp<CompRottable>() == null || thing.TryGetComp<CompRottable>().Stage == RotStage.Fresh);
        }

        private static bool Worker(Pawn pawn, WorkTypeDef work)
        {
            return !pawn.Dead && !pawn.Downed && !pawn.Drafted && !pawn.InMentalState && pawn.workSettings != null
                && !pawn.WorkTypeIsDisabled(work) && pawn.workSettings.GetPriority(work) > 0
                && pawn.CurJobDef != JobDefOf.DoBill && pawn.CurJobDef != JobDefOf.TendPatient
                && pawn.CurJobDef != JobDefOf.FeedPatient && pawn.CurJobDef != JobDefOf.Rescue;
        }

        private static IntVec3[] StorageCells(Building_WorkTable table)
        {
            Map map = table.Map;
            Room room = table.GetRoom();
            if (room == null || room.PsychologicallyOutdoors) return new IntVec3[0];
            return CellRect.CenteredOn(table.Position, 3).Cells.Where(c => c.InBounds(map) && c.Standable(map)
                && c.GetRoom(map) == room && c.GetZone(map) == null && c.GetEdifice(map) == null
                && c.Roofed(map) && c != table.InteractionCell).ToArray();
        }

        // Physical capacity deliberately ignores worker routes and reservations.
        // Native cell rules retain stack compatibility, shelf slot limits, fire
        // and construction blockers. GET never changes a live storage filter.
        private static bool CellCapacity(Map map, IEnumerable<IntVec3> cells, Thing thing)
            => cells.Any(c => c.InBounds(map) && StoreUtility.IsGoodStoreCell(c, map, thing, null, null));

        private static bool HasCapacity(Map map, Thing thing)
        {
            return map.haulDestinationManager.AllHaulDestinationsListInPriorityOrder.Any(destination =>
                destination.HaulDestinationEnabled
                && (!(destination is Thing owner) || owner.Faction == Faction.OfPlayer)
                && destination.Accepts(thing)
                && (destination is ISlotGroupParent slots
                    ? CellCapacity(map, slots.GetSlotGroup().CellsList, thing)
                    : destination is Thing container && container.TryGetInnerInteractableThingOwner() != null
                      && container.TryGetInnerInteractableThingOwner().CanAcceptAnyOf(thing)
                      && (!(container is IHaulEnroute enroute) || enroute.GetSpaceRemainingWithEnroute(thing.def) > 0)));
        }

        private static bool NeedsStorage(Thing thing)
        {
            SlotGroup group = thing.Position.GetSlotGroup(thing.Map);
            return group == null || !group.parent.Accepts(thing);
        }

        public static List<Choice> Options(Map map, List<object> blocked = null, List<ActiveNativeOrderDto> activeOrders = null)
        {
            var activeHauls = new HashSet<int>((activeOrders ?? ResilienceAutomationHelper.ActiveOrders(map))
                .Where(o => o.Kind == "haul").Select(o => o.TargetId));
            var options = new List<Choice>();
            Thing[] materials = map.listerThings.AllThings.Where(Material).ToArray();
            Pawn[] hostiles = map.mapPawns.AllPawnsSpawned.Where(p => !p.Dead && !p.Downed && p.HostileTo(Faction.OfPlayer)).ToArray();
            foreach (Thing thing in materials.Where(t => t.IsForbidden(Faction.OfPlayer) && !hostiles.Any(p => p.Position.DistanceTo(t.Position) < 30)).GroupBy(t => t.def)
                .Select(g => g.OrderBy(t => t.Position.Roofed(map)).ThenBy(t => t.HitPoints / (float)Math.Max(1, t.MaxHitPoints)).First()))
            {
                options.Add(new Choice
                {
                    key = "allow:" + thing.thingIDNumber, kind = "allow", target_id = thing.thingIDNumber,
                    label = "Allow " + thing.LabelCap, cost = "May trigger ordinary hauling/production consumption",
                    risk = "Previously forbidden stock becomes usable; no hostile within 30 cells, but route safety remains uncertain"
                });
            }
            Building_Storage[] storages = map.listerBuildings.allBuildingsColonist.OfType<Building_Storage>().ToArray();
            Zone_Stockpile[] zones = map.zoneManager.AllZones.OfType<Zone_Stockpile>().ToArray();
            var capacityCache = new Dictionary<Thing, bool>();
            Func<Thing, bool> hasCapacity = t => {
                if (!capacityCache.TryGetValue(t, out bool found))
                    capacityCache[t] = found = HasCapacity(map, t);
                return found;
            };
            var needingStorage = materials.Where(NeedsStorage).GroupBy(t => t.def)
                .ToDictionary(g => g.Key, g => g.ToArray());
            ThingDef[] unstoredDefs = needingStorage.Where(g => !g.Value.Any(hasCapacity))
                .Select(g => g.Key).ToArray();
            foreach (var linked in storages.GroupBy(b => b.GetStoreSettings()))
            {
                foreach (ThingDef def in unstoredDefs)
                {
                    Building_Storage storage = linked.FirstOrDefault(b => !b.GetStoreSettings().AllowedToAccept(def)
                        && (b.GetParentStoreSettings()?.AllowedToAccept(def) ?? true)
                        && needingStorage[def].Any(t => CellCapacity(map, b.GetSlotGroup().CellsList, t)));
                    if (storage == null) continue;
                    options.Add(new Choice
                    {
                        key = $"shelf:{storage.thingIDNumber}:{def.defName}", kind = "shelf", target_id = storage.thingIDNumber,
                        value = def.defName, label = storage.LabelShortCap + ": allow " + def.LabelCap,
                        cost = "Storage capacity and hauling labor", risk = "Linked shelves sharing settings affected=" + linked.Count() + "; other allowances compete for capacity; existing quality/special filters remain"
                    });
                }
            }
            foreach (Zone_Stockpile zone in zones)
            {
                foreach (ThingDef def in unstoredDefs.Where(d => !zone.settings.AllowedToAccept(d) && needingStorage[d].Any(t => CellCapacity(map, zone.Cells, t))))
                    options.Add(new Choice
                    {
                        key = $"stockpile:{zone.ID}:{def.defName}", kind = "stockpile", target_id = zone.ID,
                        value = def.defName, label = zone.label + ": allow " + def.LabelCap,
                        cost = "Hauling labor and floor capacity", risk = "Outdoor/roof exposure and priority affect material delivery; existing allowances remain"
                    });
            }
            foreach (Building_WorkTable table in map.listerBuildings.allBuildingsColonist.OfType<Building_WorkTable>())
            {
                IntVec3[] cells = StorageCells(table);
                if (cells.Length < 3 || hostiles.Any(p => p.GetRoom() == table.GetRoom())) continue;
                foreach (ThingDef def in unstoredDefs.Where(d => needingStorage[d].Any(t => CellCapacity(map, cells, t))))
                    options.Add(new Choice
                    {
                        key = $"zone:{table.thingIDNumber}:{def.defName}:{string.Join(";", cells.Select(c => c.x + "," + c.z))}",
                        kind = "zone", target_id = table.thingIDNumber, value = def.defName, cells = cells,
                        label = "Roofed material stockpile near " + table.LabelShortCap + ": " + def.LabelCap,
                        cost = cells.Length + " existing indoor floor cells and hauling labor", risk = "Occupies floor with stored materials; stockpile permission/priority is not completed delivery"
                    });
            }
            var giver = DefDatabase<WorkGiverDef>.GetNamedSilentFail("HaulGeneral");
            var scanner = giver?.Worker as WorkGiver_HaulGeneral;
            if (scanner == null) return options;
            Pawn[] haulers = map.mapPawns.FreeColonistsSpawned.Where(p => Worker(p, giver.workType) && !scanner.ShouldSkip(p, false)).ToArray();
            // Bound output to one feasible stack per def/worker. Do not choose
            // a representative until all native eligibility checks pass.
            foreach (var group in materials.Where(t => !t.IsForbidden(Faction.OfPlayer))
                .GroupBy(t => t.def))
            {
                Thing[] candidates = group.Where(t => !hostiles.Any(p => p.Position.DistanceTo(t.Position) < 30))
                    .OrderBy(t => t.Position.Roofed(map))
                    .ThenBy(t => t.HitPoints / (float)Math.Max(1, t.MaxHitPoints)).ToArray();
                bool haulAvailable = false;
                foreach (Pawn pawn in haulers)
                {
                    Thing thing = candidates.FirstOrDefault(t => {
                        if (activeHauls.Contains(t.thingIDNumber)
                            || !pawn.CanReserveAndReach(t, PathEndMode.ClosestTouch, Danger.Some)
                            || !HaulAIUtility.PawnCanAutomaticallyHaulFast(pawn, t, false)) return false;
                        if (!StoreUtility.TryFindBestBetterStorageFor(t, pawn, map,
                            StoreUtility.CurrentStoragePriorityOf(t, false), pawn.Faction,
                            out IntVec3 foundCell, out IHaulDestination destination)) return false;
                        return destination is ISlotGroupParent || (destination is Thing container
                            && container.TryGetInnerInteractableThingOwner() != null);
                    });
                    if (thing == null) continue;
                    haulAvailable = true;
                    options.Add(new Choice
                    {
                        key = $"haul:{thing.thingIDNumber}:{pawn.thingIDNumber}", kind = "haul", target_id = thing.thingIDNumber,
                        worker_id = pawn.thingIDNumber, label = pawn.LabelShortCap + ": haul " + thing.LabelCap,
                        cost = "Hauling labor; destination chosen by loaded vanilla storage rules", risk = "Current non-care task may be interrupted; path/priority can change before pickup"
                    });
                }
                if (!haulAvailable && needingStorage.TryGetValue(group.Key, out Thing[] waiting)
                    && waiting.Any(hasCapacity))
                    blocked?.Add(new { def_name = group.Key.defName, reason = haulers.Length == 0
                        ? "storage_capacity_exists_no_eligible_hauler" : "storage_capacity_exists_route_reservation_or_priority_blocked" });
            }
            return options;
        }

        public static ApiResult<object> Context(int id)
        {
            Map map = MapHelper.GetMapByID(id);
            if (map == null) return ApiResult<object>.Fail("Map missing");
            var blocked = new List<object>();
            var activeOrders = ResilienceAutomationHelper.ActiveOrders(map);
            var options = Options(map, blocked, activeOrders);
            return ApiResult<object>.Ok(new { available = true, options, blocked, active_orders = activeOrders });
        }

        public static ApiResult<object> Policy(ProductionRecipePolicyDto request)
        {
            Map map = MapHelper.GetMapByID(request.MapId);
            if (map == null) return ApiResult<object>.Fail("Map missing");
            Choice choice = Options(map).FirstOrDefault(c => c.key == request.Key);
            if (choice == null) return ApiResult<object>.Ok(new { applied = false, reason = "logistics_option_changed" });
            Thing target = map.listerThings.AllThings.FirstOrDefault(t => t.thingIDNumber == choice.target_id);
            switch (choice.kind)
            {
                case "allow": target.SetForbidden(false); break;
                case "shelf":
                    var shelf = (Building_Storage)target;
                    shelf.GetStoreSettings().filter.SetAllow(DefDatabase<ThingDef>.GetNamed(choice.value), true);
                    shelf.Notify_SettingsChanged(); break;
                case "stockpile":
                    var zone = map.zoneManager.AllZones.OfType<Zone_Stockpile>().First(z => z.ID == choice.target_id);
                    zone.settings.filter.SetAllow(DefDatabase<ThingDef>.GetNamed(choice.value), true);
                    zone.Notify_SettingsChanged(); break;
                case "zone":
                    var created = new Zone_Stockpile(StorageSettingsPreset.DefaultStockpile, map.zoneManager);
                    foreach (ThingDef def in created.settings.filter.AllowedThingDefs.ToArray()) created.settings.filter.SetAllow(def, false);
                    created.settings.filter.SetAllow(DefDatabase<ThingDef>.GetNamed(choice.value), true);
                    created.settings.Priority = StoragePriority.Important;
                    map.zoneManager.RegisterZone(created);
                    foreach (IntVec3 cell in choice.cells) created.AddCell(cell);
                    break;
                case "haul":
                    Pawn pawn = map.mapPawns.FreeColonistsSpawned.First(p => p.thingIDNumber == choice.worker_id);
                    var scanner = (WorkGiver_HaulGeneral)DefDatabase<WorkGiverDef>.GetNamed("HaulGeneral").Worker;
                    Job job = scanner.JobOnThing(pawn, target, false);
                    if (job == null) return ApiResult<object>.Ok(new { applied = false, reason = "haul_job_unavailable" });
                    pawn.jobs.TryTakeOrderedJob(job);
                    if (pawn.CurJob != job) return ApiResult<object>.Ok(new { applied = false, reason = "haul_job_not_started" });
                    break;
                default: return ApiResult<object>.Ok(new { applied = false, reason = "unsupported_logistics" });
            }
            return ApiResult<object>.Ok(new { applied = true, reason = "ordinary_logistics_policy_or_job_accepted_not_delivered" });
        }
    }
}

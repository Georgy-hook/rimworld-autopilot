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

        public static List<Choice> Options(Map map)
        {
            var options = new List<Choice>();
            Thing[] materials = map.listerThings.AllThings.Where(Material).ToArray();
            ThingDef[] defs = materials.Select(t => t.def).Distinct().ToArray();
            Pawn[] hostiles = map.mapPawns.AllPawnsSpawned.Where(p => !p.Dead && !p.Downed && p.HostileTo(Faction.OfPlayer)).ToArray();
            foreach (Thing thing in materials.Where(t => t.IsForbidden(Faction.OfPlayer)).GroupBy(t => t.def)
                .Select(g => g.OrderBy(t => t.Position.Roofed(map)).ThenBy(t => t.HitPoints / (float)Math.Max(1, t.MaxHitPoints)).First()))
            {
                if (hostiles.Any(p => p.Position.DistanceTo(thing.Position) < 30)) continue;
                options.Add(new Choice
                {
                    key = "allow:" + thing.thingIDNumber, kind = "allow", target_id = thing.thingIDNumber,
                    label = "Allow " + thing.LabelCap, cost = "May trigger ordinary hauling/production consumption",
                    risk = "Previously forbidden stock becomes usable; no hostile within 30 cells, but route safety remains uncertain"
                });
            }
            Building_Storage[] storages = map.listerBuildings.allBuildingsColonist.OfType<Building_Storage>().ToArray();
            Zone_Stockpile[] zones = map.zoneManager.AllZones.OfType<Zone_Stockpile>().ToArray();
            ThingDef[] unstoredDefs = defs.Where(d => !storages.Any(b => b.GetStoreSettings().AllowedToAccept(d))
                && !zones.Any(z => z.settings.AllowedToAccept(d))).ToArray();
            foreach (Building_Storage storage in storages.GroupBy(b => b.GetStoreSettings()).Select(g => g.First()))
            {
                foreach (ThingDef def in unstoredDefs.Where(d => !storage.GetStoreSettings().AllowedToAccept(d) && (storage.GetParentStoreSettings()?.AllowedToAccept(d) ?? true)))
                    options.Add(new Choice
                    {
                        key = $"shelf:{storage.thingIDNumber}:{def.defName}", kind = "shelf", target_id = storage.thingIDNumber,
                        value = def.defName, label = storage.LabelShortCap + ": allow " + def.LabelCap,
                        cost = "Storage capacity and hauling labor", risk = "Linked shelves sharing settings affected=" + storages.Count(b => b.GetStoreSettings() == storage.GetStoreSettings()) + "; other allowances compete for capacity"
                    });
            }
            foreach (Zone_Stockpile zone in map.zoneManager.AllZones.OfType<Zone_Stockpile>())
            {
                foreach (ThingDef def in unstoredDefs.Where(d => !zone.settings.AllowedToAccept(d)))
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
                foreach (ThingDef def in unstoredDefs)
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
            // One exposed/damaged representative per def keeps job generation proportional to material types, not all stacks.
            foreach (Thing thing in materials.Where(t => !t.IsForbidden(Faction.OfPlayer))
                .GroupBy(t => t.def).Select(g => g.OrderBy(t => t.Position.Roofed(map)).ThenBy(t => t.HitPoints / (float)Math.Max(1, t.MaxHitPoints)).First()))
            {
                if (hostiles.Any(p => p.Position.DistanceTo(thing.Position) < 30)) continue;
                foreach (Pawn pawn in haulers)
                {
                    if (!pawn.CanReserveAndReach(thing, PathEndMode.ClosestTouch, Danger.Some)) continue;
                    if (!HaulAIUtility.PawnCanAutomaticallyHaulFast(pawn, thing, false)) continue;
                    if (!StoreUtility.TryFindBestBetterStorageFor(thing, pawn, map,
                        StoreUtility.CurrentStoragePriorityOf(thing, false), pawn.Faction,
                        out IntVec3 foundCell, out IHaulDestination destination)) continue;
                    if (!(destination is ISlotGroupParent) && !(destination is Thing container
                        && container.TryGetInnerInteractableThingOwner() != null)) continue;
                    options.Add(new Choice
                    {
                        key = $"haul:{thing.thingIDNumber}:{pawn.thingIDNumber}", kind = "haul", target_id = thing.thingIDNumber,
                        worker_id = pawn.thingIDNumber, label = pawn.LabelShortCap + ": haul " + thing.LabelCap,
                        cost = "Hauling labor; destination chosen by loaded vanilla storage rules", risk = "Current non-care task may be interrupted; path/priority can change before pickup"
                    });
                }
            }
            return options;
        }

        public static ApiResult<object> Context(int id)
        {
            Map map = MapHelper.GetMapByID(id);
            if (map == null) return ApiResult<object>.Fail("Map missing");
            return ApiResult<object>.Ok(new { available = true, options = Options(map) });
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

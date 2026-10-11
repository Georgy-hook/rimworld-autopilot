using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;

namespace RIMAPI.Helpers
{
    // Normal storage settings, including blueprint -> frame -> building copies.
    // Profiles never move, manufacture, chill or preserve an item themselves.
    public static class StorageProfileHelper
    {
        public static readonly string[] Roles = { "kitchen_inputs", "meals", "cold_food", "medicine", "workshop_inputs",
            "textiles", "construction", "fuel", "armory", "dry_goods", "fresh_carcasses" };

        public static HashSet<ThingDef> Definitions(string role, Map map = null)
        {
            var all = DefDatabase<ThingDef>.AllDefs.Where(d => d.category == ThingCategory.Item).ToArray();
            Func<ThingDef, string, bool> category = (d, name) => d.thingCategories?.Any(c =>
                c.defName == name || c.Parents.Any(p => p.defName == name)) == true;
            Func<ThingDef, bool> rawFood = d => d.ingestible != null && !d.IsCorpse
                && d.ingestible.foodType != FoodTypeFlags.None && d.IsNutritionGivingIngestible
                && category(d, "FoodRaw") && !category(d, "EggsFertilized");
            IEnumerable<ThingDef> selected;
            switch (role)
            {
                case "kitchen_inputs": selected = all.Where(rawFood); break;
                case "meals": selected = all.Where(d => category(d, "FoodMeals") || d.defName == "MealSurvivalPack"); break;
                case "cold_food": selected = all.Where(d => rawFood(d) || category(d, "FoodMeals") || d.defName == "MealSurvivalPack"); break;
                case "medicine": selected = all.Where(d => d.IsMedicine); break;
                case "textiles": selected = all.Where(d => category(d, "Textiles")); break;
                case "construction": selected = all.Where(d => d.defName == "Steel" || d.defName == "WoodLog" || category(d, "StoneBlocks")); break;
                case "fuel": selected = all.Where(d => d.defName == "WoodLog" || d.defName == "Chemfuel"); break;
                case "armory": selected = all.Where(d => d.IsWeapon || d.IsApparel); break;
                case "fresh_carcasses": selected = all.Where(d => d.IsCorpse && d.ingestible != null
                    && d.ingestible.sourceDef?.race?.Animal == true); break;
                case "workshop_inputs":
                    selected = all.Where(d => d.ingestible == null && !d.IsCorpse &&
                        (category(d, "ResourcesRaw") || category(d, "Manufactured") || category(d, "Textiles"))
                        && !d.IsMedicine && !category(d, "Drugs") && !category(d, "MortarShells")
                        && d.defName != "Chemfuel" && d.defName != "WoodLog"); break;
                case "dry_goods": selected = all.Where(d => d.ingestible == null && !d.IsCorpse
                    && d.defName != "Chemfuel" && !category(d, "StoneChunks") && !d.defName.StartsWith("Chunk")); break;
                default: return new HashSet<ThingDef>();
            }
            return new HashSet<ThingDef>(selected);
        }

        public static StoragePriority Priority(string role) => role == "dry_goods" || role == "construction"
            ? StoragePriority.Normal : StoragePriority.Preferred;

        public static bool Specialized(StorageSettings settings)
        {
            // Adding arbitrary unstored material must not destroy an intentionally
            // narrow filter, including one made by a human or a linked shelf group.
            int total = DefDatabase<ThingDef>.AllDefs.Count(d => d.category == ThingCategory.Item && d.EverStorable(false));
            return settings.filter.AllowedThingDefs.Count(d => d.category == ThingCategory.Item) < total * .8;
        }

        public static void Apply(IStoreSettingsParent owner, string role)
        {
            var allowed = Definitions(role);
            if (allowed.Count == 0) throw new ArgumentException("Unknown or empty storage profile: " + role);
            StorageSettings settings = owner.GetStoreSettings();
            var parent = owner.GetParentStoreSettings();
            settings.filter.SetDisallowAll();
            foreach (ThingDef def in allowed.Where(d => parent?.AllowedToAccept(d) ?? true)) settings.filter.SetAllow(def, true);
            MapHelper.SetFreshness(settings.filter, true, false);
            settings.Priority = Priority(role);
            owner.Notify_SettingsChanged();
        }

        private static bool Near(Room room, Map map, Func<Building, bool> predicate, int distance, IntVec3 cell)
            => map.listerBuildings.allBuildingsColonist.Any(b => predicate(b) && b.Position.DistanceTo(cell) <= distance);

        public static bool Suitable(string role, Map map, IntVec3 cell, IEnumerable<IntVec3> cells)
        {
            Room room = cell.GetRoom(map);
            if (room == null || room.PsychologicallyOutdoors || cells.Any(c => !c.Roofed(map))) return false;
            bool kitchen = room.ContainedThings<Building_WorkTable>().Any(b => b.def.defName.Contains("Stove"));
            bool beds = room.ContainedBeds.Any();
            bool prison = room.IsPrisonCell;
            if (role == "fresh_carcasses") return !beds && !kitchen && !prison
                && Near(room, map, b => b.def.defName.Contains("Butcher"), 14, cell);
            if (role == "medicine") return !prison && Near(room, map, b => b is Building_Bed, 14, cell);
            if (role == "kitchen_inputs" || role == "meals" || role == "cold_food") return !prison
                && Near(room, map, b => b.def.defName.Contains("Stove") || b.def.defName == "Campfire", 16, cell);
            if (beds || kitchen || prison) return false;
            if (role == "workshop_inputs" || role == "textiles") return Near(room, map,
                b => b is Building_WorkTable && !b.def.defName.Contains("Butcher") && !b.def.defName.Contains("Stove"), 14, cell);
            if (role == "fuel") return Near(room, map, b => b.TryGetComp<CompRefuelable>() != null, 12, cell)
                && cells.All(c => !c.GetThingList(map).Any(t => t is Building b && b.TryGetComp<CompRefuelable>() != null));
            return true;
        }

        public static List<ProductionLogisticsHelper.Choice> Options(Map map)
        {
            var options = new List<ProductionLogisticsHelper.Choice>();
            foreach (Building_Cooler cooler in map.listerBuildings.allBuildingsColonist.OfType<Building_Cooler>())
            {
                var control = cooler.TryGetComp<CompTempControl>();
                var power = cooler.TryGetComp<CompPowerTrader>();
                IntVec3 cold = cooler.Position + IntVec3.South.RotatedBy(cooler.Rotation);
                IntVec3 hot = cooler.Position + IntVec3.North.RotatedBy(cooler.Rotation);
                if (!cold.InBounds(map) || !hot.InBounds(map) || cold.Impassable(map) || hot.Impassable(map)
                    || power?.PowerOn != true || control == null || Math.Abs(control.TargetTemperature + 10f) < .1f) continue;
                Room room = cold.GetRoom(map), exhaust = hot.GetRoom(map);
                if (room == null || room.PsychologicallyOutdoors || room.ContainedBeds.Any()
                    || map.mapPawns.AllPawnsSpawned.Any(p => p.Downed && p.GetRoom() == room)) continue;
                bool foodStore = room.ContainedThings<Building_Storage>().Any(b =>
                    b.GetStoreSettings().filter.AllowedThingDefs.Any(d => d.IsNutritionGivingIngestible)
                    && b.GetStoreSettings().filter.AllowedThingDefs.All(d => d.ingestible != null));
                if (!foodStore || exhaust == room) continue;
                if (exhaust != null && !exhaust.PsychologicallyOutdoors && (exhaust.ContainedBeds.Any()
                    || exhaust.ContainedThings<Building_Storage>().Any()
                    || map.mapPawns.AllPawnsSpawned.Any(p => p.GetRoom() == exhaust))) continue;
                options.Add(new ProductionLogisticsHelper.Choice { key = $"cooling:{cooler.thingIDNumber}:{control.TargetTemperature:F1}:{room.ID}:{exhaust?.ID}",
                    kind = "cooling", target_id = cooler.thingIDNumber, value = "-10",
                    label = "Food-only cold room: target -10 C; current=" + room.Temperature.ToString("F1"),
                    cost = "Connected electricity while cooling; exhaust heat and open-door losses",
                    risk = "Cold side South, exhaust North after rotation; no bed/patient in cold room or occupant/stock in enclosed exhaust. Actual cooling/heatstroke unproved" });
            }
            foreach (var group in map.listerBuildings.allBuildingsColonist.OfType<Building_Storage>().GroupBy(b => b.GetStoreSettings()))
            {
                var shelves = group.ToArray(); var shelf = shelves[0]; var settings = group.Key;
                // Retain a chosen profile. This is not a periodic rearrangement of
                // the entire warehouse, and no automatic policy changes occur in GET.
                if (Specialized(settings)) continue;
                foreach (string role in Roles)
                {
                    var allowed = Definitions(role);
                    if (allowed.Count == 0 || shelves.Any(b => !Suitable(role, map, b.Position, b.GetSlotGroup().CellsList))) continue;
                    var displaced = shelves.SelectMany(b => b.GetSlotGroup().CellsList.SelectMany(c => c.GetThingList(map)))
                        .Where(t => t.def.category == ThingCategory.Item && !allowed.Contains(t.def)).Distinct().ToArray();
                    // Avoid evicting the only safe destination for current goods.
                    if (displaced.Any(t => !map.haulDestinationManager.AllHaulDestinationsListInPriorityOrder.Any(d =>
                        d.HaulDestinationEnabled && d is ISlotGroupParent slots && d.Accepts(t)
                        && !(d is Building_Storage other && shelves.Any(b => b == other))
                        && slots.GetSlotGroup().CellsList.Any(c => c.Roofed(map)
                            && StoreUtility.IsGoodStoreCell(c, map, t, null, null))))) continue;
                    string signature = string.Join(",", settings.filter.AllowedThingDefs.Select(d => d.defName).OrderBy(s => s));
                    string stamp = StableStamp(signature + ":" + settings.Priority);
                    options.Add(new ProductionLogisticsHelper.Choice { key = $"profile:{shelf.thingIDNumber}:{role}:{stamp}",
                        kind = "profile", target_id = shelf.thingIDNumber, value = role,
                        label = "Dedicated " + role + "; linked shelves=" + shelves.Length,
                        cost = "Ordinary hauling; displaced stacks=" + displaced.Length + "; priority=" + Priority(role),
                        risk = "Replace mixed filter; only this purpose allowed. Reserve size is shelf capacity; no delivery or preservation proved",
                        storage_role = role, allowed_defs = allowed.Select(d => d.defName).OrderBy(s => s).ToArray(),
                        priority = (int)Priority(role), displaced_stacks = displaced.Length });
                }
            }
            return options;
        }

        private static string StableStamp(string value)
        { unchecked { uint hash = 2166136261; foreach (char c in value) hash = (hash ^ c) * 16777619; return hash.ToString("x8"); } }

        public static bool DryFoundation(Map map, IntVec3 cell)
            => cell.InBounds(map) && !cell.Fogged(map) && cell.GetTerrain(map).affordances.Contains(TerrainAffordanceDefOf.Heavy)
                && !cell.GetTerrain(map).IsWater && !cell.GetTerrain(map).defName.Contains("Marsh")
                && !cell.GetTerrain(map).defName.Contains("Mud");

        public static string SiteBlocker(Map map, Models.PasteAreaRequestDto request)
        {
            var plan = request.Blueprint;
            if (!plan.RequireDryGround && !plan.AvoidMountainRoof && !plan.HeatLure) return null;
            if (plan.Width <= 0 || plan.Height <= 0) return "Invalid guarded layout dimensions";
            if (plan.HeatLure)
            {
                if (plan.Width != 9 || plan.Height != 12) return "Unknown heat chamber layout";
                if (!map.powerNetManager.AllNetsListForReading.Any(n => n.HasActivePowerSource
                    && n.CurrentEnergyGainRate() >= 400f * CompPower.WattsToWattDaysPerTick))
                    return "Heat chamber requires an active surplus power network";
                if (!map.mapPawns.FreeColonistsSpawned.Any(p => !p.Dead && !p.Downed && !p.InMentalState
                    && !p.WorkTypeIsDisabled(WorkTypeDefOf.Construction) && p.skills.GetSkill(SkillDefOf.Construction).Level >= 5))
                    return "No capable cooler builder for heat chamber";
                foreach (var b in plan.Buildings)
                {
                    if (b.RelZ >= 8 && b.DefName != "Wall") return "Hot chamber must have no door, stock or ordinary work facility";
                    if (b.DefName == "Wall" && DefDatabase<ThingDef>.GetNamed(b.DefName).GetStatValueAbstract(StatDefOf.Flammability,
                        DefDatabase<ThingDef>.GetNamedSilentFail(b.StuffDefName)) > 0) return "Heat chamber walls must be nonflammable";
                    if (b.DefName == "Cooler" && (b.RelZ != 7 || b.Rotation != 0 || !(b.RelX == 3 || b.RelX == 5)))
                        return "Incorrect cold/exhaust orientation";
                }
            }
            foreach (IntVec3 c in CellRect.FromLimits(new IntVec3(request.Position.X, 0, request.Position.Z),
                new IntVec3(request.Position.X + plan.Width - 1, 0, request.Position.Z + plan.Height - 1)))
            {
                if (!c.InBounds(map) || c.Fogged(map)) return "Unknown or out-of-bounds storage footprint";
                if (plan.RequireDryGround && !DryFoundation(map, c)) return "Wet or unsupported storage foundation";
                if (plan.AvoidMountainRoof && c.GetRoof(map)?.isThickRoof == true) return "Storage under overhead mountain risks infestation";
                if (c.GetZone(map) != null) return "Storage footprint overlaps existing zone";
                if (plan.HeatLure)
                {
                    int x = c.x-request.Position.X, z = c.z-request.Position.Z;
                    bool hot = x >= 1 && x <= 7 && z >= 8 && z <= 10;
                    if (hot && c.GetRoof(map)?.isThickRoof != true) return "Heat chamber requires revealed overhead mountain";
                    if (z <= 6 && c.GetRoof(map)?.isThickRoof == true) return "Valuable cold store must be outside mountain roof";
                    if (hot && map.mapPawns.AllPawnsSpawned.Any(p => p.Position == c)) return "Occupied hot chamber footprint";
                }
            }
            return null;
        }
    }
}

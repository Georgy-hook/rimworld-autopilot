using System;
using System.Collections.Generic;
using System.Linq;
using RIMAPI.Models;
using RimWorld;
using UnityEngine;
using Verse;

namespace RIMAPI.Helpers
{
    public static class FarmHelper
    {
        public static MapFarmSummaryDto GenerateFarmSummary(Map map)
        {
            var zones = map.zoneManager.AllZones.OfType<Zone_Growing>().ToList();
            var basins = map.listerBuildings.allBuildingsColonist.OfType<Building_PlantGrower>().ToList();
            var summary = new MapFarmSummaryDto { TotalGrowingZones = zones.Count, TotalPlantGrowers = basins.Count };
            var growers = zones.Select(z => Tuple.Create(z.GetPlantDefToGrow(), z.ID, z.Cells, "zone:" + z.ID))
                .Concat(basins.Select(b => Tuple.Create(b.GetPlantDefToGrow(), -1, b.OccupiedRect().Cells.ToList(), "building:" + b.thingIDNumber)));
            var crops = new Dictionary<string, CropTypeDto>();
            foreach (var grower in growers)
            {
                // Read grower cells directly; do not scan all map plants per field.
                var plants = grower.Item3.Select(c => c.GetPlant(map)).Where(p => p != null).ToList();
                var definitions = plants.Select(p => p.def).Concat(new[] { grower.Item1 }).Where(d => d != null).Distinct();
                foreach (var definition in definitions)
                {
                    if (!crops.TryGetValue(definition.defName, out var crop))
                    {
                        crop = new CropTypeDto { PlantDefName = definition.defName, PlantLabel = definition.label,
                            PlantCategory = GetPlantCategory(definition), ZoneId = grower.Item2 };
                        crops[definition.defName] = crop;
                    }
                    crop.GrowerIds.Add(grower.Item4);
                    foreach (Plant plant in plants.Where(p => p.def == definition))
                    {
                        crop.TotalPlants++;
                        crop.GrowthProgressAverage += plant.Growth * 100f;
                        if (plant.HarvestableNow)
                        { crop.HarvestablePlants++; crop.ExpectedYield += plant.YieldNow(); crop.IsHarvestable = true; }
                        if (plant.Blighted) { crop.InfectedCount++; summary.TotalInfectedPlants++; }
                        if (plant.Growth >= 1f) crop.IsFullyGrown = true;
                        float days = CalculateDaysUntilHarvest(plant);
                        if (days < 0) crop.GrowthBlockedPlants++;
                        else crop.DaysUntilHarvest += days;
                    }
                }
            }
            foreach (var crop in crops.Values)
            {
                if (crop.TotalPlants > 0) crop.GrowthProgressAverage /= crop.TotalPlants;
                int estimating = crop.TotalPlants - crop.GrowthBlockedPlants;
                crop.DaysUntilHarvest = estimating > 0 ? crop.DaysUntilHarvest / estimating : -1;
                summary.TotalPlants += crop.TotalPlants;
                summary.TotalExpectedYield += crop.ExpectedYield;
                summary.GrowthProgressAverage += crop.GrowthProgressAverage * crop.TotalPlants;
            }
            if (summary.TotalPlants > 0) summary.GrowthProgressAverage /= summary.TotalPlants;
            summary.CropTypes = crops.Values.OrderByDescending(c => c.TotalPlants).ToList();
            return summary;
        }

        public static GrowingZoneDto GetGrowingZoneById(Map map, int zoneId)
        {
            var zone = map
                .zoneManager.AllZones.OfType<Zone_Growing>()
                .FirstOrDefault(z => z.ID == zoneId);

            if (zone == null)
                return null;

            var zonePlants = zone.Cells.Select(c => c.GetPlant(map)).Where(p => p != null).ToList();

            var zoneDto = new GrowingZoneDto
            {
                Zone = new ZoneDto
                {
                    Id = zone.ID,
                    CellsCount = zone.CellCount,
                    Label = zone.label ?? "Unnamed Zone",
                    BaseLabel = zone.BaseLabel,
                },
                PlantDefName = zone.GetPlantDefToGrow()?.defName ?? "None",
                PlantCount = zonePlants.Count,
                ExpectedYield = 0,
                InfectedCount = 0,
                GrowthProgress = 0,
                HasDying = false,
                HasDyingFromPollution = false,
                HasDyingFromNoPollution = false,
#if RIMWORLD_1_5
                IsSowing =
                    zone.allowSow
                    && PlantUtility.GrowthSeasonNow(
                        zone.Cells.FirstOrDefault(),
                        map,
                        forSowing: true
                    )
                    && zone.Cells.Any(c => c.GetPlant(map) == null),
#elif RIMWORLD_1_6
                IsSowing = zone.allowSow && zone.Cells.Any(c => PlantUtility.GrowthSeasonNow(c, map, zone.GetPlantDefToGrow())),
#endif
                SoilType = GetSoilType(zone.Cells.FirstOrDefault(), map),
                Fertility = GetZoneFertility(zone, map),
            };

            if (zonePlants.Count > 0)
            {
                zoneDto.GrowthProgress = zonePlants.Average(p => p.Growth);
                zoneDto.DefExpectedYield = Mathf.RoundToInt(
                    zonePlants.Sum(p => p.def.plant.harvestYield)
                );
                zoneDto.ExpectedYield = Mathf.RoundToInt(
                    zonePlants.Where(p => p.HarvestableNow).Sum(p => p.YieldNow())
                );
                zoneDto.InfectedCount = zonePlants.Count(p => p.Blighted);
                zoneDto.HasDying = zonePlants.Any(p => p.Dying);
                zoneDto.HasDyingFromPollution = zonePlants.Any(p => p.DyingFromPollution);
                zoneDto.HasDyingFromNoPollution = zonePlants.Any(p => p.DyingFromNoPollution);
            }

            return zoneDto;
        }

        /// <summary>
        /// Resolve a plant ThingDef from either its defName ("Plant_Rice") or a
        /// looser alias (label "rice", or the bare crop name "Rice"). The agents
        /// that drive this API only reliably know the defName, but accepting the
        /// label as a fallback makes the endpoint forgiving and matches operator
        /// expectations.
        /// </summary>
        public static ThingDef ResolvePlantDef(string name)
        {
            if (string.IsNullOrWhiteSpace(name))
                return null;

            var def = DefDatabase<ThingDef>.GetNamedSilentFail(name);
            if (def != null && def.plant != null)
                return def;

            return DefDatabase<ThingDef>.AllDefsListForReading.FirstOrDefault(d =>
                d.plant != null &&
                (string.Equals(d.label, name, StringComparison.OrdinalIgnoreCase) ||
                 string.Equals(d.defName, "Plant_" + name, StringComparison.OrdinalIgnoreCase)));
        }

        /// <summary>
        /// Create a growing zone. On failure, <paramref name="error"/> carries a
        /// SPECIFIC reason — historically this returned a bare null that the
        /// caller blamed on the plant def, even when the real cause was that
        /// every requested cell already belonged to another zone (the common
        /// case when an agent re-issues a growing zone over an existing one).
        /// </summary>
        public static GrowingZoneDto CreateGrowingZone(
            Map map, string plantDefName, List<IntVec3> cells, out string error)
        {
            error = null;

            var plantDef = ResolvePlantDef(plantDefName);
            if (plantDef == null || plantDef.plant == null || !plantDef.plant.sowTags.Contains("Ground")
                || !Command_SetPlantToGrow.IsPlantAvailable(plantDef, map))
            {
                error = $"Invalid plant definition: {plantDefName}";
                return null;
            }

            var zone = new Zone_Growing(map.zoneManager);
            map.zoneManager.RegisterZone(zone);

            int requested = cells.Count;
            int skippedOutOfBounds = 0;
            int skippedOccupied = 0;
            foreach (var cell in cells)
            {
                if (!cell.InBounds(map))
                {
                    skippedOutOfBounds++;
                    continue;
                }
                if (map.zoneManager.ZoneAt(cell) != null)
                {
                    skippedOccupied++;
                    continue;
                }
                if (!plantDef.CanEverPlantAt(cell, map, true, false)) continue;
                zone.AddCell(cell);
            }

            // No valid cells added — remove the empty zone and report WHY.
            if (zone.CellCount == 0)
            {
                zone.Delete();
                error =
                    $"No free cells in the requested {requested}-cell rectangle " +
                    $"({skippedOccupied} already belong to another zone, " +
                    $"{skippedOutOfBounds} out of bounds). " +
                    $"The area likely overlaps an existing zone — a zone for " +
                    $"'{plantDef.defName}' may already exist here.";
                return null;
            }

            zone.SetPlantDefToGrow(plantDef);
            return GetGrowingZoneById(map, zone.ID);
        }

        // Helper methods
        public static string GetPlantCategory(ThingDef plantDef)
        {
            if (plantDef == null)
                return "Unknown";
            if (plantDef.plant == null)
                return "Unknown";

            if (plantDef.plant.IsTree)
                return "Tree";
            if (plantDef.plant.harvestedThingDef?.IsDrug ?? false)
                return "Drug";
            if (plantDef.plant.harvestedThingDef?.IsMedicine ?? false)
                return "Medicine";
            if (plantDef.plant.Sowable)
                return "Crop";

            return "Other";
        }

        public static float CalculateDaysUntilHarvest(Plant plant)
        {
            if (plant.Blighted) return -1f;
            if (plant.Growth >= 1f)
            {
                return 0f; // Mature for normal automatic harvesting.
            }

            return PlantAutomationHelper.CalendarDays(plant.def, plant.Growth,
                plant.Map.fertilityGrid.FertilityAt(plant.Position), plant.Position.GetTemperature(plant.Map));
        }

        public static bool IsPlantResting(Plant plant)
        {
            float dayPercent = GenLocalDate.DayPercent(plant);
            return dayPercent < 0.25f || dayPercent > 0.8f;
        }

        public static string GetSoilType(IntVec3 cell, Map map)
        {
            if (!cell.InBounds(map))
                return "Unknown";
            var terrain = map.terrainGrid.TerrainAt(cell);
            return terrain?.defName ?? "Unknown";
        }

        public static float GetZoneFertility(Zone_Growing zone, Map map)
        {
            if (zone.Cells.Count == 0)
                return 0f;

            var fertilitySum = 0f;
            var sampleCells = zone.Cells.Take(10); // Sample first 10 cells for performance

            foreach (var cell in sampleCells)
            {
                if (cell.InBounds(map))
                {
                    fertilitySum += map.fertilityGrid.FertilityAt(cell);
                }
            }

            return sampleCells.Any() ? fertilitySum / sampleCells.Count() : 0f;
        }
    }
}

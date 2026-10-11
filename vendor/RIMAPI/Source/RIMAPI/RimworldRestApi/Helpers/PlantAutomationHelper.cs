using System;
using System.Collections.Generic;
using System.Linq;
using RIMAPI.Core;
using RIMAPI.Models;
using RimWorld;
using UnityEngine;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class PlantAutomationHelper
    {
        public static bool ResearchUnlocked(ThingDef def) =>
            def.plant.sowResearchPrerequisites == null || def.plant.sowResearchPrerequisites.All(r => r.IsFinished);

        public static bool BiomeAllowed(ThingDef def, Map map) =>
            def.plant.sowResearchPrerequisites == null || !def.plant.mustBeWildToSow || map.wildPlantSpawner.AllWildPlants.Contains(def);

        public static float CalendarDays(ThingDef def, float growth, float fertility, float temperature)
        {
            float rate = PlantUtility.GrowthRateFactorFor_Fertility(def, fertility)
                * PlantUtility.GrowthRateFactorFor_Temperature(def, temperature);
            // growDays counts continuous growth. Standard plants rest outside
            // local day fraction .25.. .80, even fungi; calendar estimate only.
            float growingFraction = 0.55f;
            // Normal growing work waits for Mature, not merely the threshold
            // that permits a manually designated early harvest.
            return rate <= 0 ? -1 : Mathf.Max(0, 1f - growth)
                * def.plant.growDays / rate / growingFraction;
        }

        public static ApiResult<PlantCatalogContextDto> Catalog(int mapId, int? x, int? z)
        {
            try
            {
                Map map = MapHelper.GetMapByID(mapId);
                if (map == null) return ApiResult<PlantCatalogContextDto>.Fail("Map not found.");
                var result = new PlantCatalogContextDto { Biome = map.Biome.defName, DayOfYear = GenLocalDate.DayOfYear(map) + 1 };
                var defs = DefDatabase<ThingDef>.AllDefsListForReading.Where(d => d.plant != null).ToList();
                foreach (ThingDef def in defs)
                {
                    var p = def.plant;
                    result.Plants.Add(new PlantCapabilityDto {
                        DefName = def.defName, Label = def.label, Description = def.description,
                        Category = p.harvestedThingDef?.defName == "WoodLog" ? "wood" :
                            p.harvestedThingDef?.IsMedicine == true ? "medicine" :
                            p.harvestedThingDef?.IsDrug == true ? "drug" :
                            p.humanFoodPlant ? "food" : p.purpose.ToString().ToLowerInvariant(),
                        HarvestedThing = p.harvestedThingDef?.defName,
                        HarvestYield = p.harvestYield * (p.harvestYieldAffectedByDifficulty ? Find.Storyteller.difficulty.cropYieldFactor : 1),
                        ProductNutrition = p.harvestedThingDef?.IsNutritionGivingIngestible == true
                            ? p.harvestedThingDef.GetStatValueAbstract(StatDefOf.Nutrition) : 0,
                        HumanEdibleProduct = p.harvestedThingDef?.IsNutritionGivingIngestible == true
                            && map.mapPawns.FreeColonistsSpawned.Any(c => c.RaceProps.CanEverEat(p.harvestedThingDef)),
                        CompatibleProductAnimalIds = map.mapPawns.SpawnedPawnsInFaction(Faction.OfPlayer)
                            .Where(a => a.RaceProps.Animal && p.harvestedThingDef?.ingestible!=null && a.RaceProps.CanEverEat(p.harvestedThingDef))
                            .Select(a=>a.thingIDNumber).ToList(),
                        GrazingAnimalIds = map.mapPawns.SpawnedPawnsInFaction(Faction.OfPlayer)
                            .Where(a=>a.RaceProps.Animal && def.ingestible!=null && a.RaceProps.CanEverEat(def))
                            .Select(a=>a.thingIDNumber).ToList(),
                        LivePlantNutrition = def.ingestible==null ? 0f : def.GetStatValueAbstract(StatDefOf.Nutrition),
                        WorkToSow=p.sowWork, WorkToHarvest=p.harvestWork,
                        GrowDays = p.growDays, CalendarDaysAtNormalFertility = CalendarDays(def, 0, 1, 21),
                        FertilityMin = p.fertilityMin, FertilitySensitivity = p.fertilitySensitivity,
                        MinGrowthTemperature = p.minGrowthTemperature, MaxGrowthTemperature = p.maxGrowthTemperature,
                        GrowMinGlow = p.growMinGlow, DiesToLight = p.diesToLight, RequiresPermanentDarkness = p.mustBePermanentDarknessToSow, DiesIfLeafless = p.dieIfLeafless,
                        Blightable = p.Blightable, Pollution = p.pollution.ToString(), MinimumSkill = p.sowMinSkill,
                        Sowable = p.Sowable, SowTags = p.sowTags, BiomeAllowed = BiomeAllowed(def, map),
                        NativeInBiome = map.Biome.AllWildPlants.Contains(def), ResearchUnlocked = ResearchUnlocked(def),
                        ResearchPrerequisites = p.sowResearchPrerequisites?.Select(r => r.defName).ToList() ?? new List<string>()
                    });
                }
                foreach (Zone_Growing zone in map.zoneManager.AllZones.OfType<Zone_Growing>())
                    result.Growers.Add(Site(map, "zone:" + zone.ID, "ground", zone.Cells, zone, defs, zone.ID, null, zone.GetPlantDefToGrow(), zone.allowSow));
                foreach (Building_PlantGrower grower in map.listerBuildings.allBuildingsColonist.OfType<Building_PlantGrower>())
                    result.Growers.Add(Site(map, "building:" + grower.thingIDNumber, "hydroponics", grower.OccupiedRect().Cells.ToList(), grower, defs, null, grower.thingIDNumber, grower.GetPlantDefToGrow(), true));
                IntVec3 center = x.HasValue && z.HasValue ? new IntVec3(x.Value, 0, z.Value)
                    : map.mapPawns.FreeColonistsSpawned.FirstOrDefault()?.Position ?? map.Center;
                // Bounded search, once per context refresh; avoid scanning the map per crop.
                foreach (bool indoors in new[] { true, false })
                {
                    int evaluatedPlots = 0;
                    var centers = indoors ? GrowLights(map).Select(b => b.Position).Concat(new[] { center }) : new[] { center };
                    foreach (IntVec3 origin in centers.SelectMany(p => GenRadial.RadialCellsAround(p, 30, true).Where((c, i) => i % 8 == 0)).Distinct())
                    {
                        int span = indoors ? 2 : 6;
                        var cells = CellRect.FromLimits(origin, origin + new IntVec3(span, 0, span)).Cells.ToList();
                        if (!cells.All(c => c.InBounds(map) && !c.Fogged(map) && c.GetZone(map) == null
                            && c.GetEdifice(map) == null && c.Roofed(map) == indoors && map.fertilityGrid.FertilityAt(c) >= 0.5f
                            && !c.GetThingList(map).Any(t => t is Blueprint || t is Frame))) continue;
                        if (evaluatedPlots++ >= 8) break;
                        var newSite = Site(map, indoors ? "new_indoor_ground" : "new_ground", "new_ground", cells, null, defs, null, null, null, true);
                        newSite.PointA = Pos(origin); newSite.PointB = Pos(origin + new IntVec3(span, 0, span));
                        if (!newSite.Options.Any(o => o.SafeSowingNow)) continue;
                        result.Growers.Add(newSite);
                        break;
                    }
                }
                return ApiResult<PlantCatalogContextDto>.Ok(result);
            }
            catch (Exception ex) { return ApiResult<PlantCatalogContextDto>.Fail(ex.ToString()); }
        }

        private static PositionDto Pos(IntVec3 c) => new PositionDto { X = c.x, Y = 0, Z = c.z };

        private static List<Building> GrowLights(Map map) => map.listerBuildings.allBuildingsColonist.Where(b =>
            b.def.comps?.OfType<CompProperties_Glower>().Any(g => g.overlightRadius > 0) == true
            && b.TryGetComp<CompPowerTrader>()?.PowerOn == true).ToList();

        private static bool LightSuitable(ThingDef def, IntVec3 c, Map map, List<Building> lights)
        {
            // Nighttime is normal plant rest, so inspect daylight capability too.
            bool sunLamp = lights.Any(b => c.DistanceTo(b.Position)
                < (b.def.comps.OfType<CompProperties_Glower>().FirstOrDefault(g => g.overlightRadius > 0)?.overlightRadius ?? 0) - 0.5f);
            if (def.plant.diesToLight || def.plant.mustBePermanentDarknessToSow)
                return c.Roofed(map) && !sunLamp && map.glowGrid.GroundGlowAt(c) <= 0;
            return def.plant.growMinGlow <= 0 || !c.Roofed(map) || sunLamp
                || map.glowGrid.GroundGlowAt(c) > def.plant.growMinGlow;
        }

        private static GrowerCapabilityDto Site(Map map, string id, string kind, List<IntVec3> cells,
            IPlantToGrowSettable grower, List<ThingDef> defs, int? zoneId, int? buildingId, ThingDef current, bool allowSow)
        {
            var dto = new GrowerCapabilityDto { Id = id, Kind = kind, ZoneId = zoneId, BuildingId = buildingId,
                PlantDef = current?.defName, AllowSow = allowSow, Roofed = cells.All(c => c.Roofed(map)),
                Powered = !(grower is Thing thing) || thing.TryGetComp<CompPowerTrader>()?.PowerOn != false,
                CellCount = cells.Count, PenIds = AnimalHusbandryHelper.PenIds(map,cells).ToList(),
                PlantCount = cells.Count(c => c.GetPlant(map) != null), BlightedCount = cells.Count(c => c.GetPlant(map)?.Blighted == true) };
            var growLights = GrowLights(map);
            foreach (ThingDef def in defs.Where(d => d.plant.Sowable && Command_SetPlantToGrow.IsPlantAvailable(d, map)))
            {
                if (kind == "new_ground" ? !def.plant.sowTags.Contains("Ground") : !PlantUtility.CanSowOnGrower(def, grower)) continue;
                var legal = cells.Where(c => def.CanEverPlantAt(c, map, true, false)).ToList();
                if (!legal.Any()) continue;
                float fertility = legal.Average(c => map.fertilityGrid.FertilityAt(c));
                float temperature = legal.Average(c => c.GetTemperature(map));
                float days = CalendarDays(def, 0, fertility, temperature);
                int temperate = legal.Count(c => PlantUtility.GrowthSeasonNow(c, map, def));
                int lightSuitable = legal.Count(c => LightSuitable(def, c, map, growLights));
                float? warmDays = dto.Roofed ? (float?)null : WarmDays(map, def);
                bool safe = dto.BlightedCount == 0 && dto.Powered && temperate >= legal.Count * 0.8f && lightSuitable >= legal.Count * 0.8f
                    && days >= 0 && (!def.plant.dieIfLeafless || !warmDays.HasValue || days + 1 < warmDays.Value);
                dto.Options.Add(new PlantSiteCapabilityDto { DefName = def.defName, LegalCells = legal.Count,
                    TemperateCells = temperate, LightSuitableCells = lightSuitable, Fertility = fertility, Temperature = temperature,
                    CalendarDaysToHarvestEstimate = days, OutdoorWarmDaysEstimate = warmDays, SafeSowingNow = safe,
                    Reason = dto.BlightedCount > 0 ? "clear_blight_before_sowing" : !dto.Powered ? "grower_without_power" : lightSuitable < legal.Count * 0.8f ? "insufficient_grow_light_or_darkness_required"
                        : temperate < legal.Count * 0.8f ? "outside_growth_temperature"
                        : !safe ? "estimated_season_too_short" : "estimated_viable; cold snaps, heat, light and pollution can still stop growth" });
            }
            return dto;
        }

        private static float WarmDays(Map map, ThingDef def)
        {
            float longitude = Find.WorldGrid.LongLatOf(map.Tile).x;
            int day = GenDate.DayOfYear(GenTicks.TicksAbs, longitude);
            int twelfth = (int)GenDate.Twelfth(GenTicks.TicksAbs, longitude);
            float days = 0;
            for (int i = 0; i < 12; i++)
            {
                float temp = GenTemperature.AverageTemperatureAtTileForTwelfth(map.Tile, (Twelfth)((twelfth + i) % 12));
                // Mean temperatures are a seasonal estimate, not a weather forecast.
                if (temp < def.plant.minOptimalGrowthTemperature || temp > def.plant.maxOptimalGrowthTemperature) break;
                days += i == 0 ? 5 - day % 5 : 5;
            }
            return days;
        }

        public static ApiResult<CapabilityOrderResultDto> SetCrop(SetCropRequestDto request)
        {
            var result = new CapabilityOrderResultDto();
            try
            {
                var map = MapHelper.GetMapByID(request.MapId);
                var def = FarmHelper.ResolvePlantDef(request.PlantDef);
                if (map == null || def?.plant == null) return ApiResult<CapabilityOrderResultDto>.Fail("Unknown map or plant.");
                IPlantToGrowSettable grower = request.ZoneId.HasValue
                    ? (IPlantToGrowSettable)map.zoneManager.AllZones.OfType<Zone_Growing>().FirstOrDefault(z => z.ID == request.ZoneId)
                    : MapHelper.GetThingOnMapById(request.MapId, request.BuildingId ?? -1) as Building_PlantGrower;
                if (grower == null) return ApiResult<CapabilityOrderResultDto>.Fail("Grower not found.");
                if (!Command_SetPlantToGrow.IsPlantAvailable(def, map) || !PlantUtility.CanSowOnGrower(def, grower))
                    result.Reason = "plant_not_allowed_on_grower_or_research_locked";
                else
                {
                    var cells = grower is Zone_Growing zone ? zone.Cells : ((Building_PlantGrower)grower).OccupiedRect().Cells.ToList();
                    var site = Site(map, "verify", grower is Zone_Growing ? "ground" : "hydroponics", cells, grower,
                        new List<ThingDef> { def }, request.ZoneId, request.BuildingId, null, true);
                    var option = site.Options.FirstOrDefault();
                    if (option?.SafeSowingNow != true) result.Reason = option?.Reason ?? "no_legal_cells_for_crop";
                    else { grower.SetPlantDefToGrow(def); result.Applied = true; result.Reason = "crop_selected"; }
                }
                return ApiResult<CapabilityOrderResultDto>.Ok(result);
            }
            catch (Exception ex) { return ApiResult<CapabilityOrderResultDto>.Fail(ex.ToString()); }
        }

        public static ApiResult<CapabilityOrderResultDto> CutBlight(CutBlightRequestDto request)
        {
            var result = new CapabilityOrderResultDto();
            try
            {
                var map = MapHelper.GetMapByID(request.MapId);
                var worker = PawnHelper.FindPawnById(request.WorkerPawnId);
                if (map == null) return ApiResult<CapabilityOrderResultDto>.Fail("Map not found.");
                if (worker == null || worker.Faction != Faction.OfPlayer || worker.Map != map || worker.Downed
                    || worker.Drafted || worker.InMentalState || worker.WorkTypeIsDisabled(WorkTypeDefOf.PlantCutting))
                    result.Reason = "no_available_plant_cutter";
                else if (CombatNativeHelper.HasCareJob(worker) || worker.CurJobDef == JobDefOf.Ingest)
                    result.Reason = "worker_providing_patient_care";
                else
                {
                    var requestedIds = new HashSet<int>(request.PlantIds);
                    foreach (var plant in map.listerThings.AllThings.OfType<Plant>().Where(p => requestedIds.Contains(p.thingIDNumber)))
                    {
                        if (!plant.Blighted || !worker.CanReach(plant, PathEndMode.Touch, Danger.Some)) continue;
                        bool changed = map.designationManager.DesignationOn(plant, DesignationDefOf.CutPlant) == null;
                        if (changed)
                            map.designationManager.AddDesignation(new Designation(plant, DesignationDefOf.CutPlant));
                        if (plant.Position.GetZone(map) is Zone_Growing growingZone && growingZone.allowSow)
                        { growingZone.allowSow = false; changed = true; }
                        if (!changed) continue;
                        result.AffectedCount++;
                        if (!result.TargetId.HasValue) result.TargetId = plant.thingIDNumber;
                        if (result.AffectedCount >= 200) break;
                    }
                    if (result.TargetId.HasValue)
                    {
                        var target = MapHelper.GetThingOnMapById(request.MapId, result.TargetId.Value);
                        var scanner = DefDatabase<WorkGiverDef>.AllDefs.Select(d => d.Worker).OfType<WorkGiver_PlantsCut>().FirstOrDefault();
                        Job job = scanner?.JobOnThing(worker, target, true);
                        bool alreadyCuttingBlight = worker.CurJobDef == JobDefOf.CutPlant
                            && worker.CurJob.targetA.Thing is Plant currentPlant && currentPlant.Blighted;
                        if (job != null && !alreadyCuttingBlight) worker.jobs.TryTakeOrderedJob(job);
                    }
                    result.Applied = result.AffectedCount > 0;
                    result.Reason = result.Applied ? "blighted_plants_designated_for_cutting" : "no_reachable_blighted_plants";
                }
                return ApiResult<CapabilityOrderResultDto>.Ok(result);
            }
            catch (Exception ex) { return ApiResult<CapabilityOrderResultDto>.Fail(ex.ToString()); }
        }
    }
}

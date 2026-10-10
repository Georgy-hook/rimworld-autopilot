using System;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    // Read-only husbandry observations. Estimates never create food, beds or jobs.
    public static class AnimalHusbandryHelper
    {
        public static bool FreshStoredFeed(Thing t) => t != null && t.Spawned
            && t.def.category == ThingCategory.Item && !t.def.IsDrug && !t.def.IsCorpse
            && t.def.ingestible != null && !t.Position.Fogged(t.Map)
            && !t.IsForbidden(Faction.OfPlayer) && !t.IsBurning()
            && t.GetStatValue(StatDefOf.Nutrition) > 0f
            && (t.TryGetComp<CompRottable>()?.Stage ?? RotStage.Fresh) == RotStage.Fresh;
        public static float RecoveryDemand(Pawn p) => p.needs?.food == null ? 0f
            : p.needs.food.FoodFallPerTickAssumingCategory(HungerCategory.Fed, ignoreMalnutrition: true) * 60000f;
        public static float AdultBaseline(Pawn p) => SimplifiedPastureNutritionSimulator.NutritionConsumedPerDay(p.def);
        public static object ReadContext(Map map)
        {
            try { return Context(map); }
            catch(Exception error) { return new {available=false, reason="husbandry_read_failed", error=error.ToString()}; }
        }
        public static object Context(Map map)
        {
            var animals = map.mapPawns.SpawnedPawnsInFaction(Faction.OfPlayer)
                .Where(p => p.RaceProps.Animal && !p.Dead).ToArray();
            var humans = map.mapPawns.FreeColonistsSpawned.ToArray();
            var feeds = map.listerThings.AllThings.Where(FreshStoredFeed).ToArray();
            var haygrass=DefDatabase<ThingDef>.GetNamedSilentFail("Plant_Haygrass");
            float? feedGrowthDays=haygrass?.plant?.harvestedThingDef!=null
                && animals.Any(p=>p.RaceProps.CanEverEat(haygrass.plant.harvestedThingDef))
                ? (float?)PlantAutomationHelper.CalendarDays(haygrass,0,1,21) : null;
            var markers = map.listerBuildings.allBuildingsColonist.Select(b => b.TryGetComp<CompAnimalPenMarker>())
                .Where(p => p?.PenState?.Enclosed == true).ToArray();
            var rows = animals.Select(p => {
                var pregnancy = p.health.hediffSet.hediffs.OfType<Hediff_Pregnant>().FirstOrDefault();
                var curve = p.RaceProps.litterSizeCurve;
                int? litterMax = curve == null ? 1 : curve.Points.Any() ? (int?)Math.Ceiling(curve.Points.Max(point => point.x)) : null;
                return new {
                    id = p.thingIDNumber, species = p.def.defName, gender = p.gender.ToString(),
                    stage = p.ageTracker.CurLifeStage.defName, needs_pen = p.playerSettings == null ? (bool?)null : !p.playerSettings.SupportsAllowedAreas,
                    position = new {x=p.Position.x,z=p.Position.z}, roofed = p.Position.Roofed(map),
                    food = p.needs?.food?.CurLevelPercentage, downed = p.Downed,
                    recovery_nutrition_per_day = RecoveryDemand(p),
                    current_nutrition_per_day = p.needs?.food?.FoodFallPerTick * 60000f,
                    adult_baseline_nutrition_per_day = AdultBaseline(p),
                    newborn_baseline_nutrition_per_day = Need_Food.BaseHungerRate(p.RaceProps.lifeStageAges.First().def,p.def)*60000f,
                    pregnant = pregnancy != null, pregnancy_progress = pregnancy?.GestationProgress,
                    birth_days_nominal = pregnancy == null ? (float?)null
                        : Math.Max(0f,1f-pregnancy.GestationProgress)*p.RaceProps.gestationPeriodDays,
                    litter_max_estimate = litterMax, // Curve support, not a promise of surviving births.
                    bonded = p.relations.GetFirstDirectRelationPawn(PawnRelationDefOf.Bond, other => !other.Dead)!=null,
                    comfortable_min = p.GetStatValue(StatDefOf.ComfyTemperatureMin),
                    comfortable_max = p.GetStatValue(StatDefOf.ComfyTemperatureMax),
                    temperature = p.Position.GetTemperature(map), current_bed_id = p.CurrentBed()?.thingIDNumber,
                    pen_ids = markers.Where(c => c.PenState.ContainsConnectedRegion(p.GetRegion()))
                        .Select(c => c.parent.thingIDNumber).ToArray()
                };
            }).ToArray();
            // One pool per actual stack. Compatibility is different from current access.
            // Clients must allocate shared pools once, not sum each animal's reachable food.
            var pools = feeds.Where(t => animals.Any(p => p.RaceProps.CanEverEat(t.def) && p.WillEat(t)))
                .Select(t => new {
                    thing_id=t.thingIDNumber, def_name=t.def.defName,
                    nutrition=t.stackCount*t.GetStatValue(StatDefOf.Nutrition),
                    human_edible=humans.Any(p=>p.RaceProps.CanEverEat(t.def) && p.WillEat(t)),
                    compatible_ids=animals.Where(p=>p.RaceProps.CanEverEat(t.def) && p.WillEat(t))
                        .Select(p=>p.thingIDNumber).ToArray(),
                    accessible_ids=animals.Where(p=>!p.Downed && p.RaceProps.CanEverEat(t.def) && p.WillEat(t)
                        && !t.IsForbidden(p) && p.CanReserveAndReach(t,PathEndMode.Touch,Danger.Some)
                        && OrdinaryWorkSafety.Route(p,p.Position,t.Position,PathEndMode.Touch))
                        .Select(p=>p.thingIDNumber).ToArray(),
                    ticks_until_rot=t.TryGetComp<CompRottable>()?.TicksUntilRotAtCurrentTemp,
                    roofed=t.Position.Roofed(map)
                }).ToArray();
            var corpseSources=map.listerThings.AllThings.OfType<Corpse>()
                .Where(c=>c.InnerPawn?.RaceProps.Animal==true && !c.Position.Fogged(map) && !c.IsForbidden(Faction.OfPlayer)
                    && !c.IsBurning() && (c.TryGetComp<CompRottable>()?.Stage ?? RotStage.Fresh)==RotStage.Fresh)
                .Select(c=>new {thing_id=c.thingIDNumber,species=c.InnerPawn.def.defName,
                    compatible_ids=animals.Where(p=>p.RaceProps.CanEverEat(c.def) && p.WillEat(c)).Select(p=>p.thingIDNumber).ToArray(),
                    direct_access_ids=animals.Where(p=>!p.Downed && p.RaceProps.CanEverEat(c.def) && p.WillEat(c)
                        && p.CanReserveAndReach(c,PathEndMode.Touch,Danger.Some)).Select(p=>p.thingIDNumber).ToArray(),
                    ticks_until_rot=c.TryGetComp<CompRottable>()?.TicksUntilRotAtCurrentTemp,
                    not_allocated_to_reserve=true, ingestion_or_butchering_pending=true}).Where(c=>c.compatible_ids.Length>0).ToArray();
            float humanNutrition = feeds.Where(t => humans.Any(p => p.RaceProps.CanEverEat(t.def) && p.WillEat(t)
                && (p.foodRestriction?.CurrentFoodPolicy?.Allows(t) ?? true)))
                .Sum(t=>t.stackCount*t.GetStatValue(StatDefOf.Nutrition));
            var beds=map.listerBuildings.allBuildingsColonist.OfType<Building_Bed>()
                .Where(b=>b.def.building.bed_humanlike==false).Select(b=>new {
                    id=b.thingIDNumber, def_name=b.def.defName, temperature=b.Position.GetTemperature(map),
                    roofed=b.OccupiedRect().All(c=>c.Roofed(map)),
                    occupied_ids=b.CurOccupants.Select(p=>p.thingIDNumber).ToArray(),
                    suitable_ids=animals.Where(p=>RestUtility.CanUseBedEver(p,b.def)).Select(p=>p.thingIDNumber).ToArray(),
                    thermal_benefit_ids=animals.Where(p=>CareTriageHelper.ThermalBedBeneficial(p,b))
                        .Select(p=>p.thingIDNumber).ToArray(),
                    pen_ids=markers.Where(c=>c.PenState.ContainsConnectedRegion(b.GetRegion()))
                        .Select(c=>c.parent.thingIDNumber).ToArray(),
                    power_or_fuel_is_not_room_temperature=true
                }).ToArray();
            float longitude=Find.WorldGrid.LongLatOf(map.Tile).x;
            int twelfth=(int)GenDate.Twelfth(GenTicks.TicksAbs,longitude);
            int day=GenDate.DayOfYear(GenTicks.TicksAbs,longitude);
            var seasonal=Enumerable.Range(0,12).Select(i=>new {
                offset_days=i==0 ? 0 : 5-day%5+(i-1)*5,
                duration_days=i==0 ? 5-day%5 : 5,
                mean_c=GenTemperature.AverageTemperatureAtTileForTwelfth(map.Tile,(Twelfth)((twelfth+i)%12))
            }).ToArray();
            return new { available=true, observed_tick=Find.TickManager.TicksGame,
                animals=rows, feed_pools=pools, corpse_food_potential=corpseSources, animal_beds=beds, human_nutrition=humanNutrition,
                human_reserve_nutrition=humans.Length*1.8f, seasonal_means=seasonal,
                human_demand_nutrition_day=humans.Sum(RecoveryDemand),
                hay_unit_nutrition=DefDatabase<ThingDef>.GetNamedSilentFail("Hay")?.GetStatValueAbstract(StatDefOf.Nutrition),
                post_climate_feed_growth_days_normal=feedGrowthDays,
                feed_growth_assumption="Loaded haygrass at normal fertility and 21C after thaw, before sow/harvest/haul delays; not a ready crop or guaranteed harvest.",
                forecast_basis="Actual needs/definitions and public seasonal means; recovered demand ignores starvation slowdown. Pregnancy and growth estimates are conditional; access, hauling, heat, disease, waste and weather must be checked separately.",
                pasture_is_not_stored_feed=true, existing_blueprints_are_not_shelter=true };
        }
        public static int[] PenIds(Map m,System.Collections.Generic.IEnumerable<IntVec3> cells)
        {
            var regions=cells.Select(c=>c.GetRegion(m)).Where(r=>r!=null).Distinct().ToArray();
            return m.listerBuildings.allBuildingsColonist.Select(b=>b.TryGetComp<CompAnimalPenMarker>())
                .Where(c=>c?.PenState?.Enclosed==true && regions.Any(r=>c.PenState.ContainsConnectedRegion(r)))
                .Select(c=>c.parent.thingIDNumber).ToArray();
        }
    }
}

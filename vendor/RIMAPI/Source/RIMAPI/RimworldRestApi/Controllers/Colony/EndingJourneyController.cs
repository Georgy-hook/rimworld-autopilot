using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Helpers;
using RIMAPI.Http;
using RimWorld;
using RimWorld.Planet;
using Verse;

namespace RIMAPI.Controllers
{
    public class EndingJourneyRoute : IExposable
    {
        public List<int> PawnIds = new List<int>();
        public int ObjectId;
        public void ExposeData() {
            Scribe_Collections.Look(ref PawnIds, "pawnIds", LookMode.Value);
            Scribe_Values.Look(ref ObjectId, "objectId");
        }
    }
    // Persist the forming caravan's destination until the native caravan exists.
    // The game's own CaravanArrivalAction then persists the actual journey.
    public class EndingJourneyState : GameComponent
    {
        public List<EndingJourneyRoute> Routes = new List<EndingJourneyRoute>();
        public EndingJourneyState(Game game) { }
        public override void ExposeData() {
            Scribe_Collections.Look(ref Routes, "layaEndingJourneys", LookMode.Deep);
            if (Scribe.mode == LoadSaveMode.PostLoadInit && Routes == null) Routes = new List<EndingJourneyRoute>();
        }
        public override void GameComponentTick() {
            if (Find.TickManager.TicksGame % 60 != 0) return;
            for (int i = Routes.Count - 1; i >= 0; i--) {
                var route = Routes[i];
                var target = Find.WorldObjects.AllWorldObjects.OfType<MapParent>().FirstOrDefault(o => o.ID == route.ObjectId);
                if (target == null) { Routes.RemoveAt(i); continue; }
                var caravan = Find.WorldObjects.Caravans.FirstOrDefault(c => c.IsPlayerControlled && route.PawnIds.All(id => c.PawnsListForReading.Any(p => p.thingIDNumber == id)));
                if (caravan == null) continue;
                var arrival = EndingJourneyController.Arrival(target);
                if (arrival != null && arrival.StillValid(caravan, target.Tile) && Find.WorldReachability.CanReach(caravan, target.Tile))
                    caravan.pather.StartPath(target.Tile, arrival, true);
                Routes.RemoveAt(i);
            }
        }
    }
    public class EndingJourneyPlan
    {
        public int MapId, ObjectId, SupplyDays;
        public string Team, Route, Label;
        public List<int> PawnIds;
        public List<string> Travelers, ColonistsAtHome;
        public float FoodNutrition, HomeFoodNutrition, Mass, Capacity, ApproximateDistanceTiles, DailyNutrition, NativeApproxFoodDays;
        public int MedicineCount;
        public float? TravelDays, FoodMarginDays;
        public string TravelEstimateReason;
    }
    public class EndingJourneyController
    {
        private class JourneyEstimate { public float? Days; public string Reason; }
        private static JourneyEstimate TravelEstimate(Map map, MapParent target, List<Pawn> pawns, Dictionary<string, JourneyEstimate> cache) {
            string key = target.ID + ":" + string.Join(",", pawns.Select(p => p.thingIDNumber));
            if (cache.TryGetValue(key, out var prior)) return prior;
            var result = new JourneyEstimate(); cache[key] = result;
            if (map == null || pawns.Count == 0) { result.Reason = "No map or travelers"; return result; }
            if (map.Tile.Layer != target.Tile.Layer || !map.Tile.LayerDef.SurfaceTiles) { result.Reason = "Native surface caravan estimator unavailable for this layer"; return result; }
            PlanetTile start = CaravanExitMapUtility.BestExitTileToGoTo(target.Tile, map);
            if (!start.Valid) { result.Reason = "No native exit tile"; return result; }
            try { using (var path = start.Layer.Pather.FindPath(start, target.Tile, null)) {
                if (!path.Found) { result.Reason = "Native path not found"; return result; }
                // Estimate once per target/team at full legal carrying capacity.
                // Lighter supply alternatives can move faster; food days stay separate.
                float capacity = pawns.Sum(p => MassUtility.Capacity(p));
                int speed = CaravanTicksPerMoveUtility.GetTicksPerMove(pawns, capacity, capacity);
                int ticks = CaravanArrivalTimeEstimator.EstimatedTicksToArrive(start, target.Tile, path, 0f, speed, Find.TickManager.TicksAbs);
                if (ticks <= 0 && start != target.Tile) { result.Reason = "Native estimator did not return a positive arrival estimate"; return result; }
                result.Days = ticks / 60000f;
                result.Reason = "Native path/rest/season estimator at full carrying capacity; formation time and future events excluded";
            } } catch (Exception error) { result.Reason = "Native travel estimator unavailable: " + error.GetType().Name; }
            return result;
        }
        internal static CaravanArrivalAction Arrival(MapParent target) => target.GetComponent<EscapeShipComp>() is EscapeShipComp ship
            ? (CaravanArrivalAction)new CaravanArrivalAction_VisitEscapeShip(ship)
            : target is Site site ? new CaravanArrivalAction_VisitSite(site) : null;
        private static IEnumerable<MapParent> Targets() {
            var disclosed = Find.QuestManager.QuestsListForReading.Where(q => !q.hidden && !q.dismissed && q.root != null && q.root.defName.StartsWith("EndGame_"))
                .SelectMany(q => q.QuestLookTargets).Select(t => t.WorldObject).OfType<MapParent>();
            return disclosed.Concat(Find.WorldObjects.AllWorldObjects.OfType<MapParent>().Where(o => o.HasMap && o.GetComponent<EscapeShipComp>() != null))
                .Where(o => o.Spawned && o.Tile.Valid && (o.GetComponent<EscapeShipComp>() != null || o is Site s && s.sitePartsKnown && !s.parts.Any(p => p.hidden))).Distinct();
        }
        private static bool TravelFood(Thing t) => !t.IsForbidden(Faction.OfPlayer) &&
            t.def.defName == "MealSurvivalPack" && t.TryGetComp<CompRottable>() == null;
        private static bool Medicine(Thing t) => !t.IsForbidden(Faction.OfPlayer) && t.def.IsMedicine;
        private static float DailyNutrition(List<Pawn> pawns) => pawns.Sum(p => p.needs?.food == null ? 0f :
            p.needs.food.NutritionBetweenHungryAndFed * 60000f / Math.Max(1, p.needs.food.TicksUntilHungryWhenFedIgnoringMalnutrition));
        private static bool SuitableFood(Thing food, List<Pawn> pawns) => TravelFood(food) && food.IngestibleNow &&
            pawns.All(p => p.needs?.food == null || CaravanPawnsNeedsUtility.CanEatForNutritionEver(food.def, p) &&
                (p.foodRestriction?.CurrentFoodPolicy?.filter.Allows(food) ?? true));
        private static List<TransferableOneWay> Supplies(List<Thing> items, List<Pawn> pawns, int days, out float nutrition, out int medicine) {
            int people = pawns.Count;
            float required = DailyNutrition(pawns) * days;
            var result = new List<TransferableOneWay>(); nutrition = 0; medicine = 0;
            foreach (var item in items.Where(t => SuitableFood(t, pawns)).OrderByDescending(t => t.GetStatValue(StatDefOf.Nutrition))) {
                float per = item.GetStatValue(StatDefOf.Nutrition);
                if (per <= 0 || nutrition >= required) continue;
                int count = Math.Min(item.stackCount, (int)Math.Ceiling((required - nutrition) / per));
                var transfer = new TransferableOneWay(); transfer.things.Add(item); transfer.AdjustTo(count); result.Add(transfer);
                nutrition += per * count;
            }
            foreach (var item in items.Where(Medicine).OrderBy(t => t.MarketValue)) {
                int count = Math.Min(item.stackCount, people * 2 - medicine); if (count <= 0) break;
                var transfer = new TransferableOneWay(); transfer.things.Add(item); transfer.AdjustTo(count); result.Add(transfer); medicine += count;
            }
            return result;
        }
        private static List<EndingJourneyPlan> Plans(int mapId, Dictionary<string, JourneyEstimate> estimates = null) {
            if (estimates == null) estimates = new Dictionary<string, JourneyEstimate>();
            var result = new List<EndingJourneyPlan>(); var map = MapHelper.GetMapByID(mapId);
            if (map == null || GenHostility.AnyHostileActiveThreatToPlayer(map) || Find.WorldObjects.Caravans.Any(c => c.IsPlayerControlled) ||
                Current.Game.GetComponent<EndingJourneyState>().Routes.Any()) return result;
            var available = map.mapPawns.FreeColonistsSpawned.Where(p => !SpecialistNativeSafety.Protected(p) && !p.Downed && !p.InMentalState &&
                p.health.summaryHealth.SummaryHealthPercent >= 0.8f).OrderByDescending(p => p.equipment?.Primary != null).ThenBy(p => p.thingIDNumber).ToList();
            var items = CaravanFormingUtility.AllReachableColonyItems(map);
            float totalNutrition = items.Where(TravelFood).Sum(t => t.GetStatValue(StatDefOf.Nutrition) * t.stackCount);
            int totalMedicine = items.Where(Medicine).Sum(t => t.stackCount);
            foreach (var target in Targets().Where(t => t.Tile != map.Tile && Find.WorldReachability.CanReach(map.Tile, t.Tile))) {
                foreach (string team in new[] { "scout", "migration" }) {
                    var pawns = team == "scout" ? available.Take(2).ToList() : available;
                    if (pawns.Count < (team == "scout" ? 2 : 1)) continue;
                    var home = map.mapPawns.FreeColonistsSpawned.Except(pawns).ToList();
                    if (team == "scout" && home.Count(p => !p.Downed && !p.InMentalState && p.equipment?.Primary != null && !p.WorkTagIsDisabled(WorkTags.Violent)) < 2) continue;
                    var estimate = TravelEstimate(map, target, pawns, estimates);
                    int routeBudget = estimate.Days.HasValue ? Math.Max(5, (int)Math.Ceiling(estimate.Days.Value + 2f)) : 5;
                    foreach (int days in new[] { 5, 15, 30, routeBudget }.Distinct()) {
                        float food; int meds; var supplies = Supplies(items, pawns, days, out food, out meds);
                        if (food < DailyNutrition(pawns) * days || meds < pawns.Count || totalNutrition - food < (home.Count > 0 ? 30f : 0f) || totalMedicine - meds < (home.Count > 0 ? 8 : 0)) continue;
                        float nativeDays = DaysWorthOfFoodCalculator.ApproxDaysWorthOfFood(pawns, supplies.Where(t => TravelFood(t.AnyThing)).Select(t => new ThingCount(t.AnyThing, t.CountToTransfer)).ToList(), map.Tile, IgnorePawnsInventoryMode.Ignore, Faction.OfPlayer);
                        if (estimate.Days.HasValue && nativeDays < estimate.Days.Value + 1f) continue;
                        float mass = pawns.Sum(p => MassUtility.GearAndInventoryMass(p)) + supplies.Sum(t => t.AnyThing.GetStatValue(StatDefOf.Mass) * t.CountToTransfer);
                        float capacity = pawns.Sum(p => MassUtility.Capacity(p)); if (mass > capacity) continue;
                        result.Add(new EndingJourneyPlan { MapId = mapId, ObjectId = target.ID, Team = team, SupplyDays = days,
                            Route = target.GetComponent<EscapeShipComp>() != null ? "ship_journey" : "archonexus",
                            Label = "Travel to " + target.Label + " (" + team + ", " + days + " nominal food days)",
                            PawnIds = pawns.Select(p => p.thingIDNumber).ToList(), Travelers = pawns.Select(p => p.LabelShortCap.ToString()).ToList(),
                            ColonistsAtHome = home.Select(p => p.LabelShortCap.ToString()).ToList(), FoodNutrition = food, HomeFoodNutrition = totalNutrition - food,
                            MedicineCount = meds, Mass = mass, Capacity = capacity, DailyNutrition = DailyNutrition(pawns), NativeApproxFoodDays = nativeDays,
                            TravelDays = estimate.Days, FoodMarginDays = estimate.Days.HasValue ? nativeDays - estimate.Days.Value : (float?)null, TravelEstimateReason = estimate.Reason,
                            ApproximateDistanceTiles = Find.WorldGrid.ApproxDistanceInTiles(map.Tile, target.Tile) });
                    }
                }
            }
            return result;
        }
        [Get("/api/v1/colony/endings/journey")]
        [EndpointMetadata("Read native escape ship and offered ending site expeditions, explicit traveler groups and carried supply budgets")]
        public async Task Context(HttpListenerContext context) {
            int mapId = RequestParser.GetIntParameter(context, "map_id");
            var map = MapHelper.GetMapByID(mapId);
            var recipes = DefDatabase<RecipeDef>.AllDefsListForReading.Where(r => r.products != null && r.products.Any(p => p.thingDef.defName == "MealSurvivalPack")).ToList();
            var readiness = new List<object>();
            var estimates = new Dictionary<string, JourneyEstimate>();
            bool needsRations = false;
            var items = map == null ? new List<Thing>() : CaravanFormingUtility.AllReachableColonyItems(map);
            var available = map == null ? new List<Pawn>() : map.mapPawns.FreeColonistsSpawned.Where(p => !SpecialistNativeSafety.Protected(p) && !p.Downed && !p.InMentalState && p.health.summaryHealth.SummaryHealthPercent >= 0.8f).OrderByDescending(p => p.equipment?.Primary != null).ThenBy(p => p.thingIDNumber).ToList();
            foreach (var target in Targets()) foreach (string team in new[] { "scout", "migration" }) {
                var pawns = team == "scout" ? available.Take(2).ToList() : available;
                var home = map == null ? new List<Pawn>() : map.mapPawns.FreeColonistsSpawned.Except(pawns).ToList();
                var estimate = TravelEstimate(map, target, pawns, estimates);
                int requiredDays = estimate.Days.HasValue ? Math.Max(5, (int)Math.Ceiling(estimate.Days.Value + 2f)) : 5;
                float food; int meds; var supplies = Supplies(items, pawns, requiredDays, out food, out meds);
                float stockFoodDays = DaysWorthOfFoodCalculator.ApproxDaysWorthOfFood(pawns, items.Where(t => SuitableFood(t, pawns)).Select(t => new ThingCount(t, t.stackCount)).ToList(), map == null ? target.Tile : map.Tile, IgnorePawnsInventoryMode.Ignore, Faction.OfPlayer);
                float capacity = pawns.Sum(p => MassUtility.Capacity(p));
                float mass = pawns.Sum(p => MassUtility.GearAndInventoryMass(p)) + supplies.Sum(t => t.AnyThing.GetStatValue(StatDefOf.Mass) * t.CountToTransfer);
                var blockers = new List<string>();
                if (map == null) blockers.Add("map unavailable");
                if (map != null && GenHostility.AnyHostileActiveThreatToPlayer(map)) blockers.Add("active home threat");
                if (Find.WorldObjects.Caravans.Any(c => c.IsPlayerControlled)) blockers.Add("player caravan already active");
                if (Current.Game.GetComponent<EndingJourneyState>().Routes.Any()) blockers.Add("ending caravan already forming");
                if (pawns.Count < (team == "scout" ? 2 : 1)) blockers.Add("insufficient healthy available travelers");
                if (team == "scout" && home.Count(p => !p.Downed && !p.InMentalState && p.equipment?.Primary != null && !p.WorkTagIsDisabled(WorkTags.Violent)) < 2) blockers.Add("scout needs two armed mobile home defenders");
                if (map != null && !Find.WorldReachability.CanReach(map.Tile, target.Tile)) blockers.Add("native world path unreachable");
                if (food < DailyNutrition(pawns) * requiredDays || estimate.Days.HasValue && stockFoodDays < estimate.Days.Value + 1f) { blockers.Add("insufficient food edible and policy-allowed for every traveler"); needsRations = true; }
                if (meds < pawns.Count) blockers.Add("insufficient travel medicine");
                if (home.Count > 0 && items.Where(TravelFood).Sum(t => t.GetStatValue(StatDefOf.Nutrition) * t.stackCount) - food < 30) { blockers.Add("home travel-food reserve below 30 nutrition"); needsRations = true; }
                if (home.Count > 0 && items.Where(Medicine).Sum(t => t.stackCount) - meds < 8) blockers.Add("home medicine reserve below eight");
                if (mass > capacity) blockers.Add("travel supplies exceed carrying capacity");
                readiness.Add(new { object_id = target.ID, label = target.Label, route = target.GetComponent<EscapeShipComp>() != null ? "ship_journey" : "archonexus", team,
                    travelers = pawns.Select(p => p.LabelShortCap.ToString()).ToList(), blockers,
                    minimum_supply_days = requiredDays, daily_nutrition = DailyNutrition(pawns), required_minimum_nutrition = DailyNutrition(pawns) * requiredDays,
                    acceptable_stock_nutrition = items.Where(t => SuitableFood(t, pawns)).Sum(t => t.GetStatValue(StatDefOf.Nutrition) * t.stackCount),
                    travel_days = estimate.Days, travel_estimate_reason = estimate.Reason,
                    stock_food_days = stockFoodDays, stock_food_margin_days = estimate.Days.HasValue ? stockFoodDays - estimate.Days.Value : (float?)null,
                    mass, capacity, home_colonists = home.Select(p => p.LabelShortCap.ToString()).ToList() });
            }
            await context.SendJsonResponse(ApiResult<object>.Ok(new { journeys = Plans(mapId, estimates), readiness,
                support_research_targets = needsRations ? recipes.Where(r => r.researchPrerequisite != null).Select(r => r.researchPrerequisite.defName).Distinct().ToList() : new List<string>(),
                ration_production = recipes.Select(r => new { name = r.defName, label = r.label, research = r.researchPrerequisite?.defName,
                    available_now = r.AvailableNow, skill_requirements = r.skillRequirements?.Select(s => new { skill = s.skill.defName, minimum = s.minLevel }).ToList(),
                    stations = DefDatabase<ThingDef>.AllDefsListForReading.Where(d => d.AllRecipes?.Contains(r) == true).Select(d => d.defName).ToList() }).ToList(),
                warning = "Food budgets use each selected pawn's native food need consumption rate. Every packed food must satisfy native caravan edibility and each traveler's current food policy. Native approximate food days exclude existing inventories; foraging, illness and path conditions can change the estimate. Food days are not route ETA. No animals travel in these plans. Formation, travel and arrival never verify victory." }));
        }
        [Post("/api/v1/colony/endings/journey")]
        [EndpointMetadata("Start one freshly feasible native ending caravan; persist its ordinary visit arrival until caravan formation completes")]
        public async Task Start(HttpListenerContext context) {
            int mapId = RequestParser.GetIntParameter(context, "map_id"), objectId = RequestParser.GetIntParameter(context, "object_id"), days = RequestParser.GetIntParameter(context, "supply_days");
            string team = RequestParser.GetStringParameter(context, "team"), ids = RequestParser.GetStringParameter(context, "pawn_ids");
            var plan = Plans(mapId).FirstOrDefault(p => p.ObjectId == objectId && p.Team == team && p.SupplyDays == days && string.Join(",", p.PawnIds) == ids);
            if (!RequestParser.GetBooleanParameter(context, "confirmed") || plan == null) { await context.SendJsonResponse(ApiResult<string>.Fail("Journey requirements or travelers changed")); return; }
            var map = MapHelper.GetMapByID(mapId); var target = Targets().First(t => t.ID == objectId);
            var pawns = map.mapPawns.FreeColonistsSpawned.Where(p => plan.PawnIds.Contains(p.thingIDNumber)).ToList();
            PlanetTile exitTile = CaravanExitMapUtility.BestExitTileToGoTo(target.Tile, map);
            IntVec3 center = pawns.Aggregate(IntVec3.Zero, (sum, p) => sum + p.Position) / pawns.Count;
            if (!exitTile.Valid || !RCellFinder.TryFindClosestEdgeCellTo(center, map, out IntVec3 exitSpot)) { await context.SendJsonResponse(ApiResult<string>.Fail("No native caravan exit")); return; }
            if (!RCellFinder.TryFindRandomSpotJustOutsideColony(exitSpot, map, out IntVec3 meeting)) meeting = center;
            float food; int meds; var supplies = Supplies(CaravanFormingUtility.AllReachableColonyItems(map), pawns, days, out food, out meds);
            CaravanFormingUtility.StartFormingCaravan(pawns, new List<Pawn>(), Faction.OfPlayer, supplies, meeting, exitSpot, exitTile, target.Tile);
            Current.Game.GetComponent<EndingJourneyState>().Routes.Add(new EndingJourneyRoute { PawnIds = plan.PawnIds, ObjectId = objectId });
            await context.SendJsonResponse(ApiResult<string>.Ok("ending_caravan_forming"));
        }
    }
}

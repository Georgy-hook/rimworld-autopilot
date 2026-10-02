using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using RIMAPI.Core;
using RIMAPI.Models;
using RimWorld;
using RimWorld.Planet;
using Verse;
using Verse.AI.Group;

namespace RIMAPI.Helpers {
    public static class ExpeditionPlanHelper {
        private sealed class Plan {
            public ExpeditionPlanDto Dto;
            public Map Map;
            public MapParent Target;
            public List<Pawn> Pawns;
            public List<TransferableOneWay> Supplies;
        }
        internal static bool Available(Pawn p) {
            string job = p?.CurJob?.def?.defName ?? "";
            return p != null && !p.Dead && !p.Downed && !p.InMentalState && !p.Drafted &&
                p.GetLord() == null && p.health.summaryHealth.SummaryHealthPercent >= .80f &&
                !p.health.HasHediffsNeedingTend() && !HealthAIUtility.ShouldSeekMedicalRest(p) && !CombatNativeHelper.HasCareJob(p) &&
                !new[] { "Ingest", "PatientGoToBed", "LayDown", "CarryToCryptosleepCasket", "EnterCryptosleepCasket" }.Contains(job);
        }
        private static bool TravelFood(Thing t) => !t.IsForbidden(Faction.OfPlayer) && t.IngestibleNow &&
            (t.def.defName == "MealSurvivalPack" || t.def.defName == "Pemmican");
        private static bool Edible(Thing t, Pawn p) => p.needs?.food == null ||
            CaravanPawnsNeedsUtility.CanEatForNutritionEver(t.def, p) && (p.foodRestriction?.CurrentFoodPolicy?.filter.Allows(t) ?? true);
        private static float Daily(Pawn p) => p.needs?.food == null ? 0f :
            p.needs.food.NutritionBetweenHungryAndFed * 60000f / Math.Max(1, p.needs.food.TicksUntilHungryWhenFedIgnoringMalnutrition);
        private static bool Suitable(Thing t, List<Pawn> pawns, float days) => TravelFood(t) && t.IngestibleNow && pawns.All(p => Edible(t, p)) &&
            (t.TryGetComp<CompRottable>() == null || t.TryGetComp<CompRottable>().TicksUntilRotAtTemp(40f) >= days * 60000f);
        private static string Hash(string text) {
            using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(text))).Replace("-", "").ToLowerInvariant();
        }
        internal static string Selection(ExpeditionRequestDto r) => string.Join("|", r.Mode, r.MapId, r.DestinationSettlementId, r.SiteId, r.QuestId,
            r.MinimumHomeDefenders, r.MinimumFoodAtHome, r.MinimumMedicineAtHome, r.MarginDays.ToString("R", System.Globalization.CultureInfo.InvariantCulture), r.AllowStartingWar,
            string.Join(",", (r.SaleCategories ?? new List<string>()).OrderBy(v => v)), string.Join(",", (r.PurchasePriorities ?? new List<string>()).OrderBy(v => v)),
            string.Join(",", (r.PrisonerIds ?? new List<int>()).OrderBy(v => v)));
        private static float Estimate(PlanetTile from, PlanetTile to, List<Pawn> pawns, float capacity, int ticksAbs) {
            if (!from.Valid || !to.Valid || from.Layer != to.Layer || !from.LayerDef.SurfaceTiles)
                throw new InvalidOperationException("Native surface route estimator unavailable for this destination layer");
            using (var path = from.Layer.Pather.FindPath(from, to, null)) {
                if (!path.Found) throw new InvalidOperationException("No native path to the selected destination");
                int speed = CaravanTicksPerMoveUtility.GetTicksPerMove(pawns, capacity, capacity);
                int ticks = CaravanArrivalTimeEstimator.EstimatedTicksToArrive(from, to, path, 0f, speed, ticksAbs);
                if (ticks <= 0 && from != to) throw new InvalidOperationException("Native route ETA is unknown");
                return ticks / 60000f;
            }
        }
        private static void Add(List<TransferableOneWay> supplies, Thing thing, int count) {
            if (count <= 0) return;
            var row = new TransferableOneWay(); row.things.Add(thing); row.AdjustTo(count); supplies.Add(row);
        }
        private static int Count(List<TransferableOneWay> rows, Func<Thing, bool> match) => rows.Where(t => match(t.AnyThing)).Sum(t => t.CountToTransfer);
        private static float Nutrition(List<TransferableOneWay> rows) => rows.Where(t => TravelFood(t.AnyThing)).Sum(t => t.AnyThing.GetStatValue(StatDefOf.Nutrition) * t.CountToTransfer);
        private static Plan Build(ExpeditionRequestDto r, Dictionary<string, object> facts = null) {
            facts = facts ?? new Dictionary<string, object>();
            facts["mode"] = r.Mode; facts["map_id"] = r.MapId;
            facts["minimum_home_food_items"] = r.MinimumFoodAtHome; facts["minimum_home_medicine"] = r.MinimumMedicineAtHome; facts["margin_days"] = r.MarginDays;
            var map = MapHelper.GetMapByID(r.MapId) ?? throw new InvalidOperationException("Origin map unavailable");
            if (!new[] { "trade", "raid", "rescue" }.Contains(r.Mode)) throw new InvalidOperationException("Choose trade, raid or rescue explicitly");
            if (GenHostility.AnyHostileActiveThreatToPlayer(map)) throw new InvalidOperationException("Active home threat prevents expedition");
            if (Find.WorldObjects.Caravans.Any(c => c.Faction == Faction.OfPlayer)) throw new InvalidOperationException("Player caravan already active; observe its route first");
            facts["active_formation_lord_ids"] = map.lordManager.lords.Where(l => l.LordJob is LordJob_FormAndSendCaravan).Select(l => l.loadID).ToList();
            if (map.lordManager.lords.Any(l => l.LordJob is LordJob_FormAndSendCaravan)) throw new InvalidOperationException("Native caravan formation already active");
            if (r.MinimumFoodAtHome < 0 || r.MinimumMedicineAtHome < 0 || r.MinimumHomeDefenders < 2 || r.MarginDays < 1 || r.MarginDays > 15)
                throw new InvalidOperationException("Invalid explicit home reserves or margin (1..15 days)");
            MapParent target;
            if (r.Mode == "rescue") {
                var quest = Find.QuestManager.QuestsListForReading.FirstOrDefault(q => q.id == r.QuestId && !q.Historical && !q.hidden && !q.dismissed);
                if (quest == null || !r.SiteId.HasValue) throw new InvalidOperationException("A disclosed live rescue quest and selected site are required");
                target = quest.QuestLookTargets.Select(t => t.WorldObject).OfType<Site>().FirstOrDefault(t => t.ID == r.SiteId.Value);
                if (!(target is Site site) || !site.sitePartsKnown || site.parts.Any(p => p.hidden)) throw new InvalidOperationException("Selected rescue site is not disclosed by this quest");
            } else {
                var settlement = Find.WorldObjects.Settlements.FirstOrDefault(t => t.ID == r.DestinationSettlementId);
                if (settlement?.Faction == null || settlement.Faction == Faction.OfPlayer) throw new InvalidOperationException("Selected settlement unavailable");
                if (r.Mode == "trade" && (settlement.HasMap || settlement.Faction.HostileTo(Faction.OfPlayer) || settlement.Faction.def.permanentEnemy || !settlement.Visitable || !settlement.CanTradeNow))
                    throw new InvalidOperationException("Selected settlement is not currently tradeable");
                if (r.Mode == "raid" && (!settlement.Attackable || !settlement.Faction.HostileTo(Faction.OfPlayer) && !r.AllowStartingWar))
                    throw new InvalidOperationException("Raid unavailable or starting war was not explicitly accepted");
                target = settlement;
            }
            facts["target_id"] = target.ID; facts["destination_name"] = target.LabelCap.ToString();
            if (!target.Spawned || !target.Tile.Valid) throw new InvalidOperationException("Selected destination disappeared");
            var all = map.mapPawns.FreeColonistsSpawned.ToList();
            var eligible = all.Where(p => Available(p) && CaravanAutomationHelper.IsReadyDefender(p) &&
                p.health.summaryHealth.SummaryHealthPercent >= (r.Mode == "raid" ? .85f : r.Mode == "rescue" ? .82f : .80f)).ToList();
            int minimum = r.Mode == "trade" ? 1 : r.Mode == "raid" ? 3 : 2;
            int maximum = r.Mode == "trade" ? 2 : r.Mode == "raid" ? 5 : Math.Max(2, Math.Min(6, (int)Math.Ceiling(((Site)target).ActualThreatPoints / 180f)));
            List<Pawn> team;
            if (r.PawnIds != null) {
                if (r.PawnIds.Distinct().Count() != r.PawnIds.Count) throw new InvalidOperationException("Duplicate traveler IDs");
                team = eligible.Where(p => r.PawnIds.Contains(p.thingIDNumber)).OrderBy(p => p.thingIDNumber).ToList();
                if (team.Count != r.PawnIds.Count) throw new InvalidOperationException("Selected traveler is unavailable, caring, eating or a medical patient");
            } else {
                team = eligible.OrderByDescending(p => r.Mode == "trade" ? (p.skills?.GetSkill(SkillDefOf.Social)?.Level ?? 0) * 3 + (p.skills?.GetSkill(SkillDefOf.Shooting)?.Level ?? 0) :
                    (p.skills?.GetSkill(SkillDefOf.Shooting)?.Level ?? 0) + (p.skills?.GetSkill(SkillDefOf.Melee)?.Level ?? 0))
                    .ThenBy(p => p.thingIDNumber).Take(Math.Max(0, Math.Min(maximum, eligible.Count - r.MinimumHomeDefenders))).OrderBy(p => p.thingIDNumber).ToList();
            }
            if (team.Count < minimum || team.Count > maximum) throw new InvalidOperationException("Insufficient selected armed travelers while preserving home defenders");
            if (r.Mode == "trade" && !team.Any(p => p.skills?.GetSkill(SkillDefOf.Social)?.TotallyDisabled == false && p.CanTradeWith(target.Faction, ((Settlement)target).TraderKind).Accepted)) throw new InvalidOperationException("Selected trade team has no capable negotiator");
            var home = all.Except(team).OrderBy(p => p.thingIDNumber).ToList();
            int defenders = home.Count(p => Available(p) && CaravanAutomationHelper.IsReadyDefender(p));
            if (defenders < r.MinimumHomeDefenders) throw new InvalidOperationException("Selected roster violates home defender policy");
            if (r.HomePawnIds != null && !home.Select(p => p.thingIDNumber).SequenceEqual(r.HomePawnIds.OrderBy(v => v))) throw new InvalidOperationException("Home roster changed");
            var prisonerIds = r.PrisonerIds ?? new List<int>();
            if (r.Mode != "trade" && prisonerIds.Count > 0) throw new InvalidOperationException("Prisoner exports only supported for chosen trade policy");
            var prisoners = map.mapPawns.PrisonersOfColony.Where(p => prisonerIds.Contains(p.thingIDNumber) && Available(p)).OrderBy(p => p.thingIDNumber).ToList();
            if (prisonerIds.Count != prisonerIds.Distinct().Count() || prisoners.Count != prisonerIds.Count) throw new InvalidOperationException("Selected prisoner unavailable, eating or needs care");
            if (prisoners.Any(p => ((Settlement)target).TraderKind == null || !((Settlement)target).TraderKind.WillTrade(p.def))) throw new InvalidOperationException("Selected settlement does not buy these prisoners");
            var travelers = team.Concat(prisoners).ToList();
            float capacity = travelers.Sum(p => MassUtility.Capacity(p));
            PlanetTile exit = CaravanExitMapUtility.BestExitTileToGoTo(target.Tile, map);
            float outward = Estimate(exit, target.Tile, travelers, capacity, Find.TickManager.TicksAbs);
            float back = Estimate(target.Tile, map.Tile, travelers, capacity, Find.TickManager.TicksAbs + (int)(outward * 60000f));
            float days = outward + back + r.MarginDays;
            facts["outbound_days"] = outward; facts["return_days"] = back; facts["required_food_days"] = days;
            facts["pawn_ids"] = team.Select(p => p.thingIDNumber).ToList(); facts["home_defenders"] = defenders;
            var items = CaravanFormingUtility.AllReachableColonyItems(map).Where(t => !t.IsForbidden(Faction.OfPlayer)).OrderBy(t => t.thingIDNumber).ToList();
            var supplies = new List<TransferableOneWay>();
            float daily = travelers.Sum(Daily);
            int totalFoodItems = items.Where(TravelFood).Sum(t => t.stackCount);
            int totalMedicine = items.Where(t => t.def.IsMedicine).Sum(t => t.stackCount);
            facts["daily_nutrition"] = daily; facts["required_nutrition"] = daily * days;
            facts["acceptable_stock_nutrition"] = items.Where(t => Suitable(t, travelers, days)).Sum(t => t.GetStatValue(StatDefOf.Nutrition) * t.stackCount);
            facts["stock_food_items"] = totalFoodItems; facts["stock_medicine"] = totalMedicine;
            facts["capacity"] = capacity; facts["carried_gear_mass"] = travelers.Sum(p => MassUtility.GearAndInventoryMass(p));
            facts["ration_support"] = "Produce diet-compatible packaged survival meals (PackagedSurvivalMeal research, Cooking 8, fueled/electric stove); Pemmican only if its conservative 40C lifetime covers both legs plus margin";
            if (r.Manifest != null) {
                if (r.Manifest.Any(v => v.Count <= 0) || r.Manifest.Select(v => v.ThingId).Distinct().Count() != r.Manifest.Count) throw new InvalidOperationException("Invalid selected manifest");
                foreach (var selected in r.Manifest.OrderBy(v => v.ThingId)) {
                    var item = items.FirstOrDefault(t => t.thingIDNumber == selected.ThingId && t.def.defName == selected.DefName && t.stackCount >= selected.Count);
                    if (item == null || TravelFood(item) && !Suitable(item, travelers, days)) throw new InvalidOperationException("Selected cargo or ration diet/lifetime changed");
                    if (!TravelFood(item) && !item.def.IsMedicine && (r.Mode != "trade" || item.def.defName != "Silver" && !CaravanAutomationHelper.IsSaleGood(item, r.SaleCategories)))
                        throw new InvalidOperationException("Selected cargo is not allowed by chosen expedition policy");
                    Add(supplies, item, selected.Count);
                }
            } else {
                float needed = daily * days;
                foreach (var food in items.Where(t => Suitable(t, travelers, days)).OrderByDescending(t => t.GetStatValue(StatDefOf.Nutrition)).ThenBy(t => t.thingIDNumber)) {
                    float per = food.GetStatValue(StatDefOf.Nutrition);
                    if (per <= 0 || Nutrition(supplies) >= needed) continue;
                    int count = Math.Min(food.stackCount, Math.Min((int)Math.Ceiling((needed - Nutrition(supplies)) / per), totalFoodItems - r.MinimumFoodAtHome - Count(supplies, TravelFood)));
                    Add(supplies, food, count);
                }
                int desiredMedicine = travelers.Count * (r.Mode == "trade" ? 2 : 3);
                foreach (var medicine in items.Where(t => t.def.IsMedicine).OrderBy(t => t.MarketValue).ThenBy(t => t.thingIDNumber))
                    Add(supplies, medicine, Math.Min(medicine.stackCount, Math.Min(desiredMedicine - Count(supplies, t => t.def.IsMedicine), totalMedicine - r.MinimumMedicineAtHome - Count(supplies, t => t.def.IsMedicine))));
                if (r.Mode == "trade") {
                    float goodsValue = prisoners.Sum(p => p.MarketValue);
                    float packedMass = travelers.Sum(p => MassUtility.GearAndInventoryMass(p)) + supplies.Sum(t => t.AnyThing.GetStatValue(StatDefOf.Mass) * t.CountToTransfer);
                    if ((r.PurchasePriorities?.Count ?? 0) > 0) {
                        int silver = items.Where(t => t.def.defName == "Silver").Sum(t => t.stackCount);
                        foreach (var money in items.Where(t => t.def.defName == "Silver")) {
                            int count = Math.Min(money.stackCount, Math.Min(Math.Min(3000, Math.Max(0, silver - 200)) - Count(supplies, t => t.def.defName == "Silver"),
                                (int)Math.Floor(Math.Max(0, capacity - packedMass) / Math.Max(.001f, money.GetStatValue(StatDefOf.Mass)))));
                            Add(supplies, money, count); packedMass += money.GetStatValue(StatDefOf.Mass) * Math.Max(0, count);
                        }
                    }
                    foreach (var good in items.Where(t => !TravelFood(t) && t.def.defName != "Silver" && !supplies.Any(v => v.AnyThing == t) && CaravanAutomationHelper.IsSaleGood(t, r.SaleCategories)).OrderByDescending(t => t.MarketValue / Math.Max(.05f, t.GetStatValue(StatDefOf.Mass))).ThenBy(t => t.thingIDNumber)) {
                        if (goodsValue >= 2500) break;
                        int count = Math.Min(good.stackCount, (int)Math.Floor(Math.Max(0, capacity - packedMass) / Math.Max(.001f, good.GetStatValue(StatDefOf.Mass))));
                        Add(supplies, good, count); goodsValue += good.MarketValue * Math.Max(0, count); packedMass += good.GetStatValue(StatDefOf.Mass) * Math.Max(0, count);
                    }
                }
            }
            float nutrition = Nutrition(supplies);
            float nativeDays = DaysWorthOfFoodCalculator.ApproxDaysWorthOfFood(travelers, supplies.Where(t => TravelFood(t.AnyThing)).Select(t => new ThingCount(t.AnyThing, t.CountToTransfer)).ToList(), map.Tile, IgnorePawnsInventoryMode.Ignore, Faction.OfPlayer);
            facts["packed_food_nutrition"] = nutrition; facts["packed_food_days"] = nativeDays;
            facts["food_margin_days"] = nativeDays - outward - back;
            if (nutrition < daily * days || nativeDays < days) throw new InvalidOperationException("Insufficient diet-compatible travel nutrition for both legs and chosen margin");
            int homeFoodItems = totalFoodItems - Count(supplies, TravelFood);
            int homeMedicine = totalMedicine - Count(supplies, t => t.def.IsMedicine);
            if (homeFoodItems < r.MinimumFoodAtHome || homeMedicine < r.MinimumMedicineAtHome || Count(supplies, t => t.def.IsMedicine) < travelers.Count)
                throw new InvalidOperationException("Food/medicine cargo violates explicit home item reserves or traveler medicine minimum");
            float gear = travelers.Sum(p => MassUtility.GearAndInventoryMass(p));
            float mass = gear + supplies.Sum(t => t.AnyThing.GetStatValue(StatDefOf.Mass) * t.CountToTransfer);
            facts["mass"] = mass;
            if (r.Mode == "trade" && items.Where(t => t.def.defName == "Silver").Sum(t => t.stackCount) - Count(supplies, t => t.def.defName == "Silver") < 200 && Count(supplies, t => t.def.defName == "Silver") > 0)
                throw new InvalidOperationException("Selected purchase funds violate the existing 200 silver home reserve");
            if (mass > capacity) throw new InvalidOperationException("Carried gear/inventory and selected cargo exceed native capacity");
            if (r.Mode == "trade" && prisoners.Sum(p => p.MarketValue) + supplies.Where(t => !TravelFood(t.AnyThing) && !t.AnyThing.def.IsMedicine && t.AnyThing.def.defName != "Silver").Sum(t => t.AnyThing.MarketValue * t.CountToTransfer) < 250 && Count(supplies, t => t.def.defName == "Silver") < 800)
                throw new InvalidOperationException("Trade needs 250 silver of selected goods/prisoners or 800 silver purchase funds");
            var manifest = supplies.Select(t => new ExpeditionManifestItem { ThingId = t.AnyThing.thingIDNumber, DefName = t.AnyThing.def.defName, Count = t.CountToTransfer }).OrderBy(v => v.ThingId).ToList();
            var remainingFood = items.Where(TravelFood).Select(t => new { Thing = t, Count = t.stackCount - (manifest.FirstOrDefault(v => v.ThingId == t.thingIDNumber)?.Count ?? 0) }).Where(v => v.Count > 0).ToList();
            // Explicit conversion: minimum legacy item reserve at actual remaining stack nutrition.
            float reserveNutrition = 0; int reserveItems = r.MinimumFoodAtHome;
            foreach (var row in remainingFood.OrderBy(v => v.Thing.GetStatValue(StatDefOf.Nutrition))) {
                int count = Math.Min(row.Count, reserveItems); reserveNutrition += count * row.Thing.GetStatValue(StatDefOf.Nutrition); reserveItems -= count;
            }
            string gearIdentity = string.Join(";", travelers.Select(p => p.thingIDNumber + ":" + string.Join(",", (p.inventory?.innerContainer?.ToList() ?? new List<Thing>()).Concat(p.equipment?.AllEquipmentListForReading ?? new List<ThingWithComps>()).Concat(p.apparel?.WornApparel ?? new List<Apparel>()).OrderBy(t => t.thingIDNumber).Select(t => t.thingIDNumber + ":" + t.stackCount))));
            string essentials = Hash(Selection(r) + "|" + string.Join(",", team.Select(p => p.thingIDNumber)) + "|" + string.Join(",", home.Select(p => p.thingIDNumber)) + "|" +
                string.Join(",", manifest.Select(v => v.ThingId + ":" + v.DefName + ":" + v.Count)) + "|" + gearIdentity + "|" +
                string.Join(",", travelers.Select(p => p.thingIDNumber + ":" + Math.Round(Daily(p), 2).ToString(System.Globalization.CultureInfo.InvariantCulture))) + "|" + target.Faction?.PlayerRelationKind + "|" + target.Faction?.PlayerGoodwill + "|" + (target is Site threatSite ? Math.Round(threatSite.ActualThreatPoints / 25f) : 0));
            var dto = new ExpeditionPlanDto {
                PlanId = string.Join(",", team.Select(p => p.thingIDNumber)), Essentials = essentials, Mode = r.Mode, MapId = map.uniqueID, TargetId = target.ID, QuestId = r.QuestId,
                PawnIds = team.Select(p => p.thingIDNumber).ToList(), HomePawnIds = home.Select(p => p.thingIDNumber).ToList(), Manifest = manifest,
                Travelers = team.Select(p => p.LabelShortCap.ToString()).ToList(), Prisoners = prisoners.Select(p => p.LabelShortCap.ToString()).ToList(),
                Diets = travelers.Select(p => (object)new { pawn_id = p.thingIDNumber, name = p.LabelShortCap.ToString(), prisoner = p.IsPrisonerOfColony, daily_nutrition = Daily(p),
                    policy = p.foodRestriction?.CurrentFoodPolicy?.label, acceptable_rations = items.Where(t => Suitable(t, new List<Pawn> { p }, days)).Select(t => t.def.defName).Distinct().ToList() }).ToList(),
                DestinationName = target.LabelCap.ToString(), FoodNutrition = nutrition, DailyNutrition = daily, FoodDays = nativeDays,
                OutboundDays = outward, ReturnDays = back, MarginDays = r.MarginDays, FoodMarginDays = nativeDays - outward - back,
                HomeFoodItems = homeFoodItems, MinimumHomeFoodItems = r.MinimumFoodAtHome, HomeFoodNutrition = remainingFood.Sum(v => v.Count * v.Thing.GetStatValue(StatDefOf.Nutrition)),
                MinimumHomeFoodNutrition = reserveNutrition, HomeMedicine = homeMedicine, HomeDefenders = defenders, Mass = mass, Capacity = capacity, CarriedGearMass = gear,
                EstimateReason = "Native surface path/rest/season estimator at full capacity, return starts at projected outbound arrival; formation and encounter time excluded",
                Consequences = r.Mode == "raid" ? "Attacks settlement; war accepted=" + r.AllowStartingWar : r.Mode == "rescue" ? "Visits disclosed quest site; combat/captives not guaranteed; return requires a fresh decision" : "Travel to settlement opens normal trade choice; selected prisoners may be sold only by a later confirmed transaction"
            };
            return new Plan { Dto = dto, Map = map, Target = target, Pawns = travelers, Supplies = supplies };
        }
        private static object RouteView(ExpeditionRoute route) => new {
            formation_id = route.FormationId, status = route.Status, reason = route.Reason,
            origin_map_id = route.OriginMapId, target_id = route.ObjectId, mode = route.Mode,
            pawn_ids = route.PawnIds, native_formation_active = Find.Maps.FirstOrDefault(m => m.uniqueID == route.OriginMapId)?.lordManager.lords.Any(l => l.loadID == route.NativeLordId) ?? false
        };
        public static ApiResult<ExpeditionPreviewDto> Preview(ExpeditionRequestDto request) {
            var result = new ExpeditionPreviewDto();
            var state = Current.Game?.GetComponent<ExpeditionRouteState>();
            result.Pending = state?.Routes.Take(4).Select(RouteView).ToList(); result.LastResult = state?.LastResult == null ? null : RouteView(state.LastResult);
            try { result.Plans.Add(Build(request, result.Readiness).Dto); }
            catch (Exception ex) { result.Blockers.Add(ex.Message); }
            return ApiResult<ExpeditionPreviewDto>.Ok(result);
        }
        public static ApiResult<StartTradeCaravanResponseDto> Start(ExpeditionRequestDto r) {
            try {
                if (!r.Confirmed || r.PawnIds == null || r.HomePawnIds == null || r.Manifest == null || string.IsNullOrEmpty(r.Essentials))
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("Explicit confirmation and exact preview roster/manifest are required");
                var state = Current.Game.GetComponent<ExpeditionRouteState>(); state.ValidateRoutes();
                var pending = state.Routes.FirstOrDefault(v => v.Essentials == r.Essentials && v.Policy == Selection(r));
                if (pending != null) return ApiResult<StartTradeCaravanResponseDto>.Ok(new StartTradeCaravanResponseDto { Applied = true, Status = "already_forming", FormationId = pending.FormationId });
                var plan = Build(r);
                if (plan.Dto.Essentials != r.Essentials) return ApiResult<StartTradeCaravanResponseDto>.Fail("Selected expedition essentials changed; preview and decide again");
                PlanetTile exitTile = CaravanExitMapUtility.BestExitTileToGoTo(plan.Target.Tile, plan.Map);
                IntVec3 root = plan.Pawns.Aggregate(IntVec3.Zero, (sum, p) => sum + p.Position) / plan.Pawns.Count;
                if (!RCellFinder.TryFindClosestEdgeCellTo(root, plan.Map, out IntVec3 exitSpot)) return ApiResult<StartTradeCaravanResponseDto>.Fail("No reachable native caravan exit");
                if (!RCellFinder.TryFindRandomSpotJustOutsideColony(exitSpot, plan.Map, out IntVec3 meeting)) meeting = root;
                CaravanFormingUtility.StartFormingCaravan(plan.Pawns, new List<Pawn>(), Faction.OfPlayer, plan.Supplies, meeting, exitSpot, exitTile, plan.Target.Tile);
                var lord = plan.Pawns.Select(p => p.GetLord()).Distinct().SingleOrDefault();
                if (lord == null || !(lord.LordJob is LordJob_FormAndSendCaravan)) return ApiResult<StartTradeCaravanResponseDto>.Fail("Native formation was not observed; observe before retry");
                var route = new ExpeditionRoute { OriginMapId = plan.Map.uniqueID, ObjectId = plan.Target.ID, Mode = r.Mode, QuestId = r.QuestId,
                    PawnIds = plan.Pawns.Select(p => p.thingIDNumber).OrderBy(v => v).ToList(), FormingLord = lord, NativeLordId = lord.loadID, FormationId = Guid.NewGuid().ToString("N"), Essentials = r.Essentials, Policy = Selection(r) };
                state.Routes.Add(route);
                return ApiResult<StartTradeCaravanResponseDto>.Ok(new StartTradeCaravanResponseDto { Applied = true, Status = "forming", FormationId = route.FormationId,
                    DestinationSettlementId = plan.Target.ID, DestinationName = plan.Target.LabelCap, DestinationTile = plan.Target.Tile, PawnCount = plan.Pawns.Count,
                    FoodCount = Count(plan.Supplies, TravelFood), PrisonerCount = plan.Pawns.Count(p => p.IsPrisonerOfColony), PurchasePriorities = r.PurchasePriorities ?? new List<string>() });
            } catch (Exception ex) { return ApiResult<StartTradeCaravanResponseDto>.Fail(ex.Message); }
        }
    }
}

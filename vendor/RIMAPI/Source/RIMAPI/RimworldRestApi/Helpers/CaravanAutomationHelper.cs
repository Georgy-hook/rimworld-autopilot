using System;
using System.Collections.Generic;
using System.Linq;
using RIMAPI.Core;
using RIMAPI.Models;
using RimWorld;
using RimWorld.Planet;
using UnityEngine;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class CaravanAutomationHelper
    {
        internal static bool IsReadyDefender(Pawn pawn)
        {
            if (pawn == null || pawn.Downed || pawn.InMentalState
                || pawn.health.summaryHealth.SummaryHealthPercent < 0.80f
                || pawn.equipment?.Primary == null)
                return false;
            var shooting = pawn.skills?.GetSkill(SkillDefOf.Shooting);
            var melee = pawn.skills?.GetSkill(SkillDefOf.Melee);
            return (shooting != null && !shooting.TotallyDisabled)
                || (melee != null && !melee.TotallyDisabled);
        }

        public static void ProcessPendingRoutes() => Current.Game?.GetComponent<ExpeditionRouteState>()?.ValidateRoutes();

        public static ApiResult<List<TradeDestinationDto>> GetTradeDestinations(int mapId)
        {
            try
            {
                Map map = MapHelper.GetMapByID(mapId);
                if (map == null)
                    return ApiResult<List<TradeDestinationDto>>.Fail($"Map {mapId} not found.");
                var result = Find.WorldObjects.Settlements
                    .Where(s => s.Faction != null && s.Faction != Faction.OfPlayer && !s.Faction.def.permanentEnemy)
                    .Select(s => new TradeDestinationDto
                    {
                        SettlementId = s.ID,
                        Name = s.LabelCap,
                        Tile = s.Tile,
                        FactionName = s.Faction.Name,
                        FactionDef = s.Faction.def.defName,
                        Relation = s.Faction.PlayerRelationKind.ToString(),
                        Goodwill = s.Faction.PlayerGoodwill,
                        ApproximateDistanceTiles = Find.WorldGrid.ApproxDistanceInTiles(map.Tile, s.Tile),
                        CanTradeNow = !s.Faction.HostileTo(Faction.OfPlayer) && s.Visitable && s.CanTradeNow,
                        EverVisited = s.EverVisited,
                        StockKnowledgeMayBeStale = s.EverVisited && s.RestockedSinceLastVisit,
                        TraderKind = s.TraderKind?.defName,
                        WillBuyHumanlikePrisoners = s.TraderKind != null
                            && DefDatabase<ThingDef>.GetNamedSilentFail("Human") is ThingDef human
                            && s.TraderKind.WillTrade(human),
                        KnownStock = s.EverVisited
                            ? s.Goods.Where(t => !(t is Pawn)).Take(80).Select(t => new KnownTradeItemDto
                            {
                                DefName = t.def.defName,
                                Label = t.LabelCap,
                                Count = t.stackCount,
                                MarketValue = t.MarketValue,
                                EstimatedBuyPrice = t.MarketValue * 1.4f,
                                EstimatedSellPrice = t.MarketValue * 0.6f
                            }).ToList()
                            : null
                    })
                    .OrderBy(s => s.ApproximateDistanceTiles)
                    .ToList();
                return ApiResult<List<TradeDestinationDto>>.Ok(result);
            }
            catch (Exception ex)
            {
                return ApiResult<List<TradeDestinationDto>>.Fail(ex.Message);
            }
        }

        public static ApiResult<StartTradeCaravanResponseDto> StartTradeCaravan(StartTradeCaravanRequestDto request) {
            request.Mode = "trade";
            return ExpeditionPlanHelper.Start(request);
        }

        public static ApiResult<List<RaidDestinationDto>> GetRaidDestinations(int mapId)
        {
            try
            {
                Map map = MapHelper.GetMapByID(mapId);
                if (map == null) return ApiResult<List<RaidDestinationDto>>.Fail($"Map {mapId} not found.");
                float threatPoints = Math.Max(500f, StorytellerUtility.DefaultThreatPointsNow(map) * 1.5f);
                var results = new List<RaidDestinationDto>();
                foreach (Settlement settlement in Find.WorldObjects.Settlements.Where(s => s.Faction != null && s.Faction != Faction.OfPlayer && s.Attackable))
                {
                    var options = (settlement.Faction.def.pawnGroupMakers ?? new List<PawnGroupMaker>())
                        .Where(m => m.kindDef == PawnGroupKindDefOf.Combat)
                        .SelectMany(m => m.options ?? new List<PawnGenOption>())
                        .Where(o => o.kind != null)
                        .ToList();
                    float avgPower = options.Count == 0 ? 80f : options.Average(o => Math.Max(20f, o.kind.combatPower));
                    int defenders = Mathf.Clamp(Mathf.RoundToInt(threatPoints / avgPower), 3, 30);
                    var kinds = options.OrderByDescending(o => o.selectionWeight).Select(o => o.kind).Distinct().Take(8).ToList();
                    string tech = settlement.Faction.def.techLevel.ToString();
                    var loot = new List<string> { "silver", "food", "medicine", "weapons" };
                    if (settlement.Faction.def.techLevel >= TechLevel.Industrial)
                        loot.AddRange(new[] { "components", "industrial armor" });
                    else
                        loot.AddRange(new[] { "animals", "leather", "herbal medicine" });
                    results.Add(new RaidDestinationDto
                    {
                        SettlementId = settlement.ID,
                        Name = settlement.LabelCap,
                        Tile = settlement.Tile,
                        FactionName = settlement.Faction.Name,
                        Relation = settlement.Faction.PlayerRelationKind.ToString(),
                        Goodwill = settlement.Faction.PlayerGoodwill,
                        TechLevel = tech,
                        ApproximateDistanceTiles = Find.WorldGrid.ApproxDistanceInTiles(map.Tile, settlement.Tile),
                        EstimatedDefendersMin = Math.Max(2, Mathf.RoundToInt(defenders * 0.7f)),
                        EstimatedDefendersMax = Mathf.RoundToInt(defenders * 1.4f),
                        LikelyPawnKinds = kinds.Select(k => k.label ?? k.defName).ToList(),
                        LikelyWeaponTags = kinds.SelectMany(k => k.weaponTags ?? new List<string>()).Distinct().Take(12).ToList(),
                        LikelyApparelTags = kinds.SelectMany(k => k.apparelTags ?? new List<string>()).Distinct().Take(12).ToList(),
                        PossibleLoot = loot.Distinct().ToList(),
                        EstimatedLootValue = Mathf.Round(threatPoints * (settlement.Faction.def.techLevel >= TechLevel.Industrial ? 1.5f : 1.0f)),
                        WouldStartWar = !settlement.Faction.HostileTo(Faction.OfPlayer)
                    });
                }
                return ApiResult<List<RaidDestinationDto>>.Ok(results.OrderBy(r => r.ApproximateDistanceTiles).ToList());
            }
            catch (Exception ex)
            {
                return ApiResult<List<RaidDestinationDto>>.Fail(ex.Message);
            }
        }

        public static ApiResult<StartTradeCaravanResponseDto> StartRaidCaravan(StartRaidCaravanRequestDto request) {
            request.Mode = "raid";
            return ExpeditionPlanHelper.Start(request);
        }

        public static ApiResult<StartTradeCaravanResponseDto> StartRescueMission(RescueMissionRequestDto request) {
            request.Mode = "rescue";
            return ExpeditionPlanHelper.Start(request);
        }

        public static ApiResult<RescueSiteStatusDto> GetRescueSiteStatus(int mapId)
        {
            try
            {
                Map map = MapHelper.GetMapByID(mapId);
                if (map == null) return ApiResult<RescueSiteStatusDto>.Fail($"Map {mapId} not found.");
                List<Pawn> captives = RescueCaptives(map);
                bool threat = GenHostility.AnyHostileActiveThreatToPlayer(map);
                return ApiResult<RescueSiteStatusDto>.Ok(new RescueSiteStatusDto
                {
                    MapId = map.uniqueID,
                    SiteId = map.Parent?.ID,
                    IsTemporaryMap = map.IsTempIncidentMap,
                    ActiveThreat = threat,
                    RescuerPawnIds = map.mapPawns.FreeColonistsSpawned.Select(p => p.thingIDNumber).ToList(),
                    CaptivePawnIds = captives.Select(p => p.thingIDNumber).ToList(),
                    CaptiveNames = captives.Select(p => p.Name?.ToStringShort ?? p.LabelShortCap).ToList(),
                    CanReturnHome = map.IsTempIncidentMap && !threat && captives.Count == 0
                        && map.mapPawns.FreeColonistsSpawned.Any(),
                });
            }
            catch (Exception ex)
            {
                return ApiResult<RescueSiteStatusDto>.Fail(ex.Message);
            }
        }

        public static ApiResult SecureRescueSite(RescueSiteRequestDto request)
        {
            try
            {
                Map map = MapHelper.GetMapByID(request.MapId);
                if (map == null) return ApiResult.Fail($"Map {request.MapId} not found.");
                if (GenHostility.AnyHostileActiveThreatToPlayer(map))
                    return ApiResult.Fail("The rescue site still has an active threat.");
                var pair = (from worker in map.mapPawns.FreeColonistsSpawned
                            where !worker.Dead && !worker.Downed && !worker.InMentalState && !worker.Drafted
                                && !CombatNativeHelper.HasCareJob(worker) && worker.CurJobDef != JobDefOf.Ingest
                            from target in RescueCaptives(map)
                            where worker.CanReserveAndReach(target, PathEndMode.Touch, Danger.Some)
                            orderby worker.skills?.GetSkill(SkillDefOf.Social)?.Level ?? 0 descending
                            select new { worker, target }).FirstOrDefault();
                Pawn rescuer = pair?.worker;
                Pawn captive = pair?.target;
                if (rescuer == null || captive == null)
                    return ApiResult.Fail("No reachable rescuer/captive pair is available.");
                Job job = JobMaker.MakeJob(JobDefOf.ReleasePrisoner, captive);
                job.playerForced = true;
                if (!rescuer.jobs.TryTakeOrderedJob(job))
                    return ApiResult.Fail("The rescuer could not accept the normal Release Prisoner job.");
                Messages.Message("Laya: freeing " + captive.LabelShortCap + " at the cleared rescue site.", captive, MessageTypeDefOf.PositiveEvent, false);
                return ApiResult.Ok();
            }
            catch (Exception ex)
            {
                return ApiResult.Fail(ex.Message);
            }
        }

        public static ApiResult<StartTradeCaravanResponseDto> ReturnRescueTeamHome(RescueSiteRequestDto request)
        {
            try
            {
                Map map = MapHelper.GetMapByID(request.MapId);
                if (map == null || !map.IsTempIncidentMap)
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("The selected map is not a temporary rescue site.");
                if (GenHostility.AnyHostileActiveThreatToPlayer(map) || RescueCaptives(map).Count > 0)
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("The team cannot leave before threats are cleared and captives are freed.");
                Map home = Find.Maps.FirstOrDefault(m => m.IsPlayerHome && m != map);
                if (home == null)
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("No player home settlement exists for the return route.");
                List<Pawn> pawns = map.mapPawns.AllPawnsSpawned
                    .Where(p => p != null && !p.Dead && p.Faction == Faction.OfPlayer)
                    .ToList();
                if (!pawns.Any(p => p.RaceProps?.Humanlike == true))
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("No player-controlled rescuer remains on the site.");
                Caravan caravan = CaravanExitMapUtility.ExitMapAndCreateCaravan(
                    pawns, Faction.OfPlayer, map.Tile, Direction8Way.North, home.Tile, true);
                caravan.pather.StartPath(home.Tile, new CaravanArrivalAction_Enter(home.Parent), true);
                return ApiResult<StartTradeCaravanResponseDto>.Ok(new StartTradeCaravanResponseDto
                {
                    Applied = true,
                    Status = "returning from rescue site",
                    DestinationSettlementId = home.Parent.ID,
                    DestinationName = home.Parent.LabelCap,
                    DestinationTile = home.Tile,
                    PawnCount = pawns.Count(p => p.RaceProps?.Humanlike == true),
                });
            }
            catch (Exception ex)
            {
                LogApi.Error($"Rescue return automation failed: {ex}");
                return ApiResult<StartTradeCaravanResponseDto>.Fail(ex.Message);
            }
        }

        private static List<Pawn> RescueCaptives(Map map)
        {
            return map.mapPawns.AllPawnsSpawned.Where(p => p != null && !p.Dead
                && p.RaceProps?.Humanlike == true && p.guest?.IsPrisoner == true
                && !p.IsPrisonerOfColony && !p.HostileTo(Faction.OfPlayer)).ToList();
        }

        private static int AddByPredicate(List<TransferableOneWay> result, List<Thing> source, Func<Thing, bool> predicate, int wanted)
        {
            int added = 0;
            foreach (Thing thing in source.Where(predicate).OrderByDescending(t => t.stackCount))
            {
                int count = Math.Min(thing.stackCount, wanted - added);
                if (count <= 0) break;
                AddTransferable(result, thing, count);
                added += count;
            }
            return added;
        }

        private static void AddTransferable(List<TransferableOneWay> result, Thing thing, int count)
        {
            var transferable = new TransferableOneWay();
            transferable.things.Add(thing);
            transferable.AdjustTo(count);
            result.Add(transferable);
        }

        private static bool IsTravelFood(Thing thing)
        {
            return !thing.IsForbidden(Faction.OfPlayer) && (thing.def.defName == "MealSurvivalPack" || thing.def.defName == "Pemmican");
        }

        private static bool IsMedicine(Thing thing)
        {
            return !thing.IsForbidden(Faction.OfPlayer) && thing.def.thingCategories != null
                && thing.def.thingCategories.Any(c => c.defName == "Medicine");
        }

        internal static bool IsSaleGood(Thing thing, List<string> requested)
        {
            if (thing.IsForbidden(Faction.OfPlayer) || thing.MarketValue <= 5f || IsMedicine(thing))
                return false;
            string name = thing.def.defName;
            IEnumerable<string> selectedCategories = requested == null || requested.Count == 0
                ? (IEnumerable<string>)new[] { "drugs", "apparel", "art", "animal_products", "chemfuel", "precious", "beer", "travel_food", "raw_food" }
                : requested;
            var categories = new HashSet<string>(selectedCategories, StringComparer.OrdinalIgnoreCase);
            bool drugs = name == "Flake" || name == "Yayo" || name == "SmokeleafJoint";
            bool apparel = thing.def.thingCategories != null && thing.def.thingCategories.Any(c => c.defName.Contains("Apparel"));
            bool art = name.Contains("Sculpture");
            bool animal = name.Contains("Wool") || name.Contains("Leather") || name.Contains("Milk");
            bool fuel = name == "Chemfuel";
            bool precious = name == "Gold" || name == "Jade";
            bool beer = name == "Beer";
            bool caravanFood = name == "MealSurvivalPack" || name == "Pemmican";
            bool rawFood = name == "RawCorn" || name == "RawRice" || name == "RawPotatoes" || name == "AgaveFruit" || name == "Berries";
            return (categories.Contains("drugs") && drugs)
                || (categories.Contains("apparel") && apparel)
                || (categories.Contains("art") && art)
                || (categories.Contains("animal_products") && animal)
                || (categories.Contains("chemfuel") && fuel)
                || (categories.Contains("precious") && precious)
                || (categories.Contains("beer") && beer)
                || (categories.Contains("travel_food") && caravanFood)
                || (categories.Contains("raw_food") && rawFood);
        }
    }
}

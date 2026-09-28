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
        private class PendingRoute
        {
            public HashSet<int> PawnIds;
            public int SettlementId;
            public int? SiteId;
            public bool Raid;
        }

        private static readonly List<PendingRoute> PendingRoutes = new List<PendingRoute>();

        private static bool IsReadyDefender(Pawn pawn)
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

        public static void ProcessPendingRoutes()
        {
            if (Current.Game == null || Find.WorldObjects == null) return;
            for (int i = PendingRoutes.Count - 1; i >= 0; i--)
            {
                PendingRoute pending = PendingRoutes[i];
                Caravan caravan = Find.WorldObjects.Caravans.FirstOrDefault(c => c.Faction == Faction.OfPlayer
                    && c.PawnsListForReading.Any(p => pending.PawnIds.Contains(p.thingIDNumber)));
                Settlement settlement = Find.WorldObjects.Settlements.FirstOrDefault(s => s.ID == pending.SettlementId);
                Site site = pending.SiteId.HasValue
                    ? Find.WorldObjects.AllWorldObjects.OfType<Site>().FirstOrDefault(s => s.ID == pending.SiteId.Value)
                    : null;
                if (caravan == null) continue;
                if (site != null)
                {
                    caravan.pather.StartPath(site.Tile, new CaravanArrivalAction_VisitSite(site), true);
                    PendingRoutes.RemoveAt(i);
                    continue;
                }
                if (settlement == null) continue;
                CaravanArrivalAction arrival = pending.Raid
                    ? (CaravanArrivalAction)new CaravanArrivalAction_AttackSettlement(settlement)
                    : new CaravanArrivalAction_Trade(settlement);
                caravan.pather.StartPath(settlement.Tile, arrival, true);
                // Leave the normal trade session open. The director must see
                // its actual recruits and stock before deciding whether to
                // sell a prisoner, purchase a person, or leave. Auto-selling
                // here closed the window before that decision was possible.
                PendingRoutes.RemoveAt(i);
            }
        }

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

        public static ApiResult<StartTradeCaravanResponseDto> StartTradeCaravan(StartTradeCaravanRequestDto request)
        {
            try
            {
                Map map = MapHelper.GetMapByID(request.MapId);
                if (map == null)
                    return ApiResult<StartTradeCaravanResponseDto>.Fail($"Map {request.MapId} not found.");
                if (GenHostility.AnyHostileActiveThreatToPlayer(map))
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("A trade caravan cannot leave during an active threat.");
                if (Find.WorldObjects.Caravans.Any(c => c.Faction == Faction.OfPlayer))
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("A player caravan is already active.");

                var healthy = map.mapPawns.FreeColonistsSpawned
                    .Where(p => !p.Downed && !p.InMentalState && p.health.summaryHealth.SummaryHealthPercent >= 0.80f)
                    .ToList();
                var fighters = healthy.Where(IsReadyDefender).ToList();
                int available = fighters.Count - Math.Max(2, request.MinimumHomeDefenders);
                if (available <= 0)
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("Not enough healthy, armed fighters to keep the requested defenders at home.");

                var destination = Find.WorldObjects.Settlements.FirstOrDefault(s => s.ID == request.DestinationSettlementId);
                if (destination == null)
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("The selected settlement does not exist.");
                if (destination.Faction == null || destination.Faction == Faction.OfPlayer
                    || destination.Faction.HostileTo(Faction.OfPlayer) || destination.Faction.def.permanentEnemy
                    || !destination.Visitable || !destination.CanTradeNow)
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("The selected settlement is not currently a safe trading destination.");

                var pawns = fighters
                    .OrderByDescending(p => p.skills.GetSkill(SkillDefOf.Social).Level * 3 + p.skills.GetSkill(SkillDefOf.Shooting).Level)
                    .Take(Math.Min(2, available))
                    .ToList();
                if (pawns.Count == 0)
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("No safe caravan negotiator is available.");
                var requestedPrisoners = new HashSet<int>(request.PrisonerIds ?? new List<int>());
                var salePrisoners = map.mapPawns.PrisonersOfColony
                    .Where(p => requestedPrisoners.Contains(p.thingIDNumber) && !p.Dead && !p.Downed
                        && p.health.summaryHealth.SummaryHealthPercent >= 0.70f)
                    .ToList();
                if (salePrisoners.Count > 0 && salePrisoners.Any(p => !destination.TraderKind.WillTrade(p.def)))
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("The selected settlement does not buy humanlike prisoners.");

                List<Thing> items = CaravanFormingUtility.AllReachableColonyItems(map);
                int totalFood = items.Where(IsTravelFood).Sum(t => t.stackCount);
                int totalMedicine = items.Where(IsMedicine).Sum(t => t.stackCount);
                int totalSilver = items.Where(t => t.def.defName == "Silver" && !t.IsForbidden(Faction.OfPlayer))
                    .Sum(t => t.stackCount);
                int takeFood = Math.Min(Math.Max(8, pawns.Count * 10), Math.Max(0, totalFood - request.MinimumFoodAtHome));
                int takeMedicine = Math.Min(pawns.Count * 2, Math.Max(0, totalMedicine - request.MinimumMedicineAtHome));
                if (takeFood < Math.Max(6, pawns.Count * 6))
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("Not enough shelf-stable travel food while preserving the home reserve.");

                var transferables = new List<TransferableOneWay>();
                int foodAdded = AddByPredicate(transferables, items, IsTravelFood, takeFood);
                AddByPredicate(transferables, items, IsMedicine, takeMedicine);
                int silverAdded = (request.PurchasePriorities?.Count ?? 0) > 0
                    ? AddByPredicate(transferables, items,
                        t => t.def.defName == "Silver" && !t.IsForbidden(Faction.OfPlayer),
                        Math.Min(3000, Math.Max(0, totalSilver - 200))) : 0;
                var reservedTravelStacks = new HashSet<Thing>(transferables.SelectMany(t => t.things));

                float goodsValue = salePrisoners.Sum(p => p.MarketValue);
                float goodsMass = 0f;
                int goodsStacks = 0;
                float massLimit = Math.Max(20f, pawns.Count * 28f);
                foreach (Thing thing in items.Where(t => !reservedTravelStacks.Contains(t) && IsSaleGood(t, request.SaleCategories)).OrderByDescending(t => t.MarketValue / Math.Max(0.05f, t.GetStatValue(StatDefOf.Mass))))
                {
                    if (goodsValue >= 2500f || goodsMass >= massLimit)
                        break;
                    float unitMass = Math.Max(0.01f, thing.GetStatValue(StatDefOf.Mass));
                    int count = Math.Min(thing.stackCount, Math.Max(0, Mathf.FloorToInt((massLimit - goodsMass) / unitMass)));
                    if (count <= 0)
                        continue;
                    AddTransferable(transferables, thing, count);
                    goodsMass += unitMass * count;
                    goodsValue += thing.MarketValue * count;
                    goodsStacks++;
                }
                if (goodsValue < 250f && silverAdded < 800)
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("A caravan needs at least 250 silver of safe surplus goods or 800 silver for purchases.");

                PlanetTile startingTile = CaravanExitMapUtility.BestExitTileToGoTo(destination.Tile, map);
                if (!startingTile.Valid)
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("No valid map exit toward the destination was found.");
                IntVec3 root = pawns.Aggregate(IntVec3.Zero, (sum, pawn) => sum + pawn.Position) / pawns.Count;
                if (!RCellFinder.TryFindClosestEdgeCellTo(root, map, out IntVec3 exitSpot))
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("No reachable caravan exit spot was found.");
                if (!RCellFinder.TryFindRandomSpotJustOutsideColony(exitSpot, map, out IntVec3 meetingPoint))
                    meetingPoint = root;

                var caravanPawns = pawns.Concat(salePrisoners).ToList();
                CaravanFormingUtility.StartFormingCaravan(
                    caravanPawns, new List<Pawn>(), Faction.OfPlayer, transferables,
                    meetingPoint, exitSpot, startingTile, destination.Tile);
                PendingRoutes.Add(new PendingRoute
                {
                    PawnIds = new HashSet<int>(caravanPawns.Select(p => p.thingIDNumber)),
                    SettlementId = destination.ID,
                    Raid = false
                });
                Messages.Message("Laya: trade caravan is gathering supplies for " + destination.LabelCap + ".", pawns[0], MessageTypeDefOf.PositiveEvent, false);
                return ApiResult<StartTradeCaravanResponseDto>.Ok(new StartTradeCaravanResponseDto
                {
                    Status = "forming",
                    DestinationSettlementId = destination.ID,
                    DestinationName = destination.LabelCap,
                    DestinationTile = destination.Tile,
                    PawnCount = pawns.Count,
                    GoodsStacks = goodsStacks,
                    FoodCount = foodAdded,
                    ApproximateGoodsValue = goodsValue,
                    PrisonerCount = salePrisoners.Count,
                    PurchasePriorities = request.PurchasePriorities ?? new List<string>()
                });
            }
            catch (Exception ex)
            {
                LogApi.Error($"Trade caravan automation failed: {ex}");
                return ApiResult<StartTradeCaravanResponseDto>.Fail(ex.Message);
            }
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

        public static ApiResult<StartTradeCaravanResponseDto> StartRaidCaravan(StartRaidCaravanRequestDto request)
        {
            try
            {
                Map map = MapHelper.GetMapByID(request.MapId);
                if (map == null) return ApiResult<StartTradeCaravanResponseDto>.Fail($"Map {request.MapId} not found.");
                if (GenHostility.AnyHostileActiveThreatToPlayer(map))
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("A raid expedition cannot leave during an active threat.");
                Settlement destination = Find.WorldObjects.Settlements.FirstOrDefault(s => s.ID == request.DestinationSettlementId);
                if (destination == null || !destination.Attackable)
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("The selected raid target is unavailable.");
                if (!destination.Faction.HostileTo(Faction.OfPlayer) && !request.AllowStartingWar)
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("This target is not hostile and the plan did not explicitly accept starting a war.");
                var healthy = map.mapPawns.FreeColonistsSpawned
                    .Where(p => IsReadyDefender(p) && p.health.summaryHealth.SummaryHealthPercent >= 0.85f)
                    .OrderByDescending(p => p.skills.GetSkill(SkillDefOf.Shooting).Level + p.skills.GetSkill(SkillDefOf.Melee).Level)
                    .ToList();
                int sendCount = Math.Min(5, healthy.Count - Math.Max(2, request.MinimumHomeDefenders));
                if (sendCount < 3)
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("At least three healthy fighters are required after preserving home defenders.");
                var pawns = healthy.Take(sendCount).ToList();
                List<Thing> items = CaravanFormingUtility.AllReachableColonyItems(map);
                int totalFood = items.Where(IsTravelFood).Sum(t => t.stackCount);
                int totalMedicine = items.Where(IsMedicine).Sum(t => t.stackCount);
                int takeFood = Math.Min(sendCount * 12, Math.Max(0, totalFood - request.MinimumFoodAtHome));
                int takeMedicine = Math.Min(sendCount * 3, Math.Max(0, totalMedicine - request.MinimumMedicineAtHome));
                if (takeFood < sendCount * 8 || takeMedicine < sendCount)
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("The expedition lacks safe food or medicine reserves.");
                var transferables = new List<TransferableOneWay>();
                int foodAdded = AddByPredicate(transferables, items, IsTravelFood, takeFood);
                AddByPredicate(transferables, items, IsMedicine, takeMedicine);
                PlanetTile startingTile = CaravanExitMapUtility.BestExitTileToGoTo(destination.Tile, map);
                if (!startingTile.Valid) return ApiResult<StartTradeCaravanResponseDto>.Fail("No valid exit toward the target was found.");
                IntVec3 root = pawns.Aggregate(IntVec3.Zero, (sum, pawn) => sum + pawn.Position) / pawns.Count;
                if (!RCellFinder.TryFindClosestEdgeCellTo(root, map, out IntVec3 exitSpot))
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("No reachable caravan exit was found.");
                if (!RCellFinder.TryFindRandomSpotJustOutsideColony(exitSpot, map, out IntVec3 meetingPoint)) meetingPoint = root;
                CaravanFormingUtility.StartFormingCaravan(pawns, new List<Pawn>(), Faction.OfPlayer, transferables, meetingPoint, exitSpot, startingTile, destination.Tile);
                PendingRoutes.Add(new PendingRoute
                {
                    PawnIds = new HashSet<int>(pawns.Select(p => p.thingIDNumber)),
                    SettlementId = destination.ID,
                    Raid = true
                });
                return ApiResult<StartTradeCaravanResponseDto>.Ok(new StartTradeCaravanResponseDto
                {
                    Status = "forming raid expedition",
                    DestinationSettlementId = destination.ID,
                    DestinationName = destination.LabelCap,
                    DestinationTile = destination.Tile,
                    PawnCount = pawns.Count,
                    FoodCount = foodAdded
                });
            }
            catch (Exception ex)
            {
                LogApi.Error($"Raid caravan automation failed: {ex}");
                return ApiResult<StartTradeCaravanResponseDto>.Fail(ex.Message);
            }
        }

        public static ApiResult<StartTradeCaravanResponseDto> StartRescueMission(RescueMissionRequestDto request)
        {
            try
            {
                Map map = MapHelper.GetMapByID(request.MapId);
                if (map == null) return ApiResult<StartTradeCaravanResponseDto>.Fail($"Map {request.MapId} not found.");
                if (GenHostility.AnyHostileActiveThreatToPlayer(map))
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("A rescue caravan cannot leave during an active home-map threat.");
                if (Find.WorldObjects.Caravans.Any(c => c.Faction == Faction.OfPlayer))
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("A player caravan is already active.");
                Quest quest = Find.QuestManager.QuestsListForReading.FirstOrDefault(q => q.id == request.QuestId && !q.Historical);
                if (quest == null)
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("The rescue quest no longer exists.");
                Site site = request.SiteId.HasValue
                    ? Find.WorldObjects.AllWorldObjects.OfType<Site>().FirstOrDefault(s => s.ID == request.SiteId.Value)
                    : quest.QuestLookTargets.Select(t => t.WorldObject).OfType<Site>().FirstOrDefault();
                if (site == null)
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("The quest does not expose a reachable rescue site.");

                var healthy = map.mapPawns.FreeColonistsSpawned
                    .Where(p => IsReadyDefender(p) && p.health.summaryHealth.SummaryHealthPercent >= 0.82f)
                    .OrderByDescending(p => (p.skills?.GetSkill(SkillDefOf.Shooting)?.Level ?? 0)
                        + (p.skills?.GetSkill(SkillDefOf.Melee)?.Level ?? 0))
                    .ToList();
                int available = healthy.Count - Math.Max(2, request.MinimumHomeDefenders);
                int threatSized = Math.Max(2, Math.Min(6, Mathf.CeilToInt(site.ActualThreatPoints / 180f)));
                int sendCount = Math.Min(available, threatSized);
                if (sendCount < 2)
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("At least two healthy rescuers are required after preserving home defenders.");
                List<Pawn> pawns = healthy.Take(sendCount).ToList();
                List<Thing> items = CaravanFormingUtility.AllReachableColonyItems(map);
                int totalFood = items.Where(IsTravelFood).Sum(t => t.stackCount);
                int totalMedicine = items.Where(IsMedicine).Sum(t => t.stackCount);
                int takeFood = Math.Min(sendCount * 14, Math.Max(0, totalFood - request.MinimumFoodAtHome));
                int takeMedicine = Math.Min(sendCount * 3, Math.Max(0, totalMedicine - request.MinimumMedicineAtHome));
                if (takeFood < sendCount * 8 || takeMedicine < sendCount)
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("The rescue mission lacks travel food or medicine after preserving home reserves.");
                var transferables = new List<TransferableOneWay>();
                int foodAdded = AddByPredicate(transferables, items, IsTravelFood, takeFood);
                AddByPredicate(transferables, items, IsMedicine, takeMedicine);

                PlanetTile startingTile = CaravanExitMapUtility.BestExitTileToGoTo(site.Tile, map);
                if (!startingTile.Valid)
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("No valid map exit toward the rescue site was found.");
                IntVec3 root = pawns.Aggregate(IntVec3.Zero, (sum, pawn) => sum + pawn.Position) / pawns.Count;
                if (!RCellFinder.TryFindClosestEdgeCellTo(root, map, out IntVec3 exitSpot))
                    return ApiResult<StartTradeCaravanResponseDto>.Fail("No reachable caravan exit was found.");
                if (!RCellFinder.TryFindRandomSpotJustOutsideColony(exitSpot, map, out IntVec3 meetingPoint)) meetingPoint = root;
                CaravanFormingUtility.StartFormingCaravan(pawns, new List<Pawn>(), Faction.OfPlayer, transferables,
                    meetingPoint, exitSpot, startingTile, site.Tile);
                PendingRoutes.Add(new PendingRoute
                {
                    PawnIds = new HashSet<int>(pawns.Select(p => p.thingIDNumber)),
                    SettlementId = -1,
                    SiteId = site.ID,
                    Raid = false,
                });
                Messages.Message("Laya: a rescue caravan is gathering for " + site.LabelCap + ".", pawns[0], MessageTypeDefOf.PositiveEvent, false);
                return ApiResult<StartTradeCaravanResponseDto>.Ok(new StartTradeCaravanResponseDto
                {
                    Status = "forming rescue mission",
                    DestinationSettlementId = site.ID,
                    DestinationName = site.LabelCap,
                    DestinationTile = site.Tile,
                    PawnCount = pawns.Count,
                    FoodCount = foodAdded,
                });
            }
            catch (Exception ex)
            {
                LogApi.Error($"Rescue caravan automation failed: {ex}");
                return ApiResult<StartTradeCaravanResponseDto>.Fail(ex.Message);
            }
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
                Pawn rescuer = map.mapPawns.FreeColonistsSpawned
                    .Where(p => !p.Dead && !p.Downed && !p.InMentalState)
                    .OrderByDescending(p => p.skills?.GetSkill(SkillDefOf.Social)?.Level ?? 0)
                    .FirstOrDefault();
                Pawn captive = RescueCaptives(map).FirstOrDefault();
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

        private static bool IsSaleGood(Thing thing, List<string> requested)
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

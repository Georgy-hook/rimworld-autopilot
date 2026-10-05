using System;
using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using RIMAPI.Core;
using RIMAPI.Models;
using RimWorld;
using Verse;

namespace RIMAPI.Helpers
{
    public static class LiveTradeAutomationHelper
    {
        private static readonly string[] SaleCategories =
            { "drugs", "apparel", "art", "animals", "food", "leather", "weapons", "gold" };
        private static readonly string[] PurchasePriorities =
            { "slaves", "livestock", "medicine", "advanced_components", "components", "food", "armor", "weapons", "plasteel", "wood" };

        public static ApiResult<List<LiveTraderDto>> GetOpportunities(int mapId)
        {
            try
            {
                Map map = MapHelper.GetMapByID(mapId);
                if (map == null) return ApiResult<List<LiveTraderDto>>.Fail($"Map {mapId} not found.");
                Pawn negotiator = BestNegotiator(map);
                bool hasConsole = map.listerBuildings.allBuildingsColonist.Any(b =>
                    b.def?.defName == "CommsConsole" && (b.TryGetComp<CompPowerTrader>()?.PowerOn ?? true));
                bool hasBeacon = map.listerBuildings.allBuildingsColonist.Any(b =>
                    b.def?.defName == "OrbitalTradeBeacon" && (b.TryGetComp<CompPowerTrader>()?.PowerOn ?? true));
                var result = new List<LiveTraderDto>();

                List<PassingShip> passing = Traverse.Create(map.passingShipManager)
                    .Field("passingShips").GetValue<List<PassingShip>>() ?? new List<PassingShip>();
                foreach (TradeShip ship in passing.OfType<TradeShip>().Where(s => !s.Departed && s.CanTradeNow))
                {
                    int ticks = Traverse.Create(ship).Field("ticksUntilDeparture").GetValue<int>();
                    int loadId = Traverse.Create(ship).Field("loadID").GetValue<int>();
                    result.Add(ToDto(
                        $"ship:{loadId}", ship.TraderName, ship.TraderKind, ship.Faction, true, null,
                        ticks, negotiator, hasConsole, hasBeacon, ship.Goods));
                }

                foreach (Pawn trader in map.mapPawns.AllPawnsSpawned.Where(p =>
                    p != null && !p.Dead && !p.Downed && p.TraderKind != null && p.CanTradeNow
                    && !p.HostileTo(Faction.OfPlayer)))
                {
                    result.Add(ToDto(
                        $"pawn:{trader.thingIDNumber}", trader.TraderName, trader.TraderKind, trader.Faction,
                        false, trader.thingIDNumber, 0, negotiator, hasConsole, hasBeacon,
                        trader.Goods));
                }
                return ApiResult<List<LiveTraderDto>>.Ok(result);
            }
            catch (Exception ex)
            {
                return ApiResult<List<LiveTraderDto>>.Fail(ex.Message);
            }
        }

        public static ApiResult<LiveTradePreviewDto> GetPreview(int mapId, string traderId, int minimumSilverReserve, int maximumSpend, string saleCategory)
        {
            bool opened = false;
            ITrader previousTrader = TradeSession.trader;
            Pawn previousNegotiator = TradeSession.playerNegotiator;
            TradeDeal previousDeal = TradeSession.deal;
            bool previousGiftMode = TradeSession.giftMode;
            try
            {
                Map map = MapHelper.GetMapByID(mapId);
                if (map == null) return ApiResult<LiveTradePreviewDto>.Fail($"Map {mapId} not found.");
                if (TradeSession.Active)
                    return ApiResult<LiveTradePreviewDto>.Fail("A manual trade session is already open.");
                Pawn negotiator = BestNegotiator(map);
                ITrader trader = ResolveTrader(map, traderId);
                if (negotiator == null || trader == null || !trader.CanTradeNow)
                    return ApiResult<LiveTradePreviewDto>.Fail("No available trader or negotiator.");
                if (trader is TradeShip && !map.listerBuildings.allBuildingsColonist.Any(b =>
                    b.def?.defName == "CommsConsole" && (b.TryGetComp<CompPowerTrader>()?.PowerOn ?? true)))
                    return ApiResult<LiveTradePreviewDto>.Fail("A powered comms console is required.");
                if (trader is TradeShip && !map.listerBuildings.allBuildingsColonist.Any(b =>
                    b.def?.defName == "OrbitalTradeBeacon" && (b.TryGetComp<CompPowerTrader>()?.PowerOn ?? true)))
                    return ApiResult<LiveTradePreviewDto>.Fail("A powered trade beacon is required.");
                opened = true;
                TradeSession.SetupWith(trader, negotiator, false);
                TradeDeal deal = TradeSession.deal;
                Tradeable currency = deal.CurrencyTradeable;
                int colonySilver = currency?.CountHeldBy(Transactor.Colony) ?? 0;
                int traderSilver = currency?.CountHeldBy(Transactor.Trader) ?? 0;
                int reserve = Math.Max(0, minimumSilverReserve);
                int spendLimit = Math.Max(0, maximumSpend);
                var preview = new LiveTradePreviewDto
                {
                    TraderId = traderId, ColonySilver = colonySilver, TraderSilver = traderSilver,
                    MinimumSilverReserve = reserve, MaximumSpend = spendLimit,
                };
                foreach (string category in SaleCategories)
                {
                    Tradeable row = deal.AllTradeables.FirstOrDefault(t => t.TraderWillTrade
                        && SafeSaleCount(t, map, new HashSet<string> { category }) > 0
                        && t.GetPriceFor(TradeAction.PlayerSells) > 0f);
                    if (row == null) continue;
                    float price = row.GetPriceFor(TradeAction.PlayerSells);
                    int units = Math.Min(SafeSaleCount(row, map, new HashSet<string> { category }),
                        (int)Math.Floor(traderSilver / price));
                    if (units > 0) preview.SaleOptions.Add(new LiveTradeCategoryDto
                    {
                        Category = category, Example = row.Label, MaximumUnits = units, UnitPrice = price,
                    });
                }
                if (SaleCategories.Contains(saleCategory))
                {
                    float traderSilverRemaining = traderSilver;
                    var plannedCategories = new HashSet<string> { saleCategory };
                    foreach (Tradeable row in deal.AllTradeables.Where(t => t.TraderWillTrade
                        && t.CountHeldBy(Transactor.Colony) > 0))
                    {
                        float price = row.GetPriceFor(TradeAction.PlayerSells);
                        if (price <= 0f) continue;
                        int units = Math.Min(SafeSaleCount(row, map, plannedCategories),
                            (int)Math.Floor(traderSilverRemaining / price));
                        if (units <= 0) continue;
                        float proceeds = units * price;
                        preview.PlannedSaleValue += proceeds;
                        traderSilverRemaining -= proceeds;
                    }
                }
                float availableSilver = Math.Min(spendLimit, Math.Max(0f, colonySilver + preview.PlannedSaleValue - reserve));
                foreach (string priority in PurchasePriorities.Concat(deal.AllTradeables
                    .Where(t => t.TraderWillTrade && t.CountHeldBy(Transactor.Trader) > 0 && AugmentationAutomationHelper.IsAugmentationItem(t.ThingDef))
                    .Select(t => "implant:" + t.ThingDef.defName).Distinct()).Concat(deal.AllTradeables
                    .Where(t => t.TraderWillTrade && t.CountHeldBy(Transactor.Trader) > 0 && t.ThingDef?.IsWeapon == true)
                    .Select(t => "weapon:" + t.ThingDef.defName).Distinct()).Concat(deal.AllTradeables
                    .Where(t => t.TraderWillTrade && !t.IsCurrency && t.CountHeldBy(Transactor.Trader) > 0 && t.ThingDef != null && t.ThingDef.race == null)
                    .Select(t => "item:" + t.ThingDef.defName).Distinct()))
                {
                    Tradeable row = deal.AllTradeables.Where(t => t.TraderWillTrade
                        && t.CountHeldBy(Transactor.Trader) > 0 && MatchesPriority(t, priority)
                        && CanKeepPurchasedAnimal(t, map)
                        && t.GetPriceFor(TradeAction.PlayerBuys) > 0f)
                        .OrderBy(t => t.GetPriceFor(TradeAction.PlayerBuys)).FirstOrDefault();
                    if (row == null) continue;
                    float price = row.GetPriceFor(TradeAction.PlayerBuys);
                    int units = Math.Min(row.CountHeldBy(Transactor.Trader),
                        Math.Min(PurchaseTarget(priority, row), (int)Math.Floor(availableSilver / price)));
                    if (units > 0) preview.PurchaseOptions.Add(new LiveTradeCategoryDto
                    {
                        Category = priority, Example = row.Label, MaximumUnits = units, UnitPrice = price,
                        Description = priority.StartsWith("implant:") ? AugmentationAutomationHelper.ItemSummary(row.ThingDef)
                            : row.ThingDef?.IsWeapon == true ? WeaponAutomationHelper.Summary(row.FirstThingTrader) : row.ThingDef?.description,
                    });
                }
                foreach (Tradeable row in deal.AllTradeables.Where(t => t.TraderWillTrade
                    && t.CountHeldBy(Transactor.Trader) > 0 && t.ThingDef?.race?.Humanlike == true))
                {
                    float price = row.GetPriceFor(TradeAction.PlayerBuys);
                    if (price <= 0f || price > availableSilver) continue;
                    if (row.FirstThingTrader is Pawn pawn)
                    {
                        preview.HumanlikeOffers.Add(new LiveTradePawnOfferDto
                        {
                            PawnId = pawn.thingIDNumber,
                            Name = pawn.LabelShortCap,
                            UnitPrice = price,
                            Health = pawn.health?.summaryHealth?.SummaryHealthPercent ?? 0f,
                            Age = pawn.ageTracker?.AgeBiologicalYears ?? 0,
                            Gender = pawn.gender.ToString(),
                            Skills = pawn.skills?.skills.OrderByDescending(skill => skill.Level)
                                .Take(8).Select(skill => $"{skill.def.defName}:{skill.Level}:{skill.passion}").ToList()
                                ?? new List<string>(),
                            Traits = pawn.story?.traits?.allTraits.Select(trait => trait.LabelCap).ToList()
                                ?? new List<string>(),
                            HealthConditions = pawn.health?.hediffSet?.hediffs.Select(hediff => hediff.LabelCap)
                                .Take(8).ToList() ?? new List<string>(),
                            DisabledWork = DefDatabase<WorkTypeDef>.AllDefsListForReading
                                .Where(work => pawn.WorkTypeIsDisabled(work)).Select(work => work.defName).ToList(),
                        });
                    }
                    if (preview.HumanlikeOffers.Count >= 12) break;
                }
                return ApiResult<LiveTradePreviewDto>.Ok(preview);
            }
            catch (Exception ex)
            {
                LogApi.Error($"Live trade preview failed: {ex}");
                return ApiResult<LiveTradePreviewDto>.Fail(ex.Message);
            }
            finally
            {
                if (opened)
                {
                    TradeSession.trader=previousTrader; TradeSession.playerNegotiator=previousNegotiator;
                    TradeSession.deal=previousDeal; TradeSession.giftMode=previousGiftMode;
                }
            }
        }

        public static ApiResult<LiveTradeResponseDto> Execute(LiveTradeRequestDto request)
        {
            bool opened = false;
            try
            {
                Map map = MapHelper.GetMapByID(request.MapId);
                if (map == null) return ApiResult<LiveTradeResponseDto>.Fail($"Map {request.MapId} not found.");
                if (GenHostility.AnyHostileActiveThreatToPlayer(map))
                    return ApiResult<LiveTradeResponseDto>.Fail("Trading is blocked during an active hostile threat.");
                Pawn negotiator = BestNegotiator(map);
                if (negotiator == null)
                    return ApiResult<LiveTradeResponseDto>.Fail("No conscious colonist capable of Social work can negotiate.");
                if(request.ExpectedNegotiatorId.HasValue && (negotiator.thingIDNumber!=request.ExpectedNegotiatorId.Value
                    || !InspirationAutomationHelper.Matches(negotiator,request.ExpectedInspiration,request.ExpectedIdentity)))
                    return ApiResult<LiveTradeResponseDto>.Fail("inspiration_changed_reconsider");
                ITrader trader = ResolveTrader(map, request.TraderId);
                if (trader == null || !trader.CanTradeNow)
                    return ApiResult<LiveTradeResponseDto>.Fail("The selected trader is no longer available.");
                if (trader is TradeShip)
                {
                    bool console = map.listerBuildings.allBuildingsColonist.Any(b => b.def?.defName == "CommsConsole"
                        && (b.TryGetComp<CompPowerTrader>()?.PowerOn ?? true));
                    bool beacon = map.listerBuildings.allBuildingsColonist.Any(b => b.def?.defName == "OrbitalTradeBeacon"
                        && (b.TryGetComp<CompPowerTrader>()?.PowerOn ?? true));
                    if (!console || !beacon)
                        return ApiResult<LiveTradeResponseDto>.Fail("Orbital trade requires a powered comms console and orbital trade beacon.");
                }

                if (TradeSession.Active)
                    return ApiResult<LiveTradeResponseDto>.Fail("An existing trade session must be resolved before automated trading.");
                opened = true;
                TradeSession.SetupWith(trader, negotiator, false);
                TradeDeal deal = TradeSession.deal;
                if (request.PurchasePawnId.HasValue && !(request.PurchasePriorities ?? new List<string>())
                    .Any(value => value.Equals("slaves", StringComparison.OrdinalIgnoreCase)))
                {
                    TradeSession.Close();
                    return ApiResult<LiveTradeResponseDto>.Fail("A selected pawn requires the slaves purchase priority.");
                }
                if (request.PurchasePawnId.HasValue && !deal.AllTradeables.Any(row => row.TraderWillTrade
                    && row.CountHeldBy(Transactor.Trader) > 0 && row.ThingDef?.race?.Humanlike == true
                    && row.FirstThingTrader is Pawn pawn && pawn.thingIDNumber == request.PurchasePawnId.Value))
                {
                    TradeSession.Close();
                    return ApiResult<LiveTradeResponseDto>.Fail("The chosen person is no longer offered by this trader.");
                }
                var response = new LiveTradeResponseDto
                {
                    TraderId = request.TraderId,
                    TraderName = trader.TraderName,
                    Negotiator = negotiator.LabelShortCap,
                };

                var saleCategories = new HashSet<string>((request.SaleCategories ?? new List<string>()).Select(s => s.ToLowerInvariant()));
                float traderSilverRemaining = deal.CurrencyTradeable?.CountHeldBy(Transactor.Trader) ?? 0;
                foreach (Tradeable row in deal.AllTradeables.Where(t => t.TraderWillTrade && t.CountHeldBy(Transactor.Colony) > 0))
                {
                    int surplus = SafeSaleCount(row, map, saleCategories);
                    float price = row.GetPriceFor(TradeAction.PlayerSells);
                    if (price <= 0f) continue;
                    surplus = Math.Min(surplus, (int)Math.Floor(traderSilverRemaining / price));
                    if (surplus <= 0) continue;
                    row.ForceToDestination(surplus);
                    response.SoldUnits += surplus;
                    response.ApproximateSaleValue += price * surplus;
                    traderSilverRemaining -= price * surplus;
                    response.Sold.Add($"{row.Label} x{surplus}");
                }
                deal.UpdateCurrencyCount();
                if (!deal.DoesTraderHaveEnoughSilver())
                {
                    foreach (Tradeable row in deal.AllTradeables.Where(t => t.CountToTransfer > 0)) row.ForceTo(0);
                    response.Sold.Clear();
                    response.SoldUnits = 0;
                    response.ApproximateSaleValue = 0;
                    deal.UpdateCurrencyCount();
                }

                float spend = 0f;
                bool selectedPersonPurchased = !request.PurchasePawnId.HasValue;
                var pendingItems = new HashSet<string>((request.PurchasePriorities ?? new List<string>()).Where(p => p != null && p.StartsWith("item:",StringComparison.Ordinal)));
                foreach (string priority in (request.PurchasePriorities ?? new List<string>()).Distinct())
                {
                    int remainingPawns = priority.Equals("slaves", StringComparison.OrdinalIgnoreCase)
                        || priority.Equals("livestock", StringComparison.OrdinalIgnoreCase)
                        || priority.StartsWith("item:",StringComparison.Ordinal) || priority.StartsWith("implant:",StringComparison.Ordinal)
                        || priority.StartsWith("weapon:",StringComparison.Ordinal) ? 1 : int.MaxValue;
                    foreach (Tradeable row in deal.AllTradeables
                        .Where(t => t.TraderWillTrade && t.CountHeldBy(Transactor.Trader) > 0
                            && MatchesPriority(t, priority) && CanKeepPurchasedAnimal(t, map)
                            && (!request.PurchasePawnId.HasValue || !priority.Equals("slaves", StringComparison.OrdinalIgnoreCase)
                                || (t.FirstThingTrader is Pawn pawn && pawn.thingIDNumber == request.PurchasePawnId.Value)))
                        .OrderBy(t => t.GetPriceFor(TradeAction.PlayerBuys)))
                    {
                        float unitPrice = Math.Max(0.01f, row.GetPriceFor(TradeAction.PlayerBuys));
                        int affordableByBudget = Math.Max(0, (int)Math.Floor((request.MaximumSpend - spend) / unitPrice));
                        int affordableBySilver = Math.Max(0, (int)Math.Floor(
                            ((deal.CurrencyTradeable?.CountPostDealFor(Transactor.Colony) ?? 0)
                             - request.MinimumSilverReserve) / unitPrice));
                        int wanted = Math.Min(row.CountHeldBy(Transactor.Trader), PurchaseTarget(priority, row));
                        int count = Math.Min(Math.Min(Math.Min(affordableByBudget, affordableBySilver), wanted), remainingPawns);
                        if (count <= 0) continue;
                        row.ForceToSource(count);
                        deal.UpdateCurrencyCount();
                        Tradeable currency = deal.CurrencyTradeable;
                        if (currency != null && currency.CountPostDealFor(Transactor.Colony) < request.MinimumSilverReserve)
                        {
                            row.ForceTo(0);
                            deal.UpdateCurrencyCount();
                            continue;
                        }
                        spend += unitPrice * count;
                        response.BoughtUnits += count;
                        response.ApproximatePurchaseValue += unitPrice * count;
                        response.Bought.Add($"{row.Label} x{count}");
                        pendingItems.Remove(priority);
                        if (request.PurchasePawnId.HasValue && priority.Equals("slaves", StringComparison.OrdinalIgnoreCase)
                            && row.FirstThingTrader is Pawn boughtPawn
                            && boughtPawn.thingIDNumber == request.PurchasePawnId.Value)
                            selectedPersonPurchased = true;
                        remainingPawns -= count;
                        if (remainingPawns <= 0) break;
                    }
                }

                if (!selectedPersonPurchased || pendingItems.Count > 0)
                {
                    TradeSession.Close();
                    return ApiResult<LiveTradeResponseDto>.Fail("The selected person or exact item is no longer available or affordable; no partial sale was made.");
                }
                if (response.SoldUnits == 0 && response.BoughtUnits == 0)
                {
                    TradeSession.Close();
                    return ApiResult<LiveTradeResponseDto>.Fail("No safe requested trade matched this trader's stock and budget.");
                }
                if (!deal.DoesTraderHaveEnoughSilver())
                {
                    TradeSession.Close();
                    return ApiResult<LiveTradeResponseDto>.Fail("The trader cannot afford the selected sale.");
                }
                response.Executed = deal.TryExecute(out bool actuallyTraded) && actuallyTraded;
                TradeSession.Close();
                if (!response.Executed)
                    return ApiResult<LiveTradeResponseDto>.Fail("The normal trade deal rejected the transaction.");
                Messages.Message("Laya completed a normal trade with " + trader.TraderName + ".", MessageTypeDefOf.PositiveEvent, false);
                return ApiResult<LiveTradeResponseDto>.Ok(response);
            }
            catch (Exception ex)
            {
                if (opened && TradeSession.Active) TradeSession.Close();
                LogApi.Error($"Live trade automation failed: {ex}");
                return ApiResult<LiveTradeResponseDto>.Fail(ex.Message);
            }
        }

        private static LiveTraderDto ToDto(string id, string name, TraderKindDef kind, Faction faction,
            bool orbital, int? pawnId, int ticks, Pawn negotiator, bool console, bool beacon, IEnumerable<Thing> stock)
        {
            return new LiveTraderDto
            {
                Id = id,
                Name = name,
                TraderKind = kind?.defName,
                Faction = faction?.Name,
                Orbital = orbital,
                PawnId = pawnId,
                TicksUntilDeparture = ticks,
                BestNegotiatorPawnId = negotiator?.thingIDNumber ?? 0,
                BestNegotiatorName = negotiator?.LabelShortCap,
                NegotiatorInspiration = negotiator==null?null:InspirationAutomationHelper.Describe(negotiator),
                NegotiatorTradeImprovement=negotiator?.GetStatValue(StatDefOf.TradePriceImprovement) ?? 0,
                NegotiatorSocialSkill = negotiator?.skills?.GetSkill(SkillDefOf.Social)?.Level ?? 0,
                HasPoweredCommsConsole = console,
                HasPoweredOrbitalBeacon = beacon,
                Stock = (stock ?? Enumerable.Empty<Thing>()).Where(t => t?.def != null).Select(t => new LiveTradeItemDto
                {
                    DefName = t.def.defName,
                    Label = t.LabelCap,
                    Count = t.stackCount,
                    IsWeapon = t.def.IsWeapon,
                    IsImplant = AugmentationAutomationHelper.IsAugmentationItem(t.def),
                    Description = t.def.IsWeapon ? WeaponAutomationHelper.Summary(t) : t.def.description,
                    MarketValue = t.MarketValue,
                    Humanlike = t is Pawn human && human.RaceProps.Humanlike,
                    Animal = t is Pawn animal && animal.RaceProps.Animal,
                    Health = t is Pawn patient ? patient.health?.summaryHealth?.SummaryHealthPercent ?? 0f : 1f,
                    Skills = t is Pawn recruit && recruit.RaceProps.Humanlike && recruit.skills != null
                        ? recruit.skills.skills.OrderByDescending(skill => skill.Level)
                            .Take(5).Select(skill => $"{skill.def.defName}:{skill.Level}:{skill.passion}").ToList()
                        : new List<string>(),
                    Categories = t.def.thingCategories?.Select(c => c.defName).ToList() ?? new List<string>(),
                }).ToList(),
            };
        }

        private static Pawn BestNegotiator(Map map)
        {
            return map.mapPawns.FreeColonistsSpawned
                .Where(p => !p.Dead && !p.Downed && !p.InMentalState && p.health.capacities.CanBeAwake
                    && p.skills != null && !p.WorkTypeIsDisabled(WorkTypeDefOf.Warden))
                .OrderByDescending(p => p.GetStatValue(StatDefOf.TradePriceImprovement))
                .ThenByDescending(p => p.skills.GetSkill(SkillDefOf.Social).Level)
                .FirstOrDefault();
        }

        private static ITrader ResolveTrader(Map map, string id)
        {
            if (string.IsNullOrEmpty(id)) return null;
            string[] parts = id.Split(':');
            if (parts.Length != 2 || !int.TryParse(parts[1], out int numeric)) return null;
            if (parts[0] == "pawn")
                return map.mapPawns.AllPawnsSpawned.FirstOrDefault(p => p.thingIDNumber == numeric && p.TraderKind != null);
            if (parts[0] == "ship")
            {
                List<PassingShip> passing = Traverse.Create(map.passingShipManager).Field("passingShips").GetValue<List<PassingShip>>();
                return passing?.OfType<TradeShip>().FirstOrDefault(s => Traverse.Create(s).Field("loadID").GetValue<int>() == numeric);
            }
            return null;
        }

        private static int SafeSaleCount(Tradeable row, Map map, HashSet<string> categories)
        {
            if (categories.Count == 0 || row.ThingDef == null || row.IsCurrency) return 0;
            string text = (row.ThingDef.defName + " " + row.Label + " "
                + string.Join(" ", row.ThingDef.thingCategories?.Select(c => c.defName) ?? Enumerable.Empty<string>())).ToLowerInvariant();
            bool selected = categories.Any(category =>
                (category == "drugs" && new[] { "flake", "yayo", "smokeleafjoint", "beer", "ambrosia" }
                    .Any(text.Contains))
                || (category == "animals" && row.ThingDef.race?.Animal == true)
                || (category == "food" && (text.Contains("food") || text.Contains("meal")
                    || text.Contains("rice") || text.Contains("corn") || text.Contains("potato")))
                || (category == "art" && text.Contains("sculpture"))
                || (category == "apparel" && row.ThingDef.IsApparel)
                || (category == "weapons" && row.ThingDef.IsWeapon)
                || (category == "leather" && (text.Contains("leather") || text.Contains("wool")
                    || text.Contains("cloth")))
                || (category == "gold" && (text.Contains("gold") || text.Contains("jade"))));
            if (!selected) return 0;
            int total = row.CountHeldBy(Transactor.Colony);
            int reserve = 0;
            if (new[] { "food", "meal", "meat", "rice", "corn", "potato", "pemmican", "berry" }.Any(text.Contains))
                reserve = Math.Max(20, map.mapPawns.FreeColonistsSpawnedCount * 18);
            else if (text.Contains("medicine")) reserve = 12;
            else if (text.Contains("component")) reserve = text.Contains("advanced") ? 4 : 12;
            else if (text.Contains("steel")) reserve = 350;
            else if (text.Contains("wood")) reserve = 250;
            else if (row.ThingDef.IsWeapon) reserve = 1;
            else if (row.ThingDef.race?.Animal == true) reserve = 2;
            return Math.Max(0, total - reserve);
        }

        private static bool MatchesPriority(Tradeable row, string priority)
        {
            if (row.ThingDef == null) return false;
            if ((priority ?? "").StartsWith("item:", StringComparison.Ordinal))
                return !row.IsCurrency && row.ThingDef.race == null && row.ThingDef.defName == priority.Substring(5);
            string wanted = (priority ?? "").ToLowerInvariant().Replace("_", "");
            if ((priority ?? "").StartsWith("implant:", StringComparison.Ordinal))
                return row.ThingDef.defName == priority.Substring(8) && AugmentationAutomationHelper.IsAugmentationItem(row.ThingDef);
            if ((priority ?? "").StartsWith("weapon:", StringComparison.Ordinal))
                return row.ThingDef.defName == priority.Substring(7) && row.ThingDef.IsWeapon;
            string text = (row.ThingDef.defName + row.Label + string.Join("", row.ThingDef.thingCategories?.Select(c => c.defName) ?? Enumerable.Empty<string>())).ToLowerInvariant().Replace("_", "");
            if (wanted == "advancedcomponents") return text.Contains("componentadvanced");
            if (wanted == "components") return text.Contains("component") && !text.Contains("advanced");
            if (wanted == "medicine") return text.Contains("medicine") || text.Contains("neutroamine");
            if (wanted == "slaves") return row.ThingDef.race?.Humanlike == true;
            if (wanted == "livestock") return row.ThingDef.race?.Animal == true;
            if (wanted == "food") return new[] { "food", "meal", "rice", "corn", "potato", "pemmican", "berry" }.Any(text.Contains);
            if (wanted == "weapons") return row.ThingDef.IsWeapon;
            if (wanted == "wood") return row.ThingDef == ThingDefOf.WoodLog;
            if (wanted == "armor") return text.Contains("armor") || text.Contains("helmet") || text.Contains("vest");
            return text.Contains(wanted);
        }

        private static bool CanKeepPurchasedAnimal(Tradeable row, Map map)
        {
            if (row.ThingDef?.race?.Animal != true || !row.ThingDef.race.Roamer) return true;
            return map.listerBuildings.allBuildingsAnimalPenMarkers.Any(marker =>
            {
                CompAnimalPenMarker pen = marker.TryGetComp<CompAnimalPenMarker>();
                return pen?.PenState?.Enclosed == true && pen.PenState.HasOutsideAccess
                    && pen.AnimalFilter.Allows(row.ThingDef);
            });
        }

        private static int PurchaseTarget(string priority, Tradeable row)
        {
            string value = (priority ?? "").ToLowerInvariant();
            if (value.StartsWith("item:")) return 1;
            if (value.StartsWith("implant:")) return 1;
            if (value.StartsWith("weapon:")) return 1;
            if (value == "wood") return 100;
            if (value.Contains("medicine") || value.Contains("component")) return 20;
            if (value.Contains("food")) return 50;
            if (value.Contains("slaves") || value.Contains("livestock")) return 1;
            if (row.ThingDef?.IsWeapon == true || value.Contains("armor")) return 2;
            return 10;
        }
    }
}

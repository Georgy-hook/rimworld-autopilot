using System;
using System.Collections.Generic;
using System.Linq;
using RIMAPI.Core;
using RIMAPI.Models;
using RimWorld;
using RimWorld.Planet;
using Verse;

namespace RIMAPI.Helpers
{
    // A caravan arrival opens a real TradeSession/Dialog_Trade. The existing
    // map-trader endpoint cannot see this session because the caravan has no
    // home map. Keep this separate and act only on the session already open.
    public static class CaravanTradeSessionHelper
    {
        private static readonly string[] SaleCategories =
            { "drugs", "apparel", "art", "animal_products", "chemfuel", "precious", "prisoners" };

        private static bool TrySession(out Settlement settlement, out Caravan caravan)
        {
            settlement = TradeSession.trader as Settlement;
            caravan = TradeSession.playerNegotiator?.GetCaravan();
            return TradeSession.Active && !TradeSession.giftMode && TradeSession.deal != null
                && settlement != null && caravan != null && caravan.Faction == Faction.OfPlayer;
        }

        private static bool MatchesSale(Tradeable row, string category)
        {
            string name = row.ThingDef?.defName ?? "";
            string categories = string.Join(" ", row.ThingDef?.thingCategories?.Select(c => c.defName)
                ?? Enumerable.Empty<string>());
            switch (category)
            {
                case "drugs": return name == "Flake" || name == "Yayo" || name == "SmokeleafJoint";
                case "apparel": return categories.Contains("Apparel");
                case "art": return name.Contains("Sculpture");
                case "animal_products": return name.Contains("Wool") || name.Contains("Leather") || name.Contains("Milk");
                case "chemfuel": return name == "Chemfuel";
                case "precious": return name == "Gold" || name == "Jade";
                case "prisoners": return row.FirstThingColony is Pawn pawn
                    && pawn.IsPrisonerOfColony && pawn.Faction != Faction.OfPlayer;
                default: return false;
            }
        }

        public static ApiResult<ActiveCaravanTradeDto> Preview()
        {
            try
            {
                var preview = new ActiveCaravanTradeDto();
                if (!TrySession(out Settlement settlement, out Caravan caravan))
                    return ApiResult<ActiveCaravanTradeDto>.Ok(preview);
                TradeDeal deal = TradeSession.deal;
                preview.Active = true;
                preview.SettlementId = settlement.ID;
                preview.SettlementName = settlement.LabelCap;
                preview.ColonySilver = deal.CurrencyTradeable?.CountHeldBy(Transactor.Colony) ?? 0;
                preview.TraderSilver = deal.CurrencyTradeable?.CountHeldBy(Transactor.Trader) ?? 0;
                foreach (Tradeable row in deal.AllTradeables.Where(t => t.TraderWillTrade && !t.IsCurrency
                    && t.CountHeldBy(Transactor.Trader) > 0 && t.ThingDef != null && t.ThingDef.race == null))
                {
                    float price = row.GetPriceFor(TradeAction.PlayerBuys);
                    if (price <= 0f || row.FirstThingTrader == null) continue;
                    preview.PurchaseOptions.Add(new LiveTradeCategoryDto { ThingId=row.FirstThingTrader.thingIDNumber,
                        Category="item:"+row.ThingDef.defName, Example=row.Label, MaximumUnits=row.CountHeldBy(Transactor.Trader),
                        UnitPrice=price, Description=row.ThingDef.description });
                }
                foreach (string category in SaleCategories)
                {
                    Tradeable row = deal.AllTradeables.FirstOrDefault(t => t.TraderWillTrade
                        && t.CountHeldBy(Transactor.Colony) > 0 && MatchesSale(t, category)
                        && t.GetPriceFor(TradeAction.PlayerSells) > 0f);
                    if (row == null) continue;
                    float proceeds=0f, remaining=preview.TraderSilver;
                    foreach (Tradeable sale in deal.AllTradeables.Where(t => t.TraderWillTrade && t.CountHeldBy(Transactor.Colony)>0 && MatchesSale(t,category)))
                    {
                        float price=sale.GetPriceFor(TradeAction.PlayerSells);
                        if(price<=0f)continue;
                        int units=Math.Min(sale.CountHeldBy(Transactor.Colony),Math.Min((int)Math.Floor(remaining/price),(int)Math.Floor((2500f-proceeds)/price)));
                        if(units<=0)continue;proceeds+=units*price;remaining-=units*price;
                    }
                    preview.SaleOptions.Add(new LiveTradeCategoryDto
                    {
                        Category = category, Example = row.Label,
                        MaximumUnits = row.CountHeldBy(Transactor.Colony),
                        UnitPrice = row.GetPriceFor(TradeAction.PlayerSells),
                        PlannedSaleValue = proceeds,
                    });
                }
                foreach (Tradeable row in deal.AllTradeables.Where(t => t.TraderWillTrade
                    && t.CountHeldBy(Transactor.Trader) > 0 && t.ThingDef?.race?.Humanlike == true))
                {
                    if (!(row.FirstThingTrader is Pawn pawn)) continue;
                    preview.HumanlikeOffers.Add(new LiveTradePawnOfferDto
                    {
                        PawnId = pawn.thingIDNumber, Name = pawn.LabelShortCap,
                        UnitPrice = row.GetPriceFor(TradeAction.PlayerBuys),
                        Health = pawn.health?.summaryHealth?.SummaryHealthPercent ?? 0f,
                        Age = pawn.ageTracker?.AgeBiologicalYears ?? 0,
                        Gender = pawn.gender.ToString(),
                        Skills = pawn.skills?.skills.OrderByDescending(skill => skill.Level).Take(8)
                            .Select(skill => $"{skill.def.defName}:{skill.Level}:{skill.passion}").ToList()
                            ?? new List<string>(),
                        Traits = pawn.story?.traits?.allTraits.Select(trait => trait.LabelCap).ToList()
                            ?? new List<string>(),
                        HealthConditions = pawn.health?.hediffSet?.hediffs.Take(8)
                            .Select(hediff => hediff.LabelCap).ToList() ?? new List<string>(),
                        DisabledWork = DefDatabase<WorkTypeDef>.AllDefsListForReading
                            .Where(work => pawn.WorkTypeIsDisabled(work)).Select(work => work.defName).ToList(),
                    });
                    if (preview.HumanlikeOffers.Count >= 12) break;
                }
                return ApiResult<ActiveCaravanTradeDto>.Ok(preview);
            }
            catch (Exception ex)
            {
                LogApi.Error($"Caravan trade preview failed: {ex}");
                return ApiResult<ActiveCaravanTradeDto>.Fail(ex.GetBaseException().Message);
            }
        }

        public static ApiResult<LiveTradeResponseDto> Execute(ActiveCaravanTradeRequestDto request)
        {
            try
            {
                if (request == null || !TrySession(out Settlement settlement, out Caravan caravan)
                    || settlement.ID != request.SettlementId)
                    return ApiResult<LiveTradeResponseDto>.Fail("The selected caravan trade session is no longer open.");
                if (request.CloseWithoutTrade)
                {
                    CloseSession();
                    RouteHome(caravan);
                    return ApiResult<LiveTradeResponseDto>.Ok(new LiveTradeResponseDto
                    {
                        TraderId = $"settlement:{settlement.ID}", TraderName = settlement.LabelCap,
                    });
                }
                TradeDeal deal = TradeSession.deal;
                if (request.PurchasePawnId.HasValue && request.PurchaseThingId.HasValue)
                    return ApiResult<LiveTradeResponseDto>.Fail("Choose exactly one person or item purchase.");
                if (deal.AllTradeables.Any(t => t.CountToTransfer != 0))
                    return ApiResult<LiveTradeResponseDto>.Fail("Existing manual trade selections must be resolved first.");
                var response = new LiveTradeResponseDto
                {
                    TraderId = $"settlement:{settlement.ID}", TraderName = settlement.LabelCap,
                    Negotiator = TradeSession.playerNegotiator.LabelShortCap,
                };
                string category = request.SaleCategory ?? "none";
                if (category != "none" && !SaleCategories.Contains(category))
                    return ApiResult<LiveTradeResponseDto>.Fail("Unknown caravan sale category.");
                float traderSilver = deal.CurrencyTradeable?.CountHeldBy(Transactor.Trader) ?? 0;
                foreach (Tradeable row in deal.AllTradeables.Where(t => t.TraderWillTrade
                    && t.CountHeldBy(Transactor.Colony) > 0 && MatchesSale(t, category)))
                {
                    float price = row.GetPriceFor(TradeAction.PlayerSells);
                    if (price <= 0f) continue;
                    int units = Math.Min(row.CountHeldBy(Transactor.Colony),
                        Math.Min((int)Math.Floor(traderSilver / price),
                                 (int)Math.Floor((2500f - response.ApproximateSaleValue) / price)));
                    if (units <= 0) continue;
                    row.ForceToDestination(units);
                    traderSilver -= units * price;
                    response.SoldUnits += units;
                    response.ApproximateSaleValue += units * price;
                    response.Sold.Add($"{row.Label} x{units}");
                }
                deal.UpdateCurrencyCount();
                if (request.PurchasePawnId.HasValue || request.PurchaseThingId.HasValue)
                {
                    Tradeable selected = deal.AllTradeables.SingleOrDefault(t => t.TraderWillTrade
                        && t.CountHeldBy(Transactor.Trader) > 0
                        && (request.PurchasePawnId.HasValue ? t.FirstThingTrader is Pawn pawn && pawn.RaceProps.Humanlike && pawn.thingIDNumber == request.PurchasePawnId.Value
                            : !t.IsCurrency && t.ThingDef?.race == null && t.FirstThingTrader?.thingIDNumber == request.PurchaseThingId.Value));
                    if (selected == null)
                    {
                        ClearSelections(deal);
                        return ApiResult<LiveTradeResponseDto>.Fail("The selected person or item is no longer offered.");
                    }
                    float price = selected.GetPriceFor(TradeAction.PlayerBuys);
                    if (request.ExpectedUnitPrice.HasValue && Math.Abs(request.ExpectedUnitPrice.Value-price) > .01f)
                    { ClearSelections(deal); return ApiResult<LiveTradeResponseDto>.Fail("The selected purchase price changed; choose again."); }
                    if (price <= 0f || price > request.MaximumSpend
                        || (deal.CurrencyTradeable?.CountPostDealFor(Transactor.Colony) ?? 0) - price
                           < Math.Max(0, request.MinimumSilverReserve))
                    {
                        ClearSelections(deal);
                        return ApiResult<LiveTradeResponseDto>.Fail("The selected purchase exceeds the spending limit or silver reserve.");
                    }
                    selected.ForceToSource(1);
                    deal.UpdateCurrencyCount();
                    if ((deal.CurrencyTradeable?.CountPostDealFor(Transactor.Colony) ?? 0) < Math.Max(0,request.MinimumSilverReserve))
                    { ClearSelections(deal); return ApiResult<LiveTradeResponseDto>.Fail("The normal rounded currency transfer exceeds the silver reserve."); }
                    response.BoughtUnits = 1;
                    response.ApproximatePurchaseValue = price;
                    response.Bought.Add(selected.Label);
                }
                if (response.SoldUnits == 0 && response.BoughtUnits == 0)
                    return ApiResult<LiveTradeResponseDto>.Fail("No selected sale or recruit is available in this session.");
                if (!deal.DoesTraderHaveEnoughSilver())
                {
                    ClearSelections(deal);
                    return ApiResult<LiveTradeResponseDto>.Fail("The settlement cannot afford the selected sale.");
                }
                response.Executed = deal.TryExecute(out bool actuallyTraded) && actuallyTraded;
                if (!response.Executed)
                {
                    ClearSelections(deal);
                    return ApiResult<LiveTradeResponseDto>.Fail("The normal caravan trade deal rejected the transaction.");
                }
                caravan.RecacheInventory();
                CloseSession();
                RouteHome(caravan);
                return ApiResult<LiveTradeResponseDto>.Ok(response);
            }
            catch (Exception ex)
            {
                if (TradeSession.Active && TradeSession.deal != null) ClearSelections(TradeSession.deal);
                LogApi.Error($"Caravan trade failed: {ex}");
                return ApiResult<LiveTradeResponseDto>.Fail(ex.GetBaseException().Message);
            }
        }

        private static void ClearSelections(TradeDeal deal)
        {
            foreach (Tradeable row in deal.AllTradeables.Where(t => t.CountToTransfer != 0)) row.ForceTo(0);
            deal.UpdateCurrencyCount();
        }

        private static void CloseSession()
        {
            Find.WindowStack.WindowOfType<Dialog_Trade>()?.Close(false);
            TradeSession.Close();
        }

        private static void RouteHome(Caravan caravan)
        {
            Map home = Find.Maps.FirstOrDefault(map => map.IsPlayerHome);
            if (home?.Parent != null)
                caravan.pather.StartPath(home.Tile, new CaravanArrivalAction_Enter(home.Parent), true);
        }
    }
}

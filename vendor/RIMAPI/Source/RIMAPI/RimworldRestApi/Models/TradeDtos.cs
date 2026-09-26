using System.Collections.Generic;
using Newtonsoft.Json;
using System.ComponentModel;

namespace RIMAPI.Models
{
    public class TraderKindDto
    {
        public string DefName { get; set; }
        public string Label { get; set; }

        // Using short boolean flags (0/1 or omit if false) could optimize further, 
        // but standard bools are fine for readability.
        public bool Orbital { get; set; }
        public bool Visitor { get; set; }
        public float Commonality { get; set; }

        // -- BUCKETS --
        // We only initialize these if they have data to keep JSON clean
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public List<StockRuleDto> Items { get; set; }

        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public List<StockRuleDto> Categories { get; set; }

        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public List<StockRuleDto> Tags { get; set; }

        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public List<StockRuleDto> Special { get; set; }
    }

    public class StockRuleDto
    {
        public string Name { get; set; }

        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public string Count { get; set; }

        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public string Price { get; set; }

        // FIX: Explicitly tell serializer that 'true' is the default
        [JsonProperty(DefaultValueHandling = DefaultValueHandling.Ignore)]
        [DefaultValue(true)]
        public bool Buys { get; set; } = true;
    }

    public class LiveTradeItemDto
    {
        public string DefName { get; set; }
        public string Label { get; set; }
        public int Count { get; set; }
        public float MarketValue { get; set; }
        public bool Humanlike { get; set; }
        public bool Animal { get; set; }
        public float Health { get; set; }
        public System.Collections.Generic.List<string> Skills { get; set; } = new System.Collections.Generic.List<string>();
        public System.Collections.Generic.List<string> Categories { get; set; } = new System.Collections.Generic.List<string>();
    }

    public class LiveTraderDto
    {
        public string Id { get; set; }
        public string Name { get; set; }
        public string TraderKind { get; set; }
        public string Faction { get; set; }
        public bool Orbital { get; set; }
        public int? PawnId { get; set; }
        public int TicksUntilDeparture { get; set; }
        public int BestNegotiatorPawnId { get; set; }
        public string BestNegotiatorName { get; set; }
        public int NegotiatorSocialSkill { get; set; }
        public bool HasPoweredCommsConsole { get; set; }
        public bool HasPoweredOrbitalBeacon { get; set; }
        public System.Collections.Generic.List<LiveTradeItemDto> Stock { get; set; } = new System.Collections.Generic.List<LiveTradeItemDto>();
    }

    public class LiveTradeRequestDto
    {
        public int MapId { get; set; }
        public string TraderId { get; set; }
        public System.Collections.Generic.List<string> SaleCategories { get; set; } = new System.Collections.Generic.List<string>();
        public System.Collections.Generic.List<string> PurchasePriorities { get; set; } = new System.Collections.Generic.List<string>();
        public int MinimumSilverReserve { get; set; } = 300;
        public int MaximumSpend { get; set; } = 2000;
        public int? PurchasePawnId { get; set; }
    }

    public class LiveTradePawnOfferDto
    {
        public int PawnId { get; set; }
        public string Name { get; set; }
        public float UnitPrice { get; set; }
        public float Health { get; set; }
        public int Age { get; set; }
        public string Gender { get; set; }
        public System.Collections.Generic.List<string> Skills { get; set; } = new System.Collections.Generic.List<string>();
        public System.Collections.Generic.List<string> Traits { get; set; } = new System.Collections.Generic.List<string>();
        public System.Collections.Generic.List<string> HealthConditions { get; set; } = new System.Collections.Generic.List<string>();
        public System.Collections.Generic.List<string> DisabledWork { get; set; } = new System.Collections.Generic.List<string>();
    }

    public class LiveTradeCategoryDto
    {
        public string Category { get; set; }
        public string Example { get; set; }
        public int MaximumUnits { get; set; }
        public float UnitPrice { get; set; }
    }

    public class LiveTradePreviewDto
    {
        public string TraderId { get; set; }
        public int ColonySilver { get; set; }
        public int TraderSilver { get; set; }
        public int MinimumSilverReserve { get; set; }
        public int MaximumSpend { get; set; }
        public System.Collections.Generic.List<LiveTradeCategoryDto> SaleOptions { get; set; } = new System.Collections.Generic.List<LiveTradeCategoryDto>();
        public System.Collections.Generic.List<LiveTradeCategoryDto> PurchaseOptions { get; set; } = new System.Collections.Generic.List<LiveTradeCategoryDto>();
        public float PlannedSaleValue { get; set; }
        public System.Collections.Generic.List<LiveTradePawnOfferDto> HumanlikeOffers { get; set; } = new System.Collections.Generic.List<LiveTradePawnOfferDto>();
    }

    public class LiveTradeResponseDto
    {
        public string TraderId { get; set; }
        public string TraderName { get; set; }
        public string Negotiator { get; set; }
        public int SoldUnits { get; set; }
        public int BoughtUnits { get; set; }
        public float ApproximateSaleValue { get; set; }
        public float ApproximatePurchaseValue { get; set; }
        public bool Executed { get; set; }
        public System.Collections.Generic.List<string> Sold { get; set; } = new System.Collections.Generic.List<string>();
        public System.Collections.Generic.List<string> Bought { get; set; } = new System.Collections.Generic.List<string>();
    }

    public class ActiveCaravanTradeDto
    {
        public bool Active { get; set; }
        public int SettlementId { get; set; }
        public string SettlementName { get; set; }
        public int ColonySilver { get; set; }
        public int TraderSilver { get; set; }
        public System.Collections.Generic.List<LiveTradePawnOfferDto> HumanlikeOffers { get; set; } = new System.Collections.Generic.List<LiveTradePawnOfferDto>();
        public System.Collections.Generic.List<LiveTradeCategoryDto> SaleOptions { get; set; } = new System.Collections.Generic.List<LiveTradeCategoryDto>();
    }

    public class ActiveCaravanTradeRequestDto
    {
        public int SettlementId { get; set; }
        public int? PurchasePawnId { get; set; }
        public string SaleCategory { get; set; }
        public int MinimumSilverReserve { get; set; }
        public int MaximumSpend { get; set; } = 2500;
        public bool CloseWithoutTrade { get; set; }
    }
}

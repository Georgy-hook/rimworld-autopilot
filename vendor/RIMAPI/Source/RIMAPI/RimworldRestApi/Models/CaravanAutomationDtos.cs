namespace RIMAPI.Models
{
    public class StartTradeCaravanRequestDto : ExpeditionRequestDto { }

    public class KnownTradeItemDto
    {
        public string DefName { get; set; }
        public string Label { get; set; }
        public int Count { get; set; }
        public float MarketValue { get; set; }
        public float EstimatedBuyPrice { get; set; }
        public float EstimatedSellPrice { get; set; }
    }

    public class TradeDestinationDto
    {
        public int SettlementId { get; set; }
        public string Name { get; set; }
        public int Tile { get; set; }
        public string FactionName { get; set; }
        public string FactionDef { get; set; }
        public string Relation { get; set; }
        public int Goodwill { get; set; }
        public float ApproximateDistanceTiles { get; set; }
        public bool CanTradeNow { get; set; }
        public bool EverVisited { get; set; }
        public bool StockKnowledgeMayBeStale { get; set; }
        public string TraderKind { get; set; }
        public bool WillBuyHumanlikePrisoners { get; set; }
        public System.Collections.Generic.List<KnownTradeItemDto> KnownStock { get; set; }
    }

    public class RaidDestinationDto
    {
        public int SettlementId { get; set; }
        public string Name { get; set; }
        public int Tile { get; set; }
        public string FactionName { get; set; }
        public string Relation { get; set; }
        public int Goodwill { get; set; }
        public string TechLevel { get; set; }
        public float ApproximateDistanceTiles { get; set; }
        public int EstimatedDefendersMin { get; set; }
        public int EstimatedDefendersMax { get; set; }
        public System.Collections.Generic.List<string> LikelyPawnKinds { get; set; }
        public System.Collections.Generic.List<string> LikelyWeaponTags { get; set; }
        public System.Collections.Generic.List<string> LikelyApparelTags { get; set; }
        public System.Collections.Generic.List<string> PossibleLoot { get; set; }
        public float EstimatedLootValue { get; set; }
        public bool WouldStartWar { get; set; }
    }

    public class StartRaidCaravanRequestDto : ExpeditionRequestDto { }

    public class StartTradeCaravanResponseDto
    {
        public bool Applied { get; set; }
        public string FormationId { get; set; }
        public string Status { get; set; }
        public int DestinationSettlementId { get; set; }
        public string DestinationName { get; set; }
        public int DestinationTile { get; set; }
        public int PawnCount { get; set; }
        public int GoodsStacks { get; set; }
        public int FoodCount { get; set; }
        public float ApproximateGoodsValue { get; set; }
        public int PrisonerCount { get; set; }
        public System.Collections.Generic.List<string> PurchasePriorities { get; set; }
    }
}

using System.Collections.Generic;

namespace RIMAPI.Models
{
    public class EventCatalogDto
    {
        public string DefName { get; set; }
        public string Label { get; set; }
        public string Description { get; set; }
        public string Category { get; set; }
        public string Worker { get; set; }
        public string GameCondition { get; set; }
        public string QuestScript { get; set; }
        public bool IsAnomalyIncident { get; set; }
        public bool Hidden { get; set; }
        public int EarliestDay { get; set; }
        public int MinimumPopulation { get; set; }
        public string Mod { get; set; }
        public List<string> Tags { get; set; } = new List<string>();
    }

    public class ActiveConditionDto
    {
        public int Id { get; set; }
        public string DefName { get; set; }
        public string Label { get; set; }
        public string Description { get; set; }
        public int StartedTick { get; set; }
        public int TicksLeft { get; set; }
        public bool Permanent { get; set; }
        public bool ElectricityDisabled { get; set; }
        public float TemperatureOffset { get; set; }
    }

    public class EventLetterDto
    {
        public int Id { get; set; }
        public string Label { get; set; }
        public string Text { get; set; }
        public string LetterDef { get; set; }
        public int ArrivalTick { get; set; }
        public List<string> EnabledOptions { get; set; } = new List<string>();
    }

    public class LetterChoiceRequestDto
    {
        public int LetterId { get; set; }
        public string OptionLabel { get; set; }
        public string LetterText { get; set; }
    }

    public class KidnappedPawnDto
    {
        public int Id { get; set; }
        public string Name { get; set; }
        public string Faction { get; set; }
        public float Health { get; set; }
        public bool IsKidnapped { get; set; }
        public string Holder { get; set; }
    }

    public class QuestTargetDto
    {
        public int? WorldObjectId { get; set; }
        public int? ThingId { get; set; }
        public int? Tile { get; set; }
        public string Label { get; set; }
        public string WorldObjectType { get; set; }
        public float EstimatedThreatPoints { get; set; }
    }

    public class EventContextDto
    {
        public int MapId { get; set; }
        public int GameTick { get; set; }
        public List<IncidentDto> RecentIncidents { get; set; } = new List<IncidentDto>();
        public List<ActiveConditionDto> ActiveConditions { get; set; } = new List<ActiveConditionDto>();
        public List<QuestDto> ActiveQuests { get; set; } = new List<QuestDto>();
        public List<EventLetterDto> Letters { get; set; } = new List<EventLetterDto>();
        public List<KidnappedPawnDto> KidnappedPawns { get; set; } = new List<KidnappedPawnDto>();
        public List<LiveTraderDto> TradeOpportunities { get; set; } = new List<LiveTraderDto>();
    }

    public class QuestActionRequestDto
    {
        public int QuestId { get; set; }
        public int? AccepterPawnId { get; set; }
    }

    public class RescueMissionRequestDto
    {
        public int MapId { get; set; }
        public int QuestId { get; set; }
        public int? SiteId { get; set; }
        public int MinimumHomeDefenders { get; set; } = 2;
        public int MinimumFoodAtHome { get; set; } = 30;
        public int MinimumMedicineAtHome { get; set; } = 8;
    }

    public class RescueSiteRequestDto
    {
        public int MapId { get; set; }
    }

    public class RescueSiteStatusDto
    {
        public int MapId { get; set; }
        public bool IsTemporaryMap { get; set; }
        public bool ActiveThreat { get; set; }
        public List<int> RescuerPawnIds { get; set; } = new List<int>();
        public List<int> CaptivePawnIds { get; set; } = new List<int>();
        public List<string> CaptiveNames { get; set; } = new List<string>();
        public bool CanReturnHome { get; set; }
    }
}

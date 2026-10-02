using System.Collections.Generic;
namespace RIMAPI.Models {
    // Preview is read-only; the same policy plus exact selection is required at start.
    public class ExpeditionRequestDto {
        public string Mode { get; set; }
        public int MapId { get; set; }
        public int DestinationSettlementId { get; set; }
        public int QuestId { get; set; }
        public int? SiteId { get; set; }
        public int MinimumHomeDefenders { get; set; } = 2;
        // Legacy field explicitly remains a number of MealSurvivalPack/Pemmican items.
        public int MinimumFoodAtHome { get; set; } = 30;
        public int MinimumMedicineAtHome { get; set; } = 8;
        public float MarginDays { get; set; } = 2f;
        public bool AllowStartingWar { get; set; }
        public List<string> SaleCategories { get; set; }
        public List<string> PurchasePriorities { get; set; }
        public List<int> PrisonerIds { get; set; }
        public bool Confirmed { get; set; }
        public string Essentials { get; set; }
        public List<int> PawnIds { get; set; }
        public List<int> HomePawnIds { get; set; }
        public List<ExpeditionManifestItem> Manifest { get; set; }
    }
    public class ExpeditionManifestItem {
        public int ThingId { get; set; }
        public string DefName { get; set; }
        public int Count { get; set; }
    }
    public class ExpeditionPlanDto {
        public string PlanId, Mode, DestinationName, Essentials, EstimateReason, Consequences;
        public int MapId, TargetId, QuestId, HomeFoodItems, MinimumHomeFoodItems, HomeMedicine, HomeDefenders;
        public List<int> PawnIds, HomePawnIds;
        public List<string> Travelers, Prisoners;
        public List<object> Diets;
        public List<ExpeditionManifestItem> Manifest;
        public float FoodNutrition, DailyNutrition, FoodDays, OutboundDays, ReturnDays, MarginDays, FoodMarginDays;
        public float HomeFoodNutrition, MinimumHomeFoodNutrition, Mass, Capacity, CarriedGearMass;
    }
    public class ExpeditionPreviewDto {
        public List<ExpeditionPlanDto> Plans = new List<ExpeditionPlanDto>();
        public List<string> Blockers = new List<string>();
        public object Pending, LastResult;
        public Dictionary<string, object> Readiness = new Dictionary<string, object>();
        public string Warning = "Native ETA excludes formation, combat and future incidents; both legs plus chosen margin are packed. Food policy is checked for every traveler including prisoners. No foraging credit or animals; rottable ration life is conservatively checked at 40C. minimum_food_at_home remains item units, with conversion shown separately.";
    }
}

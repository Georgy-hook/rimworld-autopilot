using System.Collections.Generic;

namespace RIMAPI.Models
{
    public class BuildingCatalogDto
    {
        public string DefName { get; set; }
        public string ConstructionKind { get; set; } = "building";
        public string Label { get; set; }
        public string Description { get; set; }
        public string DesignationCategory { get; set; }
        public List<string> ResearchPrerequisites { get; set; }
        public bool AvailableNow { get; set; }
        public List<ThingCostDto> CostList { get; set; }
        public int CostStuffCount { get; set; }
        public List<string> StuffCategories { get; set; }
        public List<string> AllowedStuffDefs { get; set; }
        public string MetadataError { get; set; }
        public int SizeX { get; set; }
        public int SizeZ { get; set; }
        public bool IsWorkTable { get; set; }
        public bool IsBed { get; set; }
        public bool RequiresPower { get; set; }
        public bool IsPowerGenerator { get; set; }
        public bool RequiresFuel { get; set; }
        public float NominalPowerOutput { get; set; }
        public float NominalPowerConsumption { get; set; }
        public float GrowthLightRadius { get; set; }
        public int MinimumConstructionSkill { get; set; }
        public float LightRadius { get; set; }
        public List<string> BuildingTags { get; set; }
        public List<string> RecipeSkills { get; set; }
    }

    public class RoyaltyContextDto
    {
        public bool Active { get; set; }
        public List<RoyalPawnContextDto> Colonists { get; set; } = new List<RoyalPawnContextDto>();
    }

    public class RoyalPawnContextDto
    {
        public int PawnId { get; set; }
        public string PawnName { get; set; }
        public string TitleDefName { get; set; }
        public string TitleLabel { get; set; }
        public int Seniority { get; set; }
        public bool RequiresThroneRoom { get; set; }
        public bool HasUnmetThroneRoomRequirements { get; set; }
        public bool RequiresBedroom { get; set; }
        public bool HasUnmetBedroomRequirements { get; set; }
        public float MinimumThroneRoomImpressiveness { get; set; }
        public int MinimumThroneRoomArea { get; set; }
        public List<string> ThroneRoomRequirementTypes { get; set; }
        public List<string> ThroneRoomRequirements { get; set; }
    }
}

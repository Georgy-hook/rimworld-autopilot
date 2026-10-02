using System.Collections.Generic;

namespace RIMAPI.Models
{
    public class CapabilityOrderResultDto
    {
        public bool Applied { get; set; }
        public string Reason { get; set; }
        public int? TargetId { get; set; }
        public int AffectedCount { get; set; }
    }
    public class PlantCatalogContextDto
    {
        public string Biome { get; set; }
        public int DayOfYear { get; set; }
        public List<PlantCapabilityDto> Plants { get; set; } = new List<PlantCapabilityDto>();
        public List<GrowerCapabilityDto> Growers { get; set; } = new List<GrowerCapabilityDto>();
    }
    public class PlantCapabilityDto
    {
        public string DefName { get; set; }
        public string Label { get; set; }
        public string Description { get; set; }
        public string Category { get; set; }
        public string HarvestedThing { get; set; }
        public float HarvestYield { get; set; }
        public float ProductNutrition { get; set; }
        public bool HumanEdibleProduct { get; set; }
        public float GrowDays { get; set; }
        public float CalendarDaysAtNormalFertility { get; set; }
        public float FertilityMin { get; set; }
        public float FertilitySensitivity { get; set; }
        public float MinGrowthTemperature { get; set; }
        public float MaxGrowthTemperature { get; set; }
        public float GrowMinGlow { get; set; }
        public bool DiesToLight { get; set; }
        public bool RequiresPermanentDarkness { get; set; }
        public bool DiesIfLeafless { get; set; }
        public bool Blightable { get; set; }
        public string Pollution { get; set; }
        public int MinimumSkill { get; set; }
        public bool Sowable { get; set; }
        public bool NativeInBiome { get; set; }
        public bool BiomeAllowed { get; set; }
        public bool ResearchUnlocked { get; set; }
        public List<string> SowTags { get; set; } = new List<string>();
        public List<string> ResearchPrerequisites { get; set; } = new List<string>();
    }
    public class GrowerCapabilityDto
    {
        public string Id { get; set; }
        public string Kind { get; set; }
        public int? ZoneId { get; set; }
        public int? BuildingId { get; set; }
        public string PlantDef { get; set; }
        public bool AllowSow { get; set; }
        public bool Roofed { get; set; }
        public bool Powered { get; set; }
        public int PlantCount { get; set; }
        public int CellCount { get; set; }
        public int BlightedCount { get; set; }
        public PositionDto PointA { get; set; }
        public PositionDto PointB { get; set; }
        public List<PlantSiteCapabilityDto> Options { get; set; } = new List<PlantSiteCapabilityDto>();
    }
    public class PlantSiteCapabilityDto
    {
        public string DefName { get; set; }
        public int LegalCells { get; set; }
        public int TemperateCells { get; set; }
        public int LightSuitableCells { get; set; }
        public float Fertility { get; set; }
        public float Temperature { get; set; }
        public float CalendarDaysToHarvestEstimate { get; set; }
        public float? OutdoorWarmDaysEstimate { get; set; }
        public bool SafeSowingNow { get; set; }
        public string Reason { get; set; }
    }
    public class SetCropRequestDto
    {
        public int MapId { get; set; }
        public int? ZoneId { get; set; }
        public int? BuildingId { get; set; }
        public string PlantDef { get; set; }
    }
    public class CutBlightRequestDto
    {
        public int MapId { get; set; }
        public List<int> PlantIds { get; set; } = new List<int>();
        public int WorkerPawnId { get; set; }
    }
    public class AnimalTrainableDto
    {
        public string DefName { get; set; }
        public string Label { get; set; }
        public bool CanTrain { get; set; }
        public bool Wanted { get; set; }
        public bool Learned { get; set; }
        public string Reason { get; set; }
    }
    public class AnimalTrainingRequestDto
    {
        public int MapId { get; set; }
        public int AnimalId { get; set; }
        public string TrainableDef { get; set; }
        public bool Wanted { get; set; } = true;
        public int? HandlerPawnId { get; set; }
        public int? MasterPawnId { get; set; }
        public bool? FollowDrafted { get; set; }
    }
    public class ReleaseAnimalsRequestDto
    {
        public int MapId { get; set; }
        public int MasterPawnId { get; set; }
        public bool Release { get; set; }
    }
    public class AugmentationContextDto
    {
        public List<AugmentationRecipeDto> Catalog { get; set; } = new List<AugmentationRecipeDto>();
        public List<AugmentationOptionDto> Options { get; set; } = new List<AugmentationOptionDto>();
    }
    public class AugmentationRecipeDto
    {
        public List<string> Benefits { get; set; } = new List<string>();
        public string RecipeDef { get; set; }
        public string Label { get; set; }
        public string Description { get; set; }
        public string HediffDef { get; set; }
        public List<string> ImplantDefs { get; set; } = new List<string>();
        public float? PartEfficiency { get; set; }
        public float SurgerySuccessFactor { get; set; }
        public bool ResearchUnlocked { get; set; }
    }
    public class AugmentationOptionDto
    {
        public string PatientContext { get; set; }
        public List<string> PatientBeliefs { get; set; } = new List<string>();
        public string PatientRole { get; set; }
        public List<string> MedicineOptions { get; set; } = new List<string>();
        public Dictionary<string, int> ImplantStock { get; set; } = new Dictionary<string, int>();
        public int PatientPawnId { get; set; }
        public string Patient { get; set; }
        public string RecipeDef { get; set; }
        public string Label { get; set; }
        public int BodyPartIndex { get; set; }
        public string BodyPart { get; set; }
        public string CurrentImplant { get; set; }
        public float CurrentEfficiency { get; set; }
        public float? NewEfficiency { get; set; }
        public List<string> ImplantDefs { get; set; } = new List<string>();
        public List<string> MissingIngredients { get; set; } = new List<string>();
        public List<int> DoctorIds { get; set; } = new List<int>();
        public List<int> BedIds { get; set; } = new List<int>();
        public Dictionary<int, string> DoctorDetails { get; set; } = new Dictionary<int, string>();
        public Dictionary<int, string> BedDetails { get; set; } = new Dictionary<int, string>();
        public bool AlreadyQueued { get; set; }
        public bool Ready { get; set; }
        public string Reason { get; set; }
        public string Risk { get; set; }
    }
    public class AugmentationRequestDto
    {
        public int MapId { get; set; }
        public int PatientPawnId { get; set; }
        public int DoctorPawnId { get; set; }
        public int BedId { get; set; }
        public string RecipeDef { get; set; }
        public int BodyPartIndex { get; set; }
    }
}

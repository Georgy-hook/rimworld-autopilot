using System.Collections.Generic;

namespace RIMAPI.Models
{
    // --- Request Objects ---
    public class CopyAreaRequestDto
    {
        public int MapId { get; set; }
        public PositionDto PointA { get; set; }
        public PositionDto PointB { get; set; }
    }

    public class PasteAreaRequestDto
    {
        public int MapId { get; set; }
        public PositionDto Position { get; set; } // This will be the bottom-left corner
        public BlueprintDto Blueprint { get; set; }
        public bool ClearObstacles { get; set; } = true; // Destroy existing things before pasting
    }

    public class CheckZoneRequestDto
    {
        public int MapId { get; set; }
        public PositionDto PointA { get; set; }
        public PositionDto PointB { get; set; }
    }

    public class InstallMinifiedRequestDto
    {
        public int MapId { get; set; }
        public int ThingId { get; set; }
        public PositionDto Position { get; set; }
        public int Rotation { get; set; }
    }

    public class ConfigureStorageBuildingsRequestDto
    {
        public int MapId { get; set; }
        public List<int> BuildingIds { get; set; } = new List<int>();
        public List<string> AllowedItemDefs { get; set; } = new List<string>();
        public List<string> AllowedItemCategories { get; set; } = new List<string>();
        public int Priority { get; set; } = 4;
    }

    public class ConstructionProjectDto
    {
        public int ThingId { get; set; }
        public string DefName { get; set; }
        public string Label { get; set; }
        public string Kind { get; set; }
        public string StuffDefName { get; set; }
        public float PercentComplete { get; set; }
        public int MinimumConstructionSkill { get; set; }
        public List<ConstructionMaterialDto> MaterialsNeeded { get; set; }
        public PositionDto Position { get; set; }
    }

    public class ConstructionMaterialDto
    {
        public string DefName { get; set; }
        public int RequiredCount { get; set; }
        public int AvailableCount { get; set; }
    }

    public class ConstructionProjectsDto
    {
        public List<ConstructionProjectDto> Projects { get; set; } = new List<ConstructionProjectDto>();
    }

    public class PrioritizeConstructionRequestDto
    {
        public int MapId { get; set; }
        public int ProjectThingId { get; set; }
        public int PawnId { get; set; }
    }

    public class PrioritizeConstructionResultDto
    {
        public bool Applied { get; set; }
        public string Reason { get; set; }
    }

    public class BuildingSiteOptionsRequestDto
    {
        public int MapId { get; set; }
        public string DefName { get; set; }
        public string StuffDefName { get; set; }
        public PositionDto Near { get; set; }
        public int Radius { get; set; } = 40;
        public int Limit { get; set; } = 8;
    }

    public class BuildingSiteOptionDto
    {
        public PositionDto Position { get; set; }
        public int Rotation { get; set; }
        public int Distance { get; set; }
    }

    public class BuildingSiteOptionsDto
    {
        public string DefName { get; set; }
        public string StuffDefName { get; set; }
        public string Reason { get; set; }
        public List<BuildingSiteOptionDto> Sites { get; set; } = new List<BuildingSiteOptionDto>();
    }

    // --- The Blueprint Data Structure ---
    public class BlueprintDto
    {
        public bool Roof { get; set; }
        public int Width { get; set; }
        public int Height { get; set; }
        public List<SavedTerrainDto> Floors { get; set; } = new List<SavedTerrainDto>();
        public List<SavedBuildingDto> Buildings { get; set; } = new List<SavedBuildingDto>();
    }

    public class SavedTerrainDto
    {
        public string DefName { get; set; }
        public int RelX { get; set; }
        public int RelZ { get; set; }
    }

    public class SavedBuildingDto
    {
        public string DefName { get; set; }
        public string StuffDefName { get; set; } // Material (Wood, Steel, etc)
        public int RelX { get; set; }
        public int RelZ { get; set; }
        public int Rotation { get; set; } // 0=North, 1=East, 2=South, 3=West
    }

    public class CheckZoneResultDto
    {
        public bool CanBuild { get; set; }
        public CheckZoneIssuesDto Issues { get; set; }
    }

    public class CheckZoneIssuesDto
    {
        public List<CheckZoneIssueDto> Terrain { get; set; } = new List<CheckZoneIssueDto>();
        public List<CheckZoneIssueDto> Ores { get; set; } = new List<CheckZoneIssueDto>();
        public List<CheckZoneIssueDto> Buildings { get; set; } = new List<CheckZoneIssueDto>();
        public List<CheckZoneIssueDto> Zones { get; set; } = new List<CheckZoneIssueDto>();
    }

    public class CheckZoneIssueDto
    {
        public int X { get; set; }
        public int Z { get; set; }
        public string DefName { get; set; }
        public string Label { get; set; }
        public string ZoneType { get; set; }
    }
}

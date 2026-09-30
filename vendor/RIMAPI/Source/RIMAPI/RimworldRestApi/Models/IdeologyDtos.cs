using System.Collections.Generic;

namespace RIMAPI.Models
{
    public class IdeologyBuildingDto
    {
        public string DefName { get; set; }
        public string Label { get; set; }
        public string PreceptName { get; set; }
        public int CostStuffCount { get; set; }
        public int SizeX { get; set; }
        public int SizeZ { get; set; }
    }

    public class IdeologyContextDto
    {
        public bool Active { get; set; }
        public int SlaveCount { get; set; }
        public string Name { get; set; }
        public List<string> Memes { get; set; } = new List<string>();
        public List<string> Precepts { get; set; } = new List<string>();
        public List<IdeologyBuildingDto> RitualBuildings { get; set; } = new List<IdeologyBuildingDto>();
    }
}

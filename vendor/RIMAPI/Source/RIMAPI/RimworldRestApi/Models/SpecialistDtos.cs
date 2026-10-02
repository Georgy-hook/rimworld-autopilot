using System.Collections.Generic;
namespace RIMAPI.Models
{
    public class SpecialistContextDto
    {
        public bool Available { get; set; } = true;
        public bool RoyaltyActive { get; set; }
        public bool IdeologyActive { get; set; }
        public bool BiotechActive { get; set; }
        public bool AnomalyActive { get; set; }
        public object RoyaltyContext { get; set; }
        public List<SpecialistRoyalAssignmentDto> RoyalAssignments { get; set; } = new List<SpecialistRoyalAssignmentDto>();
        public float PollutionPercent { get; set; }
        public int PollutedCells { get; set; }
        public List<SpecialistWastepackDto> Wastepacks { get; set; } = new List<SpecialistWastepackDto>();
        public List<SpecialistChargerDto> Chargers { get; set; } = new List<SpecialistChargerDto>();
        public List<SpecialistMechGroupDto> MechGroups { get; set; } = new List<SpecialistMechGroupDto>();
        public List<SpecialistEntityDto> Entities { get; set; } = new List<SpecialistEntityDto>();
        public List<SpecialistGenePawnDto> GenePawns { get; set; } = new List<SpecialistGenePawnDto>();
        public List<SpecialistPawnDto> SpecialistPawns { get; set; } = new List<SpecialistPawnDto>();
        public List<SpecialistTreeDto> DryadTrees { get; set; } = new List<SpecialistTreeDto>();
    }
    public class SpecialistWastepackDto { public int Id { get; set; } public int Count { get; set; } public bool Frozen { get; set; } public bool CanDissolveNow { get; set; } public float Temperature { get; set; } }
    public class SpecialistChargerDto { public int Id { get; set; } public string DefName { get; set; } public bool Powered { get; set; } }
    public class SpecialistMechDto { public int PawnId { get; set; } public string Name { get; set; } public float? Energy { get; set; } public string CurrentJob { get; set; } public string Kind { get; set; } }
    public class SpecialistMechGroupDto
    {
        public int MechanitorId { get; set; } public string MechanitorName { get; set; } public int GroupIndex { get; set; }
        public string Mode { get; set; } public List<string> ModeOptions { get; set; } = new List<string>();
        public List<SpecialistMechDto> Mechs { get; set; } = new List<SpecialistMechDto>();
        public float RechargeMin { get; set; } public float RechargeMax { get; set; }
    }
    public class SpecialistWorkerDto { public int PawnId { get; set; } public string Name { get; set; } public int Social { get; set; } public float SuppressionRate { get; set; } }
    public class SpecialistEntityDto
    {
        public int PlatformId { get; set; } public int EntityId { get; set; } public string Name { get; set; }
        public float Activity { get; set; } public bool SuppressionEnabled { get; set; } public float SuppressAbove { get; set; }
        public float ContainmentStrength { get; set; } public float MinimumStrength { get; set; }
        public float StudyFactor { get; set; } public string ContainmentMode { get; set; }
        public List<SpecialistWorkerDto> WorkerOptions { get; set; } = new List<SpecialistWorkerDto>();
    }
    public class SpecialistGeneResourceDto { public string DefName { get; set; } public float Level { get; set; } public float Target { get; set; } }
    public class SpecialistAbilityDto
    { public string DefName { get; set; } public bool Psycast { get; set; } public bool CanCast { get; set; } public string Reason { get; set; }
        public int Cooldown { get; set; } public float PsyfocusCost { get; set; } public float EntropyGain { get; set; } }
    public class SpecialistPermitDto { public string DefName { get; set; } public string Faction { get; set; } public int Favor { get; set; } public bool OnCooldown { get; set; } }
    public class SpecialistPawnDto
    { public int PawnId { get; set; } public string Name { get; set; } public float? Psyfocus { get; set; } public float? Entropy { get; set; }
        public string IdeologyRole { get; set; } public List<string> Rituals { get; set; } = new List<string>();
        public List<string> Titles { get; set; } = new List<string>();
        public List<SpecialistAbilityDto> Abilities { get; set; } = new List<SpecialistAbilityDto>();
        public List<SpecialistPermitDto> Permits { get; set; } = new List<SpecialistPermitDto>(); }
    public class SpecialistTreeDto { public int Id { get; set; } public int? ConnectedPawn { get; set; } public float Strength { get; set; }
        public float DesiredStrength { get; set; } public int MaxDryads { get; set; } public string Kind { get; set; } public float PruningHours { get; set; } }
    public class SpecialistGenePawnDto
    {
        public int PawnId { get; set; } public string Name { get; set; }
        public List<string> ActiveGenes { get; set; } = new List<string>();
        public List<SocietyNeedDto> Needs { get; set; } = new List<SocietyNeedDto>();
        public List<SpecialistGeneResourceDto> Resources { get; set; } = new List<SpecialistGeneResourceDto>();
        public List<string> Conditions { get; set; } = new List<string>();
    }
    public class SpecialistOrderRequestDto
    {
        public int MapId { get; set; } public string Kind { get; set; } public int? MechanitorId { get; set; }
        public int? GroupIndex { get; set; } public string Value { get; set; } public int? PlatformId { get; set; } public int? WorkerId { get; set; }
        public int? PawnId { get; set; } public int? ThingId { get; set; }
    }
    public class SpecialistRoyalAssignmentDto
    { public string Kind { get; set; } public int PawnId { get; set; } public int ThingId { get; set; } public int RoomId { get; set; } public string Label { get; set; } public string Description { get; set; } }
}

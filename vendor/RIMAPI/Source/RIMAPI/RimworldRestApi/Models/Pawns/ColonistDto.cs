using System.Collections.Generic;
using Newtonsoft.Json;

namespace RIMAPI.Models
{
    public class BodyPartsDto
    {
        public string BodyImage { get; set; }
        public string BodyColor { get; set; }
        public string HeadImage { get; set; }
        public string HeadColor { get; set; }
    }

    public class WorkInfoDto
    {
        public List<SkillDto> Skills { get; set; }
        public string CurrentJob { get; set; }
        public List<TraitDto> Traits { get; set; }
        public List<WorkPriorityDto> WorkPriorities { get; set; }
        public string InspirationDefName { get; set; }
    }

    public class TraitDto
    {
        public string Name { get; set; }
        public string Label { get; set; }
        public string Description { get; set; }
        public int DisabledWorkTags { get; set; }
        public bool Suppressed { get; set; }
    }

    public class PoliciesInfoDto
    {
        public int FoodPolicyId { get; set; }
        public int HostilityResponse { get; set; }
    }

    public class SocialInfoDto
    {
        public string Id { get; set; }
        public string Name { get; set; }
        public List<RelationDto> DirectRelations { get; set; }
        public int ChildrenCount { get; set; }
    }

    public class RelationDto
    {
        public string relationDefName { get; set; }
        public string otherPawnId { get; set; }
        public string otherPawnName { get; set; }
    }

    public class OpinionAboutPawnDto
    {
        public int Opinion { get; set; }
        public int OpinionAboutMe { get; set; }
    }

    public class MedicalInfoDto
    {
        public bool IsDead { get; set; }
        public bool IsDowned { get; set; } // True if crawling or incapacitated

        // Capacities (0.0 to 1.0+)
        public float Consciousness { get; set; }
        public float Moving { get; set; }
        public float Manipulation { get; set; }
        public float Sight { get; set; }
        public float Pain { get; set; }

        public float Health { get; set; }
        public List<HediffDto> Hediffs { get; set; }
        public int MedicalPolicyId { get; set; }
        public bool IsSelfTendAllowed { get; set; }
        public bool PatientFeedingEligible { get; set; }
        public bool PatientRawFoodAllowed { get; set; }
    }

    public class HediffDto
    {
        // Basic identification
        public int LoadId { get; set; }
        public string DefName { get; set; }
        public string Label { get; set; }
        public string LabelCap { get; set; }
        public string LabelInBrackets { get; set; }

        // Severity and stage
        public float Severity { get; set; }
        public string SeverityLabel { get; set; }
        public int CurStageIndex { get; set; }
        public string CurStageLabel { get; set; }

        // Body part information
        public string PartLabel { get; set; }
        public string PartDefName { get; set; }

        // Age and timing
        public int AgeTicks { get; set; }
        public string AgeString { get; set; }

        // Status flags
        public bool Visible { get; set; }
        public bool IsPermanent { get; set; }
        public bool IsTended { get; set; }
        public bool TendableNow { get; set; }
        public bool Bleeding { get; set; }
        public float BleedRate { get; set; }
        public bool IsLethal { get; set; }
        public bool IsCurrentlyLifeThreatening { get; set; }
        public bool CanEverKill { get; set; }
        public float? Immunity { get; set; }
        public float? LethalSeverity { get; set; }
        public float? TendQuality { get; set; }
        public int? TendTicksLeft { get; set; }

        // Source information
        public string SourceDefName { get; set; }
        public string SourceLabel { get; set; }
        public string SourceBodyPartGroupDefName { get; set; }
        public string SourceHediffDefName { get; set; }

        // Combat log
        public string CombatLogText { get; set; }

        // Additional properties
        public string TipStringExtra { get; set; }
        public float PainFactor { get; set; }
        public float PainOffset { get; set; }
    }

    public class SkillDto
    {
        public string Name { get; set; }
        public int Level { get; set; }
        public string Description { get; set; }
        public int MinLevel { get; set; }
        public int MaxLevel { get; set; }
        public string LevelDescriptor { get; set; }
        public bool PermanentlyDisabled { get; set; }
        public bool TotallyDisabled { get; set; }
        public float XpTotalEarned { get; set; }
        public float XpProgressPercent { get; set; }
        public float XpRequiredForLevelUp { get; set; }
        public float XpSinceLastLevel { get; set; }
        public int Aptitude { get; set; }
        public int Passion { get; set; }
        public int DisabledWorkTags { get; set; }
    }

    public class TraitDefDto
    {
        public string DefName { get; set; }
        public string Label { get; set; }
        public string Description { get; set; }
        public List<TraitDegreeDto> DegreeDatas { get; set; }
        public List<string> ConflictingTraits { get; set; }
        public List<string> DisabledWorkTypes { get; set; }
        public string DisabledWorkTags { get; set; }
    }

    public class TraitDegreeDto
    {
        public string Label { get; set; }
        public string Description { get; set; }
        public int Degree { get; set; }
        public Dictionary<string, int> SkillGains { get; set; }
        public List<StatModifierDto> StatOffsets { get; set; }
        public List<StatModifierDto> StatFactors { get; set; }
    }

    public class StatModifierDto
    {
        public string StatDefName { get; set; }
        public float Value { get; set; }
    }

    public class WorkPriorityDto
    {
        public string WorkType { get; set; }
        public int Priority { get; set; }
        public bool IsTotallyDisabled { get; set; }
    }

    public class PawnTimeAssignmentRequestDto
    {
        public int PawnId { get; set; }
        public int Hour { get; set; }
        public string Assignment { get; set; }
    }

    public class PawnWorkPrioritiesResponseDto
    {
        public List<PawnWorkPrioritiesDto> Pawns { get; set; } = new List<PawnWorkPrioritiesDto>();
        public int TotalPawns { get; set; }
        public string LastUpdated { get; set; }
    }

    public class PawnWorkPrioritiesDto
    {
        public int PawnId { get; set; }
        public string PawnName { get; set; }
        public List<WorkPriorityDto> WorkPriorities { get; set; } = new List<WorkPriorityDto>();
    }

    public class WorkListDto
    {
        public List<string> Work { get; set; }
    }

    public class WorkPriorityRequestDto
    {
        [JsonProperty("id")]
        public int Id { get; set; }

        [JsonProperty("work")]
        public string Work { get; set; } = "";

        [JsonProperty("priority")]
        public int Priority { get; set; }
    }

    public class ColonistsWorkPrioritiesRequestDto
    {
        [JsonProperty("priorities")]
        public List<WorkPriorityRequestDto> Priorities { get; set; } = new List<WorkPriorityRequestDto>();
    }

    public class TimeAssignmentDto
    {
        public string Name { get; set; }
    }

    public class OutfitDto
    {
        public int Id { get; set; }
        public string Label { get; set; }
        public ThingFilterDto Filter { get; set; }
    }

    public class ThingFilterDto
    {
        public List<string> AllowedThingDefNames { get; set; }
        public List<string> DisallowedSpecialFilterDefNames { get; set; }
        public float AllowedHitPointsMin { get; set; }
        public float AllowedHitPointsMax { get; set; }
        public string AllowedQualityMin { get; set; }
        public string AllowedQualityMax { get; set; }
        public bool AllowedHitPointsConfigurable { get; set; }
        public bool AllowedQualitiesConfigurable { get; set; }
    }

    public class PawnJobRequestDto
    {
        public int? MapId { get; set; }
        public bool AllowUnforbidEquip { get; set; }
        public int PawnId { get; set; }
        public string JobDef { get; set; }
        public int? TargetThingId { get; set; }
        public int? TargetThingIdB { get; set; }
        public PositionDto TargetPosition { get; set; }
    }

    public class MedicalTendRequestDto
    {
        public int PatientPawnId { get; set; }
        public int? DoctorPawnId { get; set; }
        public bool SelfTend { get; set; }
        public int? ReassignFromPatientId { get; set; }
    }

    public class MedicalBedRestRequestDto
    {
        public int PatientPawnId { get; set; }
        public int? BedBuildingId { get; set; }
    }

    public class MedicalFeedResultDto
    {
        public bool Applied { get; set; }
        public string Reason { get; set; }
        public int PatientPawnId { get; set; }
        public int? FeederPawnId { get; set; }
        public string FoodDef { get; set; }
    }

    public class MedicalFeedRequestDto
    {
        public int PatientPawnId { get; set; }
        public int? FeederPawnId { get; set; }
    }

    public class PrisonerCaptureRequestDto
    {
        public int MapId { get; set; }
        public int PrisonerPawnId { get; set; }
        public PositionDto PointA { get; set; }
        public PositionDto PointB { get; set; }
        public string Policy { get; set; }
    }

    public class PrisonerPolicyRequestDto
    {
        public int PrisonerPawnId { get; set; }
        public string Policy { get; set; }
    }

    public class PrisonerOrganPlanRequestDto
    {
        public int PrisonerPawnId { get; set; }
        public string OrganDefName { get; set; }
        public bool AllowLethal { get; set; }
    }

    public class BedConfigureRequestDto
    {
        public int MapId { get; set; }
        public PositionDto PointA { get; set; }
        public PositionDto PointB { get; set; }
        public bool Medical { get; set; }
        public bool ForPrisoners { get; set; }
    }
}

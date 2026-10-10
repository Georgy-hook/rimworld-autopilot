using System.Collections.Generic;
namespace RIMAPI.Models
{
    public class SocietyContextDto
    {
        public bool Available { get; set; } = true;
        public List<SocietyPersonDto> People { get; set; } = new List<SocietyPersonDto>();
        public Dictionary<string, int> Medicine { get; set; } = new Dictionary<string, int>();
        public List<SocietyMedicineDto> MedicineCatalog { get; set; } = new List<SocietyMedicineDto>();
        public List<SocietyNativeOptionDto> NativeOptions { get; set; } = new List<SocietyNativeOptionDto>();
        public List<object> GrowthMoments { get; set; } = new List<object>();
        public List<object> DrugPolicies { get; set; } = new List<object>();
        public List<object> MedicalRecipes { get; set; } = new List<object>();
        public object Facilities { get; set; }
    }
    public class SocietyNeedDto { public string DefName { get; set; } public float Level { get; set; } public string Description { get; set; } }
    public class SocietyMedicineDto
    {
        public string DefName { get; set; }
        public int Count { get; set; }
        public float Potency { get; set; }
        public float QualityMax { get; set; }
        public List<string> AllowedCare { get; set; } = new List<string>();
    }
    public class SocietyConditionDto
    {
        public string DefName { get; set; }
        public string Part { get; set; }
        public float Severity { get; set; }
        public float? Immunity { get; set; }
        public bool ImmunityCanDevelop { get; set; }
        public bool LifeThreatening { get; set; }
        public float? TendQuality { get; set; }
        public int? TendTicksLeft { get; set; }
    }
    public class SocietyThoughtDto { public string DefName { get; set; } public string Label { get; set; } public float MoodOffset { get; set; } }
    public class SocietyPersonDto
    {
        public int PawnId { get; set; }
        public string Name { get; set; }
        public bool Dead { get; set; }
        public bool Downed { get; set; }
        public bool Drafted { get; set; }
        public bool MentalState { get; set; }
        public string CurrentJob { get; set; }
        public float? MinorBreakThreshold { get; set; }
        public List<SocietyThoughtDto> Thoughts { get; set; } = new List<SocietyThoughtDto>();
        public bool MedicalAttention { get; set; }
        public string MedicalCare { get; set; }
        public float BleedingRate { get; set; }
        public List<string> CareOptions { get; set; } = new List<string>();
        public List<SocietyNeedDto> Needs { get; set; } = new List<SocietyNeedDto>();
        public List<SocietyConditionDto> Conditions { get; set; } = new List<SocietyConditionDto>();
        public List<string> Beliefs { get; set; } = new List<string>();
        public string Ideology { get; set; }
        public List<string> LearningDesires { get; set; } = new List<string>();
        public int MedicineSkill { get; set; }
        public int SocialSkill { get; set; }
        public bool CanDoctor { get; set; }
        public bool CanWarden { get; set; }
        public int DoctorPriority { get; set; }
        public int WardenPriority { get; set; }
        public float? Certainty { get; set; }
        public string PrisonerMode { get; set; }
        public float? Resistance { get; set; }
        public List<string> PrisonerOptions { get; set; } = new List<string>();
        public List<string> Timetable { get; set; } = new List<string>();
        public object Development { get; set; }
        public object Drugs { get; set; }
        public object Genes { get; set; }
    }
    public class SocietyPolicyRequestDto
    {
        public int MapId { get; set; }
        public int PawnId { get; set; }
        public string Kind { get; set; }
        public string Value { get; set; }
        public int? Hour { get; set; }
    }
    public class SocietyNativeOptionDto
    {
        public string Kind { get; set; }
        public int PawnId { get; set; }
        public int WorkerId { get; set; }
        public int TargetId { get; set; }
        public int LetterId { get; set; }
        public string Value { get; set; }
        public string Label { get; set; }
        public Dictionary<string,string> Effects { get; set; }
    }
    public class SocietyNativeRequestDto
    {
        public int MapId { get; set; }
        public string Kind { get; set; }
        public int PawnId { get; set; }
        public int WorkerId { get; set; }
        public int TargetId { get; set; }
        public int LetterId { get; set; }
        public string Value { get; set; }
        public int TraitIndex { get; set; } = -1;
        public List<string> SkillDefs { get; set; } = new List<string>();
    }
}

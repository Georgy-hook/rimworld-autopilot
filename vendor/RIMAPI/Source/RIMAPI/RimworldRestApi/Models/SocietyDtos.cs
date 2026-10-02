using System.Collections.Generic;
namespace RIMAPI.Models
{
    public class SocietyContextDto
    {
        public bool Available { get; set; } = true;
        public List<SocietyPersonDto> People { get; set; } = new List<SocietyPersonDto>();
        public Dictionary<string, int> Medicine { get; set; } = new Dictionary<string, int>();
    }
    public class SocietyNeedDto { public string DefName { get; set; } public float Level { get; set; } public string Description { get; set; } }
    public class SocietyConditionDto { public string DefName { get; set; } public float Severity { get; set; } public float? Immunity { get; set; } public bool LifeThreatening { get; set; } }
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
    }
    public class SocietyPolicyRequestDto
    {
        public int MapId { get; set; }
        public int PawnId { get; set; }
        public string Kind { get; set; }
        public string Value { get; set; }
        public int? Hour { get; set; }
    }
}

using System.Collections.Generic;
namespace RIMAPI.Models
{
    public class ResilienceContextDto
    {
        public bool Available { get; set; } = true;
        public List<object> Patients { get; set; } = new List<object>();
        public object Environment { get; set; }
        public List<ResilienceOptionDto> Options { get; set; } = new List<ResilienceOptionDto>();
    }
    public class ResilienceOptionDto
    {
        public string Kind { get; set; }
        public int WorkerId { get; set; }
        public int TargetId { get; set; }
        public string Giver { get; set; }
        public string Worker { get; set; }
        public string Target { get; set; }
        public int MedicineSkill { get; set; }
        public float? RoomCleanliness { get; set; }
        public float? CurrentTemperature { get; set; }
        public float? CurrentTargetTemperature { get; set; }
        public bool? PowerOn { get; set; }
        public float? SurgerySuccess { get; set; }
    }
    public class ResilienceOrderRequestDto
    {
        public int MapId { get; set; }
        public string Kind { get; set; }
        public int WorkerId { get; set; }
        public int TargetId { get; set; }
        public string Giver { get; set; }
    }
}

using System.Collections.Generic;
namespace RIMAPI.Models
{
    public class ResilienceContextDto
    {
        public bool Available { get; set; } = true;
        public List<object> Patients { get; set; } = new List<object>();
        public object Environment { get; set; }
        public List<ResilienceOptionDto> Options { get; set; } = new List<ResilienceOptionDto>();
        public List<ActiveNativeOrderDto> ActiveOrders { get; set; } = new List<ActiveNativeOrderDto>();
    }
    public class ActiveNativeOrderDto
    {
        public string Kind { get; set; }
        public int WorkerId { get; set; }
        public int TargetId { get; set; }
        public string JobDef { get; set; }
        public int? CarriedThingId { get; set; }
    }
    public class ResilienceOptionDto
    {
        public string ExpectedCurrentJob { get; set; }
        public int? ExpectedCarePatientId { get; set; }
        public string CareYieldReason { get; set; }
        public bool ThermalRescue { get; set; }
        public int? BedId { get; set; }
        public float? DestinationTemperature { get; set; }
        public float? TravelDistance { get; set; }
        public float? StarvationTicks { get; set; }
        public float? MalnutritionSeverity { get; set; }
        public float? LethalMargin { get; set; }
        public string PrerequisiteReason { get; set; }
        public bool FoodFeasible { get; set; }
        public string Kind { get; set; }
        public int WorkerId { get; set; }
        public int TargetId { get; set; }
        public string Giver { get; set; }
        public string Worker { get; set; }
        public string Target { get; set; }
        public int MedicineSkill { get; set; }
        public float? MedicalTendQuality { get; set; }
        public float? MedicalTendSpeed { get; set; }
        public float? RoomCleanliness { get; set; }
        public float? CurrentTemperature { get; set; }
        public float? CurrentTargetTemperature { get; set; }
        public bool? PowerOn { get; set; }
        public float? SurgerySuccess { get; set; }
    }
    public class ResilienceOrderRequestDto
    {
        public string ExpectedCurrentJob { get; set; }
        public int? ExpectedCarePatientId { get; set; }
        public int MapId { get; set; }
        public string Kind { get; set; }
        public int WorkerId { get; set; }
        public int TargetId { get; set; }
        public string Giver { get; set; }
    }
}

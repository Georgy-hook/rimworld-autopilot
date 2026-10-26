namespace RIMAPI.Models
{
    // Deriving from the existing no-body envelope preserves the job service
    // signature while exposing an unchanged exact native job as applied=false.
    public class PawnJobInProgressResultDto : RIMAPI.Core.ApiResult
    {
        public bool Applied { get; set; }
        public bool InProgress { get; set; }
        public string Reason { get; set; }
        public int PawnId { get; set; }
        public int TargetThingId { get; set; }
    }
}

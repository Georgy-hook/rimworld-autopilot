using RIMAPI.Core;
using RIMAPI.Models;

namespace RIMAPI.Services
{
    public interface IPawnJobService
    {
        ApiResult AssignJob(PawnJobRequestDto request);
        ApiResult<MedicalTendResultDto> AssignTendJob(MedicalTendRequestDto request);
        ApiResult AssignBedRest(MedicalBedRestRequestDto request);
        ApiResult<SleepingBedResultDto> AssignSleepingBed(MedicalBedRestRequestDto request);
        ApiResult<MedicalFeedResultDto> AssignFeedJob(MedicalFeedRequestDto request);
        ApiResult AddPrisonerOrganPlan(PrisonerOrganPlanRequestDto request);
    }
}

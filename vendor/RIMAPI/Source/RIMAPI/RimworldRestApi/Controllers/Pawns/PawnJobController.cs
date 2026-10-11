using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Models;
using RIMAPI.Services;
using RIMAPI.Helpers;

namespace RIMAPI.Controllers
{
    public class PawnJobController
    {
        private readonly IPawnJobService _pawnJobService;

        public PawnJobController(IPawnJobService pawnJobService)
        {
            _pawnJobService = pawnJobService;
        }

        [Post("/api/v1/pawn/job")]
        [EndpointMetadata("Assign a job to a pawn by JobDef name, with optional target")]
        public async Task AssignJob(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<PawnJobRequestDto>();
            var result = _pawnJobService.AssignJob(body);
            await context.SendJsonResponse(result);
        }

        [Post("/api/v1/pawn/medical/tend")]
        [EndpointMetadata("Assign a doctor to tend a patient")]
        public async Task AssignTendJob(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<MedicalTendRequestDto>();
            var result = _pawnJobService.AssignTendJob(body);
            await context.SendJsonResponse(result);
        }

        [Post("/api/v1/pawn/medical/bed-rest")]
        [EndpointMetadata("Assign a pawn to bed rest, optionally specifying a bed")]
        public async Task AssignBedRest(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<MedicalBedRestRequestDto>();
            var result = _pawnJobService.AssignBedRest(body);
            await context.SendJsonResponse(result);
        }

        [Post("/api/v1/pawn/medical/feed")]
        [EndpointMetadata("Assign a colonist to feed a downed or resting patient, including colony animals")]
        public async Task AssignFeedJob(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<MedicalFeedRequestDto>();
            var result = _pawnJobService.AssignFeedJob(body);
            await context.SendJsonResponse(result);
        }

        [Post("/api/v1/pawn/bed/assign")]
        [EndpointMetadata("Claim an available ordinary sleeping bed and take a normal sleep job, preserving clinical care")]
        public async Task AssignSleepingBed(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<MedicalBedRestRequestDto>();
            var result = _pawnJobService.AssignSleepingBed(body);
            await context.SendJsonResponse(result);
        }

        [Post("/api/v1/pawn/prisoner/capture")]
        [EndpointMetadata("Capture a specific downed hostile into a completed prison and apply a normal prisoner policy")]
        public async Task CapturePrisoner(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<PrisonerCaptureRequestDto>();
            var result = PrisonerAutomationHelper.StartCapture(body);
            await context.SendJsonResponse(result);
        }

        [Post("/api/v1/pawn/prisoner/policy")]
        [EndpointMetadata("Set a normal recruit, release, or hold-for-sale prisoner interaction policy")]
        public async Task SetPrisonerPolicy(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<PrisonerPolicyRequestDto>();
            var result = PrisonerAutomationHelper.SetPolicy(body);
            await context.SendJsonResponse(result);
        }

        [Post("/api/v1/pawn/prisoner/organ-plan")]
        [EndpointMetadata("Add a validated normal surgery bill to remove one selected prisoner organ")]
        public async Task AddPrisonerOrganPlan(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<PrisonerOrganPlanRequestDto>();
            var result = _pawnJobService.AddPrisonerOrganPlan(body);
            await context.SendJsonResponse(result);
        }

        [Post("/api/v1/map/beds/configure")]
        [EndpointMetadata("Mark completed beds in an exact area as medical or prisoner beds")]
        public async Task ConfigureBeds(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<BedConfigureRequestDto>();
            var result = PrisonerAutomationHelper.ConfigureBeds(body);
            await context.SendJsonResponse(result);
        }
    }
}

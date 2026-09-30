using System;
using RIMAPI.Core;
using RIMAPI.Models;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class BuildingMaintenanceHelper
    {
        public static ApiResult<BuildingRefuelResultDto> Refuel(BuildingRefuelRequestDto request)
        {
            var result = new BuildingRefuelResultDto {
                BuildingId = request.BuildingId, WorkerPawnId = request.WorkerPawnId };
            try
            {
                var building = MapHelper.GetThingOnMapById(request.MapId, request.BuildingId) as Building;
                if (building == null || building.Faction != Faction.OfPlayer)
                    return ApiResult<BuildingRefuelResultDto>.Fail("Player building not found on the selected map.");
                var fuel = building.TryGetComp<CompRefuelable>();
                if (fuel == null)
                    return ApiResult<BuildingRefuelResultDto>.Fail("Selected building does not use fuel.");
                var worker = PawnHelper.FindPawnById(request.WorkerPawnId);
                if (worker == null || worker.Dead || worker.Downed || worker.Drafted
                    || worker.InMentalState || !worker.Spawned || worker.Map != building.Map
                    || worker.WorkTypeIsDisabled(WorkTypeDefOf.Hauling))
                    result.Reason = "no_available_hauler";
                else if (worker.CurJobDef == JobDefOf.TendPatient || worker.CurJobDef == JobDefOf.FeedPatient
                         || worker.CurJobDef == JobDefOf.Rescue)
                    result.Reason = "worker_providing_patient_care";
                else if (fuel.IsFull)
                    result.Reason = "already_fueled";
                else if (worker.CurJobDef == JobDefOf.Refuel && worker.CurJob.targetA.Thing == building)
                    result.Reason = "refueling_in_progress";
                else
                {
                    var scanner = DefDatabase<WorkGiverDef>.GetNamedSilentFail("Refuel")?.Worker as WorkGiver_Scanner;
                    Job job = scanner != null && scanner.HasJobOnThing(worker, building, true)
                        ? scanner.JobOnThing(worker, building, true) : null;
                    result.Applied = job != null && worker.jobs.TryTakeOrderedJob(job);
                    result.Reason = result.Applied ? "refuel_job_assigned" : "fuel_unavailable_or_building_reserved";
                }
                return ApiResult<BuildingRefuelResultDto>.Ok(result);
            }
            catch (Exception ex)
            {
                return ApiResult<BuildingRefuelResultDto>.Fail(ex.Message);
            }
        }
    }
}

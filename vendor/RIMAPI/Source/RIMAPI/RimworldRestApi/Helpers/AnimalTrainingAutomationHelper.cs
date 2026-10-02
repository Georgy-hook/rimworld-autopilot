using System;
using System.Collections.Generic;
using System.Linq;
using RIMAPI.Core;
using RIMAPI.Models;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class AnimalTrainingAutomationHelper
    {
        public static List<AnimalTrainableDto> Describe(Pawn animal)
        {
            if (animal.training == null) return new List<AnimalTrainableDto>();
            return DefDatabase<TrainableDef>.AllDefsListForReading.Select(td => {
                AcceptanceReport report = animal.training.CanAssignToTrain(td);
                return new AnimalTrainableDto { DefName = td.defName, Label = td.label, CanTrain = report.Accepted,
                    Reason = report.Reason, Learned = animal.training.HasLearned(td), Wanted = animal.training.GetWanted(td) };
            }).ToList();
        }
        private static bool ProvidingCare(Pawn p) => CombatNativeHelper.HasCareJob(p) || p.CurJobDef == JobDefOf.Ingest;
        public static ApiResult<CapabilityOrderResultDto> Configure(AnimalTrainingRequestDto request)
        {
            var result = new CapabilityOrderResultDto { TargetId = request.AnimalId };
            try
            {
                var map = MapHelper.GetMapByID(request.MapId);
                var animal = MapHelper.GetThingOnMapById(request.MapId, request.AnimalId) as Pawn;
                if (map == null || animal?.RaceProps.Animal != true || animal.Faction != Faction.OfPlayer || animal.Dead)
                    return ApiResult<CapabilityOrderResultDto>.Fail("Owned living animal not found.");
                if (request.MasterPawnId.HasValue)
                {
                    var master = PawnHelper.FindPawnById(request.MasterPawnId.Value);
                    if (master == null || master.Faction != Faction.OfPlayer || master.Map != map || master.Dead
                        || master.Downed || master.InMentalState || ProvidingCare(master) || master.WorkTypeIsDisabled(WorkTypeDefOf.Handling)
                        || (master.skills?.GetSkill(SkillDefOf.Animals)?.Level ?? 0) < TrainableUtility.MinimumHandlingSkill(animal)
                        || animal.training?.HasLearned(TrainableDefOf.Obedience) != true)
                    { result.Reason = "master_unavailable_or_obedience_not_learned"; return ApiResult<CapabilityOrderResultDto>.Ok(result); }
                    if (animal.playerSettings.Master == master && (!request.FollowDrafted.HasValue
                        || animal.playerSettings.followDrafted == request.FollowDrafted.Value))
                    { result.Reason = "master_policy_already_set"; return ApiResult<CapabilityOrderResultDto>.Ok(result); }
                    animal.playerSettings.Master = master;
                    if (request.FollowDrafted.HasValue) animal.playerSettings.followDrafted = request.FollowDrafted.Value;
                    result.Applied = true; result.Reason = "master_and_follow_policy_set";
                }
                if (!string.IsNullOrEmpty(request.TrainableDef))
                {
                    var td = DefDatabase<TrainableDef>.GetNamedSilentFail(request.TrainableDef);
                    if (td == null) return ApiResult<CapabilityOrderResultDto>.Fail("Trainable def not found.");
                    if (animal.training?.CanAssignToTrain(td).Accepted != true)
                    { result.Reason = "species_or_age_cannot_learn_this_training"; return ApiResult<CapabilityOrderResultDto>.Ok(result); }
                    if (animal.training.GetWanted(td) == request.Wanted)
                    { result.Reason = "training_plan_already_set"; return ApiResult<CapabilityOrderResultDto>.Ok(result); }
                    animal.training.SetWantedRecursive(td, request.Wanted);
                    result.Applied = true; result.Reason = "training_plan_set; learning_requires_handler_food_and_time";
                    var handler = request.HandlerPawnId.HasValue ? PawnHelper.FindPawnById(request.HandlerPawnId.Value) : null;
                    if (request.Wanted && handler != null && handler.Faction == Faction.OfPlayer && handler.Map == map
                        && !handler.Drafted && !handler.Downed && !handler.InMentalState && !ProvidingCare(handler)
                        && !handler.WorkTypeIsDisabled(WorkTypeDefOf.Handling)
                        && (handler.skills?.GetSkill(SkillDefOf.Animals)?.Level ?? 0) >= TrainableUtility.MinimumHandlingSkill(animal))
                    {
                        var scanner = DefDatabase<WorkGiverDef>.AllDefs.Select(d => d.Worker).OfType<WorkGiver_Train>().FirstOrDefault();
                        Job job = scanner?.JobOnThing(handler, animal, true);
                        if (job != null && handler.jobs.TryTakeOrderedJob(job)) result.Reason = "training_plan_set_and_normal_training_job_assigned";
                    }
                }
                return ApiResult<CapabilityOrderResultDto>.Ok(result);
            }
            catch (Exception ex) { return ApiResult<CapabilityOrderResultDto>.Fail(ex.ToString()); }
        }
        public static ApiResult<CapabilityOrderResultDto> Release(ReleaseAnimalsRequestDto request)
        {
            var result = new CapabilityOrderResultDto { TargetId = request.MasterPawnId };
            try
            {
                var master = PawnHelper.FindPawnById(request.MasterPawnId);
                var map = MapHelper.GetMapByID(request.MapId);
                if (master == null || master.Map != map || master.Faction != Faction.OfPlayer || master.Dead)
                    result.Reason = "master_unavailable";
                else if (request.Release && (master.Downed || master.InMentalState || ProvidingCare(master))) result.Reason = "master_unavailable_for_combat";
                else if (request.Release && !master.Drafted) result.Reason = "master_must_be_drafted";
                else
                {
                    var animals = map.mapPawns.SpawnedColonyAnimals.Where(a => !a.Dead
                        && a.playerSettings?.Master == master && a.playerSettings.followDrafted
                        && a.training?.HasLearned(TrainableDefOf.Release) == true).ToList();
                    if (request.Release && !animals.Any()) result.Reason = "no_trained_following_animals";
                    else if (request.Release && animals.Any(a => a.Downed || a.InMentalState || a.health.summaryHealth.SummaryHealthPercent < 0.8f
                        || a.health.hediffSet.BleedRateTotal > 0 || a.needs.food?.CurLevelPercentage < 0.2f))
                        result.Reason = "master_group_includes_unfit_animals";
                    else
                    {
                        master.playerSettings.animalsReleased = request.Release;
                        result.Applied = true; result.AffectedCount = animals.Count;
                        result.Reason = request.Release ? "trained_animals_released_with_master" : "animal_release_disabled";
                    }
                }
                return ApiResult<CapabilityOrderResultDto>.Ok(result);
            }
            catch (Exception ex) { return ApiResult<CapabilityOrderResultDto>.Fail(ex.ToString()); }
        }
    }
}

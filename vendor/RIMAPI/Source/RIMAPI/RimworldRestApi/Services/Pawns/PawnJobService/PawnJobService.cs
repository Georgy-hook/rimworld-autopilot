using System;
using System.Linq;
using RIMAPI.Core;
using RIMAPI.Helpers;
using RIMAPI.Models;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Services
{
    public class PawnJobService : IPawnJobService
    {
        public PawnJobService() { }

        public ApiResult AddPrisonerOrganPlan(PrisonerOrganPlanRequestDto request)
        {
            try
            {
                Pawn prisoner = PawnHelper.FindPawnById(request.PrisonerPawnId);
                if (prisoner == null || !prisoner.IsPrisonerOfColony || prisoner.Dead)
                    return ApiResult.Fail("Selected pawn is not a living colony prisoner.");
                string organ = (request.OrganDefName ?? "").Trim();
                if (!new[] { "Kidney", "Lung", "Heart", "Liver" }.Contains(organ))
                    return ApiResult.Fail("Organ must be Kidney, Lung, Heart, or Liver.");
                if (!request.AllowLethal && (organ == "Heart" || organ == "Liver"))
                    return ApiResult.Fail("Heart and liver removal require an explicit lethal plan.");
                RecipeDef recipe = DefDatabase<RecipeDef>.GetNamedSilentFail("RemoveBodyPart");
                BodyPartRecord part = recipe?.Worker?.GetPartsToApplyOn(prisoner, recipe)
                    .FirstOrDefault(p => p.def?.defName == organ);
                if (part == null || !recipe.AvailableOnNow(prisoner, part))
                    return ApiResult.Fail($"No removable {organ} is available on this prisoner.");
                HealthCardUtility.CreateSurgeryBill(prisoner, recipe, part, null, true);
                return ApiResult.Ok();
            }
            catch (Exception ex)
            {
                return ApiResult.Fail(ex.Message);
            }
        }

        public ApiResult AssignJob(PawnJobRequestDto request)
        {
            try
            {
                Pawn pawn = PawnHelper.FindPawnById(request.PawnId);
                if (pawn == null)
                {
                    return ApiResult.Fail($"Pawn not found: {request.PawnId}");
                }

                JobDef jobDef = DefDatabase<JobDef>.GetNamedSilentFail(request.JobDef);
                if (jobDef == null)
                {
                    return ApiResult.Fail($"JobDef not found: {request.JobDef}");
                }

                LocalTargetInfo target = LocalTargetInfo.Invalid;

                if (request.TargetThingId.HasValue)
                {
                    Thing thing = FindSpawnedJobTarget(pawn.Map, request.TargetThingId.Value);
                    if (thing == null)
                    {
                        return ApiResult.Fail($"Target thing not found on the worker's map: {request.TargetThingId}");
                    }
                    target = thing;
                }
                else if (request.TargetPosition != null)
                {
                    target = new IntVec3(
                        request.TargetPosition.X, 0, request.TargetPosition.Z);
                }

                Thing equipTarget = null;
                bool equipWasForbidden = false;
                if (jobDef == JobDefOf.Equip)
                {
                    equipTarget = target.Thing;
                    if (!pawn.Spawned || pawn.Map == null || pawn.Faction != Faction.OfPlayer || !pawn.IsColonistPlayerControlled
                        || pawn.Dead || pawn.Downed || pawn.InMentalState || (request.MapId.HasValue && pawn.Map.uniqueID != request.MapId.Value))
                        return ApiResult.Fail("equip_pawn_unavailable_or_map_changed");
                    if (CombatNativeHelper.HasCareJob(pawn) || pawn.CurJobDef == JobDefOf.Ingest)
                        return ApiResult.Fail("equip_protected_activity");
                    if (pawn.equipment == null || !pawn.health.capacities.CapableOf(PawnCapacityDefOf.Manipulation))
                        return ApiResult.Fail("equip_pawn_incapable_of_manipulation");
                    if (equipTarget == null || equipTarget.Map != pawn.Map || !equipTarget.Spawned
                        || equipTarget.TryGetComp<CompEquippable>() == null
                        || !EquipmentUtility.CanEquip(equipTarget, pawn, out string equipReason))
                        return ApiResult.Fail("equip_target_no_longer_compatible");
                    if (pawn.CurJobDef == JobDefOf.Equip && pawn.CurJob.targetA.Thing == equipTarget)
                        return ApiResult.Fail("equip_already_in_progress");
                    if (!pawn.CanReserveAndReach(equipTarget, PathEndMode.Touch, Danger.Some))
                        return ApiResult.Fail("equip_target_unreachable_or_reserved");
                    equipWasForbidden = equipTarget.IsForbidden(pawn);
                    if (equipWasForbidden && !request.AllowUnforbidEquip)
                        return ApiResult.Fail("equip_target_forbidden");
                }
                Job job;
                if (request.TargetThingIdB.HasValue)
                {
                    Thing thingB = FindSpawnedJobTarget(pawn.Map, request.TargetThingIdB.Value);
                    if (thingB == null)
                    {
                        return ApiResult.Fail($"Secondary target thing not found on the worker's map: {request.TargetThingIdB}");
                    }
                    job = JobMaker.MakeJob(jobDef, target, thingB);
                }
                else
                {
                    job = JobMaker.MakeJob(jobDef, target);
                }
                bool success = false;
                try
                {
                    if (equipWasForbidden) equipTarget.SetForbidden(false, false);
                    success = pawn.jobs.TryTakeOrderedJob(job);
                }
                finally
                {
                    if (!success && equipWasForbidden) equipTarget.SetForbidden(true, false);
                }
                if (!success)
                {
                    return ApiResult.Fail($"Pawn {request.PawnId} could not accept job {request.JobDef}");
                }
                return ApiResult.Ok();
            }
            catch (Exception ex)
            {
                return ApiResult.Fail(ex.Message);
            }
        }

        private static Thing FindSpawnedJobTarget(Map map, int thingId)
        {
            if (map == null) return null;
            // Pawns are indexed in mapPawns, not always in listerThings.AllThings.
            Thing thing = map.listerThings.AllThings
                .FirstOrDefault(candidate => candidate.thingIDNumber == thingId);
            if (thing != null) return thing;
            Pawn targetPawn = PawnHelper.FindPawnById(thingId);
            return targetPawn != null && targetPawn.Spawned && targetPawn.Map == map
                ? targetPawn : null;
        }

        public ApiResult AssignTendJob(MedicalTendRequestDto request)
        {
            try
            {
                Pawn patient = PawnHelper.FindPawnById(request.PatientPawnId);
                if (patient == null)
                {
                    return ApiResult.Fail($"Patient pawn not found: {request.PatientPawnId}");
                }

                Pawn doctor;
                if (request.DoctorPawnId.HasValue)
                {
                    doctor = PawnHelper.FindPawnById(request.DoctorPawnId.Value);
                    if (doctor == null)
                    {
                        return ApiResult.Fail($"Doctor pawn not found: {request.DoctorPawnId}");
                    }
                    if (doctor == patient)
                    {
                        if (!request.SelfTend || patient.Downed || patient.playerSettings == null)
                            return ApiResult.Fail("Self-tend requires a mobile colonist and an explicit self_tend request");
                        patient.playerSettings.selfTend = true;
                    }
                }
                else
                {
                    // Find the best available doctor on the same map
                    doctor = patient.Map?.mapPawns.FreeColonists
                        .Where(p => p != patient && !p.Downed && !p.Dead)
                        .OrderByDescending(p => p.skills?.GetSkill(SkillDefOf.Medicine)?.Level ?? 0)
                        .FirstOrDefault();

                    if (doctor == null)
                    {
                        return ApiResult.Fail("No available doctor found on the map");
                    }
                }

                if (patient.Dead || !patient.Spawned || doctor.Dead || doctor.Downed
                    || !doctor.Spawned || doctor.Map != patient.Map)
                    return ApiResult.Fail("Tending requires a living patient and a mobile doctor on the same map");
                if (doctor.skills?.GetSkill(SkillDefOf.Medicine)?.TotallyDisabled ?? true)
                    return ApiResult.Fail("Selected doctor is incapable of medicine");
                if (doctor.InMentalState || doctor.Drafted || doctor.WorkTypeIsDisabled(WorkTypeDefOf.Doctor)
                    || !doctor.health.capacities.CapableOf(PawnCapacityDefOf.Manipulation))
                    return ApiResult.Fail("Selected doctor is not currently controllable for treatment");
                if (doctor.CurJobDef == JobDefOf.TendPatient || doctor.CurJobDef == JobDefOf.Rescue
                    || doctor.CurJobDef == JobDefOf.FeedPatient)
                    return ApiResult.Fail("Selected doctor is already providing patient care");
                if (!doctor.CanReserveAndReach(patient, PathEndMode.Touch, Danger.Some))
                    return ApiResult.Fail("Selected doctor cannot reserve and reach the patient");
                if (!(patient.health?.hediffSet?.hediffs?.Any(h => h.TendableNow()) ?? false))
                    return ApiResult.Fail("Patient has no condition currently requiring tending");
                bool success = PawnHelper.AssignTendJob(doctor, patient);
                if (!success)
                {
                    return ApiResult.Fail("Doctor could not accept tend job");
                }
                return ApiResult.Ok();
            }
            catch (Exception ex)
            {
                return ApiResult.Fail(ex.Message);
            }
        }

        public ApiResult AssignBedRest(MedicalBedRestRequestDto request)
        {
            try
            {
                Pawn patient = PawnHelper.FindPawnById(request.PatientPawnId);
                if (patient == null)
                {
                    return ApiResult.Fail($"Patient pawn not found: {request.PatientPawnId}");
                }

                Building_Bed bed = null;
                if (request.BedBuildingId.HasValue)
                {
                    Building building = BuildingHelper.FindBuildingByID(request.BedBuildingId.Value);
                    bed = building as Building_Bed;
                    if (bed == null)
                    {
                        return ApiResult.Fail($"Bed not found: {request.BedBuildingId}");
                    }
                }

                bool success = PawnHelper.AssignBedRest(patient, bed);
                if (!success)
                {
                    return ApiResult.Fail("Patient could not be assigned to bed rest");
                }
                return ApiResult.Ok();
            }
            catch (Exception ex)
            {
                return ApiResult.Fail(ex.Message);
            }
        }

        public ApiResult<MedicalFeedResultDto> AssignFeedJob(MedicalFeedRequestDto request)
        {
            var result = new MedicalFeedResultDto { PatientPawnId = request.PatientPawnId };
            try
            {
                Pawn patient = PawnHelper.FindPawnById(request.PatientPawnId);
                if (patient == null)
                {
                    return ApiResult<MedicalFeedResultDto>.Fail($"Patient pawn not found: {request.PatientPawnId}");
                }
                if (patient.Dead || !patient.Spawned || !FeedPatientUtility.ShouldBeFed(patient))
                {
                    result.Reason = "patient_not_available_in_bed";
                    return ApiResult<MedicalFeedResultDto>.Ok(result);
                }
                if (!FeedPatientUtility.IsHungry(patient))
                {
                    result.Reason = "patient_not_hungry";
                    return ApiResult<MedicalFeedResultDto>.Ok(result);
                }

                Pawn feeder = request.FeederPawnId.HasValue
                    ? PawnHelper.FindPawnById(request.FeederPawnId.Value)
                    : patient.Map?.mapPawns.FreeColonists
                        .Where(p => p != patient && !p.Downed && !p.Dead && !p.Drafted && !p.InMentalState
                                    && (patient.RaceProps.Animal
                                        ? !p.WorkTypeIsDisabled(WorkTypeDefOf.Handling) || !p.WorkTypeIsDisabled(WorkTypeDefOf.Doctor)
                                        : !p.WorkTypeIsDisabled(WorkTypeDefOf.Doctor)))
                        .OrderByDescending(p => p.skills?.GetSkill(SkillDefOf.Medicine)?.Level ?? 0)
                        .FirstOrDefault();
                result.FeederPawnId = feeder?.thingIDNumber;
                if (feeder == null || feeder == patient || feeder.Dead || feeder.Downed || feeder.Drafted
                    || feeder.InMentalState || !feeder.Spawned || feeder.Map != patient.Map
                    || (!patient.RaceProps.Animal && feeder.WorkTypeIsDisabled(WorkTypeDefOf.Doctor))
                    || (patient.RaceProps.Animal && feeder.WorkTypeIsDisabled(WorkTypeDefOf.Doctor)
                        && feeder.WorkTypeIsDisabled(WorkTypeDefOf.Handling)))
                {
                    result.Reason = "no_available_feeder";
                    return ApiResult<MedicalFeedResultDto>.Ok(result);
                }
                if (feeder.CurJobDef == JobDefOf.FeedPatient && feeder.CurJob.targetB.Thing == patient)
                {
                    result.Reason = "feeding_in_progress";
                    return ApiResult<MedicalFeedResultDto>.Ok(result);
                }
                if (feeder.CurJobDef == JobDefOf.TendPatient || feeder.CurJobDef == JobDefOf.Rescue
                    || feeder.CurJobDef == JobDefOf.FeedPatient)
                {
                    result.Reason = "feeder_providing_patient_care";
                    return ApiResult<MedicalFeedResultDto>.Ok(result);
                }

                WorkGiverDef giverDef = DefDatabase<WorkGiverDef>.GetNamedSilentFail(
                    patient.RaceProps?.Animal == true ? "DoctorFeedAnimals" : "DoctorFeedHumanlikes"
                );
                WorkGiver_Scanner scanner = giverDef?.Worker as WorkGiver_Scanner;
                Job job = scanner != null && scanner.HasJobOnThing(feeder, patient, true)
                    ? scanner.JobOnThing(feeder, patient, true) : null;
                if (job == null && patient.RaceProps?.Animal == true)
                {
                    giverDef = DefDatabase<WorkGiverDef>.GetNamedSilentFail("HandlingFeedPatientAnimals");
                    scanner = giverDef?.Worker as WorkGiver_Scanner;
                    job = scanner != null && scanner.HasJobOnThing(feeder, patient, true)
                        ? scanner.JobOnThing(feeder, patient, true) : null;
                }
                if (job == null)
                {
                    result.Reason = "no_eligible_food_or_patient_reserved";
                    return ApiResult<MedicalFeedResultDto>.Ok(result);
                }
                if (!feeder.jobs.TryTakeOrderedJob(job))
                {
                    result.Reason = "feeder_could_not_accept_job";
                    return ApiResult<MedicalFeedResultDto>.Ok(result);
                }
                result.Applied = true;
                result.Reason = "feeding_job_assigned";
                result.FoodDef = job.targetA.Thing?.def.defName;
                return ApiResult<MedicalFeedResultDto>.Ok(result);
            }
            catch (Exception ex)
            {
                return ApiResult<MedicalFeedResultDto>.Fail(ex.Message);
            }
        }
    }
}

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

                if (request.CancelFinishingTargetId.HasValue)
                {
                    if (!request.MapId.HasValue || !pawn.Spawned || pawn.Map == null
                        || pawn.Map.uniqueID != request.MapId.Value || !pawn.IsColonistPlayerControlled
                        || pawn.Faction != Faction.OfPlayer || pawn.Dead
                        || pawn.CurJobDef != JobDefOf.AttackMelee || !pawn.CurJob.killIncappedTarget
                        || pawn.CurJob.targetA.Thing?.thingIDNumber != request.CancelFinishingTargetId.Value)
                        return ApiResult.Fail("finishing_cancel_job_or_map_changed");
                    pawn.jobs.EndCurrentJob(JobCondition.InterruptForced);
                    return ApiResult.Ok();
                }

                JobDef jobDef = DefDatabase<JobDef>.GetNamedSilentFail(request.JobDef);
                if (jobDef == null)
                {
                    return ApiResult.Fail($"JobDef not found: {request.JobDef}");
                }

                bool attackJob = jobDef == JobDefOf.AttackMelee || jobDef == JobDefOf.AttackStatic
                    || (jobDef.driverClass != null &&
                        (typeof(JobDriver_AttackMelee).IsAssignableFrom(jobDef.driverClass)
                         || typeof(JobDriver_AttackStatic).IsAssignableFrom(jobDef.driverClass)));
                if (attackJob && pawn.WorkTagIsDisabled(WorkTags.Violent))
                    return ApiResult.Fail("attack_incapable_of_violence");
                if (request.RequestDraftForFinishing && !request.KillIncappedTarget)
                    return ApiResult.Fail("draft_for_finishing_requires_explicit_finish");
                if (request.KillIncappedTarget && jobDef != JobDefOf.AttackMelee)
                    return ApiResult.Fail("finish_downed_requires_attack_melee");

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

                if (attackJob && target.Thing is Pawn alliedTarget && MentalSafetyHelper.Allied(alliedTarget)
                    && !MentalSafetyHelper.ActiveAlliedAggressor(alliedTarget))
                    return ApiResult.Fail("allied_attack_target_no_longer_active");
                if (attackJob && (CombatNativeHelper.HasClinicalCareJob(pawn) || CombatNativeHelper.HasCareRetreat(pawn)))
                    return ApiResult.Fail("attack_patient_care_owned; use exact caregiver_retreat to suspend care");

                if (request.KillIncappedTarget)
                {
                    if (!request.MapId.HasValue || !pawn.Spawned || pawn.Map == null
                        || pawn.Map.uniqueID != request.MapId.Value || pawn.Faction != Faction.OfPlayer
                        || !pawn.IsColonistPlayerControlled || pawn.Dead || pawn.Downed
                        || pawn.InMentalState || (!pawn.Drafted && !request.RequestDraftForFinishing))
                        return ApiResult.Fail("finish_downed_actor_unavailable_or_map_changed");
                    Pawn victim = target.Thing as Pawn;
                    if (victim == null || victim == pawn || !victim.Spawned || victim.Map != pawn.Map
                        || victim.Dead || !victim.Downed || MentalSafetyHelper.Allied(victim)
                        || !victim.HostileTo(Faction.OfPlayer) || victim.Position.Fogged(pawn.Map))
                        return ApiResult.Fail("finish_downed_target_no_longer_eligible");
                    if (CombatNativeHelper.HasCareJob(pawn) || pawn.CurJobDef == JobDefOf.Ingest)
                        return ApiResult.Fail("finish_downed_protected_activity");
                    // Read native eligibility without invoking its order-producing delegate.
                    // This checks violence, melee verb, reach and faction/ideology constraints.
                    if (FloatMenuUtility.GetMeleeAttackAction(pawn, target, out string failReason, ignoreControlled: true) == null)
                        return ApiResult.Fail("finish_downed_native_unavailable: " + failReason);
                    if (pawn.Drafted && pawn.CurJobDef == JobDefOf.AttackMelee && pawn.CurJob.targetA.Thing == victim)
                    {
                        // JobIsSameAs ignores this flag: TryTakeOrderedJob would
                        // accept the new job while retaining the old false flag.
                        // Upgrade this already validated explicit target in place.
                        if (!pawn.CurJob.killIncappedTarget) pawn.CurJob.killIncappedTarget = true;
                        return ApiResult.Ok();
                    }
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
                if (request.KillIncappedTarget) job.killIncappedTarget = true;
                // Ordered jobs need the same pickup counts as native workgivers.
                // JobMaker's default -1 reached Toils_Ingest/Rescue in the failed
                // run and logged invalid count warnings instead of a valid batch.
                if (jobDef == JobDefOf.Ingest)
                {
                    Thing food = target.Thing;
                    if (food == null || food.def.ingestible == null || !food.IngestibleNow)
                        return ApiResult.Fail("ingest_target_not_edible");
                    float nutrition = FoodUtility.GetNutrition(pawn, food, food.def);
                    job.count = FoodUtility.WillIngestStackCountOf(pawn, food.def, nutrition);
                    if (job.count <= 0) return ApiResult.Fail("ingest_no_food_required");
                }
                else if (jobDef == JobDefOf.Rescue)
                {
                    job.count = 1;
                }
                bool draftedHere = request.KillIncappedTarget && request.RequestDraftForFinishing && !pawn.Drafted;
                bool success = false;
                try
                {
                    if (draftedHere) pawn.drafter.Drafted = true;
                    if (equipWasForbidden) equipTarget.SetForbidden(false, false);
                    success = attackJob ? MentalSafetyHelper.TakeDefenceOrder(pawn,job) : pawn.jobs.TryTakeOrderedJob(job);
                }
                finally
                {
                    if (!success && equipWasForbidden) equipTarget.SetForbidden(true, false);
                    if (!success && draftedHere) pawn.drafter.Drafted = false;
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
                bool reassign = request.ReassignFromPatientId.HasValue;
                // Repeating the exact assignment is readback, not a new job.
                // Keep medicine pickup and tend progress, including self-tending.
                if (!reassign && doctor.CurJobDef == JobDefOf.TendPatient
                    && doctor.CurJob.targetA.Thing == patient)
                    return ApiResult.Ok();
                if (reassign)
                {
                    Pawn oldPatient = doctor.CurJob?.targetA.Thing as Pawn;
                    float rate = patient.health.hediffSet.BleedRateTotal;
                    if (doctor.CurJobDef != JobDefOf.TendPatient || oldPatient == null
                        || oldPatient.thingIDNumber != request.ReassignFromPatientId.Value || oldPatient == patient
                        || oldPatient.health.hediffSet.BleedRateTotal > 0f
                        || oldPatient.health.hediffSet.hediffs.Any(h => h.def != HediffDefOf.BloodLoss
                            && h.def != HediffDefOf.Hypothermia && h.def != HediffDefOf.Heatstroke
                            && h.def.defName != "Frostbite" && h.TendableNow()
                            && (h.IsCurrentlyLifeThreatening || h.TryGetComp<HediffComp_Immunizable>() != null
                                || h.def.lethalSeverity > 0f))
                        || rate <= 0f)
                        return ApiResult.Fail("Emergency reassignment requires the exact stable current tend patient and a different patient with active bleeding");
                }
                else if (CombatNativeHelper.HasClinicalCareJob(doctor) || CombatNativeHelper.HasCareRetreat(doctor))
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

                if (!HealthAIUtility.ShouldSeekMedicalRest(patient))
                    return ApiResult.Fail("medical_rest_not_indicated");
                if (CombatNativeHelper.HasClinicalCareJob(patient) || CombatNativeHelper.HasCareRetreat(patient))
                    return ApiResult.Fail("patient_is_providing_care; recovery must wait for current care");
                if (patient.CurJobDef == JobDefOf.Ingest)
                    return ApiResult.Fail("patient_is_eating");

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
                bool scopedYield = CareTriageHelper.CanYield(feeder,patient,"feed",request.ExpectedCurrentJob,request.ExpectedCarePatientId,out _);
                if ((request.ExpectedCurrentJob != null || request.ExpectedCarePatientId.HasValue) && !scopedYield)
                { result.Reason="care_job_or_urgency_changed"; return ApiResult<MedicalFeedResultDto>.Ok(result); }
                if (!scopedYield && (feeder.CurJobDef == JobDefOf.TendPatient || feeder.CurJobDef == JobDefOf.Rescue
                    || feeder.CurJobDef == JobDefOf.FeedPatient))
                {
                    result.Reason = "feeder_providing_patient_care";
                    return ApiResult<MedicalFeedResultDto>.Ok(result);
                }

                Job job = ResilienceAutomationHelper.NativeJob(feeder,patient,"feed",
                    patient.RaceProps.Animal ? "DoctorFeedAnimals" : "DoctorFeedHumanlikes",
                    request.ExpectedCurrentJob,request.ExpectedCarePatientId);
                if (job == null && patient.RaceProps.Animal && !scopedYield)
                    job=ResilienceAutomationHelper.NativeJob(feeder,patient,"feed","HandlingFeedPatientAnimals");
                if (job == null)
                {
                    result.Reason = "no_eligible_food_or_patient_reserved";
                    return ApiResult<MedicalFeedResultDto>.Ok(result);
                }
                if (!feeder.jobs.TryTakeOrderedJob(job) || !CareTriageHelper.Matches(feeder,job,patient))
                {
                    feeder.jobs.jobQueue.RemoveAll(feeder,j=>j==job);
                    result.Reason = "feeder_could_not_accept_current_job";
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

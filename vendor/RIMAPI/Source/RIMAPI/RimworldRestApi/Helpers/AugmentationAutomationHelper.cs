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
    public static class AugmentationAutomationHelper
    {
        private static bool ImplantRecipe(RecipeDef r) => (r.addsHediff != null
            && (r.Worker is Recipe_InstallArtificialBodyPart || r.Worker is Recipe_InstallImplant)) || r.Worker is Recipe_InstallNaturalBodyPart;
        public static bool IsAugmentationItem(ThingDef item) => item != null && !item.IsStuff && DefDatabase<RecipeDef>.AllDefsListForReading
            .Any(r => ImplantRecipe(r) && ImplantDefs(r).Contains(item.defName));
        private static List<string> ImplantDefs(RecipeDef r) => r.ingredients.SelectMany(i => i.filter.AllowedThingDefs)
            .Where(d => !d.IsMedicine && d.category == ThingCategory.Item)
            .Select(d => d.defName).Distinct().ToList();
        public static string ItemSummary(ThingDef item)
        {
            var recipes = DefDatabase<RecipeDef>.AllDefsListForReading.Where(r => ImplantRecipe(r) && ImplantDefs(r).Contains(item.defName));
            return item.label + ": " + string.Join("; ", recipes.Select(r => "part efficiency " + r.addsHediff?.addedPartProps?.partEfficiency
                + "; " + string.Join(", ", r.addsHediff?.stages?.SelectMany(s => s.statOffsets ?? new List<StatModifier>())
                    .Select(s => s.stat.defName + " " + s.value) ?? Enumerable.Empty<string>()))) + "; " + item.description;
        }
        private static bool CareJob(Pawn p) => p.CurJobDef == JobDefOf.TendPatient || p.CurJobDef == JobDefOf.Rescue || p.CurJobDef == JobDefOf.FeedPatient || p.CurJobDef == JobDefOf.DoBill;
        private static bool PatientSafe(Pawn p) => p.health.hediffSet.BleedRateTotal <= 0
            && !p.InMentalState && !p.Drafted
            && !p.health.hediffSet.hediffs.Any(h => h.IsCurrentlyLifeThreatening
                || (h.TryGetComp<HediffComp_Immunizable>() is HediffComp_Immunizable immune && immune.Immunity < 1)
                || (h.def.defName == "Heatstroke" && h.Severity > 0.05f)
                || (h.def.defName == "Hypothermia" && h.Severity > 0.05f)
                || (h.def.defName == "Malnutrition" && h.Severity > 0.1f));
        private static bool Doctor(Pawn d, Pawn patient, RecipeDef recipe) => d != patient && !d.Dead && !d.Downed
            && !d.InMentalState && !d.Drafted && !CareJob(d) && !d.WorkTypeIsDisabled(WorkTypeDefOf.Doctor)
            && (recipe.skillRequirements == null || recipe.skillRequirements.All(s => s.PawnSatisfies(d)))
            && d.CanReach(patient, PathEndMode.Touch, Danger.Some);

        private static bool IngredientsReachable(Pawn doctor, Pawn patient, RecipeDef recipe, List<Thing> materials) =>
            recipe.ingredients.All(ingredient => materials.Where(t => ingredient.filter.Allows(t)
                && (!t.def.IsMedicine || MedicalCareUtility.AllowsMedicine(patient.playerSettings.medCare, t.def))
                && doctor.CanReserveAndReach(t, PathEndMode.Touch, Danger.Some))
                .GroupBy(t => t.def).Any(g => g.Sum(t => t.stackCount) >= ingredient.CountRequiredOfFor(g.Key, recipe)));

        public static ApiResult<AugmentationContextDto> Context(int mapId)
        {
            try
            {
                var map = MapHelper.GetMapByID(mapId);
                if (map == null) return ApiResult<AugmentationContextDto>.Fail("Map not found.");
                var result = new AugmentationContextDto();
                foreach (RecipeDef recipe in DefDatabase<RecipeDef>.AllDefsListForReading.Where(ImplantRecipe))
                    result.Catalog.Add(new AugmentationRecipeDto { RecipeDef = recipe.defName, Label = recipe.label,
                        Description = recipe.description, HediffDef = recipe.addsHediff?.defName, ImplantDefs = ImplantDefs(recipe),
                        PartEfficiency = recipe.addsHediff?.addedPartProps?.partEfficiency,
                        SurgerySuccessFactor = recipe.surgerySuccessChanceFactor, ResearchUnlocked = recipe.AvailableNow,
                        Benefits = (recipe.addsHediff?.stages?.SelectMany(s => s.statOffsets ?? new List<StatModifier>())
                            .Select(s => s.stat.defName + " offset " + s.value) ?? Enumerable.Empty<string>())
                            .Concat(recipe.addsHediff?.stages?.SelectMany(s => s.statFactors ?? new List<StatModifier>())
                            .Select(s => s.stat.defName + " factor " + s.value) ?? Enumerable.Empty<string>())
                            .Concat(recipe.addsHediff?.stages?.SelectMany(s => s.capMods ?? new List<PawnCapacityModifier>())
                            .Select(c => c.capacity.defName + " offset " + c.offset + " postFactor " + c.postFactor)
                            ?? Enumerable.Empty<string>()).ToList() });
                var ingredientTypes = new HashSet<string>(result.Catalog.SelectMany(r => r.ImplantDefs));
                var materials = map.listerThings.AllThings.Where(t => t.Spawned && !t.IsForbidden(Faction.OfPlayer)
                    && (t.def.IsMedicine || ingredientTypes.Contains(t.def.defName))).ToList();
                foreach (Pawn patient in map.mapPawns.FreeColonistsSpawned.Where(p => !p.Dead))
                foreach (RecipeDef recipe in patient.def.AllRecipes.Where(r => ImplantRecipe(r) && r.AvailableNow))
                foreach (BodyPartRecord part in recipe.Worker.GetPartsToApplyOn(patient, recipe))
                {
                    if (!recipe.AvailableOnNow(patient, part)) continue;
                    var option = new AugmentationOptionDto { PatientPawnId = patient.thingIDNumber, Patient = patient.LabelShortCap,
                        RecipeDef = recipe.defName, Label = recipe.label, BodyPartIndex = part?.Index ?? -1, BodyPart = part?.Label ?? "whole body",
                        CurrentImplant = part == null ? null : patient.health.hediffSet.GetDirectlyAddedPartFor(part)?.def.defName,
                        CurrentEfficiency = part == null ? 1 : PawnCapacityUtility.CalculatePartEfficiency(patient.health.hediffSet, part),
                        NewEfficiency = recipe.Worker is Recipe_InstallNaturalBodyPart ? 1f : recipe.addsHediff?.addedPartProps?.partEfficiency, ImplantDefs = ImplantDefs(recipe),
                        AlreadyQueued = patient.BillStack.Bills.OfType<Bill_Medical>().Any(b => b.recipe == recipe && b.Part == part),
                        ImplantStock = ImplantDefs(recipe).ToDictionary(name => name, name => materials
                            .Where(t => t.Spawned && t.def.defName == name && !t.IsForbidden(Faction.OfPlayer)).Sum(t => t.stackCount)),
                        PatientBeliefs = (patient.story?.traits.allTraits.Select(t => t.def.defName + ": " + t.Label) ?? Enumerable.Empty<string>())
                            .Concat(patient.Ideo?.PreceptsListForReading.Select(p => p.def.defName + ": " + p.Label) ?? Enumerable.Empty<string>()).ToList(),
                        PatientRole = "work " + string.Join(", ", DefDatabase<WorkTypeDef>.AllDefs
                            .Where(w => w.relevantSkills?.Any() == true && !patient.WorkTypeIsDisabled(w) && patient.workSettings?.GetPriority(w) > 0)
                            .OrderBy(w => patient.workSettings.GetPriority(w)).Select(w => w.defName + "=" + patient.workSettings.GetPriority(w)))
                            + "; strongest skills " + string.Join(", ", patient.skills?.skills.OrderByDescending(s => s.Level).Take(5)
                                .Select(s => s.def.defName + "=" + s.Level) ?? Enumerable.Empty<string>()),
                        PatientContext = $"{patient.LabelShortCap}; skills " + string.Join(", ", patient.skills?.skills.Select(s => s.def.defName + " " + s.Level) ?? Enumerable.Empty<string>())
                            + "; assigned work " + string.Join(", ", DefDatabase<WorkTypeDef>.AllDefs.Where(w => !patient.WorkTypeIsDisabled(w) && patient.workSettings?.GetPriority(w) > 0)
                                .Select(w => w.defName + " priority " + patient.workSettings.GetPriority(w)))
                            + "; traits " + string.Join(", ", patient.story?.traits.allTraits.Select(t => t.def.defName + ": " + t.Label) ?? Enumerable.Empty<string>())
                            + "; ideology " + (patient.Ideo?.name ?? "none") + "; precepts "
                            + string.Join(", ", patient.Ideo?.PreceptsListForReading.Select(p => p.def.defName + ": " + p.Label) ?? Enumerable.Empty<string>()),
                        Risk = "Normal surgery can fail and consume the implant; anesthesia incapacitates the patient. Check doctor surgery success, medicine, bed, light, temperature and ideology. No preliminary amputation is required." };
                    foreach (IngredientCount ingredient in recipe.ingredients)
                    {
                        var available = materials.Where(t => ingredient.filter.Allows(t) && (!t.def.IsMedicine || MedicalCareUtility.AllowsMedicine(patient.playerSettings.medCare, t.def))
                            && map.mapPawns.FreeColonistsSpawned.Any(d => Doctor(d, patient, recipe)
                                && d.CanReserveAndReach(t, PathEndMode.Touch, Danger.Some))).ToList();
                        // DoBill normally requires one sufficient type for each non-mixing ingredient.
                        if (!available.GroupBy(t => t.def).Any(g => g.Sum(t => t.stackCount) >= ingredient.CountRequiredOfFor(g.Key, recipe)))
                            option.MissingIngredients.Add(ingredient.Summary);
                    }
                    option.MedicineOptions = materials.Where(t => t.def.IsMedicine
                        && MedicalCareUtility.AllowsMedicine(patient.playerSettings.medCare, t.def))
                        .GroupBy(t => t.def).Select(g => g.Key.label + " count " + g.Sum(t => t.stackCount)
                            + "; potency " + g.First().GetStatValue(StatDefOf.MedicalPotency) + "; policy " + patient.playerSettings.medCare).ToList();
                    option.DoctorIds = map.mapPawns.FreeColonistsSpawned.Where(d => Doctor(d, patient, recipe)
                        && IngredientsReachable(d, patient, recipe, materials))
                        .OrderByDescending(d => d.GetStatValue(StatDefOf.MedicalSurgerySuccessChance)).Select(d => d.thingIDNumber).ToList();
                    option.BedIds = map.listerBuildings.allBuildingsColonist.OfType<Building_Bed>()
                        .Where(b => !b.ForPrisoners && b.Position.Roofed(map) && RestUtility.CanUseBedEver(patient, b.def)
                            && b.GetRoom()?.Temperature >= 16 && b.GetRoom()?.Temperature <= 28
                            && patient.CanReserveAndReach(b, PathEndMode.OnCell, Danger.Some))
                        .OrderByDescending(b => b.GetStatValue(StatDefOf.SurgerySuccessChanceFactor))
                        .Select(b => b.thingIDNumber).ToList();
                    option.DoctorDetails = option.DoctorIds.ToDictionary(id => id, id => {
                        var doctor = PawnHelper.FindPawnById(id);
                        return $"{doctor.LabelShortCap}: Medicine {doctor.skills?.GetSkill(SkillDefOf.Medicine)?.Level}; surgery stat {doctor.GetStatValue(StatDefOf.MedicalSurgerySuccessChance):0.00}; manipulation {doctor.health.capacities.GetLevel(PawnCapacityDefOf.Manipulation):0.00}";
                    });
                    option.BedDetails = option.BedIds.ToDictionary(id => id, id => {
                        var bed = MapHelper.GetThingOnMapById(mapId, id) as Building_Bed;
                        var room = bed.GetRoom();
                        return $"{bed.LabelShortCap}: surgery factor {bed.GetStatValue(StatDefOf.SurgerySuccessChanceFactor):0.00}; temperature {room.Temperature:0.0}; cleanliness {room.GetStat(RoomStatDefOf.Cleanliness):0.00}; light {map.glowGrid.GroundGlowAt(bed.Position):0.00}";
                    });
                    option.Ready = PatientSafe(patient) && !option.MissingIngredients.Any() && option.DoctorIds.Any() && option.BedIds.Any();
                    option.Reason = !PatientSafe(patient) ? "patient_needs_recovery_before_elective_surgery"
                        : option.MissingIngredients.Any() ? "missing_ingredients_or_medicine_policy"
                        : !option.DoctorIds.Any() ? "no_qualified_available_surgeon"
                        : !option.BedIds.Any() ? "no_reachable_roofed_temperate_bed" : "normal_surgery_available";
                    result.Options.Add(option);
                }
                return ApiResult<AugmentationContextDto>.Ok(result);
            }
            catch (Exception ex) { return ApiResult<AugmentationContextDto>.Fail(ex.ToString()); }
        }
        public static ApiResult<CapabilityOrderResultDto> Install(AugmentationRequestDto request)
        {
            var result = new CapabilityOrderResultDto { TargetId = request.PatientPawnId };
            try
            {
                var context = Context(request.MapId);
                if (!context.Success) return ApiResult<CapabilityOrderResultDto>.Fail("Cannot inspect current augmentation requirements.");
                var option = context.Data.Options.FirstOrDefault(o => o.PatientPawnId == request.PatientPawnId
                    && o.RecipeDef == request.RecipeDef && o.BodyPartIndex == request.BodyPartIndex);
                if (option == null || !option.Ready || !option.DoctorIds.Contains(request.DoctorPawnId) || !option.BedIds.Contains(request.BedId))
                { result.Reason = option?.Reason ?? "operation_no_longer_available"; return ApiResult<CapabilityOrderResultDto>.Ok(result); }
                var patient = PawnHelper.FindPawnById(request.PatientPawnId);
                var doctor = PawnHelper.FindPawnById(request.DoctorPawnId);
                var bed = MapHelper.GetThingOnMapById(request.MapId, request.BedId) as Building_Bed;
                var recipe = DefDatabase<RecipeDef>.GetNamedSilentFail(request.RecipeDef);
                var part = request.BodyPartIndex < 0 ? null : patient.RaceProps.body.AllParts.First(p => p.Index == request.BodyPartIndex);
                var bill = patient.BillStack.Bills.OfType<Bill_Medical>().FirstOrDefault(b => b.recipe == recipe && b.Part == part);
                if (doctor.CurJobDef == JobDefOf.DoBill && doctor.CurJob.targetA.Thing == patient)
                { result.Reason = "surgery_in_progress"; return ApiResult<CapabilityOrderResultDto>.Ok(result); }
                bed.Medical = true;
                if (patient.CurrentBed() != bed && !PawnHelper.AssignBedRest(patient, bed))
                { result.Reason = "patient_cannot_prepare_in_bed"; return ApiResult<CapabilityOrderResultDto>.Ok(result); }
                if (bill == null) bill = HealthCardUtility.CreateSurgeryBill(patient, recipe, part, null, true);
                bill.SetPawnRestriction(doctor);
                bill.suspended = false;
                var scanner = DefDatabase<WorkGiverDef>.AllDefs.Where(d => d.workType == WorkTypeDefOf.Doctor)
                    .Select(d => d.Worker).OfType<WorkGiver_DoBill>().FirstOrDefault();
                Job job = scanner?.JobOnThing(doctor, patient, true);
                result.Applied = true;
                result.Reason = job != null && doctor.jobs.TryTakeOrderedJob(job)
                    ? "surgery_bill_queued_and_normal_job_assigned" : "surgery_bill_queued_patient_preparing";
                return ApiResult<CapabilityOrderResultDto>.Ok(result);
            }
            catch (Exception ex) { return ApiResult<CapabilityOrderResultDto>.Fail(ex.ToString()); }
        }
    }
}

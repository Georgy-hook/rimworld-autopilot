using System;
using System.Linq;
using System.Collections.Generic;
using RimWorld;
using Verse;
using Verse.AI;
using RIMAPI.Core;
using RIMAPI.Models;
namespace RIMAPI.Helpers
{
    public static class ResilienceDiagnosisHelper
    {
        private static bool ObservableEvidence(Map map) => ModsConfig.AnomalyActive && (map.listerThings.AllThings.Any(t => t.def.defName == "GrayFleshSample" && !t.Position.Fogged(map))
            || (Find.AnalysisManager?.AnalysisDetailsForReading.Any(d => d.Satisfied) ?? false)
            || map.mapPawns.AllPawnsSpawned.Any(p => p.health.hediffSet.hediffs.Any(h => h.Visible && h.def.defName.IndexOf("Metalhorror",StringComparison.OrdinalIgnoreCase) >= 0)));
        private static bool RoutineSafe(Pawn p) => !p.Dead && !p.Downed && !p.Drafted && !p.InMentalState && p.health.hediffSet.BleedRateTotal <= 0
            && p.CurJobDef != JobDefOf.TendPatient && p.CurJobDef != JobDefOf.Rescue && p.CurJobDef != JobDefOf.FeedPatient && p.CurJobDef != JobDefOf.DoBill
            && p.CurJobDef != JobDefOf.Ingest && p.CurJobDef?.defName != "PrisonerInterrogateIdentity"
            && !p.health.hediffSet.hediffs.Any(h => h.Visible && (h.IsCurrentlyLifeThreatening || h.TendableNow()
                || (h.TryGetComp<HediffComp_Immunizable>() is HediffComp_Immunizable immune && immune.Immunity < 1)
                || h.def.defName == "Anesthetic" || h.def.defName == "Heatstroke" || h.def.defName == "Hypothermia"));
        private static bool Materials(Pawn doctor, Pawn patient, RecipeDef recipe) => recipe.ingredients.All(ingredient => patient.Map.listerThings.AllThings
            .Where(t => ingredient.filter.Allows(t) && !t.IsForbidden(doctor) && (!t.def.IsMedicine || MedicalCareUtility.AllowsMedicine(patient.playerSettings.medCare,t.def))
                && doctor.CanReserveAndReach(t,PathEndMode.Touch,Danger.Some) && ResilienceAutomationHelper.RoutineRouteSafe(doctor,t))
            .GroupBy(t => t.def).Any(g => g.Sum(t => t.stackCount) >= ingredient.CountRequiredOfFor(g.Key,recipe)));
        public static void AddOptions(Map map, ResilienceContextDto result)
        {
            if (!ObservableEvidence(map)) return;
            RecipeDef recipe=DefDatabase<RecipeDef>.GetNamedSilentFail("SurgicalInspection");
            foreach (Pawn patient in map.mapPawns.AllPawnsSpawned.Where(p => p.RaceProps.Humanlike && p.DevelopmentalStage.Adult() && (p.IsColonistPlayerControlled || p.IsPrisonerOfColony)))
            {
                if (patient.IsPrisonerOfColony && !patient.InMentalState && !patient.guest.IsInteractionEnabled(PrisonerInteractionModeDefOf.Interrogate))
                    result.Options.Add(new ResilienceOptionDto {Kind="interrogation_policy",WorkerId=0,TargetId=patient.thingIDNumber,Giver="Interrogate",Target=patient.LabelShort});
                if (recipe == null || !recipe.AvailableNow || !patient.def.AllRecipes.Contains(recipe) || !recipe.AvailableOnNow(patient,null) || !RoutineSafe(patient)
                    || patient.BillStack.Bills.Any(b => b.recipe == recipe)) continue;
                var beds=map.listerBuildings.allBuildingsColonist.OfType<Building_Bed>().Where(b => b.ForPrisoners == patient.IsPrisonerOfColony
                    && b.Position.Roofed(map) && b.GetRoom()?.Temperature >= 16 && b.GetRoom()?.Temperature <= 28
                    && RestUtility.CanUseBedEver(patient,b.def) && patient.CanReserveAndReach(b,PathEndMode.OnCell,Danger.Some))
                    .OrderByDescending(b => b == patient.CurrentBed()).ThenByDescending(b => b.GetStatValue(StatDefOf.SurgerySuccessChanceFactor)).Take(3).ToList();
                foreach (Pawn doctor in map.mapPawns.FreeColonistsSpawned.Where(d => d != patient && RoutineSafe(d) && !d.WorkTypeIsDisabled(WorkTypeDefOf.Doctor)
                    && (d.workSettings?.GetPriority(WorkTypeDefOf.Doctor) ?? 0) > 0 && d.health.capacities.CapableOf(PawnCapacityDefOf.Manipulation)
                    && (recipe.skillRequirements == null || recipe.skillRequirements.All(s => s.PawnSatisfies(d))) && d.CanReach(patient,PathEndMode.Touch,Danger.Some)
                    && ResilienceAutomationHelper.RoutineRouteSafe(d,patient)
                    && Materials(d,patient,recipe)))
                    foreach (Building_Bed bed in beds.Where(b => doctor.CanReach(b,PathEndMode.Touch,Danger.Some) && ResilienceAutomationHelper.RoutineRouteSafe(doctor,b)))
                        result.Options.Add(new ResilienceOptionDto {Kind="inspect",WorkerId=doctor.thingIDNumber,TargetId=patient.thingIDNumber,Giver=bed.thingIDNumber.ToString(),
                            Worker=doctor.LabelShort,Target=patient.LabelShort,MedicineSkill=doctor.skills?.GetSkill(SkillDefOf.Medicine)?.Level ?? 0,
                            RoomCleanliness=bed.GetRoom()?.GetStat(RoomStatDefOf.Cleanliness),CurrentTemperature=bed.Position.GetTemperature(map),SurgerySuccess=doctor.GetStatValue(StatDefOf.MedicalSurgerySuccessChance)});
            }
        }
        public static ApiResult<CapabilityOrderResultDto> Execute(ResilienceOrderRequestDto request)
        {
            Map map=MapHelper.GetMapByID(request.MapId); var result=new CapabilityOrderResultDto {TargetId=request.TargetId};
            if (map == null) return ApiResult<CapabilityOrderResultDto>.Fail("Map not found.");
            var live=new ResilienceContextDto(); AddOptions(map,live);
            if (!live.Options.Any(o => o.Kind == request.Kind && o.WorkerId == request.WorkerId && o.TargetId == request.TargetId && o.Giver == request.Giver))
            {result.Reason="diagnosis_no_longer_feasible";return ApiResult<CapabilityOrderResultDto>.Ok(result);}
            Pawn patient=MapHelper.GetThingOnMapById(request.MapId,request.TargetId) as Pawn;
            if (request.Kind == "interrogation_policy")
            {patient.guest.SetExclusiveInteraction(PrisonerInteractionModeDefOf.Interrogate);result.Applied=true;result.Reason="interrogation_enabled; normal_warden_job_required";}
            else
            {
                Pawn doctor=MapHelper.GetThingOnMapById(request.MapId,request.WorkerId) as Pawn;
                Building_Bed bed=MapHelper.GetThingOnMapById(request.MapId,int.Parse(request.Giver)) as Building_Bed;
                bool previouslyMedical=bed.Medical;bed.Medical=true;
                if (patient.CurrentBed() != bed && !PawnHelper.AssignBedRest(patient,bed))
                {bed.Medical=previouslyMedical;result.Reason="patient_cannot_prepare_in_bed";return ApiResult<CapabilityOrderResultDto>.Ok(result);}
                var bill=HealthCardUtility.CreateSurgeryBill(patient,DefDatabase<RecipeDef>.GetNamed("SurgicalInspection"),null,null,true);
                bill.SetPawnRestriction(doctor);bill.suspended=false;
                var scanner=DefDatabase<WorkGiverDef>.AllDefsListForReading.Where(d => d.workType == WorkTypeDefOf.Doctor).Select(d => d.Worker).OfType<WorkGiver_DoBill>().FirstOrDefault();
                Job job=scanner?.JobOnThing(doctor,patient,false);
                result.Applied=true;result.Reason=job != null && doctor.jobs.TryTakeOrderedJob(job) ? "inspection_bill_queued_and_normal_job_assigned; outcome_unknown" : "inspection_bill_queued_patient_preparing; outcome_unknown";
            }
            return ApiResult<CapabilityOrderResultDto>.Ok(result);
        }
    }
}

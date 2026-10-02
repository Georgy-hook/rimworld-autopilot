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
    public static class SocietyMedicalHelper
    {
        private static bool Treatment(RecipeDef r) => r.Worker is Recipe_RemoveHediff || r.Worker is Recipe_BloodTransfusion || r.Worker is Recipe_ExtractHemogen
            || r.Worker is Recipe_AdministerIngestible || r.Worker is Recipe_AdministerUsableItem || r.Worker is Recipe_RemoveBodyPart;
        private static bool Relevant(Pawn patient,RecipeDef recipe,BodyPartRecord part,Map map)
        {
            var visible=patient.health.hediffSet.hediffs.Where(h=>h.Visible).ToList();
            if(recipe.Worker is Recipe_RemoveBodyPart)return part != null && part.def.tags != null && part.def.tags.Any(t=>t.defName.IndexOf("Limb",StringComparison.OrdinalIgnoreCase)>=0)
                && visible.Any(h=>h.Part==part && (h.def.defName=="WoundInfection" || h.def.defName=="Carcinoma" || h.IsPermanent()));
            if(recipe.Worker is Recipe_RemoveHediff)return recipe.removesHediff != null && visible.Any(h=>h.def==recipe.removesHediff);
            if(recipe.Worker is Recipe_BloodTransfusion)return visible.Any(h=>h.def==HediffDefOf.BloodLoss);
            if(recipe.Worker is Recipe_ExtractHemogen)return !visible.Any(h=>h.def==HediffDefOf.BloodLoss || h.IsCurrentlyLifeThreatening || h.TendableNow())
                && map.mapPawns.AllPawnsSpawned.Any(p=>p.Faction==Faction.OfPlayer && p.genes?.GetFirstGeneOfType<Gene_Hemogen>()?.ValuePercent < .5f)
                && map.listerThings.AllThings.Where(t=>t.def==ThingDefOf.HemogenPack && !t.IsForbidden(patient)).Sum(t=>t.stackCount)<5;
            if(recipe.Worker is Recipe_AdministerIngestible || recipe.Worker is Recipe_AdministerUsableItem)
                return recipe.ingredients.Any(i=>i.filter.AllowedThingDefs.Any(d => (d.defName=="Penoxycyline" && patient.DevelopmentalStage.Adult() && patient.Downed)
                    || (d.defName=="HemogenPack" && (visible.Any(h=>h.def==HediffDefOf.BloodLoss) || patient.genes?.GetFirstGeneOfType<Gene_Hemogen>()?.ValuePercent < .5f))
                    || (d.IsDrug && visible.Any(h=>(h is Hediff_Addiction && DrugStatsUtility.GetNeed(d)!=null && h.def.chemicalNeed==DrugStatsUtility.GetNeed(d))
                        || (h is Hediff_ChemicalDependency c && c.chemical==DrugStatsUtility.GetChemical(d))))));
            return false;
        }
        private static bool Materials(Pawn doctor,Pawn patient,RecipeDef recipe) => recipe.ingredients.All(i=>patient.Map.listerThings.AllThings
            .Where(t=>i.filter.Allows(t) && !t.IsForbidden(doctor) && (!t.def.IsMedicine || MedicalCareUtility.AllowsMedicine(patient.playerSettings.medCare,t.def))
                && doctor.CanReserveAndReach(t,PathEndMode.Touch,Danger.Some) && ResilienceAutomationHelper.RoutineRouteSafe(doctor,t))
            .GroupBy(t=>t.def).Any(g=>g.Sum(t=>t.stackCount)>=i.CountRequiredOfFor(g.Key,recipe)));
        public static void AddContext(Map map,SocietyContextDto result)
        {
            var catalog=DefDatabase<RecipeDef>.AllDefsListForReading.Where(Treatment).ToList();
            result.MedicalRecipes=catalog.Select(r=>(object)new{def_name=r.defName,label=r.label,description=r.description,anesthetize=r.anesthetize,violation=r.isViolation,
                success_factor=r.surgerySuccessChanceFactor,ingredients=r.ingredients.Select(i=>i.Summary).ToList(),skills=r.skillRequirements?.Select(s=>s.skill.defName+"="+s.minLevel).ToList()}).ToList();
            foreach(Pawn patient in map.mapPawns.AllPawnsSpawned.Where(p=>p.RaceProps.Humanlike && !p.Dead && !p.Drafted && !p.InMentalState
                && (p.IsColonistPlayerControlled || p.IsPrisonerOfColony) && p.CurJobDef != JobDefOf.DoBill && p.CurJobDef != JobDefOf.TendPatient))
            foreach(RecipeDef recipe in patient.def.AllRecipes.Where(r=>Treatment(r) && r.AvailableNow))
            foreach(BodyPartRecord part in recipe.Worker.GetPartsToApplyOn(patient,recipe))
            {
                if(!recipe.AvailableOnNow(patient,part) || !Relevant(patient,recipe,part,map) || patient.BillStack.Bills.OfType<Bill_Medical>().Any(b=>b.recipe==recipe && b.Part==part))continue;
                var beds=map.listerBuildings.allBuildingsColonist.OfType<Building_Bed>().Where(b=>b.ForPrisoners==patient.IsPrisonerOfColony && b.Position.Roofed(map)
                    && b.GetRoom()?.Temperature>=16 && b.GetRoom()?.Temperature<=28 && RestUtility.IsValidBedFor(b,patient,patient,true,true,true,patient.GuestStatus)
                    && (patient.CurrentBed()==b || patient.CanReserveAndReach(b,PathEndMode.OnCell,Danger.Some)))
                    .OrderByDescending(b=>b==patient.CurrentBed()).ThenByDescending(b=>b.GetStatValue(StatDefOf.SurgerySuccessChanceFactor)).ToList();
                foreach(Pawn doctor in map.mapPawns.FreeColonistsSpawned.Where(d=>d!=patient && SocietyNativeHelper.Idle(d) && !d.WorkTypeIsDisabled(WorkTypeDefOf.Doctor)
                    && (d.workSettings?.GetPriority(WorkTypeDefOf.Doctor) ?? 0)>0 && d.health.capacities.CapableOf(PawnCapacityDefOf.Manipulation)
                    && (recipe.skillRequirements==null || recipe.skillRequirements.All(s=>s.PawnSatisfies(d))) && ResilienceAutomationHelper.RoutineRouteSafe(d,patient) && Materials(d,patient,recipe)))
                foreach(var bed in beds.Where(b=>ResilienceAutomationHelper.RoutineRouteSafe(doctor,b)))
                {
                    string condition=string.Join(",",patient.health.hediffSet.hediffs.Where(h=>h.Visible && (part==null || h.Part==part)).OrderByDescending(h=>h.IsCurrentlyLifeThreatening).Take(2).Select(h=>h.def.defName+"="+h.Severity.ToString("0.00")));
                    result.NativeOptions.Add(new SocietyNativeOptionDto{Kind="medical_recipe",PawnId=patient.thingIDNumber,WorkerId=doctor.thingIDNumber,TargetId=bed.thingIDNumber,
                        Value=recipe.defName+":"+(part?.Index ?? -1),Label=$"{patient.LabelShort}: {recipe.label} {part?.Label}; {doctor.LabelShort} in {bed.LabelShort}",
                        Effects=new Dictionary<string,string>{{"benefit",$"{condition}; {recipe.label} part={part?.Label}"},
                            {"risk",$"anesthesia={recipe.anesthetize} violation={recipe.isViolation}; failure or irreversible part loss"},
                            {"cost",$"{string.Join(",",recipe.ingredients.Select(i=>i.Summary))}; surgeon={doctor.skills?.GetSkill(SkillDefOf.Medicine)?.Level} clean={bed.GetRoom()?.GetStat(RoomStatDefOf.Cleanliness):0.00}"},
                            {"inaction","Condition persists; normal tend/medicine may still suffice"},{"uncertainty","Native surgery can fail; observe completed bill and health"}}});
                }
            }
        }
        public static ApiResult<CapabilityOrderResultDto> Execute(SocietyNativeRequestDto request)
        {
            var result=new CapabilityOrderResultDto{TargetId=request.PawnId};Map map=MapHelper.GetMapByID(request.MapId);
            if(map==null)return ApiResult<CapabilityOrderResultDto>.Fail("Map not found.");
            var live=new SocietyContextDto();AddContext(map,live);
            if(!live.NativeOptions.Any(o=>o.Kind==request.Kind && o.PawnId==request.PawnId && o.WorkerId==request.WorkerId && o.TargetId==request.TargetId && o.Value==request.Value))
            {result.Reason="medical_recipe_no_longer_feasible";return ApiResult<CapabilityOrderResultDto>.Ok(result);}
            Pawn patient=MapHelper.GetThingOnMapById(request.MapId,request.PawnId) as Pawn;Pawn doctor=MapHelper.GetThingOnMapById(request.MapId,request.WorkerId) as Pawn;
            var bed=MapHelper.GetThingOnMapById(request.MapId,request.TargetId) as Building_Bed;string[] value=request.Value.Split(':');var recipe=DefDatabase<RecipeDef>.GetNamed(value[0]);int index=int.Parse(value[1]);
            BodyPartRecord part=index<0 ? null : patient.RaceProps.body.AllParts.First(p=>p.Index==index);
            bool previouslyMedical=bed.Medical;bed.Medical=true;
            if(patient.CurrentBed()!=bed && !PawnHelper.AssignBedRest(patient,bed))
            {bed.Medical=previouslyMedical;result.Reason="patient_cannot_prepare_in_bed";return ApiResult<CapabilityOrderResultDto>.Ok(result);}
            var bill=HealthCardUtility.CreateSurgeryBill(patient,recipe,part,null,true);bill.SetPawnRestriction(doctor);bill.suspended=false;
            var scanner=DefDatabase<WorkGiverDef>.AllDefsListForReading.Where(d=>d.workType==WorkTypeDefOf.Doctor).Select(d=>d.Worker).OfType<WorkGiver_DoBill>().FirstOrDefault();
            Job job=scanner?.JobOnThing(doctor,patient,false);result.Applied=true;
            result.Reason=job!=null && doctor.jobs.TryTakeOrderedJob(job) ? "medical_bill_queued_and_normal_job_assigned; outcome_unobserved" : "medical_bill_queued_patient_preparing; outcome_unobserved";
            return ApiResult<CapabilityOrderResultDto>.Ok(result);
        }
    }
}

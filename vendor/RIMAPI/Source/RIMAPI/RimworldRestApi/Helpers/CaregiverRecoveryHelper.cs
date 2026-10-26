using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using HarmonyLib;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    // Observe a completed native tend, then allow normal need jobs for a
    // finite interval. No health/need modification, teleports or free food.
    public static class CaregiverRecoveryHelper
    {
        private sealed class Completed {public int JobId,Tick;}
        private const int MealTicks=1200,RestTicks=3600;
        private static readonly HashSet<Pawn> Issuing=new HashSet<Pawn>();
        private sealed class Window {public int Until,TotalUntil,TransitionUntil;public string Stage;public CombatJobStamp Job;public float Food,Rest;}
        private static readonly Dictionary<Pawn,Completed> Tends=new Dictionary<Pawn,Completed>();
        private static readonly Dictionary<Pawn,Window> Windows=new Dictionary<Pawn,Window>();
#if LAYA_COMBAT_LAB
        private static readonly List<object> Events=new List<object>();
        public static object Diagnostics()=>new{windows=Windows.Count,events=Events.ToArray(),completed=Tends.Select(x=>new{pawn=x.Key.thingIDNumber,job_id=x.Value.JobId,tick=x.Value.Tick}).ToArray(),medical_review=MedicalTendReviewHelper.Diagnostics(),recovery_component=Current.Game.GetComponent<CaregiverRecoveryComponent>()!=null,
            meaning="Completed native tend and observed ordinary need jobs; not a meal, sleep or recovery outcome unless needs actually change"};
#endif
        private static void Record(Pawn p,string reason)
        {
#if LAYA_COMBAT_LAB
            if(Events.Count<128)Events.Add(new{tick=Find.TickManager.TicksGame,pawn=p.thingIDNumber,reason,
                job=p.CurJobDef?.defName,job_id=p.CurJob?.loadID,food=p.needs?.food?.CurLevelPercentage,
                rest=p.needs?.rest?.CurLevelPercentage,mood=p.needs?.mood?.CurLevelPercentage,
                bleeding=p.health.hediffSet.BleedRateTotal});
#endif
        }
        public static void NativeCompleted(Pawn doctor,Pawn patient)
        {
            var job=doctor?.CurJob;
            if(doctor!=null)Record(doctor,"DoTend_post_observed_"+job?.loadID+"_finite_"+job?.endAfterTendedOnce+"_patient_"+patient?.thingIDNumber+"_target_"+job?.targetA.Thing?.thingIDNumber);
            if(job?.def!=JobDefOf.TendPatient || !job.endAfterTendedOnce || job.targetA.Thing!=patient)return;
            Tends[doctor]=new Completed{JobId=job.loadID,Tick=Find.TickManager.TicksGame};Record(doctor,"completed_tend_bound");
        }
        public static bool CompletedCare(Pawn p,int careId)=>Tends.TryGetValue(p,out var done)
            && done.JobId==careId && Find.TickManager.TicksGame-done.Tick<=180;
        private static bool Needs(Pawn p)=>(p.needs?.food?.CurLevelPercentage ?? 1f)<.35f
            || (p.needs?.rest?.CurLevelPercentage ?? 1f)<.22f;
        private static bool ClinicalWindow(Pawn doctor)
        {
            if(!CombatMedicalTransitionHelper.ThreatsClear(doctor.Map))return false;
            float budget=MealTicks+RestTicks+(CareTriageHelper.SelfTendBudgetTicks(doctor) ?? 1800f)+600f;
            foreach(var patient in doctor.Map.mapPawns.FreeColonistsSpawned.Where(p=>!p.Dead))
            {
                if(CareTriageHelper.DiseaseCareProtected(patient))return false;
                float bleed=patient.health.hediffSet.BleedRateTotal;
                if(bleed<.1f)continue;
                var limit=CareTriageHelper.BloodFunctionTicks(patient) ?? CareTriageHelper.BleedoutTicks(patient);
                if(bleed>=1.5f || !limit.HasValue || limit.Value<=budget)return false;
            }
            return true;
        }
        public static bool TryStart(Pawn doctor,Job reviewWait,int careJobId)
        {
            if(!doctor.Spawned || doctor.Dead || doctor.Downed || doctor.Drafted || doctor.InMentalState
                || doctor.CurJob!=reviewWait || doctor.jobs.jobQueue.Any() || doctor.carryTracker?.CarriedThing is Pawn
                || !Tends.TryGetValue(doctor,out var done) || done.JobId!=careJobId
                || Find.TickManager.TicksGame-done.Tick>180 || !Needs(doctor) || !ClinicalWindow(doctor)){Record(doctor,"TryStart_blocked");return false;}
            Tends.Remove(doctor);
            Job need=null;
            if((doctor.needs?.food?.CurLevelPercentage ?? 1f)<.35f
                && FoodUtility.TryFindBestFoodSourceFor(doctor,doctor,doctor.needs.food.CurCategory==HungerCategory.Starving,
                    out Thing food,out ThingDef foodDef,canRefillDispenser:false,canUseInventory:true,
                    canUsePackAnimalInventory:false,allowForbidden:false,allowCorpse:false,
                    allowSociallyImproper:false,allowHarvest:false,forceScanWholeMap:false,
                    ignoreReservations:false,calculateWantedStackCount:false,allowVenerated:true)
                && !food.def.IsDrug && (doctor.inventory.innerContainer.Contains(food)
                    || ResilienceAutomationHelper.RoutineRouteSafe(doctor,food)))
            {
                float nutrition=food.GetStatValue(StatDefOf.Nutrition);
                if(nutrition>0f)
                {
                    need=JobMaker.MakeJob(JobDefOf.Ingest,food);
                    need.count=Math.Min(food.stackCount,Math.Max(1,(int)Math.Ceiling((doctor.needs.food.MaxLevel-doctor.needs.food.CurLevel)/nutrition)));
                }
            }
            if(need==null && (doctor.needs?.rest?.CurLevelPercentage ?? 1f)<.22f)
            {
                var bed=RestUtility.FindBedFor(doctor,doctor,false,false);
                if(bed!=null && bed.Position.Roofed(doctor.Map)
                    && bed.Position.GetTemperature(doctor.Map)>=doctor.GetStatValue(StatDefOf.ComfyTemperatureMin)
                    && bed.Position.GetTemperature(doctor.Map)<=doctor.GetStatValue(StatDefOf.ComfyTemperatureMax)
                    && doctor.CanReserveAndReach(bed,PathEndMode.OnCell,Danger.Some)
                    && ResilienceAutomationHelper.RoutineRouteSafe(doctor,bed))
                {need=JobMaker.MakeJob(JobDefOf.LayDown,bed);need.expiryInterval=RestTicks;need.checkOverrideOnExpire=true;}
            }
            if(need==null){Record(doctor,"recovery_food_or_safe_bed_unavailable");return false;}
            need.playerForced=true;
            if(!Take(doctor,need))
            {Record(doctor,"recovery_need_not_observed");return false;}
            Windows[doctor]=new Window{Until=Find.TickManager.TicksGame+(doctor.CurJobDef==JobDefOf.Ingest?MealTicks:RestTicks),TotalUntil=Find.TickManager.TicksGame+MealTicks+RestTicks,Stage=doctor.CurJobDef.defName,
                Job=new CombatJobStamp(doctor.CurJob),Food=doctor.needs?.food?.CurLevelPercentage ?? 1f,
                Rest=doctor.needs?.rest?.CurLevelPercentage ?? 1f};
            Record(doctor,"completed_tend_recovery_window_opened_"+doctor.CurJobDef.defName);
            return true;
        }
        private static bool Take(Pawn p,Job job)
        {
            Issuing.Add(p);
            try{return p.jobs.TryTakeOrderedJob(job) && p.CurJobDef==job.def && p.CurJob.targetA==job.targetA;}
            finally{Issuing.Remove(p);}
        }
        // Explicit API/manual orders need not set playerForced. Observe their
        // actual native entry; normal think-tree StartJob is not an order.
        public static void Ordered(Pawn p)
        {if(p!=null && !Issuing.Contains(p) && Windows.Remove(p))Record(p,"later_order_preserved_recovery_cancelled");}
        private static bool Controllable(Pawn p)=>p!=null && p.Spawned && !p.Dead && !p.Downed && !p.Drafted
            && !p.InMentalState && Find.Maps.Contains(p.Map) && !p.jobs.jobQueue.Any() && !(p.carryTracker?.CarriedThing is Pawn);
        private static bool NativePostMealBridge(Pawn p,Window w)
        {
            int tick=Find.TickManager.TicksGame;
            return w.Stage=="Ingest" && p.CurJobDef==JobDefOf.Wait_MaintainPosture && !p.CurJob.playerForced
                && (p.needs?.food?.CurLevelPercentage ?? 0f)>w.Food+.1f && (p.needs?.rest?.CurLevelPercentage ?? 1f)<.22f
                && tick<=w.TotalUntil && (w.TransitionUntil==0 || tick<=w.TransitionUntil);
        }
        private static bool NativeRestAfterMeal(Pawn p,Window w)
        {
            if(w.Stage!="Ingest" || p.CurJobDef!=JobDefOf.LayDown || p.CurJob.playerForced
                || (p.needs?.food?.CurLevelPercentage ?? 0f)<=w.Food+.1f || Find.TickManager.TicksGame>w.TotalUntil)return false;
            var bed=p.CurJob.targetA.Thing as Building_Bed;
            return bed!=null && bed.Spawned && bed.Map==p.Map && bed.OccupiedRect().All(c=>c.Roofed(p.Map))
                && !bed.IsForbidden(p) && bed.Position.GetTemperature(p.Map)>=p.GetStatValue(StatDefOf.ComfyTemperatureMin)
                && bed.Position.GetTemperature(p.Map)<=p.GetStatValue(StatDefOf.ComfyTemperatureMax)
                && p.CanReserveAndReach(bed,PathEndMode.OnCell,Danger.Some) && ResilienceAutomationHelper.RoutineRouteSafe(p,bed);
        }
        public static bool Protected(Pawn p)
        {
            if(!Controllable(p))return false;
            if(p.CurJobDef==JobDefOf.Ingest)return true;
            if(!Windows.TryGetValue(p,out var w) || !ClinicalWindow(p))return false;
            // GETs do not end jobs or erase a pending native return boundary.
            if(w.Job.Value==p.CurJob)return Find.TickManager.TicksGame<=w.Until
                && (p.CurJobDef!=JobDefOf.LayDown || (p.needs?.rest?.CurLevelPercentage ?? 0f)<.30f);
            return NativePostMealBridge(p,w) || NativeRestAfterMeal(p,w);
        }
        private static void ReturnToCare(Pawn p,Window w)
        {
            if(w.Job.Value!=p.CurJob || !Controllable(p))return;
            // End only our exact rest. The finite own wait avoids an immediate
            // native re-selection of the same long sleep before clinical review.
            var wait=JobMaker.MakeJob(JobDefOf.Wait);wait.playerForced=true;wait.expiryInterval=180;wait.checkOverrideOnExpire=true;
            p.jobs.jobQueue.EnqueueLast(wait);Windows.Remove(p);Record(p,"finite_rest_finished_clinical_review_ready");
            p.jobs.EndCurrentJob(JobCondition.Succeeded);
        }
        public static void Tick()
        {
            foreach(var p in Windows.Keys.ToArray())
            {
                var w=Windows[p];int tick=Find.TickManager.TicksGame;
                if(!Controllable(p))
                {
                    Windows.Remove(p);Record(p,"later_queue_or_unavailable_actor");
                    if(p.Spawned && !p.Dead && !p.Downed && !p.Drafted && !p.InMentalState
                        && w.Job.Value==p.CurJob && p.CurJobDef==JobDefOf.LayDown && p.jobs.jobQueue.Any()
                        && !(p.carryTracker?.CarriedThing is Pawn))p.jobs.EndCurrentJob(JobCondition.Succeeded);
                    continue;
                }
                if(w.Job.Value!=p.CurJob)
                {
                    if(NativePostMealBridge(p,w) && ClinicalWindow(p))
                    {
                        if(w.TransitionUntil==0){w.TransitionUntil=tick+180;Record(p,"post_meal_native_posture_bridge_kept");}
                        continue;
                    }
                    if(NativeRestAfterMeal(p,w) && ClinicalWindow(p))
                    {
                        w.Stage="LayDown";w.Job=new CombatJobStamp(p.CurJob);w.Rest=p.needs.rest.CurLevelPercentage;
                        w.Until=Math.Min(w.TotalUntil,tick+RestTicks);Record(p,"post_meal_native_safe_rest_adopted");
                    }
                    else {Windows.Remove(p);Record(p,"other_job_preserved");continue;}
                }
                if(p.CurJobDef==JobDefOf.Ingest)continue; // finish a real meal
                if(p.CurJobDef==JobDefOf.LayDown && (tick>=w.Until || !ClinicalWindow(p) || p.needs.rest.CurLevelPercentage>=.30f))
                    ReturnToCare(p,w);
            }
            foreach(var p in Tends.Where(x=>!x.Key.Spawned || x.Key.Dead || Find.TickManager.TicksGame-x.Value.Tick>1800).Select(x=>x.Key).ToArray())Tends.Remove(p);
        }
    }

    [HarmonyPatch(typeof(TendUtility),nameof(TendUtility.DoTend),new[]{typeof(Pawn),typeof(Pawn),typeof(Medicine)})]
    public static class CaregiverNativeTendObservation
    {
        public static void Postfix(Pawn __0,Pawn __1)=>CaregiverRecoveryHelper.NativeCompleted(__0,__1);
    }
    [HarmonyPatch]
    public static class CaregiverLaterOrderObservation
    {
        public static MethodBase TargetMethod()=>typeof(Pawn_JobTracker).GetMethods(BindingFlags.Public|BindingFlags.Instance)
            .Single(m=>m.Name=="TryTakeOrderedJob" && m.GetParameters().Length>0 && m.GetParameters()[0].ParameterType==typeof(Job));
        public static void Prefix(Pawn ___pawn)=>CaregiverRecoveryHelper.Ordered(___pawn);
    }
    public sealed class CaregiverRecoveryComponent:GameComponent
    {
        public CaregiverRecoveryComponent(Game game){}
        public override void GameComponentTick()
        {if(Find.TickManager!=null && Find.TickManager.TicksGame%15==0)CaregiverRecoveryHelper.Tick();}
    }
}

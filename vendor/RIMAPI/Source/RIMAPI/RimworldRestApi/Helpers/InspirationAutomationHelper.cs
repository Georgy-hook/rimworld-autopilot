using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.CompilerServices;
using RIMAPI.Core;
using RIMAPI.Models;
using RimWorld;
using Verse;
using Verse.AI;
using UnityEngine;
namespace RIMAPI.Helpers {
 public static class InspirationAutomationHelper {
  // Native effects remain authoritative; unknown mod definitions are exported without invented consumption rules.
  private static float Factor(InspirationDef d,string stat) => d.statFactors?.FirstOrDefault(s=>s.stat.defName==stat)?.value ?? 1f;
  private static float Offset(InspirationDef d,string stat) => d.statOffsets?.FirstOrDefault(s=>s.stat.defName==stat)?.value ?? 0f;
  public static string Effect(InspirationDef d) {
   if(d==null)return "none";
   switch(d?.defName) {
    case "Frenzy_Work": return $"work speed x{Factor(d,"WorkSpeedGlobal"):0.###}; timed";
    case "Frenzy_Go": return $"move speed x{Factor(d,"MoveSpeed"):0.###}; timed";
    case "Frenzy_Shoot": return $"shooting accuracy offset {Offset(d,"ShootingAccuracyPawn"):0.###}; timed";
    case "Inspired_Trade": return $"trade improvement offset {Offset(d,"TradePriceImprovement"):0.###}; consumed only by actual completed trade";
    case "Inspired_Recruitment": return "next qualifying recruit succeeds; unwavering loyalty excluded";
    case "Inspired_Taming": return "next actual tame interaction succeeds; Animals minimum and food still required; consumed by attempt";
    case "Inspired_Surgery": return "applicable non-mech surgery outcome multiplier x2; minimum failure remains; consumed by applicable surgery";
    case "Inspired_Creativity": return "next actual quality generation +2 levels, capped Legendary; art/craft/furniture can consume";
    default: return "unknown loaded effect; inspect native description/stat modifiers";
   }
  }
  private sealed class Identity { public string Value=Guid.NewGuid().ToString("N"); }
  private static readonly ConditionalWeakTable<Inspiration,Identity> identities=new ConditionalWeakTable<Inspiration,Identity>();
  public static string IdentityOf(Pawn p) => Active(p)==null?"":identities.GetValue(Active(p), _=>new Identity()).Value;
  public static Inspiration Active(Pawn p) => p?.mindState?.inspirationHandler?.CurState;
  public static int? StartTick(Pawn p) => Active(p) == null ? (int?)null : Find.TickManager.TicksGame - Active(p).Age;
  public static object Describe(Pawn p) => new { pawn_id=p.thingIDNumber, name=p.LabelShortCap,
   def_name=Active(p)?.def?.defName ?? "", start_tick=StartTick(p), identity=IdentityOf(p), remaining_ticks=Active(p)==null?0:Math.Max(0,(int)(Active(p).def.baseDurationDays*60000)-Active(p).Age),
   effect=Effect(Active(p)?.def), current_job=p.CurJobDef?.defName, current_job_target_id=p.CurJob?.targetA.Thing?.thingIDNumber,
   work_speed=p.GetStatValue(StatDefOf.WorkSpeedGlobal), move_speed=p.GetStatValue(StatDefOf.MoveSpeed),
   trade_improvement=p.GetStatValue(StatDefOf.TradePriceImprovement), surgery_stat=p.GetStatValue(StatDefOf.MedicalSurgerySuccessChance) };
  public static bool Matches(Pawn p,string expected,string identity) => (Active(p)?.def?.defName ?? "") == (expected ?? "") && IdentityOf(p)==(identity ?? "");
  public static bool Protected(Pawn p) => p==null || p.Dead || p.Downed || p.Drafted || p.InMentalState
   || (p.CurJob?.def.forceCompleteBeforeNextJob ?? false) || !p.jobs.IsCurrentJobPlayerInterruptible()
   || CombatNativeHelper.HasCareJob(p) || CombatNativeHelper.Protected(p) || p.CurJobDef==JobDefOf.Ingest
   || (p.needs?.food?.CurLevelPercentage ?? 1f)<0.15f || (p.needs?.rest?.CurLevelPercentage ?? 1f)<0.08f
   || new[]{"TendPatient","FeedPatient","Rescue","Deathrest","Breastfeed","BottleFeedBaby","DoBill","Tame","PrisonerAttemptRecruit"}.Contains(p.CurJobDef?.defName);
  public static bool Worker(Pawn p,WorkTypeDef work) => !Protected(p) && p.workSettings!=null && !p.WorkTypeIsDisabled(work)
   && p.workSettings.GetPriority(work)>0 && p.health.capacities.CapableOf(PawnCapacityDefOf.Moving);
  public static ApiResult<object> Context(int id) {
   Map map=MapHelper.GetMapByID(id); if(map==null)return ApiResult<object>.Fail("Map missing");
   return ApiResult<object>.Ok(new { available=true,tick=Find.TickManager.TicksGame,
    definitions=DefDatabase<InspirationDef>.AllDefs.Select(d=>new {def_name=d.defName,label=d.label,description=d.description, duration_days=d.baseDurationDays,effect=Effect(d),
     stat_factors=d.statFactors?.Select(s=>new {stat=s.stat.defName,value=s.value}).ToArray(),stat_offsets=d.statOffsets?.Select(s=>new {stat=s.stat.defName,value=s.value}).ToArray() }).ToArray(),
    pawns=map.mapPawns.FreeColonistsSpawned.ToArray().Select(Describe).ToArray() });
  }
  private class TamePreview : WorkGiver_Tame {
   public Job Preview(Pawn worker,Pawn animal) {
    if(!TameUtility.CanTame(animal) || animal.Faction==Faction.OfPlayer || TameUtility.TriedToTameTooRecently(animal)
     || !WorkGiver_InteractAnimal.CanInteractWithAnimal(worker,animal,out string reason,false)
     || !worker.CanReserveAndReach(animal,PathEndMode.Touch,Danger.Some)
     || animal.RaceProps.Roamer && !AnimalPenUtility.AnySuitablePens(animal,false))return null;
    Thing food=null; int count=-1;
    if(animal.RaceProps.EatsFood && animal.needs?.food!=null && !HasFoodToInteractAnimal(worker,animal)) {
     float needed=JobDriver_InteractAnimal.RequiredNutritionPerFeed(animal)*8;
     food=FoodUtility.BestFoodSourceOnMap(worker,animal,false,out ThingDef foodDef,FoodPreferability.RawTasty,allowPlant:false,allowDrug:false,allowCorpse:false,allowDispenserFull:false,allowDispenserEmpty:false,allowForbidden:false,allowSociallyImproper:false,allowHarvest:false,forceScanWholeMap:false,ignoreReservations:false,calculateWantedStackCount:false,minPrefOverride:FoodPreferability.Undefined,minNutrition:needed);
     if(food==null || !worker.CanReserveAndReach(food,PathEndMode.ClosestTouch,Danger.Some))return null;
     count=Mathf.CeilToInt(needed/FoodUtility.GetNutrition(animal,food,foodDef));
    }
    Job job=JobMaker.MakeJob(JobDefOf.Tame,animal,null,food); job.count=count; return job;
   }
  }
  public sealed class TameChoice {
   public string key; public int target_id; public int worker_id; public string label; public string expected_inspiration; public int? expected_start_tick;
   public string expected_identity; public int remaining_ticks; public int animals_skill; public int minimum_skill; public float value; public float wildness; public float revenge_on_failure; public float tame_chance_stat;
   public string worker_job; public string animal_def; public float distance; public bool guaranteed_attempt; public int? food_id; public int food_count; public string products;
  }
  private static List<TameChoice> TameOptions(Map map) {
   var result=new List<TameChoice>(); var preview=new TamePreview();
   Pawn[] workers=map.mapPawns.FreeColonistsSpawned.Where(p=>Worker(p,WorkTypeDefOf.Handling))
    .OrderByDescending(p=>p.InspirationDef==InspirationDefOf.Inspired_Taming).ThenByDescending(p=>p.skills.GetSkill(SkillDefOf.Animals).Level).Take(8).ToArray();
   Pawn[] animals=map.mapPawns.AllPawnsSpawned.Where(p=>p.RaceProps.Animal && p.Faction!=Faction.OfPlayer && !p.Dead && !p.Downed).ToArray();
   // Bounded observation: retain valuable opportunities and nearby ordinary alternatives.
   Pawn[] targets=animals.OrderByDescending(p=>p.MarketValue).Take(16).Concat(animals.OrderBy(p=>workers.Select(w=>(p.Position-w.Position).LengthHorizontalSquared).DefaultIfEmpty(int.MaxValue).Min()).Take(16)).Distinct().ToArray();
   int checkedPairs=0;
   foreach(Pawn worker in workers)
    foreach(Pawn animal in targets) {
     if(++checkedPairs>128)break;
     Job job=preview.Preview(worker,animal); if(job==null)continue;
     result.Add(new TameChoice {key=$"{animal.thingIDNumber}:{worker.thingIDNumber}",target_id=animal.thingIDNumber,worker_id=worker.thingIDNumber,
      label=animal.LabelShortCap+" by "+worker.LabelShortCap,worker_job=worker.CurJobDef?.defName,animal_def=animal.def.defName,distance=(worker.Position-animal.Position).LengthHorizontal,expected_inspiration=Active(worker)?.def.defName ?? "",expected_start_tick=StartTick(worker),expected_identity=IdentityOf(worker),
      remaining_ticks=Active(worker)==null?0:Math.Max(0,(int)(Active(worker).def.baseDurationDays*60000)-Active(worker).Age),
      animals_skill=worker.skills.GetSkill(SkillDefOf.Animals).Level,minimum_skill=TrainableUtility.MinimumHandlingSkill(animal),value=animal.MarketValue,
      tame_chance_stat=worker.GetStatValue(StatDefOf.TameAnimalChance),wildness=animal.GetStatValue(StatDefOf.Wildness),revenge_on_failure=animal.RaceProps.manhunterOnTameFailChance,
      guaranteed_attempt=worker.InspirationDef==InspirationDefOf.Inspired_Taming,food_id=job.targetC.Thing?.thingIDNumber,food_count=job.count,
      products=$"meat {animal.GetStatValue(StatDefOf.MeatAmount):0}; leather {animal.GetStatValue(StatDefOf.LeatherAmount):0}; trainability {animal.RaceProps.trainability?.defName}" });
    }
   return result;
  }
  public static ApiResult<object> Taming(int id) { Map map=MapHelper.GetMapByID(id); return map==null?ApiResult<object>.Fail("Map missing"):ApiResult<object>.Ok(new{available=true,options=TameOptions(map)}); }
  public static ApiResult<object> Tame(InspirationOrderDto r) {
   Map map=MapHelper.GetMapByID(r.MapId); Pawn worker=PawnHelper.FindPawnById(r.WorkerId); Pawn animal=PawnHelper.FindPawnById(r.TargetId);
   if(map==null || worker?.Map!=map || animal?.Map!=map || !Worker(worker,WorkTypeDefOf.Handling))return ApiResult<object>.Ok(new{applied=false,reason="taming_pair_unavailable"});
   if(!Matches(worker,r.ExpectedInspiration,r.ExpectedIdentity))return ApiResult<object>.Ok(new{applied=false,reason="inspiration_changed_reconsider",reconsider=true});
   Job job=new TamePreview().Preview(worker,animal); if(job==null)return ApiResult<object>.Ok(new{applied=false,reason="taming_readiness_changed"});
   bool added=map.designationManager.DesignationOn(animal,DesignationDefOf.Tame)==null;
   if(added)map.designationManager.AddDesignation(new Designation(animal,DesignationDefOf.Tame));
   // Native WorkGiver is the final authority; preview never adds a designation or consumes inspiration.
   Job actual=new WorkGiver_Tame().JobOnThing(worker,animal,false);
   bool accepted=actual!=null && actual.def==JobDefOf.Tame && actual.targetA.Thing==animal
    && worker.jobs.TryTakeOrderedJob(actual) && worker.CurJobDef==JobDefOf.Tame && worker.CurJob?.targetA.Thing==animal;
   if(!accepted && actual!=null)worker.jobs.jobQueue.RemoveAll(worker,j=>j==actual);
   if(!accepted && added)map.designationManager.DesignationOn(animal,DesignationDefOf.Tame)?.Delete();
   return ApiResult<object>.Ok(new{applied=accepted,reason=accepted?"exact_taming_job_accepted_not_tamed":"taming_job_rejected",worker_id=worker.thingIDNumber,target_id=animal.thingIDNumber,job_assigned=accepted});
  }
  private static List<object> RecruitOptions(Map map) {
   var result=new List<object>(); var scanner=new WorkGiver_Warden_Chat();
   foreach(Pawn w in map.mapPawns.FreeColonistsSpawned.ToArray().Where(p=>Worker(p,WorkTypeDefOf.Warden)))
    foreach(Pawn p in map.mapPawns.AllPawnsSpawned.ToArray().Where(p=>p.IsPrisonerOfColony && p.guest.Recruitable)) {
     if(p.guest.ExclusiveInteractionMode!=PrisonerInteractionModeDefOf.AttemptRecruit
      || w.InspirationDef==InspirationDefOf.Inspired_Recruitment && !p.guest.IsInteractionDisabled(PrisonerInteractionModeDefOf.ReduceResistance)
      || !w.CanReserveAndReach(p,PathEndMode.Touch,Danger.Some) || scanner.JobOnThing(w,p,false)==null)continue;
     result.Add(new{key=$"{p.thingIDNumber}:{w.thingIDNumber}",target_id=p.thingIDNumber,worker_id=w.thingIDNumber,label=p.LabelShortCap+" by "+w.LabelShortCap,
      expected_inspiration=Active(w)?.def.defName ?? "",expected_start_tick=StartTick(w),expected_identity=IdentityOf(w),inspiration=Effect(Active(w)?.def),resistance=p.guest.Resistance,social=w.skills.GetSkill(SkillDefOf.Social).Level});
    }
   return result;
  }
  public static ApiResult<object> Recruitment(int id) { Map map=MapHelper.GetMapByID(id); return map==null?ApiResult<object>.Fail("Map missing"):ApiResult<object>.Ok(new{available=true,options=RecruitOptions(map)}); }
  public static ApiResult<object> Recruit(InspirationOrderDto r) {
   Map map=MapHelper.GetMapByID(r.MapId); Pawn w=PawnHelper.FindPawnById(r.WorkerId),p=PawnHelper.FindPawnById(r.TargetId);
   if(map==null || w?.Map!=map || p?.Map!=map || !Worker(w,WorkTypeDefOf.Warden) || !p.IsPrisonerOfColony || !p.guest.Recruitable || p.guest.ExclusiveInteractionMode!=PrisonerInteractionModeDefOf.AttemptRecruit
      || w.InspirationDef==InspirationDefOf.Inspired_Recruitment && !p.guest.IsInteractionDisabled(PrisonerInteractionModeDefOf.ReduceResistance)
      || !w.CanReserveAndReach(p,PathEndMode.Touch,Danger.Some))return ApiResult<object>.Ok(new{applied=false,reason="recruit_pair_unavailable"});
   if(!Matches(w,r.ExpectedInspiration,r.ExpectedIdentity))return ApiResult<object>.Ok(new{applied=false,reason="inspiration_changed_reconsider",reconsider=true});
   Job job=new WorkGiver_Warden_Chat().JobOnThing(w,p,false);
   bool accepted=job!=null && job.def==JobDefOf.PrisonerAttemptRecruit && job.targetA.Thing==p && w.jobs.TryTakeOrderedJob(job)
    && w.CurJobDef==JobDefOf.PrisonerAttemptRecruit && w.CurJob?.targetA.Thing==p;
   if(!accepted && job!=null)w.jobs.jobQueue.RemoveAll(w,j=>j==job);
   return ApiResult<object>.Ok(new{applied=accepted,reason=accepted?"exact_recruit_job_accepted_not_recruited":"recruit_job_rejected",worker_id=w.thingIDNumber,target_id=p.thingIDNumber,job_assigned=accepted});
  }
 }
}

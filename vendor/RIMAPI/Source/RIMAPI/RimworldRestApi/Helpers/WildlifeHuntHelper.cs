using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RIMAPI.Core;
using RIMAPI.Models;
using RimWorld;
using Verse;
using Verse.AI;
namespace RIMAPI.Helpers {
 public static class WildlifeHuntHelper {
  private static readonly WorkTypeDef Hunting = DefDatabase<WorkTypeDef>.GetNamedSilentFail("Hunting");
  private static bool Wild(Pawn p) => p != null && p.Spawned && p.RaceProps.Animal && !p.RaceProps.Humanlike && p.Faction == null && !p.Dead && !p.Downed && !p.InMentalState && !p.Position.Fogged(p.Map);
  public static bool RecoveryBlocksHunt(float health,float bleeding,float consciousness,float manipulation,float rest,float food,bool starving,bool diseaseProtected) =>
   diseaseProtected || bleeding > (starving ? 0f : .05f) || health < (starving ? .5f : .8f)
   || consciousness < (starving ? .5f : .8f) || manipulation < (starving ? .4f : .65f)
   || rest < (starving ? .15f : .3f) || !starving && food < .2f;
  private static string ActorReason(Pawn p) {
   if(p==null || !p.IsColonistPlayerControlled || !p.Spawned || p.Dead || p.Downed || p.InMentalState || p.drafter==null)return "actor_unavailable";
   if(p.CurJobDef==JobDefOf.Hunt)return "already_hunting";
   if(p.WorkTagIsDisabled(WorkTags.Violent))return "violence_incapable";
   if(CombatNativeHelper.Protected(p) || CombatNativeHelper.HasCareJob(p) || p.CurJobDef==JobDefOf.Ingest || p.CurJobDef==JobDefOf.DoBill)return "actor_protected_care_or_production";
   bool starving=p.health.hediffSet.HasHediff(HediffDefOf.Malnutrition) && (p.needs.food?.CurLevelPercentage ?? 1)<.2f;
   if(RecoveryBlocksHunt(p.health.summaryHealth.SummaryHealthPercent,p.health.hediffSet.BleedRateTotal,
      p.health.capacities.GetLevel(PawnCapacityDefOf.Consciousness),p.health.capacities.GetLevel(PawnCapacityDefOf.Manipulation),
      p.needs.rest?.CurLevelPercentage ?? 1,p.needs.food?.CurLevelPercentage ?? 1,starving,CareTriageHelper.DiseaseCareProtected(p)))return "actor_recovering";
   if(!WorkGiver_HunterHunt.HasHuntingWeapon(p) || WorkGiver_HunterHunt.HasShieldAndRangedWeapon(p))return "no_usable_nonexplosive_ranged_weapon";
   return null;
  }
  private static bool Willing(Pawn p,Pawn t) {
   if(HistoryEventUtility.IsKillingInnocentAnimal(p,t) && !new HistoryEvent(HistoryEventDefOf.KilledInnocentAnimal,p.Named(HistoryEventArgsNames.Doer)).Notify_PawnAboutToDo_Job())return false;
   return p.Ideo==null || !p.Ideo.IsVeneratedAnimal(t) || new HistoryEvent(HistoryEventDefOf.HuntedVeneratedAnimal,p.Named(HistoryEventArgsNames.Doer)).Notify_PawnAboutToDo_Job();
  }
  private static bool CastCell(Pawn p,Pawn t,HashSet<IntVec3> occupied,out IntVec3 cell) {
   cell=IntVec3.Invalid;
   var verb=p.TryGetAttackVerb(t);
   if(verb==null || !verb.Available())return false;
   var req=new CastPositionRequest {caster=p,target=t,verb=verb,wantCoverFromTarget=true,maxRangeFromTarget=verb.EffectiveRange*.95f};
   IntVec3 found;
   if(!CastPositionFinder.TryFindCastPosition(req,out found))return false;
   foreach(var candidate in GenRadial.RadialCellsAround(found,4f,true)) {
    if(!candidate.InBounds(p.Map) || occupied.Contains(candidate) || !candidate.Standable(p.Map) || candidate.GetEdifice(p.Map) is Building_Trap
      || candidate.GetThingList(p.Map).Any(x=>x is Fire) || !p.CanReserveAndReach(candidate,PathEndMode.OnCell,Danger.Some) || !verb.CanHitTargetFrom(candidate,t))continue;
    var path=p.Map.pathFinder.FindPathNow(p.Position,candidate,p,null,PathEndMode.OnCell);
    bool safe=path.Found && path.NodesReversed.All(n=>!(n.GetEdifice(p.Map) is Building_Trap) && !n.GetThingList(p.Map).Any(x=>x is Fire));path.ReleaseToPool();
    if(!safe)continue;occupied.Add(candidate);cell=candidate;return true;
   }
   return false;
  }
  private static IEnumerable<Pawn> Pack(Pawn t) {
   var defs=new HashSet<ThingDef>(t.RaceProps.crossAggroWith ?? new List<ThingDef>());defs.Add(t.def);
   return t.Map.mapPawns.AllPawnsSpawned.Where(p=>p!=t && !p.Dead && defs.Contains(p.def) && p.Faction==t.Faction && p.Position.InHorDistOf(t.Position,24f) && p.GetDistrict()==t.GetDistrict());
  }
  private static float ApparelArmor(Pawn p,StatDef stat) {
   var parts=p.health.hediffSet.GetNotMissingParts().Where(part=>part.depth==BodyPartDepth.Outside && part.coverageAbs>0).ToArray();
   float total=parts.Sum(part=>part.coverageAbs);if(total<=0)return 0;
   return parts.Sum(part=>part.coverageAbs*(p.apparel?.WornApparel.Where(a=>a.def.apparel.CoversBodyPart(part)).Select(a=>a.GetStatValue(stat)).DefaultIfEmpty(0).Max() ?? 0))/total;
  }
  private static int[] JointGroupActors(Pawn t,IEnumerable<Pawn> actors) {
   var occupied=new HashSet<IntVec3>();var ids=new List<int>();
   foreach(var p in actors.OrderBy(p=>p.thingIDNumber)) {
    if(ids.Count>=8)break;IntVec3 cell;
    if(ActorReason(p)==null && Willing(p,t) && CastCell(p,t,occupied,out cell))ids.Add(p.thingIDNumber);
   }
   return ids.Count>=2?ids.ToArray():new int[0];
  }
  private static object Pair(Pawn p,Pawn t) {
   string reason=ActorReason(p);IntVec3 cell=IntVec3.Invalid;
   bool feasible=reason==null && Willing(p,t) && CastCell(p,t,new HashSet<IntVec3>(),out cell);
   if(reason==null && !feasible)reason="no_willing_reachable_valid_firing_position";
   bool solo=feasible && !p.Drafted && !p.WorkTypeIsDisabled(Hunting) && p.workSettings!=null && p.workSettings.GetPriority(Hunting)>0 && p.CanReserveAndReach(t,PathEndMode.Touch,Danger.Some);
   var verb=p.TryGetAttackVerb(t);var projectile=verb?.verbProps?.defaultProjectile?.projectile;
   float distance=feasible?p.Position.DistanceTo(t.Position):0;
   var info=p.equipment?.Primary==null?null:WeaponAutomationHelper.Describe(p.equipment.Primary.def,p.equipment.Primary);
   return new {pawn_id=p.thingIDNumber,target_id=t.thingIDNumber,solo_feasible=solo,group_feasible=feasible,reason=reason,
    name=p.LabelShort,apparel_sharp_weighted=ApparelArmor(p,StatDefOf.ArmorRating_Sharp),apparel_blunt_weighted=ApparelArmor(p,StatDefOf.ArmorRating_Blunt),
    worn_armor=p.apparel?.WornApparel.Select(a=>new{def=a.def.defName,sharp=a.GetStatValue(StatDefOf.ArmorRating_Sharp),blunt=a.GetStatValue(StatDefOf.ArmorRating_Blunt)}).ToArray(),drafted=p.Drafted,armor_blunt=p.GetStatValue(StatDefOf.ArmorRating_Blunt),warmup=info?.Warmup,cooldown=info?.Cooldown,
    shooter_factor_planned=feasible?ShotReport.HitFactorFromShooter(p,cell.DistanceTo(t.Position)):(float?)null,
    planned_cover_pass=feasible?1f-CoverUtility.CalculateOverallBlockChance(t,cell,p.Map):(float?)null,weather_accuracy=p.Map.weatherManager.CurWeatherAccuracyMultiplier,target_size_factor=Math.Max(.5f,Math.Min(2f,t.BodySize)),
    weapon_accuracy=verb?.verbProps.GetHitChanceFactor(p.equipment?.Primary,feasible?cell.DistanceTo(t.Position):distance),hit_chance_current=verb==null?(float?)null:ShotReport.HitReportFor(p,verb,t).TotalEstimatedHitChance,weapon=p.equipment?.Primary?.def.defName,range=verb?.EffectiveRange ?? 0,damage=projectile?.GetDamageAmount(p.equipment?.Primary) ?? 0,
    armor_penetration=projectile?.GetArmorPenetration(p.equipment?.Primary) ?? 0,burst=verb?.verbProps?.burstShotCount ?? 0,
    shooting=p.skills?.GetSkill(SkillDefOf.Shooting)?.Level ?? 0,shooting_accuracy=p.GetStatValue(StatDefOf.ShootingAccuracyPawn),
    hunting_stealth=p.GetStatValue(StatDefOf.HuntingStealth),armor_sharp=p.GetStatValue(StatDefOf.ArmorRating_Sharp),
    health=p.health.summaryHealth.SummaryHealthPercent,rest=p.needs.rest?.CurLevelPercentage,food=p.needs.food?.CurLevelPercentage,
    consciousness=p.health.capacities.GetLevel(PawnCapacityDefOf.Consciousness),manipulation=p.health.capacities.GetLevel(PawnCapacityDefOf.Manipulation),
    malnutrition=p.health.hediffSet.GetFirstHediffOfDef(HediffDefOf.Malnutrition)?.Severity,
    move_speed=p.GetStatValue(StatDefOf.MoveSpeed),current_job=p.CurJobDef?.defName,distance=distance,
    firing_position=feasible?(object)new {x=cell.x,z=cell.z}:null,
    firing_distance=feasible?cell.DistanceTo(t.Position):0,
    effective_revenge_damage_event=PawnUtility.GetManhunterOnDamageChance(t,p),effective_revenge_current=PawnUtility.GetManhunterOnDamageChance(t,p,distance),
    effective_revenge_planned=feasible?(float?)PawnUtility.GetManhunterOnDamageChance(t,p,cell.DistanceTo(t.Position)):null};
  }
  public static ApiResult<object> Context(int mapId) {
   var map=MapHelper.GetMapByID(mapId);if(map==null)return ApiResult<object>.Fail("Map not found");
   var actors=map.mapPawns.FreeColonistsSpawned.ToArray();
   var targets=map.mapPawns.AllPawnsSpawned.Where(Wild).Where(t=>actors.Any(p=>p.Position.InHorDistOf(t.Position,60f))).OrderBy(t=>actors.Min(p=>p.Position.DistanceToSquared(t.Position))).Take(40).ToArray();
   return ApiResult<object>.Ok(new {available=true,game_tick=Find.TickManager.TicksGame,
    live_orders=actors.Select(p=>new {pawn_id=p.thingIDNumber,drafted=p.Drafted,current_job=p.CurJobDef?.defName,
     target_id=p.CurJob?.targetA.Thing?.thingIDNumber,current_cell=p.CurJob?.targetA.Cell.IsValid==true?(object)new{x=p.CurJob.targetA.Cell.x,z=p.CurJob.targetA.Cell.z}:null,
     queued_attack_ids=p.jobs.jobQueue.Where(q=>q.job.def==JobDefOf.AttackStatic).Select(q=>q.job.targetA.Thing?.thingIDNumber).ToArray()}).ToArray(),
    wild_status=map.mapPawns.AllPawnsSpawned.Where(t=>t.RaceProps.Animal && t.Faction==null).Select(t=>new{id=t.thingIDNumber,dead=t.Dead,downed=t.Downed,health=t.health.summaryHealth.SummaryHealthPercent,position=new{x=t.Position.x,z=t.Position.z}}).ToArray(),
    targets=targets.Select(t=>new {id=t.thingIDNumber,def=t.def.defName,health=t.health.summaryHealth.SummaryHealthPercent,
      body_size=t.BodySize,health_scale=t.HealthScale,melee_strike=t.def.tools?.Select(tool=>tool.power).DefaultIfEmpty(0).Max(),melee_cycle=t.def.tools?.Select(tool=>tool.cooldownTime).DefaultIfEmpty(1).Min(),move_speed=t.GetStatValue(StatDefOf.MoveSpeed),armor_sharp=t.GetStatValue(StatDefOf.ArmorRating_Sharp),
      armor_blunt=t.GetStatValue(StatDefOf.ArmorRating_Blunt),combat_power=t.kindDef.combatPower,meat=t.GetStatValue(StatDefOf.MeatAmount),leather=t.GetStatValue(StatDefOf.LeatherAmount),
      joint_group_actor_ids=JointGroupActors(t,actors),hunting_pawn_ids=actors.Where(p=>p.CurJobDef==JobDefOf.Hunt && p.CurJob.targetA.Thing==t).Select(p=>p.thingIDNumber).ToArray(),revenge_base=PawnUtility.GetManhunterOnDamageChance(t),tame_fail_revenge=PawnUtility.GetManhunterOnTameFailChance(t),
      nearby_pack_ids=Pack(t).Select(p=>p.thingIDNumber).ToArray(),pack_escalation_enabled=Find.Storyteller.difficulty.allowBigThreats,
      position=new{x=t.Position.x,z=t.Position.z}}).ToArray(),actor_options=targets.SelectMany(t=>actors.Select(p=>Pair(p,t))).ToArray(),
    uncertainty="Shot hit/armor rolls, moving wildlife, future routes and pack escalation are not guaranteed; group positions require fresh verification."});
  }
  public static ApiResult<object> Status(int mapId) {
   var map=MapHelper.GetMapByID(mapId);if(map==null)return ApiResult<object>.Fail("Map not found");
   return ApiResult<object>.Ok(new{available=true,live_orders=map.mapPawns.FreeColonistsSpawned.Select(p=>new {
    pawn_id=p.thingIDNumber,drafted=p.Drafted,current_job=p.CurJobDef?.defName,target_id=p.CurJob?.targetA.Thing?.thingIDNumber,
    current_cell=p.CurJob?.targetA.Cell.IsValid==true?(object)new{x=p.CurJob.targetA.Cell.x,z=p.CurJob.targetA.Cell.z}:null,
    queued_attack_ids=p.jobs.jobQueue.Where(q=>q.job.def==JobDefOf.AttackStatic).Select(q=>q.job.targetA.Thing?.thingIDNumber).ToArray()}).ToArray(),
    wild_status=map.mapPawns.AllPawnsSpawned.Where(t=>t.RaceProps.Animal && t.Faction==null).Select(t=>new{id=t.thingIDNumber,dead=t.Dead,downed=t.Downed,
      health=t.health.summaryHealth.SummaryHealthPercent,position=new{x=t.Position.x,z=t.Position.z}}).ToArray()});
  }
  private static readonly MethodInfo HasFood=typeof(WorkGiver_InteractAnimal).GetMethod("HasFoodToInteractAnimal",BindingFlags.NonPublic|BindingFlags.Instance);
  private static readonly MethodInfo TakeFood=typeof(WorkGiver_InteractAnimal).GetMethod("TakeFoodForAnimalInteractJob",BindingFlags.NonPublic|BindingFlags.Instance);
  private static bool InteractionReady(Pawn p,Pawn a,WorkGiver_Train scanner) {
   string reason;
   if(p.Drafted || p.Downed || p.InMentalState || CombatNativeHelper.Protected(p) || CombatNativeHelper.HasCareJob(p)
      || p.WorkTypeIsDisabled(WorkTypeDefOf.Handling) || (p.skills?.GetSkill(SkillDefOf.Animals)?.Level ?? 0)<TrainableUtility.MinimumHandlingSkill(a)
      || !WorkGiver_InteractAnimal.CanInteractWithAnimal(p,a,out reason,true))return false;
   if(!a.RaceProps.EatsFood || a.needs.food==null)return true;
   return HasFood?.Invoke(scanner,new object[]{p,a}) is bool stocked && stocked || TakeFood?.Invoke(scanner,new object[]{p,a}) is Job;
  }
  private static readonly MethodInfo Steps=typeof(Pawn_TrainingTracker).GetMethod("GetSteps",BindingFlags.NonPublic|BindingFlags.Instance);
  public static ApiResult<object> Training(int mapId) {
   var map=MapHelper.GetMapByID(mapId);if(map==null)return ApiResult<object>.Fail("Map not found");
   var scanner=DefDatabase<WorkGiverDef>.AllDefs.Select(d=>d.Worker).OfType<WorkGiver_Train>().FirstOrDefault();
   return ApiResult<object>.Ok(new {available=true,animals=map.mapPawns.SpawnedColonyAnimals.Where(a=>!a.Dead && a.training!=null).Select(a=>new {
    id=a.thingIDNumber,minimum_skill=TrainableUtility.MinimumHandlingSkill(a),degradation_period_ticks=TrainableUtility.DegradationPeriodTicks(a),tameness_can_decay=TrainableUtility.TamenessCanDecay(a),
    food=a.needs.food?.CurLevelPercentage,master_id=a.playerSettings?.Master?.thingIDNumber,follow_drafted=a.playerSettings?.followDrafted,
    trainables=DefDatabase<TrainableDef>.AllDefsListForReading.Select(td=>new {def_name=td.defName,can_train=a.training.CanAssignToTrain(td).Accepted,
      wanted=a.training.GetWanted(td),learned=a.training.HasLearned(td),steps=Steps?.Invoke(a.training,new object[]{td}),total_steps=td.steps,
      prerequisites=(td.prerequisites ?? new List<TrainableDef>()).Select(x=>x.defName).ToArray(),can_learn_now=a.training.CanBeTrained(td)}).ToArray(),
    handler_options=map.mapPawns.FreeColonistsSpawned.Select(p=>new {pawn_id=p.thingIDNumber,
      skill=p.skills?.GetSkill(SkillDefOf.Animals)?.Level ?? 0,interaction_ready=scanner!=null && InteractionReady(p,a,scanner),protected_care=CombatNativeHelper.Protected(p) || CombatNativeHelper.HasCareJob(p),
      job_available=!p.Drafted && !p.Downed && !p.InMentalState && !CombatNativeHelper.Protected(p) && !CombatNativeHelper.HasCareJob(p)
       && !p.WorkTypeIsDisabled(WorkTypeDefOf.Handling) && (p.skills?.GetSkill(SkillDefOf.Animals)?.Level ?? 0)>=TrainableUtility.MinimumHandlingSkill(a)
       && scanner?.JobOnThing(p,a,true)!=null}).ToArray()}).ToArray()});
  }
  public static ApiResult<object> Order(WildlifeHuntOrderDto r) {
   if(r==null || r.PawnIds==null || r.OwnedDraftIds==null || r.PawnIds.Count==0 || r.PawnIds.Count>8)return ApiResult<object>.Ok(new{applied=false,reason="invalid_hunt_request"});
   var map=MapHelper.GetMapByID(r.MapId);var target=map?.mapPawns.AllPawnsSpawned.FirstOrDefault(p=>p.thingIDNumber==r.TargetId);
   if(r.Mode=="cleanup" || r.Mode=="handoff") {
    var owned=map?.mapPawns.FreeColonistsSpawned.Where(p=>r.PawnIds.Contains(p.thingIDNumber)).ToArray() ?? new Pawn[0];
    foreach(var p in owned) {
     // Only our exact wildlife attack/position sequence is cancelled.
     bool ours=(p.CurJobDef==JobDefOf.AttackStatic && p.CurJob?.targetA.Thing?.thingIDNumber==r.TargetId)
       || (p.CurJobDef==JobDefOf.Goto && p.jobs.jobQueue.Any(q=>q.job.def==JobDefOf.AttackStatic && q.job.targetA.Thing?.thingIDNumber==r.TargetId));
     if(ours) {p.jobs.jobQueue.RemoveAll(p,j=>j.def==JobDefOf.AttackStatic && j.targetA.Thing?.thingIDNumber==r.TargetId);p.jobs.EndCurrentJob(JobCondition.InterruptForced);}
     bool idleOwned=r.OwnedDraftIds.Contains(p.thingIDNumber) && (p.CurJob==null || p.CurJobDef.defName=="Wait_Combat" || p.CurJobDef.defName=="Wait");
     if(r.OwnedDraftIds.Contains(p.thingIDNumber) && (ours || idleOwned) && p.Drafted && !CombatNativeHelper.HasCareJob(p))p.drafter.Drafted=false;
    }
    if(r.Mode=="cleanup")return ApiResult<object>.Ok(new{applied=true,reason="owned_group_jobs_and_drafts_released",completion="unverified"});
    if(target==null || target.Faction!=null || !target.RaceProps.Animal || target.RaceProps.Humanlike || !target.Downed || target.Dead)return ApiResult<object>.Ok(new{applied=false,reason="handoff_target_not_downed_wild_animal"});
    var finisher=owned.FirstOrDefault(p=>ActorReason(p)==null && Hunting!=null && !p.WorkTypeIsDisabled(Hunting) && p.CanReserveAndReach(target,PathEndMode.Touch,Danger.Some));
    if(finisher==null)return ApiResult<object>.Ok(new{applied=false,reason="no_available_native_hunt_finisher"});
    var job=JobMaker.MakeJob(JobDefOf.Hunt,target);job.ignoreDesignations=true;
    bool ok=finisher.jobs.TryTakeOrderedJob(job) && finisher.CurJobDef==JobDefOf.Hunt && finisher.CurJob.targetA.Thing==target;
    return ApiResult<object>.Ok(new{applied=ok,reason=ok?"downed_wild_animal_normal_hunt_observed":"native_hunt_handoff_rejected",accepted_ids=ok?new[]{finisher.thingIDNumber}:new int[0],completion="unverified"});
   }
   if(!Wild(target))return ApiResult<object>.Ok(new {applied=false,reason="target_not_living_wild_animal",completion="unverified"});
   var ids=(r.PawnIds ?? new List<int>()).Distinct().ToArray();
   var actors=ids.Select(id=>map.mapPawns.FreeColonistsSpawned.FirstOrDefault(p=>p.thingIDNumber==id)).ToArray();
   if((r.Mode!="solo" && r.Mode!="group") || ids.Length<1 || ids.Length>8 || (r.Mode=="solo" && ids.Length!=1) || (r.Mode=="group" && ids.Length<2)
     || actors.Any(p=>ActorReason(p)!=null || !Willing(p,target)))return ApiResult<object>.Ok(new {applied=false,reason="selected_actor_or_mode_unavailable",completion="unverified"});
   var cells=new List<IntVec3>();var occupied=new HashSet<IntVec3>();
   foreach(var p in actors) {IntVec3 cell;if(!CastCell(p,target,occupied,out cell))return ApiResult<object>.Ok(new {applied=false,reason="group_firing_position_or_route_unavailable",completion="unverified"});cells.Add(cell);}
   if(r.Mode=="solo") {
    var p=actors[0];if(p.Drafted || p.WorkTypeIsDisabled(Hunting) || p.workSettings?.GetPriority(Hunting)<=0)return ApiResult<object>.Ok(new{applied=false,reason="solo_hunter_not_enabled"});
    bool added=map.designationManager.DesignationOn(target,DesignationDefOf.Hunt)==null;
    if(added)map.designationManager.AddDesignation(new Designation(target,DesignationDefOf.Hunt));
    var scanner=DefDatabase<WorkGiverDef>.AllDefs.Select(d=>d.Worker).OfType<WorkGiver_HunterHunt>().FirstOrDefault();
    bool ok=scanner?.HasJobOnThing(p,target,true)==true;
    var job=ok?scanner.JobOnThing(p,target,true):null;
    ok=job!=null && p.jobs.TryTakeOrderedJob(job) && p.CurJobDef==JobDefOf.Hunt && p.CurJob.targetA.Thing==target;
    if(!ok && added)map.designationManager.RemoveAllDesignationsOn(target);
    return ApiResult<object>.Ok(new{applied=ok,reason=ok?"selected_solo_hunt_observed":"solo_native_job_rejected",accepted_ids=ok?ids:new int[0],completion="unverified"});
   }
   var accepted=new List<int>();var observations=new List<object>();var previouslyDrafted=new HashSet<int>(actors.Where(p=>p.Drafted).Select(p=>p.thingIDNumber));
   for(int i=0;i<actors.Length;i++) {
    var p=actors[i];bool wasDrafted=p.Drafted;p.drafter.Drafted=true;
    Job shot=JobMaker.MakeJob(JobDefOf.AttackStatic,target);shot.playerForced=true;shot.expiryInterval=2500;shot.expireRequiresEnemiesNearby=false;
    bool ok;
    if(p.Position==cells[i])ok=p.jobs.TryTakeOrderedJob(shot);
    else {Job go=JobMaker.MakeJob(JobDefOf.Goto,cells[i]);go.playerForced=true;ok=p.jobs.TryTakeOrderedJob(go);
      if(ok)p.jobs.jobQueue.EnqueueFirst(shot,JobTag.Misc);}
    bool observed=ok && ((p.CurJobDef==JobDefOf.AttackStatic && p.CurJob.targetA.Thing==target)
      || (p.CurJobDef==JobDefOf.Goto && p.CurJob.targetA.Cell==cells[i] && p.jobs.jobQueue.Any(q=>q.job.def==JobDefOf.AttackStatic && q.job.targetA.Thing==target)));
    if(observed)accepted.Add(p.thingIDNumber);else if(!wasDrafted)p.drafter.Drafted=false;
    observations.Add(new{pawn_id=p.thingIDNumber,was_drafted=wasDrafted,current_job=p.CurJobDef?.defName,target_id=p.CurJob?.targetA.Thing?.thingIDNumber,
       goto_cell=new{x=cells[i].x,z=cells[i].z},queued_attack_observed=p.jobs.jobQueue.Any(q=>q.job.def==JobDefOf.AttackStatic && q.job.targetA.Thing==target)});
   }
   if(accepted.Count>0 && accepted.Count<ids.Length) {
    var rollback=accepted.ToArray();
    foreach(var p in actors.Where(p=>accepted.Contains(p.thingIDNumber))) {
     bool ours=(p.CurJobDef==JobDefOf.AttackStatic && p.CurJob.targetA.Thing==target) || (p.CurJobDef==JobDefOf.Goto && p.jobs.jobQueue.Any(q=>q.job.def==JobDefOf.AttackStatic && q.job.targetA.Thing==target));
     p.jobs.jobQueue.RemoveAll(p,j=>j.def==JobDefOf.AttackStatic && j.targetA.Thing==target);
     if(ours)p.jobs.EndCurrentJob(JobCondition.InterruptForced);
     if(!previouslyDrafted.Contains(p.thingIDNumber))p.drafter.Drafted=false;
    }
    return ApiResult<object>.Ok(new{applied=false,partial=true,reason="partial_group_jobs_rolled_back",accepted_ids=new int[0],rolled_back_ids=rollback,completion="unverified"});
   }
   return ApiResult<object>.Ok(new{applied=accepted.Count==ids.Length,partial=accepted.Count>0 && accepted.Count<ids.Length,reason="selected_group_goto_then_attack_readback",
     accepted_ids=accepted,orders=observations,completion="unverified",note="Actors remain drafted; wildlife movement may invalidate queued shots. No kill guaranteed."});
  }
 }
}

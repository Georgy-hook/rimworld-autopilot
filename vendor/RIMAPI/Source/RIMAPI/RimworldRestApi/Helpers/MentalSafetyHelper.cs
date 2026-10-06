using System;
using System.Linq;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using RimWorld; using Verse; using Verse.AI;
using RIMAPI.Core; using RIMAPI.Models;
namespace RIMAPI.Helpers {
 public static class MentalSafetyHelper {
  private sealed class Token { public string Value=Guid.NewGuid().ToString("N"); }
  private static readonly ConditionalWeakTable<MentalState,Token> tokens=new ConditionalWeakTable<MentalState,Token>();
  private sealed class Defence { public string Key=Guid.NewGuid().ToString("N"); public Pawn Actor; public Pawn Target; public Job Job; public Map Map; public string Session; }
  private static readonly Dictionary<string,Defence> defences=new Dictionary<string,Defence>();
  public static bool Allied(Pawn p) => p!=null && (p.Faction==Faction.OfPlayer || p.IsColonist || p.IsPrisonerOfColony
    || (p.Faction!=null && p.Faction.RelationKindWith(Faction.OfPlayer)==FactionRelationKind.Ally));
  public static bool ActiveAlliedAggressor(Pawn p) => Allied(p) && !p.Dead && !p.Downed && p.InMentalState
    && (p.MentalState.def.defName=="Berserk" || p.MentalState.def.defName=="MurderousRage") && p.HostileTo(Faction.OfPlayer);
  public static bool TakeDefenceOrder(Pawn actor,Job job) {
   bool accepted=actor.jobs.TryTakeOrderedJob(job);
   if(accepted)TrackDefence(actor,job);
   return accepted;
  }
  private static void TrackDefence(Pawn actor,Job j) {
   if(actor==null || (!ReferenceEquals(actor.CurJob,j) && !actor.jobs.jobQueue.Any(q=>ReferenceEquals(q.job,j))))return;var target=j?.targetA.Thing as Pawn;
   if(j==null || (j.def!=JobDefOf.AttackStatic && j.def!=JobDefOf.AttackMelee) || !ActiveAlliedAggressor(target))return;
   foreach(var pair in defences.ToArray())if(!ExactDefence(pair.Value))defences.Remove(pair.Key);
   if(defences.Values.Any(old=>old.Actor==actor && ReferenceEquals(old.Job,j) && old.Session==Session(target)))return;
   var lease=new Defence{Actor=actor,Target=target,Job=j,Map=actor.Map,Session=Session(target)};
   defences[lease.Key]=lease;
  }
  private static bool Stale(Defence d) => !d.Target.Spawned || d.Target.Map!=d.Map || !ActiveAlliedAggressor(d.Target) || Session(d.Target)!=d.Session;
  private static bool ExactDefence(Defence d) => d.Actor!=null && d.Actor.Spawned && d.Actor.Map==d.Map && d.Actor.Faction==Faction.OfPlayer
    && d.Actor.IsColonistPlayerControlled && !d.Actor.Dead && d.Job.targetA.Thing==d.Target
    && (ReferenceEquals(d.Actor.CurJob,d.Job) || d.Actor.jobs.jobQueue.Any(q=>ReferenceEquals(q.job,d.Job)));
  private static ApiResult<object> CancelDefence(Map map,string key) {
   var d=defences.Values.FirstOrDefault(x=>x.Key==key && x.Map==map);
   if(d==null || !ExactDefence(d) || !Stale(d))return ApiResult<object>.Ok(new{applied=false,reason="defence_job_or_threat_changed"});
   if(ReferenceEquals(d.Actor.CurJob,d.Job))d.Actor.jobs.EndCurrentJob(JobCondition.InterruptForced);
   d.Actor.jobs.jobQueue.RemoveAll(d.Actor,j=>ReferenceEquals(j,d.Job));
   defences.Remove(d.Key);
   return ApiResult<object>.Ok(new{applied=true,reason="matching_stale_allied_attack_cancelled",actor_id=d.Actor.thingIDNumber});
  }
  public static Pawn Victim(Pawn p) => (p?.MentalState as MentalState_MurderousRage)?.target;
  public static string Session(Pawn p) => p.MentalState==null?"":tokens.GetValue(p.MentalState,_=>new Token()).Value;
  private static bool Actor(Pawn p,Map map) => p!=null && p.Spawned && p.Map==map && p.Faction==Faction.OfPlayer
   && p.IsColonistPlayerControlled && !p.Dead && !p.Downed && !p.InMentalState
   && !CombatNativeHelper.HasCareJob(p) && p.CurJobDef!=JobDefOf.Ingest
   && !(p.CurJob?.def.forceCompleteBeforeNextJob ?? false) && p.jobs.IsCurrentJobPlayerInterruptible()
   && p.health.capacities.CapableOf(PawnCapacityDefOf.Moving);
  private static bool Hazard(Map map,IntVec3 c,Pawn aggressor) => map.mapPawns.AllPawnsSpawned.Any(e=>e!=aggressor && !e.Dead && !e.Downed && e.HostileTo(Faction.OfPlayer) && !e.Position.Fogged(map)
      && c.InHorDistOf(e.Position,Math.Max(12f,(e.equipment?.Primary?.def?.Verbs?.FirstOrDefault()?.range ?? 0f)+3f)))
    || map.listerBuildings.allBuildingsNonColonist.Any(b=>CombatNativeHelper.ActiveStructure(b) && !b.Position.Fogged(map)
      && c.InHorDistOf(b.Position,Math.Max(12f,(b as Building_Turret)?.AttackVerb?.EffectiveRange ?? 0f)+3f));
  private static bool Route(Pawn actor,IntVec3 cell,Pawn aggressor,bool avoidAggressor,IntVec3? start=null) {
   Map map=actor.Map;
   if(!cell.InBounds(map) || !cell.Standable(map) || cell.Fogged(map) || cell.ContainsStaticFire(map)
      || !actor.CanReach(cell,PathEndMode.OnCell,Danger.Some))return false;
   using(var path=map.pathFinder.FindPathNow(start ?? actor.Position,cell,actor,null,PathEndMode.OnCell)) {
    if(!path.Found)return false;
    float initial=(start ?? actor.Position).DistanceToSquared(aggressor.Position);
    foreach(var c in path.NodesReversed) {
     if(c.Fogged(map) || Hazard(map,c,aggressor) || c.ContainsStaticFire(map))return false;
     if(avoidAggressor && c.DistanceToSquared(aggressor.Position)<Math.Min(initial,64f))return false;
    }
   }
   return true;
  }
  private static bool Exact(Pawn actor,MentalSafetyOptionDto p) {
   var j=actor?.CurJob;if(j==null)return false;
   if(p.Kind=="evacuate")return j.def==JobDefOf.Goto && j.targetA.Cell==new IntVec3(p.Cell.X,0,p.Cell.Z);
   return j.def==(p.Kind=="arrest"?JobDefOf.Arrest:JobDefOf.Rescue)
     && j.targetA.Thing?.thingIDNumber==(p.Kind=="arrest"?p.AggressorId:p.VictimId)
     && j.targetB.Thing?.thingIDNumber==p.BedId;
  }
  private static List<MentalSafetyOptionDto> Options(Map map) {
   var result=new List<MentalSafetyOptionDto>();
   var people=map.mapPawns.FreeColonistsSpawned.ToArray();
   foreach(var rage in people.Where(p=>!p.Dead && !p.Downed && (Victim(p)!=null || p.MentalState?.def.defName=="Berserk"))) {
    bool berserk=rage.MentalState.def.defName=="Berserk";
    foreach(Pawn victim in berserk ? people.Where(p=>p!=rage && !p.Dead && p.Position.InHorDistOf(rage.Position,20f)) : new[]{Victim(rage)}) {
    if(victim==null || victim.Dead || !victim.Spawned || victim.Map!=map || victim.Faction!=Faction.OfPlayer)continue;
    string session=Session(rage);
    if(Actor(victim,map)) {
     foreach(var cell in GenRadial.RadialCellsAround(victim.Position,20,true)
       .Where(c=>c.InBounds(map) && c.DistanceToSquared(rage.Position)>Math.Max(100f,victim.Position.DistanceToSquared(rage.Position)+36f))
       .OrderBy(c=>c.DistanceToSquared(victim.Position)).Take(24)) {
      if(!Route(victim,cell,rage,true))continue;
      result.Add(new MentalSafetyOptionDto{Key=$"evacuate:{rage.thingIDNumber}:{victim.thingIDNumber}:{cell.x}:{cell.z}",Session=session,Kind="evacuate",
       AggressorId=rage.thingIDNumber,VictimId=victim.thingIDNumber,ActorId=victim.thingIDNumber,Cell=new PositionDto{X=cell.x,Z=cell.z},
       Label=$"Move {victim.LabelShortCap} away from {rage.LabelShortCap}",Risk="Ordinary movement; aggressor may pursue/bash doors/change victim; destination is not guaranteed refuge; raid paths screened"});
      break;
     }
    }
    foreach(var worker in people.Where(p=>p!=rage && p!=victim && Actor(p,map)).Take(8)) {
     if(!worker.health.capacities.CapableOf(PawnCapacityDefOf.Manipulation))continue;
     Building_Bed prison=RestUtility.FindBedFor(rage,worker,false,false,GuestStatus.Prisoner);
     if(rage.CanBeArrestedBy(worker) && !(rage.Downed && rage.guilt.IsGuilty) && prison!=null
       && !worker.InSameExtraFaction(rage,ExtraFactionType.HomeFaction) && !worker.InSameExtraFaction(rage,ExtraFactionType.MiniFaction)
       && worker.CanReserveAndReach(rage,PathEndMode.OnCell,Danger.Some) && Route(worker,rage.Position,rage,false)
       && Route(worker,prison.Position,rage,false,rage.Position))
      result.Add(new MentalSafetyOptionDto{Key=$"arrest:{rage.thingIDNumber}:{worker.thingIDNumber}:{prison.thingIDNumber}:{victim.thingIDNumber}",Session=session,Kind="arrest",AggressorId=rage.thingIDNumber,
       VictimId=victim.thingIDNumber,ActorId=worker.thingIDNumber,BedId=prison.thingIDNumber,ArrestChance=rage.GetAcceptArrestChance(worker),
       Label=$"Attempt to arrest {rage.LabelShortCap} with {worker.LabelShortCap}",Risk="Native arrest can fail/resist; actor approaches aggressor; imprisonment/mood consequences; raid routes screened; no forced recovery"});
     if(!worker.Drafted && victim.Downed && !victim.InMentalState && ResilienceAutomationHelper.RescueRouteSafe(worker,victim)) {
      Building_Bed bed=RestUtility.FindBedFor(victim,worker,true,false);
      if(bed!=null && worker.CanReserveAndReach(victim,PathEndMode.Touch,Danger.Some)
        && Route(worker,victim.Position,rage,true) && Route(worker,bed.Position,rage,true,victim.Position))
       result.Add(new MentalSafetyOptionDto{Key=$"rescue:{rage.thingIDNumber}:{worker.thingIDNumber}:{bed.thingIDNumber}:{victim.thingIDNumber}",Session=session,Kind="rescue",AggressorId=rage.thingIDNumber,
        VictimId=victim.thingIDNumber,ActorId=worker.thingIDNumber,BedId=bed.thingIDNumber,
        Label=$"Rescue {victim.LabelShortCap} with {worker.LabelShortCap}",Risk="Normal rescue requires actual safe bed/path; attacker can follow; no guaranteed protection"});
     }
    }
   }
   }
   return result.Take(64).ToList();
  }
  public static ApiResult<object> Context(int id) {
   Map map=MapHelper.GetMapByID(id);if(map==null)return ApiResult<object>.Fail("Map missing");
   var rages=map.mapPawns.FreeColonistsSpawned.ToArray().Where(p=>!p.Dead && !p.Downed && (Victim(p)!=null || p.MentalState?.def.defName=="Berserk")).ToArray();
   var options=Options(map);
   foreach(var pair in defences.ToArray())if(!ExactDefence(pair.Value))defences.Remove(pair.Key);
   return ApiResult<object>.Ok(new{available=true,map_id=id,tick=Find.TickManager.TicksGame,options=options,
    defence_orders=defences.Values.Where(d=>d.Map==map).Select(d=>new{key=d.Key,actor_id=d.Actor.thingIDNumber,target_id=d.Target.thingIDNumber,session=d.Session,job=d.Job.def.defName,stale=Stale(d)}).ToArray(),
    threats=rages.Select(p=>new{aggressor_id=p.thingIDNumber,name=p.LabelShortCap,session=Session(p),mental_state=p.MentalState.def.defName,
      victim_id=Victim(p)?.thingIDNumber,victim_name=Victim(p)?.LabelShortCap,victim_downed=Victim(p)?.Downed,
      named_victim=p.MentalState.def.defName=="MurderousRage",job=p.CurJobDef?.defName,target_id=p.CurJob?.targetA.Thing?.thingIDNumber,can_bash_doors=p.MentalState.def.defName=="MurderousRage",kill_incapped_target=p.MentalState.def.defName=="MurderousRage"}).ToArray(),
    orders=map.mapPawns.FreeColonistsSpawned.ToArray().Select(p=>new{actor_id=p.thingIDNumber,job=p.CurJobDef?.defName,
      target_id=p.CurJob?.targetA.Thing?.thingIDNumber,bed_id=p.CurJob?.targetB.Thing?.thingIDNumber,
      position=new PositionDto{X=p.Position.x,Z=p.Position.z},cell=p.CurJob?.targetA.Cell.IsValid==true?new PositionDto{X=p.CurJob.targetA.Cell.x,Z=p.CurJob.targetA.Cell.z}:null}).ToArray(),
    blocker=rages.Length>0 && options.Count==0?"No currently eligible safe evacuation/arrest/rescue; concurrent raid and care remain relevant":""});
  }
  public static ApiResult<object> Order(MentalSafetyOrderDto request) {
   Map map=MapHelper.GetMapByID(request.MapId);if(map==null)return ApiResult<object>.Fail("Map missing");
   if(!string.IsNullOrEmpty(request.DefenceKey))return CancelDefence(map,request.DefenceKey);
   var choice=request.Cancel?request.Option:Options(map).FirstOrDefault(p=>p.Key==request.Key && p.Session==request.Session);
   if(request.Cancel && choice!=null) {
    Pawn rage=PawnHelper.FindPawnById(choice.AggressorId);
    if(rage?.Map!=map || Session(rage)!=request.Session || (rage.MentalState?.def.defName!="Berserk" && Victim(rage)?.thingIDNumber!=choice.VictimId)
       || choice.Session!=request.Session || choice.Key!=request.Key)choice=null;
   }
   if(choice==null)return ApiResult<object>.Ok(new{applied=false,reason="mental_safety_choice_changed"});
   Pawn actor=PawnHelper.FindPawnById(choice.ActorId);
   if(request.Cancel) {
    if(actor==null || !actor.Spawned || actor.Map!=map || actor.Faction!=Faction.OfPlayer || !actor.IsColonistPlayerControlled || !Exact(actor,choice))return ApiResult<object>.Ok(new{applied=false,reason="mental_safety_job_changed"});
    actor.jobs.EndCurrentJob(JobCondition.InterruptForced);
    return ApiResult<object>.Ok(new{applied=true,reason="matching_mental_safety_job_cancelled"});
   }
   Job job;
   if(choice.Kind=="evacuate")job=JobMaker.MakeJob(JobDefOf.Goto,new IntVec3(choice.Cell.X,0,choice.Cell.Z));
   else {
    Pawn target=PawnHelper.FindPawnById(choice.Kind=="arrest"?choice.AggressorId:choice.VictimId);
    Thing bed=map.listerThings.AllThings.FirstOrDefault(t=>t.thingIDNumber==choice.BedId);
    job=JobMaker.MakeJob(choice.Kind=="arrest"?JobDefOf.Arrest:JobDefOf.Rescue,target,bed);job.count=1;
   }
   bool draftedHere=choice.Kind!="rescue" && !actor.Drafted,accepted=false;
   try { if(draftedHere)actor.drafter.Drafted=true;accepted=actor.jobs.TryTakeOrderedJob(job) && Exact(actor,choice); }
   finally { if(!accepted) {actor.jobs.jobQueue.RemoveAll(actor,q=>q==job);if(draftedHere)actor.drafter.Drafted=false;} }
   return ApiResult<object>.Ok(new{applied=accepted,reason=accepted?"mental_safety_job_observed_not_completed":"mental_safety_job_not_observed",actor_id=choice.ActorId,completion="unverified"});
  }
 }
}
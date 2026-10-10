using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;
using RIMAPI.Core;
namespace RIMAPI.Helpers {
 public static class AnimalProvisioningHelper {
  public static bool FeedReserve(float humanNutrition,float batchNutrition,bool humanEdible,int people)
   => !humanEdible || humanNutrition-batchNutrition>=people*1.8f;
  public static int FeedCount(float unit,int stock,int hungryAnimals)
   => unit>0f ? Math.Min(stock,(int)Math.Floor((double)Math.Min(1.6f,hungryAnimals*.8f)/unit)) : 0;
  public static bool ElectiveSurgeryReady(float food,bool injured,bool exposed,int skill,float success)
   => food>=.5f && !injured && !exposed && skill>=8 && success>=.9f;
  public static Pawn Surgeon(Map m,Pawn patient,RecipeDef recipe) {
   var bed=patient.CurrentBed();
   if(bed==null || !bed.OccupiedRect().All(c=>c.Roofed(m)))return null;
   return m.mapPawns.FreeColonistsSpawned.Where(d=>OrdinaryWorkSafety.Worker(d,WorkTypeDefOf.Doctor)
    && d.workSettings.GetPriority(WorkTypeDefOf.Doctor)>0 && recipe.PawnSatisfiesSkillRequirements(d)
    && ElectiveSurgeryReady(patient.needs?.food?.CurLevelPercentage ?? 0f,
      patient.health.hediffSet.hediffs.Any(h=>h.Visible && (h.IsCurrentlyLifeThreatening || h is Hediff_Injury injury && !injury.IsPermanent() || h.def==HediffDefOf.Malnutrition)),
      patient.Position.GetTemperature(m)<patient.GetStatValue(StatDefOf.ComfyTemperatureMin) || patient.Position.GetTemperature(m)>patient.GetStatValue(StatDefOf.ComfyTemperatureMax),
      d.skills.GetSkill(SkillDefOf.Medicine).Level,d.GetStatValue(StatDefOf.MedicalSurgerySuccessChance)*bed.GetStatValue(StatDefOf.SurgerySuccessChanceFactor))
    && !patient.IsForbidden(d) && d.CanReserveAndReach(patient,PathEndMode.Touch,Danger.Some)
    && OrdinaryWorkSafety.Route(d,d.Position,patient.Position,PathEndMode.Touch))
    .OrderByDescending(d=>d.GetStatValue(StatDefOf.MedicalSurgerySuccessChance)).FirstOrDefault();
  }
  static bool FreshFood(Thing t) => t.Spawned && !t.Position.Fogged(t.Map) && !t.IsForbidden(Faction.OfPlayer) && !t.IsBurning() && !t.def.IsCorpse
   && t.def.ingestible!=null && t.GetStatValue(StatDefOf.Nutrition)>0 && (t.TryGetComp<CompRottable>()?.Stage ?? RotStage.Fresh)==RotStage.Fresh;
  static bool Empty(Map m,IntVec3 c) => c.InBounds(m) && !c.Fogged(m) && c.Standable(m) && c.GetZone(m)==null
   && !c.GetThingList(m).Any(t=>t is Building || t is Blueprint || t is Frame || t.def.category==ThingCategory.Item);
  public static IEnumerable<SustenanceHelper.Plan> Plans(Map m) {
   var animals=m.mapPawns.SpawnedPawnsInFaction(Faction.OfPlayer).Where(p=>p.RaceProps.Animal && !p.Dead).ToArray();
   var spot=DefDatabase<ThingDef>.GetNamedSilentFail("AnimalSleepingSpot");
   if(InstantConstructionHelper.IsInstantBuilding(spot)) foreach(var p in animals.Where(CareTriageHelper.ThermalRescueNeeded)) {
    if(m.listerBuildings.allBuildingsColonist.OfType<Building_Bed>().Any(b=>CareTriageHelper.ThermalBedBeneficial(p,b)
      && !b.CurOccupants.Any(o=>o!=p) && RestUtility.CanUseBedEver(p,b.def)))continue;
    var cells=m.listerBuildings.allBuildingsColonist.OfType<Building_Bed>().SelectMany(b=>b.GetRoom()?.Cells ?? Enumerable.Empty<IntVec3>())
     .Distinct().Where(c=>Empty(m,c) && c.Roofed(m) && CareTriageHelper.ThermalTransferBeneficial(
      p.health.hediffSet.HasHediff(HediffDefOf.Hypothermia),p.health.hediffSet.HasHediff(HediffDefOf.Heatstroke),p.Position.GetTemperature(m),c.GetTemperature(m),p.GetStatValue(StatDefOf.ComfyTemperatureMin),p.GetStatValue(StatDefOf.ComfyTemperatureMax))
      && GenConstruct.CanPlaceBlueprintAt(spot,c,Rot4.North,m,false).Accepted)
     .OrderBy(c=>c.DistanceToSquared(p.Position)).Take(1);
    foreach(var c in cells)yield return new SustenanceHelper.Plan{key=$"warmspot:{p.thingIDNumber}:{c.x}:{c.z}",kind="warmspot",target_id=p.thingIDNumber,value=$"{c.x},{c.z}",label=p.LabelShortCap+": roofed warm animal sleeping spot",cost="Loaded zero-work, zero-material spot in existing shelter; rescue remains separate",risk=$"Source {p.Position.GetTemperature(m):F1}C, destination {c.GetTemperature(m):F1}C. Creating a spot is not arrival, warmth or feeding; shared room cleanliness",
     facts=new{source_c=p.Position.GetTemperature(m),destination_c=c.GetTemperature(m),
      hypothermia=p.health.hediffSet.GetFirstHediffOfDef(HediffDefOf.Hypothermia)?.Severity,
      heatstroke=p.health.hediffSet.GetFirstHediffOfDef(HediffDefOf.Heatstroke)?.Severity,
      downed=p.Downed,work=spot.GetStatValueAbstract(StatDefOf.WorkToBuild),materials=0,rescue_pending=true}};
   }
   var food=m.listerThings.AllThings.Where(FreshFood).ToArray();
   float human=food.Where(t=>m.mapPawns.FreeColonistsSpawned.Any(p=>p.RaceProps.CanEverEat(t.def) && p.WillEat(t) && (p.foodRestriction?.CurrentFoodPolicy?.Allows(t) ?? true) && p.CanReach(t,PathEndMode.Touch,Danger.Some)))
    .Sum(t=>t.stackCount*t.GetStatValue(StatDefOf.Nutrition));
   foreach(var marker in m.listerBuildings.allBuildingsColonist.Select(b=>b.TryGetComp<CompAnimalPenMarker>()).Where(c=>c?.PenState?.Enclosed==true)) {
    var hungry=animals.Where(p=>marker.AcceptsToPen(p) && (p.needs?.food?.CurLevelPercentage ?? 1f)<.3f && marker.PenState.ContainsConnectedRegion(p.GetRegion())).ToArray();
    if(hungry.Length==0)continue;
    var cells=marker.PenState.ConnectedRegions.SelectMany(r=>r.Cells).Where(c=>Empty(m,c) && hungry.Any(p=>p.CanReach(c,PathEndMode.OnCell,Danger.Some)))
     .OrderBy(c=>c.DistanceToSquared(marker.parent.Position)).Take(3).ToArray();
    foreach(var t in food.Where(t=>hungry.Any(p=>p.RaceProps.CanEverEat(t.def) && p.WillEat(t)))) {
     var compatible=hungry.Where(p=>p.RaceProps.CanEverEat(t.def) && p.WillEat(t)).ToArray();
     float unit=t.GetStatValue(StatDefOf.Nutrition);
     int count=FeedCount(unit,t.stackCount,compatible.Length);
     if(count<=0)continue;
     bool edible=m.mapPawns.FreeColonistsSpawned.Any(p=>p.RaceProps.CanEverEat(t.def) && p.WillEat(t));
     if(!FeedReserve(human,count*unit,edible,m.mapPawns.FreeColonistsSpawned.Count))continue;
     foreach(var worker in m.mapPawns.FreeColonistsSpawned.Where(p=>OrdinaryWorkSafety.Worker(p,WorkTypeDefOf.Hauling))) {
      if(!HaulAIUtility.PawnCanAutomaticallyHaul(worker,t,true) || !worker.CanReserveAndReach(t,PathEndMode.Touch,Danger.Some))continue;
      var dest=cells.FirstOrDefault(c=>worker.CanReserve(c) && OrdinaryWorkSafety.Route(worker,worker.Position,t.Position,PathEndMode.Touch)
       && OrdinaryWorkSafety.Route(worker,t.Position,c,PathEndMode.OnCell));
      if(!cells.Contains(dest))continue;
      yield return new SustenanceHelper.Plan{key=$"penfeed:{marker.parent.thingIDNumber}:{worker.thingIDNumber}:{t.thingIDNumber}:{dest.x}:{dest.z}",kind="penfeed",target_id=marker.parent.thingIDNumber,value=$"{worker.thingIDNumber},{t.thingIDNumber},{dest.x},{dest.z},{count}",label=worker.LabelShortCap+": haul "+count+" "+t.def.label+" into "+marker.RenamableLabel,cost=$"{count*unit:F2} nutrition; remaining human-compatible reserve {human-(edible?count*unit:0):F2}; hauling labor",risk="Fresh compatible feed in connected reachable pen; ordinary haul start is not delivery or ingestion. Finite stockpile must not attract unlimited human food",
       facts=new{hungry_animals=compatible.Length,min_food=compatible.Min(p=>p.needs.food.CurLevelPercentage),
        malnutrition=compatible.Max(p=>p.health.hediffSet.GetFirstHediffOfDef(HediffDefOf.Malnutrition)?.Severity ?? 0f),
        nutrition=count*unit,human_remaining=human-(edible?count*unit:0),human_minimum=m.mapPawns.FreeColonistsSpawned.Count*1.8f,
        delivery_pending=true}};
      break;
     }
    }
   }
  }
  public static ApiResult<object> Apply(Map m,SustenanceHelper.Plan plan) {
   var parts=plan.value.Split(',').Select(int.Parse).ToArray();
   if(plan.kind=="warmspot") {
    var def=DefDatabase<ThingDef>.GetNamed("AnimalSleepingSpot"); var cell=new IntVec3(parts[0],0,parts[1]);
    if(!InstantConstructionHelper.IsInstantBuilding(def) || def.costList?.Any()==true || def.CostStuffCount>0 || !Empty(m,cell)
     || !GenConstruct.CanPlaceBlueprintAt(def,cell,Rot4.North,m,false).Accepted)return ApiResult<object>.Ok(new{applied=false,reason="warm_spot_changed"});
    var bed=ThingMaker.MakeThing(def);bed.SetFaction(Faction.OfPlayer);GenSpawn.Spawn(bed,cell,m,Rot4.North);
    return ApiResult<object>.Ok(new{applied=true,reason="warm_spot_placed",bed_id=bed.thingIDNumber,completion="rescue_arrival_warmth_unverified"});
   }
   var worker=m.mapPawns.FreeColonistsSpawned.First(p=>p.thingIDNumber==parts[0]); var food=m.listerThings.AllThings.First(t=>t.thingIDNumber==parts[1]); var destination=new IntVec3(parts[2],0,parts[3]);
   if(!Empty(m,destination))return ApiResult<object>.Ok(new{applied=false,reason="feed_destination_changed"});
   // A normal, finite non-storage haul. It creates no Critical stockpile that
   // could silently attract the humans' entire food reserve.
   if(!HaulAIUtility.PawnCanAutomaticallyHaul(worker,food,true) || !worker.CanReserve(destination))
    return ApiResult<object>.Ok(new{applied=false,reason="ordinary_feed_haul_unavailable"});
   var job=JobMaker.MakeJob(JobDefOf.HaulToCell,food,destination);
   job.haulMode=HaulMode.ToCellNonStorage;job.count=Math.Min(food.stackCount,parts[4]);worker.jobs.TryTakeOrderedJob(job);
   bool started=worker.CurJob==job;
   return ApiResult<object>.Ok(new{applied=started,reason=started?"finite_feed_haul_started":"feed_haul_not_started",completion="delivery_and_ingestion_unverified",count=job.count});
  }
 }
}

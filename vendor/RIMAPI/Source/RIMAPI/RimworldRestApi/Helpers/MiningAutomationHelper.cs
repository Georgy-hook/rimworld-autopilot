using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;
using RIMAPI.Core;
using RIMAPI.Models;
namespace RIMAPI.Helpers {
 public static class MiningAutomationHelper {
  public static List<int> ConnectedBatch(Dictionary<int,int[]> adjacency,int start,int limit) {
   var result=new List<int>();var seen=new HashSet<int>();var queue=new Queue<int>();queue.Enqueue(start);seen.Add(start);
   while(queue.Count>0 && result.Count<limit) {int id=queue.Dequeue();result.Add(id);
    foreach(int next in adjacency[id])if(seen.Add(next))queue.Enqueue(next);}
   return result;
  }
  static List<MiningPlanDto> Plans(Map m) {
   var result=new List<MiningPlanDto>();
   var mine=m.listerThings.AllThings.OfType<Mineable>().Where(t=>!t.Position.Fogged(m) && !t.IsForbidden(Faction.OfPlayer)
    && t.def.building?.mineableThing!=null && m.designationManager.DesignationAt(t.Position,DesignationDefOf.Mine)==null).ToArray();
   foreach(var group in mine.GroupBy(t=>t.def)) {
    var byId=group.ToDictionary(t=>t.thingIDNumber);var byCell=group.ToDictionary(t=>t.Position);
    var adjacency=group.ToDictionary(t=>t.thingIDNumber,t=>GenAdj.CardinalDirections.Select(d=>t.Position+d).Where(byCell.ContainsKey).Select(c=>byCell[c].thingIDNumber).ToArray());
    var unseen=new HashSet<int>(byId.Keys);
    while(unseen.Count>0) {
     var vein=ConnectedBatch(adjacency,unseen.Min(),int.MaxValue);unseen.ExceptWith(vein);
     foreach(var worker in m.mapPawns.FreeColonistsSpawned.Where(p=>OrdinaryWorkSafety.Worker(p,WorkTypeDefOf.Mining))) {
      var first=vein.Select(id=>byId[id]).Where(t=>worker.CanReserveAndReach(t,PathEndMode.Touch,Danger.Some)
       && OrdinaryWorkSafety.Route(worker,worker.Position,t.Position,PathEndMode.Touch))
       .OrderBy(t=>t.Position.DistanceToSquared(worker.Position)).FirstOrDefault();
      if(first==null)continue;
      var batch=ConnectedBatch(adjacency,first.thingIDNumber,12).Select(id=>byId[id]).ToArray();
      // Test the whole batch as absent, not each block as if its neighbors remained.
      while(batch.Length>0 && batch.Any(t=>ResilienceAutomationHelper.RemovalWouldEndangerRoof(t,null,new HashSet<IntVec3>(batch.Select(b=>b.Position)))))
       batch=batch.Take(batch.Length-1).ToArray();
      if(batch.Length==0)continue;
      int amount=group.Key.building.EffectiveMineableYield*batch.Length;
      result.Add(new MiningPlanDto{Key=$"{worker.thingIDNumber}:"+string.Join(",",batch.Select(t=>t.thingIDNumber)),WorkerId=worker.thingIDNumber,Worker=worker.LabelShortCap,
       OreDef=group.Key.defName,ProductDef=group.Key.building.mineableThing.defName,VeinCells=vein.Count,
       ThingIds=batch.Select(t=>t.thingIDNumber).ToList(),Cells=batch.Select(t=>new PositionDto{X=t.Position.x,Y=0,Z=t.Position.z}).ToList(),
       RemainingHp=batch.Sum(t=>t.HitPoints),BaseYield=amount,NominalMarketValue=amount*group.Key.building.mineableThing.GetStatValueAbstract(StatDefOf.MarketValue),
       MiningSpeed=worker.GetStatValue(StatDefOf.MiningSpeed),MiningYield=worker.GetStatValue(StatDefOf.MiningYield),MiningSkill=worker.skills.GetSkill(SkillDefOf.Mining).Level,
       TravelDistance=worker.Position.DistanceTo(first.Position)});
     }
    }
   }
   var products=new HashSet<ThingDef>(DefDatabase<ThingDef>.AllDefsListForReading.Where(d=>d.mineable && d.building?.mineableThing!=null).Select(d=>d.building.mineableThing));
   var hauler=DefDatabase<WorkGiverDef>.AllDefsListForReading.FirstOrDefault(d=>d.Worker is WorkGiver_HaulGeneral)?.Worker as WorkGiver_Scanner;
   if(hauler!=null)foreach(var item in m.listerThings.AllThings.Where(t=>t.Spawned && !t.Position.Fogged(m) && products.Contains(t.def)))
    foreach(var worker in m.mapPawns.FreeColonistsSpawned.Where(p=>OrdinaryWorkSafety.Worker(p,WorkTypeDefOf.Hauling))) {
     if(!hauler.HasJobOnThing(worker,item,true))continue;
     var job=hauler.JobOnThing(worker,item,true);
     if(job==null || !job.targetB.IsValid || !OrdinaryWorkSafety.Route(worker,worker.Position,item.Position,PathEndMode.Touch)
      || !OrdinaryWorkSafety.Route(worker,item.Position,job.targetB.Cell,PathEndMode.OnCell))continue;
     result.Add(new MiningPlanDto{Kind="haul",Key=$"haul:{worker.thingIDNumber}:{item.thingIDNumber}:{job.targetB.Cell.x}:{job.targetB.Cell.z}",WorkerId=worker.thingIDNumber,Worker=worker.LabelShortCap,
      ProductDef=item.def.defName,ThingIds=new List<int>{item.thingIDNumber},Cells=new List<PositionDto>{new PositionDto{X=item.Position.x,Z=item.Position.z},new PositionDto{X=job.targetB.Cell.x,Z=job.targetB.Cell.z}},
      BaseYield=job.count,NominalMarketValue=item.GetStatValue(StatDefOf.MarketValue)*job.count,TravelDistance=worker.Position.DistanceTo(item.Position)});
    }
   return result;
  }
  public static ApiResult<object> Context(int mapId) {
   var m=MapHelper.GetMapByID(mapId);if(m==null)return ApiResult<object>.Fail("map_missing");
   return ApiResult<object>.Ok(new{available=true,options=Plans(m),product_stocks=m.listerThings.AllThings.Where(t=>t.Spawned && !t.Position.Fogged(m) && t.def.category==ThingCategory.Item).GroupBy(t=>t.def).Select(g=>new{product_def=g.Key.defName,count=g.Sum(t=>t.stackCount)}).ToArray(),completion="visible ore and prospective ordinary work; not mined goods or income"});
  }
  public static ApiResult<object> Order(MiningOrderDto request) {
   var m=MapHelper.GetMapByID(request.MapId);if(m==null)return ApiResult<object>.Fail("map_missing");
   var plan=Plans(m).FirstOrDefault(p=>p.Key==request.Key);if(plan==null)return ApiResult<object>.Ok(new{applied=false,reason="mining_plan_changed"});
   var worker=m.mapPawns.FreeColonistsSpawned.First(p=>p.thingIDNumber==plan.WorkerId);
   var targets=plan.ThingIds.Select(id=>m.listerThings.AllThings.First(t=>t.thingIDNumber==id)).ToArray();
   if(plan.Kind=="haul") {
    var haulGiver=DefDatabase<WorkGiverDef>.AllDefsListForReading.First(d=>d.Worker is WorkGiver_HaulGeneral).Worker as WorkGiver_Scanner;
    var haul=haulGiver.JobOnThing(worker,targets[0],true);if(haul!=null)worker.jobs.TryTakeOrderedJob(haul);
    bool moving=haul!=null && worker.CurJob==haul;
    return ApiResult<object>.Ok(new{applied=moving,reason=moving?"mineral_haul_started":"mineral_haul_not_started",completion="arrival_storage_sale_unverified"});
   }
   var giver=DefDatabase<WorkGiverDef>.AllDefsListForReading.FirstOrDefault(d=>d.Worker is WorkGiver_Miner);
   if(giver==null || giver.requiredCapacities?.Any(c=>!worker.health.capacities.CapableOf(c))==true)
    return ApiResult<object>.Ok(new{applied=false,reason="native_miner_unavailable"});
   var added=targets.Select(t=>new Designation(t.Position,DesignationDefOf.Mine)).ToArray();
   foreach(var d in added)m.designationManager.AddDesignation(d);
   var scanner=(WorkGiver_Scanner)giver.Worker;
   var job=giver.scanCells ? (scanner.HasJobOnCell(worker,targets[0].Position,true)?scanner.JobOnCell(worker,targets[0].Position,true):null)
    : (scanner.HasJobOnThing(worker,targets[0],true)?scanner.JobOnThing(worker,targets[0],true):null);
   if(job!=null)worker.jobs.TryTakeOrderedJob(job);
   bool started=job!=null && worker.CurJob==job;
   if(!started){foreach(var d in added)m.designationManager.RemoveDesignation(d);return ApiResult<object>.Ok(new{applied=false,reason="native_mining_job_not_started"});}
   worker.workSettings.SetPriority(WorkTypeDefOf.Mining,1);
   return ApiResult<object>.Ok(new{applied=true,reason="exact_vein_mining_started",worker_id=worker.thingIDNumber,thing_ids=plan.ThingIds,completion="ordinary_mining_job_observed; output_haul_sale_unverified"});
  }
 }
}

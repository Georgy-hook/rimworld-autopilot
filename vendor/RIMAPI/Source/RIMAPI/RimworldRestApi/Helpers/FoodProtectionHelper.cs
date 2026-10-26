using System;
using System.Linq;
using System.Collections.Generic;
using RimWorld;
using Verse;
using Verse.AI;
using RIMAPI.Core;

namespace RIMAPI.Helpers
{
    /// <summary>Existing protective storage and ordinary finite hauling, before a freezer is affordable.</summary>
    public static class FoodProtectionHelper
    {
        private static bool SafeFood(Thing t,HashSet<ThingDef> food) => food.Contains(t.def) && t.Spawned
            && !t.Position.Fogged(t.Map) && !t.IsForbidden(Faction.OfPlayer) && !t.IsBurning()
            && (t.TryGetComp<CompRottable>()==null || t.TryGetComp<CompRottable>().Stage==RotStage.Fresh);
        private static bool ProtectedStorage(Map map,Thing food,IntVec3 cell) => cell.Roofed(map)
            || map.haulDestinationManager.SlotGroupAt(cell)?.parent is Building_Storage shelf && shelf.def.building?.preventDeteriorationOnTop==true;
        private static bool EmptyPantryCell(Map map,IntVec3 c) => StorageProfileHelper.DryFoundation(map,c)
            && c.Roofed(map) && map.roofGrid.RoofAt(c)?.isThickRoof!=true && c.Standable(map) && c.GetEdifice(map)==null
            && c.GetZone(map)==null && !c.ContainsStaticFire(map)
            && !map.listerBuildings.allBuildingsColonist.Any(b=>b is Building_Bed && b.OccupiedRect().Contains(c)
                || b.def.hasInteractionCell && b.InteractionCell==c || b is Building_Door && c.AdjacentTo8Way(b.Position));
        private static IntVec3[] Pantry(Map map,IntVec3 origin) => CellRect.CenteredOn(origin,1).Cells
            .Where(c=>EmptyPantryCell(map,c)).Take(6).ToArray();
        public static List<SustenanceHelper.Plan> Plans(Map map)
        {
            var plans=new List<SustenanceHelper.Plan>();
            var definitions=StorageProfileHelper.Definitions("cold_food",map);
            var foods=map.listerThings.AllThings.Where(t=>SafeFood(t,definitions)).ToArray();
            var destinations=map.haulDestinationManager.AllHaulDestinationsListInPriorityOrder
                .OfType<ISlotGroupParent>().Where(d=>d is IHaulDestination dest && dest.HaulDestinationEnabled
                    && (!(d is Thing owner) || owner.Faction==Faction.OfPlayer)).ToArray();
            bool coveredCapacity=foods.Any(t=>destinations.Any(d=>d.Accepts(t) && d.GetSlotGroup().CellsList
                .Any(c=>ProtectedStorage(map,t,c) && StoreUtility.IsGoodStoreCell(c,map,t,null,Faction.OfPlayer))));
            if (foods.Length>0 && !coveredCapacity)
            {
                var kitchen=map.listerBuildings.allBuildingsColonist.FirstOrDefault(b=>b.def.defName.Contains("Stove") || b.def.defName=="Campfire");
                if(kitchen!=null)
                {
                    var anchor=map.areaManager.Home.ActiveCells.Where(c=>c.DistanceToSquared(kitchen.Position)<=100 && EmptyPantryCell(map,c))
                        .OrderBy(c=>c.DistanceToSquared(kitchen.Position)).DefaultIfEmpty(IntVec3.Invalid).First();
                    if(anchor.IsValid) plans.Add(new SustenanceHelper.Plan {key="pantry:"+anchor.x+":"+anchor.z,kind="pantry",
                        value=anchor.x+":"+anchor.z,label="Covered food pantry near the completed kitchen",cost="Free ground zone; finite hauling, no refrigeration",
                        risk="Safe dry roofed cells keep exits/interaction cells; actual delivery and rot still require work"});
                }
            }
            var active=new HashSet<int>(ResilienceAutomationHelper.ActiveOrders(map).Where(o=>o.Kind=="haul").Select(o=>o.TargetId));
            var work=DefDatabase<WorkTypeDef>.GetNamedSilentFail("Hauling");
            if(work==null)return plans;
            foreach(var pawn in map.mapPawns.FreeColonistsSpawned.Where(p=>OrdinaryWorkSafety.Worker(p,work)
                && p.workSettings.GetPriority(work)>0).Take(8))
                foreach(var food in foods.Where(t=>!active.Contains(t.thingIDNumber) && !ProtectedStorage(map,t,t.Position))
                    .OrderBy(t=>t.HitPoints/(float)Math.Max(1,t.MaxHitPoints)).Take(12))
                {
                    if(!pawn.CanReserveAndReach(food,PathEndMode.ClosestTouch,Danger.Some)
                        || !OrdinaryWorkSafety.Route(pawn,pawn.Position,food.Position,PathEndMode.ClosestTouch))continue;
                    IntVec3 destination=IntVec3.Invalid;
                    foreach(var d in destinations.Where(d=>d.Accepts(food)))
                    {
                        foreach(var cell in d.GetSlotGroup().CellsList.Where(c=>ProtectedStorage(map,food,c) && c.InAllowedArea(pawn))
                            .OrderBy(c=>c.DistanceToSquared(food.Position)).Take(12))
                            if(StoreUtility.IsGoodStoreCell(cell,map,food,pawn,Faction.OfPlayer) && pawn.CanReserveAndReach(cell,PathEndMode.OnCell,Danger.Some)
                                && OrdinaryWorkSafety.Route(pawn,food.Position,cell,PathEndMode.OnCell)) {destination=cell;break;}
                        if(destination.IsValid)break;
                    }
                    if(!destination.IsValid)continue;
                    plans.Add(new SustenanceHelper.Plan {key="protectfood:"+pawn.thingIDNumber+":"+food.thingIDNumber,
                        kind="protectfood",target_id=food.thingIDNumber,value=pawn.thingIDNumber+":"+destination.x+":"+destination.z,
                        label=pawn.LabelShort+": carry exposed "+food.LabelShort+" into protective storage",cost="Finite normal hauling; preserve food/care/production jobs",
                        risk="Both path legs checked for fallout/gas/temperature/fire/enemies; hauling start is not delivery",
                        facts=new {hit_points=food.HitPoints,max_hit_points=food.MaxHitPoints,nutrition=food.GetStatValue(StatDefOf.Nutrition)*food.stackCount,
                            source_roofed=food.Position.Roofed(map),destination_temperature=destination.GetTemperature(map)}});
                    break;
                }
            return plans;
        }
        public static ApiResult<object> Apply(Map map,SustenanceHelper.Plan plan)
        {
            var parts=plan.value.Split(':').Select(int.Parse).ToArray();
            if(plan.kind=="pantry")
            {
                var cells=Pantry(map,new IntVec3(parts[0],0,parts[1]));
                if(cells.Length==0)return ApiResult<object>.Ok(new {applied=false,reason="pantry_cells_changed"});
                var zone=new Zone_Stockpile(StorageSettingsPreset.DefaultStockpile,map.zoneManager);
                StorageProfileHelper.Apply(zone,"cold_food");zone.settings.Priority=StoragePriority.Critical;
                zone.label="Laya covered human food";map.zoneManager.RegisterZone(zone);foreach(var c in cells)zone.AddCell(c);
                return ApiResult<object>.Ok(new {applied=true,reason="covered_food_zone_created",completion="haul_and_preservation_unverified"});
            }
            var pawn=map.mapPawns.FreeColonistsSpawned.First(p=>p.thingIDNumber==parts[0]);
            var food=map.listerThings.AllThings.First(t=>t.thingIDNumber==plan.target_id);var destination=new IntVec3(parts[1],0,parts[2]);
            var job=HaulAIUtility.HaulToCellStorageJob(pawn,food,destination,false);
            if(job==null)return ApiResult<object>.Ok(new {applied=false,reason="food_storage_job_changed"});
            pawn.jobs.TryTakeOrderedJob(job);
            return ApiResult<object>.Ok(new {applied=pawn.CurJob==job,reason="normal_food_storage_haul",completion="pickup_delivery_and_ingestion_unverified"});
        }
    }
}

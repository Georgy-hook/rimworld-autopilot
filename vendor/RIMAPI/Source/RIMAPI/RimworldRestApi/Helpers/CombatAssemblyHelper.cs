using System;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    // Assemble at an existing, observed home before a distant assault arrives.
    // A roofed post and a projected doorway lane are not an actual shot or cover fire.
    public static class CombatAssemblyHelper
    {
        public static bool TryPosition(Pawn pawn,Pawn target,out IntVec3 result)
        {
            result=IntVec3.Invalid;var map=pawn.Map;
            if(CombatNativeHelper.AbductionThreat(target))return false;
            var verb=pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(verb==null || verb.IsMeleeAttack || CombatNativeHelper.Protected(pawn) || CareTriageHelper.QueuedCare(pawn))return false;
            var enemies=map.mapPawns.AllPawnsSpawned.Where(p=>!p.Dead && !p.Downed && !p.Position.Fogged(map)
                && CombatNativeHelper.IsPlayerThreat(p)).ToArray();
            if(!enemies.Any() || enemies.Any(e=>pawn.Position.DistanceTo(e.Position)<=Math.Max(35f,
                e.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb?.verbProps.range+8f ?? 35f)))return false;
            var rooms=map.listerBuildings.allBuildingsColonist.OfType<Building_Bed>()
                .Where(b=>!b.ForPrisoners && b.def.building.bed_humanlike).Select(b=>b.GetRoom())
                .Where(r=>r!=null && !r.PsychologicallyOutdoors).Distinct()
                .Where(r=>!enemies.Any(e=>e.GetRoom()==r))
                .OrderByDescending(r=>map.mapPawns.FreeColonistsSpawned.Count(p=>p.GetRoom()==r))
                .ThenBy(r=>r.ContainedBeds.Min(b=>b.Position.DistanceToSquared(pawn.Position))).Take(3);
            var area=pawn.playerSettings?.AreaRestrictionInPawnCurrentMap;
            float minimum=pawn.GetStatValue(StatDefOf.ComfyTemperatureMin),maximum=pawn.GetStatValue(StatDefOf.ComfyTemperatureMax);
            int pathChecks=0;
            foreach(var room in rooms)
            {
                CombatPathBudgetHelper.Checkpoint();
                var doors=map.listerBuildings.allBuildingsColonist.OfType<Building_Door>()
                    .SelectMany(d=>GenAdj.CardinalDirections.Select(direction=>new {Door=d,Inside=d.Position+direction,Outside=d.Position-direction}))
                    .Where(x=>x.Inside.InBounds(map) && x.Outside.InBounds(map) && x.Inside.GetRoom(map)==room
                        && x.Outside.GetRoom(map)!=room && x.Outside.GetRoom(map)?.PsychologicallyOutdoors==true)
                    .OrderBy(x=>x.Door.Position.DistanceToSquared(target.Position)).Take(3);
                foreach(var door in doors)
                {
                CombatPathBudgetHelper.Checkpoint();
                    // Bound the search around the actual doorway, not by
                    // rejecting otherwise safe large rooms.
                    var cells=GenRadial.RadialCellsAround(door.Inside,12f,true)
                        .Where(c=>c.InBounds(map) && c.GetRoom(map)==room && c.Standable(map) && c.Roofed(map) && !c.Fogged(map)
                        && c.DistanceTo(door.Inside)>=6f && c.DistanceTo(door.Inside)<=12f
                        && (area==null || area[c]) && !CombatControlHelper.CellClaimed(pawn,c)
                        && !c.GetThingList(map).Any(t=>t is Pawn p && p!=pawn || t is Building_Trap && t.Faction==Faction.OfPlayer)
                        && !c.ContainsStaticFire(map) && map.gasGrid.DensityAt(c,GasType.ToxGas)==0
                        && map.gasGrid.DensityAt(c,GasType.DeadlifeDust)==0)
                        .OrderBy(c=>c==pawn.Position?-100f:c.DistanceTo(pawn.Position)+Math.Abs(c.DistanceTo(door.Inside)-9f)).Take(24);
                    foreach(var cell in cells)
                    {
                CombatPathBudgetHelper.Checkpoint();
                        float temperature=cell.GetTemperature(map);
                        if(temperature<minimum+2f || temperature>maximum-2f || !verb.CanHitTargetFrom(cell,new LocalTargetInfo(door.Inside)))continue;
                        if(cell==pawn.Position){result=cell;return true;}
                        if(++pathChecks>8)return false;
                        using(var path=CombatPathBudgetHelper.Query(pawn,pawn.Position,cell,PathEndMode.OnCell))
                        {
                            if(!CombatInterceptHelper.MovementSafe(pawn,path) || path.TotalCost>720f
                                || enemies.Any(e=>CombatInterceptHelper.ContactTicks(e,pawn)<=path.TotalCost+120f))continue;
                        }
                        result=cell;return true;
                    }
                }
            }
            return false;
        }
    }
}

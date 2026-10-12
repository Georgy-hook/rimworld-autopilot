using System;
using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using RIMAPI.Controllers;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class MeditationPlanningHelper
    {
        public static bool ScheduleOpportunity(bool protectedPawn, bool canMeditate, bool hasPsylink,
            bool natural, bool treeAvailable, int hours) => !protectedPawn && canMeditate
            && (hasPsylink || natural && treeAvailable) && hours < 4;
        private static IEnumerable<Thing> Trees(Map map) => map.listerThings.AllThings.Where(t=>t.def==ThingDefOf.Plant_TreeAnima && !t.Position.Fogged(map));
        private static int Hours(Pawn pawn) => pawn.timetable==null ? 0 : Enumerable.Range(0,24).Count(h=>pawn.timetable.GetAssignment(h)==TimeAssignmentDefOf.Meditate);
        private static bool Ready(Pawn pawn) => !SpecialistNativeSafety.Protected(pawn) && MeditationUtility.CanMeditateNow(pawn);
        private static bool Natural(Pawn pawn) => MeditationFocusDefOf.Natural.CanPawnUse(pawn);
        private static bool Near(Thing spot, Thing tree) => spot.Position.DistanceToSquared(tree.Position)<=MeditationUtility.FocusObjectSearchRadius*MeditationUtility.FocusObjectSearchRadius;
        private static bool SafeCell(Pawn pawn, IntVec3 cell) => cell.InBounds(pawn.Map) && !cell.Fogged(pawn.Map)
            && cell.Standable(pawn.Map) && cell.GetZone(pawn.Map)==null && !cell.IsForbidden(pawn)
            && MeditationUtility.SafeEnvironmentalConditions(pawn,cell,pawn.Map)
            && OrdinaryWorkSafety.Route(pawn,pawn.Position,cell,PathEndMode.OnCell)
            && pawn.CanReserveAndReach(cell,PathEndMode.OnCell,Danger.Some);
        private static IntVec3 Candidate(Pawn pawn, Thing tree) => GenRadial.RadialCellsAround(tree.Position,MeditationUtility.FocusObjectSearchRadius,false)
            .Where(c=>c.InBounds(pawn.Map) && !c.Fogged(pawn.Map) && c.Standable(pawn.Map)
                && !c.GetThingList(pawn.Map).Any(t=>t.def==ThingDefOf.MeditationSpot || t is Blueprint || t is Frame)
                && GenConstruct.CanPlaceBlueprintAt(ThingDefOf.MeditationSpot,c,Rot4.North,pawn.Map).Accepted)
            .OrderBy(c=>c.DistanceToSquared(pawn.Position)).ThenBy(c=>c.x).ThenBy(c=>c.z).Take(12)
            .Where(c=>SafeCell(pawn,c)).DefaultIfEmpty(IntVec3.Invalid).First();
        public static object Context(Map map, List<object> choices)
        {
            var trees=Trees(map).ToArray();
            var people=map.mapPawns.FreeColonistsSpawned.ToArray();
            var spots=map.listerBuildings.AllBuildingsColonistOfDef(ThingDefOf.MeditationSpot).ToArray();
            foreach(var pawn in people)
            {
                bool natural=Natural(pawn), ready=Ready(pawn);
                if (ScheduleOpportunity(!ready,MeditationUtility.CanMeditateNow(pawn),pawn.HasPsylink,natural,trees.Length>0,Hours(pawn)) && pawn.timetable!=null)
                    for(int h=0;h<24;h++) if(pawn.timetable.GetAssignment(h)==TimeAssignmentDefOf.Work || pawn.timetable.GetAssignment(h)==TimeAssignmentDefOf.Anything)
                        choices.Add(new {operation="meditation_hour",map_id=map.uniqueID,pawn_id=pawn.thingIDNumber,value=h.ToString(),
                            label=pawn.LabelShort+" hour "+h+" → Meditate",current_job=pawn.CurJobDef?.defName,
                            natural_focus=natural,has_psylink=pawn.HasPsylink,meditation_hours=Hours(pawn),
                            description="One ordinary meditation hour costs food/defense/work time. Sleep and recreation preserved. Natural focus can grow anima grass without a psylink only within tree range; target/arrival/grass still need observation."});
                if (!ready || !natural) continue;
                foreach(var tree in trees)
                {
                    foreach(var spot in spots.Where(s=>Near(s,tree) && SafeCell(pawn,s.Position) && MeditationUtility.IsValidMeditationBuildingForPawn(s,pawn)))
                    {
                        var assign=spot.TryGetComp<CompAssignableToPawn>();
                        if(assign!=null && !assign.AssignedPawnsForReading.Contains(pawn) && assign.AssignedPawnsForReading.Count==0 && assign.CanAssignTo(pawn).Accepted)
                            choices.Add(new {operation="meditation_assign",map_id=map.uniqueID,pawn_id=pawn.thingIDNumber,thing_id=spot.thingIDNumber,
                                label=pawn.LabelShort+" assign completed anima meditation spot",natural_focus=true,
                                description="Assigns a completed free spot, not a meditation job, grass or psylink."});
                    }
                    if(spots.Any(s=>Near(s,tree) && MeditationUtility.IsValidMeditationBuildingForPawn(s,pawn))
                        || map.listerThings.AllThings.OfType<Blueprint>().Any(b=>b.def.entityDefToBuild==ThingDefOf.MeditationSpot && Near(b,tree)))continue;
                    var cell=Candidate(pawn,tree);
                    if(cell.IsValid) choices.Add(new {operation="meditation_spot",map_id=map.uniqueID,pawn_id=pawn.thingIDNumber,thing_id=tree.thingIDNumber,
                        value=cell.x+":"+cell.z,label="Plan free anima meditation spot for "+pawn.LabelShort,natural_focus=true,
                        description="Normal free blueprint on a revealed safe reachable cell within 3.9 cells of the tree. Needs construction, assignment and ordinary meditation; does not change grass or powers."});
                }
            }
            return new {people=people.Select(p=>new {pawn_id=p.thingIDNumber,name=p.LabelShort,has_psylink=p.HasPsylink,
                focus_types=MeditationUtility.FocusTypesAvailableForPawn(p).Select(f=>f.defName).ToArray(),can_meditate_now=Ready(p),
                meditation_hours=Hours(p),current_job=p.CurJobDef?.defName,
                last_meditation_tick=AccessTools.Field(p.psychicEntropy?.GetType(),"lastMeditationTick")?.GetValue(p.psychicEntropy)}).ToArray(),
                trees=trees.Select(t=>new {thing_id=t.thingIDNumber,x=t.Position.x,z=t.Position.z,
                    inspect=t.GetInspectString(),grass_count=t.TryGetComp<CompSpawnSubplant>()?.SubplantsForReading.Count}).ToArray(),
                limits="Natural focus is required by the loaded meditation job for anima grass. Grass/psylink/psyfocus are observed separately. A tree does not make an ineligible pawn tribal."};
        }
        public static bool Apply(Map map, Pawn pawn, string operation, string value, int thingId)
        {
            if(map==null || pawn==null || pawn.Map!=map || !Ready(pawn))return false;
            if(operation=="meditation_hour" && ScheduleOpportunity(false,true,pawn.HasPsylink,Natural(pawn),Trees(map).Any(),Hours(pawn))
                && int.TryParse(value,out int h) && h>=0 && h<24 && pawn.timetable!=null
                && (pawn.timetable.GetAssignment(h)==TimeAssignmentDefOf.Work || pawn.timetable.GetAssignment(h)==TimeAssignmentDefOf.Anything))
                {pawn.timetable.SetAssignment(h,TimeAssignmentDefOf.Meditate);return true;}
            if(!Natural(pawn))return false;
            var thing=map.listerThings.AllThings.FirstOrDefault(t=>t.thingIDNumber==thingId);
            if(operation=="meditation_assign" && thing is Building spot && spot.def==ThingDefOf.MeditationSpot
                && Trees(map).Any(t=>Near(spot,t)) && SafeCell(pawn,spot.Position) && MeditationUtility.IsValidMeditationBuildingForPawn(spot,pawn))
            {var assign=spot.TryGetComp<CompAssignableToPawn>();if(assign!=null && assign.AssignedPawnsForReading.Count==0 && assign.CanAssignTo(pawn).Accepted){assign.TryAssignPawn(pawn);return assign.AssignedPawnsForReading.Contains(pawn);}}
            if(operation=="meditation_spot" && thing?.def==ThingDefOf.Plant_TreeAnima && !thing.Position.Fogged(map))
            {
                string[] xy=(value ?? "").Split(':');
                if(xy.Length!=2 || !int.TryParse(xy[0],out int x) || !int.TryParse(xy[1],out int z))return false;
                var cell=new IntVec3(x,0,z);
                if(!SafeCell(pawn,cell) || cell.DistanceToSquared(thing.Position)>MeditationUtility.FocusObjectSearchRadius*MeditationUtility.FocusObjectSearchRadius
                    || !GenConstruct.CanPlaceBlueprintAt(ThingDefOf.MeditationSpot,cell,Rot4.North,map).Accepted)return false;
                if(map.listerThings.AllThings.Any(t=>Near(t,thing) && (t is Building s && s.def==ThingDefOf.MeditationSpot && MeditationUtility.IsValidMeditationBuildingForPawn(s,pawn)
                    || t is Blueprint b && b.def.entityDefToBuild==ThingDefOf.MeditationSpot)))return false;
                return GenConstruct.PlaceBlueprintForBuild(ThingDefOf.MeditationSpot,cell,map,Rot4.North,Faction.OfPlayer,null)!=null;
            }
            return false;
        }
    }
}

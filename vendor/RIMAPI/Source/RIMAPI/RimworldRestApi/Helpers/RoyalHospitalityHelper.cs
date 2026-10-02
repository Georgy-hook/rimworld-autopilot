using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;
using RIMAPI.Core;
using RIMAPI.Models;

namespace RIMAPI.Helpers
{
    public static class RoyalHospitalityHelper
    {
        private static List<RoomRequirement> Bedroom(Pawn pawn) => pawn.royalty?.HighestTitleWithBedroomRequirements()?.def.GetBedroomRequirements(pawn)?.ToList() ?? new List<RoomRequirement>();
        private static List<RoomRequirement> Throne(Pawn pawn) => pawn.royalty?.HighestTitleWithThroneRoomRequirements()?.def.throneRoomRequirements ?? new List<RoomRequirement>();
        private static List<string> FloorTags(List<RoomRequirement> requirements) => requirements.OfType<RoomRequirement_TerrainWithTags>().SelectMany(r=>r.tags ?? new List<string>()).Distinct().ToList();
        private static List<string> BuildingDefs(List<RoomRequirement> requirements,Type buildingType) => requirements.OfType<RoomRequirement_Thing>().Select(r=>r.thingDef)
            .Concat(requirements.OfType<RoomRequirement_ThingAnyOf>().SelectMany(r=>r.things ?? new List<ThingDef>()))
            .Where(d=>d?.thingClass!=null && buildingType.IsAssignableFrom(d.thingClass)).Select(d=>d.defName).Distinct().ToList();
        private static List<string> Floors(List<RoomRequirement> requirements)
        {
            var tags=FloorTags(requirements);
            return tags.Count==0 ? new List<string>() : DefDatabase<TerrainDef>.AllDefsListForReading.Where(d=>tags.All(tag=>d.tags?.Contains(tag)==true)).Select(d=>d.defName).ToList();
        }
        private static List<object> Furniture(List<RoomRequirement> requirements)
        {
            var result=new List<object>();
            foreach(var r in requirements)
            {
                List<ThingDef> defs=r is RoomRequirement_Thing thing ? new List<ThingDef>{thing.thingDef}
                    : r is RoomRequirement_ThingAnyOf any ? any.things : null;
                if(defs==null)continue;
                int count=r is RoomRequirement_ThingCount singleCount ? singleCount.count : r is RoomRequirement_ThingAnyOfCount anyCount ? anyCount.count : 1;
                result.Add(new { any_of=defs.Where(d=>d!=null).Select(d=>d.defName).ToList(),count,min_quality=(string)null,assignment_required=r is RoomRequirement_HasAssignedThroneAnyOf });
            }
            return result;
        }
        private static object PawnRow(Pawn p,Map map,List<int> qualifying=null)
        {
            var bedroom=Bedroom(p);var throne=Throne(p);var title=p.royalty?.MostSeniorTitle;
            Room bedRoom=p.ownership?.OwnedBed?.GetRoom();Room throneRoom=p.ownership?.AssignedThrone?.GetRoom();
            return new { pawn_id=p.thingIDNumber,pawn_name=p.LabelShort,quest_lodger=p.IsQuestLodger(),on_map=p.Spawned && p.Map==map,
                title_def_name=title?.def.defName,title_label=title?.Label,seniority=title?.def.seniority ?? 0,
                mood=p.needs?.mood?.CurLevelPercentage,food=p.needs?.food?.CurLevelPercentage,rest=p.needs?.rest?.CurLevelPercentage,
                current_job=p.CurJobDef?.defName,assigned_bed_id=p.ownership?.OwnedBed?.thingIDNumber,bedroom_id=bedRoom?.ID,
                assigned_throne_id=p.ownership?.AssignedThrone?.thingIDNumber,throne_room_id=throneRoom?.ID,
                requires_bedroom=p.royalty.CanRequireBedroom() && bedroom.Count>0,has_unmet_bedroom_requirements=bedroom.Count>0 && (!p.royalty.HasPersonalBedroom() || p.royalty.AnyUnmetBedroomRequirements()),
                minimum_bedroom_area=bedroom.OfType<RoomRequirement_Area>().Select(r=>r.area).DefaultIfEmpty(0).Max(),
                minimum_bedroom_impressiveness=bedroom.OfType<RoomRequirement_Impressiveness>().Select(r=>r.impressiveness).DefaultIfEmpty(0).Max(),
                bedroom_requirements=bedroom.Select(r=>r.LabelCap(bedRoom).ToString()).ToList(),bedroom_requirement_types=bedroom.Select(r=>r.GetType().Name).ToList(),
                bedroom_required_things=Furniture(bedroom),bedroom_required_bed_defs=BuildingDefs(bedroom,typeof(Building_Bed)),bedroom_floor_tags=FloorTags(bedroom),bedroom_compatible_floor_defs=Floors(bedroom),
                bedroom_unmet_reasons=bedroom.Count>0 ? p.royalty.GetUnmetBedroomRequirements().ToList() : new List<string>(),
                requires_throne_room=p.royalty.CanRequireThroneroom() && throne.Count>0,has_unmet_throne_room_requirements=throne.Count>0 && (p.ownership?.AssignedThrone==null || p.royalty.AnyUnmetThroneroomRequirements()),
                minimum_throne_room_area=throne.OfType<RoomRequirement_Area>().Select(r=>r.area).DefaultIfEmpty(0).Max(),
                minimum_throne_room_impressiveness=throne.OfType<RoomRequirement_Impressiveness>().Select(r=>r.impressiveness).DefaultIfEmpty(0).Max(),
                throne_room_requirements=throne.Select(r=>r.LabelCap(throneRoom).ToString()).ToList(),throne_room_requirement_types=throne.Select(r=>r.GetType().Name).ToList(),
                throne_room_required_things=Furniture(throne),throne_required_defs=BuildingDefs(throne,typeof(Building_Throne)),throne_room_floor_tags=FloorTags(throne),throne_room_compatible_floor_defs=Floors(throne),
                throne_unmet_reasons=throne.Count>0 ? p.royalty.GetUnmetThroneroomRequirements().ToList() : new List<string>(),
                qualifying_unassigned_bed_ids=qualifying ?? new List<int>(),
                honor=Find.FactionManager.AllFactionsListForReading.Where(f=>f.def.HasRoyalTitles).Select(f=>new {faction_id=f.loadID,faction=f.Name,
                    favor=p.royalty?.GetFavor(f) ?? 0,current_title=p.royalty?.GetCurrentTitle(f)?.defName}).ToList() };
        }
        public static object Context(Map map)
        {
            if(!ModsConfig.RoyaltyActive)return new {active=false};
            var guests=new List<object>();
            foreach(var quest in Find.QuestManager.QuestsListForReading.Where(q=>!q.Historical && q.root?.defName=="EndGame_RoyalAscent"))
            foreach(var part in quest.PartsListForReading.OfType<QuestPart_RequirementsToAcceptBedroom>().Where(p=>p.mapParent?.Map==map))
            {
                var report=part.CanAccept();
                guests.Add(new {quest_id=quest.id,map_id=map.uniqueID,can_accept=report.Accepted,reason=report.Reason,
                    guests=part.targetPawns.Where(p=>p!=null && !p.Dead).Select(p=>PawnRow(p,map,map.listerBuildings.allBuildingsColonist.OfType<Building_Bed>()
                        .Where(b=>b.GetRoom()!=null && b.TryGetComp<CompAssignableToPawn>()?.AssignedPawnsForReading.Count==0
                            && p.royalty?.HighestTitleWithBedroomRequirements() is RoyalTitle title && RoyalTitleUtility.BedroomSatisfiesRequirements(b.GetRoom(),title))
                        .Select(b=>b.thingIDNumber).ToList())).ToList() });
            }
            return new {active=true,colonists=map.mapPawns.AllPawnsSpawned.Where(p=>!p.Dead && p.royalty!=null && (p.IsColonistPlayerControlled || p.IsQuestLodger())).Select(p=>PawnRow(p,map)).ToList(),
                pending_bedroom_quests=guests,title_catalog=DefDatabase<RoyalTitleDef>.AllDefsListForReading.Select(d=>new {def_name=d.defName,label=d.label,seniority=d.seniority,
                    favor_cost=d.favorCost,awardable=d.Awardable,bedroom_requirements=Furniture(d.bedroomRequirements ?? new List<RoomRequirement>()),
                    throne_room_requirements=Furniture(d.throneRoomRequirements ?? new List<RoomRequirement>()),food_requirement=d.foodRequirement.ToString(),disabled_work=d.disabledWorkTags.ToString()}).ToList(),
                warning="Native title/quest eligibility and actual bedroom requirements apply; room construction and assignment do not guarantee guest mood or a successful visit."};
        }
        public static List<SpecialistRoyalAssignmentDto> Options(Map map)
        {
            var result=new List<SpecialistRoyalAssignmentDto>();if(!ModsConfig.RoyaltyActive)return result;
            foreach(Pawn pawn in map.mapPawns.AllPawnsSpawned.Where(p=>!p.Dead && p.royalty?.MostSeniorTitle!=null && (p.IsColonistPlayerControlled || p.IsQuestLodger())))
            foreach(Building building in map.listerBuildings.allBuildingsColonist.Where(b=>b is Building_Bed || b is Building_Throne))
            {
                var assign=building.TryGetComp<CompAssignableToPawn>();Room room=building.GetRoom();
                if(assign==null || room==null || !room.ProperRoom || !assign.AssigningCandidates.Contains(pawn) || !assign.CanAssignTo(pawn).Accepted
                    || assign.AssignedPawnsForReading.Any(p=>p!=pawn) || !pawn.CanReach(building,PathEndMode.Touch,Danger.Some))continue;
                bool bed=building is Building_Bed;
                if(bed && (((Building_Bed)building).Medical || ((Building_Bed)building).ForPrisoners || pawn.ownership.OwnedBed==building
                    || Bedroom(pawn).Count==0 || !Bedroom(pawn).All(r=>r.MetOrDisabled(room,pawn))))continue;
                if(!bed && (pawn.ownership.AssignedThrone==building || Throne(pawn).Count==0 || RoomRoleWorker_ThroneRoom.Validate(room)!=null
                    || !Throne(pawn).All(r=>r is RoomRequirement_HasAssignedThroneAnyOf assigned ? assigned.things.Contains(building.def) : r.MetOrDisabled(room,pawn))))continue;
                result.Add(new SpecialistRoyalAssignmentDto {Kind=bed ? "royal_bed" : "royal_throne",PawnId=pawn.thingIDNumber,ThingId=building.thingIDNumber,RoomId=room.ID,
                    Label=$"{pawn.LabelShort}: assign {building.LabelShort} in room {room.ID}",Description="Current native room requirements met; changes ownership through the native assignment component; mood and visit outcome remain unobserved."});
            }
            return result;
        }
        public static ApiResult<CapabilityOrderResultDto> Execute(Map map,SpecialistOrderRequestDto request)
        {
            var result=new CapabilityOrderResultDto{Reason="royal_assignment_no_longer_feasible"};
            var option=Options(map).FirstOrDefault(o=>o.Kind==request.Kind && o.PawnId==request.PawnId && o.ThingId==request.ThingId);
            if(option==null)return ApiResult<CapabilityOrderResultDto>.Ok(result);
            var pawn=MapHelper.GetThingOnMapById(map.uniqueID,option.PawnId) as Pawn;var building=MapHelper.GetThingOnMapById(map.uniqueID,option.ThingId);
            building.TryGetComp<CompAssignableToPawn>().TryAssignPawn(pawn);
            result.Applied=request.Kind=="royal_bed" ? pawn.ownership.OwnedBed==building : pawn.ownership.AssignedThrone==building;
            result.TargetId=option.ThingId;result.Reason=result.Applied ? "native_royal_room_ownership_assigned; hospitality_outcome_unobserved" : "native_assignment_rejected";
            return ApiResult<CapabilityOrderResultDto>.Ok(result);
        }
    }
}

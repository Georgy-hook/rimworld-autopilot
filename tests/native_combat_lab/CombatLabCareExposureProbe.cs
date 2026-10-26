#if LAYA_COMBAT_LAB
using System;
using System.Collections.Generic;
using System.Linq;
using RIMAPI.Helpers;
using RIMAPI.Models;
using RimWorld;
using Verse;
using Verse.AI;
namespace RIMAPI.Controllers
{
    public static class CombatLabCareExposureProbe
    {
        private static void Register(Pawn pawn,Job job,Pawn enemy,bool moving=false)
        {
            pawn.drafter.Drafted=true;
            if(!CombatOrderHelper.Take(pawn,ref job))throw new InvalidOperationException("Declared ordinary job rejected");
            CombatControlHelper.Remember(new CombatTacticRequestDto{MapId=pawn.Map.uniqueID,Tactic="hold_cover",TargetPawnId=enemy.thingIDNumber,FighterIds=new List<int>{pawn.thingIDNumber}},
                new CombatTacticResponseDto{Applied=true,Tactic="hold_cover",TargetPawnId=enemy.thingIDNumber,
                    PositionedPawnIds=moving?new List<int>{pawn.thingIDNumber}:new List<int>(),
                    AttackingPawnIds=moving?new List<int>():new List<int>{pawn.thingIDNumber}},pawn.Map);
        }
        public static object Run(string phase)
        {
            if(CombatLabState.Scenario!="execution_contract_care")throw new InvalidOperationException("Retained care fixture required");
            var doctor=CombatLabState.Allies[0];var map=doctor.Map;var enemy=CombatLabState.Enemies[0];
            if(phase=="care_declare")
            {
                if(!CombatLabState.HoldInitial)throw new InvalidOperationException("Declare only before begin");
                // This is a new needs/triage contract, not a raid benchmark.
                // All differences are declared before its first native tick.
                enemy.DeSpawn();
                foreach(var pawn in CombatLabState.Allies)
                {
                    pawn.drafter.Drafted=false;
                    var wait=JobMaker.MakeJob(JobDefOf.Wait,12000);wait.playerForced=true;
                    pawn.jobs.StartJob(wait,JobCondition.InterruptForced);
                }
                var torso=CombatLabState.Allies[2].health.hediffSet.GetNotMissingParts().First(p=>p.def.defName=="Torso");
                CombatLabState.Allies[2].health.AddHediff(DefDatabase<HediffDef>.GetNamed("Cut"),torso).Severity=3f;
                doctor.needs.food.CurLevelPercentage=.25f;doctor.needs.rest.CurLevelPercentage=.15f;
                var food=ThingMaker.MakeThing(ThingDefOf.MealSurvivalPack);food.stackCount=4;
                GenSpawn.Spawn(food,new IntVec3(109,0,110),map);
                var cell=new IntVec3(110,0,114);
                if(cell.GetThingList(map).Any(t=>t is Building))throw new InvalidOperationException("Declared recovery bed cell unavailable");
                var bed=(Building_Bed)ThingMaker.MakeThing(ThingDefOf.Bed,ThingDefOf.WoodLog);bed.SetFaction(Faction.OfPlayer);GenSpawn.Spawn(bed,cell,map);
                doctor.ownership.ClaimBedIfNonMedical(bed);
                var support=ThingMaker.MakeThing(ThingDefOf.Wall,ThingDefOf.BlocksGranite);support.SetFaction(Faction.OfPlayer);
                GenSpawn.Spawn(support,new IntVec3(109,0,114),map);foreach(var roofCell in bed.OccupiedRect())map.roofGrid.SetRoof(roofCell,RoofDefOf.RoofConstructed);
            }
            else if(phase=="ranged_declare")
            {
                if(!CombatLabState.HoldInitial)throw new InvalidOperationException("Declare only before begin");
                var torso=doctor.health.hediffSet.GetNotMissingParts().First(p=>p.def.defName=="Torso");
                doctor.health.AddHediff(DefDatabase<HediffDef>.GetNamed("Cut"),torso).Severity=2f;
                foreach(var eq in enemy.equipment.AllEquipmentListForReading.ToList())eq.Destroy();
                enemy.equipment.AddEquipment((ThingWithComps)ThingMaker.MakeThing(DefDatabase<ThingDef>.GetNamed("Gun_HeavySMG")));
                foreach(var cell in new[]{new IntVec3(112,0,108),new IntVec3(112,0,109)})
                {
                    if(cell.GetThingList(map).Any(t=>t is Building))throw new InvalidOperationException("Declared cover wall cell unavailable");
                    var wall=ThingMaker.MakeThing(ThingDefOf.Wall,ThingDefOf.BlocksGranite);wall.SetFaction(Faction.OfPlayer);GenSpawn.Spawn(wall,cell,map);
                }
                var cover=CombatLabState.Allies[2];cover.DeSpawn();GenSpawn.Spawn(cover,new IntVec3(110,0,118),map);
                foreach(var gun in new[]{doctor,cover})
                {var fire=JobMaker.MakeJob(JobDefOf.AttackStatic,enemy);fire.playerForced=true;Register(gun,fire,enemy);}
                var moving=CombatLabState.Allies[1];var move=JobMaker.MakeJob(JobDefOf.Goto,new IntVec3(104,0,118));move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                Register(moving,move,enemy,true);
                doctor.stances.SetStance(new Stance_Cooldown(180,enemy,doctor.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb));
                var foe=JobMaker.MakeJob(JobDefOf.AttackStatic,doctor);foe.playerForced=true;enemy.jobs.StartJob(foe,JobCondition.InterruptForced);
            }
            else throw new InvalidOperationException("Unknown declared care/exposure phase");
            return new{phase,map_id=map.uniqueID,after=CombatLabState.State(true),recovery=CaregiverRecoveryHelper.Diagnostics(),
                declared_beds=map.listerBuildings.allBuildingsColonist.OfType<Building_Bed>().Select(b=>new{id=b.thingIDNumber,
                    cells=b.OccupiedRect().Select(c=>new{x=c.x,z=c.z,roofed=c.Roofed(map)}).ToArray(),
                    temperature=b.Position.GetTemperature(map),native_doctor_can_reserve_reach=doctor.CanReserveAndReach(b,PathEndMode.OnCell,Danger.Some),
                    native_safe_route=ResilienceAutomationHelper.RoutineRouteSafe(doctor,b)}).ToArray(),
                statement="Separate physical contract; declared needs, injuries, services and orders before first tick only. No original raid fixture was changed and no raid win is added."};
        }
    }
}
#endif

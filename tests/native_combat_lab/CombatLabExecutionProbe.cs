#if LAYA_COMBAT_LAB
// Declared executor contracts. These commands never run in a raid benchmark.
using System;
using System.Linq;
using RIMAPI.Helpers;
using RIMAPI.Models;
using RimWorld;
using Verse;
using Verse.AI;
namespace RIMAPI.Controllers
{
    public static class CombatLabExecutionProbe
    {
        public static IntVec3 Goal=>new IntVec3(110,0,104);
        public static void Initialize(string scenario,Map map)
        {
            if(!scenario.StartsWith("execution_contract_",StringComparison.Ordinal))return;
            if(CombatLabState.Allies.Count!=3 || CombatLabState.Enemies.Count!=1)
                throw new InvalidOperationException("Declared three-defender executor cohort required");
            var doctor=CombatLabState.Allies.FirstOrDefault(p=>!p.WorkTypeIsDisabled(WorkTypeDefOf.Doctor));
            if(doctor==null)throw new InvalidOperationException("No legal doctor in declared cohort; no reroll");
            CombatLabState.Allies.Remove(doctor);CombatLabState.Allies.Insert(0,doctor);
            var cells=new[]{new IntVec3(110,0,110),new IntVec3(108,0,112),new IntVec3(108,0,108)};
            for(int n=0;n<3;n++)
            {
                var p=CombatLabState.Allies[n];p.DeSpawn();GenSpawn.Spawn(p,cells[n],map);
                p.drafter.Drafted=n==0;
                var waiting=JobMaker.MakeJob(n==0?JobDefOf.Wait_Combat:JobDefOf.Wait,12000);
                waiting.playerForced=true;waiting.canUseRangedWeapon=false;
                p.jobs.StartJob(waiting,JobCondition.InterruptForced);
            }
            var actor=CombatLabState.Allies[0];
            foreach(var eq in actor.equipment.AllEquipmentListForReading.ToList())eq.Destroy();
            actor.equipment.AddEquipment((ThingWithComps)ThingMaker.MakeThing(DefDatabase<ThingDef>.GetNamed("Gun_AssaultRifle")));
            var enemy=CombatLabState.Enemies[0];enemy.DeSpawn();GenSpawn.Spawn(enemy,new IntVec3(132,0,110),map);
            var enemyWait=JobMaker.MakeJob(JobDefOf.Wait,12000);enemyWait.playerForced=true;
            enemy.jobs.StartJob(enemyWait,JobCondition.InterruptForced);
            if(scenario.EndsWith("care",StringComparison.Ordinal))
            {
                var patient=CombatLabState.Allies[1];
                var torso=patient.health.hediffSet.GetNotMissingParts().First(p=>p.def.defName=="Torso");
                patient.health.AddHediff(DefDatabase<HediffDef>.GetNamed("Cut"),torso).Severity=3f;
            }
            if(scenario.EndsWith("blocked",StringComparison.Ordinal))
                foreach(var c in new[]{Goal+IntVec3.North,Goal+IntVec3.South,Goal+IntVec3.East,Goal+IntVec3.West})
                {
                    var wall=ThingMaker.MakeThing(ThingDefOf.Wall,ThingDefOf.BlocksGranite);
                    wall.SetFaction(Faction.OfPlayer);GenSpawn.Spawn(wall,c,map);
                }
            CombatLabState.SetupMark("declared_executor_positions_and_services_before_held_baseline");
        }
        public static object Run(string phase)
        {
            if(CombatLabState.Scenario?.StartsWith("execution_contract_",StringComparison.Ordinal)!=true)
                throw new InvalidOperationException("Executor probe is restricted to its declared contract fixture");
            var p=CombatLabState.Allies[0];var enemy=CombatLabState.Enemies[0];
            int tick=Find.TickManager.TicksGame;var before=CombatLabState.State(false);bool accepted=false;
            if(phase=="declare")
            {
                if(!CombatLabState.HoldInitial || CombatLabState.StepTicks!=0)
                    throw new InvalidOperationException("Initial declared action requires held native clock");
                var hold=JobMaker.MakeJob(JobDefOf.Wait_Combat);hold.playerForced=true;hold.canUseRangedWeapon=false;
                if(!CombatOrderHelper.Take(p,ref hold))throw new InvalidOperationException("Initial owned hold rejected");
                if(CombatLabState.Scenario.EndsWith("care",StringComparison.Ordinal))
                {
                    var fire=JobMaker.MakeJob(JobDefOf.AttackStatic,enemy);fire.playerForced=true;
                    accepted=CombatOrderHelper.Take(p,ref fire);
                    CombatControlHelper.Remember(new CombatTacticRequestDto{Tactic="stationary_fire",FighterIds=new System.Collections.Generic.List<int>{p.thingIDNumber}},
                        new CombatTacticResponseDto{Applied=accepted,Tactic="stationary_fire",AttackingPawnIds=new System.Collections.Generic.List<int>{p.thingIDNumber},TargetPawnId=enemy.thingIDNumber},p.Map);
                }
                else
                {
                    // This initial cooldown is part of the declared API fixture,
                    // set only before its first native tick, identically A/D0.
                    p.stances.SetStance(new Stance_Cooldown(120,enemy,p.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb));
                    var move=JobMaker.MakeJob(JobDefOf.Goto,Goal);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                    accepted=CombatOrderHelper.Take(p,ref move);
                    if(accepted)
                    {
                        CombatControlHelper.RememberMove(p,move,CombatOrderHelper.QueueShot(p,enemy));
                        CombatControlHelper.Remember(new CombatTacticRequestDto{Tactic="hold_cover",FighterIds=new System.Collections.Generic.List<int>{p.thingIDNumber}},
                            new CombatTacticResponseDto{Applied=true,Tactic="hold_cover",PositionedPawnIds=new System.Collections.Generic.List<int>{p.thingIDNumber},TargetPawnId=enemy.thingIDNumber},p.Map);
                    }
                }
            }
            else if(phase=="repeat_fire")
            {var fire=JobMaker.MakeJob(JobDefOf.AttackStatic,enemy);fire.playerForced=true;accepted=CombatOrderHelper.Take(p,ref fire);}
            else if(phase=="repeat_move")
            {var move=JobMaker.MakeJob(JobDefOf.Goto,Goal);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;accepted=CombatOrderHelper.Take(p,ref move);}
            else if(phase=="manual_care")
            {
                if(!CombatLabState.Scenario.EndsWith("care",StringComparison.Ordinal) || CombatLabState.HoldInitial)
                    throw new InvalidOperationException("Later medical override is declared only in the active care contract");
                p.drafter.Drafted=false;
                var manual=JobMaker.MakeJob(JobDefOf.Wait,120);manual.playerForced=true;
                p.jobs.StartJob(manual,JobCondition.InterruptForced);
                var care=JobMaker.MakeJob(JobDefOf.TendPatient,CombatLabState.Allies[1]);care.playerForced=true;
                p.jobs.jobQueue.EnqueueLast(care);accepted=true;
            }
            else throw new InvalidOperationException("Unknown executor probe phase");
            return new{phase,accepted,tick,goal_x=Goal.x,goal_z=Goal.z,before,after=CombatLabState.State(false),
                purpose="Declared native executor contract; no autonomous raid qualification credit"};
        }
    }
}
#endif

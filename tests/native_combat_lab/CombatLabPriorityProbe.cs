#if LAYA_COMBAT_LAB
using System;
using System.Linq;
using System.Reflection;
using RIMAPI.Helpers;
using RimWorld;
using Verse;
using Verse.AI;
namespace RIMAPI.Controllers
{
    public static class CombatLabPriorityProbe
    {
        public static object Read()
        {
            if(CombatLabState.Scenario!="ranged_priority_contract" || !CombatLabState.HoldInitial
                || CombatLabState.StepTicks!=0 || CombatLabState.Allies.Count!=2 || CombatLabState.Enemies.Count!=2)
                throw new InvalidOperationException("Priority probe requires its exact held initial contract");
            var before=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            int tick=Find.TickManager.TicksGame;
            var actor=CombatLabState.Allies[0];var foes=CombatLabState.Enemies;
            var guns=CombatLabState.Allies.ToArray();
            var group=typeof(CombatControlHelper).GetMethod("GroupTarget",BindingFlags.NonPublic|BindingFlags.Static);
            var urgency=typeof(CombatControlHelper).GetMethod("ThreatUrgency",BindingFlags.NonPublic|BindingFlags.Static);
            var forecast=typeof(CombatControlHelper).GetMethod("ObservedRangedPressure",BindingFlags.NonPublic|BindingFlags.Static)
                ?? typeof(CombatControlHelper).GetMethod("RangedPressure",BindingFlags.NonPublic|BindingFlags.Static);
            if(group==null || urgency==null || forecast==null)throw new MissingMethodException("Native production priority methods unavailable");
            var selected=(Pawn)group.Invoke(null,new object[]{actor,foes,foes[0]});
            var rows=foes.Select(enemy=>new{enemy=enemy.thingIDNumber,weapon=enemy.equipment.Primary.def.defName,
                x=enemy.Position.x,z=enemy.Position.z,job=enemy.CurJobDef?.defName,
                moving=enemy.pather.Moving,known_goal=enemy.pather.Destination.Cell.ToString(),
                currently_shootable=CombatInterceptHelper.CanShootNow(actor,enemy),
                current_pressure=guns.Sum(g=>CombatControlHelper.ShotQuality(enemy,g,enemy.Position)),
                observed_future_pressure=(float)forecast.Invoke(null,new object[]{enemy,guns}),
                actual_urgency=(float)urgency.Invoke(null,new object[]{enemy,guns,null,(int?)null})}).ToArray();
            var after=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            return new{native_process_id=CombatLabState.ProcessId,native_instance_id=CombatLabState.InstanceId,
                tick,scenario=CombatLabState.Scenario,actual_group_target=selected?.thingIDNumber,
                actor=actor.thingIDNumber,rifle=foes[0].thingIDNumber,flanker=foes[1].thingIDNumber,
                rows,rng_before=before,rng_after=after,rng_unchanged=before==after,
                tick_unchanged=Find.TickManager.TicksGame==tick,
                limits="Calls the actual production GroupTarget in the held initial native state. No issued order, shot, hit, injury, raid or survival credit."};
        }
    }
}
#endif

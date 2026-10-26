#if LAYA_COMBAT_LAB
using System;
using System.Linq;
using RIMAPI.Helpers;
using RIMAPI.Models;
using RimWorld;
using Verse;
namespace RIMAPI.Controllers
{
    public static class CombatLabPreparedPostProbe
    {
        private static bool used;
        public static object Run()
        {
            if(used || !CombatLabState.LoadedBaseline || CombatLabState.HoldInitial || (CombatLabState.StepTicks!=180 && CombatLabState.StepTicks!=30)
                || CombatLabState.Scenario!="melee_rush" || CombatLabState.Allies.Count!=4 || CombatLabState.Enemies.Count!=8)
                throw new InvalidOperationException("Exact unused saved choke cohort required");
            used=true;int tick=Find.TickManager.TicksGame;
            string rng=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            var target=CombatLabState.Enemies[0];
            var before=CombatLabState.Allies.Select(p=>new{id=p.thingIDNumber,x=p.Position.x,z=p.Position.z,job=p.CurJobDef.defName}).ToArray();
            var request=new CombatTacticRequestDto{MapId=CombatLabState.Map.uniqueID,Tactic="hold_cover",
                FighterIds=CombatLabState.Allies.Select(p=>p.thingIDNumber).ToList(),TargetPawnId=target.thingIDNumber};
            var result=CombatTacticsHelper.Apply(request);
            return new{native_process_id=CombatLabState.ProcessId,native_instance_id=CombatLabState.InstanceId,tick,
                success=result.Success,result=result.Data,errors=result.Errors,before,
                after=CombatLabState.Allies.Select(p=>new{id=p.thingIDNumber,x=p.Position.x,z=p.Position.z,
                    job=p.CurJobDef.defName,goal_x=p.CurJob.targetA.Cell.x,goal_z=p.CurJob.targetA.Cell.z,
                    plan=CombatControlHelper.TestMode(p)}).ToArray(),
                rng_before=rng,rng_after=CombatLabState.RandomProperty.GetValue(null,null).ToString(),
                tick_unchanged=tick==Find.TickManager.TicksGame,
                limits="One actual hold_cover action on the exact held saved four-gun/eight-raider cohort. No fixture edits or model/raid qualification."};
        }
    }
}
#endif

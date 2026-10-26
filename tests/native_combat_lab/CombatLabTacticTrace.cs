#if LAYA_COMBAT_LAB
using System;
using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using RIMAPI.Core;
using RIMAPI.Helpers;
using RIMAPI.Models;
using Verse;
namespace RIMAPI.Controllers
{
    public static class CombatLabTacticTrace
    {
        public static readonly List<object> Rows=new List<object>();
        public static object ReadPawns(CombatTacticRequestDto request)
        {
            return CombatLabState.Allies.Where(p=>request.FighterIds!=null && request.FighterIds.Contains(p.thingIDNumber))
                .Select(p=>new{id=p.thingIDNumber,x=p.Position.x,z=p.Position.z,job=p.CurJobDef?.defName,
                    job_id=p.CurJob?.loadID,target=p.CurJob?.targetA.Thing?.thingIDNumber,
                    goal_x=p.CurJob?.targetA.Cell.x,goal_z=p.CurJob?.targetA.Cell.z,
                    mode=CombatControlHelper.TestMode(p),warmup=(p.stances.curStance as Stance_Warmup)?.ticksLeft,
                    native_path_ready=p.pather?.curPath?.Found,native_path_total=p.pather?.curPath?.TotalCost}).ToArray();
        }
    }
    [HarmonyPatch(typeof(CombatTacticsHelper),nameof(CombatTacticsHelper.Apply))]
    public static class CombatLabTacticHook
    {
        public static void Prefix(CombatTacticRequestDto request,out object __state)
        {
            __state=CombatLabTacticTrace.Rows.Count<128 && CombatLabState.Map==Find.CurrentMap
                ?new{tick=Find.TickManager.TicksGame,tactic=request.Tactic,target=request.TargetPawnId,before=CombatLabTacticTrace.ReadPawns(request)}:null;
        }
        public static void Postfix(CombatTacticRequestDto request,ApiResult<CombatTacticResponseDto> __result,object __state)
        {
            if(__state!=null && CombatLabTacticTrace.Rows.Count<128)CombatLabTacticTrace.Rows.Add(new{input=__state,
                success=__result.Success,notes=__result.Data?.Notes,errors=__result.Errors,after=CombatLabTacticTrace.ReadPawns(request)});
        }
    }
}
#endif

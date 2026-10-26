#if LAYA_COMBAT_LAB
using System;
using System.Linq;
using System.Reflection;
using HarmonyLib;
using RIMAPI.Helpers;
using Verse;
using Verse.AI;

namespace RIMAPI.Controllers
{
    // Arms one declared fault only inside an actual HTTP Apply. It never runs
    // in benchmarks or changes budgets, jobs, combat physics or pawn health.
    public static class CombatLabHttpBudgetProbe
    {
        public static object Arm(string phase)
        {
            if(CombatLabState.Scenario!="execution_contract_care")
                throw new InvalidOperationException("Retained care contract only");
            if(!new[]{"prefilter","core","after_order","readback","remember","clear"}.Contains(phase))
                throw new InvalidOperationException("Undeclared HTTP boundary phase");
            CombatTacticsHelper.TestDeferredApplyPhase=phase=="clear"?null:phase;
            return new{phase,armed=CombatTacticsHelper.TestDeferredApplyPhase,map_id=CombatLabState.Map.uniqueID,
                tick=Find.TickManager.TicksGame,state=CombatLabState.State(false),
                meaning="Single typed budget-deferral injection for a real HTTP request, not battle evidence"};
        }
    }
    [HarmonyPatch]
    public static class CombatLabHttpAfterOrder
    {
        static MethodBase TargetMethod()=>typeof(CombatOrderHelper).GetMethods(BindingFlags.Public|BindingFlags.Static)
            .Single(m=>m.Name=="Take" && m.GetParameters().Length==2);
        static void Postfix(bool __result)
        {
            if(__result)CombatTacticsHelper.TestApplyBoundary("after_order");
        }
    }
}
#endif

using System;
using System.Linq;
using HarmonyLib;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    // A short, unsaved observer lease scopes this guard to a live autonomous run.
    // Ordinary human play with the API mod alone keeps vanilla permissions.
    public static class AutonomyDrugSafety
    {
        public static DateTime UntilUtc=DateTime.MinValue;
        public static Game Session;
        public static int BlockedDoses,LastBlockedTick,LastPawnId;
        public static string LastDrug;
        public static bool Active => Current.Game!=null && Current.Game==Session && DateTime.UtcNow<UntilUtc;
        public static void Lease(bool enabled)
        {
            if(Session!=Current.Game){BlockedDoses=0;LastBlockedTick=0;LastPawnId=0;LastDrug=null;}
            Session=Current.Game;UntilUtc=enabled ? DateTime.UtcNow.AddSeconds(60) : DateTime.MinValue;
        }
        public static bool Block(bool active, bool player, bool nonMedical, bool required, bool risky) =>
            active && player && nonMedical && !required && risky;
        private static bool Required(Pawn pawn, ThingDef drug)
        {
            var chemical=DrugStatsUtility.GetDrugComp(drug)?.chemical;
            var need=DrugStatsUtility.GetNeed(drug);
            return pawn.health.hediffSet.hediffs.Any(h=>h.Visible && (h is Hediff_Addiction && need!=null && h.def.chemicalNeed==need
                || h is Hediff_ChemicalDependency dependency && chemical!=null && dependency.chemical==chemical));
        }
        public static bool Block(Pawn pawn, ThingDef drug) => pawn!=null && drug!=null && drug.IsDrug &&
            Block(Active,pawn.Faction==Faction.OfPlayer,drug.IsNonMedicalDrug,Required(pawn,drug),DrugCapacitySafety.Risk(pawn,drug));
        public static void Filter(Pawn pawn, ref Job job)
        {
            if(job==null || (job.def!=JobDefOf.Ingest && job.def!=JobDefOf.TakeFromOtherInventory) || !job.targetA.HasThing || !Block(pawn,job.targetA.Thing.def))return;
            BlockedDoses++;LastBlockedTick=Find.TickManager.TicksGame;LastPawnId=pawn.thingIDNumber;LastDrug=job.targetA.Thing.def.defName;
            job=null;
        }
    }
    [HarmonyPatch(typeof(JoyGiver_Ingest),"TryGiveJob")]
    public static class AutonomousJoyDrugGuard
    {
        [HarmonyPostfix] public static void Postfix(Pawn pawn, ref Job __result) => AutonomyDrugSafety.Filter(pawn,ref __result);
    }
    [HarmonyPatch(typeof(JoyGiver_Ingest),"TryGiveJobInGatheringArea")]
    public static class AutonomousGatheringDrugGuard
    {
        [HarmonyPostfix] public static void Postfix(Pawn pawn, ref Job __result) => AutonomyDrugSafety.Filter(pawn,ref __result);
    }
    [HarmonyPatch(typeof(JobGiver_TakeDrugsForDrugPolicy),"TryGiveJob")]
    public static class AutonomousScheduledDrugGuard
    {
        [HarmonyPostfix] public static void Postfix(Pawn pawn, ref Job __result) => AutonomyDrugSafety.Filter(pawn,ref __result);
    }
}

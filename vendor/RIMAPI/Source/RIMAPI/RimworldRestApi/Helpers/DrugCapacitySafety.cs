using System.Linq;
using RimWorld;
using Verse;

namespace RIMAPI.Helpers
{
    public static class DrugCapacitySafety
    {
        public static HediffStage[] Stages(ThingDef drug) => drug.ingestible?.outcomeDoers?
            .OfType<IngestionOutcomeDoer_GiveHediff>().Where(d => d.hediffDef != null)
            .SelectMany(d => d.hediffDef.stages ?? Enumerable.Empty<HediffStage>()).ToArray() ?? new HediffStage[0];
        public static bool Risk(bool downed, bool malnutrition, float consciousness, float moving,
                                float manipulation, bool sedating, bool increasesHunger) =>
            sedating && (downed || malnutrition || consciousness < .8f || moving < .6f || manipulation < .6f)
            || increasesHunger && malnutrition;
        public static bool Risk(Pawn pawn, ThingDef drug)
        {
            var stages=Stages(drug);
            bool sedating=stages.Any(s => s.capMods != null && s.capMods.Any(c => c.offset < 0 || c.postFactor < 1));
            return Risk(pawn.Downed, pawn.health.hediffSet.hediffs.Any(h => h.Visible && h.def.defName=="Malnutrition"),
                pawn.health.capacities.GetLevel(PawnCapacityDefOf.Consciousness), pawn.health.capacities.GetLevel(PawnCapacityDefOf.Moving),
                pawn.health.capacities.GetLevel(PawnCapacityDefOf.Manipulation), sedating, stages.Any(s=>s.hungerRateFactorOffset>0));
        }
        public static object Facts(ThingDef drug) => Stages(drug).SelectMany(s => s.capMods ?? Enumerable.Empty<PawnCapacityModifier>())
            .Select(c => new {capacity=c.capacity.defName,offset=c.offset,factor=c.postFactor}).ToArray();
    }
}

using System.Linq;
using RimWorld;
using Verse;
using RIMAPI.Helpers;

namespace RIMAPI.Controllers
{
    public static class SpecialistNativeSafety
    {
        public static bool Protected(Pawn p) => p == null || p.Dead || p.Downed || p.Drafted || p.InMentalState ||
            CombatNativeHelper.HasCareJob(p) || p.CurJobDef == JobDefOf.Ingest ||
            p.health.hediffSet.hediffs.Any(h => h.Visible && (h.IsCurrentlyLifeThreatening || h.TendableNow() || (h.TryGetComp<HediffComp_Immunizable>() is HediffComp_Immunizable immune && immune.Immunity < 1)));
    }
}

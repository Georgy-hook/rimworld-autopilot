using System.Linq;
using RimWorld;
using Verse;

namespace RIMAPI.Controllers
{
    public static class SpecialistNativeSafety
    {
        public static bool Protected(Pawn p) => p == null || p.Dead || p.Downed || p.Drafted || p.InMentalState ||
            new[] { "Deathrest", "Breastfeed", "Lessongiving", "BottleFeedBaby", "BreastfeedCarryToMom", "BringBabyToSafetyUnforced", "CarryToMomAfterBirth", "BabySuckle", "BabyPlay", "PlayStatic", "PlayWalking", "PlayToys", "Lessonreceiving", "PrisonerInterrogateIdentity", "Ingest" }.Contains(p.CurJobDef?.defName) ||
            p.CurJobDef == JobDefOf.TendPatient || p.CurJobDef == JobDefOf.Rescue || p.CurJobDef == JobDefOf.FeedPatient || p.CurJobDef == JobDefOf.DoBill ||
            p.health.hediffSet.hediffs.Any(h => h.IsCurrentlyLifeThreatening || (h.TryGetComp<HediffComp_Immunizable>() is HediffComp_Immunizable immune && immune.Immunity < 1));
    }
}

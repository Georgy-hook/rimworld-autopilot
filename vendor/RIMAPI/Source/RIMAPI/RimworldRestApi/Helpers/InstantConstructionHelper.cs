using System;
using RimWorld;
using Verse;

namespace RIMAPI.Helpers
{
    public static class InstantConstructionHelper
    {
        // Same rule as Designator_Build, without its developer god-mode branch.
        // Loaded stats include XML inheritance and material-specific modifiers.
        public static bool IsInstantBuilding(ThingDef def, ThingDef stuff = null)
        {
            return def != null && def.category == ThingCategory.Building
                && def.GetStatValueAbstract(StatDefOf.WorkToBuild, stuff) == 0f;
        }

        public static float Progress(float workDone, float workRequired)
        {
            if (workRequired <= 0f || float.IsNaN(workRequired) || float.IsInfinity(workRequired)
                || float.IsNaN(workDone) || float.IsInfinity(workDone)) return 0f;
            return Math.Max(0f, Math.Min(1f, workDone / workRequired));
        }
    }
}

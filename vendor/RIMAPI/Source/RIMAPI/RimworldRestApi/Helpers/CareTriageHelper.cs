using System;
using System.Linq;
using System.Reflection;
using RimWorld;
using Verse;
using Verse.AI;
namespace RIMAPI.Helpers
{
    // Comparisons concern ordinary care jobs only. They never end a job themselves.
    public static class CareTriageHelper
    {
        private static readonly PropertyInfo StarvationRate = typeof(Need_Food).GetProperty("MalnutritionSeverityPerInterval", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly PropertyInfo Frozen = typeof(Need_Food).GetProperty("IsFrozen", BindingFlags.Instance | BindingFlags.NonPublic);
        public static Hediff Malnutrition(Pawn p) => p?.health?.hediffSet.hediffs.FirstOrDefault(h => h.Visible && h.def == HediffDefOf.Malnutrition);
        public static float? StarvationTicks(Pawn p)
        {
            Hediff h = Malnutrition(p);
            Need_Food food = p?.needs?.food;
            if (h == null || h.def.lethalSeverity <= 0 || food == null || !food.Starving || StarvationRate == null || Frozen == null) return null;
            try
            {
                if ((bool)Frozen.GetValue(food, null) && !p.Deathresting) return null;
                float rate = (float)StarvationRate.GetValue(food, null);
                return rate > 0 && !float.IsNaN(rate) && !float.IsInfinity(rate)
                    ? Math.Max(0f, h.def.lethalSeverity - h.Severity) * 150f / rate : (float?)null;
            }
            catch (Exception) { return null; } // Missing/modded native getter means unknown, never a zero ETA.
        }
        public static float? BleedoutTicks(Pawn p)
        {
            if (p?.health == null) return null;
            float rate = p.health.hediffSet.BleedRateTotal;
            // Installed HediffGiver_Bleeding heals BloodLoss below .1; no finite bleedout at that rate.
            if (rate < .1f) return float.PositiveInfinity;
            Hediff blood = p.health.hediffSet.GetFirstHediffOfDef(HediffDefOf.BloodLoss);
            // In a complete native hediff set absence of BloodLoss is known zero.
            return Math.Max(0f, 1f - (blood?.Severity ?? 0f)) * 60000f / rate;
        }
        public static bool DiseaseCareProtected(Pawn p) => p.health.hediffSet.hediffs.Any(h => h.Visible
            && h.def != HediffDefOf.BloodLoss && h.def != HediffDefOf.Malnutrition
            && (PawnHelper.CanDevelopImmunity(h) && h.TryGetComp<HediffComp_Immunizable>().Immunity < 1f
                || h.IsCurrentlyLifeThreatening || h.TendableNow() && (h.def.lethalSeverity > 0f || h.def.defName.IndexOf("infection", StringComparison.OrdinalIgnoreCase) >= 0)));
        public static bool CanYield(Pawn worker, Pawn next, string kind, string expectedJob, int? expectedPatient, out string reason)
        {
            reason = null;
            if ((kind != "feed" && kind != "rescue") || worker == null || next == null || worker == next
                || !worker.IsColonistPlayerControlled || !worker.Spawned || worker.Dead || worker.Downed || worker.Drafted || worker.InMentalState
                || (worker.CurJob?.def.forceCompleteBeforeNextJob ?? false) || !worker.jobs.IsCurrentJobPlayerInterruptible()
                || !next.IsColonistPlayerControlled || !next.Spawned || next.Dead || next.Map != worker.Map || worker.carryTracker?.CarriedThing != null
                || QueuedCare(worker) || expectedJob == null || !expectedPatient.HasValue || worker.CurJobDef?.defName != expectedJob) return false;
            Job job = worker.CurJob;
            if (job == null || (job.def != JobDefOf.TendPatient && job.def != JobDefOf.Rescue)
                || !(job.targetA.Thing is Pawn old) || old.thingIDNumber != expectedPatient.Value || old.Dead || !old.Spawned || old.Map != worker.Map
                || DiseaseCareProtected(old) || DiseaseCareProtected(worker)) return false;
            Hediff mal = Malnutrition(next);
            float? urgent = StarvationTicks(next), oldStarvation = StarvationTicks(old), bleed = BleedoutTicks(old);
            if (mal == null || next.needs?.food == null || !next.needs.food.Starving || !(mal.IsCurrentlyLifeThreatening || mal.Severity >= .75f)
                || !urgent.HasValue || !bleed.HasValue || bleed.Value <= urgent.Value * 2f + 600f) return false;
            if (job.def == JobDefOf.TendPatient && old.health.hediffSet.BleedRateTotal > 0f) return false;
            if (old != next && oldStarvation.HasValue && oldStarvation.Value <= urgent.Value + 600f) return false;
            if (old == next && kind != "feed") return false;
            reason = old == next ? "stable_tend_to_feed_same_starving_patient" : "starvation_precedes_current_patient_known_deadline";
            return true;
        }
        private static bool RouteSafe(Pawn actor, IntVec3 from, Thing target, PathEndMode end)
        {
            Map map=actor.Map;
            if (target == null || !target.Spawned || target.Map != map || target.IsForbidden(actor) || target.Position.Fogged(map)) return false;
            using (var path=map.pathFinder.FindPathNow(from,target.Position,actor,null,end))
            {
                if (!path.Found) return false;
                // Only observed threats. Both approach and food/carry leg are checked on the native path.
                var enemies=map.mapPawns.AllPawnsSpawned.Where(p=>!p.Dead && !p.Downed && p.HostileTo(actor) && !p.Position.Fogged(map)).ToArray();
                var turrets=map.listerBuildings.allBuildingsNonColonist.Where(b=>CombatNativeHelper.ActiveStructure(b) && !b.Position.Fogged(map)).ToArray();
                foreach (IntVec3 c in path.NodesReversed)
                    if (c.Fogged(map) || c.ContainsStaticFire(map)
                        || enemies.Any(p=>c.InHorDistOf(p.Position,Math.Max(12f,(p.equipment?.Primary?.def.Verbs?.FirstOrDefault()?.range ?? 0f)+3f)))
                        || turrets.Any(b=>c.InHorDistOf(b.Position,Math.Max(12f,(b as Building_Turret)?.AttackVerb?.EffectiveRange ?? 0f)+3f))) return false;
            }
            return true;
        }
        public static bool JobRouteSafe(Pawn actor, Job job)
        {
            Thing first=job.targetA.Thing, second=job.targetB.Thing;
            if (first == null || second == null) return false;
            // Inventory food is already with the feeder; a ground source must be reachable.
            IntVec3 from=actor.Position;
            if (first.Spawned)
            { if (!RouteSafe(actor,from,first,PathEndMode.Touch)) return false; from=first.Position; }
            else if (job.def != JobDefOf.FeedPatient || first.ParentHolder != actor.inventory) return false;
            return RouteSafe(actor,from,second,job.def == JobDefOf.Rescue ? PathEndMode.OnCell : PathEndMode.Touch);
        }
        public static bool Care(Job j) => j != null && (j.def == JobDefOf.FeedPatient || j.def == JobDefOf.Rescue || j.def == JobDefOf.TendPatient);
        public static bool QueuedCare(Pawn p) => p.jobs.jobQueue.Any(q=>Care(q.job));
        public static bool QueuedFor(Map map, Pawn patient, string kind) => map.mapPawns.AllPawnsSpawned.Any(p=>p.jobs.jobQueue.Any(q=>
            q.job != null && (kind == "feed" ? q.job.def == JobDefOf.FeedPatient && q.job.targetB.Thing == patient
                : kind == "rescue" ? q.job.def == JobDefOf.Rescue && q.job.targetA.Thing == patient
                : kind == "tend" && q.job.def == JobDefOf.TendPatient && q.job.targetA.Thing == patient)));
        public static bool Matches(Pawn worker, Job job, Pawn patient) => worker.CurJobDef == job.def
            && worker.CurJob?.targetA.Thing == job.targetA.Thing && worker.CurJob?.targetB.Thing == job.targetB.Thing
            && (job.def == JobDefOf.FeedPatient ? worker.CurJob?.targetB.Thing == patient : worker.CurJob?.targetA.Thing == patient);
    }
}

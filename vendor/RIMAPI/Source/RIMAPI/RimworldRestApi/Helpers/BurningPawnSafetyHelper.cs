using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;
using RIMAPI.Core;
using RIMAPI.Models;

namespace RIMAPI.Helpers
{
    // An attached pawn fire is different from a ground fire near a building.
    public static class BurningPawnSafetyHelper
    {
        public static Fire AttachedFire(Pawn p) => p?.TryGetComp<CompAttachBase>()?.GetAttachment(ThingDefOf.Fire) as Fire;
        public static bool PlayerPatient(Pawn p) => p != null && p.Spawned && !p.Dead
            && (p.IsColonistPlayerControlled || p.Faction == Faction.OfPlayer && p.RaceProps.Animal);
        public static bool ProtectsPatient(Job job) => job?.def == JobDefOf.BeatFire
            && job.targetA.Thing is Fire fire && fire.parent is Pawn p && PlayerPatient(p)
            && AttachedFire(p) == fire && !fire.Destroyed;
        public static bool ObservedThreat(Map map) => map.mapPawns.AllPawnsSpawned.Any(p => !p.Dead && !p.Downed
            && !p.Position.Fogged(map) && CombatNativeHelper.IsPlayerThreat(p))
            || map.listerBuildings.allBuildingsNonColonist.Any(b => !b.Position.Fogged(map) && CombatNativeHelper.ActiveStructure(b));
        public static List<object> Facts(Map map) => map.mapPawns.AllPawnsSpawned.Where(PlayerPatient)
            .Where(p => AttachedFire(p) is Fire f && !f.Destroyed).Select(p => (object)new {
                pawn_id=p.thingIDNumber, name=p.LabelShort, downed=p.Downed, fire_id=AttachedFire(p).thingIDNumber,
                fire_size=AttachedFire(p).fireSize, health=p.health.summaryHealth.SummaryHealthPercent,
                x=p.Position.x,z=p.Position.z, in_bed=p.InBed(), current_job=p.CurJobDef?.defName }).ToList();
        private static bool Free(Pawn worker) => worker != null && worker.IsColonistPlayerControlled && worker.Spawned
            && !worker.Dead && !worker.Downed && !worker.Drafted && !worker.InMentalState && !worker.IsBurning()
            && worker.workSettings != null && !CombatNativeHelper.HasCareJob(worker) && !CareTriageHelper.QueuedCare(worker)
            && worker.carryTracker?.CarriedThing == null && worker.CurJobDef != JobDefOf.Ingest
            && worker.jobs.jobQueue.Count == 0 && !(worker.CurJob?.playerForced ?? false)
            && worker.jobs.IsCurrentJobPlayerInterruptible()
            && !(worker.CurJob?.def.forceCompleteBeforeNextJob ?? false);
        private static Job Job(Pawn worker,Pawn patient,Fire fire)
        {
            if (!Free(worker) || !PlayerPatient(patient) || worker == patient || patient.Map != worker.Map
                || fire == null || fire.Destroyed || fire.parent != patient || AttachedFire(patient) != fire
                || ObservedThreat(worker.Map) || !ResilienceAutomationHelper.RoutineRouteSafe(worker,patient)) return null;
            if (worker.Map.mapPawns.AllPawnsSpawned.Any(p => p != worker && p.CurJobDef == JobDefOf.BeatFire
                    && p.CurJob?.targetA.Thing == fire)) return null;
            foreach (WorkGiverDef giver in DefDatabase<WorkGiverDef>.AllDefsListForReading
                .Where(g => g.workType?.defName == "Firefighter"))
            {
                if (worker.WorkTypeIsDisabled(giver.workType) || giver.requiredCapacities != null
                    && giver.requiredCapacities.Any(c => !worker.health.capacities.CapableOf(c))
                    || !(giver.Worker is WorkGiver_Scanner scanner)) continue;
                foreach(Thing scanned in new Thing[]{fire,patient})
                {
                    if(!scanner.HasJobOnThing(worker,scanned,true))continue;
                    Job job=scanner.JobOnThing(worker,scanned,true);
                    if (job?.def == JobDefOf.BeatFire && job.targetA.Thing == fire) return job;
                }
            }
            return null;
        }
        public static void AddOptions(Map map,ResilienceContextDto result)
        {
            if (ObservedThreat(map)) return;
            foreach (Pawn patient in map.mapPawns.AllPawnsSpawned.Where(PlayerPatient))
            {
                Fire fire=AttachedFire(patient); if (fire == null || fire.Destroyed) continue;
                foreach (Pawn worker in map.mapPawns.FreeColonistsSpawned.Where(Free)
                    .OrderBy(p => p.Position.DistanceToSquared(patient.Position)).Take(8))
                {
                    if (Job(worker,patient,fire) == null) continue;
                    result.Options.Add(new ResilienceOptionDto {Kind="extinguish",WorkerId=worker.thingIDNumber,
                        TargetId=patient.thingIDNumber,Giver=fire.thingIDNumber.ToString(),Worker=worker.LabelShort,
                        Target=patient.LabelShort,TravelDistance=worker.Position.DistanceTo(patient.Position)});
                    if (result.Options.Count(o => o.Kind == "extinguish") >= 16) return;
                }
            }
        }
        public static ApiResult<CapabilityOrderResultDto> Execute(ResilienceOrderRequestDto request,Pawn worker,Pawn patient)
        {
            var result=new CapabilityOrderResultDto {TargetId=request.TargetId};
            Fire fire=AttachedFire(patient);
            if (!int.TryParse(request.Giver,out int expected) || fire == null || fire.thingIDNumber != expected)
            {result.Reason="attached_pawn_fire_changed_or_extinguished";return ApiResult<CapabilityOrderResultDto>.Ok(result);}
            Job job=Job(worker,patient,fire);
            if (job == null)
            {result.Reason="no_free_native_firefighter_or_safe_route";return ApiResult<CapabilityOrderResultDto>.Ok(result);}
            job.playerForced=true;
            bool accepted=worker.jobs.TryTakeOrderedJob(job);
            result.Applied=accepted && worker.CurJob == job && worker.CurJobDef == JobDefOf.BeatFire && worker.CurJob.targetA.Thing == fire;
            if (!result.Applied) worker.jobs.jobQueue.RemoveAll(worker,j => j == job);
            result.Reason=result.Applied ? "exact_pawn_fire_job_observed; extinguishing_unverified" : "fire_job_not_current";
            return ApiResult<CapabilityOrderResultDto>.Ok(result);
        }
    }
}

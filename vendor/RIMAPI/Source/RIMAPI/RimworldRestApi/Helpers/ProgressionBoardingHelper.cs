using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class ProgressionBoardingHelper
    {
        public static List<ProgressionBoardingDto> Options(Building root)
        {
            var result = new List<ProgressionBoardingDto>();
            if (root == null || !root.Spawned || ShipCountdown.CountingDown) return result;
            var map = root.Map;
            var parts = ShipUtility.ShipBuildingsAttachedTo(root).ToList();
            if (!ShipUtility.RequiredParts().All(p => parts.Count(b => b.def == p.Key) >= p.Value)) return result;
            // Keep pawns available while the reactor's defense cycle is underway.
            bool ready = parts.Select(b => b.TryGetComp<CompHibernatable>()).Where(c => c != null).All(c => c.Running);
            if (map.mapPawns.AllPawnsSpawned.Any(p => !p.Dead && p.HostileTo(Faction.OfPlayer))) return result;
            var colonists = map.mapPawns.FreeColonistsSpawned.Where(p => !p.Dead && !p.IsQuestLodger()).ToList();
            var workers = colonists.Where(p => !p.Downed && !p.InMentalState && !p.Drafted && p.jobs != null).ToList();
            foreach (var casket in parts.OfType<Building_CryptosleepCasket>().Where(c => !c.HasAnyContents && c.def.building.isPlayerEjectable))
            foreach (var passenger in colonists.Where(p => !p.InMentalState && !p.Drafted))
            {
                if (!casket.Accepts(passenger)) continue;
                if (!passenger.Downed && !ready) continue;
                foreach (var worker in passenger.Downed ? workers : workers.Where(p => p == passenger))
                {
                    if (worker.CurJobDef == JobDefOf.EnterCryptosleepCasket || worker.CurJobDef == JobDefOf.CarryToCryptosleepCasket) continue;
                    // A boarding order must not interrupt a caregiver's active emergency job.
                    if (worker.CurJobDef != null && new[] { "TendPatient", "Rescue", "FeedPatient", "DoBill" }.Contains(worker.CurJobDef.defName)) continue;
                    if (!worker.CanReserveAndReach(casket, PathEndMode.InteractionCell, Danger.Some) || casket.IsForbidden(worker)) continue;
                    if (passenger.Downed && (!worker.CanReserveAndReach(passenger, PathEndMode.OnCell, Danger.Some) || passenger.IsForbidden(worker) || worker.WorkTagIsDisabled(WorkTags.ManualDumb))) continue;
                    result.Add(new ProgressionBoardingDto {
                        MapId = map.uniqueID, RootId = root.thingIDNumber, PawnId = passenger.thingIDNumber,
                        WorkerId = worker.thingIDNumber, CasketId = casket.thingIDNumber,
                        Pawn = passenger.LabelShortCap.ToString(), Worker = worker.LabelShortCap.ToString(),
                        Job = passenger.Downed ? "CarryToCryptosleepCasket" : "EnterCryptosleepCasket",
                        ReactorRunning = ready, PawnDowned = passenger.Downed,
                        PawnHealthFraction = passenger.health.summaryHealth.SummaryHealthPercent,
                        WorkerHealthFraction = worker.health.summaryHealth.SummaryHealthPercent,
                        PawnWeapon = passenger.equipment?.Primary?.def.defName,
                        CurrentJob = worker.CurJobDef?.defName,
                        PawnMedicineSkill = passenger.skills?.GetSkill(SkillDefOf.Medicine)?.Level ?? 0,
                        RemainingMobileCombatColonists = workers.Count(p => p != passenger && !p.WorkTagIsDisabled(WorkTags.Violent)),
                        RemainingArmedMobileCombatColonists = workers.Count(p => p != passenger && !p.WorkTagIsDisabled(WorkTags.Violent) && p.equipment?.Primary != null),
                        RemainingMobileDoctors = workers.Count(p => p != passenger && !p.WorkTypeIsDisabled(WorkTypeDefOf.Doctor)),
                        PsychicBondWarning = ModsConfig.BiotechActive && passenger.health.hediffSet.HasHediff(HediffDefOf.PsychicBond)
                    });
                }
            }
            return result;
        }

        public static bool Order(Building root, int pawnId, int workerId, int casketId)
        {
            var option = Options(root).FirstOrDefault(o => o.PawnId == pawnId && o.WorkerId == workerId && o.CasketId == casketId);
            if (option == null) return false;
            var pawn = root.Map.mapPawns.FreeColonistsSpawned.First(p => p.thingIDNumber == pawnId);
            var worker = root.Map.mapPawns.FreeColonistsSpawned.First(p => p.thingIDNumber == workerId);
            var casket = ShipUtility.ShipBuildingsAttachedTo(root).OfType<Building_CryptosleepCasket>().First(c => c.thingIDNumber == casketId);
            var job = pawn.Downed ? JobMaker.MakeJob(JobDefOf.CarryToCryptosleepCasket, pawn, casket) : JobMaker.MakeJob(JobDefOf.EnterCryptosleepCasket, casket);
            // Ordinary ordered jobs perform reservations, travel, carrying and the 500-tick wait.
            return worker.jobs.TryTakeOrderedJob(job, JobTag.Misc) && worker.CurJob == job;
        }
    }

    public class ProgressionBoardingDto
    {
        public int MapId { get; set; }
        public int RootId { get; set; }
        public int PawnId { get; set; }
        public int WorkerId { get; set; }
        public int CasketId { get; set; }
        public string Pawn { get; set; }
        public string Worker { get; set; }
        public string Job { get; set; }
        public string CurrentJob { get; set; }
        public bool ReactorRunning { get; set; }
        public bool PawnDowned { get; set; }
        public float PawnHealthFraction { get; set; }
        public float WorkerHealthFraction { get; set; }
        public string PawnWeapon { get; set; }
        public int PawnMedicineSkill { get; set; }
        public int RemainingMobileCombatColonists { get; set; }
        public int RemainingArmedMobileCombatColonists { get; set; }
        public int RemainingMobileDoctors { get; set; }
        public bool PsychicBondWarning { get; set; }
    }
}

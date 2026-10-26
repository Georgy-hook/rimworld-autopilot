using System;
using System.Collections.Generic;
using System.Linq;
using RIMAPI.Models;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    // A new first-care intent while a selected defender is still drafted.
    // Existing clinical jobs and later queued instructions never qualify.
    public static class CombatMedicalTransitionHelper
    {
        public static bool ThreatsClear(Map map)
            => map!=null && !map.mapPawns.AllPawnsSpawned.Any(p=>!p.Dead && !p.Downed
                    && CombatNativeHelper.IsPlayerThreat(p))
                && !map.listerBuildings.allBuildingsNonColonist.Any(CombatNativeHelper.ActiveStructure);

        private static bool SelectedDoctor(Pawn doctor,int jobId,bool self=false)
        {
            if(doctor==null || !doctor.IsColonistPlayerControlled || !doctor.Spawned || doctor.Dead
                || doctor.Downed || doctor.InMentalState || !doctor.Drafted || doctor.CurJob?.loadID!=jobId
                || doctor.jobs.jobQueue.Any() || doctor.carryTracker?.CarriedThing!=null
                || CombatNativeHelper.HasCareJob(doctor) || CombatNativeHelper.HasCareRetreat(doctor)
                || CareTriageHelper.QueuedCare(doctor) || doctor.WorkTypeIsDisabled(WorkTypeDefOf.Doctor)
                || (doctor.skills?.GetSkill(SkillDefOf.Medicine)?.TotallyDisabled ?? true)
                || !doctor.health.capacities.CapableOf(PawnCapacityDefOf.Manipulation)
                || !doctor.health.capacities.CapableOf(PawnCapacityDefOf.Moving)
                || !self && doctor.health.hediffSet.BleedRateTotal>=1.5f
                || doctor.stances.curStance is Stance_Warmup
                || CombatControlHelper.CurrentPlan(doctor)==null)return false;
            var verb=doctor.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(verb?.state==VerbState.Bursting)return false;
            return doctor.CurJobDef==JobDefOf.AttackStatic && CombatOrderHelper.Owned(doctor,doctor.CurJob)
                || doctor.CurJobDef==JobDefOf.Wait_Combat
                    && (!doctor.CurJob.playerForced || CombatOrderHelper.Owned(doctor,doctor.CurJob))
                || doctor.CurJobDef==JobDefOf.Goto && CombatOrderHelper.Owned(doctor,doctor.CurJob)
                    && doctor.Position==doctor.CurJob.targetA.Cell && !doctor.pather.Moving;
        }

        public static bool Ready(Pawn doctor,Pawn patient,int jobId,out float travel)
        {
            travel=0f;
            if(patient==null || !SelectedDoctor(doctor,jobId,patient==doctor) || !patient.Spawned
                || patient.Map!=doctor.Map || !patient.IsColonistPlayerControlled || patient.Dead
                || patient.health.hediffSet.BleedRateTotal<.1f
                || !patient.health.hediffSet.hediffs.Any(h=>h.Visible && h.TendableNow())
                || CombatNativeHelper.HasClinicalCareJob(patient) || CombatNativeHelper.HasCareRetreat(patient)
                || CareTriageHelper.QueuedCare(patient) || patient.carryTracker?.CarriedThing!=null
                || !ThreatsClear(doctor.Map) || patient.IsForbidden(doctor)
                || !doctor.CanReserveAndReach(patient,PathEndMode.Touch,Danger.Some)
                || !ResilienceAutomationHelper.RoutineRouteSafe(doctor,patient))return false;
            if(doctor.Map.mapPawns.AllPawnsSpawned.Any(p=>p!=doctor
                && (p.CurJobDef==JobDefOf.TendPatient || p.CurJobDef==JobDefOf.Rescue)
                && p.CurJob.targetA.Thing==patient))return false;
            Map map=doctor.Map;
            using(var path=CombatPathBudgetHelper.Query(doctor,doctor.Position,patient.Position,PathEndMode.Touch))
            {
                if(!path.Found || float.IsInfinity(path.TotalCost) || float.IsNaN(path.TotalCost)
                    || path.TotalCost<0f)return false;
                // GET and POST check the same complete native approach.
                if(path.NodesReversed.Any(c=>c.Fogged(map) || c.ContainsStaticFire(map)
                    || map.gasGrid.DensityAt(c,GasType.ToxGas)>0
                    || map.gasGrid.DensityAt(c,GasType.DeadlifeDust)>0
                    || map.gasGrid.DensityAt(c,GasType.RotStink)>0))return false;
                travel=path.TotalCost;
            }
            return true;
        }

        public static List<CombatReleaseTendOptionDto> Options(Map map)
        {
            var result=new List<CombatReleaseTendOptionDto>();
            if(!ThreatsClear(map))return result;
            var patients=map.mapPawns.FreeColonistsSpawned.Where(p=>p.Downed && !p.Dead
                    && p.health.hediffSet.BleedRateTotal>=1.5f)
                .OrderBy(p=>CareTriageHelper.BleedoutTicks(p) ?? float.PositiveInfinity).Take(5).ToArray();
            foreach(var doctor in map.mapPawns.FreeColonistsSpawned.Where(p=>p.CurJob!=null
                    && SelectedDoctor(p,p.CurJob.loadID)).Take(8))
                foreach(var patient in patients)
                {
                CombatPathBudgetHelper.Checkpoint();
                    if(!Ready(doctor,patient,doctor.CurJob.loadID,out var travel))continue;
                    result.Add(new CombatReleaseTendOptionDto{DoctorId=doctor.thingIDNumber,
                            PatientId=patient.thingIDNumber,ReleaseCombatJobId=doctor.CurJob.loadID,
                            ExpectedCurrentJob=doctor.CurJobDef.defName,TravelTicks=travel,
                            LockedTicks=CombatInterceptHelper.MovementLockTicks(doctor),
                            MedicalTendSpeed=doctor.GetStatValue(StatDefOf.MedicalTendSpeed),
                            MedicalTendQuality=doctor.GetStatValue(StatDefOf.MedicalTendQuality),
                            BleedoutTicks=CareTriageHelper.BleedoutTicks(patient),
                            Doctor=doctor.LabelShort,Patient=patient.LabelShort});
                }
            return result;
        }
    }
}

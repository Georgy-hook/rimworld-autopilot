using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;

namespace RIMAPI.Helpers
{
    public static class CombatDoctorTransitMath
    {
        private static bool Known(float n)=>n>=0 && !float.IsNaN(n) && !float.IsInfinity(n);
        // Cover at the destination cannot pay for a worse crossfire prefix.
        public static bool Prefix(float exposure,float holding,float total,float holdingTotal,float elapsed)
            =>Known(exposure) && Known(holding) && Known(total) && Known(holdingTotal) && Known(elapsed)
                && exposure<=holding+.1f && total<=holdingTotal+elapsed*.1f;
        public static bool TimelyReduction(float initial,float firstReduction,float movementLock)
            =>Known(initial) && Known(movementLock)
                && (initial<.6f || Known(firstReduction) && firstReduction<=movementLock+90f);
        public static bool StagedEndpoint(float initial,float endpoint,float distance)
            =>Known(initial) && Known(endpoint) && Known(distance) && distance>0 && distance<=4f
                && endpoint<=initial-.2f;
        public static bool Accept(bool prefixSafe,bool earlyReduction,bool protectedArrival)
            =>prefixSafe && (earlyReduction || protectedArrival);
    }
    public static partial class CombatControlHelper
    {
        private static bool ClinicalRangedTransit(Pawn p)
            =>p.Map.mapPawns.AllPawnsSpawned.Any(e=>Threat(e) && e.equipment?.Primary?.def.IsRangedWeapon==true)
                && (IsReservedDoctor(p) || MedicalFunctionWarning(p));
        private static bool DoctorStagedCell(Pawn p,IntVec3 cell,float before,float after,List<Pawn> threats)
            =>CombatDoctorTransitMath.StagedEndpoint(before,after,cell.DistanceTo(p.Position))
                && threats.Any(e=>FocusedRangedThreat(e,p) && CombatExposureHelper.Lane(e,p,cell,e.Position)<=.1f);

        // An actual aimed enemy, not an arbitrary group target. Preserve an
        // existing mover's cover lease and the gun's personal contact defence.
        // Warmups/bursts and clinical/manual queues remain with their owners.
        private static Pawn DoctorCoverTarget(Pawn gun,List<Pawn> threats)
        {
            if(!threats.Any(e=>e.equipment?.Primary?.def.IsRangedWeapon==true))return null;
            var doctor=ReservedDoctor(gun.Map);
            if(doctor==null || doctor==gun || TeamImmediateDanger(gun)
                || CriticalRangedInjury(gun) || MedicalFunctionWarning(gun))return null;
            return threats.Where(e=>FocusedRangedThreat(e,doctor)
                    && CohortGunFreeFor(gun,doctor,e) && CombatInterceptHelper.CanShootNow(gun,e))
                .OrderBy(NextRangedBurst).ThenBy(e=>e.thingIDNumber).FirstOrDefault();
        }
        private static void ObserveDoctorCover(Pawn gun,Pawn enemy,List<Pawn> threats)
        {
            if(!threats.Any(e=>e.equipment?.Primary?.def.IsRangedWeapon==true))return;
            var doctor=ReservedDoctor(gun.Map);
            if(doctor==null || doctor==gun || !FocusedRangedThreat(enemy,doctor)
                || !CohortGunFreeFor(gun,doctor,enemy) || !TeamCoverReady(gun,enemy,threats))return;
            if(AimTarget(gun)!=enemy && gun.CurJob?.targetA.Thing!=enemy)return;
            bool newlyBound=!CoverTransfers.TryGetValue(gun,out var old) || old.Mover!=doctor || old.Enemy!=enemy;
            CoverTransfers[gun]=new CoverTransfer{Mover=doctor,Enemy=enemy,Until=Find.TickManager.TicksGame+600};
            if(newlyBound)TeamEvent("observed_same_enemy_physician_cover",gun,enemy,doctor);
        }
    }
}

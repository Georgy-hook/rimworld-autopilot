using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class CombatDoctorBoundMath
    {
        private static bool Known(float n)=>n>=0 && !float.IsNaN(n) && !float.IsInfinity(n);
        public static float Window(int started,int now,float travel,float cycle)
        {
            if(now<started || now-started>900 || !Known(travel) || !Known(cycle))return float.PositiveInfinity;
            float horizon=Math.Max(Math.Max(0,600-(now-started)),travel+cycle);
            return horizon<=600 && now-started+horizon<=900?horizon:float.PositiveInfinity;
        }
        public static bool Keep(bool exact,bool foreign,bool clinical,bool immediate,int age)
            =>exact && !foreign && !clinical && !immediate && age>=0 && age<=900;
    }
    public static partial class CombatControlHelper
    {
        private sealed class DoctorBound
        {public CombatJobStamp Move;public Map Map;public IntVec3 Goal;public int Started,Reviewed;}
        private static readonly Dictionary<Pawn,DoctorBound> DoctorBounds=new Dictionary<Pawn,DoctorBound>();
        private static void RememberDoctorBound(Pawn p,Job move,IntVec3 goal)
            =>DoctorBounds[p]=new DoctorBound{Move=new CombatJobStamp(move),Map=p.Map,Goal=goal,
                Started=Find.TickManager.TicksGame,Reviewed=Find.TickManager.TicksGame};
        private static bool DoctorBoundEligible(Pawn p,DoctorBound b)
            =>p.Spawned && !p.Dead && p.Map!=null && p.Map==b.Map && NativeDoctor(p)
                && Plans.TryGetValue(p.thingIDNumber,out var plan) && Valid(plan)
                && Find.TickManager.TicksGame>=b.Started && Find.TickManager.TicksGame-b.Started<=900
                && !p.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(p,q.job))
                && p.Map.mapPawns.AllPawnsSpawned.Any(t=>Threat(t) && t.equipment?.Primary?.def.IsRangedWeapon==true)
                && !p.Map.mapPawns.AllPawnsSpawned.Any(t=>Threat(t) && CombatNativeHelper.AbductionThreat(t));
        private static bool DoctorBoundInTransit(Plan plan)
            =>DoctorBounds.TryGetValue(plan.Pawn,out var b) && DoctorBoundEligible(plan.Pawn,b)
                && plan.Pawn.CurJob==b.Move.Value && plan.OwnedJob==b.Move.Value
                && plan.Pawn.CurJobDef==JobDefOf.Goto && plan.Pawn.CurJob.targetA.Cell==b.Goal;
        private static void PruneDoctorBounds()
        {
            foreach(var pair in DoctorBounds.ToArray())
            {
                var p=pair.Key;var b=pair.Value;
                bool arrival=p.Spawned && p.Position==b.Goal
                    && (CombatOrderHelper.Owned(p,p.CurJob) || p.CurJobDef==JobDefOf.Wait_Combat && !p.CurJob.playerForced);
                bool pending=p.Spawned && b.Move.Value!=null && p.jobs.jobQueue.Any(q=>q.job==b.Move.Value);
                if(!DoctorBoundEligible(p,b) || !arrival && !pending
                    && (!Plans.TryGetValue(p.thingIDNumber,out var plan) || !DoctorBoundInTransit(plan)))DoctorBounds.Remove(p);
            }
        }
        private static float DoctorBoundRemainingTicks(Pawn p,CombatPathBudgetHelper.Observation path)
        {
            if(!path.Found)return float.PositiveInfinity;
            var cells=RemainingRangedCells(p,path).ToArray();
            if(cells.Length==0 || cells.Length>40)return float.PositiveInfinity;
            // A borrowed native path's TotalCost describes the original search,
            // not its current cursor. Measure only the remaining loaded steps.
            float ticks=p.stances.curStance is Stance_Warmup?0:CombatInterceptHelper.MovementLockTicks(p);
            var previous=p.Position;
            foreach(var cell in cells)
            {
                CombatPathBudgetHelper.Checkpoint("doctor_bound_remaining_time");
                float step=previous==p.Position && p.pather?.Moving==true && cell==p.pather.nextCell
                    ?Math.Max(1f,p.pather.nextCellCostLeft):CombatInterceptHelper.PlannedJogStepTicks(p,previous,cell);
                if(!(step>=0) || float.IsInfinity(step))return float.PositiveInfinity;
                ticks+=step;previous=cell;
            }
            return ticks;
        }
        private static bool KeepDoctorBoundRoute(Plan plan,CombatPathBudgetHelper.Observation path)
        {
            var p=plan.Pawn;if(!DoctorBoundInTransit(plan))return false;
            var b=DoctorBounds[p];
            float horizon=CombatDoctorBoundMath.Window(b.Started,Find.TickManager.TicksGame,
                DoctorBoundRemainingTicks(p,path),TeamCycle(p));
            if(float.IsInfinity(horizon) || !path.Found || !CombatInterceptHelper.MovementSafe(p,path))return false;
            bool safe=SaferRangedRoute(p,path,true,out _,null,horizon,true,true);
            if(safe)b.Reviewed=Find.TickManager.TicksGame;
            TeamEvent(safe?"doctor_bound_remaining_route_kept":"doctor_bound_remaining_route_unsafe",p,plan.Target);
            return safe;
        }
        private static bool KeepDoctorBoundIntent(Pawn p)
        {
            if(!Plans.TryGetValue(p.thingIDNumber,out var plan) || !DoctorBoundInTransit(plan))return false;
            var b=DoctorBounds[p];
            if(!CombatDoctorBoundMath.Keep(true,p.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(p,q.job)),
                CombatNativeHelper.Protected(p) || CareTriageHelper.QueuedCare(p),TeamImmediateDanger(p),Find.TickManager.TicksGame-b.Started))return false;
            if(Find.TickManager.TicksGame-b.Reviewed<=60)return true;
            using(var path=CombatPathBudgetHelper.Borrowed(p.pather.curPath))return KeepDoctorBoundRoute(plan,path);
        }
        private static bool TryDoctorBoundAnchor(Pawn doctor,out IntVec3 goal)
        {
            goal=IntVec3.Invalid;
            if(!DoctorBounds.TryGetValue(doctor,out var b) || !DoctorBoundEligible(doctor,b))return false;
            bool reached=doctor.Position==b.Goal;
            if(!reached && !KeepDoctorBoundIntent(doctor))return false;
            if(b.Goal.ContainsStaticFire(doctor.Map) || doctor.Map.gasGrid.DensityAt(b.Goal,GasType.ToxGas)>0
                || doctor.Map.gasGrid.DensityAt(b.Goal,GasType.DeadlifeDust)>0
                || !CombatDoctorReserveMath.UnexposedRoute(0,
                    DoctorProjectedExposure(doctor,b.Goal,Math.Min(600,TeamCycle(doctor)*2+240))))return false;
            goal=b.Goal;return true;
        }
    }
}

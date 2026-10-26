using System;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class CombatPendingMoveMath
    {
        public static bool Started(bool moving,bool pathFound)=>moving && pathFound;
        public static bool Pending(bool exactCurrent,bool foreign,bool routeStarted,int age,int capturedLock,float step)
            =>exactCurrent && !foreign && !routeStarted && age>=0 && capturedLock>=0
                && step>0 && !float.IsInfinity(step) && !float.IsNaN(step)
                && age<=capturedLock+Math.Max(90f,step*3f);
    }
    public static partial class CombatControlHelper
    {
        // No path yet during an accepted native cooldown is a pending start,
        // not a failed path. This reads the accepted job stamp and finite age;
        // it creates, caches, consumes and releases no PawnPath.
        private static bool PendingOwnedRangedMove(Plan plan)
        {
            var p=plan.Pawn;
            if(!Valid(plan) || plan.RangedWithdrawal?.Value!=p.CurJob || p.CurJobDef!=JobDefOf.Goto
                || !SelectedMoves.TryGetValue(p,out var selected))return false;
            bool foreign=p.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(p,q.job))
                || CareTriageHelper.QueuedCare(p) || CombatNativeHelper.Protected(p);
            if(!CombatPendingMoveMath.Pending(selected.Key==p.CurJob && plan.OwnedJob==p.CurJob,
                foreign,CombatPendingMoveMath.Started(p.pather.Moving,p.pather.curPath?.Found==true),Find.TickManager.TicksGame-selected.AcceptedTick,
                selected.InitialLock,p.TicksPerMoveCardinal))return false;
            var goal=p.CurJob.targetA.Cell;
            if(TeamImmediateDanger(p) || !goal.InBounds(p.Map) || !goal.Standable(p.Map) || goal.Fogged(p.Map)
                || goal.ContainsStaticFire(p.Map) || p.Map.gasGrid.DensityAt(goal,GasType.ToxGas)>0
                || p.Map.gasGrid.DensityAt(goal,GasType.DeadlifeDust)>0)return false;
            TeamEvent("exact_owned_withdrawal_waits_native_start",p,plan.Target);
            return true;
        }
    }
}

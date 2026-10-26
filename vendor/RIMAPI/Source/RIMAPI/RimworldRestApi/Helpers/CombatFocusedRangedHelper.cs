using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static partial class CombatControlHelper
    {
        // An observed aimed lane, never inferred merely from enemy proximity.
        private static bool FocusedRangedThreat(Pawn enemy,Pawn pawn)
        {
            if(!Threat(enemy) || enemy.equipment?.Primary?.def.IsRangedWeapon!=true || AimTarget(enemy)!=pawn)return false;
            var verb=enemy.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            return verb!=null && (enemy.stances.curStance is Stance_Warmup || verb.state==VerbState.Bursting
                || enemy.stances.curStance is Stance_Cooldown)
                && CombatExposureHelper.Lane(enemy,pawn,pawn.Position,enemy.Position)>=.6f;
        }
        private static bool TargetedWoundedRanged(Pawn pawn,System.Collections.Generic.List<Pawn> threats)
            => (pawn.health.summaryHealth.SummaryHealthPercent<.85f || pawn.health.hediffSet.BleedRateTotal>=.1f)
                && threats.Any(e=>FocusedRangedThreat(e,pawn));
        private static bool ReviewFocusedRangedThreat(Plan plan,System.Collections.Generic.List<Pawn> threats)
        {
            var pawn=plan.Pawn;
            if(!TargetedWoundedRanged(pawn,threats) || !CombatOrderHelper.Owned(pawn,pawn.CurJob)
                || pawn.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(pawn,q.job)))return false;
            // Keep a genuinely improving native route; do not cancel and rebuild
            // an already accepted withdrawal every time another gun moves.
            if(pawn.CurJobDef==JobDefOf.Goto && pawn.pather.curPath?.Found==true
                && CombatInterceptHelper.MovementCellsSafe(pawn,RemainingRangedCells(pawn,pawn.pather.curPath))
                && SaferRangedRoute(pawn,pawn.pather.curPath,true,out _))return true;
            bool moved;urgentTeamTransition=true;
            try{moved=TryBreakRangedContact(plan,threats,true);}
            finally{urgentTeamTransition=false;}
            if(moved)TeamEvent("targeted_wounded_ranged_checked_exit",pawn,
                threats.FirstOrDefault(e=>FocusedRangedThreat(e,pawn)));
            return moved;
        }
    }
}

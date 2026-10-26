using System;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class CombatCoverCommitmentMath
    {
        public static bool Keep(int now,int until,bool moverLive,bool exactOwnedMove,bool arrived,
            bool foreign,bool gunCapable,bool immediate,float contact,float locked)
            =>now<=until && moverLive && exactOwnedMove && !arrived && !foreign && gunCapable && !immediate
                && contact>=0 && locked>=0 && !float.IsNaN(contact) && !float.IsNaN(locked)
                && !float.IsInfinity(contact) && !float.IsInfinity(locked) && contact>locked+90f;
    }
    public static partial class CombatControlHelper
    {
        // Readiness to launch the NEXT projectile is not ownership of the
        // CURRENT move/cover transaction. A transient cooldown or conservative
        // future-lane refusal must not reassign this gun to a second mover.
        // This retains target intent only: the unchanged firing/FF checks may
        // stop an unsafe shot. It never licenses firing through an ally.
        private static bool ActiveCoverTransfer(Pawn gun,CoverTransfer cover)
        {
            var mover=cover.Mover;
            if(!Eligible(gun) || !Threat(cover.Enemy) || !mover.Spawned || mover.Dead || mover.Downed
                || mover.Map!=gun.Map || !Plans.TryGetValue(mover.thingIDNumber,out var plan) || !Valid(plan)
                || !SelectedMoves.TryGetValue(mover,out var selected))return false;
            var move=selected.Key;
            bool exact=move?.def==JobDefOf.Goto && Present(mover,move) && plan.OwnedJob==move;
            if(!exact)return false;
            bool foreign=!CombatOrderHelper.Owned(gun,gun.CurJob)
                || gun.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(gun,q.job))
                || mover.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(mover,q.job));
            var threats=gun.Map.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
            return CombatCoverCommitmentMath.Keep(Find.TickManager.TicksGame,cover.Until,true,exact,
                mover.Position==move.targetA.Cell,foreign,!CriticalRangedInjury(gun) && !MedicalFunctionWarning(gun),
                TeamImmediateDanger(gun),EarliestContact(gun,threats),CombatInterceptHelper.MovementLockTicks(gun));
        }
    }
}

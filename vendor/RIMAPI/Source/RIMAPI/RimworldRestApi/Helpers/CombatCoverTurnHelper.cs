using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class CombatCoverTurnMath
    {
        private static bool Known(float x)=>x>=0f && !float.IsNaN(x) && !float.IsInfinity(x);
        public static bool CoverBurstFits(float contact,float first,float burst,float escape)
            =>Known(contact) && Known(first) && Known(burst) && Known(escape)
                && contact>first+burst+escape+30f;
        public static bool ProtectedArrivalImproves(float route,float holding,float terminal,float holdingTerminal,float travel,float settle)
            =>Known(route) && Known(holding) && Known(terminal) && Known(holdingTerminal)
                && Known(travel) && Known(settle) && travel>0f && settle>0f && terminal<=.1f
                && route+terminal*settle<=holding+holdingTerminal*settle-(travel+settle)*.1f;
    }
    // Native route proofs are never cached. Only a bounded candidate cursor
    // survives an incomplete review, so the next pulse does not restart the
    // same rejected prefix. Every selected cell and route is checked afresh.
    public static partial class CombatControlHelper
    {
        private sealed class EscapeSearch
        {public IntVec3 Origin;public Pawn Target;public IntVec3[] Cells;public int Next,Until;}
        private static readonly Dictionary<Pawn,Dictionary<string,EscapeSearch>> EscapeSearches=new Dictionary<Pawn,Dictionary<string,EscapeSearch>>();
        private static IEnumerable<IntVec3> ReviewEscapeCells(Pawn p,Pawn target,string kind,IEnumerable<IntVec3> candidates,int maximum=8)
        {
            int tick=Find.TickManager.TicksGame;
            if(!EscapeSearches.TryGetValue(p,out var searches))EscapeSearches[p]=searches=new Dictionary<string,EscapeSearch>();
            if(!searches.TryGetValue(kind,out var search) || search.Origin!=p.Position || search.Target!=target
                || tick>search.Until || search.Next>=search.Cells.Length)
                searches[kind]=search=new EscapeSearch{Origin=p.Position,Target=target,Cells=candidates.Distinct().Take(256).ToArray(),Until=tick+600};
            int stop=Math.Min(search.Cells.Length,search.Next+maximum);
            while(search.Next<stop)
            {
                yield return search.Cells[search.Next];
                // Normal rejection advances. An exception before completing
                // the proof retains this exact candidate for a fresh review.
                search.Next++;
            }
        }

        private sealed class CoverTurn
        {
            public Plan Mover,Gun;public Pawn Enemy;public int Started,ShotAt=-1,MoveAt=-1,Until;
            public IntVec3 Goal;public bool Moving;
        }
        private static readonly Dictionary<Map,CoverTurn> CoverTurns=new Dictionary<Map,CoverTurn>();
        private static float EarliestContact(Pawn p,List<Pawn> threats)=>threats.Where(e=>MeleeThreat(e) && CombatInterceptHelper.Pursuing(e,p))
            .Select(e=>CombatInterceptHelper.ContactTicks(e,p)).DefaultIfEmpty(10000f).Min();
        private static bool CoverGunWindow(Pawn p,Pawn enemy,List<Pawn> threats,bool allowSelectedIdle=false)
        {
            if(!Eligible(p) || p.CurJobDef==JobDefOf.Goto || CriticalRangedInjury(p) || MedicalFunctionWarning(p)
                || p.jobs.jobQueue.Any() || !CombatOrderHelper.Owned(p,p.CurJob)
                    && !(allowSelectedIdle && CohortOwned(p) && Plans.TryGetValue(p.thingIDNumber,out var selected)
                        && DoctorReserveStationary(selected))
                || !CombatInterceptHelper.CanShootNow(p,enemy))return false;
            var v=p.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            float burst=Math.Max(0,v.verbProps.burstShotCount-1)*v.verbProps.ticksBetweenBurstShots;
            float first=v.state==VerbState.Bursting?0f:
                p.stances.curStance is Stance_Warmup w && w.focusTarg.Thing==enemy?w.ticksLeft:
                CombatInterceptHelper.MovementLockTicks(p)+v.verbProps.warmupTime*60f*p.GetStatValue(StatDefOf.AimingDelayFactor);
            return CombatCoverTurnMath.CoverBurstFits(EarliestContact(p,threats),first,burst,8f/Math.Max(.1f,Speed(p))*60f)
                && IncomingRangedExposure(p,p.Position)<=.6f;
        }
        private static bool TurnValid(CoverTurn t)
        {
            if(!Valid(t.Mover) || !Valid(t.Gun) || !Threat(t.Enemy) || Find.TickManager.TicksGame>t.Until
                || !CombatInterceptHelper.Pursuing(t.Enemy,t.Mover.Pawn))return false;
            foreach(var plan in new[]{t.Mover,t.Gun})
                if(!CombatOrderHelper.Owned(plan.Pawn,plan.Pawn.CurJob)
                    || CombatNativeHelper.Protected(plan.Pawn) || CareTriageHelper.QueuedCare(plan.Pawn)
                    || plan.Pawn.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(plan.Pawn,q.job)))return false;
            return true;
        }
        private static void EndCoverTurn(Map map,CoverTurn turn,string reason)
        {TeamEvent(reason,turn.Mover.Pawn,turn.Enemy,turn.Gun.Pawn);CoverTurns.Remove(map);}
        private static bool KeepCoverTurn(Pawn p,Pawn nextTarget=null)
        {
            if(!CoverTurns.TryGetValue(p.Map,out var t) || !TurnValid(t) || TeamImmediateDanger(p))return false;
            if(p==t.Gun.Pawn)
            {
                var threats=p.Map.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
                if(!CoverGunWindow(p,t.Enemy,threats))return false;
                return nextTarget!=t.Enemy && AimTarget(p)==t.Enemy && CombatOrderHelper.Owned(p,p.CurJob);
            }
            // A finite preparation does not authorize a new advance by the
            // waiting mover. Its useful existing fire remains untouched.
            return p==t.Mover.Pawn && !t.Moving && CombatOrderHelper.Owned(p,p.CurJob);
        }
        private static bool KeepCoverTurnPlan(Plan p,List<Pawn> threats)
        {
            if(!CoverTurns.TryGetValue(p.Pawn.Map,out var t) || !TurnValid(t))return false;
            if(p==t.Gun && CoverGunWindow(p.Pawn,t.Enemy,threats) && AimTarget(p.Pawn)==t.Enemy)return true;
            return p==t.Mover && !t.Moving && !TeamImmediateDanger(p.Pawn);
        }
        private static void ReviewCoverTurns()
        {
            int tick=Find.TickManager.TicksGame;
            foreach(var group in Plans.Values.Where(Valid).GroupBy(p=>p.Pawn.Map).ToArray())
            {
                Map map=group.Key;var threats=map.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
                if(MeleeCohort(map,threats))
                {
                    if(CoverTurns.TryGetValue(map,out var obsolete))EndCoverTurn(map,obsolete,"cover_turn_role_superseded_by_checked_cohort");
                    continue; // Release ONLY the stale role; accepted native jobs remain.
                }
                if(!CoverTurns.TryGetValue(map,out var turn))
                {
                    // Prepare the gun before spending the mover's last escape
                    // margin. Do not preempt a foreign queue or useful burst.
                    foreach(var mover in group.Where(p=>p.Pawn.CurJobDef!=JobDefOf.Goto && CombatOrderHelper.Owned(p.Pawn,p.Pawn.CurJob)
                        && !p.Pawn.jobs.jobQueue.Any()).OrderBy(p=>EarliestContact(p.Pawn,threats)))
                    {
                        var enemy=threats.Where(e=>MeleeThreat(e) && CombatInterceptHelper.Pursuing(e,mover.Pawn))
                            .OrderBy(e=>CombatInterceptHelper.ContactTicks(e,mover.Pawn)).FirstOrDefault();
                        if(enemy==null)continue;
                        float contact=CombatInterceptHelper.ContactTicks(enemy,mover.Pawn);
                        if(contact>TeamCycle(mover.Pawn)*2f+8f/Math.Max(.1f,Speed(mover.Pawn))*60f+90f
                            || contact<=8f/Math.Max(.1f,Speed(mover.Pawn))*60f+30f)continue;
                        var gun=group.Where(p=>p!=mover && CoverGunWindow(p.Pawn,enemy,threats)
                            && (!(p.Pawn.stances.curStance is Stance_Warmup) || AimTarget(p.Pawn)==enemy)
                            && p.Pawn.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb.state!=VerbState.Bursting)
                            .OrderByDescending(p=>AimTarget(p.Pawn)==enemy).ThenBy(p=>IsReservedDoctor(p.Pawn))
                            .ThenByDescending(p=>EarliestContact(p.Pawn,threats)).FirstOrDefault();
                        if(gun==null)continue;
                        var shot=JobMaker.MakeJob(JobDefOf.AttackStatic,enemy);shot.playerForced=true;
                        urgentTeamTransition=true;bool accepted;
                        try{accepted=CombatOrderHelper.Take(gun.Pawn,ref shot);}finally{urgentTeamTransition=false;}
                        if(!accepted)continue;
                        gun.OwnedJob=shot;gun.Target=enemy;gun.Mode="shoot";
                        turn=new CoverTurn{Mover=mover,Gun=gun,Enemy=enemy,Started=tick,
                            Until=tick+(int)Math.Min(600f,contact-30f)};
                        CoverTurns[map]=turn;TeamEvent("cover_turn_prepare_same_enemy",mover.Pawn,enemy,gun.Pawn);break;
                    }
                }
                if(turn==null)continue;
                if(!TurnValid(turn)){EndCoverTurn(map,turn,"cover_turn_released_changed_native_intent_or_deadline");continue;}
                var actor=turn.Mover.Pawn;var helper=turn.Gun.Pawn;
                if(turn.Moving)
                {
                    if(actor.Position==turn.Goal || actor.CurJob==turn.Mover.QueuedShot)
                    {EndCoverTurn(map,turn,"cover_turn_native_arrival_rejoin_review");continue;}
                    if(!CoverGunWindow(helper,turn.Enemy,threats))
                        EndCoverTurn(map,turn,"cover_turn_gun_escape_deadline_releases_own_fire");
                    continue;
                }
                float left=CombatInterceptHelper.ContactTicks(turn.Enemy,actor);
                if(left<=8f/Math.Max(.1f,Speed(actor))*60f+30f || !CoverGunWindow(helper,turn.Enemy,threats))
                {EndCoverTurn(map,turn,"cover_turn_no_wait_past_escape_deadline");continue;}
                int realShot=CombatShotEvidenceHelper.LastTick(helper,turn.Enemy.thingIDNumber);
                if(realShot<turn.Started)continue;
                if(turn.ShotAt<0){turn.ShotAt=realShot;TeamEvent("cover_turn_real_same_enemy_projectile",actor,turn.Enemy,helper);}
                urgentTeamTransition=true;
                try
                {
                    if(!TryRangedRetreat(actor,turn.Enemy,turn.Mover.Anchor,out var move,true))continue;
                    turn.Mover.OwnedJob=move;turn.Mover.QueuedShot=SelectedMoves[actor].Value;
                    turn.Mover.Target=turn.Enemy;turn.Mover.Mode="retreat";turn.Mover.LastMoveTick=tick;
                    turn.Moving=true;turn.MoveAt=tick;turn.Goal=move.targetA.Cell;
                    TeamEvent("cover_turn_checked_move_after_real_shot",actor,turn.Enemy,helper);
                }
                finally{urgentTeamTransition=false;}
            }
        }
    }
}

using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class CombatDoctorDetourMath
    {
        public static bool Keep(bool exactFirst,bool pendingFirst,bool atVia,bool nativeIdle,bool foreign,bool clinical,int age)
            =>!foreign && !clinical && age>=0 && age<=600 && (exactFirst || pendingFirst || atVia && nativeIdle);
    }
    public static partial class CombatControlHelper
    {
        private sealed class DoctorDetour
        {public CombatJobStamp First;public IntVec3 Via,Goal;public int Started,Review;}
        private static readonly Dictionary<Pawn,DoctorDetour> DoctorDetours=new Dictionary<Pawn,DoctorDetour>();
        private static void PruneDoctorDetours()
        {
            foreach(var p in DoctorDetours.Keys.ToArray())
                if(!Plans.TryGetValue(p.thingIDNumber,out var plan) || !Valid(plan) || !KeepDoctorDetour(p))DoctorDetours.Remove(p);
        }
#if LAYA_COMBAT_LAB
        private static readonly List<object> DoctorRouteEvents=new List<object>();
        private static readonly Dictionary<string,int> DoctorRouteReasons=new Dictionary<string,int>();
        private static void DoctorRouteRefusal(string reason,Pawn p,IntVec3? via=null,IntVec3? goal=null)
        {
            DoctorRouteReasons[reason]=DoctorRouteReasons.TryGetValue(reason,out var n)?n+1:1;
            if(DoctorRouteEvents.Count<128)DoctorRouteEvents.Add(new{tick=Find.TickManager.TicksGame,reason,pawn=p.thingIDNumber,
                x=p.Position.x,z=p.Position.z,via_x=via?.x,via_z=via?.z,goal_x=goal?.x,goal_z=goal?.z});
        }
        private static void DoctorRouteEvent(string reason,Pawn p,DoctorDetour d)
        {if(DoctorRouteEvents.Count<128)DoctorRouteEvents.Add(new{tick=Find.TickManager.TicksGame,reason,pawn=p.thingIDNumber,
            x=p.Position.x,z=p.Position.z,via_x=d.Via.x,via_z=d.Via.z,goal_x=d.Goal.x,goal_z=d.Goal.z,
            current=p.CurJobDef?.defName,current_id=p.CurJob?.loadID,current_goal=p.CurJob?.targetA.Cell.ToString(),first_id=d.First.Value?.loadID});}
        private static object DoctorRouteDiagnostics()=>new{events=DoctorRouteEvents.ToArray(),reasons=new Dictionary<string,int>(DoctorRouteReasons),active=DoctorDetours.Count};
#endif
        private static void DoctorRouteReject(string reason,Pawn p,IntVec3? via=null,IntVec3? goal=null)
        {
#if LAYA_COMBAT_LAB
            DoctorRouteRefusal(reason,p,via,goal);
#endif
        }
        private static bool DoctorDetourPending(Pawn p,DoctorDetour d)
        {
            if(d.First.Value==null || !CombatOrderHelper.Owned(p,d.First.Value)
                || !p.jobs.jobQueue.Any(q=>q.job==d.First.Value) || !SelectedMoves.TryGetValue(p,out var selected))return false;
            bool current=CombatOrderHelper.Owned(p,p.CurJob) || (p.CurJobDef==JobDefOf.Wait_Combat
                || p.CurJobDef==JobDefOf.Wait_MaintainPosture) && !p.CurJob.playerForced;
            bool foreign=p.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(p,q.job));
            return current && CombatPendingMoveMath.Pending(true,foreign,false,Find.TickManager.TicksGame-d.Started,
                selected.InitialLock,p.TicksPerMoveCardinal);
        }
        private static bool KeepDoctorDetour(Pawn p)
        {
            if(!Eligible(p) || !DoctorDetours.TryGetValue(p,out var d) || TeamImmediateDanger(p))return false;
            bool foreign=p.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(p,q.job));
            bool idle=p.CurJob==null || (p.CurJobDef==JobDefOf.Wait_Combat || p.CurJobDef==JobDefOf.Wait_MaintainPosture)
                && (!p.CurJob.playerForced || CombatOrderHelper.Owned(p,p.CurJob));
            return CombatDoctorDetourMath.Keep(d.First.Value==p.CurJob && p.CurJobDef==JobDefOf.Goto
                && CombatOrderHelper.Owned(p,p.CurJob),DoctorDetourPending(p,d),p.Position==d.Via,idle,foreign,
                CombatNativeHelper.Protected(p) || CareTriageHelper.QueuedCare(p),Find.TickManager.TicksGame-d.Started);
        }
        private static CombatPathBudgetHelper.Observation JoinDoctorRoute(Pawn p,
            CombatPathBudgetHelper.Observation first,CombatPathBudgetHelper.Observation second,bool remaining)
        {
            var a=(remaining?RemainingRangedCells(p,first).Prepend(p.Position):first.NodesReversed.Reverse()).ToArray();
            var b=second.NodesReversed.Reverse().Skip(1);
            return new CombatPathBudgetHelper.Observation(first.Found && second.Found,
                first.TotalCost+second.TotalCost,a.Concat(b).Reverse());
        }
        private static bool TryDoctorDetour(Plan plan,List<Pawn> threats,IEnumerable<IntVec3> pool)
        {
            try{return TryDoctorDetourCore(plan,threats,pool);}
            catch(CombatReviewDeferredException){DoctorRouteReject("budget_deferred",plan.Pawn);throw;}
        }
        private static bool TryDoctorDetourCore(Plan plan,List<Pawn> threats,IEnumerable<IntVec3> pool)
        {
            var p=plan.Pawn;
            if(!ClinicalRangedTransit(p) || p.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(p,q.job)))return false;
            var goals=pool.Where(c=>IncomingRangedExposure(p,c)<=.1f && c.DistanceTo(p.Position)>4f)
                .OrderBy(c=>c.DistanceToSquared(p.Position)).Take(8).ToArray();
            if(goals.Length==0){DoctorRouteReject("no_protected_goals",p);return false;}
            float current=IncomingRangedExposure(p,p.Position);
            // The native shortest path has no enemy-fire cost. Probe bounded
            // lateral waypoints, then validate both native legs as ONE route.
            // Only the first Goto is issued; arrival must revalidate the tail.
            var vias=GenAdj.CardinalDirections.Select(v=>p.Position+v*3)
                .Where(c=>c.InBounds(p.Map) && c.Standable(p.Map) && !c.Fogged(p.Map) && !CellClaimed(p,c)
                    && !c.GetThingList(p.Map).Any(t=>t is Pawn || t is Building_Trap)
                    && threats.All(e=>c.DistanceTo(e.Position)>=8f)
                    && IncomingRangedExposure(p,c)<=current+.1f)
                .OrderBy(c=>goals.Min(g=>c.DistanceToSquared(g)));
            var key=threats.Where(e=>e.equipment?.Primary?.def.IsRangedWeapon==true).OrderBy(e=>e.thingIDNumber).FirstOrDefault() ?? plan.Target;
            bool anyVia=false;
            foreach(var via in ReviewEscapeCells(p,key,"doctor_two_leg",vias,1))
            {
                anyVia=true;
                var goal=goals.OrderBy(g=>g.DistanceToSquared(via)).First();
                using(var first=CombatPathBudgetHelper.Query(p,p.Position,via,PathEndMode.OnCell))
                using(var tail=CombatPathBudgetHelper.Query(p,via,goal,PathEndMode.OnCell))
                using(var joined=JoinDoctorRoute(p,first,tail,false))
                {
                    if(!first.Found || first.TotalCost>120f){DoctorRouteReject("first_missing_or_long",p,via,goal);continue;}
                    if(!tail.Found || joined.TotalCost>480f){DoctorRouteReject("tail_missing_or_long",p,via,goal);continue;}
                    if(!CombatInterceptHelper.MovementSafe(p,joined)){DoctorRouteReject("movement_unsafe",p,via,goal);continue;}
                    if(!SaferRangedRoute(p,joined,false,out _,via)){DoctorRouteReject("exposure_not_improving",p,via,goal);continue;}
                }
                bool accepted;urgentTeamTransition=true;
                try
                {
                    if(KeepGroupPosition(p,via))continue;
                    var move=JobMaker.MakeJob(JobDefOf.Goto,via);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                    accepted=CombatOrderHelper.Take(p,ref move);if(!accepted){DoctorRouteReject("native_take_refused",p,via,goal);continue;}
                    p.stances.CancelBusyStanceSoft();move=RememberMove(p,move,null);
                    plan.OwnedJob=move;plan.QueuedShot=null;plan.Mode="retreat";plan.LastMoveTick=Find.TickManager.TicksGame;
                    plan.RangedWithdrawal=new CombatJobStamp(move);RetreatJobs[p]=new CombatJobStamp(move);
                    plan.RecoveryCell=goal;plan.RecoveryUntilTick=Find.TickManager.TicksGame+600;
                    DoctorDetours[p]=new DoctorDetour{First=new CombatJobStamp(move),Via=via,Goal=goal,Started=Find.TickManager.TicksGame};
#if LAYA_COMBAT_LAB
                    DoctorRouteEvent("first_accepted",p,DoctorDetours[p]);
#endif
                    TeamEvent("doctor_two_leg_first_accepted",p,plan.Target);
                }
                finally{urgentTeamTransition=false;}
                return true;
            }
            if(!anyVia)DoctorRouteReject("no_eligible_via",p);
            return false;
        }
        private static bool ReviewDoctorDetour(Plan plan,List<Pawn> threats)
        {
            var p=plan.Pawn;if(!DoctorDetours.TryGetValue(p,out var d))return false;
            if(!KeepDoctorDetour(p) || !threats.Any()){DoctorDetours.Remove(p);return false;}
            int tick=Find.TickManager.TicksGame;
            if(DoctorDetourPending(p,d))return true;
            if(p.Position!=d.Via)
            {
                if(PendingOwnedRangedMove(plan))return true;
                if(tick<d.Review)return true;d.Review=tick+60;
                using(var first=CombatPathBudgetHelper.Borrowed(p.pather.curPath))
                using(var tail=CombatPathBudgetHelper.Query(p,d.Via,d.Goal,PathEndMode.OnCell))
                using(var joined=JoinDoctorRoute(p,first,tail,true))
                    if(first.Found && tail.Found && CombatInterceptHelper.MovementSafe(p,joined)
                        && SaferRangedRoute(p,joined,true,out _,d.Via))return true;
                DoctorDetours.Remove(p);TeamEvent("doctor_two_leg_changed_route_refused",p,plan.Target);return false;
            }
            // Do not interpret an accepted first leg as arrival at shelter.
            // Later/manual/clinical jobs were checked above; the ordinary
            // transition and the whole remaining path must still be valid.
            using(var tail=CombatPathBudgetHelper.Query(p,p.Position,d.Goal,PathEndMode.OnCell))
                if(!CombatInterceptHelper.MovementSafe(p,tail) || !SaferRangedRoute(p,tail,false,out _))
                {DoctorRouteReject("arrival_tail_unsafe_or_unimproved",p,d.Via,d.Goal);DoctorDetours.Remove(p);TeamEvent("doctor_two_leg_tail_refused",p,plan.Target);return false;}
            urgentTeamTransition=true;
            try
            {
                var move=JobMaker.MakeJob(JobDefOf.Goto,d.Goal);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                if(!CombatOrderHelper.Take(p,ref move))return true;
                move=RememberMove(p,move,null);plan.OwnedJob=move;plan.QueuedShot=null;plan.Mode="retreat";plan.LastMoveTick=tick;
                plan.RangedWithdrawal=new CombatJobStamp(move);RetreatJobs[p]=new CombatJobStamp(move);
#if LAYA_COMBAT_LAB
                DoctorRouteEvent("tail_accepted_after_native_arrival",p,d);
#endif
                TeamEvent("doctor_two_leg_tail_accepted_after_arrival",p,plan.Target);DoctorDetours.Remove(p);return true;
            }
            finally{urgentTeamTransition=false;}
        }
    }
}

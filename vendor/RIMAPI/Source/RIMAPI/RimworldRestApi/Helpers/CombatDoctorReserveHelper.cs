using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class CombatDoctorReserveMath
    {
        private static bool Known(float n)=>n>=0 && !float.IsNaN(n) && !float.IsInfinity(n);
        public static bool Early(float current,float forecast)
            =>Known(current) && Known(forecast) && current<.6f && forecast>=.6f;
        public static bool Worse(float current,float proposed)
            =>!Known(current) || !Known(proposed) || proposed>current+.1f;
        public static bool UnexposedRoute(float peak,float terminal)
            =>Known(peak) && Known(terminal) && peak<=.1f && terminal<=.1f;
    }
    public static partial class CombatControlHelper
    {
        private static readonly Dictionary<Pawn,int> DoctorPrepositionReviews=new Dictionary<Pawn,int>();
#if LAYA_COMBAT_LAB
        private static readonly List<object> DoctorReserveEvents=new List<object>();
        private static readonly Dictionary<string,int> DoctorReserveCounts=new Dictionary<string,int>();
        private static object DoctorReserveDiagnostics()=>new{counts=new Dictionary<string,int>(DoctorReserveCounts),events=DoctorReserveEvents.ToArray()};
#endif
        private static void DoctorReserveTrace(string reason,Pawn p,IntVec3? goal=null,float? current=null,float? forecast=null)
        {
#if LAYA_COMBAT_LAB
            DoctorReserveCounts[reason]=DoctorReserveCounts.TryGetValue(reason,out var n)?n+1:1;
            if(DoctorReserveEvents.Count<128)DoctorReserveEvents.Add(new{tick=Find.TickManager.TicksGame,reason,pawn=p.thingIDNumber,
                x=p.Position.x,z=p.Position.z,goal_x=goal?.x,goal_z=goal?.z,current,forecast,
                job=p.CurJobDef?.defName,job_id=p.CurJob?.loadID});
#endif
        }
        // Only native observed routes are projected. Unknown geometry remains
        // unknown; comfortable current cover does not erase an observed flank.
        private static float DoctorProjectedExposure(Pawn p,IntVec3 cell,float horizon)
        {
            if(horizon<0 || float.IsNaN(horizon) || float.IsInfinity(horizon))return float.PositiveInfinity;
            float peak=IncomingRangedExposure(p,cell);
            for(float time=120f;time<=horizon;time+=120f)
            {CombatPathBudgetHelper.Checkpoint("doctor_projected_exposure");peak=Math.Max(peak,IncomingRangedExposure(p,cell,time));}
            if(horizon>0)peak=Math.Max(peak,IncomingRangedExposure(p,cell,horizon));
            return peak;
        }
        // Capability to hold a position is not evidence of a covering shot.
        // An approaching enemy can be outside native range while these guns
        // remain armed and stationary. Early transit must be unexposed itself.
        private static bool DoctorReserveStationary(Plan g)
            =>OwnStationaryGun(g) || Valid(g) && g.Pawn.CurJobDef==JobDefOf.Wait_Combat
                && !g.Pawn.CurJob.playerForced && g.Pawn.pather?.Moving!=true
                && !g.Pawn.jobs.jobQueue.Any() && !(g.Pawn.carryTracker?.CarriedThing is Pawn);
        private static bool DoctorReserveGun(Plan g,Pawn physician)
            =>g.Pawn!=physician && DoctorReserveStationary(g)
                && g.Pawn.equipment?.Primary?.def.IsRangedWeapon==true
                && !CriticalRangedInjury(g.Pawn) && !MedicalFunctionWarning(g.Pawn)
                && !CareTriageHelper.QueuedCare(g.Pawn) && !CombatNativeHelper.Protected(g.Pawn);
        private static bool BesideOpaqueCover(Map map,IntVec3 cell)
            =>GenAdj.CardinalDirections.Any(direction=>(cell+direction).InBounds(map)
                && (cell+direction).GetEdifice(map)?.def.Fillage==FillCategory.Full);
        private static void ReviewDoctorPreposition()
        {
            int tick=Find.TickManager.TicksGame;
            foreach(var group in Plans.Values.Where(Valid).GroupBy(p=>p.Pawn.Map).ToArray())
            {
                var threats=group.Key.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
                var key=threats.Where(e=>e.equipment?.Primary?.def.IsRangedWeapon==true).OrderBy(e=>e.thingIDNumber).FirstOrDefault();
                if(key==null)continue;
                var p=ReservedDoctor(group.Key);
                if(p==null || !Plans.TryGetValue(p.thingIDNumber,out var plan) || !DoctorReserveStationary(plan)
                    || CareTriageHelper.QueuedCare(p) || CombatNativeHelper.Protected(p) || TeamImmediateDanger(p)
                    || p.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb.state==VerbState.Bursting
                    || DoctorPrepositionReviews.TryGetValue(p,out var last) && tick-last<45)continue;
                float current=IncomingRangedExposure(p,p.Position),forecast=DoctorProjectedExposure(p,p.Position,600f);
                if(!CombatDoctorReserveMath.Early(current,forecast))continue;
                DoctorPrepositionReviews[p]=tick;DoctorReserveTrace("observed_flank_before_current_exposure",p,null,current,forecast);
                int stationary=group.Count(g=>DoctorReserveGun(g,p));
                if(stationary<2){DoctorReserveTrace("less_than_two_stationary_guns",p);continue;}
                // Proposal order only: prefer cells outside the loaded range
                // of current and observed future enemy positions. Ranking a
                // middle rear point first can page through the warning window.
                // Every chosen cell still needs the full exposure/path proof.
                try
                {
                var rangeBounds=new List<Tuple<IntVec3,float>>();
                foreach(var enemy in threats.Where(e=>e.equipment?.Primary?.def.IsRangedWeapon==true))
                {
                    if(!CombatInterceptHelper.TryObservedFuturePosition(enemy,600f,out var future))return;
                    float range=enemy.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb.verbProps.range;
                    rangeBounds.Add(Tuple.Create(enemy.Position,range));rangeBounds.Add(Tuple.Create(future,range));
                }
                float dx=p.Position.x-(float)threats.Average(e=>e.Position.x),dz=p.Position.z-(float)threats.Average(e=>e.Position.z);
                float length=(float)Math.Sqrt(dx*dx+dz*dz);if(length<1f)continue;
                float back=Math.Min(18f,threats.Where(e=>e.equipment?.Primary?.def.IsRangedWeapon==true)
                    .Max(e=>e.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb.verbProps.range)*.5f);
                var rear=new IntVec3(p.Position.x+(int)Math.Round(dx/length*back),0,p.Position.z+(int)Math.Round(dz/length*back));
                // Rank near a loaded-range rear bound. Paging every adjacent
                // exposed cell first can exhaust the entire warning window.
                // Ranking is only a proposal; all exposure/path gates remain.
                var cells=GenRadial.RadialCellsAround(p.Position,18f,false)
                    .Where(c=>c.InBounds(p.Map) && c.Standable(p.Map) && !c.Fogged(p.Map) && !CellClaimed(p,c)
                        && c!=p.Position && c.DistanceTo(p.Position)<=18f && c.DistanceTo(plan.Anchor)<=26f
                        && !c.GetThingList(p.Map).Any(t=>t is Pawn || t is Building_Trap)
                        && threats.All(e=>c.DistanceTo(e.Position)>=8f))
                    // Range margin alone put all finite pages into exposed
                    // open ground and omitted nearer existing wall edges.
                    // Static adjacency ranks a PROPOSAL only; current and all
                    // projected lanes plus the whole native route below must
                    // still be unexposed. No cover value is inferred here.
                    .OrderBy(c=>BesideOpaqueCover(p.Map,c)?0:1)
                    .ThenByDescending(c=>rangeBounds.Min(b=>c.DistanceTo(b.Item1)-b.Item2))
                    .ThenBy(c=>c.DistanceToSquared(p.Position));
                    foreach(var cell in ReviewEscapeCells(p,key,"doctor_early_position",cells,2))
                    {
                        if(IncomingRangedExposure(p,cell)>.1f){DoctorReserveTrace("current_endpoint_exposed",p,cell);continue;}
                        if(DoctorProjectedExposure(p,cell,600f)>.1f){DoctorReserveTrace("forecast_endpoint_exposed",p,cell);continue;}
                        using(var route=CombatPathBudgetHelper.Query(p,p.Position,cell,PathEndMode.OnCell))
                        {
                            if(!route.Found || route.TotalCost>480f){DoctorReserveTrace("route_missing_or_long",p,cell);continue;}
                            if(!CombatInterceptHelper.MovementSafe(p,route) || !SaferRangedRoute(p,route,false,out _,null,600f,true))
                            {DoctorReserveTrace("route_not_safely_improving",p,cell);continue;}
                        }
                        bool moved;urgentTeamTransition=true;
                        try
                        {
                            var move=JobMaker.MakeJob(JobDefOf.Goto,cell);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                            moved=CombatOrderHelper.Take(p,ref move);if(!moved){DoctorReserveTrace("native_take_refused",p,cell);continue;}
                            p.stances.CancelBusyStanceSoft();move=RememberMove(p,move,null);
                            plan.OwnedJob=move;plan.QueuedShot=null;plan.Mode="retreat";plan.LastMoveTick=tick;
                            plan.RangedWithdrawal=new CombatJobStamp(move);RetreatJobs[p]=new CombatJobStamp(move);
                            plan.RecoveryCell=cell;plan.RecoveryUntilTick=tick+180;MedicalExits.Add(p);
                            RememberDoctorBound(p,move,cell);
                            DoctorReserveTrace("early_native_move_accepted",p,cell,current,forecast);
                            TeamEvent("physician_preposition_before_observed_flank",p,key);
                        }
                        finally{urgentTeamTransition=false;}
                        return;
                    }
                }
                catch(CombatReviewDeferredException)
                {
                    // A deferred search has not completed this candidate.
                    // Resume its retained finite page on the next pulse;
                    // do not spend the warning window on the normal45tick delay.
                    DoctorPrepositionReviews.Remove(p);
                    DoctorReserveTrace("budget_deferred",p);throw;
                }
                return; // One finite medical-position review per pulse.
            }
        }
    }
}

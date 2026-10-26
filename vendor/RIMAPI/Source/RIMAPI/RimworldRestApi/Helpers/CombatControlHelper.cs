using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;
using RIMAPI.Models;

namespace RIMAPI.Helpers
{
    // Execute the selected ranged plan between strategic model decisions.
    // No saved orders, unselected pawns, patient jobs or enemy AI changes.
    public static partial class CombatControlHelper
    {
        private class Plan
        {
            public Pawn Pawn; public string Tactic; public IntVec3 Anchor;
            private CombatJobStamp owned,queued;
            public Job OwnedJob{get=>owned?.Value;set=>owned=new CombatJobStamp(value);}
            public Job QueuedShot{get=>queued?.Value;set=>queued=new CombatJobStamp(value);}
            public Pawn Target; public int UntilTick;
            public DateTime UntilUtc; public string Mode; public int LastMoveTick;
            public IntVec3 ProgressCell; public int ProgressTick;
            public int RangedCoverReviewTick; public int DefenseReviewTick;
            public int CoverTransitReviewTick;public bool CoverTransitUseful=true;
            public int SupportReviewTick;
            public int FriendlyLaneReviewTick;
            public int InterceptReviewTick;public JobDef InterceptObservedJob;public IntVec3 InterceptObservedGoal;
            public Building WatchedBreach; public IntVec3 BreachPosition;
            public IntVec3 RecoveryCell; public int RecoveryUntilTick;
            public CombatJobStamp RangedWithdrawal;
            public CombatJobStamp FastBait;public int FastBaitReviewTick;public int[] FastBaitCover=new int[0];
        }
        private sealed class SelectedMove
        {
            private readonly CombatJobStamp move,shot;
            public readonly int AcceptedTick,InitialLock;
            public IntVec3 ProgressCell;public int ProgressTick;
            public SelectedMove(Pawn pawn,Job acceptedMove,Job acceptedShot)
            {move=new CombatJobStamp(acceptedMove);shot=new CombatJobStamp(acceptedShot);
                AcceptedTick=ProgressTick=Find.TickManager.TicksGame;ProgressCell=pawn.Position;
                InitialLock=(int)Math.Ceiling(CombatInterceptHelper.MovementLockTicks(pawn));}
            public Job Key=>move.Value;public Job Value=>shot.Value;
        }
        private static readonly Dictionary<int,Plan> Plans=new Dictionary<int,Plan>();
        private static readonly Dictionary<Pawn,CombatJobStamp> RetreatJobs=new Dictionary<Pawn,CombatJobStamp>();
        private static readonly Dictionary<Pawn,SelectedMove> SelectedMoves=new Dictionary<Pawn,SelectedMove>();
        private static readonly Dictionary<Pawn,IntVec3> AssemblyAnchors=new Dictionary<Pawn,IntVec3>();
        private static readonly HashSet<string> RangedPlans=new HashSet<string>{"hold_cover","firing_line","focus_fire","advance_to_range","preemptive_strike","intercept_kidnapper","backstep_fire","kite","contact_melee","stationary_fire","fallback_line","spread_out","withdraw_and_regroup"};
#if LAYA_COMBAT_LAB
        public static bool TestDisabled;
        public static int PulseTicks,Remembered,Cancelled,Retreated,Attempted,Supported,LineHeld,SelectedLineHeld,WarmupsKept;
        public static readonly List<object> CancelledEvents=new List<object>();
        public static readonly List<object> EscapeWindowRefusals=new List<object>();
        public static readonly List<object> RetreatPostReviews=new List<object>();
        public static readonly List<object> GroupFocusReviews=new List<object>();
        public static readonly List<object> SupportWindowReviews=new List<object>();
        private static readonly Dictionary<int,int> LastGroupFocusReview=new Dictionary<int,int>();
        public static readonly List<object> InterceptStops=new List<object>();
        public static readonly List<object> LineWindowChecks=new List<object>();
        public static readonly List<object> WarmupCuts=new List<object>();
        public static readonly List<object> EarlyRotationEvents=new List<object>();
        public static readonly List<object> CoverForecastChecks=new List<object>();
        public static readonly List<object> CoverTransits=new List<object>();
        public static readonly List<object> CoverTransitReviews=new List<object>();
        public static int CoverForecastRejected,CoverForecastUnknown;
        public static readonly List<object> RangedRouteChecks=new List<object>();
        public static readonly List<object> RangedWithdrawals=new List<object>();
        public static readonly List<object> RangedThreatForecasts=new List<object>();
        private static readonly Dictionary<int,int> LastRangedThreatForecast=new Dictionary<int,int>();
        public static readonly List<object> FastBaitEvents=new List<object>();
        private static readonly Dictionary<int,int> LastLineCheck=new Dictionary<int,int>();
        public static string TestMode(Pawn pawn)=>Plans.TryGetValue(pawn.thingIDNumber,out var plan)?plan.Mode:null;
        public static int? TestTarget(Pawn pawn)=>Plans.TryGetValue(pawn.thingIDNumber,out var plan)?plan.Target?.thingIDNumber:null;
        public static bool TestContactSupport(Pawn pawn,out Job move)
        {
            move=null;
            if(!Plans.TryGetValue(pawn.thingIDNumber,out var plan) || !Valid(plan))
                throw new InvalidOperationException("Held support contract has no eligible selected native plan");
            bool accepted=TryContactSupport(plan,pawn.Map.mapPawns.AllPawnsSpawned.Where(Threat).ToList());
            if(accepted)move=plan.OwnedJob;
            return accepted;
        }
        public static void TestDeclareSupport(Pawn pawn,Pawn target,IntVec3 goal,bool foreignQueue)
        {
            if(!Plans.TryGetValue(pawn.thingIDNumber,out var plan) || !Valid(plan))
                throw new InvalidOperationException("Declared support needs the exact held native selected plan");
            var move=JobMaker.MakeJob(JobDefOf.Goto,goal);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
            if(!CombatOrderHelper.Take(pawn,ref move))throw new InvalidOperationException("Declared support move rejected");
            var shot=CombatOrderHelper.QueueShot(pawn,target);move=RememberMove(pawn,move,shot);
            plan.OwnedJob=move;plan.QueuedShot=shot;plan.Target=target;plan.Mode="support";plan.SupportReviewTick=0;
            plan.LastMoveTick=Find.TickManager.TicksGame;
            if(foreignQueue)
            {
                var later=JobMaker.MakeJob(JobDefOf.Wait);later.playerForced=true;
                pawn.jobs.jobQueue.EnqueueLast(later);
            }
        }
        private static void RecordGroupFocus(Pawn pawn,List<Pawn> threats,Pawn[] guns,Func<Pawn,float> score,
            Pawn requested,Pawn rawBest,Pawn committed,Pawn best,Pawn personal,Pawn chosen,bool deadline)
        {
            int tick=Find.TickManager.TicksGame;
            if(GroupFocusReviews.Count>=128 || threats.Count<2
                || LastGroupFocusReview.TryGetValue(pawn.thingIDNumber,out var last) && tick-last<60)return;
            LastGroupFocusReview[pawn.thingIDNumber]=tick;
            GroupFocusReviews.Add(new{tick,pawn=pawn.thingIDNumber,requested=requested?.thingIDNumber,
                raw_best=rawBest?.thingIDNumber,committed=committed?.thingIDNumber,
                best_after_commit=best?.thingIDNumber,personal=personal?.thingIDNumber,chosen=chosen?.thingIDNumber,deadline_override=deadline,
                job=pawn.CurJobDef?.defName,aimed=AimTarget(pawn)?.thingIDNumber,
                warmup=(pawn.stances.curStance as Stance_Warmup)?.ticksLeft,
                gun_lock=CombatInterceptHelper.MovementLockTicks(pawn),observed_threat_count=threats.Count,
                candidates=threats.Take(12).Select(t=>new{id=t.thingIDNumber,x=t.Position.x,z=t.Position.z,
                    health=t.health.summaryHealth.SummaryHealthPercent,weapon=t.equipment?.Primary?.def.defName,
                    victim=ObservedVictim(t)?.thingIDNumber,legal_current_shot=CombatInterceptHelper.CanShootNow(pawn,t),
                    contact_estimate=ObservedVictim(t) is Pawn victim?CombatInterceptHelper.ContactTicks(t,victim):(float?)null,
                    urgency=ThreatUrgency(t,guns),score=score(t)}).ToArray(),
                team=guns.Select(g=>new{id=g.thingIDNumber,x=g.Position.x,z=g.Position.z,job=g.CurJobDef?.defName,
                    aimed=AimTarget(g)?.thingIDNumber,warmup=(g.stances.curStance as Stance_Warmup)?.ticksLeft}).ToArray(),
                meaning="Bounded read-only record of actual native group choice. Scores and contact estimates are decision inputs, not shots or outcomes."});
        }
        public static object Diagnostics()=>new {component=Current.Game.GetComponent<CombatControlComponent>()!=null,plans=Plans.Count,pulses=PulseTicks,remembered=Remembered,cancelled=Cancelled,retreated=Retreated,attempted=Attempted,supported=Supported,supported_line_holds=LineHeld,selected_line_holds=SelectedLineHeld,warmups_kept=WarmupsKept,cancel_events=CancelledEvents.ToArray(),escape_window_refusals=EscapeWindowRefusals.ToArray(),retreat_posts=RetreatPostReviews.ToArray(),intercept_stops=InterceptStops.ToArray(),line_window_checks=LineWindowChecks.ToArray(),warmup_cuts=WarmupCuts.ToArray(),early_rotations=EarlyRotationEvents.ToArray(),cover_transit_reviews=CoverTransitReviews.ToArray(),cover_transits=CoverTransits.ToArray(),cover_forecast_checks=CoverForecastChecks.ToArray(),cover_forecast_rejected=CoverForecastRejected,cover_forecast_unknown=CoverForecastUnknown,ranged_route_checks=RangedRouteChecks.ToArray(),ranged_withdrawals=RangedWithdrawals.ToArray(),ranged_threat_forecasts=RangedThreatForecasts.ToArray(),fast_bait_events=FastBaitEvents.ToArray(),contact_defense=CombatContactHelper.Diagnostics(),orders=CombatOrderHelper.Diagnostics(),path_budget=CombatPathBudgetHelper.Diagnostics(),team_care=TeamCareDiagnostics(),caregiver_recovery=CaregiverRecoveryHelper.Diagnostics()};
        public static void TestReset(bool disabled){CombatCarrierVolleyHelper.Reset();TestDisabled=disabled;Plans.Clear();RetreatJobs.Clear();SelectedMoves.Clear();AssemblyAnchors.Clear();PulseTicks=Remembered=Cancelled=Retreated=Attempted=Supported=LineHeld=SelectedLineHeld=WarmupsKept=CoverForecastRejected=CoverForecastUnknown=0;CancelledEvents.Clear();EscapeWindowRefusals.Clear();RetreatPostReviews.Clear();GroupFocusReviews.Clear();SupportWindowReviews.Clear();LastGroupFocusReview.Clear();InterceptStops.Clear();LineWindowChecks.Clear();LastLineCheck.Clear();WarmupCuts.Clear();EarlyRotationEvents.Clear();CoverForecastChecks.Clear();CoverTransits.Clear();CoverTransitReviews.Clear();RangedRouteChecks.Clear();RangedWithdrawals.Clear();RangedThreatForecasts.Clear();LastRangedThreatForecast.Clear();FastBaitEvents.Clear();}
#endif
        public static Job RememberMove(Pawn pawn,Job move,Job shot)
        {
            // TryTakeOrderedJob can retain an equivalent existing Goto. Track
            // the accepted native job, not an unused request object.
            if(move?.def==JobDefOf.Goto && pawn.CurJobDef==JobDefOf.Goto && pawn.CurJob.playerForced
                && pawn.CurJob.targetA.Cell==move.targetA.Cell && pawn.CurJob.locomotionUrgency==move.locomotionUrgency)
                move=pawn.CurJob;
            else if(move?.def==JobDefOf.Goto && !Present(pawn,move))
                move=pawn.jobs.jobQueue.Select(q=>q.job).FirstOrDefault(j=>j.def==JobDefOf.Goto && j.playerForced
                    && j.targetA.Cell==move.targetA.Cell && j.locomotionUrgency==move.locomotionUrgency) ?? move;
            if(!SelectedMoves.TryGetValue(pawn,out var existing) || existing.Key!=move || existing.Value!=shot)
                SelectedMoves[pawn]=new SelectedMove(pawn,move,shot);
            if(AssemblyAnchors.TryGetValue(pawn,out var assembly) && move?.targetA.Cell!=assembly)AssemblyAnchors.Remove(pawn);
            return move;
        }
        public static bool PreserveMoveBeforeShot(Pawn pawn,Job requested)
        {
            if(requested?.def!=JobDefOf.AttackStatic || !Eligible(pawn)
                || !SelectedMoves.TryGetValue(pawn,out var selected))return false;
            var move=selected.Key;var shot=selected.Value;var target=requested.targetA.Thing as Pawn;
            if(move?.def!=JobDefOf.Goto || shot==null || shot.targetA.Thing!=target || target==null || !Threat(target)
                || !Present(pawn,move) || !Present(pawn,shot) || pawn.Position==move.targetA.Cell)return false;
            int tick=Find.TickManager.TicksGame;
            if(pawn.Position!=selected.ProgressCell){selected.ProgressCell=pawn.Position;selected.ProgressTick=tick;}
            bool pending=pawn.jobs.jobQueue.Any(q=>q.job==move);
            int noProgress=tick-selected.ProgressTick;
            int allowance=(int)Math.Ceiling(Math.Max(90f,pawn.TicksPerMoveCardinal*3f));
            if(selected.ProgressTick==selected.AcceptedTick)allowance+=selected.InitialLock;
            if(noProgress>allowance || !pending && pawn.CurJob!=move)return false;
            var goal=move.targetA.Cell;
            if(!goal.InBounds(pawn.Map) || !goal.Standable(pawn.Map) || goal.ContainsStaticFire(pawn.Map)
                || pawn.Position.ContainsStaticFire(pawn.Map)
                || pawn.Map.gasGrid.DensityAt(goal,GasType.ToxGas)>0
                || pawn.Map.gasGrid.DensityAt(goal,GasType.DeadlifeDust)>0)return false;
            if(pawn.Map.mapPawns.AllPawnsSpawned.Any(e=>Threat(e) && MeleeThreat(e)
                && e.Position.InHorDistOf(pawn.Position,2.1f)))return false;
            return pending || pawn.CurJob==move;
        }
        public static void RememberAssembly(Pawn pawn,IntVec3 cell)
        {AssemblyAnchors[pawn]=cell;if(Plans.TryGetValue(pawn.thingIDNumber,out var plan))plan.Anchor=cell;}
        private static bool MovingOrBusy(Pawn pawn)=>pawn.pather.Moving || pawn.stances.FullBodyBusy;
        public static void RememberRegroup(Pawn pawn,Job move)
        {RetreatJobs[pawn]=new CombatJobStamp(RememberMove(pawn,move,null));if(Plans.TryGetValue(pawn.thingIDNumber,out var plan))plan.LastMoveTick=Find.TickManager.TicksGame;}
        private static bool Present(Pawn pawn,Job job) => CombatOrderHelper.Owned(pawn,job)
            && (pawn.CurJob==job || pawn.jobs.jobQueue.Any(q=>q.job==job));
        public static bool CellClaimed(Pawn pawn,IntVec3 cell) => pawn.Map.mapPawns.FreeColonistsSpawned.ToArray()
            .Any(p=>p!=pawn && p.Drafted && !p.Dead && !p.Downed
                && (p.CurJobDef==JobDefOf.Goto && p.CurJob.targetA.Cell==cell
                    || p.jobs.jobQueue.Any(q=>q.job.def==JobDefOf.Goto && q.job.targetA.Cell==cell)));
        private static bool StuckAtContact(Plan plan) => !(plan.Pawn.stances?.curStance is Stance_Cooldown)
            && Find.TickManager.TicksGame-Math.Max(plan.ProgressTick,plan.LastMoveTick)>=60
            && plan.Pawn.Map.mapPawns.AllPawnsSpawned.Any(e=>Threat(e) && MeleeThreat(e)
                && e.Position.InHorDistOf(plan.Pawn.Position,2.1f));
        public static string CurrentPlan(Pawn pawn) => Plans.TryGetValue(pawn.thingIDNumber,out var p) && Valid(p) ? p.Tactic : null;
        public static IntVec3 DefensiveAnchor(Pawn pawn) => Plans.TryGetValue(pawn.thingIDNumber,out var p) && Valid(p) ? p.Anchor : pawn.Position;
        public static bool PreserveEscape(Pawn pawn,string nextTactic)
        {
            if(!RangedPlans.Contains(nextTactic) || !Plans.TryGetValue(pawn.thingIDNumber,out var plan) || !Valid(plan))return false;
            if(KeepDoctorDetour(pawn))return true;
            if(KeepCohortIntent(pawn,nextTactic))return true;
            if(KeepObservedRangePost(pawn,nextTactic))return true;
            if(PendingOwnedRangedMove(plan))return true;
            if(HoldingBreach(plan,nextTactic))return true;
            if(HoldingRecovery(plan,nextTactic))return true;
            if((plan.Mode=="support" || plan.Mode=="intercept" || plan.Mode=="assembly" || plan.Mode=="cover") && pawn.Map.mapPawns.AllPawnsSpawned.Any(e=>Threat(e) && MeleeThreat(e)
                && CombatInterceptHelper.Pursuing(e,pawn) && e.Position.DistanceTo(pawn.Position)<6f))return false;
            if(plan.Mode=="intercept" && !CombatNativeHelper.AbductionThreat(plan.Target))return false;
            if((plan.Mode!="retreat" && plan.Mode!="support" && plan.Mode!="intercept" && plan.Mode!="assembly" && plan.Mode!="cover") || plan.OwnedJob?.def!=JobDefOf.Goto || StuckAtContact(plan))return false;
            bool pending=pawn.jobs.jobQueue.Any(q=>q.job==plan.OwnedJob);
            return pending || pawn.CurJob==plan.OwnedJob && MovingOrBusy(pawn)
                && !plan.OwnedJob.targetA.Cell.ContainsStaticFire(pawn.Map)
                && pawn.Map.gasGrid.DensityAt(plan.OwnedJob.targetA.Cell,GasType.ToxGas)==0
                && pawn.Map.gasGrid.DensityAt(plan.OwnedJob.targetA.Cell,GasType.DeadlifeDust)==0;
        }
        public static bool PreserveShot(Pawn pawn,string nextTactic)
        {
            if(!Eligible(pawn) || !new[]{"hold_cover","firing_line","focus_fire","advance_to_range","stationary_fire","fallback_line","kite","backstep_fire"}.Contains(nextTactic)
                || (pawn.CurJobDef!=JobDefOf.AttackStatic && pawn.CurJobDef!=JobDefOf.Wait_Combat)
                || !(AimTarget(pawn) is Pawn target))return false;
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(nextTactic=="kite" || nextTactic=="backstep_fire")
            {
                if(pawn.health.summaryHealth.SummaryHealthPercent<.85f || pawn.health.hediffSet.BleedRateTotal>0f)return false;
                float contact=pawn.Map.mapPawns.AllPawnsSpawned.Where(t=>Threat(t) && ClosingMelee(t,pawn))
                    .Select(t=>CombatInterceptHelper.ContactTicks(t,pawn)).DefaultIfEmpty(9999f).Min();
                float aim=(pawn.stances.curStance as Stance_Warmup)?.ticksLeft ?? 0f;
                if(verb?.state!=VerbState.Bursting && !CombatInterceptMath.FinishVolley(contact,aim,
                    Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots,
                    pawn.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f,
                    CombatInterceptHelper.MovementLockTicks(pawn),pawn.stances.curStance is Stance_Warmup))return false;
            }
            return (pawn.stances.curStance is Stance_Warmup || verb?.state==VerbState.Bursting)
                && Threat(target) && CombatInterceptHelper.CanShootNow(pawn,target);
        }
        public static bool PreserveContact(Pawn pawn,string nextTactic)
            => RangedPlans.Contains(nextTactic) && nextTactic!="withdraw_and_regroup"
                && Plans.TryGetValue(pawn.thingIDNumber,out var plan) && Valid(plan)
                && pawn.CurJobDef==JobDefOf.AttackMelee && pawn.CurJob==plan.OwnedJob
                && pawn.CurJob.targetA.Thing is Pawn target && Threat(target)
                && CombatInterceptMath.ContactDefence(true,pawn.Position.DistanceTo(target.Position));
        public static Pawn AimTarget(Pawn pawn)
        {
            var verb=pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            var busy=pawn.stances?.curStance as Stance_Busy;
            if(verb!=null && busy?.verb==verb
                && (pawn.stances.curStance is Stance_Warmup || pawn.stances.curStance is Stance_Cooldown || verb.state==VerbState.Bursting))
                return (pawn.stances?.curStance as Stance_Busy)?.focusTarg.Thing as Pawn
                    ?? pawn.CurJob?.targetA.Thing as Pawn;
            return pawn.CurJobDef==JobDefOf.AttackStatic ? pawn.CurJob?.targetA.Thing as Pawn:null;
        }
        private static bool Eligible(Pawn p) => p!=null && p.Spawned && !p.Dead && !p.Downed && p.Drafted && !p.InMentalState
            && !p.WorkTagIsDisabled(WorkTags.Violent) && p.equipment?.Primary?.def.IsRangedWeapon==true
            && !CombatNativeHelper.Protected(p) && !CareTriageHelper.QueuedCare(p);
        private static bool Valid(Plan p) => Eligible(p.Pawn) && Find.Maps.Contains(p.Pawn.Map)
            && Find.TickManager.TicksGame<=p.UntilTick && DateTime.UtcNow<=p.UntilUtc;
        private static bool ReviewCarrierVolley(Plan plan,List<Pawn> threats)
        {
            var pawn=plan.Pawn;var target=AimTarget(pawn) ?? plan.Target;
            if(!Eligible(pawn) || target==null || !Threat(target) || pawn.CurJobDef==JobDefOf.Goto
                || pawn.CurJobDef==JobDefOf.AttackMelee || !CombatOrderHelper.Owned(pawn,pawn.CurJob)
                || pawn.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(pawn,q.job)))return false;
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            if(verb.state==VerbState.Bursting || threats.Any(t=>MeleeThreat(t) && CombatInterceptHelper.Pursuing(t,pawn)
                && CombatInterceptHelper.ContactTicks(t,pawn)<=120f))return false;
            if(!CombatCarrierVolleyHelper.ShouldHold(pawn,target,out var reason,out var pending,out var leader))return false;
            if(plan.Mode=="carrier_volley_wait" && pawn.CurJob==plan.OwnedJob)return true;
            pawn.stances.CancelBusyStanceSoft();
            if(pawn.CurJobDef==JobDefOf.AttackStatic)
            {CombatOrderHelper.DropQueued(pawn);pawn.jobs.EndCurrentJob(JobCondition.InterruptForced,false);}
            var wait=JobMaker.MakeJob(JobDefOf.Wait,75);wait.playerForced=true;wait.canUseRangedWeapon=false;
            if(!CombatOrderHelper.Take(pawn,ref wait))return false;
            plan.OwnedJob=wait;plan.QueuedShot=null;plan.Target=target;plan.Mode="carrier_volley_wait";
#if LAYA_COMBAT_LAB
            CombatCarrierVolleyHelper.Record(pawn,target,reason,pending,leader);
#endif
            return true;
        }
        private static bool TryShortFriendlyAngle(Plan plan,Pawn target,List<Pawn> threats)
        {
            var pawn=plan.Pawn;var map=pawn.Map;
            if(!Eligible(pawn) || !CombatOrderHelper.Owned(pawn,pawn.CurJob)
                || Find.TickManager.TicksGame<plan.FriendlyLaneReviewTick || OtherSelectedGunMoving(pawn)
                || pawn.health.summaryHealth.SummaryHealthPercent<.85f || pawn.health.hediffSet.BleedRateTotal>.1f
                || pawn.health.capacities.GetLevel(PawnCapacityDefOf.Moving)<.85f
                || pawn.health.capacities.GetLevel(PawnCapacityDefOf.Consciousness)<.85f
                || pawn.health.capacities.GetLevel(PawnCapacityDefOf.Manipulation)<.75f
                || threats.Any(t=>t.equipment?.Primary?.def.IsRangedWeapon!=true)
                || !(ObservedVictim(target) is Pawn victim) || victim==pawn || victim.Downed)return false;
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            if(pawn.stances.curStance is Stance_Warmup || verb.state==VerbState.Bursting
                || verb.verbProps.defaultProjectile?.projectile?.explosionRadius>0f
                || verb.verbProps.defaultProjectile?.projectile?.damageDef==DamageDefOf.Flame)return false;
            plan.FriendlyLaneReviewTick=Find.TickManager.TicksGame+60;
            float exposure=IncomingRangedExposure(pawn,pawn.Position);
            var cells=GenRadial.RadialCellsAround(pawn.Position,3f,false).Where(c=>c.InBounds(map) && c.Standable(map)
                && !c.Fogged(map) && !CellClaimed(pawn,c) && !c.GetThingList(map).Any(t=>t is Pawn)
                && threats.All(t=>c.DistanceTo(t.Position)>=8f)
                && verb.CanHitTargetFrom(c,target) && CombatInterceptHelper.FriendlyLaneClear(pawn,target,c)
                && IncomingRangedExposure(pawn,c)<=exposure+.05f)
                .OrderBy(c=>c.DistanceToSquared(pawn.Position)).ThenBy(c=>IncomingRangedExposure(pawn,c)).Take(4);
            foreach(var cell in cells)
            {
                CombatPathBudgetHelper.Checkpoint();
                using(var path=CombatPathBudgetHelper.Query(pawn,pawn.Position,cell,PathEndMode.OnCell))
                    if(path.TotalCost>60f || !CombatInterceptHelper.MovementSafe(pawn,path)
                        || !CoverShotWindow(pawn,target,cell,path.TotalCost))continue;
                var move=JobMaker.MakeJob(JobDefOf.Goto,cell);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                if(!CombatOrderHelper.Take(pawn,ref move))continue;
                var shot=CombatOrderHelper.QueueShot(pawn,target);
                if(shot==null)return false;
                move=RememberMove(pawn,move,shot);plan.OwnedJob=move;plan.QueuedShot=shot;plan.Target=target;plan.Mode="position";
                plan.LastMoveTick=Find.TickManager.TicksGame;
#if LAYA_COMBAT_LAB
                if(SupportWindowReviews.Count<128)SupportWindowReviews.Add(new{tick=Find.TickManager.TicksGame,
                    reason="short_friendly_angle",pawn=pawn.thingIDNumber,target=target.thingIDNumber,victim=victim.thingIDNumber,
                    x=pawn.Position.x,z=pawn.Position.z,goal_x=cell.x,goal_z=cell.z,
                    meaning="Ordinary checked short move and selected-target queue; not arrival, shot or damage."});
#endif
                return true;
            }
            return false;
        }
        private static bool ReviewUnsafeFriendlyLane(Plan plan,List<Pawn> threats)
        {
            var pawn=plan.Pawn;var target=AimTarget(pawn) ?? plan.Target;
            if(target==null || !Threat(target) || pawn.CurJobDef==JobDefOf.Goto || pawn.CurJobDef==JobDefOf.AttackMelee)return false;
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            if(!verb.CanHitTargetFrom(pawn.Position,target) || CombatInterceptHelper.FriendlyLaneClear(pawn,target,pawn.Position))return false;
            if(plan.Mode=="friendly_lane_wait" && Find.TickManager.TicksGame<plan.FriendlyLaneReviewTick)return true;
            if(TryShortFriendlyAngle(plan,target,threats))return true;
            // A different safe enemy can be selected by the ordinary focus
            // logic. Otherwise open a checked angle instead of leaving a
            // native AttackStatic/Wait_Combat shooting through the ally.
            if(threats.Any(t=>CombatInterceptHelper.CanShootNow(pawn,t)))return false;
            // A pinned ally can have a checked short supporting window even
            // when a generic future-target approach has no route forecast.
            // Use the existing full contact/care/path guards before waiting.
            if(TryContactSupport(plan,threats))return true;
            plan.FriendlyLaneReviewTick=Find.TickManager.TicksGame+60;
            if(CombatInterceptHelper.TryPosition(pawn,target,out var cell) && cell!=pawn.Position)
            {
                var move=JobMaker.MakeJob(JobDefOf.Goto,cell);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                if(CombatOrderHelper.Take(pawn,ref move))
                {
                    var shot=CombatOrderHelper.QueueShot(pawn,target);
                    if(shot!=null){RememberMove(pawn,move,shot);plan.OwnedJob=move;plan.QueuedShot=shot;plan.Mode="position";return true;}
                }
            }
            var wait=JobMaker.MakeJob(JobDefOf.Wait,75);wait.playerForced=true;wait.canUseRangedWeapon=false;
            if(CombatOrderHelper.Take(pawn,ref wait)){plan.OwnedJob=wait;plan.QueuedShot=null;plan.Mode="friendly_lane_wait";return true;}
            return false;
        }
        public static void Remember(CombatTacticRequestDto request,CombatTacticResponseDto result,Map map,bool observedOnly=false)
        {
            if(request.Tactic=="stand_down") {foreach(Pawn p in map.mapPawns.FreeColonistsSpawned.Where(p=>!p.Drafted))Plans.Remove(p.thingIDNumber);return;}
            if(!RangedPlans.Contains(request.Tactic) || (!result.Applied && !result.PreservedPawnIds.Any()))return;
            foreach(Pawn p in map.mapPawns.FreeColonistsSpawned.Where(p=>request.FighterIds.Contains(p.thingIDNumber) && Eligible(p)))
            {
                if(!observedOnly)CombatPathBudgetHelper.Checkpoint();
                bool preserved=result.PreservedPawnIds.Contains(p.thingIDNumber);
                if(!preserved && !result.AttackingPawnIds.Contains(p.thingIDNumber)
                    && !result.PositionedPawnIds.Contains(p.thingIDNumber))continue;
                if(Plans.TryGetValue(p.thingIDNumber,out var held) && Valid(held)
                    && preserved && (Present(p,held.OwnedJob) || observedOnly || HoldingBreach(held,request.Tactic)))
                {
                    // A preserved shot/escape did not execute the newly requested
                    // tactic. Renew its existing role without changing that role.
                    held.UntilTick=Find.TickManager.TicksGame+1200;held.UntilUtc=DateTime.UtcNow.AddSeconds(30);
                    continue;
                }
                if(!Plans.TryGetValue(p.thingIDNumber,out var plan) || !Valid(plan))
                    plan=new Plan{Pawn=p,Anchor=AssemblyAnchors.TryGetValue(p,out var assemblyAnchor)?assemblyAnchor:p.Position,Tactic=request.Tactic,ProgressCell=p.Position,ProgressTick=Find.TickManager.TicksGame};
                // Repeating a defensive order must not move its anchor forward.
                if(plan.Tactic!=request.Tactic && request.Tactic=="preemptive_strike")plan.Anchor=p.Position;
                plan.Tactic=request.Tactic;
                if(!result.PreservedPawnIds.Contains(p.thingIDNumber) || !Present(p,plan.OwnedJob))
                {
                    plan.OwnedJob=p.CurJob;plan.QueuedShot=null;plan.Mode="shoot";
                    plan.Target=map.mapPawns.AllPawnsSpawned.FirstOrDefault(t=>t.thingIDNumber==result.TargetPawnId);
                    if(SelectedMoves.TryGetValue(p,out var selected) && Present(p,selected.Key))
                    {
                        plan.OwnedJob=selected.Key;plan.QueuedShot=selected.Value;
                        plan.Target=selected.Value?.targetA.Thing as Pawn ?? plan.Target;
                        plan.Mode=AssemblyAnchors.TryGetValue(p,out var rally) && rally==selected.Key.targetA.Cell?"assembly"
                            :RetreatJobs.TryGetValue(p,out var retreat) && retreat.Value==selected.Key ? "retreat":"position";
                    }
                    else
                    {
                        var shot=p.jobs.jobQueue.Select(q=>q.job).LastOrDefault(j=>j.def==JobDefOf.AttackStatic
                            && j.targetA.Thing==plan.Target);
                        if(shot!=null)plan.OwnedJob=shot;
                        else if(AimTarget(p) is Pawn actual)plan.Target=actual;
                    }
                }
                plan.UntilTick=Find.TickManager.TicksGame+1200;plan.UntilUtc=DateTime.UtcNow.AddSeconds(30);
                Plans[p.thingIDNumber]=plan;
#if LAYA_COMBAT_LAB
                Remembered++;
#endif
            }
        }
        public static CombatTacticResponseDto Refresh(Map map,List<int> ids)
        {
            var result=new CombatTacticResponseDto{Tactic="refresh_control"};
            result.RefreshedControlPawnIds=RetainControlLeases(map,ids);
            result.UnrefreshedControlPawnIds=(ids ?? new List<int>()).Distinct().Except(result.RefreshedControlPawnIds).ToList();
            if(result.RefreshedControlPawnIds.Any())result.Notes.Add("Existing live selected roles renewed; no pawn order or geometry review performed.");
            return result;
        }
        private static bool Threat(Pawn p) => p.Spawned && !p.Dead && !p.Downed && !p.Position.Fogged(p.Map) && CombatNativeHelper.IsPlayerThreat(p);
        private static float Speed(Pawn p) => 60f/Math.Max(1f,p.TicksPerMoveCardinal);
        private static bool MeleeThreat(Pawn p)=>p.equipment?.Primary?.def.IsRangedWeapon!=true || p.CurJobDef==JobDefOf.AttackMelee;
        private static bool ClosingMelee(Pawn enemy,Pawn pawn)
        {
            if(!MeleeThreat(enemy))return false;
            float distance=enemy.Position.DistanceTo(pawn.Position);
            if(CombatInterceptHelper.Pursuing(enemy,pawn) || distance<3f)return true;
            if(distance>=16f || enemy.CurJobDef!=JobDefOf.AttackMelee && enemy.CurJobDef?.defName!="PredatorHunt")return false;
            // A raider approaching another gun or a firing port can switch
            // targets at contact. An intact blocking wall is a different case.
            if(enemy.CurJob?.targetA.Thing is Building wall && wall.def.Fillage==FillCategory.Full
                && !GenSight.LineOfSight(enemy.Position,pawn.Position,pawn.Map)
                && !enemy.CanReach(pawn,PathEndMode.Touch,Danger.Deadly))return false;
            return true;
        }
        private static bool DefensivePlan(string tactic)=>new[]{"hold_cover","firing_line","focus_fire","stationary_fire","fallback_line"}.Contains(tactic);
        public static bool RetainIncomingPost(Pawn pawn,Pawn target)
        {
            if(!Eligible(pawn) || target==null || pawn.CurJobDef==JobDefOf.Goto
                || pawn.health.summaryHealth.SummaryHealthPercent<.85f || pawn.health.hediffSet.BleedRateTotal>0f
                || pawn.health.capacities.GetLevel(PawnCapacityDefOf.Moving)<.85f
                || pawn.Position.ContainsStaticFire(pawn.Map)
                || pawn.Map.gasGrid.DensityAt(pawn.Position,GasType.ToxGas)>0
                || pawn.Map.gasGrid.DensityAt(pawn.Position,GasType.DeadlifeDust)>0)return false;
            var threats=pawn.Map.mapPawns.AllPawnsSpawned.Where(Threat).ToArray();
            if(!threats.Any() || threats.Any(t=>!t.RaceProps.Humanlike || t.equipment?.Primary?.def.IsRangedWeapon==true))return false;
            var guns=pawn.Map.mapPawns.FreeColonistsSpawned.Where(g=>Eligible(g)
                && (g.CurJobDef==JobDefOf.Wait_Combat || g.CurJobDef==JobDefOf.AttackStatic)
                && (g==pawn || VerbUtility.InterceptChanceFactorFromDistance(pawn.Position.ToVector3Shifted(),g.Position)==0f)).ToArray();
            if(guns.Length<3 || !CombatInterceptHelper.IncomingToRange(pawn,target,pawn.Position,out var incoming)
                || !CombatInterceptHelper.FutureFriendlyLaneClear(pawn,target,pawn.Position,incoming,"incoming_prepared_post"))return false;
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            float first=CombatInterceptHelper.MovementLockTicks(pawn)+verb.verbProps.warmupTime*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor)
                +Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots+30f;
            // A real observed route enters this close formation's existing
            // firing lane within180ticks. A distant future endpoint must not
            // send a gun around walls before that earlier stationary volley.
            return threats.All(t=>CombatInterceptHelper.ContactTicks(t,pawn)>first);
        }
        private static bool HoldingRecovery(Plan plan,string tactic) => DefensivePlan(tactic)
            && Find.TickManager.TicksGame<=plan.RecoveryUntilTick && plan.Pawn.Position==plan.RecoveryCell
            && CriticalRangedInjury(plan.Pawn)
            && (plan.Pawn.health.hediffSet.BleedRateTotal>=.25f || plan.Pawn.health.hediffSet.PainTotal>.3f
                || !plan.Pawn.Map.mapPawns.AllPawnsSpawned.Any(t=>Threat(t) && CombatInterceptHelper.CanShootNow(plan.Pawn,t)))
            && !plan.Pawn.Position.ContainsStaticFire(plan.Pawn.Map)
            && plan.Pawn.Map.gasGrid.DensityAt(plan.Pawn.Position,GasType.ToxGas)==0
            && plan.Pawn.Map.gasGrid.DensityAt(plan.Pawn.Position,GasType.DeadlifeDust)==0
            && IncomingRangedExposure(plan.Pawn,plan.Pawn.Position)<=.2f
            && !plan.Pawn.Map.mapPawns.AllPawnsSpawned.Any(e=>Threat(e) && MeleeThreat(e)
                && e.Position.DistanceTo(plan.Pawn.Position)<8f);
        private static bool Bashing(Pawn threat,Building wall)=>Threat(threat) && threat.CurJobDef==JobDefOf.AttackMelee
            && threat.CurJob?.targetA.Thing==wall;
        private static bool HoldingBreach(Plan plan,string nextTactic)
        {
            var wall=plan.WatchedBreach;var pawn=plan.Pawn;
            if(!DefensivePlan(nextTactic) || wall==null || !wall.Spawned || wall.Destroyed
                || !pawn.Map.mapPawns.AllPawnsSpawned.Any(e=>Bashing(e,wall))
                || !plan.BreachPosition.Standable(pawn.Map)
                || plan.BreachPosition.ContainsStaticFire(pawn.Map)
                || pawn.Map.gasGrid.DensityAt(plan.BreachPosition,GasType.ToxGas)>0
                || pawn.Map.gasGrid.DensityAt(plan.BreachPosition,GasType.DeadlifeDust)>0
                || IncomingRangedExposure(pawn,pawn.Position)>.6f)return false;
            if(pawn.Map.mapPawns.AllPawnsSpawned.Any(e=>Threat(e) && e.Position.DistanceTo(pawn.Position)<6f))return false;
            return pawn.Position==plan.BreachPosition || pawn.CurJob==plan.OwnedJob
                && pawn.CurJobDef==JobDefOf.Goto && pawn.pather.Moving;
        }
        private static bool TryCoverObservedBreach(Plan plan,List<Pawn> threats)
        {
            Pawn pawn=plan.Pawn;
            if(!DefensivePlan(plan.Tactic) || !Eligible(pawn) || IncomingRangedExposure(pawn,pawn.Position)>.6f)return false;
            var attacks=threats.Where(e=>e.CurJobDef==JobDefOf.AttackMelee && e.CurJob?.targetA.Thing is Building b
                && b.Spawned && b.Faction==Faction.OfPlayer && b.def.Fillage==FillCategory.Full
                && (b is Building_Door || b.def.passability==Traversability.Impassable)).ToList();
            if(!attacks.Any())return false;
            var group=attacks.GroupBy(e=>(Building)e.CurJob.targetA.Thing)
                .OrderBy(g=>(float)g.Key.HitPoints/g.Count()).ThenBy(g=>g.Key.thingIDNumber).First();
            var wall=group.Key;var attacker=group.OrderBy(e=>e.thingIDNumber).First();
            int dx=attacker.Position.x-wall.Position.x,dz=attacker.Position.z-wall.Position.z;
            if(dx==0 && dz==0)return false;
            var outside=Math.Abs(dx)>=Math.Abs(dz)?new IntVec3(Math.Sign(dx),0,0):new IntVec3(0,0,Math.Sign(dz));
            var inside=wall.Position-outside;var map=pawn.Map;var room=pawn.GetRoom();
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            // A forecast lane to the INSIDE of an observed wall attack. This
            // neither shoots through the wall nor assumes the attacker will
            // enter it; the real shot is rechecked after an actual opening.
            var cells=GenRadial.RadialCellsAround(inside,13f,true)
                .Where(c=>c.InBounds(map) && c.Standable(map) && !c.Fogged(map) && c.GetRoom(map)==room
                    && c.DistanceTo(wall.Position)>=6f && c.DistanceTo(pawn.Position)<=18f
                    && (c.x-wall.Position.x)*outside.x+(c.z-wall.Position.z)*outside.z<=-2
                    && !CellClaimed(pawn,c) && !c.GetThingList(map).Any(t=>t is Pawn && t!=pawn)
                    && verb?.CanHitTargetFrom(c,new LocalTargetInfo(inside))==true)
                .OrderBy(c=>c.DistanceTo(pawn.Position)+Math.Abs(c.DistanceTo(wall.Position)-9f)*.5f).Take(8);
            foreach(var cell in cells)
            {
                CombatPathBudgetHelper.Checkpoint();
                if(cell==pawn.Position){plan.WatchedBreach=wall;plan.BreachPosition=cell;return true;}
                using(var path=CombatPathBudgetHelper.Query(pawn,pawn.Position,cell,PathEndMode.OnCell))
                    if(path.TotalCost>480f || !CombatInterceptHelper.MovementSafe(pawn,path)
                        || path.NodesReversed.Any(c=>c.GetRoom(map)!=room))continue;
                var move=JobMaker.MakeJob(JobDefOf.Goto,cell);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                if(!CombatOrderHelper.Take(pawn,ref move))continue;
                move=RememberMove(pawn,move,null);plan.OwnedJob=move;plan.QueuedShot=null;plan.Target=attacker;
                plan.WatchedBreach=wall;plan.BreachPosition=cell;plan.Mode="breach";
                return true;
            }
            return false;
        }
        public static float IncomingRangedExposure(Pawn pawn,IntVec3 cell,float horizon=0f)
        {
            CombatPathBudgetHelper.Checkpoint("IncomingRangedExposure");
            // Sum of uncovered native firing lanes, not a probability of injury.
            // A wall facing the selected target does not protect the other flank.
            float total=0;
            foreach(var enemy in pawn.Map.mapPawns.AllPawnsSpawned.Where(e=>Threat(e)
                && e.equipment?.Primary?.def.IsRangedWeapon==true))
            {
                float current=CombatExposureHelper.Lane(enemy,pawn,cell,enemy.Position);
                if(horizon>0)
                {
                    if(!CombatInterceptHelper.TryObservedFuturePosition(enemy,horizon,out var future))return float.PositiveInfinity;
                    current=CombatInterceptMath.ExposureEnvelope(current,CombatExposureHelper.Lane(enemy,pawn,cell,future));
                }
                total+=current;
            }
            return total;
        }
        private static bool TryTakeCoveredShot(Plan plan,Pawn target)
        {
            var pawn=plan.Pawn;
            if(!TryCoveredShot(pawn,target,out var covered))return false;
                    var move=JobMaker.MakeJob(JobDefOf.Goto,covered);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                    if(CombatOrderHelper.Take(pawn,ref move))
                    {
                        var shot=CombatOrderHelper.QueueShot(pawn,target);move=RememberMove(pawn,move,shot);
                        plan.OwnedJob=move;plan.QueuedShot=shot;plan.Target=target;plan.Mode="cover";plan.LastMoveTick=Find.TickManager.TicksGame;plan.CoverTransitReviewTick=0;plan.CoverTransitUseful=true;
#if LAYA_COMBAT_LAB
                        if(CoverTransits.Count<128)CoverTransits.Add(new{tick=Find.TickManager.TicksGame,pawn=pawn.thingIDNumber,
                            target=target.thingIDNumber,job_id=move.loadID,x=pawn.Position.x,z=pawn.Position.z,
                            goal_x=covered.x,goal_z=covered.z,queued_shot=shot?.targetA.Thing?.thingIDNumber,
                            interpretation="Accepted native move to forecast cover; not arrival, damage avoidance or a shot"});
#endif
                        return true;
                    }
            return false;
        }
        public static bool TryCoveredShot(Pawn pawn,Pawn target,out IntVec3 cell)
        {
            cell=IntVec3.Invalid;if(!Eligible(pawn) || target==null)return false;
            var map=pawn.Map;var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(pawn.stances.curStance is Stance_Warmup || verb?.state==VerbState.Bursting)return false;
            float cycle=(verb?.verbProps.warmupTime ?? 0)*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor)
                +Math.Max(0,(verb?.verbProps.burstShotCount ?? 1)-1)*(verb?.verbProps.ticksBetweenBurstShots ?? 0)
                +pawn.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f+30f;
            float current=IncomingRangedExposure(pawn,pawn.Position,cycle);
            if(float.IsInfinity(current))
            {
#if LAYA_COMBAT_LAB
                CoverForecastUnknown++;
#endif
                return false;
            }
            if(current<.35f)return false;
            bool firingNow=map.mapPawns.AllPawnsSpawned.Any(e=>Threat(e) && CombatInterceptHelper.CanShootNow(pawn,e));
            bool wounded=CriticalRangedInjury(pawn);
            bool otherMoving=!AllowsRangedMedicalRotation(pawn,target);
            if(!CombatInterceptMath.CoverRotation(wounded,firingNow,otherMoving,0))return false;
            var enemies=map.mapPawns.AllPawnsSpawned.Where(Threat).ToArray();
            var ranged=enemies.Where(e=>e.equipment?.Primary?.def.IsRangedWeapon==true)
                .Select(e=>new{Pawn=e,Range=e.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb?.verbProps.range ?? 0}).ToArray();
            var pool=GenRadial.RadialCellsAround(pawn.Position,!wounded && firingNow?4f:ranged.Length>=2?18f:4f,false)
                .Where(c=>c.InBounds(map) && c.Standable(map) && !c.Fogged(map)
                && !c.GetThingList(map).Any(t=>t is Pawn) && !CellClaimed(pawn,c) && c.DistanceTo(DefensiveAnchor(pawn))<=26f
                && enemies.All(e=>c.DistanceTo(e.Position)>=12f)).ToArray();
            // Cheap range geometry bounds expensive native firing-lane reads.
            // Keep nearby hard-cover candidates as well as range-break cells.
            var shortlist=pool.Where(c=>c.DistanceTo(pawn.Position)<=4f).Take(48)
                .Concat(pool.OrderBy(c=>ranged.Count(e=>c.InHorDistOf(e.Pawn.Position,e.Range+1f))*100f+c.DistanceTo(pawn.Position)).Take(24)).Distinct();
            var cells=shortlist.Where(c=>
                (verb?.CanHitTargetFrom(c,target)==true || !firingNow
                    && CombatInterceptHelper.IncomingToRange(pawn,target,c,out var expected) && c.DistanceTo(expected)>=12f)
                && CombatInterceptHelper.FriendlyLaneClear(pawn,target,c)
                && enemies.All(e=>c.DistanceTo(e.Position)>=12f))
                .Select(c=>new {Cell=c,Exposure=IncomingRangedExposure(pawn,c)})
                .Where(c=>CombatInterceptMath.CoverImproves(current,c.Exposure)).OrderBy(c=>c.Exposure+c.Cell.DistanceTo(pawn.Position)*.025f).Take(8);
            float best=float.PositiveInfinity;
            foreach(var candidate in cells)
                using(var path=CombatPathBudgetHelper.Query(pawn,pawn.Position,candidate.Cell,PathEndMode.OnCell))
                    if(path.TotalCost<=480f && CombatInterceptMath.CoverRotation(wounded,firingNow,otherMoving,path.TotalCost)
                        && CombatInterceptHelper.MovementSafe(pawn,path))
                    {
                        float horizon=CombatInterceptHelper.MovementLockTicks(pawn)+path.TotalCost+cycle;
                        float projected=IncomingRangedExposure(pawn,candidate.Cell,horizon);
                        float staying=IncomingRangedExposure(pawn,pawn.Position,horizon);
                        bool improves=CombatInterceptMath.CoverImproves(staying,projected);
                        bool shotWindow=wounded || CoverShotWindow(pawn,target,candidate.Cell,path.TotalCost);
#if LAYA_COMBAT_LAB
                        if(!improves || !shotWindow)CoverForecastRejected++;
                        if(CoverForecastChecks.Count<128)CoverForecastChecks.Add(new{tick=Find.TickManager.TicksGame,pawn=pawn.thingIDNumber,
                            x=candidate.Cell.x,z=candidate.Cell.z,path_cost=path.TotalCost,horizon,
                            current_exposure=candidate.Exposure,projected_exposure=float.IsInfinity(projected)?(float?)null:projected,
                            staying_exposure=float.IsInfinity(staying)?(float?)null:staying,
                            forecast_available=!float.IsInfinity(projected) && !float.IsInfinity(staying),
                            improves,selected_shot_window=shotWindow,wounded_escape=wounded,
                            interpretation="Candidate protection and selected-target firing-window check, not arrival or a projectile"});
#endif
                        if(!improves || !shotWindow)continue;
                        float score=projected+path.TotalCost*.0005f;
                        if(score>=best)continue;
                        best=score;cell=candidate.Cell;
                        if(projected<=.1f)break; // Already a protected forecast; no unbounded search.
                    }
            return cell.IsValid;
        }
        public static bool CheckedDefensivePost(Pawn pawn,Pawn target,IntVec3 cell)
        {
            if(!Eligible(pawn) || target==null || !cell.InBounds(pawn.Map) || !cell.Standable(pawn.Map) || cell.Fogged(pawn.Map))return false;
            using(var path=CombatPathBudgetHelper.Query(pawn,pawn.Position,cell,PathEndMode.OnCell))
                return path.TotalCost<=120f && CombatInterceptHelper.MovementSafe(pawn,path)
                    && CoverShotWindow(pawn,target,cell,path.TotalCost);
        }
        private static bool CoverShotWindow(Pawn pawn,Pawn target,IntVec3 cell,float travel)
        {
            var verb=pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(verb==null || target==null || !target.Spawned || target.Map!=pawn.Map
                || float.IsNaN(travel) || float.IsInfinity(travel) || travel<0f)return false;
            float arrival=CombatInterceptHelper.MovementLockTicks(pawn)+travel;
            float aim=verb.verbProps.warmupTime*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor);
            float burst=Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots;
            // The previous weapon cooldown can delay even a one-cell move.
            // Keep the exact queued Pawn target through arrival and the first
            // burst, with one control interval for ordinary job transitions.
            // A target losing LOS after an already launched bullet is not a
            // reason to discard a useful cover move: flight is not warmup.
            foreach(float horizon in new[]{arrival,arrival+aim,arrival+aim+burst+15f})
            {
                CombatPathBudgetHelper.Checkpoint();
                if(!CombatInterceptHelper.TryObservedFuturePosition(target,horizon,out var future)
                    || CombatExposureHelper.CanHitPawnAt(verb,target,cell,future)!=true
                    || !CombatInterceptHelper.FutureFriendlyLaneClear(pawn,target,cell,future,"covered_first_burst"))return false;
            }
            return true;
        }
        private static IEnumerable<Pawn> SelectedMovingGuns(Pawn pawn)
            => pawn.Map.mapPawns.FreeColonistsSpawned.Where(p=>p!=pawn && !p.Dead && !p.Downed && p.Drafted
                && p.equipment?.Primary?.def.IsRangedWeapon==true
                && (Plans.TryGetValue(p.thingIDNumber,out var plan) && Valid(plan)
                        && plan.OwnedJob?.def==JobDefOf.Goto && Present(p,plan.OwnedJob)
                        && (plan.OwnedJob!=p.CurJob || MovingOrBusy(p) || p.Position!=plan.OwnedJob.targetA.Cell)
                    || SelectedMoves.TryGetValue(p,out var move) && move.Key?.def==JobDefOf.Goto && Present(p,move.Key)
                        && (move.Key!=p.CurJob || MovingOrBusy(p) || p.Position!=move.Key.targetA.Cell)));
        private static bool OtherSelectedGunMoving(Pawn pawn)=>SelectedMovingGuns(pawn).Any();
        public static Pawn ObservedVictim(Pawn threat)
        {
            if(new[]{"AttackMelee","AttackStatic","PredatorHunt"}.Contains(threat.CurJobDef?.defName)
                && threat.CurJob.targetA.Thing is Pawn actual && actual.Faction==Faction.OfPlayer && !actual.Dead)return actual;
            var busy=threat.stances?.curStance as Stance_Busy;
            var verb=threat.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            // The native cooldown retains the last shot's actual focus. An
            // unrelated medical or ability stance is not a gun attack.
            return verb!=null && busy?.verb==verb && busy.focusTarg.Thing is Pawn shot
                && shot.Faction==Faction.OfPlayer && !shot.Dead ? shot:null;
        }
        private static bool MedicalReady(Pawn p)=>p.RaceProps.Humanlike && p.Spawned && !p.Dead && !p.Downed && !p.InMentalState
            && !p.WorkTypeIsDisabled(WorkTypeDefOf.Doctor)
            && p.health.capacities.GetLevel(PawnCapacityDefOf.Consciousness)>.1f
            && p.health.capacities.GetLevel(PawnCapacityDefOf.Moving)>.1f
            && p.health.capacities.GetLevel(PawnCapacityDefOf.Manipulation)>.1f;
        private static float ThreatUrgency(Pawn threat,Pawn[] guns,Dictionary<Pawn,int> attackerCounts=null,int? readyMedicCount=null)
        {
            if(!guns.Any())return 0f;
            var victim=ObservedVictim(threat);
            // An observed pursuer's current route is toward its actual victim.
            // Another nearby gun is not that victim, especially while a bait
            // pawn is already moving away under an existing escape plan.
            float contact=MeleeThreat(threat)?victim!=null?CombatInterceptHelper.ContactTicks(threat,victim)
                :guns.Min(g=>CombatInterceptHelper.ContactTicks(threat,g)):9999f;
            int attackers=victim==null?0:attackerCounts!=null && attackerCounts.TryGetValue(victim,out var count)?count
                :threat.Map.mapPawns.AllPawnsSpawned.Count(t=>Threat(t) && ObservedVictim(t)==victim);
            float pressure=victim?.Faction==Faction.OfPlayer?CombatInterceptMath.VictimPressure(victim.health.summaryHealth.SummaryHealthPercent,
                victim.health.capacities.GetLevel(PawnCapacityDefOf.Moving),victim.health.hediffSet.BleedRateTotal,attackers):0f;
            if(victim?.Faction==Faction.OfPlayer && MedicalReady(victim))
                pressure+=CombatInterceptMath.MedicPressure(true,true,
                    readyMedicCount ?? threat.Map.mapPawns.FreeColonistsSpawned.Count(MedicalReady));
            // A flanker with an open loaded firing lane can be more dangerous
            // than a wounded rifle behind the front cover. Count actual native
            // hit/cover factors across our selected guns; this is expected
            // exposure, not a guaranteed hit, damage or suppression effect.
            float ranged=threat.equipment?.Primary?.def.IsRangedWeapon==true
                ?ObservedRangedPressure(threat,guns)*60f:0f;
            return CombatInterceptMath.MeleePriority(contact)+pressure+ranged;
        }
        private static float ObservedRangedPressure(Pawn threat,Pawn[] guns)
        {
            var live=guns.Where(g=>g.Spawned && !g.Dead && !g.Downed).ToArray();
            float current=live.Sum(g=>ShotQuality(threat,g,threat.Position)),projected=0f;
            const float horizon=180f;
            bool available=CombatInterceptHelper.TryObservedFuturePosition(threat,horizon,out var from);
            var verb=threat.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(verb==null)available=false;
            if(available)
                foreach(var gun in live.Take(12))
                {
                CombatPathBudgetHelper.Checkpoint();
                    if(!CombatInterceptHelper.TryObservedFuturePosition(gun,horizon,out var target))
                    {available=false;break;}
                    float lane=CombatExposureHelper.Lane(threat,gun,target,from);
                    if(float.IsNaN(lane) || float.IsInfinity(lane)){available=false;break;}
                    float distance=from.DistanceTo(target);
                    projected+=lane*ShotReport.HitFactorFromShooter(threat,distance)
                        *verb.verbProps.GetHitChanceFactor(threat.equipment.Primary,distance);
                }
            // A forecast can raise observed urgency, never erase a current
            // firing threat. Only the already observed routes are advanced;
            // no later enemy turn or job is invented or forced.
            float result=CombatInterceptMath.ForecastRangedPressure(current,projected,available);
#if LAYA_COMBAT_LAB
            int tick=Find.TickManager.TicksGame;
            if(RangedThreatForecasts.Count<128 && (!LastRangedThreatForecast.TryGetValue(threat.thingIDNumber,out var last) || tick-last>=60))
            {
                LastRangedThreatForecast[threat.thingIDNumber]=tick;
                RangedThreatForecasts.Add(new{tick,enemy=threat.thingIDNumber,current,projected=available?(float?)projected:null,
                    future_x=available?(int?)from.x:null,future_z=available?(int?)from.z:null,horizon,
                    forecast_available=available,forecast_guns=Math.Min(12,live.Length),total_guns=live.Length,selected_pressure=result,used_by_production=true,
                    checked_firing_lanes=live.Where(g=>CombatInterceptHelper.CanShootNow(g,threat)).Select(g=>g.thingIDNumber).ToArray(),
                    aiming_guns=live.Where(g=>AimTarget(g)==threat).Select(g=>g.thingIDNumber).ToArray(),
                    interpretation="Target-priority forecast over observed routes, not a shot, hit or suppressed attacker"});
            }
#endif
            return result;
        }
        public static float ShotQuality(Pawn pawn,Pawn target,IntVec3 cell)
        {
            var verb=pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(verb==null || !verb.CanHitTargetFrom(cell,target))return 0f;
            float distance=cell.DistanceTo(target.Position);
            // Loaded native factors, not a guaranteed hit or armor penetration.
            return ShotReport.HitFactorFromShooter(pawn,distance)*verb.verbProps.GetHitChanceFactor(pawn.equipment.Primary,distance)
                *(1f-CoverUtility.CalculateOverallBlockChance(target,cell,pawn.Map));
        }
        public static Pawn DefensiveTarget(Pawn pawn,Pawn fallback)
        {
            if(fallback!=null && CombatNativeHelper.AbductionThreat(fallback))return fallback;
            // Share a volley only while its loaded commitment still fits
            // before the gun's own observed pursuer can make contact.
            var own=pawn.Map.mapPawns.AllPawnsSpawned.Where(t=>Threat(t) && CombatInterceptHelper.Pursuing(t,pawn)
                    && CombatInterceptHelper.CanShootNow(pawn,t))
                .OrderBy(t=>CombatInterceptHelper.ContactTicks(t,pawn)).ThenBy(t=>t.health.summaryHealth.SummaryHealthPercent)
                .FirstOrDefault();
            if(own==null)return fallback;
            if(fallback!=null && fallback!=own && MeleeThreat(fallback) && ObservedVictim(fallback) is Pawn other && other!=pawn
                && pawn.health.summaryHealth.SummaryHealthPercent>=.85f && pawn.health.hediffSet.BleedRateTotal==0f
                && pawn.health.capacities.GetLevel(PawnCapacityDefOf.Moving)>=.85f && CombatInterceptHelper.CanShootNow(pawn,fallback))
            {
                var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
                float aim=(pawn.stances.curStance as Stance_Warmup)?.ticksLeft
                    ?? (verb?.verbProps.warmupTime ?? 0)*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor);
                // Choose the squad's endangered target while this gun can
                // still cover it. Whether to stay for an entire cooldown or
                // leave under that cover is checked separately by the plan.
                if(CombatInterceptMath.SupportVolley(CombatInterceptHelper.ContactTicks(own,pawn),aim,
                    Math.Max(0,(verb?.verbProps.burstShotCount ?? 1)-1)*(verb?.verbProps.ticksBetweenBurstShots ?? 0),
                    CombatInterceptHelper.MovementLockTicks(pawn),pawn.stances.curStance is Stance_Warmup))return fallback;
            }
            return own;
        }
        public static Pawn AvailableFiringTarget(Pawn pawn,Pawn requested)
        {
            if(requested!=null && CombatInterceptHelper.CanShootNow(pawn,requested))return DefensiveTarget(pawn,requested);
            // A defensive order for an obscured target must not discard an
            // actual shot at another observed attacker in the same fight.
            return GroupTarget(pawn,pawn.Map.mapPawns.AllPawnsSpawned.Where(Threat).ToList()) ?? requested;
        }
        private static bool EarlierPursuitOpportunity(Pawn pawn,Pawn earlier,Pawn committed)
        {
            if(!Eligible(pawn) || earlier==null || committed==null || earlier==committed
                || !CombatOrderHelper.Owned(pawn,pawn.CurJob)
                || pawn.CurJobDef!=JobDefOf.AttackStatic && pawn.CurJobDef!=JobDefOf.Wait_Combat
                || pawn.stances.curStance is Stance_Warmup
                || !MeleeThreat(earlier) || !MeleeThreat(committed)
                || !earlier.RaceProps.Humanlike || CombatNativeHelper.AbductionThreat(committed)
                || !(ObservedVictim(earlier) is Pawn victim) || victim.Downed || !victim.Spawned
                || !(ObservedVictim(committed) is Pawn oldVictim) || oldVictim.Downed || !oldVictim.Spawned
                || !CombatInterceptHelper.Pursuing(earlier,victim)
                || !CombatInterceptHelper.Pursuing(committed,oldVictim)
                || !CombatInterceptHelper.CanShootNow(pawn,earlier))return false;
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(verb==null || verb.state==VerbState.Bursting || verb.verbProps.defaultProjectile?.projectile==null)return false;
            // Existing aim/bursts remain commitments. An idle/cooling gun can
            // use its last complete new burst against an earlier real pursuer
            // before spending an additional full cycle on the old group focus.
            float aim=verb.verbProps.warmupTime*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor);
            float burst=Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots;
            float flight=CombatInterceptMath.NativeFlightTicks(pawn.Position.DistanceTo(earlier.Position),
                verb.verbProps.defaultProjectile.projectile.SpeedTilesPerTick);
            return CombatInterceptMath.FocusDeadline(CombatInterceptHelper.ContactTicks(earlier,victim),
                CombatInterceptHelper.ContactTicks(committed,oldVictim),CombatInterceptHelper.MovementLockTicks(pawn),
                aim,burst,pawn.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f,flight);
        }
        private static Pawn GroupTarget(Pawn pawn,List<Pawn> threats,Pawn selected=null)
        {
            var guns=Plans.Values.Where(Valid).Select(p=>p.Pawn).Where(p=>p.Map==pawn.Map).ToArray();
            if(!threats.Any(CombatNativeHelper.AbductionThreat))
            {
                var bait=Plans.Values.Where(Valid).FirstOrDefault(p=>p.Pawn.Map==pawn.Map
                    && p.FastBait?.Value==p.Pawn.CurJob && p.Pawn.CurJobDef==JobDefOf.Goto && MovingOrBusy(p.Pawn)
                    && p.FastBaitCover.Contains(pawn.thingIDNumber) && Threat(p.Target)
                    && CombatInterceptHelper.Pursuing(p.Target,p.Pawn) && CombatInterceptHelper.CanShootNow(pawn,p.Target));
                if(bait!=null)return DefensiveTarget(pawn,bait.Target);
            }
            var coordinated=CoordinatedTarget(pawn,threats);
            if(coordinated!=null)return coordinated;
            var attackerCounts=threats.Select(ObservedVictim).Where(p=>p!=null).GroupBy(p=>p).ToDictionary(g=>g.Key,g=>g.Count());
            int medics=pawn.Map.mapPawns.FreeColonistsSpawned.Count(MedicalReady);
            Func<Pawn,float> score=t=>CombatNativeHelper.AbductionThreat(t)?10000f:
                guns.Where(g=>g.CurJobDef!=JobDefOf.Goto && g.CurJobDef!=JobDefOf.AttackMelee && CombatInterceptHelper.CanShootNow(g,t))
                    .Sum(g=>ShotQuality(g,t,g.Position))*16f*CombatInterceptMath.TargetVulnerability(
                        t.health.summaryHealth.SummaryHealthPercent,t.GetStatValue(StatDefOf.IncomingDamageFactor),t.BodySize)
                    +(guns.Any(g=>CombatInterceptHelper.Pursuing(t,g))?20f:0f)+ThreatUrgency(t,guns,attackerCounts,medics);
            var best=threats.Where(t=>CombatInterceptHelper.CanShootNow(pawn,t))
                .OrderByDescending(score)
                .ThenBy(t=>t.thingIDNumber).FirstOrDefault();
#if LAYA_COMBAT_LAB
            var rawBest=best;
#endif
            // A group already aiming/firing at the same observed attacker
            // should finish that commitment instead of splitting after each
            // small ranking change. A queued order is not actual gun focus.
            // A weapon cooldown alone recovers a past shot. It must not
            // reserve the group's next target; real aim/bursts still do.
            // Selecting a different job never shortens that native cooldown.
            var focusCounts=guns.Where(g=>g.CurJobDef==JobDefOf.AttackStatic || g.CurJobDef==JobDefOf.Wait_Combat)
                .Where(g=>(g.stances.curStance is Stance_Warmup
                    || g.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb?.state==VerbState.Bursting)
                    && (g.stances.curStance as Stance_Busy)?.verb==g.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb)
                .Select(AimTarget).Where(t=>t!=null && threats.Contains(t))
                .GroupBy(t=>t).ToDictionary(group=>group.Key,group=>group.Count());
            var committed=focusCounts.Where(entry=>entry.Value>=2 && CombatInterceptHelper.CanShootNow(pawn,entry.Key))
                .OrderByDescending(entry=>entry.Value).ThenByDescending(entry=>score(entry.Key)).ThenBy(entry=>entry.Key.thingIDNumber)
                .Select(entry=>entry.Key).FirstOrDefault();
            bool deadline=EarlierPursuitOpportunity(pawn,best,committed);
            if(!deadline && committed!=null && best!=null && CombatInterceptMath.KeepCommittedFocus(focusCounts[committed],
                ThreatUrgency(committed,guns,attackerCounts,medics),ThreatUrgency(best,guns,attackerCounts,medics),
                CombatNativeHelper.AbductionThreat(best)))best=committed;
            var personal=DefensiveTarget(pawn,best);
            Pawn chosen=best;
            if(personal!=null && personal!=best)chosen=personal;
            else if(!deadline && selected!=null && threats.Contains(selected) && CombatInterceptHelper.CanShootNow(pawn,selected)
                && !(best!=null && CombatNativeHelper.AbductionThreat(best) && !CombatNativeHelper.AbductionThreat(selected))
                && (best==null || score(best)<=score(selected)+8f))chosen=selected;
#if LAYA_COMBAT_LAB
            RecordGroupFocus(pawn,threats,guns,score,selected,rawBest,committed,best,personal,chosen,deadline);
#endif
            return chosen;
        }
        private static bool TryContactSupport(Plan plan,List<Pawn> threats)
        {
            Pawn pawn=plan.Pawn;Map map=pawn.Map;
            if(plan.Mode=="support" && pawn.CurJob==plan.OwnedJob && (pawn.pather.Moving || PreserveTeamApproach(plan,threats)) && !StuckAtContact(plan))
                return ContinueSupportApproach(plan,threats);
            if(threats.Any(t=>MeleeThreat(t) && CombatInterceptHelper.Pursuing(t,pawn)
                && pawn.Position.DistanceTo(t.Position)<6f))return false;
            if(pawn.health.summaryHealth.SummaryHealthPercent<.85f || pawn.health.hediffSet.BleedRateTotal>.1f
                || pawn.health.capacities.GetLevel(PawnCapacityDefOf.Moving)<.85f)return false;
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(verb==null || pawn.stances.curStance is Stance_Warmup || verb.state==VerbState.Bursting || verb.verbProps.defaultProjectile?.projectile?.explosionRadius>0f
                || verb.verbProps.defaultProjectile?.projectile?.damageDef==DamageDefOf.Flame)return false;
            // Fire already available from here takes priority over an optional
            // forward support angle at another target.
            if(threats.Any(t=>CombatInterceptHelper.CanShootNow(pawn,t)))return false;
            var allies=map.mapPawns.FreeColonistsSpawned.ToArray();
            var ownPursuers=threats.Where(t=>CombatInterceptHelper.Pursuing(t,pawn)).ToArray();
            float cycle=verb.verbProps.warmupTime*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor)
                +Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots
                +pawn.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f;
            var contacts=threats.Where(MeleeThreat).Select(t=>new{Enemy=t,Ally=allies.FirstOrDefault(a=>a!=pawn
                && !a.Dead && CombatInterceptHelper.Pursuing(t,a) && CombatInterceptHelper.ContactTicks(t,a)<=cycle*2f+180f)})
                .Where(x=>x.Ally!=null && !CombatInterceptHelper.CanShootNow(pawn,x.Enemy))
                .OrderBy(x=>pawn.Position.DistanceToSquared(x.Enemy.Position)).Take(2);
            float exposure=IncomingRangedExposure(pawn,pawn.Position);
            bool reservePhysician=NativeDoctor(pawn) && IsReservedDoctor(pawn);
            int contactBudget=16;
            foreach(var contact in contacts)
            {
                CombatPathBudgetHelper.Checkpoint();
                // Seek a short lateral window only when the current lane is
                // blocked. An available covering shot takes priority over a
                // costly advance toward the pinned ally.
                var cells=GenRadial.RadialCellsAround(pawn.Position,8f,false).Where(c=>c.InBounds(map) && c.Standable(map)
                    && !c.Fogged(map) && !CellClaimed(pawn,c) && !c.GetThingList(map).Any(t=>t is Pawn)
                    && (!reservePhysician || !threats.Where(MeleeThreat).Any(t=>c.DistanceTo(t.Position)+1f<pawn.Position.DistanceTo(t.Position)))
                    && c.DistanceTo(contact.Enemy.Position)>=4f && c.DistanceTo(contact.Enemy.Position)<=verb.verbProps.range-1f
                    && c.DistanceTo(contact.Ally.Position)<=Math.Max(5f,Math.Min(12f,verb.verbProps.range*.5f))
                    && threats.All(t=>c.DistanceTo(t.Position)>=3.5f)
                    && verb.CanHitTargetFrom(c,contact.Enemy) && CombatInterceptHelper.FriendlyLaneClear(pawn,contact.Enemy,c)
                    && IncomingRangedExposure(pawn,c)<=Math.Max(.6f,exposure-.1f))
                    .OrderBy(c=>IncomingRangedExposure(pawn,c)*30f+c.DistanceTo(pawn.Position)).Take(8);
                foreach(var cell in cells)
                {
                CombatPathBudgetHelper.Checkpoint();
                    if(PreserveDoctorPosition(pawn,cell))continue;
                    using(var path=CombatPathBudgetHelper.Query(pawn,pawn.Position,cell,PathEndMode.OnCell))
                    {
                        if(path.TotalCost>240f || !CombatInterceptHelper.MovementSafe(pawn,path))continue;
                        if(ownPursuers.Any(t=>CombatInterceptHelper.ContactTicks(t,pawn)
                            <=path.TotalCost+CombatInterceptHelper.MovementLockTicks(pawn)+cycle+90f))continue;
                        if(!SupportShotWindow(pawn,contact.Enemy,cell,path.TotalCost,threats,ref contactBudget,false))continue;
                    }
                    var move=JobMaker.MakeJob(JobDefOf.Goto,cell);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                    if(KeepGroupPosition(pawn,cell) || PreserveTeamMove(pawn,move))continue;
                    pawn.stances.CancelBusyStanceSoft();
                    if(!CombatOrderHelper.Take(pawn,ref move))continue;
                    var shot=CombatOrderHelper.QueueShot(pawn,contact.Enemy);move=RememberMove(pawn,move,shot);
                    RememberSupportApproach(pawn,move,shot,contact.Enemy);
#if LAYA_COMBAT_LAB
                    Supported++;
#endif
                    return true;
                }
            }
            return false;
        }
        private static bool SupportShotWindow(Pawn pawn,Pawn target,IntVec3 goal,float travel,List<Pawn> threats,
            ref int pathBudget,bool continuing)
        {
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(verb==null || target==null || !Threat(target))return false;
            float aim=verb.verbProps.warmupTime*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor);
            float burst=Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots;
            float locked=CombatInterceptHelper.MovementLockTicks(pawn);
            float flight=CombatInterceptMath.NativeFlightTicks(goal.DistanceTo(target.Position),
                verb.verbProps.defaultProjectile?.projectile?.SpeedTilesPerTick ?? 0f);
            foreach(var enemy in threats.Where(MeleeThreat).OrderBy(t=>t.Position.DistanceToSquared(goal)))
            {
                CombatPathBudgetHelper.Checkpoint();
                if(pathBudget--<=0)return false; // Unknown contact never authorizes another approach.
                using(var path=CombatPathBudgetHelper.Query(enemy,enemy.Position,goal,PathEndMode.Touch))
                {
                    if(!path.Found)return false;
                    // A potential native retarget bound, not the enemy's
                    // actual order. Faster native urgency must not be hidden.
                    float progress=enemy.pather?.Moving==true?Math.Max(0f,enemy.pather.nextCellCostTotal-enemy.pather.nextCellCostLeft):0f;
                    float contact=Math.Max(0f,path.TotalCost-progress)*(enemy.CurJob?.locomotionUrgency==LocomotionUrgency.Sprint?.75f:1f)
                        +CombatInterceptHelper.MovementLockTicks(enemy);
                    bool fits=CombatInterceptMath.SupportApproachWindow(contact,travel,locked,aim,burst,flight);
#if LAYA_COMBAT_LAB
                    if(SupportWindowReviews.Count<96)SupportWindowReviews.Add(new{tick=Find.TickManager.TicksGame,
                        pawn=pawn.thingIDNumber,target=target.thingIDNumber,enemy=enemy.thingIDNumber,goal_x=goal.x,goal_z=goal.z,
                        travel,locked,aim,burst,flight,potential_contact=contact,fits,continuing,
                        meaning="Potential native retarget route bound, not an enemy order, shot or guaranteed safety"});
#endif
                    if(!fits)return false;
                }
            }
            return true;
        }
        private static bool ContinueSupportApproach(Plan plan,List<Pawn> threats)
        {
            var pawn=plan.Pawn;int tick=Find.TickManager.TicksGame;
            // Later manual/clinical instructions are never ours to clear.
            if(pawn.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(pawn,q.job)))return true;
            if(PreserveDoctorPosition(pawn,plan.OwnedJob.targetA.Cell))
            {
                if(pawn.CurJob==plan.OwnedJob && CombatOrderHelper.Owned(pawn,pawn.CurJob))
                {
                    CombatOrderHelper.DropQueued(pawn);pawn.jobs.EndCurrentJob(JobCondition.InterruptForced,false);
                    plan.OwnedJob=pawn.CurJob;plan.QueuedShot=null;plan.Mode="shoot";
                }
                return false;
            }
            if(tick<plan.SupportReviewTick)return true;
            plan.SupportReviewTick=tick+30;
            var route=pawn.pather.curPath;bool useful=false;
            if((route==null || !route.Found) && PreserveTeamApproach(plan,threats))return true;
            if(route!=null && route.Found)
            {
                var cells=RemainingRangedCells(pawn,route).ToList();float travel=0f;var previous=pawn.Position;
                var next=pawn.pather.nextCell;
                if(next.IsValid && next!=pawn.Position && (cells.Count==0 || cells[0]!=next))cells.Insert(0,next);
                foreach(var cell in cells)
                {
                CombatPathBudgetHelper.Checkpoint();
                    travel+=previous==pawn.Position && cell==pawn.pather.nextCell?Math.Max(1f,pawn.pather.nextCellCostLeft)
                        :CombatInterceptHelper.PlannedJogStepTicks(pawn,previous,cell);
                    previous=cell;
                }
                int budget=16;
                useful=CombatInterceptHelper.MovementCellsSafe(pawn,cells)
                    && SupportShotWindow(pawn,plan.Target,plan.OwnedJob.targetA.Cell,travel,threats,ref budget,true);
            }
            if(useful)return true;
            if(pawn.CurJob==plan.OwnedJob && CombatOrderHelper.Owned(pawn,pawn.CurJob))
            {
                CombatOrderHelper.DropQueued(pawn);pawn.jobs.EndCurrentJob(JobCondition.InterruptForced,false);
                plan.OwnedJob=pawn.CurJob;plan.QueuedShot=null;plan.Mode="shoot";
            }
            return false;
        }
        private static bool CriticalRangedInjury(Pawn pawn)=>CombatInterceptMath.CriticalRangedInjury(
            pawn.health.summaryHealth.SummaryHealthPercent,pawn.health.hediffSet.BleedRateTotal,pawn.health.hediffSet.PainTotal,
            pawn.health.capacities.GetLevel(PawnCapacityDefOf.Consciousness),pawn.health.capacities.GetLevel(PawnCapacityDefOf.Moving),
            pawn.health.capacities.GetLevel(PawnCapacityDefOf.Manipulation),pawn.health.capacities.GetLevel(PawnCapacityDefOf.Sight));
        private static IEnumerable<IntVec3> RemainingRangedCells(Pawn pawn,CombatPathBudgetHelper.Observation path)
            =>path.NodesReversed.Take(path.NodesLeftCount).Reverse().SkipWhile(c=>c==pawn.Position);
        private static IEnumerable<IntVec3> RemainingRangedCells(Pawn pawn,PawnPath path)
            =>path.NodesReversed.Take(path.NodesLeftCount).Reverse().SkipWhile(c=>c==pawn.Position);
        private static bool SaferRangedRoute(Pawn pawn,PawnPath path,bool continuing,out float score)
            =>SaferRangedRoute(pawn,CombatPathBudgetHelper.Borrowed(path),continuing,out score);
        private static bool SaferRangedRoute(Pawn pawn,CombatPathBudgetHelper.Observation path,bool continuing,out float score,IntVec3? pauseAt=null,float reserveHorizon=0f,bool requireUnexposed=false,bool retainUnexposed=false)
        {
            score=float.PositiveInfinity;
            if(!path.Found)return false;
            var cells=(continuing?RemainingRangedCells(pawn,path):path.NodesReversed.AsEnumerable().Reverse().Skip(1)).ToArray();
            if(cells.Length==0 || cells.Length>40)return false;
            float ticks=pawn.stances.curStance is Stance_Warmup?0f:CombatInterceptHelper.MovementLockTicks(pawn);
            float before=IncomingRangedExposure(pawn,pawn.Position,ticks),holding=before;
            bool clinicalTransit=ClinicalRangedTransit(pawn),prefixSafe=true;
            float initial=before,movementLock=ticks,firstReduction=float.PositiveInfinity;
            float total=ticks*before,holdingTotal=total,peak=before,holdingPeak=before;
            var previous=pawn.Position;
            foreach(var cell in cells)
            {
                CombatPathBudgetHelper.Checkpoint();
                float step=continuing && previous==pawn.Position && pawn.pather?.Moving==true && cell==pawn.pather.nextCell
                    ?Math.Max(1f,pawn.pather.nextCellCostLeft):CombatInterceptHelper.PlannedJogStepTicks(pawn,previous,cell);
                ticks+=step;
                float exposure=IncomingRangedExposure(pawn,cell,ticks);
                float stationary=IncomingRangedExposure(pawn,pawn.Position,ticks);
                total+=step*(before+exposure)*.5f;holdingTotal+=step*(holding+stationary)*.5f;
                peak=Math.Max(peak,exposure);holdingPeak=Math.Max(holdingPeak,stationary);
                if(clinicalTransit)
                {
                    prefixSafe &= CombatDoctorTransitMath.Prefix(exposure,stationary,total,holdingTotal,ticks);
                    if(float.IsPositiveInfinity(firstReduction) && exposure<=initial-.2f)firstReduction=ticks;
                }
                before=exposure;holding=stationary;previous=cell;
                if(pauseAt.HasValue && cell==pauseAt.Value)
                {
                    // The second ordinary Goto is reviewed on the next native
                    // pulse. Include that finite transition in both horizons.
                    ticks+=15f;
                    float later=IncomingRangedExposure(pawn,cell,ticks),still=IncomingRangedExposure(pawn,pawn.Position,ticks);
                    total+=15f*(before+later)*.5f;holdingTotal+=15f*(holding+still)*.5f;
                    peak=Math.Max(peak,later);holdingPeak=Math.Max(holdingPeak,still);
                    if(clinicalTransit)prefixSafe &= CombatDoctorTransitMath.Prefix(later,still,total,holdingTotal,ticks);
                    before=later;holding=still;pauseAt=null;
                }
            }
            bool improves=CombatInterceptMath.RangedRouteImproves(total,holdingTotal,peak,holdingPeak,ticks);
            // Compare the same finite horizon on both alternatives. A short
            // crossing to observed hard shelter is not equivalent to staying
            // exposed indefinitely after the travel-only comparison ends.
            float settle=Math.Max(TeamCycle(pawn),reserveHorizon-ticks);
            float terminal=reserveHorizon>0?DoctorProjectedExposure(pawn,previous,reserveHorizon):IncomingRangedExposure(pawn,previous,ticks+settle);
            float holdingTerminal=reserveHorizon>0?DoctorProjectedExposure(pawn,pawn.Position,reserveHorizon):IncomingRangedExposure(pawn,pawn.Position,ticks+settle);
            bool protectedArrival=CombatCoverTurnMath.ProtectedArrivalImproves(total,holdingTotal,
                terminal,holdingTerminal,ticks,settle);
            bool safeContinuation=continuing && Plans.TryGetValue(pawn.thingIDNumber,out var retainedRange)
                && (OwnedRangePostInTransit(retainedRange) || CohortInTransit(retainedRange)) && CombatRangePostMath.ContinuingNotWorse(
                    total,holdingTotal,peak,holdingPeak,terminal,holdingTerminal,ticks);
            improves=improves || protectedArrival || safeContinuation;
            bool retainedMedicalRoute=retainUnexposed && continuing && requireUnexposed
                && CombatDoctorReserveMath.UnexposedRoute(peak,terminal);
            improves |= retainedMedicalRoute;
            // This gate applies to new AND remaining physician routes. The
            // native cooldown is part of elapsed exposure, never cancelled.
            bool timelyReduction=!clinicalTransit || CombatDoctorTransitMath.TimelyReduction(initial,firstReduction,movementLock);
            if(clinicalTransit)improves &= CombatDoctorTransitMath.Accept(prefixSafe,timelyReduction,protectedArrival);
            // Stationary armed allies alone are not suppressing this enemy.
            // Without confirmed cover, even an improving route cannot admit
            // a checked exposed prefix, native movement lock or endpoint.
            if(requireUnexposed)improves &= CombatDoctorReserveMath.UnexposedRoute(peak,terminal);
            score=total+terminal*settle+ticks*.05f;
#if LAYA_COMBAT_LAB
            if(RangedRouteChecks.Count<128)RangedRouteChecks.Add(new{tick=Find.TickManager.TicksGame,pawn=pawn.thingIDNumber,
                continuing,x=previous.x,z=previous.z,cells=cells.Length,duration=ticks,
                exposure_ticks=float.IsInfinity(total)?(float?)null:total,
                holding_exposure_ticks=float.IsInfinity(holdingTotal)?(float?)null:holdingTotal,
                peak=float.IsInfinity(peak)?(float?)null:peak,holding_peak=float.IsInfinity(holdingPeak)?(float?)null:holdingPeak,
                improves,require_unexposed=requireUnexposed,retained_medical_route=retainedMedicalRoute,protected_arrival=protectedArrival,continuing_range_not_worse=safeContinuation,
                clinical_transit=clinicalTransit,prefix_safe=prefixSafe,timely_reduction=timelyReduction,
                first_reduction_ticks=float.IsInfinity(firstReduction)?(float?)null:firstReduction,
                terminal_exposure=terminal,holding_terminal_exposure=holdingTerminal,
                equal_settle_horizon=settle,interpretation="Same finite travel and post-arrival horizon; not guaranteed safety or arrival"});
#endif
            return improves;
        }
        private static bool ReviewRangedWithdrawal(Plan plan,List<Pawn> threats)
        {
            var pawn=plan.Pawn;int tick=Find.TickManager.TicksGame;
            if(PendingOwnedRangedMove(plan))return true;
            if(plan.Mode!="retreat" || plan.RangedWithdrawal?.Value!=pawn.CurJob || pawn.CurJobDef!=JobDefOf.Goto
                || !MovingOrBusy(pawn))return false;
            if(tick<plan.RangedCoverReviewTick || pawn.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(pawn,q.job)))return true;
            plan.RangedCoverReviewTick=tick+60;
            try
            {
            // Read the actual native cursor, including its observed remaining
            // current-step cost. Never dispose or consume the game's curPath.
            var remaining=pawn.pather.curPath;
            bool medicalBound=DoctorBoundInTransit(plan);
            using(var observed=CombatPathBudgetHelper.Borrowed(remaining))
                if(observed.Found && (medicalBound?KeepDoctorBoundRoute(plan,observed):
                    CombatInterceptHelper.MovementCellsSafe(pawn,RemainingRangedCells(pawn,remaining))
                    && SaferRangedRoute(pawn,observed,true,out _)))return true;
            if(TryBreakRangedContact(plan,threats,true))return true;
            // The remaining owned route is now worse than holding here and
            // no checked replacement was found. Do not continue blindly into
            // additional firing lanes; later/manual jobs and queues are not ours.
            if(plan.RangedWithdrawal?.Value==pawn.CurJob && !pawn.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(pawn,q.job)))
            {
                CombatOrderHelper.DropQueued(pawn);
                pawn.jobs.EndCurrentJob(JobCondition.InterruptForced,false);
                plan.OwnedJob=pawn.CurJob;plan.QueuedShot=null;plan.Mode="shoot";
                plan.RangedWithdrawal=null;plan.RecoveryUntilTick=0;
            }
            return false;
            }
            catch(CombatReviewDeferredException)
            {
                // An unfinished proof is not a completed safe/unsafe review.
                // Preserve the owned job and retry on the next native pulse.
                plan.RangedCoverReviewTick=tick;
                throw;
            }
        }
        private static Pawn RangedShotAfterMove(Pawn pawn,IntVec3 cell,float travel,List<Pawn> threats)
        {
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(verb==null)return null;
            float arrival=travel+(pawn.stances.curStance is Stance_Warmup?0f:CombatInterceptHelper.MovementLockTicks(pawn));
            float horizon=arrival+verb.verbProps.warmupTime*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor)
                +Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots+30f;
            return threats.Where(t=>verb.CanHitTargetFrom(cell,t) && CombatInterceptHelper.FriendlyLaneClear(pawn,t,cell)
                && CombatInterceptHelper.TryObservedFuturePosition(t,horizon,out var future)
                && CombatExposureHelper.CanHitCandidate(verb,cell,future,pawn.Map)==true
                && CombatInterceptHelper.FutureFriendlyLaneClear(pawn,t,cell,future,"ranged_after_move"))
                .OrderByDescending(t=>ShotQuality(pawn,t,cell)).ThenBy(t=>t.thingIDNumber).FirstOrDefault();
        }
        private static bool ObservedTargetedRangedThreat(Pawn pawn,List<Pawn> threats)
        {
            return threats.Any(enemy=>
            {
                var verb=enemy.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
                var projectile=verb?.verbProps.defaultProjectile?.projectile;
                return enemy.equipment?.Primary?.def.IsRangedWeapon==true && verb!=null
                    && projectile!=null && projectile.damageDef==DamageDefOf.Bullet && projectile.explosionRadius<=0f
                    && AimTarget(enemy)==pawn
                    && (enemy.stances.curStance is Stance_Warmup || verb.state==VerbState.Bursting)
                    && CombatExposureHelper.Lane(enemy,pawn,pawn.Position,enemy.Position)>=.6f;
            });
        }
        private static bool TryBreakRangedContact(Plan plan,List<Pawn> threats,bool reviewing=false)
        {
            Pawn pawn=plan.Pawn;int tick=Find.TickManager.TicksGame;
            if(!Eligible(pawn))return false;
            float exposure=IncomingRangedExposure(pawn,pawn.Position);
            bool wounded=CriticalRangedInjury(pawn) || MedicalFunctionWarning(pawn) || TargetedWoundedRanged(pawn,threats);
            bool preserveMedical=IsReservedDoctor(pawn);
            var coveredEnemy=!wounded && !preserveMedical?ProactiveCoveredEnemy(pawn,threats):null;
            bool shelterOnly=wounded || preserveMedical || coveredEnemy!=null;bool singleTargeted=false;
            bool clinicalTransit=ClinicalRangedTransit(pawn);
            if(!shelterOnly)
            {
                // The physician's checked transit must not veto every healthy
                // gun's short rotation when TWO other actual guns retain fire.
                if(!AllowsRangedMedicalRotation(pawn,plan.Target))return false;
                // A single actual aimed gun can be dangerous without crossfire.
                // This extra rotation never interrupts this gun's useful aim,
                // a queued instruction, or another moving selected defender.
                singleTargeted=exposure<1.4f && pawn.CurJob==plan.OwnedJob && !pawn.jobs.jobQueue.Any()
                    && !(pawn.stances.curStance is Stance_Warmup) && ObservedTargetedRangedThreat(pawn,threats);
                if(!DefensivePlan(plan.Tactic) || (exposure<1.4f && !singleTargeted) || !CombatInterceptHelper.ReadyCover(pawn,plan.Target).Any())return false;
                var anchorGun=Plans.Values.Where(Valid).Select(p=>p.Pawn).Where(p=>p.Map==pawn.Map
                    && p.CurJobDef!=JobDefOf.Goto && CombatInterceptHelper.CanShootNow(p,plan.Target))
                    .OrderByDescending(p=>p.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb?.verbProps.range ?? 0)
                    .ThenBy(p=>IncomingRangedExposure(p,p.Position)).ThenBy(p=>p.thingIDNumber).FirstOrDefault();
                if(anchorGun==pawn)return false;
            }
            if(!reviewing && tick<plan.RangedCoverReviewTick)return false;
            plan.RangedCoverReviewTick=tick+90;
            if(threats.Any(e=>MeleeThreat(e) && pawn.Position.DistanceTo(e.Position)<8f))return false;
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(verb?.state==VerbState.Bursting || exposure<.6f)return false;
            var map=pawn.Map;
            // Temporarily losing a firing lane is preferable to leaving an
            // already wounded gun in observed crossfire. Other selected guns
            // keep their jobs; this is an ordinary checked movement order.
            var ranged=threats.Where(e=>e.equipment?.Primary?.def.IsRangedWeapon==true)
                .Select(e=>new{Pawn=e,Range=e.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb?.verbProps.range ?? 0}).ToArray();
            var pool=GenRadial.RadialCellsAround(pawn.Position,18f,false)
                .Where(c=>c.InBounds(map) && c.Standable(map) && !c.Fogged(map)
                    && (coveredEnemy==null || c.DistanceTo(pawn.Position)<=8f)
                    && c.DistanceTo(plan.Anchor)<=26f && !CellClaimed(pawn,c)
                    && !c.GetThingList(map).Any(t=>t is Pawn || t is Building_Trap && t.Faction==Faction.OfPlayer)
                    && threats.All(e=>c.DistanceTo(e.Position)>=8f)).ToArray();
            var cells=pool.Where(c=>c.DistanceTo(pawn.Position)<=4f).Take(48)
                .Concat(pool.OrderBy(c=>ranged.Count(e=>c.InHorDistOf(e.Pawn.Position,e.Range+1f))*100f+c.DistanceTo(pawn.Position)).Take(24))
                .Distinct().Where(c=>IncomingRangedExposure(pawn,c)<=.1f
                    || clinicalTransit && DoctorStagedCell(pawn,c,exposure,IncomingRangedExposure(pawn,c),threats))
                .OrderBy(c=>c.DistanceTo(pawn.Position));
            IntVec3 bestCell=IntVec3.Invalid;float bestScore=float.PositiveInfinity;Pawn nextShot=null;
            foreach(var cell in ReviewEscapeCells(pawn,plan.Target,"ranged",cells,2))
            {
                CombatPathBudgetHelper.Checkpoint();
                if(!cell.Standable(map) || CellClaimed(pawn,cell)
                    || threats.Any(e=>cell.DistanceTo(e.Position)<8f))continue;
                float endpoint=IncomingRangedExposure(pawn,cell);
                if(endpoint>.1f && !(clinicalTransit && DoctorStagedCell(pawn,cell,exposure,endpoint,threats)))continue;
                using(var path=CombatPathBudgetHelper.Query(pawn,pawn.Position,cell,PathEndMode.OnCell))
                {
                    if(path.TotalCost>480f || !CombatInterceptHelper.MovementSafe(pawn,path)
                        || !SaferRangedRoute(pawn,path,false,out var risk) || risk>=bestScore)continue;
                    var shot=shelterOnly?null:RangedShotAfterMove(pawn,cell,path.TotalCost,threats);
                    if(!shelterOnly && shot==null)continue;
                    bestScore=risk;bestCell=cell;nextShot=shot;
                    // Commit the first fully validated refuge. Exploring every
                    // remaining candidate can throw BudgetDeferred after this
                    // proof and discard the only useful accepted decision.
                    break;
                }
            }
            if(bestCell.IsValid)
            {
                if(KeepGroupPosition(pawn,bestCell))return false;
                var move=JobMaker.MakeJob(JobDefOf.Goto,bestCell);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                pawn.stances.CancelBusyStanceSoft();
                if(pawn.CurJobDef==JobDefOf.AttackStatic){CombatOrderHelper.DropQueued(pawn);pawn.jobs.EndCurrentJob(JobCondition.InterruptForced,false);}
                if(!CombatOrderHelper.Take(pawn,ref move))return false;
                var shot=nextShot==null?null:CombatOrderHelper.QueueShot(pawn,nextShot);
                move=RememberMove(pawn,move,shot);RetreatJobs[pawn]=new CombatJobStamp(move);
                plan.OwnedJob=move;plan.QueuedShot=shot;plan.Mode="retreat";plan.LastMoveTick=tick;
                if(nextShot!=null)plan.Target=nextShot;
                plan.RecoveryCell=bestCell;plan.RecoveryUntilTick=tick+600;plan.RangedWithdrawal=new CombatJobStamp(move);
                if(coveredEnemy!=null)TeamEvent("two_actual_guns_cover_front_refuge_before_wound",pawn,coveredEnemy);
#if LAYA_COMBAT_LAB
                if(RangedWithdrawals.Count<128)RangedWithdrawals.Add(new{tick,pawn=pawn.thingIDNumber,critical=wounded,preserving_doctor=preserveMedical,single_targeted=singleTargeted,exposure_before=exposure,
                    target=nextShot?.thingIDNumber,queued_shot=shot!=null,x=bestCell.x,z=bestCell.z,
                    health=pawn.health.summaryHealth.SummaryHealthPercent,bleeding=pawn.health.hediffSet.BleedRateTotal,
                    interpretation="Accepted native move and optional selected shot, not arrival or firing"});
#endif
                return true;
            }
            return clinicalTransit && TryDoctorDetour(plan,threats,pool);
        }
        private static void ReviewPursuedApproach(Plan plan)
        {
            var pawn=plan.Pawn;
            if((plan.Mode!="position" && plan.Mode!="intercept") || pawn.CurJob!=plan.OwnedJob
                || pawn.CurJobDef!=JobDefOf.Goto || !CombatOrderHelper.Owned(pawn,pawn.CurJob)
                || !Present(pawn,plan.QueuedShot) || plan.QueuedShot.def!=JobDefOf.AttackStatic
                || pawn.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(pawn,q.job)))return;
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(pawn.stances.curStance is Stance_Warmup || verb?.state==VerbState.Bursting)return;
            var target=plan.QueuedShot.targetA.Thing as Pawn;
            var review=CombatPursuitApproachHelper.Check(pawn,target,pawn.pather.curPath,0f,true);
            if(review.Clear)return;
            var wait=JobMaker.MakeJob(JobDefOf.Wait_Combat);wait.playerForced=true;
            // Take preserves current/queued clinical and later foreign orders.
            // Only this owned forward approach and its selected shot stop.
            if(!CombatOrderHelper.Take(pawn,ref wait))return;
#if LAYA_COMBAT_LAB
            CombatPursuitApproachHelper.RecordStop(pawn,target,review);
#endif
            plan.OwnedJob=wait;plan.QueuedShot=null;plan.Mode="shoot";
            plan.Target=pawn.Map.mapPawns.AllPawnsSpawned.FirstOrDefault(e=>e.thingIDNumber==review.Pursuer);
            SelectedMoves.Remove(pawn);RetreatJobs.Remove(pawn);
        }
        private static readonly Dictionary<Pawn,int> CarrierPageReviews=new Dictionary<Pawn,int>();
        private static Game CarrierPageReviewGame;
        private static void ReviewCarrierDeparturePages()
        {
            int tick=Find.TickManager.TicksGame;
            if(CarrierPageReviewGame!=Current.Game){CarrierPageReviews.Clear();CarrierPageReviewGame=Current.Game;}
            foreach(var stale in CarrierPageReviews.Keys.Where(p=>p.Destroyed || p.Dead || !p.Spawned).ToArray())CarrierPageReviews.Remove(stale);
            foreach(var group in Plans.Values.Where(Valid).GroupBy(p=>p.Pawn.Map).ToArray())
            {
                var threats=group.Key.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
                if(threats.Count!=1 || !CombatCarrierInterceptHelper.Eligible(threats[0]))continue;
                var waiting=group.Where(OwnStationaryGun)
                    .Where(p=>p.Tactic!="stationary_fire" && !CombatNativeHelper.Protected(p.Pawn)
                        && !CareTriageHelper.QueuedCare(p.Pawn))
                    .OrderBy(p=>CarrierPageReviews.TryGetValue(p.Pawn,out int prior)?prior:int.MinValue)
                    .ThenBy(p=>p.Pawn.thingIDNumber).Take(2).ToArray();
                foreach(var plan in waiting)
                {
                    CarrierPageReviews[plan.Pawn]=tick;
                    TryCarrierAdvance(plan,threats);
                }
            }
        }
        private static bool TryCarrierAdvance(Plan plan,List<Pawn> threats)
        {
            Pawn pawn=plan.Pawn;
            if(plan.Tactic=="stationary_fire")return false;
            var carrier=threats.Where(CombatNativeHelper.AbductionThreat).OrderBy(t=>t.Position.DistanceToSquared(pawn.Position)).FirstOrDefault();
            if(carrier==null)return false;
            if(pawn.stances.curStance is Stance_Warmup && AimTarget(pawn)==carrier
                && CombatInterceptHelper.CanShootNow(pawn,carrier))return false;
            int tick=Find.TickManager.TicksGame;
            bool needsAdvance=CombatInterceptHelper.CarrierWindowNeedsAdvance(pawn,carrier);
            // A selected approach is a means to get a shot. Once a checked
            // interior firing window opens, use it before finishing an older
            // waypoint. Do not replace an escape, support or assembly move.
            if(!needsAdvance && (plan.Mode=="position" || plan.Mode=="intercept")
                && pawn.CurJob==plan.OwnedJob && pawn.CurJobDef==JobDefOf.Goto
                && plan.QueuedShot?.targetA.Thing==carrier && Present(pawn,plan.QueuedShot)
                && CombatInterceptHelper.CanShootNow(pawn,carrier))
            {
                var previousCell=plan.OwnedJob.targetA.Cell;
                var attack=JobMaker.MakeJob(JobDefOf.AttackStatic,carrier);attack.playerForced=true;
                if(CombatOrderHelper.Take(pawn,ref attack))
                {
                    plan.OwnedJob=attack;plan.QueuedShot=null;plan.Target=carrier;plan.Mode="shoot";
#if LAYA_COMBAT_LAB
                    if(InterceptStops.Count<128)InterceptStops.Add(new{tick,pawn=pawn.thingIDNumber,target=carrier.thingIDNumber,
                        x=pawn.Position.x,z=pawn.Position.z,previous_x=previousCell.x,previous_z=previousCell.z,
                        current_shot=pawn.CurJob==attack,job=pawn.CurJobDef?.defName});
#endif
                    return true;
                }
            }
            // Kidnap's job target may remain the victim after pickup. Observe
            // the actual path destination so a changed exit triggers review.
            var goal=carrier.pather?.Destination.IsValid==true?carrier.pather.Destination.Cell
                :carrier.CurJob?.targetA.Cell ?? IntVec3.Invalid;
            if(tick<plan.InterceptReviewTick && plan.InterceptObservedJob==carrier.CurJobDef
                && plan.InterceptObservedGoal==goal)return false;
            plan.InterceptReviewTick=tick+60;plan.InterceptObservedJob=carrier.CurJobDef;plan.InterceptObservedGoal=goal;
            if(!needsAdvance
                || !CombatInterceptHelper.TryPosition(pawn,carrier,out var cell) || cell==pawn.Position)return false;
            var move=JobMaker.MakeJob(JobDefOf.Goto,cell);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
            if(!CombatOrderHelper.Take(pawn,ref move))return false;
            var shot=CombatOrderHelper.QueueShot(pawn,carrier);move=RememberMove(pawn,move,shot);
            plan.OwnedJob=move;plan.QueuedShot=shot;plan.Target=carrier;plan.Mode="intercept";plan.LastMoveTick=Find.TickManager.TicksGame;
            return true;
        }
        private static bool TryReleaseCompletedEscape(Plan plan,List<Pawn> threats)
        {
            // A range-advantage post is not a melee escape whose sole cause
            // disappears when one attacker chooses a different victim. Its
            // actual remaining route is still reviewed immediately below.
            if(OwnedRangePostInTransit(plan) || CohortInTransit(plan) || DoctorBoundInTransit(plan))return false;
            var pawn=plan.Pawn;var cause=plan.Target;
            if(plan.Mode!="retreat" || plan.Tactic=="withdraw_and_regroup"
                || pawn.CurJob!=plan.OwnedJob || pawn.CurJobDef!=JobDefOf.Goto || cause==null
                || CareTriageHelper.QueuedCare(pawn) || CombatNativeHelper.Protected(pawn)
                || pawn.carryTracker?.CarriedThing is Pawn
                || pawn.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(pawn,q.job))
                || pawn.health.summaryHealth.SummaryHealthPercent<.85f || pawn.health.hediffSet.BleedRateTotal>0f
                || pawn.health.capacities.GetLevel(PawnCapacityDefOf.Moving)<.85f
                || pawn.Position.ContainsStaticFire(pawn.Map)
                || pawn.Map.gasGrid.DensityAt(pawn.Position,GasType.ToxGas)>0
                || pawn.Map.gasGrid.DensityAt(pawn.Position,GasType.DeadlifeDust)>0)return false;
            bool ended=cause.Dead || cause.Downed || !cause.Spawned
                || cause.Map==pawn.Map && !cause.Position.Fogged(pawn.Map) && ObservedVictim(cause) is Pawn other && other!=pawn;
            // A different distant pursuer is a deadline to check, not an
            // unconditional veto of a physician's currently useful shot.
            // Retain the generic escape rule; this finite medical rejoin
            // independently bounds contact from EVERY observed melee threat.
            bool physician=NativeDoctor(pawn) && IsReservedDoctor(pawn)
                && threats.All(MeleeThreat);
            if(!ended || !physician && threats.Any(t=>CombatInterceptHelper.Pursuing(t,pawn))
                || IncomingRangedExposure(pawn,pawn.Position)>.1f)return false;
            var target=GroupTarget(pawn,threats,null);
            if(target==null || !CombatInterceptHelper.CanShootNow(pawn,target))return false;
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            float aim=verb.verbProps.warmupTime*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor);
            var projectile=verb.verbProps.defaultProjectile?.projectile;
            float flight=projectile==null?0f:CombatInterceptMath.NativeFlightTicks(pawn.Position.DistanceTo(target.Position),projectile.SpeedTilesPerTick);
            if(float.IsInfinity(flight))return false;
            float burst=Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots;
            foreach(var threat in threats.Where(t=>physician?MeleeThreat(t):ClosingMelee(t,pawn)))
            {
                CombatPathBudgetHelper.Checkpoint();
                // Stopping invalidates the old moving escape forecast. Use a
                // conservative straight approach to this stationary cell;
                // terrain and enemy locks can delay contact, never hasten it.
                float step=threat.TicksPerMoveCardinal*(threat.CurJob?.locomotionUrgency==LocomotionUrgency.Sprint?.75f:1f);
                float contact=Math.Max(0,pawn.Position.DistanceTo(threat.Position)-1.5f)*Math.Max(1f,step);
                if(!CombatInterceptMath.SupportVolley(contact,aim+flight,burst,CombatInterceptHelper.MovementLockTicks(pawn),false))return false;
            }
            var previous=plan.OwnedJob.targetA.Cell;
            var attack=JobMaker.MakeJob(JobDefOf.AttackStatic,target);attack.playerForced=true;
            if(!CombatOrderHelper.Take(pawn,ref attack))return false;
            plan.OwnedJob=attack;plan.QueuedShot=null;plan.Target=target;plan.Mode="shoot";
#if LAYA_COMBAT_LAB
            if(InterceptStops.Count<128)InterceptStops.Add(new{tick=Find.TickManager.TicksGame,pawn=pawn.thingIDNumber,
                target=target.thingIDNumber,cause=cause.thingIDNumber,cause_active=Threat(cause),
                x=pawn.Position.x,z=pawn.Position.z,previous_x=previous.x,previous_z=previous.z,
                current_shot=pawn.CurJob==attack,job=pawn.CurJobDef?.defName,kind="completed_contact_escape"});
#endif
            return true;
        }
        // A forecast cover transit has its own role. Current firing range
        // does not complete that relocation; preserve it until native arrival.
        // Immediate contact and hazard checks still run before this method.
        private static bool CoverTransitStillUseful(Plan plan)
        {
            var pawn=plan.Pawn;int tick=Find.TickManager.TicksGame;
            if(tick<plan.CoverTransitReviewTick)return plan.CoverTransitUseful;
            plan.CoverTransitReviewTick=tick+60;plan.CoverTransitUseful=true;
            var goal=plan.OwnedJob.targetA.Cell;
            using(var path=CombatPathBudgetHelper.Query(pawn,pawn.Position,goal,PathEndMode.OnCell))
            {
                if(!path.Found || path.TotalCost>480f || !CombatInterceptHelper.MovementSafe(pawn,path))return true;
                var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
                float cycle=verb.verbProps.warmupTime*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor)
                    +Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots
                    +pawn.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f+30f;
                float horizon=CombatInterceptHelper.MovementLockTicks(pawn)+path.TotalCost+cycle;
                float staying=IncomingRangedExposure(pawn,pawn.Position,horizon),projected=IncomingRangedExposure(pawn,goal,horizon);
                bool available=!float.IsInfinity(staying) && !float.IsInfinity(projected);
                bool shotWindow=CriticalRangedInjury(pawn) || CoverShotWindow(pawn,plan.Target,goal,path.TotalCost);
                if(available)plan.CoverTransitUseful=CombatInterceptMath.CoverImproves(staying,projected) && shotWindow;
#if LAYA_COMBAT_LAB
                if(CoverTransitReviews.Count<128)CoverTransitReviews.Add(new{tick,pawn=pawn.thingIDNumber,
                    job_id=plan.OwnedJob.loadID,x=pawn.Position.x,z=pawn.Position.z,goal_x=goal.x,goal_z=goal.z,
                    path_cost=path.TotalCost,horizon,forecast_available=available,
                    staying=available?(float?)staying:null,projected=available?(float?)projected:null,
                    preserve=plan.CoverTransitUseful,selected_shot_window=shotWindow,
                    interpretation="Current route endpoint and selected firing-window review; not arrival or guaranteed safety"});
#endif
                return plan.CoverTransitUseful;
            }
        }
        private static bool TryFinishFiringApproach(Plan plan,List<Pawn> threats)
        {
            var pawn=plan.Pawn;var target=plan.Target;
            if((plan.Mode!="position" && plan.Mode!="cover") || pawn.CurJob!=plan.OwnedJob || pawn.CurJobDef!=JobDefOf.Goto
                || target==null || !Threat(target) || CombatNativeHelper.AbductionThreat(target)
                || plan.QueuedShot?.targetA.Thing!=target || !Present(pawn,plan.QueuedShot)
                || pawn.Position.ContainsStaticFire(pawn.Map)
                || pawn.Map.gasGrid.DensityAt(pawn.Position,GasType.ToxGas)>0
                || pawn.Map.gasGrid.DensityAt(pawn.Position,GasType.DeadlifeDust)>0
                || !CombatInterceptHelper.InteriorShotWindow(pawn,target))return false;
            var goal=plan.OwnedJob.targetA.Cell;
            // Keep a move to better cover. A point already offering a checked
            // shot and no greater ranged exposure need not be passed just
            // because it was not the original destination.
            if(plan.Mode=="cover")
            {
                // A currently available shot does not finish a move selected
                // for a future flank. Review both cells at the same remaining
                // native travel/first-cycle horizon. If that measured advantage
                // ends, a legal current firing window can release the move.
                if(CoverTransitStillUseful(plan))return false;
            }
            else if(IncomingRangedExposure(pawn,pawn.Position)>IncomingRangedExposure(pawn,goal)+.1f)return false;
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            float aim=verb.verbProps.warmupTime*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor);
            float burst=Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots;
            float cooldown=pawn.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f;
            if(threats.Where(t=>ClosingMelee(t,pawn)).Any(t=>!CombatInterceptMath.FinishVolley(
                CombatInterceptHelper.ContactTicks(t,pawn),aim,burst,cooldown,CombatInterceptHelper.MovementLockTicks(pawn),false)))return false;
            bool releasedCover=plan.Mode=="cover";
            var attack=JobMaker.MakeJob(JobDefOf.AttackStatic,target);attack.playerForced=true;
            if(!CombatOrderHelper.Take(pawn,ref attack))return false;
            plan.OwnedJob=attack;plan.QueuedShot=null;plan.Mode="shoot";
#if LAYA_COMBAT_LAB
            if(InterceptStops.Count<128)InterceptStops.Add(new{tick=Find.TickManager.TicksGame,pawn=pawn.thingIDNumber,target=target.thingIDNumber,
                x=pawn.Position.x,z=pawn.Position.z,previous_x=goal.x,previous_z=goal.z,
                current_shot=pawn.CurJob==attack,job=pawn.CurJobDef?.defName,kind="ordinary_firing_approach",released_cover_transit=releasedCover});
#endif
            return true;
        }
        private static bool ContactDefence(Plan plan,List<Pawn> threats)
        {
            var pawn=plan.Pawn;
            var adjacent=threats.Where(t=>CombatInterceptMath.ContactDefence(true,pawn.Position.DistanceTo(t.Position))).ToArray();
            if(!adjacent.Any())
            {
                if(plan.Mode=="contact" && pawn.CurJob==plan.OwnedJob && pawn.CurJobDef==JobDefOf.AttackMelee)
                {CombatOrderHelper.DropQueued(pawn);pawn.jobs.EndCurrentJob(JobCondition.InterruptForced,false);plan.OwnedJob=pawn.CurJob;plan.Mode="shoot";}
                return false;
            }
            if(plan.Mode=="retreat" && pawn.CurJob==plan.OwnedJob && pawn.pather.Moving
                && !pawn.stances.stagger.Staggered && adjacent.All(t=>Speed(pawn)>Speed(t)*1.1f)
                && adjacent.All(t=>plan.OwnedJob.targetA.Cell.DistanceTo(t.Position)>pawn.Position.DistanceTo(t.Position)+3f))return true;
            var contact=pawn.CurJobDef==JobDefOf.AttackMelee && pawn.CurJob.targetA.Thing is Pawn current && adjacent.Contains(current)
                ?current:adjacent.OrderBy(t=>pawn.Position.DistanceToSquared(t.Position)).First();
            if(TryRangedRetreat(pawn,contact,plan.Anchor,out var retreat))
            {plan.OwnedJob=retreat;plan.QueuedShot=SelectedMoves[pawn].Value;plan.Target=contact;plan.Mode="retreat";plan.LastMoveTick=Find.TickManager.TicksGame;return true;}
            if(pawn.meleeVerbs.TryGetMeleeVerb(contact)==null)return true;
            if(pawn.CurJobDef!=JobDefOf.AttackMelee || pawn.CurJob.targetA.Thing!=contact)
            {
                var defend=JobMaker.MakeJob(JobDefOf.AttackMelee,contact);defend.playerForced=true;
                defend.expiryInterval=120;defend.checkOverrideOnExpire=true;
                if(!CombatOrderHelper.Take(pawn,ref defend))return true;
                plan.OwnedJob=pawn.CurJobDef==JobDefOf.AttackMelee && pawn.CurJob.targetA.Thing==contact?pawn.CurJob:defend;
            }
            else plan.OwnedJob=pawn.CurJob;
            CombatContactHelper.Remember(pawn,plan.OwnedJob);
            plan.QueuedShot=null;plan.Target=contact;plan.Mode="contact";
            return true; // An actual adjacent opponent precedes future contact estimates and focus fire.
        }
        private static bool RetreatPursuer(Pawn enemy,Pawn pawn)
        {
            if(CombatInterceptHelper.Pursuing(enemy,pawn))return true;
            // A live building attack has an observed different target. Keep
            // the existing immediate-contact buffer, without treating a gun
            // striking furniture four or five cells away as pawn pursuit.
            bool building=enemy.CurJobDef==JobDefOf.AttackMelee
                && enemy.CurJob.targetA.Thing is Building b && b.Spawned && !b.Destroyed;
            return enemy.Position.InHorDistOf(pawn.Position,building?3f:5f);
        }
        private static bool PreserveUncoveredShot(Pawn pawn,Pawn target,List<Pawn> threats)
            => target!=null && threats.All(t=>t.RaceProps.Humanlike && t.equipment?.Primary?.def.IsRangedWeapon!=true)
                && pawn.health.summaryHealth.SummaryHealthPercent>=.85f && pawn.health.hediffSet.BleedRateTotal==0f
                && pawn.health.capacities.GetLevel(PawnCapacityDefOf.Consciousness)>=.85f
                && pawn.health.capacities.GetLevel(PawnCapacityDefOf.Moving)>=.85f
                && pawn.health.capacities.GetLevel(PawnCapacityDefOf.Manipulation)>=.75f
                && !pawn.Position.ContainsStaticFire(pawn.Map)
                && pawn.Map.gasGrid.DensityAt(pawn.Position,GasType.ToxGas)==0
                && pawn.Map.gasGrid.DensityAt(pawn.Position,GasType.DeadlifeDust)==0
                && CombatInterceptHelper.CanShootNow(pawn,target);
        public static bool TryRangedRetreat(Pawn pawn,Pawn target,IntVec3 anchor,out Job issued,bool requireCoveredCorridor=false,bool medicalDeadline=false)
        {
            issued=null;if(!Eligible(pawn))return false;
            if(KeepArrivalShot(pawn))return false; // No path search or cancellation before a finite rejoin.
#if LAYA_COMBAT_LAB
            if(TestDisabled)return false;
            Attempted++;
#endif
            Map map=pawn.Map;
            var threats=map.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
            var close=threats.Where(MeleeThreat).ToList();
            if(!close.Any())return false;
            medicalDeadline &= NativeDoctor(pawn) && IsReservedDoctor(pawn);
            if(!medicalDeadline && MeleeCohort(map,threats) && CombatFallbackMath.WaitForMovingPeers(
                !TeamImmediateDanger(pawn) && !CriticalRangedInjury(pawn) && !MedicalFunctionWarning(pawn),
                OtherSelectedGunMoving(pawn),threats.Any(e=>CombatInterceptHelper.CanShootNow(pawn,e)),
                EarliestContact(pawn,threats),TeamCycle(pawn)))return false;
            var following=new List<Pawn>();
            foreach(var enemy in close)if(RetreatPursuer(enemy,pawn))following.Add(enemy);
            var pursuers=following.OrderBy(t=>CombatInterceptHelper.ContactTicks(t,pawn)).Take(2).ToArray();
            if(!pursuers.Any())return false; // This gun should cover the actually pursued ally.
            float old=close.Min(t=>pawn.Position.DistanceTo(t.Position));
            // Under adjacent melee hits, stagger and wounds can make a nominal
            // escape impossible. Do not repeatedly replace self-defence with it.
            var lockedPursuers=close.Where(t=>t.Position.InHorDistOf(pawn.Position,2.1f)
                && CombatInterceptHelper.Pursuing(t,pawn) && Speed(pawn)<=Speed(t)*1.1f).ToArray();
            if(lockedPursuers.Any() && pawn.stances.stagger.Staggered)return false;
            var covering=CombatInterceptHelper.ReadyCover(pawn,target);
            if(requireCoveredCorridor)covering=covering.Where(g=>RecentCover(g,target)).ToList();
            bool actualPursuit=CombatInterceptHelper.Pursuing(target,pawn);
            if(requireCoveredCorridor && (!actualPursuit || !covering.Any()))return false;
            bool coveredCandidate=requireCoveredCorridor || CombatInterceptMath.CoveredBait(actualPursuit,covering.Count,true);
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            float cycle=(verb?.verbProps.warmupTime ?? 0)*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor)
                +Math.Max(0,(verb?.verbProps.burstShotCount ?? 1)-1)*(verb?.verbProps.ticksBetweenBurstShots ?? 0)
                +pawn.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f;
            float before=pursuers.Min(t=>CombatInterceptHelper.ContactTicks(t,pawn));int pathChecks=0;
            bool preserveShot=PreserveUncoveredShot(pawn,target,threats);
            float? stationaryContact=null;
            var orderedCandidates=GenRadial.RadialCellsAround(pawn.Position,8f,false).Where(c=>c.InBounds(map) && c.Standable(map) && !c.Fogged(map)
                && !c.ContainsStaticFire(map) && map.gasGrid.DensityAt(c,GasType.ToxGas)==0 && map.gasGrid.DensityAt(c,GasType.DeadlifeDust)==0
                && !c.GetThingList(map).Any(t=>t is Pawn || t is Building_Trap && t.Faction==Faction.OfPlayer) && !CellClaimed(pawn,c)
                && c.DistanceTo(anchor)<=26f && close.Min(t=>c.DistanceTo(t.Position))>=Math.Max(lockedPursuers.Any()?4f:6f,old+3f)
                && (coveredCandidate || target==null || c.DistanceTo(target.Position)<=(verb?.verbProps.range ?? 0)-1f))
                // Escaping a sword does not require keeping a shot through
                // every wall. That requirement forced exposed forward/side
                // moves when a safe rear cell temporarily lost sight.
                .OrderByDescending(c=>close.Min(t=>c.DistanceTo(t.Position))*3f-c.DistanceTo(anchor)*.7f
                    -IncomingRangedExposure(pawn,c)*40f
                    + (target!=null && verb!=null && verb.CanHitTargetFrom(c,target)
                        && CombatInterceptHelper.FriendlyLaneClear(pawn,target,c)?8f:0f)
                    +covering.Count(g=>c.InHorDistOf(g.Position,16f)
                        && g.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb.CanHitTargetFrom(g.Position,new LocalTargetInfo(c)))*16f)
                .ToList();
            // Keep a healthy gun inside actual covering guns' loaded free-
            // interception radius when a checked escape permits it. A far
            // rear endpoint can strand this gun behind those allies if the
            // observed pursuer later changes victim. No such switch is assumed.
            // Wounded escapes and ranged/mixed threats keep their old order.
            var actualGuns=covering.Where(g=>AimTarget(g)==target).ToArray();
            bool preferCloseSupport=preserveShot && actualPursuit && actualGuns.Any();
            var closeCandidates=preferCloseSupport?orderedCandidates.Select(c=>new{Cell=c,
                    Count=actualGuns.Count(g=>c.InHorDistOf(g.Position,4f)
                        && VerbUtility.InterceptChanceFactorFromDistance(c.ToVector3Shifted(),g.Position)==0f)})
                .Where(x=>x.Count>0 && verb.CanHitTargetFrom(x.Cell,target)
                    && CombatInterceptHelper.FriendlyLaneClear(pawn,target,x.Cell)
                    // Cheap conservative shortlist only. The actual native
                    // pursuer path is independently checked below.
                    && pursuers.All(t=>actualGuns.All(g=>g.Position.InHorDistOf(t.Position,2.1f)
                        || !CombatInterceptMath.InterveningAlly(t.Position.x,t.Position.z,x.Cell.x,x.Cell.z,
                            g.Position.x,g.Position.z,2f))))
                .OrderByDescending(x=>x.Count).Take(4).Select(x=>x.Cell):Enumerable.Empty<IntVec3>();
            var preferred=closeCandidates.ToArray();
            var stationaryFriends=map.mapPawns.FreeColonistsSpawned.Where(g=>g!=pawn && Eligible(g)
                && g.CurJobDef!=JobDefOf.Goto).ToArray();
            // A finite covering burst calls for a short useful step, not the
            // farthest endpoint behind the line. Straight geometry only ranks
            // candidates; native actor/pursuer routes below remain decisive.
            var handoffCandidates=orderedCandidates.OrderBy(c=>pursuers.Sum(e=>stationaryFriends.Count(g=>
                    !g.Position.InHorDistOf(e.Position,2.1f) && CombatInterceptMath.InterveningAlly(
                        e.Position.x,e.Position.z,c.x,c.z,g.Position.x,g.Position.z,2f))))
                .ThenBy(c=>c.DistanceToSquared(pawn.Position));
            // A normal rejection must finish its finite page before another
            // actor is reviewed. Eight candidates, each with actor/pursuer and
            // stationary comparison paths, repeatedly exhausted eight queries.
            // Keep the quota unchanged and evaluate one complete proof at a
            // time. Active formation ranks real exits toward the common rear;
            // all route, firing-window and intervening-ally checks still apply.
            IEnumerable<IntVec3> ranked=requireCoveredCorridor?handoffCandidates:preferred.Concat(orderedCandidates);
            if(!requireCoveredCorridor && MeleeCohort(map,threats)
                && FallbackCohorts.TryGetValue(map,out var rally))
                ranked=ranked.OrderBy(c=>c.DistanceToSquared(CohortFormationPost(rally,pawn)))
                    .ThenBy(c=>c.DistanceToSquared(pawn.Position));
            var candidates=ReviewEscapeCells(pawn,target,requireCoveredCorridor?"handoff":"melee",ranked,1);
            foreach(var cell in candidates)
            {
                CombatPathBudgetHelper.Checkpoint();
                // Cached candidate order is not a cached safety proof.
                if(!cell.Standable(map) || cell.Fogged(map) || CellClaimed(pawn,cell)
                    || cell.ContainsStaticFire(map) || map.gasGrid.DensityAt(cell,GasType.ToxGas)>0
                    || map.gasGrid.DensityAt(cell,GasType.DeadlifeDust)>0
                    || cell.GetThingList(map).Any(t=>t is Pawn || t is Building_Trap && t.Faction==Faction.OfPlayer)
                    || close.Min(t=>cell.DistanceTo(t.Position))<Math.Max(lockedPursuers.Any()?4f:6f,old+3f))continue;
                using(var path=CombatPathBudgetHelper.Query(pawn,pawn.Position,cell,PathEndMode.OnCell))
                {
                    if(!CombatTacticsHelper.RetreatRouteSafe(pawn,path))continue;
                    if(path.NodesReversed.Any(c=>map.gasGrid.DensityAt(c,GasType.ToxGas)>0 || map.gasGrid.DensityAt(c,GasType.DeadlifeDust)>0))continue;
                    bool corridor=coveredCandidate && path.NodesReversed.All(c=>covering.Any(g=>
                        g.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb.CanHitTargetFrom(g.Position,new LocalTargetInfo(c))));
                    if(requireCoveredCorridor && !corridor)continue;
                    if(target!=null && cell.DistanceTo(target.Position)>(verb?.verbProps.range ?? 0)-1f
                        && !CombatInterceptMath.CoveredBait(actualPursuit,covering.Count,corridor))continue;
                    float ownLock=pawn.stances.curStance is Stance_Warmup?0:CombatInterceptHelper.MovementLockTicks(pawn);
                    if(lockedPursuers.Any() && (pawn.stances.stagger.Staggered || lockedPursuers.Any(t=>
                        !CombatInterceptMath.LockedEscapeWindow(ownLock,CombatInterceptHelper.MovementLockTicks(t),path.TotalCost))))continue;
                    // Moving eight cells is not useful kiting when an uncovered
                    // faster pursuer arrives just as soon. Require a measured
                    // new firing window, or actual same-pursuer covering fire.
                    float after=float.MaxValue;
                    foreach(var pursuer in pursuers)
                    {
                CombatPathBudgetHelper.Checkpoint();
                        if(++pathChecks>16)return false;
                        using(var enemyPath=CombatPathBudgetHelper.Query(pursuer,pursuer.Position,cell,PathEndMode.Touch))
                        {
                            if(!enemyPath.Found){after=0;break;}
                            // Every fallback must avoid pulling the observed
                            // pursuer through a stationary selected ally. A
                            // distant escape is not safe team support merely
                            // because the mover itself gains contact time.
                            if(map.mapPawns.FreeColonistsSpawned.Any(g=>g!=pawn && Eligible(g)
                                && g.CurJobDef!=JobDefOf.Goto && !g.Position.InHorDistOf(pursuer.Position,2.1f)
                                && enemyPath.NodesReversed.Any(c=>c.InHorDistOf(g.Position,1.5f))))
                            {after=0;break;}
                            after=Math.Min(after,enemyPath.TotalCost+CombatInterceptHelper.MovementLockTicks(pursuer)
                                -path.TotalCost-ownLock);
                        }
                    }
                    bool actualCover=covering.Any(g=>pursuers.Any(t=>AimTarget(g)==t));
                    // A healthy gun with a legal current shot loses all firing
                    // time spent moving. Compare both stationary windows with
                    // native Touch paths, rather than an approximate distance
                    // before moving against a path cost after moving. Actual
                    // same-pursuer cover and clinical escapes keep their rules.
                    if(preserveShot && !actualCover)
                    {
                        if(!stationaryContact.HasValue)
                        {
                            float baseline=float.MaxValue;
                            foreach(var pursuer in pursuers)
                            {
                CombatPathBudgetHelper.Checkpoint();
                                using(var currentPath=CombatPathBudgetHelper.Query(pursuer,pursuer.Position,pawn.Position,PathEndMode.Touch))
                                {
                                    if(!currentPath.Found){baseline=float.NaN;break;}
                                    baseline=Math.Min(baseline,currentPath.TotalCost+CombatInterceptHelper.MovementLockTicks(pursuer));
                                }
                            }
                            stationaryContact=baseline;
                        }
                        if(!CombatInterceptMath.StationaryShotGain(stationaryContact.Value,after,ownLock))
                        {
#if LAYA_COMBAT_LAB
                            if(EscapeWindowRefusals.Count<128)EscapeWindowRefusals.Add(new{tick=Find.TickManager.TicksGame,
                                pawn=pawn.thingIDNumber,target=target?.thingIDNumber,reason="uncovered_current_shot_window",
                                before,stationary_contact=stationaryContact.Value,after,cycle,path_cost=path.TotalCost,own_lock=ownLock,
                                stationary_firing_window=stationaryContact.Value-ownLock,
                                actual_cover=actualCover,goal_x=cell.x,goal_z=cell.z});
#endif
                            continue;
                        }
                    }
                    if(!CombatInterceptMath.UsefulEscape(before,after,cycle,actualCover,path.TotalCost+ownLock))
                    {
#if LAYA_COMBAT_LAB
                        if(EscapeWindowRefusals.Count<128)EscapeWindowRefusals.Add(new{tick=Find.TickManager.TicksGame,
                            pawn=pawn.thingIDNumber,target=target?.thingIDNumber,before,after,cycle,
                            path_cost=path.TotalCost,own_lock=ownLock,cover=covering.Select(g=>g.thingIDNumber).ToArray(),actual_cover=actualCover});
#endif
                        continue;
                    }
                }
                if(KeepGroupPosition(pawn,cell))continue; // Review before cancelling the exact arrival shot.
                var move=JobMaker.MakeJob(JobDefOf.Goto,cell);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                // A verified emergency escape must interrupt aiming. Otherwise
                // the move can wait behind the very shot that contact prevents.
                pawn.stances.CancelBusyStanceSoft();
                if(pawn.CurJobDef==JobDefOf.AttackStatic)
                    {CombatOrderHelper.DropQueued(pawn);pawn.jobs.EndCurrentJob(JobCondition.InterruptForced,false);}
                if(!CombatOrderHelper.Take(pawn,ref move))continue;
                Job shot=null;
                if(target!=null)
                {
                    shot=CombatOrderHelper.QueueShot(pawn,target);
                }
                move=RememberMove(pawn,move,shot);
                if(Plans.TryGetValue(pawn.thingIDNumber,out var selectedPlan))
                {
                    selectedPlan.LastMoveTick=Find.TickManager.TicksGame;
                    selectedPlan.RangedWithdrawal=new CombatJobStamp(move);
                }
                RetreatJobs[pawn]=new CombatJobStamp(move);issued=move;
#if LAYA_COMBAT_LAB
                if(RetreatPostReviews.Count<64)RetreatPostReviews.Add(new{tick=Find.TickManager.TicksGame,
                    pawn=pawn.thingIDNumber,target=target?.thingIDNumber,x=pawn.Position.x,z=pawn.Position.z,
                    goal_x=cell.x,goal_z=cell.z,actual_pursuit=actualPursuit,
                    covering=covering.Select(g=>g.thingIDNumber).ToArray(),
                    close_cover=covering.Where(g=>cell.InHorDistOf(g.Position,4f)
                        && VerbUtility.InterceptChanceFactorFromDistance(cell.ToVector3Shifted(),g.Position)==0f).Select(g=>g.thingIDNumber).ToArray(),
                    accepted_job=move.loadID,queued_target=shot?.targetA.Thing?.thingIDNumber,
                    health=pawn.health.summaryHealth.SummaryHealthPercent,
                    meaning="Accepted ordinary retreat and observed gun geometry; no assumed enemy retarget or shot outcome"});
                Retreated++;
#endif
                return true;
            }
            return false;
        }
        private static bool SelectedMeleeLine(Plan plan,List<Pawn> threats,Pawn[] guns)
        {
            var pawn=plan.Pawn;var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            return DefensivePlan(plan.Tactic) && verb!=null && threats.Any()
                && threats.All(t=>t.RaceProps.Humanlike && t.equipment?.Primary?.def.IsRangedWeapon!=true)
                && pawn.health.summaryHealth.SummaryHealthPercent>=.85f && pawn.health.hediffSet.BleedRateTotal==0f
                && pawn.health.capacities.GetLevel(PawnCapacityDefOf.Moving)>=.85f
                && pawn.health.capacities.GetLevel(PawnCapacityDefOf.Consciousness)>=.85f
                && pawn.health.capacities.GetLevel(PawnCapacityDefOf.Manipulation)>=.75f
                && (pawn.needs?.food?.CurLevelPercentage ?? 1f)>=.15f && (pawn.needs?.rest?.CurLevelPercentage ?? 1f)>=.15f
                && !pawn.Position.ContainsStaticFire(pawn.Map)
                && pawn.Map.gasGrid.DensityAt(pawn.Position,GasType.ToxGas)==0
                && pawn.Map.gasGrid.DensityAt(pawn.Position,GasType.DeadlifeDust)==0
                && verb.verbProps.defaultProjectile?.projectile is ProjectileProperties projectile
                && projectile.explosionRadius<=0f && projectile.damageDef!=DamageDefOf.Flame
                && guns.Count(g=>g.Position.InHorDistOf(pawn.Position,12f)
                    && (g.CurJobDef==JobDefOf.AttackStatic || g.CurJobDef==JobDefOf.Wait_Combat))>=3
                && threats.Any(t=>verb.CanHitTargetFrom(pawn.Position,t)
                    && CombatInterceptHelper.FriendlyLaneClear(pawn,t,pawn.Position));
        }
        private static bool RecentCover(Pawn gun,Pawn enemy)
        {
            var verb=gun.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            return gun.CurJobDef!=JobDefOf.Goto && verb!=null && AimTarget(gun)==enemy
                && (gun.stances.curStance is Stance_Cooldown || verb.state==VerbState.Bursting)
                && CombatInterceptHelper.CanShootNow(gun,enemy);
        }
        private static bool RotateFastCoveredBait(Plan[] plans,List<Pawn> threats)
        {
            if(plans.Length<3)return false;
            if(plans.Any(p=>p.FastBait?.Value==p.Pawn.CurJob && p.Pawn.CurJobDef==JobDefOf.Goto
                && MovingOrBusy(p.Pawn) && Threat(p.Target) && CombatInterceptHelper.Pursuing(p.Target,p.Pawn)))return true;
            int tick=Find.TickManager.TicksGame;
            if(plans.Count(p=>p.Pawn.CurJobDef==JobDefOf.Goto && MovingOrBusy(p.Pawn))>1)return false;
            foreach(var plan in plans.OrderByDescending(p=>Speed(p.Pawn)))
            {
                CombatPathBudgetHelper.Checkpoint();
                var pawn=plan.Pawn;
                if(plan.Mode!="shoot" || pawn.CurJob!=plan.OwnedJob || pawn.jobs.jobQueue.Any()
                    || pawn.CurJobDef!=JobDefOf.AttackStatic && pawn.CurJobDef!=JobDefOf.Wait_Combat
                    || pawn.health.summaryHealth.SummaryHealthPercent<.9f || pawn.health.hediffSet.BleedRateTotal>0f
                    || CriticalRangedInjury(pawn) || tick<plan.FastBaitReviewTick
                    || MedicalReady(pawn) && plans.Count(p=>MedicalReady(p.Pawn))<2)continue;
                var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
                if(verb==null || verb.state==VerbState.Bursting)continue;
                var near=threats.Where(MeleeThreat).Where(t=>t.Position.InHorDistOf(pawn.Position,20f)).ToArray();
                if(!near.Any())continue;
                var enemy=near.Where(t=>CombatInterceptHelper.Pursuing(t,pawn))
                    .OrderBy(t=>CombatInterceptHelper.ContactTicks(t,pawn)).FirstOrDefault();
                if(enemy==null)continue;
                var cover=CombatInterceptHelper.ReadyCover(pawn,enemy).Where(g=>RecentCover(g,enemy)).ToArray();
                float fastest=near.Max(Speed);
                if(!CombatInterceptMath.FastCoveredBait(true,Speed(pawn),fastest,cover.Length))continue;
                plan.FastBaitReviewTick=tick+30;
                if(!TryRangedRetreat(pawn,enemy,plan.Anchor,out var move,true))continue;
                plan.OwnedJob=move;plan.QueuedShot=SelectedMoves[pawn].Value;plan.Target=enemy;plan.Mode="retreat";
                plan.LastMoveTick=tick;plan.FastBait=new CombatJobStamp(move);plan.FastBaitCover=cover.Select(g=>g.thingIDNumber).ToArray();
#if LAYA_COMBAT_LAB
                if(FastBaitEvents.Count<128)FastBaitEvents.Add(new{tick,pawn=pawn.thingIDNumber,target=enemy.thingIDNumber,
                    actor_speed=Speed(pawn),fastest_melee=fastest,cover=plan.FastBaitCover,
                    cover_stances=cover.Select(g=>g.stances.curStance.GetType().Name).ToArray(),
                    x=pawn.Position.x,z=pawn.Position.z,goal_x=move.targetA.Cell.x,goal_z=move.targetA.Cell.z,
                    interpretation="Checked faster retreat under recent same-enemy fire; AI pursuit and continued cover remain observed outcomes"});
#endif
                return true;
            }
            return false;
        }
        private static bool MedicalTurnPending(Plan plan,List<Pawn> threats,Pawn[] guns)
        {
            var pawn=plan.Pawn;
            if(!MedicalReady(pawn) || plan.Mode!="shoot" || pawn.CurJob!=plan.OwnedJob
                || pawn.jobs.jobQueue.Any()
                || pawn.CurJobDef!=JobDefOf.AttackStatic && pawn.CurJobDef!=JobDefOf.Wait_Combat
                || !SelectedMeleeLine(plan,threats,guns))return false;
            var enemy=threats.Where(t=>MeleeThreat(t) && CombatInterceptHelper.Pursuing(t,pawn))
                .OrderBy(t=>CombatInterceptHelper.ContactTicks(t,pawn)).FirstOrDefault();
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(enemy==null || verb==null)return false;
            float cycle=verb.verbProps.warmupTime*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor)
                +Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots
                +pawn.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f;
            // Reserve the next available turn even while the doctor's current
            // burst finishes. No burst is cancelled and no route is assumed.
            return CombatInterceptMath.EarlyLineRotation(CombatInterceptHelper.ContactTicks(enemy,pawn),
                cycle,8f/Math.Max(.1f,Speed(pawn))*60f,false,false,false,true);
        }
        private static void RotateSelectedLines()
        {
            foreach(var group in Plans.Values.Where(Valid).GroupBy(p=>p.Pawn.Map).ToArray())
            {
                CombatPathBudgetHelper.Checkpoint();
                var plans=group.ToArray();var guns=plans.Select(p=>p.Pawn).ToArray();
                var threats=group.Key.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
                if(RotateFastCoveredBait(plans,threats))continue;
                if(guns.Length<3 || guns.Any(OtherSelectedGunMoving))continue;
                bool medicalTurnPending=plans.Any(p=>MedicalTurnPending(p,threats,guns));
                // The front gun's escape deadline precedes the medical role.
                // Serial doctor-first moves left a two-pursuer gun holding its
                // line until contact. Keep one moving gun and use the medical
                // role only to break equal observed contact deadlines.
                foreach(var plan in plans.OrderBy(p=>threats.Where(t=>MeleeThreat(t)
                        && CombatInterceptHelper.Pursuing(t,p.Pawn))
                        .Select(t=>CombatInterceptHelper.ContactTicks(t,p.Pawn)).DefaultIfEmpty(float.PositiveInfinity).Min())
                    .ThenByDescending(p=>MedicalReady(p.Pawn)))
                {
                    var pawn=plan.Pawn;
                    if(plan.Mode!="shoot" || pawn.CurJob!=plan.OwnedJob || pawn.jobs.jobQueue.Any()
                        || pawn.CurJobDef!=JobDefOf.AttackStatic && pawn.CurJobDef!=JobDefOf.Wait_Combat
                        || !SelectedMeleeLine(plan,threats,guns))continue;
                    var enemy=threats.Where(t=>MeleeThreat(t) && CombatInterceptHelper.Pursuing(t,pawn))
                        .OrderBy(t=>CombatInterceptHelper.ContactTicks(t,pawn)).FirstOrDefault();
                    if(enemy==null)continue;
                    var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
                    float cycle=verb.verbProps.warmupTime*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor)
                        +Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots
                        +pawn.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f;
                    float contact=CombatInterceptHelper.ContactTicks(enemy,pawn),margin=8f/Math.Max(.1f,Speed(pawn))*60f;
                    bool doctor=MedicalReady(pawn),warming=pawn.stances.curStance is Stance_Warmup;
                    int remainingWarmup=(pawn.stances.curStance as Stance_Warmup)?.ticksLeft ?? 0;
                    var aimed=AimTarget(pawn);
                    bool usefulAim=aimed!=null && Threat(aimed)
                        && verb.CanHitTargetFrom(pawn.Position,aimed)
                        && CombatInterceptHelper.FriendlyLaneClear(pawn,aimed,pawn.Position);
                    bool usefulWarmup=warming && usefulAim;
                    if(usefulAim && CombatInterceptMath.DeferForMedicalTurn(medicalTurnPending,doctor,contact,
                        warming?remainingWarmup:verb.verbProps.warmupTime*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor),
                        Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots,
                        pawn.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f,
                        CombatInterceptHelper.MovementLockTicks(pawn),warming,margin))continue;
                    if(usefulWarmup && CombatInterceptMath.MedicVolleyThenEscape(contact,remainingWarmup,
                        Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots,
                        pawn.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f,
                        CombatInterceptHelper.MovementLockTicks(pawn),true,margin))continue;
                    // Preserve a capable doctor before all front guns enter
                    // melee. A cancellable warmup may yield to that measured
                    // rotation; a committed burst still cannot. The retreat
                    // must independently prove a safe path and useful firing
                    // time after arrival, without inventing covering fire.
                    bool yieldWarmup=CombatInterceptMath.YieldLineWarmup(contact,remainingWarmup,
                        Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots,
                        pawn.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f,
                        margin,warming,verb.state==VerbState.Bursting);
                    if(!CombatInterceptMath.EarlyLineRotation(contact,cycle,margin,false,
                        warming,verb.state==VerbState.Bursting,doctor || yieldWarmup))continue;
                    // The existing native path check must still prove a useful
                    // post-arrival shot window or actual same-pursuer cover.
                    // Merely belonging to this line does not supply that cover.
                    if(!TryRangedRetreat(pawn,enemy,plan.Anchor,out var retreat))continue;
                    plan.OwnedJob=retreat;plan.QueuedShot=SelectedMoves[pawn].Value;
                    plan.Target=enemy;plan.Mode="retreat";plan.LastMoveTick=Find.TickManager.TicksGame;
#if LAYA_COMBAT_LAB
                    if(EarlyRotationEvents.Count<128)EarlyRotationEvents.Add(new{tick=Find.TickManager.TicksGame,
                        pawn=pawn.thingIDNumber,target=enemy.thingIDNumber,doctor,contact,cycle,
                        medical_turn_pending=medicalTurnPending,escape_margin=margin,
                        warmup_yield=warming,remaining_warmup=remainingWarmup,
                        x=pawn.Position.x,z=pawn.Position.z,goal_x=retreat.targetA.Cell.x,goal_z=retreat.targetA.Cell.z,
                        queued_shot=plan.QueuedShot?.targetA.Thing?.thingIDNumber});
#endif
                    break; // Keep the other selected guns at their current tasks.
                }
            }
        }
        public static void Tick()
        {
            if(Find.TickManager==null || Find.TickManager.TicksGame%15!=0)return;
            using(CombatPathBudgetHelper.Begin("Tick",8))
                try {TickBudgeted();} catch(CombatReviewDeferredException) {}
        }
        private static void TickBudgeted()
        {
#if LAYA_COMBAT_LAB
            if(TestDisabled)return;
#endif
            if(Find.TickManager==null || Find.TickManager.TicksGame%15!=0)return;
#if LAYA_COMBAT_LAB
            PulseTicks++;
#endif
            CombatContactHelper.Tick();
            CombatOrderHelper.Prune();
            PruneDoctorDetours();
            PruneDoctorBounds();
            foreach(var pawn in SelectedMoves.Keys.ToArray())
                if(!pawn.Spawned || pawn.Dead || !Present(pawn,SelectedMoves[pawn].Key) && !Present(pawn,SelectedMoves[pawn].Value))
                {SelectedMoves.Remove(pawn);RetreatJobs.Remove(pawn);AssemblyAnchors.Remove(pawn);}
            // ThreatsClear and exact job/clinical/route guards remain mandatory.
            // First care must get the unchanged pulse budget before optional
            // geometry can defer the remainder of a postcombat review.
            TryTeamFirstCare();
            ReviewImmediateTeamDanger();
            // An observed sole carrier has a finite exit deadline. At most two
            // selected actors get a four-query page before optional geometry.
            ReviewCarrierDeparturePages();
            ReviewPhysicianFireReturn();
            ReviewDoctorPreposition();
            ReviewFireDoctorGuard(true);
            PrepareOpeningCohortCover();
            ReviewCoordinatedFire();
            // A measured short shelter window must be reviewed before the
            // long fallback search spends the finite path budget. This is one
            // owned, checked movement transaction; the other guns retain fire.
            ReviewShortRangedScreen();
            // A deadline exit must receive the unchanged finite path budget
            // before optional formation/range-post search can defer the pulse.
            // A healthy melee formation has one optional movement coordinator.
            // Immediate danger/critical clinical changes keep guard-first order.
            bool cohortFirst=PrioritizeMeleeCohort();
            if(cohortFirst)ReviewFallbackCohorts();
            CohortTrace("before_deadline_guard");
            ReviewFireDoctorGuard();
            CohortTrace("after_deadline_guard");
            if(!cohortFirst)ReviewFallbackCohorts();
            CohortTrace("after_cohort_review");
            ReviewCoverTurns();
            // Preserve melee arbitration without paying for an inapplicable
            // range phase. An inert cohort must still not veto a map with an
            // actually observed ranged threat. The reviewer checks its own
            // jobs, movement, cover and routes before any reassignment.
            if(FallbackCohorts.Count==0 || Plans.Values.Where(Valid).Select(p=>p.Pawn.Map).Distinct()
                .Any(map=>map.mapPawns.AllPawnsSpawned.Any(t=>Threat(t)
                    && t.equipment?.Primary?.def.IsRangedWeapon==true)))ReviewObservedRangePosts();
            foreach(var pair in Plans.OrderBy(x=>x.Value.DefenseReviewTick).ThenBy(x=>x.Key).ToList())
            {
                CombatPathBudgetHelper.Checkpoint();
                var plan=pair.Value;Pawn pawn=plan.Pawn;
                plan.DefenseReviewTick=Find.TickManager.TicksGame;
                if(!Valid(plan)){Plans.Remove(pair.Key);RetreatJobs.Remove(pawn);SelectedMoves.Remove(pawn);AssemblyAnchors.Remove(pawn);continue;}
                if(plan.ProgressCell!=pawn.Position){plan.ProgressCell=pawn.Position;plan.ProgressTick=Find.TickManager.TicksGame;}
                if(DoctorDetours.ContainsKey(pawn)
                    && ReviewDoctorDetour(plan,pawn.Map.mapPawns.AllPawnsSpawned.Where(Threat).ToList()))continue;
                if(pawn.CurJob==plan.QueuedShot && Present(pawn,plan.QueuedShot))
                {
                    plan.OwnedJob=plan.QueuedShot;plan.QueuedShot=null;
                    plan.Target=pawn.CurJob.targetA.Thing as Pawn;plan.Mode="shoot";
                }
                // The native ordered-job tracker may copy a Goto. Its reference
                // then differs despite the same forced waypoint and retained
                // selected shot. A cleared queue or changed destination remains
                // a new external intent and must cancel the previous plan.
                if(pawn.CurJob!=plan.OwnedJob && pawn.CurJobDef==JobDefOf.Goto && plan.OwnedJob?.def==JobDefOf.Goto
                    && pawn.CurJob.playerForced && pawn.CurJob.targetA.Cell==plan.OwnedJob.targetA.Cell
                    && pawn.CurJob.locomotionUrgency==plan.OwnedJob.locomotionUrgency && plan.QueuedShot!=null)
                {
                    var retainedShot=pawn.jobs.jobQueue.Select(q=>q.job).FirstOrDefault(j=>j.def==JobDefOf.AttackStatic
                        && j.playerForced && j.targetA.Thing==plan.QueuedShot.targetA.Thing);
                    if(retainedShot!=null)
                    {
                        plan.OwnedJob=pawn.CurJob;plan.QueuedShot=retainedShot;
                        RememberMove(pawn,pawn.CurJob,retainedShot);
                        if(plan.Mode=="retreat")RetreatJobs[pawn]=new CombatJobStamp(pawn.CurJob);
                    }
                }
                // A validated API move/shot pair can replace the previous
                // waypoint between pulses. Retain that known selected pair;
                // unrelated/manual jobs have no entry in SelectedMoves.
                if(pawn.CurJob!=plan.OwnedJob && SelectedMoves.TryGetValue(pawn,out var moved)
                    && pawn.CurJob==moved.Key && moved.Value!=null && Present(pawn,moved.Value))
                {
                    plan.OwnedJob=moved.Key;plan.QueuedShot=moved.Value;plan.Target=moved.Value.targetA.Thing as Pawn;
                    plan.Mode=RetreatJobs.TryGetValue(pawn,out var retreatMove) && retreatMove.Value==moved.Key?"retreat":"position";
                }
                // A new external job cancels ownership. Native queued shots and
                // the engine's idle post-job transition remain part of the plan.
                bool queuedShot=Present(pawn,pawn.CurJob) && (pawn.CurJob==plan.QueuedShot
                    || pawn.CurJobDef==JobDefOf.AttackStatic && pawn.CurJob?.targetA.Thing==plan.Target);
                bool pendingMove=Present(pawn,plan.OwnedJob) && pawn.jobs.jobQueue.Any(q=>q.job==plan.OwnedJob);
                bool idle=pawn.CurJobDef==JobDefOf.Wait_Combat || pawn.CurJobDef==JobDefOf.Wait_MaintainPosture;
                if(pawn.CurJob!=plan.OwnedJob && !queuedShot && !idle && !pendingMove){Plans.Remove(pair.Key);
#if LAYA_COMBAT_LAB
                    Cancelled++;
                    if(CancelledEvents.Count<128)CancelledEvents.Add(new{tick=Find.TickManager.TicksGame,pawn=pawn.thingIDNumber,
                        current=pawn.CurJobDef?.defName,current_forced=pawn.CurJob?.playerForced,current_target=pawn.CurJob?.targetA.Thing?.thingIDNumber,
                        current_urgency=pawn.CurJob?.locomotionUrgency.ToString(),owned=plan.OwnedJob?.def?.defName,
                        owned_target=plan.OwnedJob?.targetA.Thing?.thingIDNumber,mode=plan.Mode,tactic=plan.Tactic,
                        current_cell=pawn.CurJob?.targetA.Cell.ToString(),owned_cell=plan.OwnedJob?.targetA.Cell.ToString(),
                        selected_is_current=SelectedMoves.TryGetValue(pawn,out var known) && known.Key==pawn.CurJob,
                        queued=pawn.jobs.jobQueue.Select(q=>new{job=q.job.def.defName,target=q.job.targetA.Thing?.thingIDNumber}).ToArray()});
#endif
                    continue;}
                if(pendingMove)continue;
                var threats=pawn.Map.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
                if(!threats.Any())continue;
                if(ContactDefence(plan,threats))continue;
                if(ReviewCohortMember(plan,threats))continue;
                if(ReviewFocusedRangedThreat(plan,threats))continue;
                if(KeepCoverTurnPlan(plan,threats))continue;
                ReviewPursuedApproach(plan);
                if(ReviewCarrierVolley(plan,threats))continue;
                if(ReviewUnsafeFriendlyLane(plan,threats))continue;
                if(PreserveTeamApproach(plan,threats))continue;
                var activeVerb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
                // A native burst already in progress is a short commitment.
                // Replacing AttackStatic with Goto here used to cut that burst
                // before the later aim-preservation check could run.
                if(activeVerb?.state==VerbState.Bursting && AimTarget(pawn) is Pawn burstingTarget
                    && Threat(burstingTarget) && CombatInterceptHelper.FriendlyLaneClear(pawn,burstingTarget,pawn.Position))continue;
                // Recheck a newly observed pickup/escape before finishing an
                // older generic rally waypoint. A useful active warmup stays.
                if(TryCarrierAdvance(plan,threats))continue;
                if(plan.Mode=="assembly" && plan.OwnedJob?.def==JobDefOf.Goto && pawn.CurJob==plan.OwnedJob && MovingOrBusy(pawn)
                    && threats.All(t=>pawn.Position.DistanceTo(t.Position)>6f)
                    && !plan.OwnedJob.targetA.Cell.ContainsStaticFire(pawn.Map))continue;
                // A pursuer switching to a nearby ally changes the escape's
                // purpose. Review a safe covering angle before finishing a
                // now unnecessary retreat behind that ally's body. The support
                // move still checks this gun's own pursuers and firing cycle.
                if(plan.Mode=="retreat" && threats.Any(t=>MeleeThreat(t) && ObservedVictim(t) is Pawn endangeredAlly
                    && endangeredAlly!=pawn && !endangeredAlly.Downed && t.Position.InHorDistOf(endangeredAlly.Position,8f))
                    && TryContactSupport(plan,threats))continue;
                if(TryReleaseCompletedEscape(plan,threats))continue;
                if(ReviewRangedWithdrawal(plan,threats))continue;
                if(plan.Mode=="retreat" && pawn.CurJob==plan.OwnedJob && MovingOrBusy(pawn) && !StuckAtContact(plan))continue;
                if(HoldingRecovery(plan,plan.Tactic))continue; // Short shelter window for a fresh clinical decision.
                if(TryBreakRangedContact(plan,threats))continue;
                if(TryContactSupport(plan,threats))continue;
                var melee=threats.Where(t=>ClosingMelee(t,pawn))
                    .OrderBy(t=>CombatInterceptHelper.ContactTicks(t,pawn))
                    .ThenBy(t=>pawn.Position.DistanceToSquared(t.Position)).FirstOrDefault();
                var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
                float warmup=(pawn.stances.curStance as Stance_Warmup)?.ticksLeft
                    ?? (verb?.verbProps.warmupTime ?? 0)*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor);
                float contact=melee==null?9999f:CombatInterceptHelper.ContactTicks(melee,pawn);
                float headstart=6f/Math.Max(.1f,Speed(pawn))*60f;
                float cooldown=pawn.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f;
                float burst=Math.Max(0,(verb?.verbProps.burstShotCount ?? 1)-1)*(verb?.verbProps.ticksBetweenBurstShots ?? 0);
                float locked=(pawn.stances.curStance as Stance_Busy)?.ticksLeft ?? 0;
                var guns=Plans.Values.Where(Valid).Select(p=>p.Pawn).Where(p=>p.Map==pawn.Map).ToArray();
                bool firstInApproach=melee!=null && !(melee.CurJob?.targetA.Thing is Pawn victim && victim.Faction==Faction.OfPlayer)
                    && guns.OrderBy(g=>g.Position.DistanceToSquared(melee.Position)).ThenBy(g=>g.thingIDNumber).FirstOrDefault()==pawn;
                bool pursued=melee!=null && (CombatInterceptHelper.Pursuing(melee,pawn) || firstInApproach);
                var covering=melee==null?new List<Pawn>():CombatInterceptHelper.ReadyCover(pawn,melee);
                bool cooperativeFinish=pursued && covering.Count>=2 && pawn.health.hediffSet.BleedRateTotal==0f
                    && pawn.health.summaryHealth.SummaryHealthPercent>=.85f
                    && pawn.health.capacities.GetLevel(PawnCapacityDefOf.Moving)>=.85f
                    && IncomingRangedExposure(pawn,pawn.Position)<=.6f;
                // Honor a selected covered firing line while two actual guns
                // are committed to this observed pursuer. An early peel here
                // removed the short-range gun during its first cooldown and
                // left the front guns without its following volley.
                int committedCover=covering.Count(g=>g.stances.curStance is Stance_Busy busy
                    && busy.verb==g.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb && busy.focusTarg.Thing==melee);
                bool supportedLine=cooperativeFinish && DefensivePlan(plan.Tactic)
                    && CombatInterceptHelper.Pursuing(melee,pawn)
                    && CombatInterceptHelper.CanShootNow(pawn,melee)
                    && committedCover>=2;
                // A selected firing line is not a lure. Against an observed
                // human melee assault, a healthy formed group can keep its
                // current legal fire instead of every gun peeling after its
                // first cooldown. Contact defence still runs before this.
                bool selectedMeleeLine=melee!=null && SelectedMeleeLine(plan,threats,guns);
#if LAYA_COMBAT_LAB
                if(supportedLine)LineHeld++;
                if(selectedMeleeLine)SelectedLineHeld++;
                int lineTick=Find.TickManager.TicksGame;
                if(melee!=null && pursued && contact<500 && LineWindowChecks.Count<128
                    && (!LastLineCheck.TryGetValue(pawn.thingIDNumber,out int priorLineTick) || lineTick-priorLineTick>=60))
                {
                    LastLineCheck[pawn.thingIDNumber]=lineTick;
                    LineWindowChecks.Add(new{tick=lineTick,pawn=pawn.thingIDNumber,target=melee.thingIDNumber,tactic=plan.Tactic,
                        contact,actual_pursuit=CombatInterceptHelper.Pursuing(melee,pawn),ready_cover=covering.Count,
                        committed_cover=committedCover,cooperative=cooperativeFinish,own_shot=CombatInterceptHelper.CanShootNow(pawn,melee),
                        physical_cover=CoverUtility.CalculateOverallBlockChance(pawn,melee.Position,pawn.Map),
                        health=pawn.health.summaryHealth.SummaryHealthPercent,bleeding=pawn.health.hediffSet.BleedRateTotal,
                        ranged_exposure=IncomingRangedExposure(pawn,pawn.Position),held=supportedLine,selected_line=selectedMeleeLine});
                }
#endif
                // Peel one actually covered gun before its head start expires.
                // Waiting for the last supported volley kept every gun on the
                // front until the next movement order was already too late.
                if(cooperativeFinish && !supportedLine && !selectedMeleeLine
                    && CombatInterceptMath.EarlyCoveredPeel(contact,warmup+burst+cooldown,
                        8f/Math.Max(.1f,Speed(pawn))*60f,covering.Count,OtherSelectedGunMoving(pawn),
                        CombatInterceptHelper.DefendedApproach(pawn,melee),pawn.stances.curStance is Stance_Warmup,
                        CombatInterceptHelper.CanShootNow(pawn,melee))
                    && TryRangedRetreat(pawn,melee,plan.Anchor,out var earlyRetreat))
                {plan.OwnedJob=earlyRetreat;plan.QueuedShot=SelectedMoves[pawn].Value;plan.Target=melee;
                    plan.Mode="retreat";plan.LastMoveTick=Find.TickManager.TicksGame;continue;}
                // A selected gun can finish a short volley under actual same-target
                // cover. Requiring every pursued gun to leave at once stopped all
                // useful fire against a melee rush. This still needs an observed
                // firing window; aimed/queued orders alone are not covering guns.
                bool supported=melee!=null && (!pursued && covering.Any() || cooperativeFinish)
                    && CombatInterceptHelper.CanShootNow(pawn,melee) && contact>Math.Max(warmup+burst,locked)+30f;
                // Keep a measured complete volley and its native cooldown when
                // they still fit before contact. Demanding another six cells
                // of unused head start made every gun retreat after one burst.
                // A gun covering someone else's pursuer is itself the cover;
                // it need not wait for a third gun to begin firing first.
                bool finishVolley=melee!=null && plan.Tactic!="withdraw_and_regroup"
                    && pawn.health.summaryHealth.SummaryHealthPercent>=.85f && pawn.health.hediffSet.BleedRateTotal==0f
                    && pawn.health.capacities.GetLevel(PawnCapacityDefOf.Moving)>=.85f
                    && IncomingRangedExposure(pawn,pawn.Position)<=.6f
                    && CombatInterceptHelper.CanShootNow(pawn,melee)
                    && CombatInterceptMath.FinishVolley(contact,warmup,burst,cooldown,locked,pawn.stances.curStance is Stance_Warmup);
                // A checked corridor or supported selected cover can sustain
                // the line; unsupported or wounded guns retain escape checks.
                bool holdLine=supportedLine || selectedMeleeLine || melee!=null && new[]{"stationary_fire","focus_fire","hold_cover","firing_line","fallback_line"}.Contains(plan.Tactic)
                    && pawn.health.hediffSet.BleedRateTotal==0f && pawn.health.summaryHealth.SummaryHealthPercent>=.85f
                    && pawn.health.capacities.GetLevel(PawnCapacityDefOf.Moving)>=.85f
                    && CombatInterceptHelper.DefendedApproach(pawn,melee) && CombatInterceptHelper.ReadyCover(pawn,melee).Any();
                if(melee!=null && !supported && !finishVolley && !holdLine && contact<CombatInterceptMath.ShotCommitment(warmup,burst,cooldown,headstart+30f,locked))
                {
                    // Keep an owned safe retreat waypoint instead of replacing
                    // it every quarter second and never reaching the shot.
                    if(plan.Mode=="retreat" && pawn.CurJob==plan.OwnedJob && pawn.CurJobDef==JobDefOf.Goto
                        && MovingOrBusy(pawn) && !StuckAtContact(plan))continue;
                    if(TryRangedRetreat(pawn,melee,plan.Anchor,out var retreat))
                    {plan.OwnedJob=retreat;plan.QueuedShot=SelectedMoves[pawn].Value;plan.Target=melee;plan.Mode="retreat";plan.LastMoveTick=Find.TickManager.TicksGame;continue;}
                }
                if(plan.Mode=="contact" && pawn.CurJob==plan.OwnedJob && pawn.CurJobDef==JobDefOf.AttackMelee
                    && (plan.Target==null || !Threat(plan.Target) || pawn.Position.DistanceTo(plan.Target.Position)>1.5f))
                {CombatOrderHelper.DropQueued(pawn);pawn.jobs.EndCurrentJob(JobCondition.InterruptForced,false);plan.OwnedJob=pawn.CurJob;plan.Mode="shoot";}
                // Finish the selected firing approach. A newly visible target
                // must not discard a valid waypoint every quarter second.
                if(TryFinishFiringApproach(plan,threats))continue;
                if(pawn.CurJob==plan.OwnedJob && pawn.CurJobDef==JobDefOf.Goto && MovingOrBusy(pawn))continue;
                Pawn target=finishVolley && !pursued ? melee:GroupTarget(pawn,threats,plan.Target);
                if(KeepTransferredCover(pawn,target))continue;
                // Preserve aim unless a different observed melee attacker now
                // reaches the selected firing group sooner than this target.
                if((pawn.stances.curStance is Stance_Warmup || verb?.state==VerbState.Bursting)
                    && (pawn.CurJobDef==JobDefOf.AttackStatic || pawn.CurJobDef==JobDefOf.Wait_Combat))
                {
                    var aimed=AimTarget(pawn);
                    bool currentShot=aimed!=null && Threat(aimed) && verb?.CanHitTargetFrom(pawn.Position,aimed)==true
                        && CombatInterceptHelper.FriendlyLaneClear(pawn,aimed,pawn.Position);
                    bool abductionSwitch=target!=null && target!=aimed && CombatNativeHelper.AbductionThreat(target)
                        && (aimed==null || !CombatNativeHelper.AbductionThreat(aimed));
                    // Complete an actual useful warmup before re-ranking other
                    // threatened allies. Swing cooldowns and small priority
                    // changes must not repeatedly reset the only covering gun.
                    if(currentShot && !abductionSwitch)
                    {
#if LAYA_COMBAT_LAB
                        WarmupsKept++;
#endif
                        continue;
                    }
                    if(verb?.state==VerbState.Bursting)continue; // Already committed projectiles keep their native burst.
#if LAYA_COMBAT_LAB
                    if(WarmupCuts.Count<128)WarmupCuts.Add(new{tick=Find.TickManager.TicksGame,pawn=pawn.thingIDNumber,
                        aimed=aimed?.thingIDNumber,next=target?.thingIDNumber,current_shot=currentShot,
                        abduction_switch=abductionSwitch,remaining=(pawn.stances.curStance as Stance_Warmup)?.ticksLeft});
#endif
                    pawn.stances.CancelBusyStanceSoft();CombatOrderHelper.DropQueued(pawn);pawn.jobs.EndCurrentJob(JobCondition.InterruptForced,false);plan.OwnedJob=pawn.CurJob;
                }
                if(target==null){TryCoverObservedBreach(plan,threats);continue;}
                if(new[]{"hold_cover","firing_line","focus_fire","fallback_line","spread_out","stationary_fire"}.Contains(plan.Tactic)
                    && TryTakeCoveredShot(plan,target))continue;
                if(pawn.CurJobDef==JobDefOf.AttackStatic && pawn.CurJob?.targetA.Thing==target)continue;
                var attack=JobMaker.MakeJob(JobDefOf.AttackStatic,target);attack.playerForced=true;
                if(CombatOrderHelper.Take(pawn,ref attack))
                {plan.OwnedJob=attack;plan.Target=target;plan.Mode="shoot";}
            }
            // Optional support angles cannot precede deadline safety. The
            // outer shared path/time budget remains unchanged.
            ReviewTeamHandoffs();
            RotateSelectedLines();
        }
    }
    public class CombatControlComponent : GameComponent
    {
        public CombatControlComponent(Game game){}
        public override void GameComponentTick(){CombatControlHelper.Tick();}
    }
}

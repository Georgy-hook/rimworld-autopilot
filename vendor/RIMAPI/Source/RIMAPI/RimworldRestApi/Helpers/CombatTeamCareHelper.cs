using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;
using RIMAPI.Models;
using RIMAPI.Services;

namespace RIMAPI.Helpers
{
    public static class CombatIdleFireMath
    {
        public static bool Control(bool selected,bool nativeIdle,bool foreignQueue,bool clinical,bool busy,bool laneSafe)
            =>selected && nativeIdle && !foreignQueue && !clinical && busy && !laneSafe;
    }
    public static partial class CombatControlHelper
    {
        private sealed class CoverTransfer
        {public Pawn Mover,Enemy;public int Until;}
        private static readonly Dictionary<Pawn,CoverTransfer> CoverTransfers=new Dictionary<Pawn,CoverTransfer>();
        private static readonly HashSet<Pawn> MedicalExits=new HashSet<Pawn>();
        private static readonly Dictionary<Pawn,int> TeamReviews=new Dictionary<Pawn,int>();
        private static readonly Dictionary<Pawn,string> MoveStages=new Dictionary<Pawn,string>();
        [ThreadStatic] private static bool urgentTeamTransition;
#if LAYA_COMBAT_LAB
        private static readonly List<object> TeamEvents=new List<object>();
        public static object TeamCareDiagnostics()=>new{events=TeamEvents.ToArray(),cover_transfers=CoverTransfers.Count,
            doctor_routes=DoctorRouteDiagnostics(),
            doctor_reserve=DoctorReserveDiagnostics(),
            medical_exits=MedicalExits.Count,cohort=FallbackDiagnostics(),meaning="Readback of real transitions and native shot evidence; assignments are not hits, tends or raid wins"};
#endif
        private static void TeamEvent(string reason,Pawn p,Pawn target=null,Pawn other=null)
        {
#if LAYA_COMBAT_LAB
            if(TeamEvents.Count<384)TeamEvents.Add(new{tick=Find.TickManager.TicksGame,reason,pawn=p?.thingIDNumber,
                target=target?.thingIDNumber,other=other?.thingIDNumber,current=p?.CurJobDef?.defName,job_id=p?.CurJob?.loadID,
                x=p?.Position.x,z=p?.Position.z,bleeding=p?.health.hediffSet.BleedRateTotal,
                doctor=p!=null && MedicalReady(p),native_shot_tick=target==null || p==null?(int?)null:CombatShotEvidenceHelper.LastTick(p,target.thingIDNumber)});
#endif
        }
        private static bool NativeDoctor(Pawn p)=>MedicalReady(p)
            && !CaregiverRecoveryHelper.Protected(p)
            && !(p.skills?.GetSkill(SkillDefOf.Medicine)?.TotallyDisabled ?? true)
            && !CombatNativeHelper.Protected(p) && !CareTriageHelper.QueuedCare(p)
            && !(p.carryTracker?.CarriedThing is Pawn);
        private static float TeamCycle(Pawn p)
        {
            var v=p.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            return v==null?float.PositiveInfinity:v.verbProps.warmupTime*60f*p.GetStatValue(StatDefOf.AimingDelayFactor)
                +Math.Max(0,v.verbProps.burstShotCount-1)*v.verbProps.ticksBetweenBurstShots
                +p.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f;
        }
        private static bool MedicalFunctionWarning(Pawn p)
        {
            if(!NativeDoctor(p) || !p.health.hediffSet.hediffs.Any(h=>h.TendableNow() && h.Bleeding))return false;
            var deadline=CareTriageHelper.BloodFunctionTicks(p);var care=CareTriageHelper.SelfTendBudgetTicks(p);
            return p.health.hediffSet.BleedRateTotal>=1.5f || deadline.HasValue && care.HasValue && deadline<=care+1800;
        }
        private static bool TeamImmediateDanger(Pawn p)=>p.Position.ContainsStaticFire(p.Map)
            || p.Map.gasGrid.DensityAt(p.Position,GasType.ToxGas)>0
            || p.Map.gasGrid.DensityAt(p.Position,GasType.DeadlifeDust)>0
            || p.Map.mapPawns.AllPawnsSpawned.Any(e=>Threat(e) && MeleeThreat(e) && e.Position.InHorDistOf(p.Position,2.1f));
        private static bool TeamCoverReady(Pawn p,Pawn enemy,List<Pawn> threats)
        {
            if(!Eligible(p) || p.CurJobDef==JobDefOf.Goto || CombatNativeHelper.Protected(p) || CareTriageHelper.QueuedCare(p)
                || p.health.capacities.GetLevel(PawnCapacityDefOf.Consciousness)<.65f
                || p.health.capacities.GetLevel(PawnCapacityDefOf.Manipulation)<.5f
                || p.health.capacities.GetLevel(PawnCapacityDefOf.Moving)<.5f
                || MedicalFunctionWarning(p) || !Threat(enemy) || !CombatInterceptHelper.CanShootNow(p,enemy))return false;
            int shot=CombatShotEvidenceHelper.LastTick(p,enemy.thingIDNumber);
            if(shot<0 || Find.TickManager.TicksGame-shot>TeamCycle(p)+60)return false;
            var warm=p.stances.curStance as Stance_Warmup;
            float ready=warm?.focusTarg.Thing==enemy?warm.ticksLeft:CombatInterceptHelper.MovementLockTicks(p)+TeamCycle(p);
            if(threats.Where(MeleeThreat).Any(e=>CombatInterceptHelper.Pursuing(e,p) && CombatInterceptHelper.ContactTicks(e,p)<=ready+30))return false;
            return (IncomingRangedExposure(p,p.Position)<=.6f || !CriticalRangedInjury(p)) && SupportHorizon(p,enemy,p.Position,0);
        }
        public static bool PreserveTeamMove(Pawn pawn,Job next)
        {
            if(!urgentTeamTransition && (next?.def==JobDefOf.Goto || next?.def==JobDefOf.AttackStatic)
                && !(next.targetA.Thing is Pawn abduct && CombatNativeHelper.AbductionThreat(abduct))
                && KeepDoctorBoundIntent(pawn))return true;
            if(!urgentTeamTransition && (next?.def==JobDefOf.Goto || next?.def==JobDefOf.AttackStatic) && KeepDoctorDetour(pawn))return true;
            if(next?.def==JobDefOf.Goto && Eligible(pawn) && KeepGroupPosition(pawn,next.targetA.Cell))return true;
            if(urgentTeamTransition || next==null || next.def!=JobDefOf.Goto && next.def!=JobDefOf.AttackStatic
                || !Eligible(pawn) || TeamImmediateDanger(pawn))return false;
            if(next.targetA.Thing is Pawn urgent && CombatNativeHelper.AbductionThreat(urgent))return false;
            if(KeepCohortCover(pawn,next.def==JobDefOf.AttackStatic?next.targetA.Thing as Pawn:null))return true;
            if(KeepCoverTurn(pawn,next.def==JobDefOf.AttackStatic?next.targetA.Thing as Pawn:null))return true;
            if(next.def==JobDefOf.Goto && PreserveDoctorPosition(pawn,next.targetA.Cell))return true;
            if(next.def==JobDefOf.Goto && DelayDoctorMoveUntilReadyCover(pawn,next.targetA.Cell))return true;
            if(SelectedMoves.TryGetValue(pawn,out var move) && move.Value!=null && move.Key?.def==JobDefOf.Goto
                && PreserveMoveBeforeShot(pawn,move.Value))
            {
                if(next.def==JobDefOf.Goto && next.targetA.Cell==move.Key.targetA.Cell)return false;
                TeamEvent("accepted_move_kept_before_optional_reassignment",pawn,move.Value.targetA.Thing as Pawn);
                return true;
            }
            return KeepTransferredCover(pawn,next.def==JobDefOf.AttackStatic?next.targetA.Thing as Pawn:null);
        }
        private static bool DelayDoctorMoveUntilReadyCover(Pawn doctor,IntVec3 goal)
        {
            if(!NativeDoctor(doctor) || MedicalFunctionWarning(doctor) || !Plans.TryGetValue(doctor.thingIDNumber,out var plan) || !Valid(plan))return false;
            var threats=doctor.Map.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
            var enemy=threats.Where(e=>MeleeThreat(e) && CombatInterceptHelper.Pursuing(e,doctor))
                .OrderBy(e=>CombatInterceptHelper.ContactTicks(e,doctor)).FirstOrDefault();
            if(enemy==null)return false;
            var other=Plans.Values.Where(Valid).Select(x=>x.Pawn).Where(p=>p!=doctor && p.Map==doctor.Map).ToArray();
            if(other.Any(p=>TeamCoverReady(p,enemy,threats)))return false;
            var preparing=other.Where(p=>p.CurJobDef!=JobDefOf.Goto && AimTarget(p)==enemy
                && p.stances.curStance is Stance_Warmup && CombatInterceptHelper.CanShootNow(p,enemy))
                .Select(p=>new{Pawn=p,Delay=((Stance_Warmup)p.stances.curStance).ticksLeft}).OrderBy(x=>x.Delay).FirstOrDefault();
            if(preparing==null)return false;
            // A short wait is justified only by a real same-enemy warmup and
            // a newly checked native escape duration. Never wait past escape.
            using(var path=CombatPathBudgetHelper.Query(doctor,doctor.Position,goal,PathEndMode.OnCell))
                if(path.Found && CombatInterceptHelper.ContactTicks(enemy,doctor)>preparing.Delay+path.TotalCost+60)
                {TeamEvent("doctor_waits_for_finite_covering_shot",doctor,enemy,preparing.Pawn);return true;}
            return false;
        }
        public static void RememberSupportApproach(Pawn pawn,Job move,Job shot,Pawn enemy)
        {
            if(move?.def!=JobDefOf.Goto || !Present(pawn,move) || shot==null || !Present(pawn,shot)
                || shot.targetA.Thing!=enemy || !Plans.TryGetValue(pawn.thingIDNumber,out var plan))
                throw new InvalidOperationException("Exact accepted support move and its selected shot required");
            move=RememberMove(pawn,move,shot);plan.OwnedJob=move;plan.QueuedShot=shot;plan.Target=enemy;plan.Mode="support";
            plan.LastMoveTick=Find.TickManager.TicksGame;plan.SupportReviewTick=Find.TickManager.TicksGame+30;
        }
        private static bool KeepTransferredCover(Pawn pawn,Pawn nextTarget)
        {
            if(!CoverTransfers.TryGetValue(pawn,out var cover) || Find.TickManager.TicksGame>cover.Until
                || !cover.Mover.Spawned || cover.Mover.Dead || cover.Mover.Downed || !Threat(cover.Enemy))return false;
            if(cover.Mover.CurJobDef!=JobDefOf.Goto && !CombatNativeHelper.HasClinicalCareJob(cover.Mover))return false;
            if(nextTarget==cover.Enemy)return false;
            if(ActiveCoverTransfer(pawn,cover))
            {TeamEvent("exact_inflight_cover_intent_kept_independent_of_next_shot",pawn,cover.Enemy,cover.Mover);return true;}
            var threats=pawn.Map.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
            if(!TeamCoverReady(pawn,cover.Enemy,threats) || TeamImmediateDanger(pawn) || MedicalFunctionWarning(pawn))return false;
            TeamEvent("actual_cover_kept_during_handoff",pawn,cover.Enemy,cover.Mover);return true;
        }
        public static bool PreserveTeamTactic(Pawn pawn,CombatTacticRequestDto request)
        {
            if(!RangedPlans.Contains(request.Tactic) || !Eligible(pawn) || TeamImmediateDanger(pawn))return false;
            if(request.Tactic=="intercept_kidnapper")return false;
            if(KeepDoctorDetour(pawn))return true;
            if(KeepDoctorBoundIntent(pawn))return true;
            if(KeepCohortIntent(pawn,request.Tactic))return true;
            if(KeepCohortCover(pawn))return true;
            if(KeepCoverTurn(pawn))return true;
            if(SelectedMoves.TryGetValue(pawn,out var move) && move.Value!=null && PreserveMoveBeforeShot(pawn,move.Value))return true;
            var target=request.TargetPawnId.HasValue?pawn.Map.mapPawns.AllPawnsSpawned.FirstOrDefault(p=>p.thingIDNumber==request.TargetPawnId.Value):null;
            return KeepTransferredCover(pawn,target);
        }
        private static bool PreserveTeamApproach(Plan plan,List<Pawn> threats)
        {
            var p=plan.Pawn;
            if(plan.Mode!="support" && plan.Mode!="position" || !SelectedMoves.TryGetValue(p,out var selected)
                || selected.Value==null || selected.Key==null || p.Position==selected.Key.targetA.Cell)return false;
            if(!PreserveMoveBeforeShot(p,selected.Value))return false;
            var path=p.pather.curPath;
            if(path!=null && path.Found && !CombatInterceptHelper.MovementCellsSafe(p,RemainingRangedCells(p,path)))
            {TeamEvent("approach_new_native_route_hazard",p,plan.Target);return false;}
            // Missing path/Motion while the accepted native start is pending is
            // not a failed route. The existing fixed progress allowance applies.
            return true;
        }
        private static void ObserveTeamMoves()
        {
            foreach(var pair in SelectedMoves.Take(32).ToArray())
            {
                var p=pair.Key;var move=pair.Value;if(!p.Spawned || p.Dead)continue;
                var target=move.Value?.targetA.Thing as Pawn;
                string stage=move.Key!=null && p.Position==move.Key.targetA.Cell?"arrival":
                    p.CurJob==move.Key?(p.pather.Moving?"moving":"pending_native_start"):
                    p.jobs.jobQueue.Any(q=>q.job==move.Key)?"pending_queued_start":
                    p.CurJob==move.Value?"selected_shot_started":"owned_move_no_longer_present";
                if(target!=null && CombatShotEvidenceHelper.LastTick(p,target.thingIDNumber)>=move.AcceptedTick)stage="real_projectile_after_move_intent";
                if(!MoveStages.TryGetValue(p,out var old) || old!=stage){MoveStages[p]=stage;TeamEvent(stage,p,target);}
            }
        }
        private static void ReviewNativeIdleFire(Plan plan)
        {
            var p=plan.Pawn;var v=p.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            bool nativeIdle=p.CurJobDef==JobDefOf.Wait_Combat && !p.CurJob.playerForced
                && !CombatOrderHelper.Owned(p,p.CurJob);
            if(!nativeIdle || p.jobs.jobQueue.Any() || CombatNativeHelper.Protected(p)
                || CareTriageHelper.QueuedCare(p) || CaregiverRecoveryHelper.Protected(p))return;
            bool busy=p.stances.curStance is Stance_Warmup || v?.state==VerbState.Bursting;
            // Cooldown retains the previous focus even after AttackStatic has
            // selected another target. It is not a prospective native shot.
            if(!busy)return;
            var target=AimTarget(p);
            bool safe=target==null || Threat(target) && CombatInterceptHelper.FriendlyLaneClear(p,target,p.Position);
            if(!CombatIdleFireMath.Control(Valid(plan),nativeIdle,false,false,busy,safe))return;
            // A selected actor's native post-job idle must not start arbitrary
            // automatic targets outside the controller's friendly-lane guard.
            // Keep a safe in-progress shot; stop a newly unsafe one before a
            // controlled hold is registered. Foreign/clinical intent is above.
            if(!safe){p.stances.CancelBusyStanceSoft();v?.Reset();}
            var hold=JobMaker.MakeJob(JobDefOf.Wait_Combat);hold.playerForced=true;
            if(!CombatOrderHelper.Take(p,ref hold))return;
            plan.OwnedJob=hold;plan.QueuedShot=null;plan.Mode="shoot";
            TeamEvent(safe?"native_idle_returned_to_selected_fire_control":"unsafe_native_idle_fire_stopped",p,target);
        }
        private static void ReviewImmediateTeamDanger()
        {
            // Bounded urgent safety is included in whole-Tick timing, but an
            // expired optional geometry budget cannot leave an owned unsafe
            // shot running. The native path-query quota is still enforced.
            using(CombatPathBudgetHelper.CriticalSafety())
                foreach(var plan in Plans.Values.Where(Valid).Take(32).ToArray())
                {
                    var p=plan.Pawn;
                    if(TeamImmediateDanger(p))ContactDefence(plan,p.Map.mapPawns.AllPawnsSpawned.Where(Threat).ToList());
                    ReviewNativeIdleFire(plan);
                    var firing=p.stances.curStance is Stance_Warmup
                        || p.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb?.state==VerbState.Bursting;
                    var selected=p.CurJob?.targetA.Thing as Pawn;
                    // An active unsafe burst still stops immediately. An old
                    // cooldown focus must not cancel a new safe selected job.
                    var target=firing?AimTarget(p) ?? selected:selected;
                    if((p.CurJobDef==JobDefOf.AttackStatic || p.CurJobDef==JobDefOf.Wait_Combat) && CombatOrderHelper.Owned(p,p.CurJob)
                        && target!=null && (!Threat(target) || !CombatInterceptHelper.FriendlyLaneClear(p,target,p.Position)))
                    {
                        TeamEvent("urgent_owned_shot_stopped_target_or_friendly_lane_changed",p,target);
                        p.stances.CancelBusyStanceSoft();p.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb?.Reset();
                        StopUnsafeOwnedShot(plan);
                    }
                }
        }
        private static void StopUnsafeOwnedShot(Plan plan)
        {
            var p=plan.Pawn;
            // Ending the rejected shot alone leaves a new vanilla idle job
            // outside our ownership table. The pending cover transaction then
            // loses its mover, and vanilla idle can select another unsafe shot.
            // Issue our own controlled hold through the normal exact readback;
            // never register an engine/manual job as if it were ours.
            var hold=JobMaker.MakeJob(JobDefOf.Wait_Combat);hold.playerForced=true;
            if(CombatOrderHelper.Take(p,ref hold))
            {
                plan.OwnedJob=hold;plan.QueuedShot=null;plan.Mode="shoot";
                TeamEvent("unsafe_shot_replaced_by_owned_controlled_hold",p);return;
            }
            // Safety still stops the rejected owned shot if a later foreign
            // instruction prevented acceptance. Take protects that later queue.
            CombatOrderHelper.DropQueued(p);p.jobs.EndCurrentJob(JobCondition.InterruptForced,false);
            plan.OwnedJob=null;plan.QueuedShot=null;plan.Mode="shoot";
        }
        private static bool TryTeamFirstCare()
        {
            foreach(var group in Plans.Values.Where(Valid).GroupBy(x=>x.Pawn.Map).ToArray())
            {
                var map=group.Key;
                if(!CombatMedicalTransitionHelper.ThreatsClear(map))continue;
                var patients=map.mapPawns.FreeColonistsSpawned.Where(p=>!p.Dead && p.health.hediffSet.BleedRateTotal>=.1f
                    && p.health.hediffSet.hediffs.Any(h=>h.TendableNow())).OrderBy(p=>CareTriageHelper.BleedoutTicks(p) ?? float.PositiveInfinity).Take(5).ToArray();
                foreach(var plan in group.Where(x=>NativeDoctor(x.Pawn)).OrderByDescending(x=>x.Pawn.GetStatValue(StatDefOf.MedicalTendSpeed)).ToArray())
                {
                    var doctor=plan.Pawn;
                    foreach(var patient in patients.OrderByDescending(p=>p==doctor && MedicalFunctionWarning(doctor)))
                    {
                        CombatPathBudgetHelper.Checkpoint("first_care");
                        if(!CombatMedicalTransitionHelper.Ready(doctor,patient,doctor.CurJob?.loadID ?? -1,out var travel))continue;
                        var result=new PawnJobService().AssignTendJob(new MedicalTendRequestDto{PatientPawnId=patient.thingIDNumber,
                            DoctorPawnId=doctor.thingIDNumber,SelfTend=doctor==patient,ReviewAfterTend=true,ReleaseCombatJobId=doctor.CurJob.loadID});
                        if(result.Success && result.Data?.Applied==true){MedicalExits.Remove(doctor);TeamEvent("bound_native_first_tend_accepted",doctor,patient);return true;}
                    }
                }
            }
            return false;
        }
        private static bool SupportHorizon(Pawn p,Pawn enemy,IntVec3 cell,float travel)
        {
            var v=p.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;if(v==null)return false;
            float first=travel+CombatInterceptHelper.MovementLockTicks(p)+v.verbProps.warmupTime*60f*p.GetStatValue(StatDefOf.AimingDelayFactor)
                +CombatInterceptMath.NativeFlightTicks(cell.DistanceTo(enemy.Position),v.verbProps.defaultProjectile?.projectile?.SpeedTilesPerTick ?? 0)+30;
            if(p.Map.mapPawns.AllPawnsSpawned.Any(e=>Threat(e) && MeleeThreat(e) && CombatInterceptHelper.Pursuing(e,p)
                && CombatInterceptHelper.ContactTicks(e,p)<=first+TeamCycle(p)+30))return false;
            if(IncomingRangedExposure(p,cell)>1.4f || MedicalFunctionWarning(p))return false;
            foreach(var horizon in new[]{first,first+TeamCycle(p)})
            {
                CombatPathBudgetHelper.Checkpoint("support_cycle");
                if(!CombatInterceptHelper.TryObservedFuturePosition(enemy,horizon,out var future)
                    || CombatExposureHelper.CanHitPawnAt(v,enemy,cell,future)!=true
                    || !CombatInterceptHelper.FutureFriendlyLaneClear(p,enemy,cell,future,"team_care_support"))return false;
            }
            return true;
        }
        private static void ReviewTeamHandoffs()
        {
            ObserveTeamMoves();int tick=Find.TickManager.TicksGame;
            foreach(var group in Plans.Values.Where(Valid).GroupBy(p=>p.Pawn.Map).ToArray())
            {
                var plans=group.ToArray();var threats=group.Key.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
                if(!threats.Any())continue;
                var doctors=plans.Where(x=>NativeDoctor(x.Pawn)).ToArray();
                float Contact(Pawn p)=>threats.Where(e=>MeleeThreat(e) && CombatInterceptHelper.Pursuing(e,p))
                    .Select(e=>CombatInterceptHelper.ContactTicks(e,p)).DefaultIfEmpty(10000f).Min();
                var medical=doctors.OrderByDescending(x=>Contact(x.Pawn)).ThenBy(x=>IncomingRangedExposure(x.Pawn,x.Pawn.Position))
                    .ThenByDescending(x=>x.Pawn.GetStatValue(StatDefOf.MedicalTendSpeed)).FirstOrDefault();
                foreach(var plan in plans.OrderBy(x=>TeamReviews.TryGetValue(x.Pawn,out var prior)?prior:0))
                {
                    var p=plan.Pawn;
                    if(p.CurJobDef==JobDefOf.Goto || !CombatOrderHelper.Owned(p,p.CurJob) || CareTriageHelper.QueuedCare(p)
                        || p.jobs.jobQueue.Any() || CombatNativeHelper.Protected(p))continue;
                    if(TeamReviews.TryGetValue(p,out var last) && tick-last<45)continue;
                    TeamReviews[p]=tick;CombatPathBudgetHelper.Checkpoint("team_handoff");
                    var own=threats.Where(e=>MeleeThreat(e) && CombatInterceptHelper.Pursuing(e,p))
                        .OrderBy(e=>CombatInterceptHelper.ContactTicks(e,p)).FirstOrDefault();
                    var incoming=threats.Where(e=>FocusedRangedThreat(e,p))
                        .OrderBy(e=>e.Position.DistanceToSquared(p.Position)).FirstOrDefault();
                    bool targetedWound=TargetedWoundedRanged(p,threats);
                    bool medicalExit=MedicalFunctionWarning(p) || NativeDoctor(p) && targetedWound || medical==plan && own!=null
                        && Contact(p)<=TeamCycle(p)+8f/Math.Max(.1f,Speed(p))*60f+90f;
                    if(medicalExit)
                    {
                        var enemy=own ?? incoming ?? threats.OrderBy(e=>e.Position.DistanceToSquared(p.Position)).First();
                        var cover=plans.Select(x=>x.Pawn).Where(g=>g!=p && TeamCoverReady(g,enemy,threats)).ToArray();
                        if(cover.Any() || TeamImmediateDanger(p) || MedicalFunctionWarning(p) || targetedWound)
                        {
                            bool moved=false;urgentTeamTransition=true;
                            try
                            {
                                if(own!=null && TryRangedRetreat(p,own,plan.Anchor,out var move))
                                {plan.OwnedJob=move;plan.QueuedShot=SelectedMoves[p].Value;plan.Target=own;plan.Mode="retreat";plan.LastMoveTick=tick;moved=true;}
                                else if(own==null)moved=TryBreakRangedContact(plan,threats,true);
                            }
                            finally{urgentTeamTransition=false;}
                            if(moved)
                            {
                                MedicalExits.Add(p);
                                foreach(var gun in cover)CoverTransfers[gun]=new CoverTransfer{Mover=p,Enemy=enemy,Until=tick+600};
                                TeamEvent(cover.Any()?"medical_exit_with_observed_cover":"medical_emergency_exit_without_ready_cover",p,enemy,cover.FirstOrDefault());continue;
                            }
                        }
                    }
                    if(p.health.hediffSet.BleedRateTotal>.1f || CriticalRangedInjury(p)
                        || p.stances.curStance is Stance_Warmup || p.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb?.state==VerbState.Bursting)continue;
                    var foe=threats.Where(e=>ObservedVictim(e) is Pawn ally && ally!=p && !ally.Dead && !ally.Downed)
                        .OrderByDescending(e=>NativeDoctor(ObservedVictim(e)))
                        .ThenBy(e=>MeleeThreat(e)?CombatInterceptHelper.ContactTicks(e,ObservedVictim(e)):10000).FirstOrDefault();
                    if(foe==null || CombatNativeHelper.AbductionThreat(foe))continue;
                    if(SupportHorizon(p,foe,p.Position,0))
                    {
                        if(TeamImmediateDanger(p) || MedicalFunctionWarning(p))continue;
                        var shot=JobMaker.MakeJob(JobDefOf.AttackStatic,foe);shot.playerForced=true;
                        if(CombatOrderHelper.Take(p,ref shot)){plan.OwnedJob=shot;plan.Target=foe;plan.Mode="shoot";TeamEvent("support_target_selected",p,foe,ObservedVictim(foe));}
                        continue;
                    }
                    // The existing short-angle executor retains native route,
                    // pursuer, exposure and friendly-fire checks. Its horizon
                    // eligibility below is extended to the approach, not only
                    // an already established eight-cell contact.
                    if(TryContactSupport(plan,threats))TeamEvent("support_approach_accepted",p,plan.Target,ObservedVictim(plan.Target));
                }
            }
        }
    }
}

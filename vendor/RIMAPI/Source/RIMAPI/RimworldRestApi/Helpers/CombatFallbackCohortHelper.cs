using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class CombatFallbackMath
    {
        private static bool Known(float x)=>x>=0 && !float.IsNaN(x) && !float.IsInfinity(x);
        public static bool LeaveFormation(bool critical,bool immediate,float before,float after)
            =>critical || immediate || !(before>=0) || !(after>=0) || float.IsInfinity(before)
                || float.IsInfinity(after) || after<=before+1;
        public static bool Protected(float exposure)=>exposure>=0 && !float.IsInfinity(exposure) && exposure<=.1f;
        public static float FutureShotHorizon(float travel,float locked,float aim,float burst,float flight)
            =>Known(travel) && Known(locked) && Known(aim) && Known(burst) && Known(flight)
                && travel+locked+aim+burst+flight+30<=600
                ?travel+locked+aim+burst+flight+30:float.PositiveInfinity;
        public static bool CoverObserved(int created,int shot,int now,float cycle)
            =>shot>=created && now>=shot && Known(cycle) && now-shot<=cycle+60;
        public static bool ArrivalMargin(float contactAfter,float first,float burst,bool realCover)
            =>Known(contactAfter) && Known(first) && Known(burst)
                && contactAfter>first+burst+(realCover?60:120);
        public static bool MoveSlot(int moving,int stationary,bool meleeOnly)
            =>moving==0 || meleeOnly && moving==1 && stationary>=2;
        public static bool OptionalOwner(bool live,bool capable,bool owned,bool meleeOnly,bool abduction)
            =>live && capable && owned && meleeOnly && !abduction;
        public static bool GroupFirst(bool safe,float contact)
            =>safe && Known(contact) && contact>120;
        public static bool PendingCover(bool owned,bool safe,bool sameThreat,int now,int until)
            =>owned && safe && sameThreat && now<until;
        public static bool FutureClinicalOrigin(bool physicianMoving,bool routeChecked,bool exactOwnedMove)
            =>physicianMoving && routeChecked || exactOwnedMove;
        public static bool Access(float cost,float available,bool routeSafe)
            =>Known(cost) && Known(available) && routeSafe && cost<=180 && cost+600<available;
        public static float BoundDistance(float cycle,float speed)
            =>Known(cycle) && Known(speed) && cycle>0 && speed>0?Math.Min(4f,cycle*speed/180f):0;
        public static bool WaitForMovingPeers(bool healthy,bool moving,bool useful,float contact,float cycle)
            =>healthy && moving && useful && Known(contact) && Known(cycle) && contact>cycle+90f;
        public static bool RenewCompleted(bool meleeOnly,bool moving,bool reached,bool fired,int age,float contact,float cycle,float escape)
            =>meleeOnly && !moving && reached && fired && age>=30
                && Known(contact) && Known(cycle) && Known(escape) && cycle>0
                && contact<=cycle+escape+90f;
        public static bool FormationAuthority(bool meleeOnly,int committedBounds)
            =>meleeOnly || committedBounds>0;
    }

    public static partial class CombatControlHelper
    {
        private sealed class FallbackCohort
        {
            public Pawn Doctor; public IntVec3 Origin,Anchor;
            public int Created,Until,NextReview,NextRenew; public int[] Members;
            public Pawn PendingMover,PendingGun,PendingEnemy;public int PendingUntil;
            public readonly HashSet<Pawn> Staged=new HashSet<Pawn>();
            public readonly Dictionary<Pawn,IntVec3> Posts=new Dictionary<Pawn,IntVec3>();
            public readonly Dictionary<Pawn,int> LastMemberReview=new Dictionary<Pawn,int>();
            public readonly Dictionary<Pawn,IntVec3> Offsets=new Dictionary<Pawn,IntVec3>();
        }
        private sealed class FallbackMove
        {public CombatJobStamp Job;public IntVec3 Goal;public int Until,Arrived=-1;public bool PhysicianRejoin,FromCohort;}
        private static readonly Dictionary<Map,FallbackCohort> FallbackCohorts=new Dictionary<Map,FallbackCohort>();
        private static readonly Dictionary<Pawn,FallbackMove> FallbackMoves=new Dictionary<Pawn,FallbackMove>();
        private static void ReopenCompletedCohortBound(FallbackCohort cohort,Pawn pawn)
        {
            cohort.Staged.Remove(pawn);
            cohort.Posts.Remove(pawn);
            FallbackMoves.Remove(pawn);
            cohort.LastMemberReview.Remove(pawn);
        }
        private static int CohortMovingCount(Plan[] plans)
            =>plans.Count(p=>CohortInTransit(p) || DoctorBoundInTransit(p)
                || p.Pawn.CurJobDef==JobDefOf.Goto && CombatOrderHelper.Owned(p.Pawn,p.Pawn.CurJob));
        private static IntVec3 CohortFormationPost(FallbackCohort cohort,Pawn pawn)
            =>cohort.Anchor+(cohort.Offsets.TryGetValue(pawn,out var offset)?offset:IntVec3.Zero);
#if LAYA_COMBAT_LAB
        private static readonly List<object> FallbackProofs=new List<object>();
        private static readonly Dictionary<string,int> FallbackReasons=new Dictionary<string,int>();
        private static readonly List<object> FallbackReviews=new List<object>();
        private static readonly List<object> MemberReceipts=new List<object>();
        private static readonly Dictionary<Map,int> LastMemberReceipt=new Dictionary<Map,int>();
        private static object FallbackDiagnostics()=>new{proofs=FallbackProofs.ToArray(),reasons=new Dictionary<string,int>(FallbackReasons),reviews=FallbackReviews.ToArray(),
            member_receipts=MemberReceipts.ToArray(),
            meaning="Native route/cover/access checks at acceptance, not arrival, treatment or battle victory"};
#endif

        [System.Diagnostics.Conditional("LAYA_COMBAT_LAB")]
        private static void RecordCohortReceipts(FallbackCohort cohort,Plan[] plans)
        {
#if LAYA_COMBAT_LAB
            int tick=Find.TickManager.TicksGame;var map=plans[0].Pawn.Map;
            if(MemberReceipts.Count>=96 || tick-cohort.Created>1200
                || LastMemberReceipt.TryGetValue(map,out var last) && tick-last<60)return;
            LastMemberReceipt[map]=tick;
            foreach(var plan in plans.Take(4))
            {
                var p=plan.Pawn;bool hasPost=cohort.Posts.TryGetValue(p,out var post);
                FallbackMoves.TryGetValue(p,out var done);
                MemberReceipts.Add(new{tick,pawn=p.thingIDNumber,staged=cohort.Staged.Contains(p),
                    x=p.Position.x,z=p.Position.z,has_post=hasPost,post_x=hasPost?(int?)post.x:null,post_z=hasPost?(int?)post.z:null,
                    job=p.CurJobDef?.defName,current_id=p.CurJob?.loadID,selected_id=plan.OwnedJob?.loadID,
                    withdrawal_id=plan.RangedWithdrawal?.Value?.loadID,receipt_id=done?.Job.Value?.loadID,
                    arrived=done?.Arrived,until=done?.Until,native_moving=p.pather.Moving,native_path_found=p.pather.curPath?.Found,
                    queued=p.jobs.jobQueue.Select(q=>new{id=q.job.loadID,def=q.job.def.defName,owned=CombatOrderHelper.Owned(p,q.job)}).ToArray()});
            }
#endif
        }

        [System.Diagnostics.Conditional("LAYA_COMBAT_LAB")]
        private static void CohortTrace(string reason,Pawn pawn=null,Pawn enemy=null,IntVec3? cell=null,float? exposure=null,float? horizon=null)
        {
#if LAYA_COMBAT_LAB
            FallbackReasons[reason]=FallbackReasons.TryGetValue(reason,out var n)?n+1:1;
            if(FallbackReviews.Count<320)FallbackReviews.Add(new{tick=Find.TickManager.TicksGame,reason,
                pawn=pawn?.thingIDNumber,enemy=enemy?.thingIDNumber,x=cell?.x,z=cell?.z,
                job=pawn?.CurJobDef?.defName,job_id=pawn?.CurJob?.loadID,
                actor_x=pawn?.Position.x,actor_z=pawn?.Position.z,
                exposure_known=exposure.HasValue && !float.IsNaN(exposure.Value) && !float.IsInfinity(exposure.Value),
                exposure=exposure.HasValue && !float.IsNaN(exposure.Value) && !float.IsInfinity(exposure.Value)?exposure:null,
                horizon});
#endif
        }
        private static bool CohortOwned(Pawn p)=>Eligible(p) && !CaregiverRecoveryHelper.Protected(p)
            && !p.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(p,q.job))
            && (CombatOrderHelper.Owned(p,p.CurJob)
                || p.CurJobDef==JobDefOf.Wait_Combat && !p.CurJob.playerForced);
        private static bool CohortCell(Pawn p,IntVec3 c)=>c.InBounds(p.Map) && c.Standable(p.Map)
            && !c.Fogged(p.Map) && !c.ContainsStaticFire(p.Map)
            && p.Map.gasGrid.DensityAt(c,GasType.ToxGas)==0
            && p.Map.gasGrid.DensityAt(c,GasType.DeadlifeDust)==0
            && !c.GetThingList(p.Map).Any(t=>t is Building_Trap || t is Pawn other && other!=p);
        private static bool CohortLive(Pawn p,out FallbackCohort c)
        {
            if(!FallbackCohorts.TryGetValue(p.Map,out c) || !c.Members.Contains(p.thingIDNumber)
                || Find.TickManager.TicksGame>c.Until || !CohortOwned(p))return false;
            return c.Doctor.Spawned && !c.Doctor.Dead && !c.Doctor.Downed
                && c.Doctor.Map==p.Map && !p.Map.mapPawns.AllPawnsSpawned.Any(t=>Threat(t) && CombatNativeHelper.AbductionThreat(t));
        }
        private static bool CohortInTransit(Plan plan)
            =>CohortLive(plan.Pawn,out _) && FallbackMoves.TryGetValue(plan.Pawn,out var move)
                && Find.TickManager.TicksGame<=move.Until && move.Job.Value==plan.Pawn.CurJob
                && plan.OwnedJob==plan.Pawn.CurJob && plan.Pawn.CurJobDef==JobDefOf.Goto
                && plan.Pawn.CurJob.targetA.Cell==move.Goal;
        private static bool MeleeCohort(Map map,List<Pawn> threats)
            =>FallbackCohorts.TryGetValue(map,out var c) && threats.Count>0
                && CombatFallbackMath.OptionalOwner(Find.TickManager.TicksGame<=c.Until,
                    c.Doctor.Spawned && !c.Doctor.Dead && !c.Doctor.Downed && c.Doctor.Map==map && NativeDoctor(c.Doctor),
                    CohortOwned(c.Doctor),threats.All(MeleeThreat),threats.Any(CombatNativeHelper.AbductionThreat));
        private static bool PrioritizeMeleeCohort()
        {
            var groups=Plans.Values.Where(Valid).GroupBy(p=>p.Pawn.Map).ToArray();
            return groups.Length>0 && groups.All(group=>{
                var threats=group.Key.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
                return group.Count()>=2 && threats.Count>0 && threats.All(MeleeThreat)
                    && !threats.Any(CombatNativeHelper.AbductionThreat)
                    && group.All(p=>CombatFallbackMath.GroupFirst(!TeamImmediateDanger(p.Pawn) && !CriticalRangedInjury(p.Pawn)
                        && !MedicalFunctionWarning(p.Pawn),EarliestContact(p.Pawn,threats)));
            });
        }
        private static bool KeepCheckedCohortCover(Plan plan,List<Pawn> threats)
        {
            var p=plan.Pawn;
            if(!MeleeCohort(p.Map,threats) || !CoverTransfers.TryGetValue(p,out var cover)
                || Find.TickManager.TicksGame>cover.Until || !Plans.TryGetValue(cover.Mover.thingIDNumber,out var moving) || !CohortInTransit(moving)
                || AimTarget(p)!=cover.Enemy || !CombatOrderHelper.Owned(p,p.CurJob)
                || TeamImmediateDanger(p) || CriticalRangedInjury(p) || MedicalFunctionWarning(p)
                || !CoverGunWindow(p,cover.Enemy,threats) || !TeamCoverReady(p,cover.Enemy,threats))return false;
            CohortTrace("checked_cohort_cover_kept_during_transit",p,cover.Enemy);return true;
        }
        private static bool PendingCohort(FallbackCohort c)
        {
            var p=c.PendingMover;var gun=c.PendingGun;var enemy=c.PendingEnemy;
            if(p==null || gun==null || enemy==null || p.Map==null || gun.Map!=p.Map)return false;
            var threats=p.Map.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
            bool owned=CohortLive(p,out var live) && live==c && CohortOwned(gun)
                && Plans.TryGetValue(gun.thingIDNumber,out var gp) && CohortStationary(gp,threats)
                && !c.Staged.Contains(p) && p.CurJobDef!=JobDefOf.Goto && p.CurJobDef!=JobDefOf.AttackMelee;
            if(!CombatFallbackMath.PendingCover(owned,!TeamImmediateDanger(p) && !TeamImmediateDanger(gun)
                && !MedicalFunctionWarning(gun),Threat(enemy),Find.TickManager.TicksGame,c.PendingUntil))return false;
            return threats.Any() && CohortGunFreeFor(gun,p,enemy)
                && CohortCoverWindow(gun,enemy,threats);
        }
        private static bool CohortStationary(Plan p,List<Pawn> threats)
            =>threats.All(MeleeThreat)?OwnStationaryGun(p):DoctorReserveStationary(p);
        private static bool CohortCompatible(string tactic,bool meleeOnly,bool enrolled)
            =>DefensivePlan(tactic) || meleeOnly && enrolled && RangedPlans.Contains(tactic) && tactic!="intercept_kidnapper"
                || !meleeOnly && new[]{"kite","backstep_fire","spread_out"}.Contains(tactic);
        private static bool CohortGunFreeFor(Pawn gun,Pawn mover,Pawn enemy)
        {
            // Preparation must obey the same real-cover lease that Take will
            // protect. Otherwise we wait for a second target's projectile from
            // a gun that is correctly forbidden to abandon the first mover.
            // Even the same enemy cannot overwrite another in-flight mover:
            // the current transfer stores one exact mover, not a shared label.
            if(!CoverTransfers.TryGetValue(gun,out var held)
                || !ActiveCoverTransfer(gun,held) && !KeepTransferredCover(gun,null))return true;
            return held.Mover==mover && held.Enemy==enemy;
        }
        private static Pawn CohortCoverTarget(Pawn p)
            =>FallbackCohorts.TryGetValue(p.Map,out var c) && c.PendingGun==p && PendingCohort(c)?c.PendingEnemy:null;
        private static bool KeepCohortCover(Pawn p,Pawn next=null)
        {
            var target=CohortCoverTarget(p);
            if(target==null || next==target || !CombatOrderHelper.Owned(p,p.CurJob))return false;
            // Preserve only a finite autonomous covering target, never a
            // foreign/manual/clinical action or an unsafe/current contact.
            CohortTrace("pending_cover_target_kept",p,target);return true;
        }
        private static bool KeepCohortIntent(Pawn p,string tactic,IntVec3? next=null)
        {
            if(!CohortLive(p,out var cohort) || TeamImmediateDanger(p))return false;
            bool enrolledMelee=cohort.Members.Contains(p.thingIDNumber) && RangedPlans.Contains(tactic)
                && tactic!="intercept_kidnapper" && MeleeCohort(p.Map,p.Map.mapPawns.AllPawnsSpawned.Where(Threat).ToList());
            var threats=p.Map.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
            if(!CohortCompatible(tactic,threats.All(MeleeThreat),enrolledMelee))return false;
            // Selecting a rally is not an accepted formation transaction. A
            // ranged cohort with ZERO admitted bounds used to prevent ordinary
            // checked firing/escape positions while never moving anyone itself.
            // Independent medical intent, exact moves and cover leases retain
            // their own authority even when this optional proposal has none.
            int committed=cohort.Posts.Count(kv=>FallbackMoves.TryGetValue(kv.Key,out var move)
                && move.FromCohort && (move.Job.Value!=null && kv.Key.CurJob==move.Job.Value
                    || kv.Key.Position==move.Goal && cohort.Staged.Contains(kv.Key)));
            if(!CombatFallbackMath.FormationAuthority(threats.All(MeleeThreat),committed))return false;
            if(Plans.TryGetValue(p.thingIDNumber,out var plan) && CohortInTransit(plan))return true;
            if(!cohort.Posts.TryGetValue(p,out var post) || p.Position!=post)
            {
                if(!next.HasValue)return false;
                bool release=CombatFallbackMath.LeaveFormation(CriticalRangedInjury(p) || MedicalFunctionWarning(p),
                    TeamImmediateDanger(p),p.Position.DistanceTo(CohortFormationPost(cohort,p)),next.Value.DistanceTo(CohortFormationPost(cohort,p)));
                if(!release)TeamEvent("cohort_optional_departure_refused",p);
                return !release;
            }
            if(!CombatFallbackMath.Protected(IncomingRangedExposure(p,post,TeamCycle(p))))return false;
            var close=p.Map.mapPawns.AllPawnsSpawned.Where(t=>Threat(t) && MeleeThreat(t));
            if(close.Any(t=>CombatInterceptHelper.ContactTicks(t,p)<=TeamCycle(p)+90))return false;
            if(!threats.Any(t=>CombatInterceptHelper.CanShootNow(p,t)) && !KeepCohortCover(p))
            {
                if(!next.HasValue)return false;
                var v=p.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
                bool local=next.Value.InHorDistOf(CohortFormationPost(cohort,p),4f)
                    && CombatFallbackMath.Protected(IncomingRangedExposure(p,next.Value,TeamCycle(p)))
                    && threats.Any(t=>v.CanHitTargetFrom(next.Value,t)
                        && CombatInterceptHelper.FriendlyLaneClear(p,t,next.Value));
                return !local;
            }
            return !next.HasValue || next.Value!=post;
        }

        // This proof concerns the real prospective physician route, not radius
        // or a role label. It owns no pooled path after Query returns.
        private static bool CohortAccess(FallbackCohort c,Pawn member,IntVec3 post,float arrival,out float maximumCost)
        {
            maximumCost=0;
            var doctor=c.Doctor;
            // Only this physician's fully checked proposed route licenses its
            // prospective origin. Other members use the physician's REAL cell.
            // A stale assigned post, manual move or clinical job cannot stand
            // in for a destination the physician has never reached.
            var from=CombatFallbackMath.FutureClinicalOrigin(member==doctor,true,false)?post:doctor.Position;
            var patients=member.Map.mapPawns.FreeColonistsSpawned.Where(p=>!p.Dead && p.Downed
                && p.Position.InHorDistOf(c.Origin,20)).ToArray();
            var destinations=patients.Length==0?new[]{post}:patients.Select(p=>p.Position).ToArray();
            foreach(var destination in destinations)
                using(var path=CombatPathBudgetHelper.Query(doctor,from,destination,PathEndMode.Touch))
                {
                    float deadline=patients.Length==0?10000:patients.Select(p=>CareTriageHelper.BleedoutTicks(p) ?? 0).Min();
                    // A healthy shooter's prospective corridor is not already
                    // an active treatment job. Real patients retain the full
                    // protected native clinical route and deadline requirement.
                    bool clinical=patients.Length>0 || !member.Map.mapPawns.AllPawnsSpawned.Any(t=>Threat(t)
                        && t.equipment?.Primary?.def.IsRangedWeapon==true);
                    bool safe=path.Found && CombatInterceptHelper.MovementSafe(doctor,path)
                        && path.NodesReversed.All(cell=>clinical
                            ?CombatFallbackMath.Protected(IncomingRangedExposure(doctor,cell,Math.Min(600,arrival+TeamCycle(doctor))))
                            :CombatPhysicianLineMath.Terminal(IncomingRangedExposure(doctor,cell,Math.Min(600,arrival+TeamCycle(doctor))),member==doctor));
                    if(!CombatFallbackMath.Access(path.TotalCost,deadline,safe)){CohortTrace("clinical_access_rejected",member,null,destination);return false;}
                    maximumCost=Math.Max(maximumCost,path.TotalCost);
                }
            return true;
        }

        private static FallbackCohort NewCohort(Plan[] plans,List<Pawn> threats)
        {
            var map=plans[0].Pawn.Map;var doctor=ReservedDoctor(map);
            if(doctor==null || !CohortOwned(doctor))return null;
            // The tactical rally is relative to the CURRENT combat group. Beds
            // remain a clinical destination, not an instruction to put short
            // ranged guns behind an opaque room before they can fire again.
            bool meleeOnly=threats.All(MeleeThreat);
            IntVec3 medicalPost=IntVec3.Invalid;
            bool sharedPost=!meleeOnly && TryDoctorBoundAnchor(doctor,out medicalPost);
            var front=sharedPost?plans.Where(p=>p.Pawn!=doctor).ToArray():plans;
            var combatPositions=front.Select(p=>p.Pawn.Position).ToArray();
            var origin=new IntVec3((int)combatPositions.Average(c=>c.x),0,(int)combatPositions.Average(c=>c.z));
            var patients=map.mapPawns.FreeColonistsSpawned.Where(p=>p.Downed && !p.Dead && p.Position.InHorDistOf(origin,20)).ToArray();
            if(patients.Any())origin=patients.OrderBy(p=>CareTriageHelper.BleedoutTicks(p) ?? 0).First().Position;
            float dx=origin.x-(float)threats.Average(t=>t.Position.x),dz=origin.z-(float)threats.Average(t=>t.Position.z);
            float length=(float)Math.Sqrt(dx*dx+dz*dz);if(length<1)return null;
            // One bound is at most one third of the shortest loaded firing
            // cycle, capped by the local neighborhood. The old six-cell rear
            // put the first SMG out of fire for189ticks before others moved.
            float bound=plans.Min(p=>CombatFallbackMath.BoundDistance(TeamCycle(p.Pawn),Speed(p.Pawn)));
            if(bound<=0)return null;
            var rear=new IntVec3(origin.x+(int)Math.Round(dx/length*bound),0,origin.z+(int)Math.Round(dz/length*bound));
            // Rank physical positions only; each route, endpoint, covering gun
            // and clinical corridor is independently rechecked before issuing.
            // A short melee bound and a rear firing edge are different search
            // spaces. The old ranged disc inspected only open ground around
            // the front row; each rejected exposed point excluded the entire
            // group. The finite cursor now also reaches existing shelter edges.
            // Admission still requires the same forecast, future shot, route,
            // actual covering projectile and physician-access proof.
            var anchors=GenRadial.RadialCellsAround(rear,meleeOnly?4:12,true).Where(c=>CohortCell(doctor,c)
                && c.DistanceTo(origin)<=(meleeOnly?12:18) && plans.All(p=>c.DistanceTo(p.Anchor)<=26))
                .OrderBy(c=>c.DistanceToSquared(rear));
            foreach(var cell in meleeOnly?anchors.Take(6):ReviewEscapeCells(doctor,threats.First(),"ranged_cohort_anchor",anchors,2))
            {
                CombatPathBudgetHelper.Checkpoint("cohort_anchor");
                float exposure=IncomingRangedExposure(doctor,cell,Math.Min(600,TeamCycle(doctor)*2+240));
                if(meleeOnly?!CombatFallbackMath.Protected(exposure):!CombatPhysicianLineMath.Terminal(exposure,false))continue;
                if(threats.Where(MeleeThreat).Any(t=>cell.DistanceTo(t.Position)<12))continue;
                if(!meleeOnly && !CohortAnchorHasShot(plans,cell,threats))continue;
                var cohort=new FallbackCohort{Doctor=doctor,Origin=origin,Anchor=cell,Created=Find.TickManager.TicksGame,
                    Until=Find.TickManager.TicksGame+1800,Members=plans.Select(p=>p.Pawn.thingIDNumber).ToArray()};
                // Translate the real melee line instead of funneling four
                // independently pursued guns into one three-cell rally disc.
                // Native path, future-shot/FF and clinical checks remain below.
                if(meleeOnly)foreach(var plan in plans)cohort.Offsets[plan.Pawn]=plan.Pawn.Position-origin;
                if(sharedPost && !patients.Any())cohort.Posts[doctor]=medicalPost;
                TeamEvent("cohort_clinical_anchor_selected",doctor);return cohort;
            }
            return null;
        }

        // A cell not yet reached need not shoot the target's OLD location.
        // Actual covering fire still uses CanShootNow and a real projectile.
        // This candidate's follow-up needs only the loaded native future Pawn
        // geometry at the measured move/aim/burst/flight horizon.
        private static Pawn CohortArrivalShot(Pawn p,IntVec3 cell,float travel,List<Pawn> threats)
        {
            var v=p.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            float locked=CombatInterceptHelper.MovementLockTicks(p);
            float aim=v.verbProps.warmupTime*60*p.GetStatValue(StatDefOf.AimingDelayFactor);
            float burst=Math.Max(0,v.verbProps.burstShotCount-1)*v.verbProps.ticksBetweenBurstShots;
            float baseHorizon=CombatFallbackMath.FutureShotHorizon(travel,locked,aim,burst,0);
            if(float.IsInfinity(baseHorizon))return null;
            foreach(var t in threats.OrderByDescending(t=>ObservedRangedPressure(t,new[]{p})))
            {
                CombatPathBudgetHelper.Checkpoint("cohort_future_shot");
                if(!CombatInterceptHelper.TryObservedFuturePosition(t,baseHorizon,out var future))continue;
                float flight=CombatInterceptMath.NativeFlightTicks(cell.DistanceTo(future),
                    v.verbProps.defaultProjectile?.projectile?.SpeedTilesPerTick ?? 0);
                float horizon=CombatFallbackMath.FutureShotHorizon(travel,locked,aim,burst,flight);
                if(float.IsInfinity(horizon) || !CombatInterceptHelper.TryObservedFuturePosition(t,horizon,out future))continue;
                if(CombatExposureHelper.CanHitPawnAt(v,t,cell,future)==true
                    && CombatInterceptHelper.FutureFriendlyLaneClear(p,t,cell,future,"cohort_arrival_shot"))return t;
            }
            return null;
        }

        private static bool CohortReadyMeleeMover(Plan plan,List<Pawn> threats)
            =>!threats.All(MeleeThreat) || CriticalRangedInjury(plan.Pawn) || MedicalFunctionWarning(plan.Pawn)
                || threats.Any(t=>CombatInterceptHelper.CanShootNow(plan.Pawn,t));

        // Preparing a covering TARGET must precede the first generic warmup,
        // but optional path search must not starve the group's firing phase.
        // This phase issues no movement and acquires no PawnPath. It uses only
        // the existing strict gun window and exact owned current-position shot.
        private static void PrepareOpeningCohortCover()
        {
            int tick=Find.TickManager.TicksGame;
            foreach(var group in Plans.Values.Where(Valid).GroupBy(p=>p.Pawn.Map).ToArray())
            {
                var threats=group.Key.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
                if(!threats.Any() || !threats.All(MeleeThreat) || threats.Any(CombatNativeHelper.AbductionThreat))continue;
                var plans=group.Where(p=>CohortOwned(p.Pawn) && DefensivePlan(p.Tactic)).ToArray();
                if(plans.Length<3 || plans.Any(p=>TeamImmediateDanger(p.Pawn)))continue;
                if(!FallbackCohorts.TryGetValue(group.Key,out var c))
                {
                    c=NewCohort(plans,threats);if(c==null)continue;FallbackCohorts[group.Key]=c;
                }
                if(PendingCohort(c) || tick-c.Created>180)continue;
                var mover=plans.Where(p=>CohortStationary(p,threats) && CohortReadyMeleeMover(p,threats)
                        && !c.Staged.Contains(p.Pawn))
                    .OrderBy(p=>EarliestContact(p.Pawn,threats)).ThenByDescending(p=>p.Pawn==c.Doctor).FirstOrDefault();
                if(mover==null)continue;
                var enemy=threats.Where(t=>CombatInterceptHelper.Pursuing(t,mover.Pawn))
                    .OrderBy(t=>CombatInterceptHelper.ContactTicks(t,mover.Pawn)).FirstOrDefault();
                if(enemy==null)continue;
                var gun=plans.Where(p=>p!=mover && CohortStationary(p,threats)
                        && CohortGunFreeFor(p.Pawn,mover.Pawn,enemy) && CoverGunWindow(p.Pawn,enemy,threats))
                    .OrderByDescending(p=>AimTarget(p.Pawn)==enemy).ThenBy(p=>p.Pawn==c.Doctor).FirstOrDefault();
                if(gun==null || gun.Pawn.stances.curStance is Stance_Warmup
                    || gun.Pawn.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb.state==VerbState.Bursting)continue;
                var shot=JobMaker.MakeJob(JobDefOf.AttackStatic,enemy);shot.playerForced=true;
                if(!CombatOrderHelper.Take(gun.Pawn,ref shot))continue;
                gun.OwnedJob=shot;gun.Target=enemy;gun.Mode="shoot";
                c.PendingMover=mover.Pawn;c.PendingGun=gun.Pawn;c.PendingEnemy=enemy;
                c.PendingUntil=tick+(int)Math.Min(180,TeamCycle(gun.Pawn)+30);
                TeamEvent("opening_same_enemy_cover_prepared_before_generic_fire",gun.Pawn,enemy,mover.Pawn);
            }
        }

        private static void ReviewFallbackCohorts()
        {
            int tick=Find.TickManager.TicksGame;
            foreach(var map in FallbackCohorts.Keys.ToArray())
                if(!Find.Maps.Contains(map) || tick>FallbackCohorts[map].Until || !Plans.Values.Any(p=>Valid(p) && p.Pawn.Map==map))
                    FallbackCohorts.Remove(map);
            foreach(var p in FallbackMoves.Keys.ToArray())
                if(!p.Spawned || p.Dead || tick>FallbackMoves[p].Until || !FallbackCohorts.ContainsKey(p.Map))FallbackMoves.Remove(p);
            foreach(var group in Plans.Values.Where(Valid).GroupBy(p=>p.Pawn.Map).ToArray())
            {
                var map=group.Key;var threats=map.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
                FallbackCohorts.TryGetValue(map,out var enrolled);
                var plans=group.Where(p=>CohortCompatible(p.Tactic,threats.All(MeleeThreat),
                    enrolled!=null && enrolled.Members.Contains(p.Pawn.thingIDNumber)) && CohortOwned(p.Pawn)).ToArray();
                if(plans.Length<2 || !threats.Any() || threats.Any(CombatNativeHelper.AbductionThreat))
                {CohortTrace("no_owned_defensive_group_or_abduction");FallbackCohorts.Remove(map);continue;}
                if(!FallbackCohorts.TryGetValue(map,out var cohort) || tick>cohort.Until || !cohort.Doctor.Spawned || cohort.Doctor.Dead || cohort.Doctor.Downed)
                {
                    bool pressure=plans.Any(p=>IncomingRangedExposure(p.Pawn,p.Pawn.Position,Math.Min(600,TeamCycle(p.Pawn)*2+180))>=.6f
                        || threats.Any(t=>MeleeThreat(t) && CombatInterceptHelper.Pursuing(t,p.Pawn)
                            && CombatInterceptHelper.ContactTicks(t,p.Pawn)<=TeamCycle(p.Pawn)*2+180));
                    if(!pressure){CohortTrace("no_pressure");continue;}
                    cohort=NewCohort(plans,threats);if(cohort==null){CohortTrace("no_anchor");continue;}FallbackCohorts[map]=cohort;
                    if(threats.All(MeleeThreat) && CoverTurns.TryGetValue(map,out var obsolete))
                        EndCoverTurn(map,obsolete,"cover_turn_role_superseded_by_checked_cohort");
                }
                if(tick<cohort.NextReview)continue;cohort.NextReview=tick+30;
                // The deadline guard and the formation controller share the
                // same exact owned native withdrawals. Record that committed
                // move, rather than treating its actor as stationary or waiting
                // forever for a cohort-only receipt that was never created.
                // This records an accepted goal, not arrival or clinical access.
                foreach(var movingPlan in plans.Where(p=>p.Mode=="retreat"
                    && p.Pawn.CurJobDef==JobDefOf.Goto && p.OwnedJob==p.Pawn.CurJob
                    && CombatOrderHelper.Owned(p.Pawn,p.Pawn.CurJob)))
                {
                    var p=movingPlan.Pawn;var move=p.CurJob;
                    if(FallbackMoves.TryGetValue(p,out var oldMove) && oldMove.Job.Value==move)continue;
                    var goal=move.targetA.Cell;
                    if(!goal.InBounds(map) || goal==p.Position)continue;
                    cohort.Posts[p]=goal;cohort.Staged.Remove(p);
                    FallbackMoves[p]=new FallbackMove{Job=new CombatJobStamp(move),Goal=goal,Until=tick+900};
                    CohortTrace("owned_deadline_withdrawal_joined_cohort",p,movingPlan.Target,goal);
                }
                // A physician can acquire a checked early bound after a cohort
                // already exists. Do not leave the other guns on its old rally.
                // Existing cohort movers keep their exact covering transaction.
                if(TryDoctorBoundAnchor(cohort.Doctor,out var committed)
                    && (!cohort.Posts.TryGetValue(cohort.Doctor,out var heldPost) || heldPost!=committed)
                    && !plans.Any(CohortInTransit))
                {
                    var shared=NewCohort(plans,threats);
                    if(shared!=null)
                    {shared.NextReview=tick+30;FallbackCohorts[map]=cohort=shared;CohortTrace("cohort_synced_to_checked_physician_bound");}
                }
                if(threats.All(MeleeThreat) && plans.All(p=>cohort.Staged.Contains(p.Pawn))
                    && !plans.Any(p=>p.Pawn.CurJobDef==JobDefOf.Goto)
                    && plans.Any(p=>EarliestContact(p.Pawn,threats)<=TeamCycle(p.Pawn)*2+180))
                {
                    var next=NewCohort(plans,threats);
                    if(next!=null){FallbackCohorts[map]=cohort=next;CohortTrace("next_checked_group_bound");}
                }
                // Against observed melee-only pressure two staggered movers may
                // use two remaining stationary guns. Each move STILL needs its
                // own actual same-enemy projectile and checked route/deadline.
                // Ranged keeps one exposed mover; a separately checked wholly
                // unexposed physician transit may coexist with two real guns.
                foreach(var arrived in plans.Where(p=>cohort.Posts.TryGetValue(p.Pawn,out var goal) && p.Pawn.Position==goal))
                {
                    bool useful=threats.All(MeleeThreat) || threats.Any(t=>CombatInterceptHelper.CanShootNow(arrived.Pawn,t))
                        || CombatNativeHelper.HasClinicalCareJob(arrived.Pawn);
                    if(useful && cohort.Staged.Add(arrived.Pawn))TeamEvent("cohort_native_arrival",arrived.Pawn,arrived.Target);
                    if(FallbackMoves.TryGetValue(arrived.Pawn,out var completed) && completed.Goal==arrived.Pawn.Position
                        && completed.Arrived<0)completed.Arrived=tick;
                    if(!useful)cohort.Staged.Remove(arrived.Pawn);
                }
                // Arrival completes one bound, not the whole fight. Waiting
                // for ALL original members to stage leaves the first arrivals
                // locked at a post that a fresh observed pursuer has reached.
                // Reopen only completed, actually fired bounds; never steal an
                // in-flight move or a fresh arrival's first covering volley.
                RecordCohortReceipts(cohort,plans);
                if(tick>=cohort.NextRenew && threats.All(MeleeThreat))
                {
                    var renew=plans.Where(p=>cohort.Staged.Contains(p.Pawn)
                        && FallbackMoves.TryGetValue(p.Pawn,out var done)
                        && CombatFallbackMath.RenewCompleted(true,p.Pawn.CurJobDef==JobDefOf.Goto,p.Pawn.Position==done.Goal,
                            threats.Any(t=>CombatShotEvidenceHelper.LastTick(p.Pawn,t.thingIDNumber)>=done.Arrived),
                            done.Arrived<0?-1:tick-done.Arrived,EarliestContact(p.Pawn,threats),TeamCycle(p.Pawn),
                            8f/Math.Max(.1f,Speed(p.Pawn))*60f)).ToArray();
                    if(renew.Length>0)
                    {
                        var next=NewCohort(plans,threats);
                        if(next!=null)
                        {
                            cohort.Anchor=next.Anchor;cohort.Origin=next.Origin;
                            cohort.NextRenew=tick+(int)plans.Min(p=>TeamCycle(p.Pawn));
                            foreach(var renewed in renew)
                            {
                                // Retire the OLD receipt atomically with its
                                // staged flag. Keeping Posts made the next
                                // review re-stage the same unmoved actor and
                                // silently cancel the reopened withdrawal.
                                ReopenCompletedCohortBound(cohort,renewed.Pawn);
                                TeamEvent("completed_bound_reopened_after_actual_fire",renewed.Pawn,renewed.Target);
                            }
                            // Existing epoch/expiry, actual covering leases,
                            // posts and checked jobs stay intact. Every new
                            // route/shot/access proof is still made below.
                        }
                    }
                }
                int moving=CohortMovingCount(plans);
                bool protectedPhysicianMoving=plans.Any(p=>DoctorBoundInTransit(p) && KeepDoctorBoundIntent(p.Pawn));
                if(!CombatFallbackMath.MoveSlot(moving,plans.Count(p=>CohortStationary(p,threats))-1,threats.All(MeleeThreat) || protectedPhysicianMoving))
                {CohortTrace("owned_move_slots_full");continue;}
                var mover=PendingCohort(cohort)?plans.FirstOrDefault(p=>p.Pawn==cohort.PendingMover):plans.Where(p=>!cohort.Staged.Contains(p.Pawn))
                    .Where(p=>p.Pawn.CurJobDef!=JobDefOf.Goto && p.Pawn.CurJobDef!=JobDefOf.AttackMelee)
                    .Where(p=>CohortReadyMeleeMover(p,threats))
                    // Preserve one actually capable physician before spending
                    // both doctors as covering guns for nonmedical movers.
                    // R left only an actor with native Doctor disabled; the
                    // clear battlefield could not stop untreated blood loss.
                    // Immediate danger still runs before this optional phase;
                    // every actual route, deadline and covering shot is checked.
                    // One finite refusal is not a veto on all later actors.
                    // Keep a pending actual-cover transaction, otherwise review
                    // the least recently examined gun before returning to an
                    // unshootable physician or an exposed first candidate.
                    .OrderBy(p=>cohort.LastMemberReview.TryGetValue(p.Pawn,out var reviewed)?reviewed:-1)
                    .ThenByDescending(p=>p.Pawn==cohort.Doctor)
                    .ThenBy(p=>threats.All(MeleeThreat)?EarliestContact(p.Pawn,threats):10000)
                    .ThenByDescending(p=>p.Pawn.health.hediffSet.BleedRateTotal).FirstOrDefault();
                if(mover==null){CohortTrace("no_unstaged_stationary_mover");continue;}
                var pawn=mover.Pawn;var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
                cohort.LastMemberReview[pawn]=tick;
                bool physicianRejoin=!threats.All(MeleeThreat) && PhysicianAtBlindPost(mover,cohort,threats);
                if(TeamImmediateDanger(pawn) || !threats.All(MeleeThreat) && pawn.stances.curStance is Stance_Warmup || verb.state==VerbState.Bursting){CohortTrace("mover_contact_or_warmup",pawn);continue;}
                var enemy=PendingCohort(cohort)?cohort.PendingEnemy:threats.OrderByDescending(t=>ObservedVictim(t)==pawn?1000:0)
                    .ThenByDescending(t=>MeleeThreat(t)?CombatInterceptMath.MeleePriority(CombatInterceptHelper.ContactTicks(t,pawn)):
                        ObservedRangedPressure(t,new[]{pawn})*60).First();
                var gun=PendingCohort(cohort)?plans.FirstOrDefault(p=>p.Pawn==cohort.PendingGun):plans.Where(p=>p!=mover && CohortStationary(p,threats) && CohortGunFreeFor(p.Pawn,pawn,enemy) && CohortCoverWindow(p.Pawn,enemy,threats) && !KeepCoverTurn(p.Pawn,enemy))
                    .OrderByDescending(p=>AimTarget(p.Pawn)==enemy).ThenBy(p=>p.Pawn==cohort.Doctor).FirstOrDefault();
                bool actual=gun!=null && AimTarget(gun.Pawn)==enemy && CombatFallbackMath.CoverObserved(cohort.Created,
                    CombatShotEvidenceHelper.LastTick(gun.Pawn,enemy.thingIDNumber),tick,TeamCycle(gun.Pawn));
                // A blind physician need not borrow a gun for an independently
                // chosen, unshootable enemy. Bind the pair that is REALLY
                // firing now, then require the physician's future shot to that
                // exact same enemy. This is not a relaxation of cover safety.
                if(physicianRejoin && !actual && TryPhysicianCoverPair(mover,cohort,plans,threats,out var observedGun,out var observedEnemy))
                {gun=observedGun;enemy=observedEnemy;actual=true;CohortTrace("physician_actual_cover_pair_selected",pawn,enemy);}
                CohortTrace(actual?"actual_cover":gun==null?"no_cover_gun":"no_same_enemy_projectile",pawn,enemy);
                if(!actual)
                {
                    if(gun!=null && !PendingCohort(cohort))
                    {
                        cohort.PendingMover=pawn;cohort.PendingGun=gun.Pawn;cohort.PendingEnemy=enemy;
                        cohort.PendingUntil=tick+(int)Math.Min(180,TeamCycle(gun.Pawn)+30);
                        CohortTrace("pending_same_enemy_cover_bound",pawn,enemy);
                    }
                    if(gun!=null && !(gun.Pawn.stances.curStance is Stance_Warmup)
                        && gun.Pawn.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb.state!=VerbState.Bursting)
                    {
                        var shot=JobMaker.MakeJob(JobDefOf.AttackStatic,enemy);shot.playerForced=true;
                        if(CombatOrderHelper.Take(gun.Pawn,ref shot))
                        {gun.OwnedJob=shot;gun.Target=enemy;gun.Mode="shoot";TeamEvent("cohort_cover_prepared",gun.Pawn,enemy,pawn);}
                    }
                    // No proof of fire is not a covering transaction. Existing
                    // independent emergency exits remain authoritative.
                    continue;
                }
                // A blind physician is already at a real refuge. Searching
                // only the front group's three-cell rally disc can offer
                // nothing except crossfire. Search a short local firing edge
                // from that refuge; the same actual cover, clinical corridor,
                // measured route, future shot and FF checks still follow.
                var region=physicianRejoin?GenRadial.RadialCellsAround(pawn.Position,10,false):
                    GenRadial.RadialCellsAround(CohortFormationPost(cohort,pawn),threats.All(MeleeThreat)?2:3,true);
                var cells=region.Where(c=>c!=pawn.Position && CohortCell(pawn,c)
                    && !CellClaimed(pawn,c) && !cohort.Posts.Any(kv=>kv.Key!=pawn && kv.Value==c))
                    .OrderBy(c=>physicianRejoin?c.DistanceToSquared(pawn.Position)+c.DistanceToSquared(cohort.Anchor)*.05f:
                        c.DistanceToSquared(CohortFormationPost(cohort,pawn))+c.DistanceToSquared(pawn.Position)*(threats.All(MeleeThreat)?1.5f:.05f));
                foreach(var cell in ReviewEscapeCells(pawn,enemy,"cohort",cells,2))
                {
                    CohortTrace("candidate",pawn,enemy,cell);
                    // A short firing rejoin is judged over measured travel and
                    // its actual shot cycle below, not a long persistent-post
                    // forecast before the route is even known. Current danger
                    // still rejects here; full future route/shot checks remain.
                    float terminalHorizon=physicianRejoin?0:Math.Min(600,TeamCycle(pawn)*2+240);
                    float terminalExposure=IncomingRangedExposure(pawn,cell,terminalHorizon);
                    if(threats.All(MeleeThreat)?!CombatFallbackMath.Protected(terminalExposure):!CombatPhysicianLineMath.Terminal(terminalExposure,pawn==cohort.Doctor))
                    {CohortTrace("endpoint_exposed",pawn,enemy,cell,terminalExposure,terminalHorizon);continue;}
                    if(physicianRejoin && CohortArrivalShot(pawn,cell,
                        pawn.Position.DistanceTo(cell)*pawn.TicksPerMoveCardinal,new List<Pawn>{enemy})==null)
                    {CohortTrace("local_physician_edge_has_no_shot",pawn,enemy,cell);continue;}
                    using(var path=CombatPathBudgetHelper.Query(pawn,pawn.Position,cell,PathEndMode.OnCell))
                    {
                        float moveLimit=threats.All(MeleeThreat)?Math.Min(120f,TeamCycle(pawn)*.5f):480f;
                        if(!path.Found || path.TotalCost<=0 || path.TotalCost>moveLimit || !CombatTacticsHelper.RetreatRouteSafe(pawn,path)){CohortTrace("actor_route_rejected",pawn,enemy,cell);continue;}
                        float locked=CombatInterceptHelper.MovementLockTicks(pawn),travel=locked+path.TotalCost;
                        if(threats.Any(t=>t.equipment?.Primary?.def.IsRangedWeapon==true)
                            && !(physicianRejoin?CoveredPhysicianRejoin(pawn,path):SaferRangedRoute(pawn,path,false,out _)))
                        {CohortTrace("ranged_route_rejected",pawn,enemy,cell);continue;}
                        var rejoin=CohortArrivalShot(pawn,cell,path.TotalCost,physicianRejoin?new List<Pawn>{enemy}:threats);
                        if(rejoin==null && !MedicalFunctionWarning(pawn)){CohortTrace("no_future_rejoin_shot",pawn,enemy,cell);continue;}
                        float after=10000;
                        foreach(var pursuer in threats.Where(t=>MeleeThreat(t) && CombatInterceptHelper.Pursuing(t,pawn)).Take(2))
                            using(var pursuit=CombatPathBudgetHelper.Query(pursuer,pursuer.Position,cell,PathEndMode.Touch))
                            {if(!pursuit.Found){after=0;break;}after=Math.Min(after,pursuit.TotalCost+CombatInterceptHelper.MovementLockTicks(pursuer)-travel);}
                        if(!CombatFallbackMath.ArrivalMargin(after,verb.verbProps.warmupTime*60*pawn.GetStatValue(StatDefOf.AimingDelayFactor),
                            Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots,true)){CohortTrace("contact_deadline_rejected",pawn,enemy,cell);continue;}
                        if(!CohortAccess(cohort,pawn,cell,travel,out var accessCost))continue;
                        var move=JobMaker.MakeJob(JobDefOf.Goto,cell);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                        urgentTeamTransition=true;bool accepted;
                        try{accepted=CombatOrderHelper.Take(pawn,ref move);}finally{urgentTeamTransition=false;}
                        if(!accepted){CohortTrace("native_take_rejected",pawn,enemy,cell);continue;}
                        CohortTrace("native_take_accepted",pawn,enemy,cell);
                        cohort.PendingMover=cohort.PendingGun=cohort.PendingEnemy=null;
                        var follow=rejoin==null?null:CombatOrderHelper.QueueShot(pawn,rejoin);
                        move=RememberMove(pawn,move,follow);mover.OwnedJob=move;mover.QueuedShot=follow;mover.Target=enemy;
                        mover.Mode="retreat";mover.LastMoveTick=tick;mover.RangedWithdrawal=new CombatJobStamp(move);
                        RetreatJobs[pawn]=new CombatJobStamp(move);cohort.Posts[pawn]=cell;
                        FallbackMoves[pawn]=new FallbackMove{Job=new CombatJobStamp(move),Goal=cell,Until=tick+(int)Math.Min(900,travel+TeamCycle(pawn)*2+120),PhysicianRejoin=physicianRejoin,FromCohort=true};
                        CoverTransfers[gun.Pawn]=new CoverTransfer{Mover=pawn,Enemy=enemy,Until=tick+600};
#if LAYA_COMBAT_LAB
                        if(FallbackProofs.Count<72)FallbackProofs.Add(new{tick,pawn=pawn.thingIDNumber,
                            job_id=move.loadID,goal_x=cell.x,goal_z=cell.z,rejoin_target=rejoin?.thingIDNumber,queued_shot_id=follow?.loadID,anchor_x=cohort.Anchor.x,anchor_z=cohort.Anchor.z,
                            doctor=cohort.Doctor.thingIDNumber,cover_gun=gun.Pawn.thingIDNumber,target=enemy.thingIDNumber,
                            cover_shot_tick=CombatShotEvidenceHelper.LastTick(gun.Pawn,enemy.thingIDNumber),
                            cohort_created=cohort.Created,travel_ticks=travel,contact_after_arrival=after,access_cost=accessCost,
                            clinical_origin_x=cohort.Origin.x,clinical_origin_z=cohort.Origin.z});
#endif
                        TeamEvent(physicianRejoin?"physician_post_arrival_firing_rejoin":"cohort_move_after_actual_cover_and_access",pawn,enemy,gun.Pawn);return;
                    }
                }
            }
        }

        private static bool ReviewCohortMember(Plan plan,List<Pawn> threats)
        {
            var p=plan.Pawn;
            if(!CohortLive(p,out var cohort) || !cohort.Posts.TryGetValue(p,out var goal))return false;
            if(CohortInTransit(plan))
            {
                if(PendingOwnedRangedMove(plan))return true;
                var path=p.pather.curPath;
                using(var observed=CombatPathBudgetHelper.Borrowed(path))
                    if(observed.Found && CombatInterceptHelper.MovementCellsSafe(p,RemainingRangedCells(p,observed))
                        && (FallbackMoves[p].PhysicianRejoin?RejoinRemainingSafe(plan,observed):
                            !threats.Any(t=>t.equipment?.Primary?.def.IsRangedWeapon==true) || SaferRangedRoute(p,observed,true,out _)))return true;
                FallbackMoves.Remove(p);return false;
            }
            if(p.Position!=goal || TeamImmediateDanger(p) || (threats.All(MeleeThreat)
                ?!CombatFallbackMath.Protected(IncomingRangedExposure(p,goal,TeamCycle(p)))
                :!CombatPhysicianLineMath.Terminal(IncomingRangedExposure(p,goal,TeamCycle(p)),p==cohort.Doctor)))return false;
            if(threats.Any(t=>MeleeThreat(t) && CombatInterceptHelper.ContactTicks(t,p)<=TeamCycle(p)+90))return false;
            var target=CoordinatedTarget(p,threats) ?? threats.Where(t=>CombatInterceptHelper.CanShootNow(p,t))
                .OrderByDescending(t=>ObservedRangedPressure(t,new[]{p})).FirstOrDefault();
            if(target!=null && (p.CurJobDef!=JobDefOf.AttackStatic || p.CurJob.targetA.Thing!=target))
            {
                var shot=JobMaker.MakeJob(JobDefOf.AttackStatic,target);shot.playerForced=true;
                if(CombatOrderHelper.Take(p,ref shot))
                {plan.OwnedJob=shot;plan.Target=target;plan.Mode="shoot";TeamEvent("cohort_arrived_rejoined_fire",p,target);}
            }
            return target!=null;
        }
    }
}

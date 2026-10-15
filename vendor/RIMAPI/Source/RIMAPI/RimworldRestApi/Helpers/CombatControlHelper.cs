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
    public static class CombatControlHelper
    {
        private class Plan
        {
            public Pawn Pawn; public string Tactic; public IntVec3 Anchor;
            public Job OwnedJob, QueuedShot; public Pawn Target; public int UntilTick;
            public DateTime UntilUtc; public string Mode; public int LastMoveTick;
            public IntVec3 ProgressCell; public int ProgressTick;
            public int RangedCoverReviewTick;
            public Building WatchedBreach; public IntVec3 BreachPosition;
        }
        private static readonly Dictionary<int,Plan> Plans=new Dictionary<int,Plan>();
        private static readonly Dictionary<Pawn,Job> RetreatJobs=new Dictionary<Pawn,Job>();
        private static readonly Dictionary<Pawn,KeyValuePair<Job,Job>> SelectedMoves=new Dictionary<Pawn,KeyValuePair<Job,Job>>();
        private static readonly HashSet<string> RangedPlans=new HashSet<string>{"hold_cover","firing_line","focus_fire","advance_to_range","preemptive_strike","intercept_kidnapper","backstep_fire","kite","contact_melee","stationary_fire","fallback_line","spread_out","withdraw_and_regroup"};
#if LAYA_COMBAT_LAB
        public static bool TestDisabled;
        public static int PulseTicks,Remembered,Cancelled,Retreated,Attempted;
        public static object Diagnostics()=>new {component=Current.Game.GetComponent<CombatControlComponent>()!=null,plans=Plans.Count,pulses=PulseTicks,remembered=Remembered,cancelled=Cancelled,retreated=Retreated,attempted=Attempted};
        public static void TestReset(bool disabled){TestDisabled=disabled;Plans.Clear();RetreatJobs.Clear();SelectedMoves.Clear();PulseTicks=Remembered=Cancelled=Retreated=Attempted=0;}
#endif
        public static void RememberMove(Pawn pawn,Job move,Job shot)
            => SelectedMoves[pawn]=new KeyValuePair<Job,Job>(move,shot);
        public static void RememberRegroup(Pawn pawn,Job move)
        {RetreatJobs[pawn]=move;RememberMove(pawn,move,null);if(Plans.TryGetValue(pawn.thingIDNumber,out var plan))plan.LastMoveTick=Find.TickManager.TicksGame;}
        private static bool Present(Pawn pawn,Job job) => job!=null
            && (pawn.CurJob==job || pawn.jobs.jobQueue.Any(q=>q.job==job));
        public static bool CellClaimed(Pawn pawn,IntVec3 cell) => pawn.Map.mapPawns.FreeColonistsSpawned.ToArray()
            .Any(p=>p!=pawn && p.Drafted && !p.Dead && !p.Downed
                && (p.CurJobDef==JobDefOf.Goto && p.CurJob.targetA.Cell==cell
                    || p.jobs.jobQueue.Any(q=>q.job.def==JobDefOf.Goto && q.job.targetA.Cell==cell)));
        private static bool StuckAtContact(Plan plan) => Find.TickManager.TicksGame-Math.Max(plan.ProgressTick,plan.LastMoveTick)>=60
            && plan.Pawn.Map.mapPawns.AllPawnsSpawned.Any(e=>Threat(e) && MeleeThreat(e)
                && e.Position.InHorDistOf(plan.Pawn.Position,2.1f));
        public static string CurrentPlan(Pawn pawn) => Plans.TryGetValue(pawn.thingIDNumber,out var p) && Valid(p) ? p.Tactic : null;
        public static IntVec3 DefensiveAnchor(Pawn pawn) => Plans.TryGetValue(pawn.thingIDNumber,out var p) && Valid(p) ? p.Anchor : pawn.Position;
        public static bool PreserveEscape(Pawn pawn,string nextTactic)
        {
            if(!RangedPlans.Contains(nextTactic) || !Plans.TryGetValue(pawn.thingIDNumber,out var plan) || !Valid(plan))return false;
            if(HoldingBreach(plan,nextTactic))return true;
            if(plan.Mode!="retreat" || plan.OwnedJob?.def!=JobDefOf.Goto || StuckAtContact(plan))return false;
            bool pending=pawn.jobs.jobQueue.Any(q=>q.job==plan.OwnedJob);
            return pending || pawn.CurJob==plan.OwnedJob && pawn.pather.Moving
                && !plan.OwnedJob.targetA.Cell.ContainsStaticFire(pawn.Map)
                && pawn.Map.gasGrid.DensityAt(plan.OwnedJob.targetA.Cell,GasType.ToxGas)==0
                && pawn.Map.gasGrid.DensityAt(plan.OwnedJob.targetA.Cell,GasType.DeadlifeDust)==0;
        }
        public static bool PreserveShot(Pawn pawn,string nextTactic)
        {
            if(!Eligible(pawn) || !new[]{"hold_cover","firing_line","focus_fire","advance_to_range","stationary_fire","fallback_line"}.Contains(nextTactic)
                || (pawn.CurJobDef!=JobDefOf.AttackStatic && pawn.CurJobDef!=JobDefOf.Wait_Combat)
                || !(AimTarget(pawn) is Pawn target))return false;
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            return (pawn.stances.curStance is Stance_Warmup || verb?.state==VerbState.Bursting)
                && Threat(target) && CombatInterceptHelper.CanShootNow(pawn,target);
        }
        public static Pawn AimTarget(Pawn pawn)
        {
            var verb=pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(pawn.stances?.curStance is Stance_Warmup || verb?.state==VerbState.Bursting)
                return (pawn.stances?.curStance as Stance_Busy)?.focusTarg.Thing as Pawn
                    ?? pawn.CurJob?.targetA.Thing as Pawn;
            return pawn.CurJobDef==JobDefOf.AttackStatic ? pawn.CurJob?.targetA.Thing as Pawn:null;
        }
        private static bool Eligible(Pawn p) => p!=null && p.Spawned && !p.Dead && !p.Downed && p.Drafted && !p.InMentalState
            && !p.WorkTagIsDisabled(WorkTags.Violent) && p.equipment?.Primary?.def.IsRangedWeapon==true
            && !CombatNativeHelper.Protected(p) && !CareTriageHelper.QueuedCare(p);
        private static bool Valid(Plan p) => Eligible(p.Pawn) && Find.Maps.Contains(p.Pawn.Map)
            && Find.TickManager.TicksGame<=p.UntilTick && DateTime.UtcNow<=p.UntilUtc;
        public static void Remember(CombatTacticRequestDto request,CombatTacticResponseDto result,Map map)
        {
            if(request.Tactic=="stand_down") {foreach(Pawn p in map.mapPawns.FreeColonistsSpawned.Where(p=>!p.Drafted))Plans.Remove(p.thingIDNumber);return;}
            if(!RangedPlans.Contains(request.Tactic) || (!result.Applied && !result.PreservedPawnIds.Any()))return;
            foreach(Pawn p in map.mapPawns.FreeColonistsSpawned.Where(p=>request.FighterIds.Contains(p.thingIDNumber) && Eligible(p)))
            {
                bool preserved=result.PreservedPawnIds.Contains(p.thingIDNumber);
                if(!preserved && !result.AttackingPawnIds.Contains(p.thingIDNumber)
                    && !result.PositionedPawnIds.Contains(p.thingIDNumber))continue;
                if(Plans.TryGetValue(p.thingIDNumber,out var held) && Valid(held)
                    && preserved && (Present(p,held.OwnedJob) || HoldingBreach(held,request.Tactic)))
                {
                    // A preserved shot/escape did not execute the newly requested
                    // tactic. Renew its existing role without changing that role.
                    held.UntilTick=Find.TickManager.TicksGame+1200;held.UntilUtc=DateTime.UtcNow.AddSeconds(30);
                    continue;
                }
                if(!Plans.TryGetValue(p.thingIDNumber,out var plan) || !Valid(plan))
                    plan=new Plan{Pawn=p,Anchor=p.Position,Tactic=request.Tactic,ProgressCell=p.Position,ProgressTick=Find.TickManager.TicksGame};
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
                        plan.Mode=RetreatJobs.TryGetValue(p,out var retreat) && retreat==selected.Key ? "retreat":"position";
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
            foreach(int id in ids ?? new List<int>())if(Plans.TryGetValue(id,out var plan) && Valid(plan) && plan.Pawn.Map==map)
            {
                plan.UntilTick=Find.TickManager.TicksGame+1200;plan.UntilUtc=DateTime.UtcNow.AddSeconds(30);
                result.Notes.Add("Existing selected control lease refreshed; no new pawn order.");
            }
            return result;
        }
        private static bool Threat(Pawn p) => p.Spawned && !p.Dead && !p.Downed && !p.Position.Fogged(p.Map) && CombatNativeHelper.IsPlayerThreat(p);
        private static float Speed(Pawn p) => 60f/Math.Max(1f,p.TicksPerMoveCardinal);
        private static bool MeleeThreat(Pawn p)=>p.equipment?.Primary?.def.IsRangedWeapon!=true || p.CurJobDef==JobDefOf.AttackMelee;
        private static bool DefensivePlan(string tactic)=>new[]{"hold_cover","firing_line","focus_fire","stationary_fire","fallback_line"}.Contains(tactic);
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
                if(cell==pawn.Position){plan.WatchedBreach=wall;plan.BreachPosition=cell;return true;}
                using(var path=map.pathFinder.FindPathNow(pawn.Position,cell,pawn,null,PathEndMode.OnCell))
                    if(path.TotalCost>480f || !CombatInterceptHelper.MovementSafe(pawn,path)
                        || path.NodesReversed.Any(c=>c.GetRoom(map)!=room))continue;
                var move=JobMaker.MakeJob(JobDefOf.Goto,cell);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                if(!MentalSafetyHelper.TakeDefenceOrder(pawn,move))continue;
                RememberMove(pawn,move,null);plan.OwnedJob=move;plan.QueuedShot=null;plan.Target=attacker;
                plan.WatchedBreach=wall;plan.BreachPosition=cell;plan.Mode="breach";
                return true;
            }
            return false;
        }
        public static float IncomingRangedExposure(Pawn pawn,IntVec3 cell)
        {
            // Sum of uncovered native firing lanes, not a probability of injury.
            // A wall facing the selected target does not protect the other flank.
            return pawn.Map.mapPawns.AllPawnsSpawned.Where(e=>Threat(e)
                    && e.equipment?.Primary?.def.IsRangedWeapon==true)
                .Where(e=>e.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb?.CanHitTargetFrom(e.Position,new LocalTargetInfo(cell))==true)
                .Sum(e=>1f-CoverUtility.CalculateOverallBlockChance(new LocalTargetInfo(cell),e.Position,pawn.Map));
        }
        public static bool TryCoveredShot(Pawn pawn,Pawn target,out IntVec3 cell)
        {
            cell=IntVec3.Invalid;if(!Eligible(pawn) || target==null)return false;
            var map=pawn.Map;var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            float current=IncomingRangedExposure(pawn,pawn.Position);
            if(current<.35f || pawn.stances.curStance is Stance_Warmup || verb?.state==VerbState.Bursting)return false;
            bool firingNow=verb?.CanHitTargetFrom(pawn.Position,target)==true;
            var enemies=map.mapPawns.AllPawnsSpawned.Where(Threat).ToArray();
            var cells=GenRadial.RadialCellsAround(pawn.Position,4f,false).Where(c=>c.InBounds(map) && c.Standable(map) && !c.Fogged(map)
                && !c.GetThingList(map).Any(t=>t is Pawn) && !CellClaimed(pawn,c) && c.DistanceTo(DefensiveAnchor(pawn))<=8f
                && (verb?.CanHitTargetFrom(c,target)==true || !firingNow
                    && CombatInterceptHelper.IncomingToRange(pawn,target,c,out var expected) && c.DistanceTo(expected)>=12f)
                && CombatInterceptHelper.FriendlyLaneClear(pawn,target,c)
                && enemies.All(e=>c.DistanceTo(e.Position)>=12f))
                .Select(c=>new {Cell=c,Exposure=IncomingRangedExposure(pawn,c)})
                .Where(c=>c.Exposure<=current-.2f).OrderBy(c=>c.Exposure+c.Cell.DistanceTo(pawn.Position)*.025f).Take(8);
            foreach(var candidate in cells)
                using(var path=map.pathFinder.FindPathNow(pawn.Position,candidate.Cell,pawn,null,PathEndMode.OnCell))
                    if(path.TotalCost<=240f && CombatInterceptHelper.MovementSafe(pawn,path)){cell=candidate.Cell;return true;}
            return false;
        }
        private static Pawn GroupTarget(Pawn pawn,List<Pawn> threats)
        {
            var guns=Plans.Values.Where(Valid).Select(p=>p.Pawn).Where(p=>p.Map==pawn.Map).ToArray();
            return threats.Where(t=>CombatInterceptHelper.CanShootNow(pawn,t))
                .OrderByDescending(t=>CombatNativeHelper.Kidnapper(t)?10000f:
                    guns.Count(g=>g.CurJobDef!=JobDefOf.Goto && g.CurJobDef!=JobDefOf.AttackMelee
                        && g.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb?.CanHitTargetFrom(g.Position,t)==true)*8f
                    +(1f-t.health.summaryHealth.SummaryHealthPercent)*18f
                    +(guns.Any(g=>CombatInterceptHelper.Pursuing(t,g))?20f:0f)
                    +(t.equipment?.Primary?.def.IsRangedWeapon!=true && guns.Any(g=>g.Position.DistanceTo(t.Position)<7f)?100f:0f)
                    +Math.Max(0,25f-guns.Select(g=>g.Position.DistanceTo(t.Position)).DefaultIfEmpty(99).Min()))
                .ThenBy(t=>t.thingIDNumber).FirstOrDefault();
        }
        private static bool TryBreakRangedContact(Plan plan,List<Pawn> threats)
        {
            Pawn pawn=plan.Pawn;int tick=Find.TickManager.TicksGame;
            if(!Eligible(pawn))return false;
            if(pawn.health.summaryHealth.SummaryHealthPercent>=.9f && pawn.health.hediffSet.BleedRateTotal<.25f
                && pawn.health.hediffSet.PainTotal<.18f)return false;
            if(tick<plan.RangedCoverReviewTick)return false;
            plan.RangedCoverReviewTick=tick+90;
            if(threats.Any(e=>MeleeThreat(e) && pawn.Position.DistanceTo(e.Position)<8f))return false;
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(verb?.state==VerbState.Bursting || IncomingRangedExposure(pawn,pawn.Position)<.6f)return false;
            var map=pawn.Map;
            // Temporarily losing a firing lane is preferable to leaving an
            // already wounded gun in observed crossfire. Other selected guns
            // keep their jobs; this is an ordinary checked movement order.
            var cells=GenRadial.RadialCellsAround(pawn.Position,8f,false)
                .Where(c=>c.InBounds(map) && c.Standable(map) && !c.Fogged(map)
                    && c.DistanceTo(plan.Anchor)<=16f && !CellClaimed(pawn,c)
                    && !c.GetThingList(map).Any(t=>t is Pawn || t is Building_Trap && t.Faction==Faction.OfPlayer)
                    && threats.All(e=>c.DistanceTo(e.Position)>=8f))
                .Take(96).Where(c=>IncomingRangedExposure(pawn,c)<=.1f).Take(8);
            foreach(var cell in cells)
            {
                using(var path=map.pathFinder.FindPathNow(pawn.Position,cell,pawn,null,PathEndMode.OnCell))
                    if(path.TotalCost>480f || !CombatInterceptHelper.MovementSafe(pawn,path))continue;
                var move=JobMaker.MakeJob(JobDefOf.Goto,cell);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                pawn.stances.CancelBusyStanceSoft();
                if(pawn.CurJobDef==JobDefOf.AttackStatic)pawn.jobs.EndCurrentJob(JobCondition.InterruptForced,false);
                if(!MentalSafetyHelper.TakeDefenceOrder(pawn,move))continue;
                RememberMove(pawn,move,null);RetreatJobs[pawn]=move;
                plan.OwnedJob=move;plan.QueuedShot=null;plan.Mode="retreat";plan.LastMoveTick=tick;
                return true;
            }
            return false;
        }
        public static bool TryRangedRetreat(Pawn pawn,Pawn target,IntVec3 anchor,out Job issued)
        {
            issued=null;if(!Eligible(pawn))return false;
#if LAYA_COMBAT_LAB
            if(TestDisabled)return false;
            Attempted++;
#endif
            Map map=pawn.Map;
            var threats=map.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
            var close=threats.Where(MeleeThreat).ToList();
            if(!close.Any())return false;
            float old=close.Min(t=>pawn.Position.DistanceTo(t.Position));
            // Under adjacent melee hits, stagger and wounds can make a nominal
            // escape impossible. Do not repeatedly replace self-defence with it.
            if(close.Any(t=>t.Position.InHorDistOf(pawn.Position,2.1f)
                && CombatInterceptHelper.Pursuing(t,pawn) && Speed(pawn)<=Speed(t)*1.1f))return false;
            var covering=CombatInterceptHelper.ReadyCover(pawn,target);
            var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            var candidates=GenRadial.RadialCellsAround(pawn.Position,8f,false).Where(c=>c.InBounds(map) && c.Standable(map) && !c.Fogged(map)
                && !c.ContainsStaticFire(map) && map.gasGrid.DensityAt(c,GasType.ToxGas)==0 && map.gasGrid.DensityAt(c,GasType.DeadlifeDust)==0
                && !c.GetThingList(map).Any(t=>t is Pawn || t is Building_Trap && t.Faction==Faction.OfPlayer) && !CellClaimed(pawn,c)
                && c.DistanceTo(anchor)<=26f && close.Min(t=>c.DistanceTo(t.Position))>=Math.Max(6f,old+3f)
                && (target==null || c.DistanceTo(target.Position)<=(verb?.verbProps.range ?? 0)-1f))
                // Escaping a sword does not require keeping a shot through
                // every wall. That requirement forced exposed forward/side
                // moves when a safe rear cell temporarily lost sight.
                .OrderByDescending(c=>close.Min(t=>c.DistanceTo(t.Position))*3f-c.DistanceTo(anchor)*.7f
                    -IncomingRangedExposure(pawn,c)*40f
                    +covering.Count(g=>c.InHorDistOf(g.Position,16f)
                        && g.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb.CanHitTargetFrom(g.Position,new LocalTargetInfo(c)))*16f)
                .Take(8).ToList();
            foreach(var cell in candidates)
            {
                using(var path=map.pathFinder.FindPathNow(pawn.Position,cell,pawn,null,PathEndMode.OnCell))
                {
                    if(!CombatTacticsHelper.RetreatRouteSafe(pawn,path))continue;
                    if(path.NodesReversed.Any(c=>map.gasGrid.DensityAt(c,GasType.ToxGas)>0 || map.gasGrid.DensityAt(c,GasType.DeadlifeDust)>0))continue;
                }
                var move=JobMaker.MakeJob(JobDefOf.Goto,cell);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                // A verified emergency escape must interrupt aiming. Otherwise
                // the move can wait behind the very shot that contact prevents.
                pawn.stances.CancelBusyStanceSoft();
                if(pawn.CurJobDef==JobDefOf.AttackStatic)
                    pawn.jobs.EndCurrentJob(JobCondition.InterruptForced,false);
                if(!MentalSafetyHelper.TakeDefenceOrder(pawn,move))continue;
                Job shot=null;
                if(target!=null){shot=JobMaker.MakeJob(JobDefOf.AttackStatic,target);shot.playerForced=true;pawn.jobs.jobQueue.EnqueueLast(shot);}
                RememberMove(pawn,move,shot);
                if(Plans.TryGetValue(pawn.thingIDNumber,out var selectedPlan))selectedPlan.LastMoveTick=Find.TickManager.TicksGame;
                RetreatJobs[pawn]=move;issued=move;
#if LAYA_COMBAT_LAB
                Retreated++;
#endif
                return true;
            }
            return false;
        }
        public static void Tick()
        {
#if LAYA_COMBAT_LAB
            if(TestDisabled)return;
#endif
            if(Find.TickManager==null || Find.TickManager.TicksGame%15!=0)return;
#if LAYA_COMBAT_LAB
            PulseTicks++;
#endif
            foreach(var pawn in SelectedMoves.Keys.ToArray())
                if(!pawn.Spawned || pawn.Dead || !Present(pawn,SelectedMoves[pawn].Key) && !Present(pawn,SelectedMoves[pawn].Value))
                {SelectedMoves.Remove(pawn);RetreatJobs.Remove(pawn);}
            foreach(var pair in Plans.ToList())
            {
                var plan=pair.Value;Pawn pawn=plan.Pawn;
                if(!Valid(plan)){Plans.Remove(pair.Key);RetreatJobs.Remove(pawn);SelectedMoves.Remove(pawn);continue;}
                if(plan.ProgressCell!=pawn.Position){plan.ProgressCell=pawn.Position;plan.ProgressTick=Find.TickManager.TicksGame;}
                // A new external job cancels ownership. Native queued shots and
                // the engine's idle post-job transition remain part of the plan.
                bool queuedShot=pawn.CurJob==plan.QueuedShot
                    || pawn.CurJobDef==JobDefOf.AttackStatic && pawn.CurJob?.targetA.Thing==plan.Target;
                bool pendingMove=pawn.jobs.jobQueue.Any(q=>q.job==plan.OwnedJob);
                bool idle=pawn.CurJobDef==JobDefOf.Wait_Combat || pawn.CurJobDef==JobDefOf.Wait_MaintainPosture;
                if(pawn.CurJob!=plan.OwnedJob && !queuedShot && !idle && !pendingMove){Plans.Remove(pair.Key);
#if LAYA_COMBAT_LAB
                    Cancelled++;
#endif
                    continue;}
                if(pendingMove)continue;
                var threats=pawn.Map.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
                if(!threats.Any())continue;
                if(plan.Mode=="retreat" && pawn.CurJob==plan.OwnedJob && pawn.pather.Moving && !StuckAtContact(plan))continue;
                if(TryBreakRangedContact(plan,threats))continue;
                var melee=threats.Where(t=>MeleeThreat(t) && (CombatInterceptHelper.Pursuing(t,pawn) || pawn.Position.DistanceTo(t.Position)<3f))
                    .OrderBy(t=>pawn.Position.DistanceToSquared(t.Position)).FirstOrDefault();
                var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
                float warmup=(pawn.stances.curStance as Stance_Warmup)?.ticksLeft
                    ?? (verb?.verbProps.warmupTime ?? 0)*60f*pawn.GetStatValue(StatDefOf.AimingDelayFactor);
                float contact=melee==null?9999f:CombatInterceptHelper.ContactTicks(melee,pawn);
                float headstart=6f/Math.Max(.1f,Speed(pawn))*60f;
                float cooldown=pawn.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f;
                float burst=Math.Max(0,(verb?.verbProps.burstShotCount ?? 1)-1)*(verb?.verbProps.ticksBetweenBurstShots ?? 0);
                float locked=(pawn.stances.curStance as Stance_Busy)?.ticksLeft ?? 0;
                bool supported=melee!=null && CombatInterceptHelper.CanShootNow(pawn,melee)
                    && CombatInterceptHelper.ReadyCover(pawn,melee).Any() && contact>warmup+burst+30f;
                // Stationary fire preserves a shot, not an obligation to wait
                // for melee contact in open ground. Only a verified defended
                // approach can extend that commitment beyond the escape margin.
                bool holdLine=melee!=null && new[]{"stationary_fire","focus_fire","hold_cover","firing_line","fallback_line"}.Contains(plan.Tactic)
                    && pawn.health.hediffSet.BleedRateTotal==0f && pawn.health.summaryHealth.SummaryHealthPercent>=.85f
                    && pawn.health.capacities.GetLevel(PawnCapacityDefOf.Moving)>=.85f
                    && CombatInterceptHelper.DefendedApproach(pawn,melee) && CombatInterceptHelper.ReadyCover(pawn,melee).Any();
                if(melee!=null && !supported && !holdLine && contact<CombatInterceptMath.ShotCommitment(warmup,burst,cooldown,headstart+30f,locked))
                {
                    // Keep an owned safe retreat waypoint instead of replacing
                    // it every quarter second and never reaching the shot.
                    if(plan.Mode=="retreat" && pawn.CurJob==plan.OwnedJob && pawn.CurJobDef==JobDefOf.Goto
                        && pawn.pather.Moving && !StuckAtContact(plan))continue;
                    if(TryRangedRetreat(pawn,melee,plan.Anchor,out var retreat))
                    {plan.OwnedJob=retreat;plan.QueuedShot=SelectedMoves[pawn].Value;plan.Target=melee;plan.Mode="retreat";plan.LastMoveTick=Find.TickManager.TicksGame;continue;}
                    if(CombatInterceptMath.ContactDefence(true,pawn.Position.DistanceTo(melee.Position)))
                    {
                        if(pawn.CurJobDef!=JobDefOf.AttackMelee || pawn.CurJob.targetA.Thing!=melee)
                        {
                            var defend=JobMaker.MakeJob(JobDefOf.AttackMelee,melee);defend.playerForced=true;
                            defend.expiryInterval=120;defend.checkOverrideOnExpire=true;
                            if(MentalSafetyHelper.TakeDefenceOrder(pawn,defend))
                            {plan.OwnedJob=defend;plan.QueuedShot=null;plan.Target=melee;plan.Mode="contact";}
                        }
                        continue;
                    }
                }
                if(plan.Mode=="contact" && pawn.CurJob==plan.OwnedJob && pawn.CurJobDef==JobDefOf.AttackMelee
                    && (plan.Target==null || !Threat(plan.Target) || pawn.Position.DistanceTo(plan.Target.Position)>1.5f))
                {pawn.jobs.EndCurrentJob(JobCondition.InterruptForced,false);plan.OwnedJob=pawn.CurJob;plan.Mode="shoot";}
                // Finish the selected firing approach. A newly visible target
                // must not discard a valid waypoint every quarter second.
                if(pawn.CurJob==plan.OwnedJob && pawn.CurJobDef==JobDefOf.Goto && pawn.pather.Moving)continue;
                // Aim is preserved until a real urgent contact requires escape.
                if((pawn.stances.curStance is Stance_Warmup || verb?.state==VerbState.Bursting)
                    && (pawn.CurJobDef==JobDefOf.AttackStatic || pawn.CurJobDef==JobDefOf.Wait_Combat))
                {
                    if(AimTarget(pawn) is Pawn aimed && Threat(aimed) && CombatInterceptHelper.CanShootNow(pawn,aimed))continue;
                    if(verb?.state==VerbState.Bursting)continue; // Already committed projectiles keep their native burst.
                    pawn.stances.CancelBusyStanceSoft();pawn.jobs.EndCurrentJob(JobCondition.InterruptForced,false);plan.OwnedJob=pawn.CurJob;
                }
                Pawn target=GroupTarget(pawn,threats);
                if(target==null){TryCoverObservedBreach(plan,threats);continue;}
                if(new[]{"hold_cover","firing_line","focus_fire","fallback_line","spread_out","stationary_fire"}.Contains(plan.Tactic)
                    && TryCoveredShot(pawn,target,out var covered))
                {
                    var move=JobMaker.MakeJob(JobDefOf.Goto,covered);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                    if(MentalSafetyHelper.TakeDefenceOrder(pawn,move))
                    {
                        var shot=JobMaker.MakeJob(JobDefOf.AttackStatic,target);shot.playerForced=true;
                        pawn.jobs.jobQueue.EnqueueLast(shot);RememberMove(pawn,move,shot);
                        plan.OwnedJob=move;plan.QueuedShot=shot;plan.Target=target;plan.Mode="position";continue;
                    }
                }
                if(pawn.CurJobDef==JobDefOf.AttackStatic && pawn.CurJob?.targetA.Thing==target)continue;
                var attack=JobMaker.MakeJob(JobDefOf.AttackStatic,target);attack.playerForced=true;
                if(MentalSafetyHelper.TakeDefenceOrder(pawn,attack))
                {plan.OwnedJob=attack;plan.Target=target;plan.Mode="shoot";}
            }
        }
    }
    public class CombatControlComponent : GameComponent
    {
        public CombatControlComponent(Game game){}
        public override void GameComponentTick(){CombatControlHelper.Tick();}
    }
}

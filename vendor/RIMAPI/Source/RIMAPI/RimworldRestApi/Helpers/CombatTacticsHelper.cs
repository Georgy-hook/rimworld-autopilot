using System;
using System.Collections.Generic;
using System.Linq;
using RIMAPI.Core;
using RIMAPI.Models;
using RimWorld;
using Verse;
using Verse.AI;
using Verse.AI.Group;

namespace RIMAPI.Helpers
{
    public static class CombatTacticsHelper
    {
        private static readonly HashSet<string> PositioningTactics = new HashSet<string>
        {
            "hold_cover", "focus_fire", "firing_line", "spread_out", "kite", "backstep_fire", "advance_to_range",
            "withdraw_and_regroup", "staggered_retreat",
            "melee_block", "door_defense", "killbox_hold", "fallback_line", "wide_flank",
            "pincer", "counter_snipe", "smoke_advance", "siege_harass", "drop_pod_encircle",
            "infestation_choke", "cluster_poke", "intercept_kidnapper", "covered_rescue",
            "fire_retreat", "civilian_retreat"
        };

        // The engine executes this request on its main thread. Capture job
        // identities once; deferred cleanup reads them without paths, geometry,
        // native job creation, or a second budget checkpoint.
        private sealed class ApplyObservation
        {
            public Map Map;
            public List<Pawn> Pawns;
            public List<int> Requested,Preserved=new List<int>();
            public List<int> Refreshed=new List<int>();
            public Dictionary<int,Tuple<Job,int?,bool,int[]>> Before;
            public CombatTacticResponseDto Result;
            public string Phase;
        }
#if LAYA_COMBAT_LAB
        public static string TestDeferredApplyPhase;
        [ThreadStatic] public static bool TestInsideApply;
        public static void TestApplyBoundary(string phase)
        {
            if(!TestInsideApply || TestDeferredApplyPhase!=phase)return;
            TestDeferredApplyPhase=null;
            throw new CombatReviewDeferredException("BudgetDeferred:declared_http_contract_"+phase);
        }
#endif
        private static void ApplyBoundary(ApplyObservation observation,string phase)
        {
            observation.Phase=phase;
#if LAYA_COMBAT_LAB
            TestApplyBoundary(phase);
#endif
            CombatPathBudgetHelper.Checkpoint(phase);
        }
        public static ApiResult<CombatTacticResponseDto> Apply(CombatTacticRequestDto request)
        {
            if(request==null)return ApiResult<CombatTacticResponseDto>.Fail("A tactical request is required.");
            using(CombatPathBudgetHelper.Begin("Apply",64))
            {
                var map=MapHelper.GetMapByID(request.MapId);
                var pawns=map?.mapPawns.FreeColonistsSpawned.ToList() ?? new List<Pawn>();
                var originalIds=request.FighterIds;
                var observation=new ApplyObservation{Map=map,Pawns=pawns,Requested=originalIds?.ToList() ?? new List<int>(),
                    Before=pawns.ToDictionary(p=>p.thingIDNumber,p=>Tuple.Create(p.CurJob,p.CurJob?.loadID,p.Drafted,p.jobs.jobQueue.Select(q=>q.job.loadID).ToArray())),
                    Result=new CombatTacticResponseDto{Tactic=request.Tactic,TargetPawnId=request.TargetPawnId}};
#if LAYA_COMBAT_LAB
                TestInsideApply=true;
#endif
                try
                {
                    if(request.Tactic=="refresh_control" && map!=null)
                    {
                        observation.Result=CombatControlHelper.Refresh(map,request.FighterIds);
                        observation.Refreshed=observation.Result.RefreshedControlPawnIds.ToList();
                        ReadBackAcceptedJobs(observation);
                        return ApiResult<CombatTacticResponseDto>.Ok(observation.Result);
                    }
                    observation.Refreshed=CombatControlHelper.RetainControlLeases(map,observation.Requested,request);
                    ApplyBoundary(observation,"prefilter");
                    foreach(var pawn in pawns.Where(p=>observation.Requested.Contains(p.thingIDNumber)))
                    {
                        CombatPathBudgetHelper.Checkpoint("prefilter");
                        if(CombatControlHelper.PreserveEscape(pawn,request.Tactic)
                            || CombatControlHelper.PreserveShot(pawn,request.Tactic)
                            || CombatControlHelper.PreserveContact(pawn,request.Tactic)
                            || CombatControlHelper.PreserveTeamTactic(pawn,request))
                            observation.Preserved.Add(pawn.thingIDNumber);
                    }
                    request.FighterIds=observation.Requested.Except(observation.Preserved).ToList();
                    ApplyBoundary(observation,"core");
                    var response=request.FighterIds.Any() || !observation.Preserved.Any()
                        ? ApplyCore(request,observation)
                        : ApiResult<CombatTacticResponseDto>.Ok(observation.Result);
                    if(!response.Success || response.Data==null)return response;
                    observation.Result=response.Data;
                    request.FighterIds=originalIds;
                    ApplyBoundary(observation,"readback");
                    ReadBackAcceptedJobs(observation);
                    ApplyBoundary(observation,"remember");
                    CombatControlHelper.Remember(request,observation.Result,map,observedOnly:true);
                    return response;
                }
                catch(CombatReviewDeferredException ex)
                {
                    request.FighterIds=originalIds;
                    var result=observation.Result;
                    result.Deferred=true;result.ReviewComplete=false;
                    result.DeferredReason=ex.Message;result.DeferredPhase=observation.Phase;
                    result.DeferredPawnIds=observation.Requested.Distinct().ToList();
                    result.Notes.Add(ex.Message+"; incomplete review, not an unsafe route. Existing native jobs and accepted partial actions are read back, not replayed or claimed completed.");
                    // Deliberately no Checkpoint or tactical selection in this
                    // cleanup. It may not rethrow the same exhausted budget.
                    ReadBackAcceptedJobs(observation);
                    if(map!=null)CombatControlHelper.Remember(request,result,map,observedOnly:true);
                    return ApiResult<CombatTacticResponseDto>.Ok(result);
                }
                finally
                {
                    request.FighterIds=originalIds;
#if LAYA_COMBAT_LAB
                    TestInsideApply=false;
#endif
                }
            }
        }
        private static void ReadBackAcceptedJobs(ApplyObservation observation)
        {
            var result=observation.Result;
            result.RefreshedControlPawnIds=observation.Refreshed.ToList();
            result.CurrentJobs.Clear();result.ChangedPawnIds.Clear();
            result.Applied=result.PsycastQueued;
            foreach(var pawn in observation.Pawns)
            {
                var prior=observation.Before[pawn.thingIDNumber];
                var queue=pawn.jobs.jobQueue.Select(q=>q.job).ToArray();
                bool changed=!ReferenceEquals(prior.Item1,pawn.CurJob) || prior.Item2!=pawn.CurJob?.loadID
                    || prior.Item3!=pawn.Drafted || !prior.Item4.SequenceEqual(queue.Select(j=>j.loadID));
                result.Applied|=changed;
                if(changed)result.ChangedPawnIds.Add(pawn.thingIDNumber);
                if(!observation.Requested.Contains(pawn.thingIDNumber) && !changed)continue;
                var jobs=queue.Concat(pawn.CurJob==null?Array.Empty<Job>():new[]{pawn.CurJob}).ToArray();
                bool moving=jobs.Any(j=>j.def==JobDefOf.Goto && CombatOrderHelper.Owned(pawn,j));
                bool attacking=jobs.Any(j=>(j.def==JobDefOf.AttackStatic || j.def==JobDefOf.AttackMelee)
                    && CombatOrderHelper.Owned(pawn,j));
                if(moving)result.PositionedPawnIds.Add(pawn.thingIDNumber);
                if(attacking)result.AttackingPawnIds.Add(pawn.thingIDNumber);
                if(pawn.Drafted && changed)result.DraftedPawnIds.Add(pawn.thingIDNumber);
                if(!changed && (moving || attacking || observation.Preserved.Contains(pawn.thingIDNumber)))
                    result.PreservedPawnIds.Add(pawn.thingIDNumber);
                result.CurrentJobs.Add(new CombatOrderReadbackDto{PawnId=pawn.thingIDNumber,
                    JobId=pawn.CurJob?.loadID,Owned=CombatOrderHelper.Owned(pawn,pawn.CurJob),
                    JobDefName=pawn.CurJobDef?.defName,TargetThingId=pawn.CurJob?.targetA.Thing?.thingIDNumber,
                    Drafted=pawn.Drafted,QueuedJobIds=queue.Select(j=>j.loadID).ToList(),
                    QueuedJobDefs=queue.Select(j=>j.def.defName).ToList()});
            }
            result.PositionedPawnIds=result.PositionedPawnIds.Distinct().ToList();
            result.AttackingPawnIds=result.AttackingPawnIds.Distinct().ToList();
            result.DraftedPawnIds=result.DraftedPawnIds.Distinct().ToList();
            result.PreservedPawnIds=result.PreservedPawnIds.Except(result.ChangedPawnIds).Distinct().ToList();
            result.PartialApplied=result.Deferred && result.Applied;
        }

        private static ApiResult<CombatTacticResponseDto> ApplyCore(CombatTacticRequestDto request,ApplyObservation observation)
        {
            try
            {
                Map map = MapHelper.GetMapByID(request.MapId);
                if (map == null)
                    return ApiResult<CombatTacticResponseDto>.Fail($"Map {request.MapId} not found.");
                string tactic = (request.Tactic ?? "").Trim().ToLowerInvariant();
                if (tactic == "caregiver_retreat") return ApplyCareRetreat(map, request);
                if(new[]{"emp_control","smoke_advance","mortar_counterbattery","mortar_reload","attack_structure"}.Contains(tactic))return ApiResult<CombatTacticResponseDto>.Ok(CombatNativeHelper.Apply(map,request));
                if (tactic == "stand_down")
                {
                    var colonists = map.mapPawns.FreeColonistsSpawned.ToList();
                    if (map.mapPawns.AllPawnsSpawned.ToArray().Any(p => !p.Downed
                            && CombatNativeHelper.ActionableHostile(p, colonists, map))
                        || map.listerBuildings.allBuildingsNonColonist.Any(b => !b.Position.Fogged(map)
                            && CombatNativeHelper.ActiveStructure(b)))
                        // Hostiles remain: this changed precondition must not
                        // become a server error or an accepted stand-down.
                        return ApiResult<CombatTacticResponseDto>.Ok(
                            CombatTacticReadinessHelper.StandDownBlocked(tactic,request.TargetPawnId));
                    foreach (Pawn pawn in map.mapPawns.FreeColonistsSpawned.Where(p => request.FighterIds.Contains(p.thingIDNumber)
                        && p.drafter?.Drafted == true && !CombatNativeHelper.HasClinicalCareJob(p)
                        && !CombatNativeHelper.HasCareRetreat(p) && !CareTriageHelper.QueuedCare(p)
                        && !(p.carryTracker?.CarriedThing is Pawn)
                        && !(p.CurJobDef==JobDefOf.AttackMelee && p.CurJob.killIncappedTarget
                             && p.CurJob.targetA.Thing is Pawn victim && !victim.Dead && victim.Downed)
                        && !p.jobs.jobQueue.Any(q=>q.job.def==JobDefOf.AttackMelee && q.job.killIncappedTarget
                             && q.job.targetA.Thing is Pawn queuedVictim && !queuedVictim.Dead && queuedVictim.Downed)).ToList())
                        pawn.drafter.Drafted = false;
                    return ApiResult<CombatTacticResponseDto>.Ok(new CombatTacticResponseDto { Tactic = tactic });
                }

                if (!PositioningTactics.Contains(tactic) && !new[] { "melee_assault", "rush_ranged", "melee_hold_line", "lure_enemy",
                    "preemptive_strike", "stationary_fire", "screen_melee", "guard_shooters", "psycast_control", "psycast_support", "contact_melee" }.Contains(tactic))
                    return ApiResult<CombatTacticResponseDto>.Fail("Unknown combat tactic; no fighters drafted.");
                List<Pawn> fighters = map.mapPawns.FreeColonistsSpawned
                    .Where(p => request.FighterIds.Contains(p.thingIDNumber) && !p.Dead && !p.Downed
                        && !p.InMentalState && !CombatNativeHelper.Protected(p) && !CareTriageHelper.QueuedCare(p))
                    .ToList();
                if (fighters.Count == 0)
                {
                    observation.Result=CombatTacticReadinessHelper.NoSelectedFighters(tactic,request.TargetPawnId);
                    return ApiResult<CombatTacticResponseDto>.Ok(observation.Result);
                }
                if (!new[] {"civilian_retreat","withdraw_and_regroup","lure_enemy","psycast_support","psycast_control"}.Contains(tactic))
                    fighters.RemoveAll(p => p.WorkTagIsDisabled(WorkTags.Violent));
                if (fighters.Count == 0)
                    return ApiResult<CombatTacticResponseDto>.Fail("Selected pawns cannot perform violent work; choose protected movement or care.");
                Pawn target = request.TargetPawnId.HasValue
                    ? map.mapPawns.AllPawnsSpawned.FirstOrDefault(p => p.thingIDNumber == request.TargetPawnId.Value && !p.Dead && !p.Downed && CombatNativeHelper.IsPlayerThreat(p))
                    : map.mapPawns.AllPawnsSpawned
                        .Where(p => !p.Dead && !p.Downed && CombatNativeHelper.IsPlayerThreat(p))
                        .OrderBy(p => fighters.Min(f => f.Position.DistanceToSquared(p.Position)))
                        .FirstOrDefault();
                if (target != null && MentalSafetyHelper.Allied(target) && !MentalSafetyHelper.ActiveAlliedAggressor(target))
                    return ApiResult<CombatTacticResponseDto>.Fail("Allied target is no longer an active mental threat; no fighters drafted.");
                if (target == null && tactic != "psycast_support" && tactic != "psycast_control")
                {
                    observation.Result=CombatTacticReadinessHelper.NoActiveTarget(tactic,request.TargetPawnId);
                    return ApiResult<CombatTacticResponseDto>.Ok(observation.Result);
                }
                int retreatPathAttempts = 0; // Shared by every selected fighter in this order.
                var result = observation.Result = new CombatTacticResponseDto
                {
                    Tactic = tactic,
                    TargetPawnId = target?.thingIDNumber,
                };

                // A selected defense must reach the native controller before
                // optional formation geometry can exhaust its review budget.
                if(CombatSelectedGuardHelper.TryAdmit(tactic,fighters,target,result))
                    return ApiResult<CombatTacticResponseDto>.Ok(result);

                if (tactic == "intercept_kidnapper" && !CombatNativeHelper.AbductionThreat(target)) {
                    result.Notes.Add("No observed pickup attempt on our downed pawn or actual carrier remains; no fighters drafted.");
                    return ApiResult<CombatTacticResponseDto>.Ok(result);
                }

                if (tactic == "lure_enemy" && fighters.Any(p => !CombatInterceptHelper.Pursuing(target,p)
                    || CombatInterceptHelper.ReadyCover(p,target).Count == 0))
                {
                    result.Notes.Add("Lure is not followed by the selected threat with ready guns firing at that same threat; no pawn drafted.");
                    return ApiResult<CombatTacticResponseDto>.Ok(result);
                }
                if(tactic=="contact_melee" && fighters.Any(p=>target==null
                    || !CombatInterceptMath.ContactDefence(!p.WorkTagIsDisabled(WorkTags.Violent),p.Position.DistanceTo(target.Position))
                    || p.meleeVerbs.TryGetMeleeVerb(target)==null))
                {result.Notes.Add("Exact melee contact changed; no defender drafted and no distant charge ordered.");return ApiResult<CombatTacticResponseDto>.Ok(result);}

                foreach (Pawn pawn in fighters)
                {
                CombatPathBudgetHelper.Checkpoint();
                    if (pawn.drafter != null)
                    {
                        pawn.drafter.Drafted = true;
                        result.DraftedPawnIds.Add(pawn.thingIDNumber);
                    }
                }

                if (!string.IsNullOrEmpty(request.AbilityDefName) && request.PsycasterPawnId.HasValue)
                {
                    Pawn caster = fighters.FirstOrDefault(p => p.thingIDNumber == request.PsycasterPawnId.Value);
                    Pawn abilityTarget = request.AbilityTargetPawnId.HasValue
                        ? map.mapPawns.AllPawnsSpawned.FirstOrDefault(p => p.thingIDNumber == request.AbilityTargetPawnId.Value)
                        : target;
                    IntVec3? targetCell = request.AbilityTargetPosition == null
                        ? (IntVec3?)null
                        : new IntVec3(request.AbilityTargetPosition.X, 0, request.AbilityTargetPosition.Z);
                    ApiResult<bool> cast = PsychicAutomationHelper.QueuePsycast(caster, request.AbilityDefName, abilityTarget, targetCell);
                    result.PsycastQueued = cast.Success;
                    result.Psycast = request.AbilityDefName;
                    if (!cast.Success)
                        result.Notes.AddRange(cast.Errors);
                }

                // A support/control cast is the complete order for this cycle.  The
                // caster must not immediately discard it for an AttackMelee job.
                if (tactic == "psycast_control" || tactic == "psycast_support")
                    return ApiResult<CombatTacticResponseDto>.Ok(result);

                if (!new[] {"civilian_retreat","withdraw_and_regroup","staggered_retreat","fire_retreat","lure_enemy","kite","backstep_fire"}.Contains(tactic))
                {
                    foreach (var pawn in fighters.ToArray())
                    {
                CombatPathBudgetHelper.Checkpoint();
                        var contact = tactic=="contact_melee" ? target : map.mapPawns.AllPawnsSpawned.Where(p => !p.Dead && !p.Downed && CombatNativeHelper.IsPlayerThreat(p)
                            && CombatInterceptMath.ContactDefence(!pawn.WorkTagIsDisabled(WorkTags.Violent),pawn.Position.DistanceTo(p.Position)))
                            .OrderBy(p => pawn.Position.DistanceToSquared(p.Position)).FirstOrDefault();
                        if (contact == null || pawn.meleeVerbs.TryGetMeleeVerb(contact) == null) continue;
                        if (IsRanged(pawn) && CombatControlHelper.TryRangedRetreat(pawn,contact,pawn.Position,out var escape))
                        {
                            result.PositionedPawnIds.Add(pawn.thingIDNumber);
                            result.Notes.Add($"{pawn.LabelShort}: short checked retreat and queued shot; gun melee only if no escape is feasible.");
                            fighters.Remove(pawn);continue;
                        }
                        if (pawn.CurJobDef == JobDefOf.AttackMelee && pawn.CurJob.targetA.Thing == contact)
                        {
                            CombatContactHelper.Remember(pawn,pawn.CurJob);
                            result.AttackingPawnIds.Add(pawn.thingIDNumber);
                        }
                        else
                        {
                            var defend = JobMaker.MakeJob(JobDefOf.AttackMelee,contact);
                            defend.playerForced = true; defend.expiryInterval = 120; defend.checkOverrideOnExpire = true;
                            if (CombatOrderHelper.Take(pawn,ref defend))
                            {CombatContactHelper.Remember(pawn,defend);result.AttackingPawnIds.Add(pawn.thingIDNumber);}
                        }
                        result.Notes.Add($"{pawn.LabelShort}: contact self-defence against {contact.thingIDNumber}; short melee job, not a distant charge or completed fight.");
                        fighters.Remove(pawn);
                    }
                    if (fighters.Count == 0) return ApiResult<CombatTacticResponseDto>.Ok(result);
                }

                if (target == null)
                {
                    result.Notes.Add("No living hostile target remains; fighters were drafted but no attack was issued.");
                    return ApiResult<CombatTacticResponseDto>.Ok(result);
                }

                if (tactic == "melee_hold_line")
                {
                    Pawn closeThreat = map.mapPawns.AllPawnsSpawned
                        .Where(p => !p.Dead && !p.Downed && CombatNativeHelper.IsPlayerThreat(p))
                        .OrderBy(p => fighters.Min(f => f.Position.DistanceToSquared(p.Position)))
                        .FirstOrDefault();
                    bool threatened = closeThreat != null
                        && fighters.Min(f => f.Position.DistanceTo(closeThreat.Position)) <= 7f;
                    Pawn anchor = fighters.OrderBy(p => p.Position.DistanceToSquared(target.Position)).First();
                    foreach (Pawn pawn in fighters)
                    {
                CombatPathBudgetHelper.Checkpoint();
                        if (threatened)
                        {
                            if (pawn.CurJob?.def == JobDefOf.AttackMelee && pawn.CurJob.targetA.Thing == closeThreat)
                            {
                                result.AttackingPawnIds.Add(pawn.thingIDNumber);
                                continue;
                            }
                            Job attack = JobMaker.MakeJob(JobDefOf.AttackMelee, closeThreat);
                            attack.playerForced = true;
                            if (CombatOrderHelper.Take(pawn,ref attack))
                                result.AttackingPawnIds.Add(pawn.thingIDNumber);
                            continue;
                        }
                        if (pawn.Position.DistanceToSquared(anchor.Position) <= 9)
                        {
                            pawn.jobs.StopAll();
                            result.Notes.Add($"{pawn.LabelShortCap} is holding with the melee group.");
                            continue;
                        }
                        IntVec3 safe;
                        if (TryFindTrapFreeCell(pawn, anchor.Position, target.Position, tactic, out safe, 0f))
                        {
                            Job move = JobMaker.MakeJob(JobDefOf.Goto, safe);
                            move.playerForced = true;
                            if (CombatOrderHelper.Take(pawn,ref move))
                                result.PositionedPawnIds.Add(pawn.thingIDNumber);
                        }
                        else
                            result.Notes.Add($"No trap-free route to the melee group for {pawn.LabelShortCap}.");
                    }
                    return ApiResult<CombatTacticResponseDto>.Ok(result);
                }

                if (tactic == "lure_enemy")
                {
                    foreach (Pawn pawn in fighters)
                    {
                CombatPathBudgetHelper.Checkpoint();
                        var guns = CombatInterceptHelper.ReadyCover(pawn,target);
                        float dx=pawn.Position.x-target.Position.x,dz=pawn.Position.z-target.Position.z;
                        float distance=(float)Math.Sqrt(dx*dx+dz*dz);
                        var desired=pawn.Position+new IntVec3((int)Math.Round(dx*6/Math.Max(1,distance)),0,(int)Math.Round(dz*6/Math.Max(1,distance)));
                        IntVec3 safe=IntVec3.Invalid;
                        foreach (var cell in GenRadial.RadialCellsAround(desired,7f,true).OrderBy(c=>c.DistanceToSquared(desired)))
                        {
                CombatPathBudgetHelper.Checkpoint();
                            if (!cell.InBounds(map) || !cell.Standable(map) || cell.Fogged(map) || !pawn.CanReserve(cell)
                                || cell.DistanceTo(target.Position)<8f || cell.DistanceTo(target.Position)>20f
                                || !guns.Any(g=>g.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb.CanHitTargetFrom(g.Position,new LocalTargetInfo(cell)))) continue;
                            using(var path=CombatPathBudgetHelper.Query(pawn,pawn.Position,cell,PathEndMode.OnCell))
                                if(RetreatRouteSafe(pawn,path) && CombatInterceptHelper.MovementSafe(pawn,path)
                                    && path.NodesReversed.All(c=>guns.Any(g=>g.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb.CanHitTargetFrom(g.Position,new LocalTargetInfo(c)))))
                                {safe=cell;break;}
                        }
                        if(!CombatInterceptMath.SupportedLure(CombatInterceptHelper.Pursuing(target,pawn),guns.Count,safe.IsValid))
                        {result.Notes.Add($"{pawn.LabelShort}: no followed, covered escape; lure was not executed.");continue;}
                        if(pawn.CurJobDef==JobDefOf.Goto && pawn.CurJob.targetA.Cell==safe)
                        {result.PositionedPawnIds.Add(pawn.thingIDNumber);continue;}
                        var move=JobMaker.MakeJob(JobDefOf.Goto,safe);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                        if(CombatOrderHelper.Take(pawn,ref move))result.PositionedPawnIds.Add(pawn.thingIDNumber);
                        result.Notes.Add($"{pawn.LabelShort}: observed pursuer {target.thingIDNumber}; {guns.Count} guns already firing at this same enemy. Arrival/pursuit/hits unverified.");
                    }
                    return ApiResult<CombatTacticResponseDto>.Ok(result);
                }

                if (tactic == "stationary_fire")
                {
                    var sharedTarget=target;
                    foreach (Pawn pawn in fighters)
                    {
                CombatPathBudgetHelper.Checkpoint();
                        target=CombatControlHelper.AvailableFiringTarget(pawn,sharedTarget);
                        Verb verb = pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
                        if (!IsRanged(pawn) || pawn.WorkTagIsDisabled(WorkTags.Violent)
                            || verb == null || !verb.Available() || !CanShootTarget(pawn, pawn.Position, target))
                        {
                            result.Notes.Add($"No current-position shot is available for {pawn.LabelShortCap}; no movement ordered.");
                            continue;
                        }
                        // Repeated accepted defense must preserve an in-progress warmup.
                        if (pawn.CurJob?.def == JobDefOf.AttackStatic && pawn.CurJob.targetA.Thing == target)
                        {
                            result.AttackingPawnIds.Add(pawn.thingIDNumber);
                            continue;
                        }
                        Job shot = JobMaker.MakeJob(JobDefOf.AttackStatic, target);
                        shot.playerForced = true;
                        if (CombatOrderHelper.Take(pawn,ref shot)) result.AttackingPawnIds.Add(pawn.thingIDNumber);
                    }
                    return ApiResult<CombatTacticResponseDto>.Ok(result);
                }
                if (tactic == "preemptive_strike")
                {
                    foreach (Pawn pawn in fighters)
                    {
                CombatPathBudgetHelper.Checkpoint();
                        float range = pawn.equipment?.Primary?.def?.Verbs?.FirstOrDefault()?.range ?? 0f;
                        if (!IsRanged(pawn) || range < 25f)
                        {
                            result.Notes.Add($"{pawn.LabelShortCap} has no suitable long-range weapon.");
                            pawn.drafter.Drafted = false;
                            result.DraftedPawnIds.Remove(pawn.thingIDNumber);
                            continue;
                        }
                        float dx = pawn.Position.x - target.Position.x;
                        float dz = pawn.Position.z - target.Position.z;
                        float distance = (float)Math.Sqrt(dx * dx + dz * dz);
                        if (distance <= range - 2f)
                        {
                            Job attack = JobMaker.MakeJob(JobDefOf.AttackStatic, target);
                            attack.playerForced = true;
                            if (CombatOrderHelper.Take(pawn,ref attack))
                                result.AttackingPawnIds.Add(pawn.thingIDNumber);
                            else
                            {
                                result.Notes.Add($"Could not queue a shot for {pawn.LabelShortCap}; undrafted.");
                                pawn.drafter.Drafted = false;
                                result.DraftedPawnIds.Remove(pawn.thingIDNumber);
                            }
                            continue;
                        }
                        string targetJob = target.CurJobDef?.defName ?? "";
                        string targetLordToil = target.GetLord()?.CurLordToil?.GetType().Name ?? "";
                        bool preparing = targetJob.IndexOf("wait", StringComparison.OrdinalIgnoreCase) >= 0
                            || targetJob.IndexOf("wander", StringComparison.OrdinalIgnoreCase) >= 0
                            || targetLordToil.IndexOf("stage", StringComparison.OrdinalIgnoreCase) >= 0
                            || targetLordToil.IndexOf("siege", StringComparison.OrdinalIgnoreCase) >= 0;
                        if (targetJob.Equals("Goto", StringComparison.OrdinalIgnoreCase)
                            || targetJob.IndexOf("attack", StringComparison.OrdinalIgnoreCase) >= 0
                            || targetJob.IndexOf("breach", StringComparison.OrdinalIgnoreCase) >= 0
                            || targetJob.IndexOf("kidnap", StringComparison.OrdinalIgnoreCase) >= 0)
                            preparing = false;
                        if (!preparing)
                        {
                            pawn.jobs.StopAll();
                            result.Notes.Add($"{target.LabelShortCap} is advancing; {pawn.LabelShortCap} holds position instead of chasing.");
                            continue;
                        }
                        // A short waypoint is intentionally re-evaluated against live
                        // enemy movement; a full-map Goto can run into a new assault.
                        float step = Math.Min(8f, Math.Max(0f, distance - (range - 4f)));
                        float scale = step / Math.Max(distance, 1f);
                        IntVec3 desired = new IntVec3(
                            pawn.Position.x - (int)Math.Round(dx * scale), 0,
                            pawn.Position.z - (int)Math.Round(dz * scale));
                        IntVec3 safe;
                        if (TryFindTrapFreeCell(pawn, desired, target.Position, tactic, out safe, Math.Max(15f, range - 7f)))
                        {
                            Job move = JobMaker.MakeJob(JobDefOf.Goto, safe);
                            move.playerForced = true;
                            if (CombatOrderHelper.Take(pawn,ref move))
                                result.PositionedPawnIds.Add(pawn.thingIDNumber);
                            else
                            {
                                result.Notes.Add($"Could not queue advance for {pawn.LabelShortCap}; undrafted.");
                                pawn.drafter.Drafted = false;
                                result.DraftedPawnIds.Remove(pawn.thingIDNumber);
                            }
                        }
                        else
                        {
                            result.Notes.Add($"No trap-free route to firing range for {pawn.LabelShortCap}; undrafted.");
                            pawn.drafter.Drafted = false;
                            result.DraftedPawnIds.Remove(pawn.thingIDNumber);
                        }
                    }
                    return ApiResult<CombatTacticResponseDto>.Ok(result);
                }

                if (tactic == "screen_melee" || tactic == "guard_shooters")
                {
                    List<Pawn> shooters = map.mapPawns.FreeColonistsSpawned
                        .Where(p => !p.Dead && !p.Downed && !p.InMentalState
                            && p.drafter?.Drafted == true && IsRanged(p))
                        .ToList();
                    List<Pawn> threats = map.mapPawns.AllPawnsSpawned
                        .Where(p => !p.Dead && !p.Downed && CombatNativeHelper.IsPlayerThreat(p))
                        .ToList();
                    foreach (Pawn pawn in fighters)
                    {
                CombatPathBudgetHelper.Checkpoint();
                        if (IsRanged(pawn))
                        {
                            if (CanShootTarget(pawn, pawn.Position, target))
                            {
                                if (pawn.CurJob?.def == JobDefOf.AttackStatic && pawn.CurJob.targetA.Thing == target)
                                {
                                    result.AttackingPawnIds.Add(pawn.thingIDNumber);
                                    continue;
                                }
                                Job shot = JobMaker.MakeJob(JobDefOf.AttackStatic, target);
                                shot.playerForced = true;
                                if (CombatOrderHelper.Take(pawn,ref shot))
                                    result.AttackingPawnIds.Add(pawn.thingIDNumber);
                                continue;
                            }
                            // A guard order must not strand armed escorts behind a
                            // wall while an unarmed colonist screens the threat.
                            IntVec3 firingCell;
                            if (TryFindFiringCell(pawn, target, out firingCell)
                                || target.pather?.Moving != true && TryFindApproachCell(pawn, target, tactic, out firingCell))
                            {
                                MoveAndAim(pawn,target,firingCell,result);
                            }
                            else
                                result.Notes.Add($"{pawn.LabelShortCap} has no safe firing route around the obstruction.");
                            continue;
                        }

                        Pawn nearestShooter = shooters.OrderBy(p => p.Position.DistanceToSquared(pawn.Position)).FirstOrDefault();
                        bool isolatedUnarmed = nearestShooter != null && pawn.equipment?.Primary == null
                            && pawn.Position.DistanceToSquared(nearestShooter.Position) > 144;
                        if (isolatedUnarmed)
                        {
                            // An isolated civilian must converge with the shooter.
                            // Retreating directly away from the pursuer can instead
                            // drag it out of gun range while the shooter gives chase.
                            Pawn immediateThreat = threats
                                .OrderBy(p => p.Position.DistanceToSquared(pawn.Position))
                                .FirstOrDefault();
                            if (immediateThreat != null
                                && pawn.Position.DistanceToSquared(immediateThreat.Position) <= 100)
                            {
                                IntVec3 regroup;
                                if (TryFindGuardRegroupCell(pawn, nearestShooter, immediateThreat, out regroup))
                                {
                                    Job retreat = JobMaker.MakeJob(JobDefOf.Goto, regroup);
                                    retreat.playerForced = true;
                                    if (CombatOrderHelper.Take(pawn,ref retreat))
                                        result.PositionedPawnIds.Add(pawn.thingIDNumber);
                                }
                                else
                                    result.Notes.Add($"No short trap-free route for isolated {pawn.LabelShortCap} toward the shooter; reassess tactic.");
                                continue;
                            }
                        }
                        float shooterRadius = tactic == "screen_melee" ? 12f : 5f;
                        float fighterRadius = tactic == "screen_melee" ? 9f : 4f;
                        Pawn intercept = threats
                            .Where(p => !isolatedUnarmed && (tactic != "guard_shooters" || pawn.equipment?.Primary != null)
                                && (nearestShooter == null
                                || p.Position.DistanceTo(nearestShooter.Position) <= shooterRadius
                                || p.Position.DistanceTo(pawn.Position) <= fighterRadius))
                            .OrderBy(p => nearestShooter == null
                                ? p.Position.DistanceToSquared(pawn.Position)
                                : p.Position.DistanceToSquared(nearestShooter.Position))
                            .FirstOrDefault();
                        if (intercept != null)
                        {
                            if (pawn.CurJob?.def == JobDefOf.AttackMelee && pawn.CurJob.targetA.Thing == intercept)
                            {
                                result.AttackingPawnIds.Add(pawn.thingIDNumber);
                                continue;
                            }
                            Job attack = JobMaker.MakeJob(JobDefOf.AttackMelee, intercept);
                            attack.playerForced = true;
                            if (CombatOrderHelper.Take(pawn,ref attack))
                                result.AttackingPawnIds.Add(pawn.thingIDNumber);
                            continue;
                        }

                        if (nearestShooter == null)
                        {
                            result.Notes.Add($"No shooter is available for {pawn.LabelShortCap} to guard.");
                            continue;
                        }
                        if (pawn.Position.DistanceToSquared(nearestShooter.Position) <= 9)
                        {
                            pawn.jobs.StopAll();
                            result.Notes.Add($"{pawn.LabelShortCap} guards the firing group until an enemy approaches.");
                            continue;
                        }
                        float dx = target.Position.x - nearestShooter.Position.x;
                        float dz = target.Position.z - nearestShooter.Position.z;
                        float distance = (float)Math.Sqrt(dx * dx + dz * dz);
                        float offset = pawn.equipment?.Primary == null && tactic == "guard_shooters" ? -3f : 2f;
                        IntVec3 desired = new IntVec3(
                            nearestShooter.Position.x + (int)Math.Round(dx * offset / Math.Max(distance, 1f)), 0,
                            nearestShooter.Position.z + (int)Math.Round(dz * offset / Math.Max(distance, 1f)));
                        IntVec3 safe;
                        if (TryFindTrapFreeCell(pawn, desired, target.Position, tactic, out safe, 0f))
                        {
                            Job move = JobMaker.MakeJob(JobDefOf.Goto, safe);
                            move.playerForced = true;
                            if (CombatOrderHelper.Take(pawn,ref move))
                                result.PositionedPawnIds.Add(pawn.thingIDNumber);
                        }
                        else
                            result.Notes.Add($"No trap-free guard position exists for {pawn.LabelShortCap}.");
                    }
                    return ApiResult<CombatTacticResponseDto>.Ok(result);
                }

                if(tactic=="withdraw_and_regroup" && fighters.Count>=2)
                {
                    var threats=map.mapPawns.AllPawnsSpawned.Where(p=>!p.Dead && !p.Downed && CombatNativeHelper.IsPlayerThreat(p)).ToArray();
                    var covering=fighters.Where(p=>IsRanged(p) && CanShootTarget(p,p.Position,target)
                            && threats.All(e=>p.Position.DistanceTo(e.Position)>7f))
                        .OrderByDescending(p=>threats.Min(e=>p.Position.DistanceTo(e.Position)))
                        .Take(Math.Max(1,fighters.Count/2)).ToList();
                    foreach(Pawn gun in covering)
                    {
                CombatPathBudgetHelper.Checkpoint();
                        if(gun.CurJobDef==JobDefOf.AttackStatic && CombatControlHelper.PreserveShot(gun,"focus_fire"))
                            result.PreservedPawnIds.Add(gun.thingIDNumber);
                        else
                        {
                            var shot=JobMaker.MakeJob(JobDefOf.AttackStatic,target);shot.playerForced=true;
                            if(!CombatOrderHelper.Take(gun,ref shot))continue;
                        }
                        result.AttackingPawnIds.Add(gun.thingIDNumber);fighters.Remove(gun);
                    }
                    if(result.AttackingPawnIds.Any())result.Notes.Add("Selected covering guns keep firing while other fighters regroup; actual shots and escape remain unverified.");
                }
                Building defense = FindDefense(map, request.DefenseBuildingId, tactic, target.Position, fighters);
                if (tactic == "intercept_kidnapper"
                    || (tactic == "focus_fire" && CombatNativeHelper.AbductionThreat(target)))
                {
                    if (!CombatNativeHelper.AbductionThreat(target))
                    {
                        result.Notes.Add("Observed pickup attempt or carrier changed; reassess the threat.");
                        return ApiResult<CombatTacticResponseDto>.Ok(result);
                    }
                    foreach (Pawn pawn in fighters)
                    {
                CombatPathBudgetHelper.Checkpoint();
                        if (!IsRanged(pawn))
                        {
                            if (pawn.CurJob?.def == JobDefOf.AttackMelee
                                && pawn.CurJob.targetA.Thing == target)
                            {
                                result.AttackingPawnIds.Add(pawn.thingIDNumber);
                                continue;
                            }
                            Job attack = JobMaker.MakeJob(JobDefOf.AttackMelee, target);
                            attack.playerForced = true;
                            if (CombatOrderHelper.Take(pawn,ref attack))
                                result.AttackingPawnIds.Add(pawn.thingIDNumber);
                            continue;
                        }
                        if (CanShootTarget(pawn, pawn.Position, target))
                        {
                            if (pawn.CurJob?.def == JobDefOf.AttackStatic
                                && pawn.CurJob.targetA.Thing == target)
                            {
                                result.AttackingPawnIds.Add(pawn.thingIDNumber);
                                continue;
                            }
                            Job shot = JobMaker.MakeJob(JobDefOf.AttackStatic, target);
                            shot.playerForced = true;
                            if (CombatOrderHelper.Take(pawn,ref shot))
                                result.AttackingPawnIds.Add(pawn.thingIDNumber);
                            continue;
                        }
                        IntVec3 safe;
                        if (!TryFindFiringCell(pawn,target,out safe))
                        {
                            var ownPursuer=CombatPursuitApproachHelper.ObservedOwnPursuer(pawn);
                            if(ownPursuer!=null)
                            {
                                // Rejecting a dangerous forward intercept must
                                // leave this gun under normal defensive review.
                                // It can fire at its pursuer or make a checked
                                // escape while the other interceptors continue.
                                var hold=JobMaker.MakeJob(JobDefOf.Wait_Combat);hold.playerForced=true;
                                if(CombatOrderHelper.Take(pawn,ref hold))
                                {
                                    result.PreservedPawnIds.Add(pawn.thingIDNumber);
                                    result.Notes.Add($"{pawn.LabelShort} retains a controlled defense against an observed own melee pursuer; other interceptors continue.");
                                }
                            }
                            result.Notes.Add($"No timely predictive firing window for {pawn.LabelShort}; no blind pursuit waypoint was issued.");
                            continue;
                        }
                        MoveAndAim(pawn,target,safe,result);
                    }
                    return ApiResult<CombatTacticResponseDto>.Ok(result);
                }
                if (PositioningTactics.Contains(tactic))
                {
                    var sharedTarget=target;
                    List<Pawn> ordered = fighters
                        .OrderByDescending(p => IsRanged(p) ? p.skills?.GetSkill(SkillDefOf.Shooting)?.Level ?? 0 : p.skills?.GetSkill(SkillDefOf.Melee)?.Level ?? 0)
                        .ToList();
                    for (int i = 0; i < ordered.Count; i++)
                    {
                        Pawn pawn = ordered[i];
                        target=new[]{"hold_cover","firing_line","fallback_line","focus_fire","backstep_fire"}.Contains(tactic)
                            ?CombatControlHelper.DefensiveTarget(pawn,sharedTarget):sharedTarget;
                        if(new[]{"hold_cover","firing_line","fallback_line"}.Contains(tactic)
                            && !CombatInterceptHelper.CanShootNow(pawn,target) && CombatAssemblyHelper.TryPosition(pawn,target,out var rallyCell))
                        {
                            if(rallyCell==pawn.Position)
                            {
                                if(pawn.CurJobDef!=JobDefOf.Wait_Combat)
                                {
                                    var hold=JobMaker.MakeJob(JobDefOf.Wait_Combat);hold.playerForced=true;
                                    if(!CombatOrderHelper.Take(pawn,ref hold))continue;
                                }
                                result.PreservedPawnIds.Add(pawn.thingIDNumber);
                            }
                            else MoveAndAim(pawn,target,rallyCell,result);
                            if(rallyCell==pawn.Position || result.PositionedPawnIds.Contains(pawn.thingIDNumber))CombatControlHelper.RememberAssembly(pawn,rallyCell);
                            result.Notes.Add("Assemble at a checked post inside an existing roofed home before the distant assault; the future doorway lane is not an observed shot.");
                            continue;
                        }
                        Pawn nearestThreat = (tactic == "backstep_fire" || tactic == "withdraw_and_regroup")
                            ? map.mapPawns.AllPawnsSpawned
                                .Where(p => !p.Dead && !p.Downed && CombatNativeHelper.IsPlayerThreat(p))
                                .OrderBy(p => pawn.Position.DistanceToSquared(p.Position))
                                .FirstOrDefault() ?? target
                            : target;
                        if(tactic=="backstep_fire" && IsRanged(pawn))
                        {
                            if(CombatControlHelper.TryRangedRetreat(pawn,nearestThreat,CombatControlHelper.DefensiveAnchor(pawn),out var retreat))
                            {result.PositionedPawnIds.Add(pawn.thingIDNumber);continue;}
                            Pawn shotTarget=CombatInterceptHelper.CanShootNow(pawn,nearestThreat)?nearestThreat
                                :CombatInterceptHelper.CanShootNow(pawn,target)?target:null;
                            if(shotTarget!=null)
                            {
                                if(pawn.CurJobDef!=JobDefOf.AttackStatic || pawn.CurJob.targetA.Thing!=shotTarget)
                                {
                                    var shot=JobMaker.MakeJob(JobDefOf.AttackStatic,shotTarget);shot.playerForced=true;
                                    if(!CombatOrderHelper.Take(pawn,ref shot))continue;
                                }
                                result.AttackingPawnIds.Add(pawn.thingIDNumber);
                            }
                            else result.PreservedPawnIds.Add(pawn.thingIDNumber);
                            result.Notes.Add("No checked escape buys another firing window or actual covering fire; retain the defensive gun instead of unsupported repeated movement.");
                            continue;
                        }
                        if (tactic == "advance_to_range" || tactic == "focus_fire")
                        {
                            float range = pawn.equipment?.Primary?.def?.Verbs?.FirstOrDefault()?.range ?? 0f;
                            if (!IsRanged(pawn) || range <= 6f)
                            {
                                result.Notes.Add($"{pawn.LabelShortCap} has no usable ranged weapon for a covered advance.");
                                continue;
                            }
                            if(tactic=="focus_fire" && CombatControlHelper.TryCoveredShot(pawn,target,out var coveredFocus))
                            {MoveAndAim(pawn,target,coveredFocus,result);continue;}
                            if(tactic=="focus_fire" && !IsRanged(target) && CombatInterceptHelper.IncomingToRange(pawn,target,pawn.Position,out var incomingFocus))
                            {
                                if(pawn.CurJobDef==JobDefOf.Goto)pawn.jobs.StopAll();
                                result.PreservedPawnIds.Add(pawn.thingIDNumber);continue;
                            }
                            float dx = target.Position.x - pawn.Position.x;
                            float dz = target.Position.z - pawn.Position.z;
                            float distance = (float)Math.Sqrt(dx * dx + dz * dz);
                            if (distance <= range - 2f && CanShootTarget(pawn, pawn.Position, target))
                            {
                                if (pawn.CurJobDef == JobDefOf.AttackStatic && pawn.CurJob.targetA.Thing == target)
                                { result.AttackingPawnIds.Add(pawn.thingIDNumber); continue; }
                                Job shot = JobMaker.MakeJob(JobDefOf.AttackStatic, target);
                                shot.playerForced = true;
                                if (CombatOrderHelper.Take(pawn,ref shot))
                                    result.AttackingPawnIds.Add(pawn.thingIDNumber);
                                continue;
                            }
                            IntVec3 firingCell;
                            if (CombatInterceptHelper.TryPosition(pawn,target,out firingCell,defensive:tactic=="focus_fire"))
                            {
                                MoveAndAim(pawn,target,firingCell,result);
                            }
                            else result.Notes.Add($"No timely predictive firing lane for {pawn.LabelShort}; changing distant edge-of-range waypoints is not progress.");
                            continue;
                        }
                        float threatRange = nearestThreat.equipment?.Primary?.def?.Verbs?.FirstOrDefault()?.range ?? 0f;
                        float retreatDistance = Math.Max(18f, Math.Min(45f, threatRange + 4f));
                        if (tactic == "withdraw_and_regroup" && pawn.Position.DistanceTo(nearestThreat.Position) >= retreatDistance)
                        {
                            pawn.jobs.StopAll();
                            result.Notes.Add($"{pawn.LabelShortCap} has regained space and waits for the next order.");
                            continue;
                        }
                        if (tactic == "hold_cover" || tactic == "firing_line" || tactic == "fallback_line")
                        {
                            target=CombatControlHelper.AvailableFiringTarget(pawn,target);
                            if(CombatControlHelper.TryCoveredShot(pawn,target,out var coveredCell))
                            {MoveAndAim(pawn,target,coveredCell,result);continue;}
                            if(IsRanged(pawn) && (CoverUtility.CalculateOverallBlockChance(pawn,target.Position,map)>=.3f
                                    || CombatControlHelper.RetainIncomingPost(pawn,target))
                                && CombatInterceptHelper.IncomingToRange(pawn,target,pawn.Position,out var incomingCell)
                                && !CanShootTarget(pawn,pawn.Position,target))
                            {
                                if(pawn.CurJobDef!=JobDefOf.Wait_Combat)
                                {
                                    var hold=JobMaker.MakeJob(JobDefOf.Wait_Combat);hold.playerForced=true;
                                    if(!CombatOrderHelper.Take(pawn,ref hold))continue;
                                }
                                result.PreservedPawnIds.Add(pawn.thingIDNumber);
                                result.Notes.Add("Covered defender holds while the observed approach enters its firing lane; no forward step out of cover.");
                                continue;
                            }
                            // These defensive orders used to walk two cells
                            // backward on every cycle because their desired
                            // position was recomputed from the current cell.
                            // Cover outside this shooter's range is not a
                            // firing line: moving there can abandon an ally
                            // fighting next to the target.
                            float range = pawn.equipment?.Primary?.def?.Verbs?.FirstOrDefault()?.range ?? 0f;
                            if (CanShootTarget(pawn, pawn.Position, target))
                            {
                                if (pawn.CurJob?.def == JobDefOf.AttackStatic && pawn.CurJob.targetA.Thing == target)
                                {
                                    result.AttackingPawnIds.Add(pawn.thingIDNumber);
                                    continue;
                                }
                                Job shot = JobMaker.MakeJob(JobDefOf.AttackStatic, target);
                                shot.playerForced = true;
                                if (CombatOrderHelper.Take(pawn,ref shot))
                                    result.AttackingPawnIds.Add(pawn.thingIDNumber);
                                continue;
                            }
                            IntVec3 firingCell;
                            if (CombatInterceptHelper.TryPosition(pawn, target, out firingCell, defensive:true))
                            {
                                MoveAndAim(pawn,target,firingCell,result);
                                continue;
                            }
                            // A covered firing order must not strand a shooter who
                            // starts outside weapon range (or on the far side of a
                            // building). Advance in safe, short steps until a real
                            // firing cell becomes reachable; then the next cycle
                            // uses the exact line-of-sight check above.
                            IntVec3 approach;
                            if (target.pather?.Moving != true && TryFindApproachCell(pawn, target, tactic, out approach)
                                && CombatInterceptMath.DefensiveAdvance(approach.DistanceTo(pawn.Position),
                                    pawn.Position.DistanceTo(target.Position),approach.DistanceTo(target.Position),false))
                            {
                                if (pawn.CurJob?.def == JobDefOf.Goto && pawn.CurJob.targetA.Cell == approach)
                                {
                                    result.PositionedPawnIds.Add(pawn.thingIDNumber);
                                    continue;
                                }
                                Job move = JobMaker.MakeJob(JobDefOf.Goto, approach);
                                move.playerForced = true;
                                if (CombatOrderHelper.Take(pawn,ref move))
                                    result.PositionedPawnIds.Add(pawn.thingIDNumber);
                                continue;
                            }
                            bool usableCover = defense != null && IsRanged(pawn)
                                && defense.Position.DistanceTo(target.Position) <= range - 2f
                                && CanShootTarget(pawn, defense.Position, target);
                            bool needsCover = usableCover
                                && pawn.Position.DistanceToSquared(defense.Position) > 9;
                            if (!needsCover)
                            {
                                // A selected gun already at its defensive post
                                // still needs the short native contact controller.
                                // Record an actual retained/issued Wait_Combat,
                                // rather than losing the plan when no move or
                                // immediate shot is possible from this post.
                                if(IsRanged(pawn))
                                {
                                    if(pawn.CurJobDef!=JobDefOf.Wait_Combat)
                                    {
                                        var hold=JobMaker.MakeJob(JobDefOf.Wait_Combat);hold.playerForced=true;
                                        if(!CombatOrderHelper.Take(pawn,ref hold))continue;
                                    }
                                    result.PreservedPawnIds.Add(pawn.thingIDNumber);
                                }
                                result.Notes.Add($"{pawn.LabelShortCap} cannot shoot {target.LabelShortCap} from the current side of cover.");
                                continue;
                            }
                        }
                        if (tactic == "kite" && pawn.Position.DistanceTo(target.Position) >= 10f)
                        {
                            // Do not keep retreating beyond the insects' pursuit
                            // distance. The lure stays in the firing envelope and
                            // shoots while the covering group attacks separately.
                            Job shot = JobMaker.MakeJob(JobDefOf.AttackStatic, target);
                            shot.playerForced = true;
                            if (CombatOrderHelper.Take(pawn,ref shot))
                                result.AttackingPawnIds.Add(pawn.thingIDNumber);
                            continue;
                        }
                        if (tactic == "backstep_fire" && pawn.Position.DistanceTo(nearestThreat.Position) >= 9f)
                        {
                            float range = pawn.equipment?.Primary?.def?.Verbs?.FirstOrDefault()?.range ?? 0f;
                            if (IsRanged(pawn) && pawn.Position.DistanceTo(target.Position) <= range)
                            {
                                Job shot = JobMaker.MakeJob(JobDefOf.AttackStatic, target);
                                shot.playerForced = true;
                                if (CombatOrderHelper.Take(pawn,ref shot))
                                    result.AttackingPawnIds.Add(pawn.thingIDNumber);
                            }
                            else
                                pawn.jobs.StopAll();
                            continue;
                        }
                        if ((tactic == "withdraw_and_regroup" || tactic == "civilian_retreat")
                            && TryFindCoveredRetreatCell(pawn, nearestThreat, ref retreatPathAttempts, out IntVec3 coveredRetreat))
                        {
                            if (pawn.CurJobDef == JobDefOf.Goto && pawn.CurJob.targetA.Cell == coveredRetreat)
                            {
                                result.PositionedPawnIds.Add(pawn.thingIDNumber);
                                continue;
                            }
                            Job regroup = JobMaker.MakeJob(JobDefOf.Goto, coveredRetreat);
                            regroup.playerForced = true;
                            if (CombatOrderHelper.Take(pawn,ref regroup))
                            {result.PositionedPawnIds.Add(pawn.thingIDNumber);CombatControlHelper.RememberRegroup(pawn,regroup);}
                            continue;
                        }
                        IntVec3 desired = DesiredCell(pawn, nearestThreat, defense, tactic, i, ordered.Count);
                        IntVec3 safe;
                        bool choke = tactic == "melee_block" || tactic == "door_defense" || tactic == "infestation_choke";
                        bool positionFound = choke
                            ? ResilienceDefenseHelper.TryPosition(pawn, nearestThreat, defense,
                                ordered.Take(i).Count(f => IsRanged(f) == IsRanged(pawn)), out safe)
                            : TryFindTrapFreeCell(pawn, desired, nearestThreat.Position, tactic, out safe,
                                6f, tactic == "kite" ? 16f : tactic == "backstep_fire" ? 14f : float.MaxValue);
                        if (positionFound)
                        {
                            if(IsRanged(pawn) && new[]{"hold_cover","firing_line","fallback_line"}.Contains(tactic))
                            {
                                if(CanShootTarget(pawn,safe,target) && CombatControlHelper.CheckedDefensivePost(pawn,target,safe))
                                    MoveAndAim(pawn,target,safe,result);
                                else
                                {
                                    if(pawn.CurJobDef!=JobDefOf.Wait_Combat)
                                    {
                                        var hold=JobMaker.MakeJob(JobDefOf.Wait_Combat);hold.playerForced=true;
                                        if(!CombatOrderHelper.Take(pawn,ref hold))continue;
                                    }
                                    result.PreservedPawnIds.Add(pawn.thingIDNumber);
                                    result.Notes.Add("No short checked firing window at the fallback cell; retain this defensive post.");
                                }
                                continue;
                            }
                            if (pawn.CurJobDef == JobDefOf.Goto && pawn.CurJob.targetA.Cell == safe)
                            {
                                result.PositionedPawnIds.Add(pawn.thingIDNumber);
                                continue;
                            }
                            Job move = JobMaker.MakeJob(JobDefOf.Goto, safe);
                            move.playerForced = true;
                            if (CombatOrderHelper.Take(pawn,ref move))
                            {
                                result.PositionedPawnIds.Add(pawn.thingIDNumber);
                                if(tactic=="withdraw_and_regroup")CombatControlHelper.RememberRegroup(pawn,move);
                            }
                        }
                        else
                        {
                            result.Notes.Add($"No trap-free reachable position was found for {pawn.LabelShortCap}; current position retained.");
                            if (tactic == "civilian_retreat")
                            {
                                pawn.drafter.Drafted = false;
                                result.DraftedPawnIds.Remove(pawn.thingIDNumber);
                            }
                        }
                    }
                    if (result.PositionedPawnIds.Count > 0 || result.AttackingPawnIds.Count > 0
                        || tactic == "civilian_retreat" || tactic == "hold_cover" || tactic == "firing_line"
                        || tactic == "fallback_line"
                        || tactic == "backstep_fire" || tactic == "advance_to_range" || tactic == "withdraw_and_regroup"
                        || tactic == "melee_block" || tactic == "door_defense" || tactic == "infestation_choke")
                        return ApiResult<CombatTacticResponseDto>.Ok(result);
                }

                bool meleeRush = tactic == "rush_ranged" || tactic == "melee_block";
                foreach (Pawn pawn in fighters)
                {
                CombatPathBudgetHelper.Checkpoint();
                    bool ranged = IsRanged(pawn) && !meleeRush;
                    JobDef jobDef = ranged ? JobDefOf.AttackStatic : JobDefOf.AttackMelee;
                    Job attack = JobMaker.MakeJob(jobDef, target);
                    attack.playerForced = true;
                    if (CombatOrderHelper.Take(pawn,ref attack))
                        result.AttackingPawnIds.Add(pawn.thingIDNumber);
                }
                return ApiResult<CombatTacticResponseDto>.Ok(result);
            }
            catch(CombatReviewDeferredException) {throw;}
            catch (Exception ex)
            {
                LogApi.Error($"Combat tactic failed: {ex}");
                return ApiResult<CombatTacticResponseDto>.Fail(ex.Message);
            }
        }

        private static ApiResult<CombatTacticResponseDto> ApplyCareRetreat(Map map, CombatTacticRequestDto request)
        {
            var result = new CombatTacticResponseDto { Tactic = "caregiver_retreat" };
            if (request.FighterIds == null || request.FighterIds.Count != 1)
                return ApiResult<CombatTacticResponseDto>.Fail("Care retreat requires exactly one named caregiver.");
            Pawn actor = MapHelper.GetThingOnMapById(map.uniqueID, request.FighterIds[0]) as Pawn;
            Thing threat = request.TargetPawnId.HasValue
                ? MapHelper.GetThingOnMapById(map.uniqueID, request.TargetPawnId.Value) : null;
            if (actor == null || !actor.IsColonistPlayerControlled || actor.Dead || actor.Downed || actor.InMentalState
                || !CombatNativeHelper.HasClinicalCareJob(actor) || actor.CurJobDef.defName != request.ExpectedCurrentJob
                || !(CombatNativeHelper.CareTarget(actor) is Pawn patient)
                || patient.thingIDNumber != request.ExpectedCarePatientId || actor.carryTracker?.CarriedThing is Pawn
                || !CombatNativeHelper.ImmediateCareThreat(actor, threat))
            {
                result.Notes.Add("Exact care or immediate threat changed; current care retained.");
                return ApiResult<CombatTacticResponseDto>.Ok(result);
            }
            int attempts = 0;
            IntVec3 safe;
            int dx = Math.Sign(actor.Position.x - threat.Position.x);
            int dz = Math.Sign(actor.Position.z - threat.Position.z);
            if (dx == 0 && dz == 0) dx = 1;
            IntVec3 desired = new IntVec3(actor.Position.x + dx * 8, 0, actor.Position.z + dz * 8);
            if (!TryFindCoveredRetreatCell(actor, threat, ref attempts, out safe)
                && !TryFindTrapFreeCell(actor, desired,
                    threat.Position, "civilian_retreat", out safe, 6f))
            {
                result.Notes.Add("No checked escape route; current care retained.");
                return ApiResult<CombatTacticResponseDto>.Ok(result);
            }
            // A normal forced Goto can retreat without toggling the draft and
            // destroying care before a replacement job has been accepted.
            Job move = JobMaker.MakeJob(JobDefOf.Goto, safe);
            move.playerForced = true;
            int moveId = move.loadID;
            // TryTakeOrderedJob clears later queued instructions. Put this
            // exact escape first and let native queue selection start it;
            // later jobs keep their identity, order and native reservations.
            actor.jobs.jobQueue.EnqueueFirst(move, JobTag.Misc);
            actor.jobs.EndCurrentJob(JobCondition.InterruptForced, true);
            if (move.loadID == moveId && actor.CurJob == move)
            {
                CombatNativeHelper.RememberCareRetreat(actor, move);
                result.PositionedPawnIds.Add(actor.thingIDNumber);
            }
            else result.Notes.Add("Native escape did not become the current job; inspect current care and queued instructions before retrying.");
            result.TargetPawnId = threat.thingIDNumber;
            result.Notes.Add("Only the named caregiver's care may be suspended; escape completion unverified.");
            return ApiResult<CombatTacticResponseDto>.Ok(result);
        }

        private static bool IsRanged(Pawn pawn)
        {
            return pawn?.equipment?.Primary?.def?.IsRangedWeapon ?? false;
        }

        private static bool CanShootTarget(Pawn pawn, IntVec3 from, Thing target)
        {
            if (!IsRanged(pawn) || target == null || target.Destroyed
                || !from.InBounds(pawn.Map) || !from.Standable(pawn.Map)
                || (target is Pawn victim && (victim.Dead || victim.Downed)))
                return false;
            Verb verb = pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            return verb != null && (from == pawn.Position ? CombatInterceptHelper.CanShootNow(pawn,target)
                :verb.CanHitTargetFrom(from,target) && CombatInterceptHelper.FriendlyLaneClear(pawn,target,from));
        }

        private static bool TryFindFiringCell(Pawn pawn, Pawn target, out IntVec3 result)
            => CombatInterceptHelper.TryPosition(pawn,target,out result);

        private static void MoveAndAim(Pawn pawn,Pawn target,IntVec3 cell,CombatTacticResponseDto result)
        {
            if(CareTriageHelper.QueuedCare(pawn))return;
            if(cell==pawn.Position)
            {
                if(CombatInterceptHelper.CanShootNow(pawn,target))
                {
                    if(pawn.CurJobDef==JobDefOf.AttackStatic && pawn.CurJob.targetA.Thing==target)
                        result.AttackingPawnIds.Add(pawn.thingIDNumber);
                    else
                    {
                        var immediate=JobMaker.MakeJob(JobDefOf.AttackStatic,target);immediate.playerForced=true;
                        if(CombatOrderHelper.Take(pawn,ref immediate))result.AttackingPawnIds.Add(pawn.thingIDNumber);
                    }
                }
                else result.Notes.Add("Already at the predicted firing cell; no zero-distance move or replacement shot queued. A fresh native firing opportunity is required.");
                return;
            }
            bool same=pawn.CurJobDef==JobDefOf.Goto && pawn.CurJob.targetA.Cell==cell;
            bool queued=pawn.jobs.jobQueue.Any(q=>q.job.def==JobDefOf.AttackStatic && q.job.targetA.Thing==target);
            if(same && queued){result.PositionedPawnIds.Add(pawn.thingIDNumber);return;}
            var move=JobMaker.MakeJob(JobDefOf.Goto,cell);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
            if(!CombatOrderHelper.Take(pawn,ref move))return;
            var shot=CombatOrderHelper.QueueShot(pawn,target,true);
            CombatControlHelper.RememberMove(pawn,move,shot);
            result.PositionedPawnIds.Add(pawn.thingIDNumber);
            result.Notes.Add(CombatInterceptHelper.LastPrediction ?? "Normal firing approach; arrival and selected-target shot are unverified.");
            result.Notes.Add($"{pawn.LabelShort}: queued normal shot at exact enemy {target.thingIDNumber} after arrival; not a fired projectile or hit.");
        }

        private static bool TryFindApproachCell(Pawn pawn, Pawn target, string tactic, out IntVec3 result)
        {
            float dx = target.Position.x - pawn.Position.x;
            float dz = target.Position.z - pawn.Position.z;
            float distance = (float)Math.Sqrt(dx * dx + dz * dz);
            if (distance < 7f)
            {
                result = IntVec3.Invalid;
                return false;
            }
            float step = Math.Min(12f, Math.Max(3f, distance - 6f));
            IntVec3 desired = new IntVec3(
                pawn.Position.x + (int)Math.Round(dx * step / distance), 0,
                pawn.Position.z + (int)Math.Round(dz * step / distance));
            IntVec3 candidate;
            if (TryFindTrapFreeCell(pawn, desired, target.Position, tactic, out candidate, 6f)
                && candidate.DistanceToSquared(target.Position) + 4 < pawn.Position.DistanceToSquared(target.Position))
            {
                result = candidate;
                return true;
            }
            result = IntVec3.Invalid;
            return false;
        }

        private static Building FindDefense(Map map, int? requestedId, string tactic, IntVec3 target, List<Pawn> fighters)
        {
            IEnumerable<Building> candidates = map.listerBuildings.allBuildingsColonist
                .Where(b => b != null && !b.Destroyed && !(b is Building_Trap));
            if (tactic == "melee_block" || tactic == "door_defense" || tactic == "infestation_choke")
                candidates = candidates.Where(ResilienceDefenseHelper.IsActualChoke);
            if (requestedId.HasValue)
            {
                Building exact = candidates.FirstOrDefault(b => b.thingIDNumber == requestedId.Value);
                if (exact != null) return exact;
            }
            string[] preferred = tactic == "melee_block" || tactic == "door_defense" || tactic == "infestation_choke"
                ? new[] { "door", "wall" }
                : tactic == "killbox_hold"
                    ? new[] { "barricade", "sandbag", "turret", "wall" }
                    : tactic == "fallback_line" || tactic == "fire_retreat"
                        ? new[] { "barricade", "sandbag", "door", "wall" }
                        : new[] { "barricade", "sandbag", "wall", "shelf", "turret" };
            return candidates
                .Where(b => preferred.Any(token => (b.def.defName + " " + b.Label).ToLowerInvariant().Contains(token)))
                .Where(b => fighters.Any(f => f.Position.DistanceToSquared(b.Position) <= 400))
                .Where(b => b.Position.DistanceToSquared(target) >= 36)
                .Where(b => tactic != "hold_cover" && tactic != "firing_line" || fighters.Any(f =>
                    IsRanged(f) && b.Position.DistanceTo(target) <=
                    (f.equipment?.Primary?.def?.Verbs?.FirstOrDefault()?.range ?? 0f) - 2f))
                .OrderBy(b => fighters.Min(f => f.Position.DistanceToSquared(b.Position)) + b.Position.DistanceToSquared(target) / 4)
                .FirstOrDefault();
        }

        private static IntVec3 DesiredCell(Pawn pawn, Pawn target, Building defense, string tactic, int index, int count)
        {
            if (tactic == "kite" || tactic == "backstep_fire")
            {
                float awayX = pawn.Position.x - target.Position.x;
                float awayZ = pawn.Position.z - target.Position.z;
                float distance = (float)Math.Sqrt(awayX * awayX + awayZ * awayZ);
                float step = Math.Min(tactic == "kite" ? 10f : 6f,
                    Math.Max(0f, (tactic == "kite" ? 14f : 11f) - distance));
                if (distance < 0.1f) awayX = 1f;
                return new IntVec3(
                    pawn.Position.x + (int)Math.Round(awayX * step / Math.Max(distance, 1f)), 0,
                    pawn.Position.z + (int)Math.Round(awayZ * step / Math.Max(distance, 1f)));
            }
            IntVec3 baseCell = tactic == "withdraw_and_regroup" ? pawn.Position : defense?.Position ?? pawn.Position;
            int dx = Math.Sign(baseCell.x - target.Position.x);
            int dz = Math.Sign(baseCell.z - target.Position.z);
            if (dx == 0 && dz == 0) dx = 1;
            int sideX = -dz;
            int sideZ = dx;
            int spacing = tactic == "spread_out" || tactic == "drop_pod_encircle" ? 3 : 1;
            int centered = index - count / 2;

            if (tactic == "staggered_retreat" || tactic == "fire_retreat" || tactic == "civilian_retreat"
                || tactic == "withdraw_and_regroup")
                return new IntVec3(pawn.Position.x + dx * 8 + sideX * centered, 0, pawn.Position.z + dz * 8 + sideZ * centered);
            if (tactic == "wide_flank" || tactic == "pincer")
            {
                int side = (index % 2 == 0 ? -1 : 1) * Math.Max(7, 3 + count);
                return new IntVec3(target.Position.x + dx * 14 + sideX * side, 0, target.Position.z + dz * 14 + sideZ * side);
            }
            if (tactic == "drop_pod_encircle")
            {
                IntVec3[] ring = { IntVec3.North, IntVec3.East, IntVec3.South, IntVec3.West, IntVec3.NorthEast, IntVec3.SouthWest };
                IntVec3 offset = ring[index % ring.Length] * 7;
                return target.Position + offset;
            }
            int depth = tactic == "melee_block" || tactic == "door_defense" || tactic == "infestation_choke" ? 1 : 2;
            return new IntVec3(baseCell.x + dx * depth + sideX * centered * spacing, 0, baseCell.z + dz * depth + sideZ * centered * spacing);
        }

        internal static bool RetreatRouteSafe(Pawn pawn,PawnPath path)
            =>RetreatRouteSafe(pawn,CombatPathBudgetHelper.Borrowed(path));
        internal static bool RetreatRouteSafe(Pawn pawn,CombatPathBudgetHelper.Observation path)
        {
            List<Pawn> threats = pawn.Map.mapPawns.AllPawnsSpawned
                .Where(p => !p.Dead && !p.Downed && CombatNativeHelper.IsPlayerThreat(p)).ToList();
            var turrets = pawn.Map.listerBuildings.allBuildingsNonColonist.OfType<Building_Turret>()
                .Where(CombatNativeHelper.ActiveStructure).ToList();
            // Allow a first step out of existing contact and bends in a narrow
            // escape route. Never route through a live threat or friendly trap.
            return path.Found && path.NodesReversed.All(node => !HasFriendlyTrap(node, pawn.Map)
                && !node.ContainsStaticFire(pawn.Map)
                && threats.All(threat => node != threat.Position && node.DistanceToSquared(threat.Position)
                    >= (node.DistanceToSquared(pawn.Position) <= 4
                        ? Math.Min(4, pawn.Position.DistanceToSquared(threat.Position)) : 4))
                && turrets.All(turret => !turret.AttackVerb.CanHitTargetFrom(turret.Position, node)
                    || node.DistanceToSquared(turret.Position) >= pawn.Position.DistanceToSquared(turret.Position)));
        }

        private static bool TryFindCoveredRetreatCell(Pawn pawn, Thing threat, ref int pathAttempts, out IntVec3 result)
        {
            Map map = pawn.Map;
            List<Pawn> covering = map.mapPawns.FreeColonistsSpawned
                .Where(shooter => shooter != pawn && !shooter.Dead && !shooter.Downed && !shooter.InMentalState
                    && !shooter.WorkTagIsDisabled(WorkTags.Violent) && IsRanged(shooter)
                    && !CombatNativeHelper.Protected(shooter)
                    && shooter.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb?.Available() == true
                    && CanShootTarget(shooter, shooter.Position, threat))
                .OrderBy(shooter => shooter.Position.DistanceToSquared(pawn.Position)).Take(3).ToList();
            foreach (Pawn shooter in covering)
            {
                CombatPathBudgetHelper.Checkpoint();
                IEnumerable<IntVec3> candidates = GenRadial.RadialCellsAround(pawn.Position, 8f, false)
                    .Where(cell => cell.InBounds(map) && cell.Standable(map) && !cell.Fogged(map)
                        && !cell.ContainsStaticFire(map) && !HasFriendlyTrap(cell, map)
                        && !cell.GetThingList(map).OfType<Pawn>().Any()
                        && cell.InHorDistOf(shooter.Position, 8f)
                        && cell.DistanceToSquared(shooter.Position) + 4 < pawn.Position.DistanceToSquared(shooter.Position)
                        && cell.DistanceToSquared(threat.Position) >= 36)
                    .OrderBy(cell => CombatControlHelper.IncomingRangedExposure(pawn,cell))
                    .ThenBy(cell => cell.DistanceToSquared(shooter.Position))
                    .ThenByDescending(cell => cell.DistanceToSquared(threat.Position));
                foreach (IntVec3 cell in candidates)
                {
                CombatPathBudgetHelper.Checkpoint();
                    if (++pathAttempts > 16)
                    {
                        result = IntVec3.Invalid;
                        return false;
                    }
                    var path = CombatPathBudgetHelper.Query(pawn,pawn.Position,cell,PathEndMode.OnCell);
                    bool safe = RetreatRouteSafe(pawn, path);
                    path.Dispose();
                    if (!safe) continue;
                    result = cell;
                    return true;
                }
            }
            result = IntVec3.Invalid;
            return false;
        }

        private static bool TryFindGuardRegroupCell(Pawn pawn, Pawn shooter, Pawn threat, out IntVec3 result)
        {
            Map map = pawn.Map;
            int currentShooterDistance = pawn.Position.DistanceToSquared(shooter.Position);
            IEnumerable<IntVec3> candidates = GenRadial.RadialCellsAround(pawn.Position, 8f, true)
                .Where(cell => cell != pawn.Position && cell.InBounds(map) && cell.Standable(map)
                    && !cell.Fogged(map) && !cell.ContainsStaticFire(map) && !HasFriendlyTrap(cell, map)
                    && !cell.GetThingList(map).OfType<Pawn>().Any()
                    && cell.DistanceToSquared(shooter.Position) + 4 < currentShooterDistance
                    && cell.DistanceToSquared(threat.Position) >= 36)
                .OrderBy(cell => cell.DistanceToSquared(shooter.Position))
                .ThenByDescending(cell => cell.DistanceToSquared(threat.Position))
                .Take(24);
            foreach (IntVec3 cell in candidates)
            {
                CombatPathBudgetHelper.Checkpoint();
                var path = CombatPathBudgetHelper.Query(pawn,pawn.Position,cell,PathEndMode.OnCell);
                int startingThreatDistance = pawn.Position.DistanceToSquared(threat.Position);
                bool valid = path.Found && path.NodesReversed.All(node => !HasFriendlyTrap(node, map)
                    && (node == pawn.Position || node.DistanceToSquared(threat.Position) >=
                        (node.DistanceToSquared(pawn.Position) <= 4
                            ? Math.Min(4, startingThreatDistance) : 4)));
                path.Dispose();
                if (!valid) continue;
                result = cell;
                return true;
            }
            result = IntVec3.Invalid;
            return false;
        }

        private static bool TryFindTrapFreeCell(Pawn pawn, IntVec3 desired, IntVec3 hostile, string tactic, out IntVec3 result,
            float minimumHostileDistance = 6f, float maximumHostileDistance = float.MaxValue)
        {
            Map map = pawn.Map;
            bool melee = tactic == "melee_block" || tactic == "door_defense" || tactic == "rush_ranged" || tactic == "infestation_choke";
            List<Pawn> nearbyHostiles = melee ? null : map.mapPawns.AllPawnsSpawned
                .Where(p => !p.Dead && !p.Downed && CombatNativeHelper.IsPlayerThreat(p)).ToList();
            IEnumerable<IntVec3> candidates = GenRadial.RadialCellsAround(desired, 7f, true)
                .Where(cell => cell.InBounds(map) && cell.Standable(map) && !cell.Fogged(map)
                    && !cell.ContainsStaticFire(map) && !HasFriendlyTrap(cell, map)
                    && !cell.GetThingList(map).OfType<Pawn>().Any())
                .OrderBy(cell => cell.DistanceToSquared(desired));
            foreach (IntVec3 cell in candidates)
            {
                CombatPathBudgetHelper.Checkpoint();
                if (!melee && (cell.DistanceToSquared(hostile) < minimumHostileDistance * minimumHostileDistance
                    || nearbyHostiles.Any(p => cell.DistanceToSquared(p.Position)
                        < minimumHostileDistance * minimumHostileDistance)))
                    continue;
                if (cell.DistanceToSquared(hostile) > maximumHostileDistance * maximumHostileDistance)
                    continue;
                var path = CombatPathBudgetHelper.Query(pawn,pawn.Position,cell,PathEndMode.OnCell);
                bool valid = path.Found && path.NodesReversed.All(node => !HasFriendlyTrap(node, map));
                if (tactic == "withdraw_and_regroup" || tactic == "civilian_retreat")
                    valid = valid && RetreatRouteSafe(pawn, path);
                path.Dispose();
                if (!valid) continue;
                result = cell;
                return true;
            }
            result = IntVec3.Invalid;
            return false;
        }

        private static bool HasFriendlyTrap(IntVec3 cell, Map map)
        {
            return cell.GetThingList(map).Any(t => t is Building_Trap && t.Faction == Faction.OfPlayer);
        }
    }
}

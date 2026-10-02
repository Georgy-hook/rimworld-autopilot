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

        public static ApiResult<CombatTacticResponseDto> Apply(CombatTacticRequestDto request)
        {
            try
            {
                Map map = MapHelper.GetMapByID(request.MapId);
                if (map == null)
                    return ApiResult<CombatTacticResponseDto>.Fail($"Map {request.MapId} not found.");
                string tactic = (request.Tactic ?? "").Trim().ToLowerInvariant();
                if(new[]{"emp_control","smoke_advance","mortar_counterbattery","mortar_reload","attack_structure"}.Contains(tactic))return ApiResult<CombatTacticResponseDto>.Ok(CombatNativeHelper.Apply(map,request));
                if (tactic == "stand_down")
                {
                    if (map.mapPawns.AllPawnsSpawned.Any(p => !p.Dead && !p.Downed && p.HostileTo(Faction.OfPlayer))
                        || map.listerBuildings.allBuildingsNonColonist.Any(CombatNativeHelper.ActiveStructure))
                        return ApiResult<CombatTacticResponseDto>.Fail("Hostiles remain; stand down no longer feasible.");
                    foreach (Pawn pawn in map.mapPawns.FreeColonistsSpawned.Where(p => p.drafter?.Drafted == true))
                        pawn.drafter.Drafted = false;
                    return ApiResult<CombatTacticResponseDto>.Ok(new CombatTacticResponseDto { Tactic = tactic });
                }

                if (!PositioningTactics.Contains(tactic) && !new[] { "melee_assault", "rush_ranged", "melee_hold_line", "lure_enemy",
                    "preemptive_strike", "screen_melee", "guard_shooters", "psycast_control", "psycast_support" }.Contains(tactic))
                    return ApiResult<CombatTacticResponseDto>.Fail("Unknown combat tactic; no fighters drafted.");
                List<Pawn> fighters = map.mapPawns.FreeColonistsSpawned
                    .Where(p => request.FighterIds.Contains(p.thingIDNumber) && !p.Dead && !p.Downed
                        && !p.InMentalState && !CombatNativeHelper.Protected(p))
                    .ToList();
                if (fighters.Count == 0)
                    return ApiResult<CombatTacticResponseDto>.Fail("No selected healthy fighter is available on this map.");
                Pawn target = request.TargetPawnId.HasValue
                    ? map.mapPawns.AllPawnsSpawned.FirstOrDefault(p => p.thingIDNumber == request.TargetPawnId.Value && !p.Dead && !p.Downed && p.HostileTo(Faction.OfPlayer))
                    : map.mapPawns.AllPawnsSpawned
                        .Where(p => !p.Dead && !p.Downed && p.HostileTo(Faction.OfPlayer))
                        .OrderBy(p => fighters.Min(f => f.Position.DistanceToSquared(p.Position)))
                        .FirstOrDefault();
                if (target == null && tactic != "psycast_support" && tactic != "psycast_control")
                    return ApiResult<CombatTacticResponseDto>.Fail("No living active hostile target remains; no fighters drafted.");
                var result = new CombatTacticResponseDto
                {
                    Tactic = tactic,
                    TargetPawnId = target?.thingIDNumber,
                };

                if (tactic == "intercept_kidnapper" && !CombatNativeHelper.Kidnapper(target)) {
                    result.Notes.Add("Target is no longer an actual kidnapper carrying a player-owned victim; no fighters drafted.");
                    return ApiResult<CombatTacticResponseDto>.Ok(result);
                }

                foreach (Pawn pawn in fighters)
                {
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

                if (target == null)
                {
                    result.Notes.Add("No living hostile target remains; fighters were drafted but no attack was issued.");
                    return ApiResult<CombatTacticResponseDto>.Ok(result);
                }

                if (tactic == "melee_hold_line")
                {
                    Pawn closeThreat = map.mapPawns.AllPawnsSpawned
                        .Where(p => !p.Dead && !p.Downed && p.HostileTo(Faction.OfPlayer))
                        .OrderBy(p => fighters.Min(f => f.Position.DistanceToSquared(p.Position)))
                        .FirstOrDefault();
                    bool threatened = closeThreat != null
                        && fighters.Min(f => f.Position.DistanceTo(closeThreat.Position)) <= 7f;
                    Pawn anchor = fighters.OrderBy(p => p.Position.DistanceToSquared(target.Position)).First();
                    foreach (Pawn pawn in fighters)
                    {
                        if (threatened)
                        {
                            if (pawn.CurJob?.def == JobDefOf.AttackMelee && pawn.CurJob.targetA.Thing == closeThreat)
                            {
                                result.AttackingPawnIds.Add(pawn.thingIDNumber);
                                continue;
                            }
                            Job attack = JobMaker.MakeJob(JobDefOf.AttackMelee, closeThreat);
                            attack.playerForced = true;
                            if (pawn.jobs.TryTakeOrderedJob(attack))
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
                            if (pawn.jobs.TryTakeOrderedJob(move))
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
                        Pawn nearest = map.mapPawns.AllPawnsSpawned
                            .Where(p => !p.Dead && !p.Downed && p.HostileTo(Faction.OfPlayer))
                            .OrderBy(p => pawn.Position.DistanceToSquared(p.Position))
                            .FirstOrDefault();
                        if (nearest == null) continue;
                        float dx = pawn.Position.x - nearest.Position.x;
                        float dz = pawn.Position.z - nearest.Position.z;
                        float distance = (float)Math.Sqrt(dx * dx + dz * dz);
                        if (distance < 0.1f) dx = 1f;
                        if (distance >= 8f && distance <= 14f)
                        {
                            pawn.jobs.StopAll();
                            result.Notes.Add($"{pawn.LabelShortCap} stays within lure distance; reassess enemy pursuit.");
                            continue;
                        }
                        float step = Math.Min(6f, Math.Abs(11f - distance));
                        float direction = distance < 8f ? 1f : -1f;
                        IntVec3 desired = new IntVec3(
                            pawn.Position.x + (int)Math.Round(dx * direction * step / Math.Max(distance, 1f)), 0,
                            pawn.Position.z + (int)Math.Round(dz * direction * step / Math.Max(distance, 1f)));
                        IntVec3 safe;
                        if (TryFindTrapFreeCell(pawn, desired, nearest.Position, tactic, out safe, 6f, 16f))
                        {
                            Job move = JobMaker.MakeJob(JobDefOf.Goto, safe);
                            move.playerForced = true;
                            if (pawn.jobs.TryTakeOrderedJob(move))
                                result.PositionedPawnIds.Add(pawn.thingIDNumber);
                        }
                        else
                            result.Notes.Add($"No trap-free lure position exists for {pawn.LabelShortCap}.");
                    }
                    return ApiResult<CombatTacticResponseDto>.Ok(result);
                }

                if (tactic == "preemptive_strike")
                {
                    foreach (Pawn pawn in fighters)
                    {
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
                            if (pawn.jobs.TryTakeOrderedJob(attack))
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
                            if (pawn.jobs.TryTakeOrderedJob(move))
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
                        .Where(p => !p.Dead && !p.Downed && p.HostileTo(Faction.OfPlayer))
                        .ToList();
                    foreach (Pawn pawn in fighters)
                    {
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
                                if (pawn.jobs.TryTakeOrderedJob(shot))
                                    result.AttackingPawnIds.Add(pawn.thingIDNumber);
                                continue;
                            }
                            // A guard order must not strand armed escorts behind a
                            // wall while an unarmed colonist screens the threat.
                            IntVec3 firingCell;
                            if (TryFindFiringCell(pawn, target, out firingCell)
                                || TryFindApproachCell(pawn, target, tactic, out firingCell))
                            {
                                Job move = JobMaker.MakeJob(JobDefOf.Goto, firingCell);
                                move.playerForced = true;
                                if (pawn.jobs.TryTakeOrderedJob(move))
                                    result.PositionedPawnIds.Add(pawn.thingIDNumber);
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
                                    if (pawn.jobs.TryTakeOrderedJob(retreat))
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
                            if (pawn.jobs.TryTakeOrderedJob(attack))
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
                            if (pawn.jobs.TryTakeOrderedJob(move))
                                result.PositionedPawnIds.Add(pawn.thingIDNumber);
                        }
                        else
                            result.Notes.Add($"No trap-free guard position exists for {pawn.LabelShortCap}.");
                    }
                    return ApiResult<CombatTacticResponseDto>.Ok(result);
                }

                Building defense = FindDefense(map, request.DefenseBuildingId, tactic, target.Position, fighters);
                if (tactic == "intercept_kidnapper"
                    || (tactic == "focus_fire" && CombatNativeHelper.Kidnapper(target)))
                {
                    if (!(target.carryTracker?.CarriedThing is Pawn))
                    {
                        result.Notes.Add("Target is no longer carrying a pawn; reassess the threat.");
                        return ApiResult<CombatTacticResponseDto>.Ok(result);
                    }
                    foreach (Pawn pawn in fighters)
                    {
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
                            if (pawn.jobs.TryTakeOrderedJob(attack))
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
                            if (pawn.jobs.TryTakeOrderedJob(shot))
                                result.AttackingPawnIds.Add(pawn.thingIDNumber);
                            continue;
                        }
                        float dx = target.Position.x - pawn.Position.x;
                        float dz = target.Position.z - pawn.Position.z;
                        float distance = (float)Math.Sqrt(dx * dx + dz * dz);
                        float step = Math.Min(24f, Math.Max(0f, distance - 3f));
                        IntVec3 desired = new IntVec3(
                            pawn.Position.x + (int)Math.Round(dx * step / Math.Max(distance, 1f)), 0,
                            pawn.Position.z + (int)Math.Round(dz * step / Math.Max(distance, 1f)));
                        IntVec3 safe;
                        if (!TryFindTrapFreeCell(pawn, desired, target.Position, tactic, out safe, 2f))
                        {
                            result.Notes.Add($"No trap-free pursuit route exists for {pawn.LabelShortCap}.");
                            continue;
                        }
                        Job current = pawn.CurJob;
                        if (current?.def == JobDefOf.Goto && current.targetA.Cell.IsValid
                            && current.targetA.Cell.DistanceToSquared(safe) <= 9)
                        {
                            result.PositionedPawnIds.Add(pawn.thingIDNumber);
                            continue;
                        }
                        Job chase = JobMaker.MakeJob(JobDefOf.Goto, safe);
                        chase.playerForced = true;
                        if (pawn.jobs.TryTakeOrderedJob(chase))
                            result.PositionedPawnIds.Add(pawn.thingIDNumber);
                    }
                    return ApiResult<CombatTacticResponseDto>.Ok(result);
                }
                if (PositioningTactics.Contains(tactic))
                {
                    List<Pawn> ordered = fighters
                        .OrderByDescending(p => IsRanged(p) ? p.skills?.GetSkill(SkillDefOf.Shooting)?.Level ?? 0 : p.skills?.GetSkill(SkillDefOf.Melee)?.Level ?? 0)
                        .ToList();
                    for (int i = 0; i < ordered.Count; i++)
                    {
                        Pawn pawn = ordered[i];
                        Pawn nearestThreat = (tactic == "backstep_fire" || tactic == "withdraw_and_regroup")
                            ? map.mapPawns.AllPawnsSpawned
                                .Where(p => !p.Dead && !p.Downed && p.HostileTo(Faction.OfPlayer))
                                .OrderBy(p => pawn.Position.DistanceToSquared(p.Position))
                                .FirstOrDefault() ?? target
                            : target;
                        if (tactic == "advance_to_range" || tactic == "focus_fire")
                        {
                            float range = pawn.equipment?.Primary?.def?.Verbs?.FirstOrDefault()?.range ?? 0f;
                            if (!IsRanged(pawn) || range <= 6f)
                            {
                                result.Notes.Add($"{pawn.LabelShortCap} has no usable ranged weapon for a covered advance.");
                                continue;
                            }
                            float dx = target.Position.x - pawn.Position.x;
                            float dz = target.Position.z - pawn.Position.z;
                            float distance = (float)Math.Sqrt(dx * dx + dz * dz);
                            if (distance <= range - 2f && CanShootTarget(pawn, pawn.Position, target))
                            {
                                Job shot = JobMaker.MakeJob(JobDefOf.AttackStatic, target);
                                shot.playerForced = true;
                                if (pawn.jobs.TryTakeOrderedJob(shot))
                                    result.AttackingPawnIds.Add(pawn.thingIDNumber);
                                continue;
                            }
                            if (distance <= range - 2f)
                            {
                                IntVec3 firingCell;
                                if (TryFindFiringCell(pawn, target, out firingCell))
                                {
                                    Job move = JobMaker.MakeJob(JobDefOf.Goto, firingCell);
                                    move.playerForced = true;
                                    if (pawn.jobs.TryTakeOrderedJob(move))
                                        result.PositionedPawnIds.Add(pawn.thingIDNumber);
                                }
                                else
                                    result.Notes.Add($"No clear trap-free firing lane exists for {pawn.LabelShortCap}.");
                                continue;
                            }
                            float step = Math.Min(8f, Math.Max(0f, distance - (range - 4f)));
                            IntVec3 approachCell = new IntVec3(
                                pawn.Position.x + (int)Math.Round(dx * step / Math.Max(distance, 1f)), 0,
                                pawn.Position.z + (int)Math.Round(dz * step / Math.Max(distance, 1f)));
                            IntVec3 safeApproach;
                            if (TryFindTrapFreeCell(pawn, approachCell, target.Position, tactic, out safeApproach, 6f))
                            {
                                Job move = JobMaker.MakeJob(JobDefOf.Goto, safeApproach);
                                move.playerForced = true;
                                if (pawn.jobs.TryTakeOrderedJob(move))
                                    result.PositionedPawnIds.Add(pawn.thingIDNumber);
                            }
                            else
                                result.Notes.Add($"No trap-free approach exists for {pawn.LabelShortCap}; current position retained.");
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
                        if (tactic == "hold_cover" || tactic == "firing_line")
                        {
                            // These defensive orders used to walk two cells
                            // backward on every cycle because their desired
                            // position was recomputed from the current cell.
                            // Cover outside this shooter's range is not a
                            // firing line: moving there can abandon an ally
                            // fighting next to the target.
                            float range = pawn.equipment?.Primary?.def?.Verbs?.FirstOrDefault()?.range ?? 0f;
                            if (CanShootTarget(pawn, pawn.Position, target))
                            {
                                Job shot = JobMaker.MakeJob(JobDefOf.AttackStatic, target);
                                shot.playerForced = true;
                                if (pawn.jobs.TryTakeOrderedJob(shot))
                                    result.AttackingPawnIds.Add(pawn.thingIDNumber);
                                continue;
                            }
                            IntVec3 firingCell;
                            if (TryFindFiringCell(pawn, target, out firingCell))
                            {
                                Job move = JobMaker.MakeJob(JobDefOf.Goto, firingCell);
                                move.playerForced = true;
                                if (pawn.jobs.TryTakeOrderedJob(move))
                                    result.PositionedPawnIds.Add(pawn.thingIDNumber);
                                continue;
                            }
                            // A covered firing order must not strand a shooter who
                            // starts outside weapon range (or on the far side of a
                            // building). Advance in safe, short steps until a real
                            // firing cell becomes reachable; then the next cycle
                            // uses the exact line-of-sight check above.
                            IntVec3 approach;
                            if (TryFindApproachCell(pawn, target, tactic, out approach))
                            {
                                Job move = JobMaker.MakeJob(JobDefOf.Goto, approach);
                                move.playerForced = true;
                                if (pawn.jobs.TryTakeOrderedJob(move))
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
                                pawn.jobs.StopAll();
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
                            if (pawn.jobs.TryTakeOrderedJob(shot))
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
                                if (pawn.jobs.TryTakeOrderedJob(shot))
                                    result.AttackingPawnIds.Add(pawn.thingIDNumber);
                            }
                            else
                                pawn.jobs.StopAll();
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
                            Job move = JobMaker.MakeJob(JobDefOf.Goto, safe);
                            move.playerForced = true;
                            if (pawn.jobs.TryTakeOrderedJob(move))
                                result.PositionedPawnIds.Add(pawn.thingIDNumber);
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
                        || tactic == "backstep_fire" || tactic == "advance_to_range" || tactic == "withdraw_and_regroup"
                        || tactic == "melee_block" || tactic == "door_defense" || tactic == "infestation_choke")
                        return ApiResult<CombatTacticResponseDto>.Ok(result);
                }

                bool meleeRush = tactic == "rush_ranged" || tactic == "melee_block";
                foreach (Pawn pawn in fighters)
                {
                    bool ranged = IsRanged(pawn) && !meleeRush;
                    JobDef jobDef = ranged ? JobDefOf.AttackStatic : JobDefOf.AttackMelee;
                    Job attack = JobMaker.MakeJob(jobDef, target);
                    attack.playerForced = true;
                    if (pawn.jobs.TryTakeOrderedJob(attack))
                        result.AttackingPawnIds.Add(pawn.thingIDNumber);
                }
                return ApiResult<CombatTacticResponseDto>.Ok(result);
            }
            catch (Exception ex)
            {
                LogApi.Error($"Combat tactic failed: {ex}");
                return ApiResult<CombatTacticResponseDto>.Fail(ex.Message);
            }
        }

        private static bool IsRanged(Pawn pawn)
        {
            return pawn?.equipment?.Primary?.def?.IsRangedWeapon ?? false;
        }

        private static bool CanShootTarget(Pawn pawn, IntVec3 from, Pawn target)
        {
            if (!IsRanged(pawn) || target == null || target.Dead || target.Downed)
                return false;
            Verb verb = pawn.equipment.Primary.TryGetComp<CompEquippable>()?.PrimaryVerb;
            return verb != null && verb.CanHitTargetFrom(from, target);
        }

        private static bool TryFindFiringCell(Pawn pawn, Pawn target, out IntVec3 result)
        {
            Map map = pawn.Map;
            float range = pawn.equipment?.Primary?.def?.Verbs?.FirstOrDefault()?.range ?? 0f;
            if (range <= 6f)
            {
                result = IntVec3.Invalid;
                return false;
            }
            IEnumerable<IntVec3> candidates = GenRadial.RadialCellsAround(pawn.Position, 24f, true)
                .Where(cell => cell != pawn.Position && cell.InBounds(map) && cell.Standable(map)
                    && !cell.Fogged(map) && !cell.ContainsStaticFire(map) && !HasFriendlyTrap(cell, map)
                    && !cell.GetThingList(map).OfType<Pawn>().Any()
                    && cell.DistanceTo(target.Position) >= 6f
                    && cell.DistanceTo(target.Position) <= range - 1f
                    && CanShootTarget(pawn, cell, target))
                .OrderBy(cell => cell.DistanceToSquared(pawn.Position));
            foreach (IntVec3 cell in candidates)
            {
                PawnPath path = map.pathFinder.FindPathNow(pawn.Position, cell, pawn, null, PathEndMode.OnCell);
                bool valid = path.Found && path.NodesReversed.All(node => !HasFriendlyTrap(node, map));
                path.ReleaseToPool();
                if (!valid) continue;
                result = cell;
                return true;
            }
            result = IntVec3.Invalid;
            return false;
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
                PawnPath path = map.pathFinder.FindPathNow(pawn.Position, cell, pawn, null, PathEndMode.OnCell);
                int startingThreatDistance = pawn.Position.DistanceToSquared(threat.Position);
                bool valid = path.Found && path.NodesReversed.All(node => !HasFriendlyTrap(node, map)
                    && (node == pawn.Position || node.DistanceToSquared(threat.Position) >=
                        (node.DistanceToSquared(pawn.Position) <= 4
                            ? Math.Min(4, startingThreatDistance) : 4)));
                path.ReleaseToPool();
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
                .Where(p => !p.Dead && !p.Downed && p.HostileTo(Faction.OfPlayer)).ToList();
            IEnumerable<IntVec3> candidates = GenRadial.RadialCellsAround(desired, 7f, true)
                .Where(cell => cell.InBounds(map) && cell.Standable(map) && !cell.Fogged(map)
                    && !cell.ContainsStaticFire(map) && !HasFriendlyTrap(cell, map)
                    && !cell.GetThingList(map).OfType<Pawn>().Any())
                .OrderBy(cell => cell.DistanceToSquared(desired));
            foreach (IntVec3 cell in candidates)
            {
                if (!melee && (cell.DistanceToSquared(hostile) < minimumHostileDistance * minimumHostileDistance
                    || nearbyHostiles.Any(p => cell.DistanceToSquared(p.Position)
                        < minimumHostileDistance * minimumHostileDistance)))
                    continue;
                if (cell.DistanceToSquared(hostile) > maximumHostileDistance * maximumHostileDistance)
                    continue;
                PawnPath path = map.pathFinder.FindPathNow(pawn.Position, cell, pawn, null, PathEndMode.OnCell);
                bool valid = path.Found && path.NodesReversed.All(node => !HasFriendlyTrap(node, map));
                path.ReleaseToPool();
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

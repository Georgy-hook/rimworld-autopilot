using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;
using RIMAPI.Core;
using RIMAPI.Models;
namespace RIMAPI.Helpers
{
    public static class SpecialistAutomationHelper
    {
        private static bool Protected(Pawn p) => p == null || p.Dead || p.Downed || p.Drafted || p.InMentalState
            || p.CurJobDef == JobDefOf.TendPatient || p.CurJobDef == JobDefOf.Rescue || p.CurJobDef == JobDefOf.FeedPatient
            || p.CurJobDef == JobDefOf.DoBill || p.health.hediffSet.hediffs.Any(h => h.IsCurrentlyLifeThreatening
                || (h.TryGetComp<HediffComp_Immunizable>() is HediffComp_Immunizable immune && immune.Immunity < 1));
        private static List<string> Modes(Pawn owner, MechanitorControlGroup group, Map map)
        {
            var mechs = group.MechsForReading;
            if (Protected(owner) || owner.Map != map || mechs.Count == 0
                || mechs.Any(p => Protected(p) || !p.Spawned || p.Map != map || p.Faction != Faction.OfPlayer
                    || p.CurJobDef == JobDefOf.MechCharge)) return new List<string>();
            return new[] { "Work", "Recharge", "SelfShutdown" }.Where(n => DefDatabase<MechWorkModeDef>.GetNamedSilentFail(n) != null).ToList();
        }
        private static WorkGiver_Warden_SuppressActivity cachedSuppressor;
        private static WorkGiver_Warden_SuppressActivity Suppressor()
        {
            if (cachedSuppressor == null)
                cachedSuppressor = DefDatabase<WorkGiverDef>.AllDefsListForReading
                    .FirstOrDefault(d => d.giverClass != null && typeof(WorkGiver_Warden_SuppressActivity).IsAssignableFrom(d.giverClass))
                    ?.Worker as WorkGiver_Warden_SuppressActivity;
            return cachedSuppressor;
        }
        private static bool WardenAvailable(Pawn p, Building_HoldingPlatform platform) => !Protected(p) && p.Spawned
            && p.Faction == Faction.OfPlayer && p.IsColonistPlayerControlled && p.Map == platform.Map
            && !p.WorkTypeIsDisabled(WorkTypeDefOf.Warden) && (p.workSettings?.GetPriority(WorkTypeDefOf.Warden) ?? 0) > 0
            && p.CurJobDef != JobDefOf.ActivitySuppression && p.CanReach(platform, PathEndMode.Touch, Danger.Some);
        // Installed WorkGiver has no nonallocating HasJobOnThing override.
        // Mirror its eligibility checks without JobMaker or JobFailReason writes.
        private static bool SuppressionReady(Pawn worker, Building_HoldingPlatform platform)
        {
            var entity = platform?.HeldPawn;
            if (!ModsConfig.AnomalyActive || entity == null || !WardenAvailable(worker, platform)
                || !ActivitySuppressionUtility.CanBeSuppressed(entity, true, false)) return false;
            var activity = entity.TryGetComp<CompActivity>();
            if (activity == null || activity.ActivityLevel < activity.suppressIfAbove
                || StatDefOf.ActivitySuppressionRate.Worker.IsDisabledFor(worker)
                || StatDefOf.ActivitySuppressionRate.Worker.GetValue(worker) <= 0f
                || !worker.CanReserve(entity, 1, -1, null, false)
                || !worker.CanReserve(platform, 1, -1, null, false)) return false;
            return SocialInteractionUtility.TryGetAdjacentInteractionCell(worker, platform, false, out var _);
        }
        private static Job SuppressionJob(Pawn worker, Building_HoldingPlatform platform)
        {
            if (!ModsConfig.AnomalyActive || platform?.HeldPawn == null || !WardenAvailable(worker, platform)
                || !ActivitySuppressionUtility.CanBeSuppressed(platform.HeldPawn, true, false)) return null;
            return Suppressor()?.JobOnThing(worker, platform, false);
        }
        public static ApiResult<SpecialistContextDto> Context(int mapId)
        {
            var map = MapHelper.GetMapByID(mapId);
            if (map == null) return ApiResult<SpecialistContextDto>.Fail("Map not found.");
            var result = new SpecialistContextDto { RoyaltyActive = ModsConfig.RoyaltyActive, IdeologyActive = ModsConfig.IdeologyActive,
                BiotechActive = ModsConfig.BiotechActive, AnomalyActive = ModsConfig.AnomalyActive };
            if (ModsConfig.BiotechActive)
            {
                result.PollutedCells = map.pollutionGrid.TotalPollution; result.PollutionPercent = map.pollutionGrid.AllPollutableCells.Count > 0 ? map.pollutionGrid.TotalPollutionPercent : 0;
                foreach (var thing in map.listerThings.AllThings)
                {
                    var dissolution = thing.TryGetComp<CompDissolution>();
                    if (thing.def.defName == "Wastepack" && dissolution != null)
                        result.Wastepacks.Add(new SpecialistWastepackDto { Id = thing.thingIDNumber, Count = thing.stackCount,
                            Frozen = dissolution.IsFrozen, CanDissolveNow = dissolution.CanDissolveNow, Temperature = thing.AmbientTemperature });
                    if (thing is Building_MechCharger)
                        result.Chargers.Add(new SpecialistChargerDto { Id = thing.thingIDNumber, DefName = thing.def.defName,
                            Powered = thing.TryGetComp<CompPowerTrader>()?.PowerOn == true });
                }
                foreach (var owner in map.mapPawns.FreeColonists.Where(p => p.mechanitor != null))
                    foreach (var group in owner.mechanitor.controlGroups)
                    {
                        var row = new SpecialistMechGroupDto { MechanitorId = owner.thingIDNumber, MechanitorName = owner.LabelShort,
                            GroupIndex = group.Index, Mode = group.WorkMode?.defName, ModeOptions = Modes(owner, group, map),
                            RechargeMin = group.mechRechargeThresholds.min, RechargeMax = group.mechRechargeThresholds.max };
                        foreach (var mech in group.MechsForReading)
                            row.Mechs.Add(new SpecialistMechDto { PawnId = mech.thingIDNumber, Name = mech.LabelShort,
                                Energy = mech.needs?.energy?.CurLevelPercentage, CurrentJob = mech.CurJobDef?.defName, Kind = mech.kindDef.defName });
                        result.MechGroups.Add(row);
                    }
                foreach (var p in map.mapPawns.FreeColonists.Where(p => p.genes != null))
                {
                    var row = new SpecialistGenePawnDto { PawnId = p.thingIDNumber, Name = p.LabelShort };
                    row.ActiveGenes.AddRange(p.genes.GenesListForReading.Where(g => g.Active).Select(g => g.def.defName));
                    foreach (var gene in p.genes.GenesListForReading.OfType<Gene_Resource>().Where(g => g.Active))
                        row.Resources.Add(new SpecialistGeneResourceDto { DefName = gene.def.defName, Level = gene.ValuePercent,
                            Target = gene.Max > 0 ? gene.targetValue / gene.Max : 0 });
                    foreach (var need in p.needs.AllNeeds.Where(n => n.def.onlyIfCausedByGene))
                        row.Needs.Add(new SocietyNeedDto { DefName = need.def.defName, Level = need.CurLevelPercentage, Description = need.def.description });
                    row.Conditions.AddRange(p.health.hediffSet.hediffs.Select(h => h.def.defName));
                    if (row.ActiveGenes.Count > 0 || row.Resources.Count > 0 || row.Needs.Count > 0) result.GenePawns.Add(row);
                }
            }
            foreach (var p in map.mapPawns.FreeColonists)
            {
                var row = new SpecialistPawnDto { PawnId = p.thingIDNumber, Name = p.LabelShort,
                    Psyfocus = ModsConfig.RoyaltyActive ? p.psychicEntropy?.CurrentPsyfocus : null,
                    Entropy = ModsConfig.RoyaltyActive ? p.psychicEntropy?.EntropyRelativeValue : null,
                    IdeologyRole = ModsConfig.IdeologyActive ? p.Ideo?.GetRole(p)?.def.defName : null };
                if (p.abilities != null) foreach (var ability in p.abilities.abilities)
                { var report = ability.CanCast;
                    row.Abilities.Add(new SpecialistAbilityDto { DefName = ability.def.defName, Psycast = ability.def.IsPsycast,
                        CanCast = report.Accepted, Reason = report.Reason, Cooldown = ability.CooldownTicksRemaining,
                        PsyfocusCost = ability.def.PsyfocusCost, EntropyGain = ability.def.EntropyGain }); }
                if (ModsConfig.RoyaltyActive && p.royalty != null)
                {
                    row.Titles.AddRange(p.royalty.AllTitlesForReading.Select(t => t.def.defName));
                    foreach (var permit in p.royalty.AllFactionPermits)
                        row.Permits.Add(new SpecialistPermitDto { DefName = permit.Permit.defName, Faction = permit.Faction.Name,
                            Favor = p.royalty.GetFavor(permit.Faction), OnCooldown = permit.OnCooldown });
                }
                if (ModsConfig.IdeologyActive && p.Ideo != null)
                    row.Rituals.AddRange(p.Ideo.PreceptsListForReading.OfType<Precept_Ritual>().Select(r => r.def.defName));
                if (row.Abilities.Count > 0 || row.Titles.Count > 0 || row.IdeologyRole != null || row.Rituals.Count > 0)
                    result.SpecialistPawns.Add(row);
            }
            if (ModsConfig.IdeologyActive)
                foreach (var tree in map.listerThings.AllThings.Where(t => t.TryGetComp<CompTreeConnection>() != null))
                { var connection = tree.TryGetComp<CompTreeConnection>();
                    result.DryadTrees.Add(new SpecialistTreeDto { Id = tree.thingIDNumber,
                        ConnectedPawn = connection.ConnectedPawn?.thingIDNumber, Strength = connection.ConnectionStrength,
                        DesiredStrength = connection.DesiredConnectionStrength, MaxDryads = connection.MaxDryads,
                        Kind = connection.DryadKind.defName, PruningHours = connection.PruningHoursToMaintain(connection.DesiredConnectionStrength) }); }
            if (ModsConfig.AnomalyActive)
                foreach (var platform in map.listerThings.AllThings.OfType<Building_HoldingPlatform>().Where(t => t.Faction == Faction.OfPlayer && t.HeldPawn != null))
                {
                    var entity = platform.HeldPawn;
                    var activity = entity.TryGetComp<CompActivity>();
                    var target = entity.TryGetComp<CompHoldingPlatformTarget>();
                    var row = new SpecialistEntityDto { PlatformId = platform.thingIDNumber, EntityId = entity.thingIDNumber,
                        Name = entity.LabelShort, Activity = activity?.ActivityLevel ?? 0, SuppressionEnabled = activity?.suppressionEnabled == true,
                        SuppressAbove = activity?.suppressIfAbove ?? 0, ContainmentStrength = platform.GetStatValue(StatDefOf.ContainmentStrength),
                        MinimumStrength = entity.GetStatValue(StatDefOf.MinimumContainmentStrength), StudyFactor = activity?.ActivityResearchFactor ?? 1,
                        ContainmentMode = target?.containmentMode.ToString() };
                    foreach (var worker in map.mapPawns.FreeColonists)
                        if (SuppressionReady(worker, platform))
                            row.WorkerOptions.Add(new SpecialistWorkerDto { PawnId = worker.thingIDNumber, Name = worker.LabelShort,
                                Social = worker.skills?.GetSkill(SkillDefOf.Social)?.Level ?? 0,
                                SuppressionRate = worker.GetStatValue(StatDefOf.ActivitySuppressionRate) });
                    result.Entities.Add(row);
                }
            return ApiResult<SpecialistContextDto>.Ok(result);
        }
        public static ApiResult<CapabilityOrderResultDto> Execute(SpecialistOrderRequestDto request)
        {
            var map = MapHelper.GetMapByID(request.MapId);
            if (map == null) return ApiResult<CapabilityOrderResultDto>.Fail("Map not found.");
            var result = new CapabilityOrderResultDto { Reason = "selection_no_longer_feasible" };
            if (request.Kind == "mech_mode" && ModsConfig.BiotechActive && request.MechanitorId.HasValue && request.GroupIndex.HasValue)
            {
                var owner = MapHelper.GetThingOnMapById(request.MapId, request.MechanitorId.Value) as Pawn;
                var group = owner?.mechanitor?.controlGroups.FirstOrDefault(g => g.Index == request.GroupIndex.Value);
                if (owner?.Faction != Faction.OfPlayer || group == null || !Modes(owner, group, map).Contains(request.Value))
                    return ApiResult<CapabilityOrderResultDto>.Ok(result);
                group.SetWorkMode(DefDatabase<MechWorkModeDef>.GetNamed(request.Value));
                result.Applied = true; result.TargetId = owner.thingIDNumber; result.AffectedCount = group.MechsForReading.Count;
                result.Reason = "group_policy_set; normal_mech_jobs_required";
            }
            else if (request.Kind == "suppress" && ModsConfig.AnomalyActive && request.PlatformId.HasValue && request.WorkerId.HasValue)
            {
                var platform = MapHelper.GetThingOnMapById(request.MapId, request.PlatformId.Value) as Building_HoldingPlatform;
                var worker = MapHelper.GetThingOnMapById(request.MapId, request.WorkerId.Value) as Pawn;
                if (platform == null || platform.Faction != Faction.OfPlayer || worker == null) return ApiResult<CapabilityOrderResultDto>.Ok(result);
                var job = SuppressionJob(worker, platform);
                if (job != null && worker.jobs.TryTakeOrderedJob(job))
                { result.Applied = true; result.TargetId = platform.thingIDNumber; result.Reason = "normal_activity_suppression_job_assigned; not_completed"; }
            }
            return ApiResult<CapabilityOrderResultDto>.Ok(result);
        }
    }
}

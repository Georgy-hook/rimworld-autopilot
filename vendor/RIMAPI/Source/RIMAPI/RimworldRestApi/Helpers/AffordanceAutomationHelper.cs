using System;
using System.Collections.Generic;
using System.Linq;
using RIMAPI.Core;
using RimWorld;
using RimWorld.Planet;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    // Normal player affordances, generated from the loaded game. No debug gizmos,
    // arbitrary reflected methods or direct health/quest mutations are executed.
    public static class AffordanceAutomationHelper
    {
        private static readonly Dictionary<Type, bool> MenuCompTypes = new Dictionary<Type, bool>();
        private static readonly Dictionary<Type, bool> MenuThingTypes = new Dictionary<Type, bool>();
        private static IEnumerable<Command_Action> ScannerCommands(Building_SubcoreScanner scanner)
        {
            var labels=new[] { "SubcoreScannerStart".Translate().ToString(), "InsertPerson".Translate().ToString()+"...",
                "CommandCancelSubcoreScan".Translate().ToString(), "CommandCancelLoad".Translate().ToString() };
            return scanner.GetGizmos().OfType<Command_Action>().Where(c => !c.Disabled && c.action != null && labels.Contains(c.defaultLabel));
        }
        private static bool HasMenu(Thing t)
        {
            Type type = t.GetType();
            if (!MenuThingTypes.TryGetValue(type, out bool own))
            {
                Type declaring = type.GetMethod("GetFloatMenuOptions")?.DeclaringType;
                own = declaring != null && declaring != typeof(Thing) && declaring != typeof(ThingWithComps);
                MenuThingTypes[type] = own;
            }
            if (own) return true;
            if (!(t is ThingWithComps tc)) return false;
            return tc.AllComps.Any(c => {
                Type ct = c.GetType();
                if (!MenuCompTypes.TryGetValue(ct, out bool has))
                {
                    has = ct.GetMethod("CompFloatMenuOptions")?.DeclaringType != typeof(ThingComp);
                    MenuCompTypes[ct] = has;
                }
                return has;
            });
        }
        private static readonly HashSet<string> ProtectedCareJobs = new HashSet<string> {
            "BottleFeedBaby", "Breastfeed", "BreastfeedCarryToMom", "BringBabyToSafety", "BringBabyToSafetyUnforced",
            "CarryToMomAfterBirth", "BabySuckle", "BabyPlay", "PlayStatic", "PlayWalking", "PlayToys",
            "Lessonreceiving", "Lessongiving", "Deathrest"
        };
        internal static bool Eligible(Pawn p) => p.IsColonistPlayerControlled && !p.Dead && !p.Downed && !p.InMentalState
            && p.CurJobDef != JobDefOf.TendPatient && p.CurJobDef != JobDefOf.Rescue
            && p.CurJobDef != JobDefOf.FeedPatient && p.CurJobDef != JobDefOf.DoBill
            && !ProtectedCareJobs.Contains(p.CurJobDef?.defName ?? "");

        private static bool SafeInteraction(Pawn p, Thing t, List<Pawn> threats = null)
        {
            if (p.Drafted || t.IsForbidden(p)) return false;
            // Utility interactions must not pull a civilian into a hive, raid or an
            // exposed gas cell. Combat/rescue have their own explicit risk decisions.
            if (t.Map.gasGrid.DensityAt(t.Position, GasType.ToxGas) > 0
                || t.Map.gasGrid.DensityAt(t.Position, GasType.RotStink) > 0) return false;
            threats=threats ?? t.Map.mapPawns.AllPawnsSpawned.Where(h => !h.Dead && !h.Downed && h.HostileTo(p)).ToList();
            return !threats.Any(h => h.Position.DistanceTo(t.Position) < 30 || h.Position.DistanceTo(p.Position) < 20)
                && p.CanReach(t, PathEndMode.Touch, Danger.Some);
        }
        private static IEnumerable<FloatMenuOption> Menus(Pawn p, Thing t, List<Pawn> threats = null)
        {
            if (!Eligible(p) || !SafeInteraction(p,t,threats)) return Enumerable.Empty<FloatMenuOption>();
            return t.GetFloatMenuOptions(p).Where(o => o != null && !o.Disabled && o.action != null);
        }
        private static bool NeedsDestination(Ability a) =>
            a.CompOfType<CompAbilityEffect_WithDest>()?.Props.destination == AbilityEffectDestination.Selected;

        internal static bool CanUse(Ability a, LocalTargetInfo target)
        {
            if (!Eligible(a.pawn) || !a.CanQueueCast || a.def.targetWorldCell) return false;
            // Use the same native disabled/target validation as the player's gizmo.
            // An undrafted-only prohibition stays visible in the catalogue; normal
            // combat drafting makes the ability available on the next observation.
            if (a.GizmoDisabled(out _) || !a.CanApplyOn(target)) return false;
            if (a.def.targetRequired && (!a.verb.ValidateTarget(target,false)
                || !a.verb.verbProps.targetParams.CanTarget(target.ToTargetInfo(a.pawn.Map), a.verb))) return false;
            if (a.def.IsPsycast && a.pawn.psychicEntropy != null
                && (a.pawn.psychicEntropy.CurrentPsyfocus < a.FinalPsyfocusCost(target)
                    || a.pawn.psychicEntropy.WouldOverflowEntropy(a.def.EntropyGain))) return false;
            return true;
        }
        private static object PawnFacts(Pawn p) => new {
            pawn_id=p.thingIDNumber, name=p.LabelShort, health=p.health.summaryHealth.SummaryHealthPercent,
            downed=p.Downed, drafted=p.Drafted, job=p.CurJobDef?.defName,
            food=p.needs?.food?.CurLevelPercentage, mood=p.needs?.mood?.CurLevelPercentage,
            ideology=p.Ideo?.name, conditions=p.health.hediffSet.hediffs.Where(h => h.Visible).Select(h => new {
                def_name=h.def.defName, severity=h.Severity, part=h.Part?.Label }).ToList(),
            skills=p.skills?.skills.Select(s => new { name=s.def.defName, level=s.Level }).ToList()
        };

        public static ApiResult<object> Context(int mapId)
        {
            Map map=MapHelper.GetMapByID(mapId);
            if (map == null) return ApiResult<object>.Fail("Map not found.");
            var pawns=map.mapPawns.FreeColonistsSpawned.Where(Eligible).ToList();
            var pawnFacts=pawns.ToDictionary(p => p.thingIDNumber,PawnFacts);
            var threats=map.mapPawns.AllPawnsSpawned.Where(h => !h.Dead && !h.Downed && h.HostileTo(Faction.OfPlayer)).ToList();
            var abilities=new List<object>();
            var options=new List<object>();
            foreach (Pawn p in pawns)
                foreach (Ability a in p.abilities?.AllAbilitiesForReading ?? new List<Ability>())
                {
                    bool disabled=a.GizmoDisabled(out string reason);
                    abilities.Add(new { pawn_id=p.thingIDNumber, def_name=a.def.defName, label=a.def.LabelCap.ToString(),
                        description=a.def.description, content=a.def.modContentPack?.Name, disabled, reason,
                        hostile=a.def.hostile, psyfocus=a.def.PsyfocusCost, heat=a.def.EntropyGain,
                        cooldown=a.CooldownTicksRemaining, charges=a.UsesCharges ? a.RemainingCharges : -1,
                        radius=a.def.EffectRadius, range=a.verb?.verbProps.range, needs_destination=NeedsDestination(a),
                        world_target=a.def.targetWorldCell, effects=a.EffectComps.Select(c => c.GetType().Name).ToList() });
                    if (disabled) continue;
                    // One purpose/worker choice; targeting is a separate native
                    // stage. Avoid an abilities × all map things scan here.
                    foreach (Thing t in new[] { p })
                    {
                        LocalTargetInfo target=t;
                        if (!a.CanQueueCast || (!a.def.targetRequired && !CanUse(a,target))) continue;
                        options.Add(new { key=$"ability:{p.thingIDNumber}:{a.def.defName}:{t.thingIDNumber}", kind="ability",
                            pawn_id=p.thingIDNumber, target_id=t.thingIDNumber, ability=a.def.defName,
                            label=a.def.LabelCap.ToString(), description=a.def.description,
                            target=a.def.targetRequired ? "Choose native target next" : t.LabelCap.ToString(), target_def=t.def.defName,
                            pawn=pawnFacts[p.thingIDNumber], target_pawn=a.def.targetRequired ? null : pawnFacts[p.thingIDNumber],
                            hostile=a.def.hostile, target_hostile=t.HostileTo(p),
                            cost=new { psyfocus=a.def.PsyfocusCost, heat=a.def.EntropyGain,
                                cooldown=a.def.cooldownTicksRange.ToString(), charges=a.UsesCharges },
                            affected_allies=a.def.targetRequired ? -1 : map.mapPawns.AllPawnsSpawned.Count(q => !q.HostileTo(p)
                                && q.Position.DistanceTo(t.Position) <= a.def.EffectRadius),
                            risk="Use the native effect description: side effects, ideology, friendly area effects and charges matter. A valid target is not proof this helps.",
                            inspect=t.GetInspectString() });
                    }
                }
            var targetsWithMenus=map.listerThings.AllThings.Where(t => t.Spawned && t.def.category != ThingCategory.Mote
                && !(t is Pawn) && HasMenu(t)).ToList();
            foreach (Thing t in targetsWithMenus)
                foreach (Pawn p in pawns)
                    foreach (FloatMenuOption menu in Menus(p,t,threats))
                        options.Add(new { key=$"menu:{p.thingIDNumber}:{t.thingIDNumber}:{menu.Label}", kind="menu",
                            pawn_id=p.thingIDNumber, target_id=t.thingIDNumber, label=menu.Label,
                            target=t.LabelCap.ToString(), target_def=t.def.defName,
                            description=menu.Label+"; "+(menu.tooltip?.text ?? t.def.description), inspect=t.GetInspectString(), pawn=pawnFacts[p.thingIDNumber],
                            content=t.def.modContentPack?.Name,
                            risk=(t is Building_SubcoreScanner scanner && scanner.DestroyOccupantBrain ? "Lethal ripscan destroys the selected person's brain. " : "")
                                + (t.TryGetComp<CompBiosculpterPod>() != null ? "Biosculpting takes the selected pawn away for the full cycle; needs nutrition and power. " : "")
                                + (t.def.defName.Contains("GeneExtractor") ? "Gene extraction has recovery and regrowth constraints; inspect donor health. " : "")
                                + "Native job/menu uses labor/resources; acceptance is not completion." });
            foreach (var scanner in map.listerBuildings.allBuildingsColonist.OfType<Building_SubcoreScanner>())
                foreach (var command in ScannerCommands(scanner))
                    options.Add(new { key=$"scanner:{scanner.thingIDNumber}:{command.defaultLabel}",kind="scanner",
                        pawn_id=0,target_id=scanner.thingIDNumber,label=command.defaultLabel,target=scanner.LabelCap.ToString(),
                        target_def=scanner.def.defName, description=command.defaultDesc, inspect=scanner.GetInspectString(),
                        cost=$"Scan ticks {scanner.def.building.subcoreScannerTicks}; {string.Join("; ",scanner.def.building.subcoreScannerFixedIngredients.Select(i => i.Summary))}",
                        risk=scanner.DestroyOccupantBrain ? "LETHAL: destroys occupant brain. Cancelling an occupied ripscan also kills; native confirmation remains mandatory."
                            : "Occupies a selected person; brain scan consumes time and ingredients and has native health consequences." });
            return ApiResult<object>.Ok(new { available=true, abilities, options, target_count=targetsWithMenus.Count,
                missing_adapters=abilities.Count == 0 ? "No learned abilities on available colonists." :
                "Destination and world-target casts require separate destination selection; unavailable casts are catalogued." });
        }

        public static ApiResult<object> Execute(int mapId, string kind, int pawnId, int targetId, string abilityDef, string label)
        {
            Map map=MapHelper.GetMapByID(mapId);
            Pawn p=map?.mapPawns.FreeColonistsSpawned.FirstOrDefault(x => x.thingIDNumber == pawnId);
            Thing t=map?.listerThings.AllThings.FirstOrDefault(x => x.thingIDNumber == targetId && x.Spawned);
            if (kind == "scanner" && t is Building_SubcoreScanner scanner && scanner.Faction == Faction.OfPlayer)
            {
                var commands=ScannerCommands(scanner).Where(c => c.defaultLabel == label).ToList();
                if (commands.Count != 1) return ApiResult<object>.Ok(new { applied=false,reason="scanner_command_changed" });
                commands[0].action();
                return ApiResult<object>.Ok(new { applied=true,reason="native_scanner_command",completion="unverified" });
            }
            if (p == null || t == null || !Eligible(p)) return ApiResult<object>.Ok(new { applied=false, reason="stale_subject" });
            if (kind == "menu")
            {
                var menus=Menus(p,t).Where(m => m.Label == label).ToList();
                if (menus.Count != 1) return ApiResult<object>.Ok(new { applied=false, reason="menu_changed" });
                var before=p.CurJob; int windows=Find.WindowStack.Windows.Count;
                menus[0].action();
                return ApiResult<object>.Ok(new { applied=true, reason="native_menu_invoked", completion="unverified",
                    job_changed=before != p.CurJob, choice_opened=windows != Find.WindowStack.Windows.Count });
            }
            if (kind == "ability")
            {
                Ability a=p.abilities?.AllAbilitiesForReading.FirstOrDefault(x => x.def.defName == abilityDef);
                if (a == null || !a.CanQueueCast || a.GizmoDisabled(out _)
                    || (!a.def.targetRequired && !CanUse(a,t))) return ApiResult<object>.Ok(new { applied=false, reason="cast_changed" });
                var before=p.CurJob; int windows=Find.WindowStack.Windows.Count;
                if (a.def.targetWorldCell)
                {
                    CameraJumper.TryJump(CameraJumper.GetWorldTarget(p));
                    Find.WorldTargeter.BeginTargeting(delegate(GlobalTargetInfo destination) {
                        if (!a.ValidateGlobalTarget(destination)) return false;
                        a.QueueCastingJob(destination); return true;
                    }, true, a.def.uiIcon, !p.IsCaravanMember(), null, a.WorldMapExtraLabel, a.ValidateGlobalTarget);
                    return ApiResult<object>.Ok(new { applied=true,reason="choose_native_world_target",completion="unverified" });
                }
                if (a.def.targetRequired)
                {
                    Find.Targeter.BeginTargeting(a.verb,allowNonSelectedTargetingSource:true);
                    return ApiResult<object>.Ok(new { applied=true,reason="choose_native_target",completion="unverified" });
                }
                a.QueueCastingJob(t, LocalTargetInfo.Invalid);
                bool accepted=before != p.CurJob || windows != Find.WindowStack.Windows.Count
                    || a.verb.WarmingUp || a.CooldownTicksRemaining > 0;
                return ApiResult<object>.Ok(new { applied=accepted, reason=accepted ? "cast_or_confirmation_queued" : "cast_unconfirmed",
                    completion="unverified" });
            }
            return ApiResult<object>.Ok(new { applied=false, reason="unknown_kind" });
        }
    }
}

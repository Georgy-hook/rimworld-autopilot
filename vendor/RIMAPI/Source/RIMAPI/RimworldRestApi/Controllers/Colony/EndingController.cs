using System.Collections.Generic;
using System.Diagnostics;
using System.Reflection;
using System.Linq;
using System.Net;
using System.Threading.Tasks;
using HarmonyLib;
using RIMAPI.Core;
using RIMAPI.Helpers;
using RIMAPI.Http;
using RIMAPI.Models;
using RimWorld;
using Verse;

namespace RIMAPI.Controllers
{
    // Records only the engine's actual victory credits, never inferred from a countdown.
    public class EndingEvidence : GameComponent
    {
        public string CampaignId = System.Guid.NewGuid().ToString("N");
        public string Route;
        public string Text;
        public int Tick = -1;
        public bool ExitsToMainMenu;
        public bool RoyalCountdown;
        public EndingEvidence(Game game) { }
        public override void ExposeData() {
            Scribe_Values.Look(ref CampaignId, "layaCampaignId");
            if (Scribe.mode == LoadSaveMode.PostLoadInit && string.IsNullOrEmpty(CampaignId)) CampaignId = System.Guid.NewGuid().ToString("N");
            Scribe_Values.Look(ref Route, "layaEndingRoute");
            Scribe_Values.Look(ref Text, "layaEndingText");
            Scribe_Values.Look(ref Tick, "layaEndingTick", -1);
            Scribe_Values.Look(ref ExitsToMainMenu, "layaEndingTerminal");
            Scribe_Values.Look(ref RoyalCountdown, "layaRoyalCountdown");
        }
    }
    [HarmonyPatch(typeof(GameVictoryUtility), nameof(GameVictoryUtility.ShowCredits))]
    public static class EndingCreditsHook
    {
        public static string ActiveNativeSource;
        public static void Postfix(string victoryText, bool exitToMainMenu) {
            var evidence = Current.Game?.GetComponent<EndingEvidence>();
            if (evidence == null) return;
            evidence.Tick = Find.TickManager.TicksGame;
            evidence.Text = victoryText;
            evidence.ExitsToMainMenu = exitToMainMenu;
            // The native credits text is kept as authoritative evidence. Route attribution
            // is a convenience and is deliberately unknown when a translated string differs.
            string callers = new StackTrace().ToString();
            evidence.Route = ActiveNativeSource ?? (callers.Contains("VoidAwakeningUtility") ? "anomaly_void" :
                callers.Contains("ArchonexusCountdown") ? "archonexus" :
                callers.Contains("CompCerebrexCore") ? "odyssey_mechhive" :
                callers.Contains("ShipCountdown") ? (evidence.Route == "royal_ascent" ? evidence.Route : "ship_escape") : "native_credits");
        }
    }
    // Scoped native caller hooks provide route attribution even when release builds
    // inline caller frames. They observe calls; no source routine is ever invoked here.
    [HarmonyPatch]
    public static class EndingNativeSourceHook
    {
        public static IEnumerable<MethodBase> TargetMethods() {
            foreach (var pair in new[] {
                new[] { "RimWorld.ShipCountdown", "CountdownEnded" },
                new[] { "RimWorld.ArchonexusCountdown", "EndGame" },
                new[] { "RimWorld.Utility.VoidAwakeningUtility", "EmbraceTheVoid" },
                new[] { "RimWorld.Utility.VoidAwakeningUtility", "DisruptTheLink" },
                new[] { "RimWorld.CompCerebrexCore", "DeactivateCore" } }) {
                var method = AccessTools.Method(AccessTools.TypeByName(pair[0]), pair[1]);
                if (method != null) yield return method;
            }
        }
        public static void Prefix(MethodBase __originalMethod, out string __state) {
            __state = EndingCreditsHook.ActiveNativeSource;
            string type = __originalMethod.DeclaringType.Name;
            EndingCreditsHook.ActiveNativeSource = type == "CompCerebrexCore" ? "odyssey_mechhive" : type == "ArchonexusCountdown" ? "archonexus" :
                type == "VoidAwakeningUtility" ? "anomaly_void" : Current.Game?.GetComponent<EndingEvidence>()?.RoyalCountdown == true ? "royal_ascent" : "ship_escape";
        }
        public static System.Exception Finalizer(System.Exception __exception, string __state) { EndingCreditsHook.ActiveNativeSource = __state; return __exception; }
    }
    [HarmonyPatch(typeof(QuestPart_EndGame), nameof(QuestPart_EndGame.Notify_QuestSignalReceived))]
    public static class EndingRoyalCountdownHook
    {
        public static void Prefix(out bool __state) { __state = !ShipCountdown.CountingDown; }
        public static void Postfix(QuestPart_EndGame __instance, Signal signal, bool __state) {
            if (!__state || signal.tag != __instance.inSignal || !ShipCountdown.CountingDown) return;
            var evidence = Current.Game?.GetComponent<EndingEvidence>();
            if (evidence != null) evidence.RoyalCountdown = __instance.quest?.root?.defName == "EndGame_RoyalAscent";
        }
    }
    [HarmonyPatch(typeof(ShipCountdown), nameof(ShipCountdown.InitiateCountdown), new[] { typeof(Building) })]
    public static class EndingShipCountdownHook
    {
        public static void Prefix() { var evidence = Current.Game?.GetComponent<EndingEvidence>(); if (evidence != null) evidence.RoyalCountdown = false; }
    }
    public class EndingController
    {
        private static bool EndingQuest(Quest q) => q.root != null &&
            (q.root.defName.StartsWith("EndGame_") || q.root.defName.Contains("VoidMonolith") || q.root.defName.Contains("Gravship") || q.root.defName.Contains("Mechhive"));
        private static IEnumerable<Thing> Sites() => Find.Maps.SelectMany(m => m.listerThings.AllThings)
            .Where(t => t.Spawned && (t is Building_ArchonexusCore || t is Building_VoidMonolith || t.def.defName.Contains("VoidStructure") || t.def.defName == "VoidNode" || t.def.defName.Contains("Mechhive") || t.TryGetComp<CompCerebrexCore>() != null));
        private static IEnumerable<FloatMenuOption> Options(Thing thing, Pawn pawn) => thing is Building_ArchonexusCore core
            ? core.GetMultiSelectFloatMenuOptions(new[] { pawn }) : thing.GetFloatMenuOptions(pawn);

        [Get("/api/v1/colony/endings")]
        [EndpointMetadata("Read DLC ending quests, native site jobs, live requirements and verified engine credits")]
        public async Task Context(HttpListenerContext context) {
            // The queue invokes GET handlers synchronously on Unity's thread up to their first await.
            // Reject a future off-thread caller rather than copying a concurrently changing game list.
            if (!UnityData.IsInMainThread || Current.ProgramState != ProgramState.Playing || Current.Game == null) {
                await context.SendJsonResponse(ApiResult<object>.Fail("ending_context_game_read_unavailable")); return;
            }
            var evidence = Current.Game.GetComponent<EndingEvidence>();
            var maps = EndingReadBoundary.Capture(() => Find.Maps);
            var pawnSnapshots = maps.ToDictionary(m => m, m => EndingReadBoundary.Capture(() => m.mapPawns.FreeColonistsSpawned));
            var pawnLabels = pawnSnapshots.ToDictionary(pair => pair.Key,
                pair => EndingReadBoundary.Project(pair.Value, p => p.LabelShortCap.ToString()));
            var hostileCounts = maps.ToDictionary(m => m, m => EndingReadBoundary.Capture(() => m.mapPawns.AllPawnsSpawned)
                .Count(p => p.HostileTo(Faction.OfPlayer) && !p.Dead));
            var siteSnapshots = maps.ToDictionary(m => m, m => EndingReadBoundary.Capture(() => m.listerThings.AllThings)
                .Where(t => t.Spawned && (t is Building_ArchonexusCore || t is Building_VoidMonolith
                    || t.def.defName.Contains("VoidStructure") || t.def.defName == "VoidNode"
                    || t.def.defName.Contains("Mechhive") || t.TryGetComp<CompCerebrexCore>() != null)).ToArray());
            var questSnapshot = EndingReadBoundary.Capture(() => Find.QuestManager.QuestsListForReading)
                .Where(q => !q.hidden && !q.hiddenInUI && EndingQuest(q)).ToArray();
            var allAccepters = pawnSnapshots.Values.SelectMany(p => p).ToArray();
            var quests = EndingReadBoundary.Project(questSnapshot, q => {
                var parts = EndingReadBoundary.Capture(() => q.PartsListForReading);
                var targets = EndingReadBoundary.Capture(() => q.QuestLookTargets);
                var acceptance = QuestUtility.CanAcceptQuest(q);
                return new {
                    quest_id = q.id, route = q.root.defName, label = q.name, description = q.description.ToString(),
                    state = q.State.ToString(), expires_in_ticks = q.TicksUntilExpiry,
                    requires_accepter = q.RequiresAccepter, acceptance = acceptance.Reason,
                    can_accept = q.State == QuestState.NotYetAccepted && acceptance.Accepted,
                    quest_offer = GameEventAutomationHelper.ToQuestDto(q),
                    accepter_ids = allAccepters.Where(p => QuestUtility.CanPawnAcceptQuest(p, q)).Select(p => p.thingIDNumber).ToArray(),
                    targets = targets.Select(t => t.ToString()).ToArray(), part_types = parts.Select(p => p.GetType().Name).Distinct().ToArray()
                };
            });
            var jobs = new List<object>();
            var blockers = new List<object>();
            foreach (var map in maps) foreach (var site in siteSnapshots[map])
            foreach (var pawn in pawnSnapshots[map].Where(p => !SpecialistNativeSafety.Protected(p))) {
                // Generate the native preview once. Never enumerate a live pawn getter around these callbacks.
                var options = EndingReadBoundary.Capture(() => Options(site, pawn));
                var inspect = site.GetInspectString();
                foreach (var option in options) {
                    if (option.Disabled || option.action == null)
                        blockers.Add(new { map_id = map.uniqueID, thing_id = site.thingIDNumber, pawn_id = pawn.thingIDNumber,
                            site = site.def.defName, label = option.Label, inspect });
                    else
                        jobs.Add(new { map_id = map.uniqueID, thing_id = site.thingIDNumber, pawn_id = pawn.thingIDNumber,
                            label = option.Label, site = site.def.defName, pawn = pawn.LabelShortCap.ToString(), inspect,
                            current_job = pawn.CurJob?.def.defName, hostile_pawns = hostileCounts[map], colonists = pawnLabels[map] });
                }
            }
            await context.SendJsonResponse(ApiResult<object>.Ok(new {
                royalty = ModsConfig.RoyaltyActive, ideology = ModsConfig.IdeologyActive,
                biotech = ModsConfig.BiotechActive, anomaly = ModsConfig.AnomalyActive, odyssey = ModsConfig.OdysseyActive,
                quests, site_jobs = jobs, site_blockers = blockers, ship_countdown = ShipCountdown.CountingDown,
                archonexus_countdown = ArchonexusCountdown.CountdownActivated,
                victory_verified = evidence != null && evidence.Tick >= 0,
                ending_tick = evidence?.Tick ?? -1, ending_route = evidence?.Route,
                ending_text = evidence?.Text, exits_to_main_menu = evidence?.ExitsToMainMenu ?? false,
                anomaly_level = ModsConfig.AnomalyActive ? Find.Anomaly.Level : -1,
                support_research_targets = new Dictionary<string, List<string>> {
                    // These are native infrastructure unlocks, not claims that every
                    // such technology is a mandatory victory gate.
                    { "royal_ascent", ResearchFor(d => ModsConfig.RoyaltyActive && d.comps != null && d.comps.Any(c => c.compClass?.Name == "CompAssignableToPawn_Throne")) },
                    { "archonexus", new List<string>() },
                    { "anomaly_void", ResearchFor(d => ModsConfig.AnomalyActive && d.thingClass != null && typeof(Building_HoldingPlatform).IsAssignableFrom(d.thingClass)) },
                    { "odyssey_mechhive", ResearchFor(d => ModsConfig.OdysseyActive && (d.thingClass == typeof(Building_GravEngine) || d.comps != null && d.comps.Any(c => c.compClass != null && typeof(CompGravshipFacility).IsAssignableFrom(c.compClass)))) }
                },
                research_gate_note = "Royal Ascent requires honor/title and hospitality, Archonexus requires native cycle wealth/study/faction gates, and monolith advancement checks native entity discoveries and active-condition restrictions. Infrastructure research targets are supporting options, never substitute proof of those gates."
            }));
        }
        private static List<string> ResearchFor(System.Func<ThingDef, bool> filter) => DefDatabase<ThingDef>.AllDefsListForReading.Where(filter)
            .SelectMany(d => d.researchPrerequisites ?? new List<ResearchProjectDef>()).Select(r => r.defName).Distinct().ToList();
        [Post("/api/v1/colony/endings/accept")]
        [EndpointMetadata("Accept an offered ending quest using native requirements and eligible accepter; never generates or completes quests")]
        public async Task Accept(HttpListenerContext context) {
            int id = RequestParser.GetIntParameter(context, "quest_id"), pawnId = RequestParser.GetIntParameter(context, "pawn_id");
            var quest = Find.QuestManager.QuestsListForReading.FirstOrDefault(q => q.id == id && EndingQuest(q));
            var pawn = PawnsFinder.AllMaps_FreeColonistsSpawned.FirstOrDefault(p => p.thingIDNumber == pawnId);
            if (!RequestParser.GetBooleanParameter(context, "confirmed") || quest == null || quest.State != QuestState.NotYetAccepted ||
                !QuestUtility.CanAcceptQuest(quest).Accepted || (quest.RequiresAccepter && (pawn == null || !QuestUtility.CanPawnAcceptQuest(pawn, quest)))) {
                await context.SendJsonResponse(ApiResult<string>.Fail("Ending quest conditions changed or unconfirmed")); return;
            }
            // Same review/version/reward guard as ordinary quests; ending routes
            // cannot bypass it through a second acceptance endpoint.
            var body = await context.Request.ReadBodyAsync<QuestActionRequestDto>();
            if (body == null || body.QuestId != id || body.AccepterPawnId.GetValueOrDefault() != pawnId) {
                await context.SendJsonResponse(ApiResult<string>.Fail("quest_offer_review_required")); return;
            }
            var result = GameEventAutomationHelper.AcceptQuest(body);
            if (!result.Success) {
                await context.SendJsonResponse(ApiResult<string>.Fail(string.Join("; ", result.Errors))); return;
            }
            await context.SendJsonResponse(ApiResult<string>.Ok("ending_quest_accepted"));
        }
        [Post("/api/v1/colony/endings/job")]
        [EndpointMetadata("Invoke one freshly regenerated ordinary ending site float-menu action; may open an explicit native choice dialog")]
        public async Task Job(HttpListenerContext context) {
            int mapId = RequestParser.GetIntParameter(context, "map_id"), thingId = RequestParser.GetIntParameter(context, "thing_id"), pawnId = RequestParser.GetIntParameter(context, "pawn_id");
            string label = RequestParser.GetStringParameter(context, "label");
            var site = Sites().FirstOrDefault(t => t.Map.uniqueID == mapId && t.thingIDNumber == thingId);
            var pawn = site?.Map.mapPawns.FreeColonistsSpawned.FirstOrDefault(p => p.thingIDNumber == pawnId && !SpecialistNativeSafety.Protected(p));
            var option = pawn == null ? null : Options(site, pawn).FirstOrDefault(o => o.Label == label && !o.Disabled && o.action != null);
            if (!RequestParser.GetBooleanParameter(context, "confirmed") || option == null) {
                await context.SendJsonResponse(ApiResult<string>.Fail("Ending site option changed or unconfirmed")); return;
            }
            option.action();
            await context.SendJsonResponse(ApiResult<string>.Ok("ending_native_action_requested"));
        }
    }
}

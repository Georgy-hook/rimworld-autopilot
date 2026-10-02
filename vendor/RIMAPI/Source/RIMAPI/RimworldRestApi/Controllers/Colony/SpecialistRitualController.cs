using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Threading.Tasks;
using HarmonyLib;
using RIMAPI.Core;
using RIMAPI.Helpers;
using RIMAPI.Http;
using RimWorld;
using UnityEngine;
using Verse;
using Verse.AI.Group;

namespace RIMAPI.Controllers
{
    public class SpecialistRitualController
    {
        private static T Field<T>(object target, string name) => (T)AccessTools.Field(target.GetType(), name).GetValue(target);
        private static Dialog_BeginLordJob Dialog => Find.WindowStack.Windows.OfType<Dialog_BeginLordJob>().FirstOrDefault();
        private static IEnumerable<Command> Commands(Thing thing) {
            foreach (var command in thing.GetGizmos().OfType<Command_Ritual>()) yield return command;
            var psychic = thing.TryGetComp<CompPsychicRitualSpot>();
            if (psychic != null && psychic.GetPsychicRitual() == null)
                foreach (var command in psychic.CompGetGizmosExtra().OfType<Command>()) yield return command;
        }
        [Get("/api/v1/specialists/rituals")]
        [EndpointMetadata("Read native Ideology and Anomaly ritual commands, participant assignments, role changes and live start blockers")]
        public async Task Context(HttpListenerContext context) {
            var dialog = Dialog; int mapId=RequestParser.GetMapId(context);
            var choices = new List<object>();
            var starts = new List<object>();
            if (dialog == null) foreach (var map in Find.Maps.Where(m=>m.uniqueID==mapId)) foreach (var thing in map.listerThings.AllThings.Where(t => (t.Faction == Faction.OfPlayer && (t is Building || t is Pawn) || t.Spawned && !t.Position.Fogged(t.Map) && t.TryGetComp<CompTreeConnection>() != null)))
                foreach (var command in Commands(thing).Where(c => !c.Disabled && !c.defaultLabel.StartsWith("DEV")))
                    starts.Add(new { map_id = map.uniqueID, thing_id = thing.thingIDNumber, label = command.defaultLabel,
                        description = command.Desc, inspect = thing.GetInspectString() });
            if (dialog is Dialog_BeginRitual ordinary) {
                var assignments = Field<RitualRoleAssignments>(ordinary, "assignments");
                var target = Field<TargetInfo>(ordinary, "target");
                foreach (var role in assignments.AllRolesForReading)
                    foreach (var pawn in assignments.CandidatesForRole(role, target, true, true).Where(p => !assignments.Forced(p) && assignments.RoleForPawn(p)!=role && !SpecialistNativeSafety.Protected(p)))
                        choices.Add(new { operation = "assign", role_id = role.id, pawn_id = pawn.thingIDNumber,
                            label = pawn.LabelShortCap + " → " + role.Label, assigned = assignments.RoleForPawn(pawn)?.id,
                            pawn_job = pawn.CurJob?.def.defName, pawn_health = pawn.health.summaryHealth.SummaryHealthPercent });
                foreach (var pawn in assignments.Participants.Where(p => !assignments.Forced(p) && assignments.RoleForPawn(p)!=null))
                    choices.Add(new { operation = "remove", pawn_id = pawn.thingIDNumber, label = "Remove " + pawn.LabelShortCap });
                foreach (var pawn in assignments.SpectatorCandidates().Where(p => !assignments.SpectatorsForReading.Contains(p) && !assignments.Forced(p) && !SpecialistNativeSafety.Protected(p)))
                    choices.Add(new { operation = "spectate", pawn_id = pawn.thingIDNumber, label = "Spectate: " + pawn.LabelShortCap });
                var changer = assignments.AllRolesForReading.OfType<RitualRoleIdeoRoleChanger>().Select(r => assignments.FirstAssignedPawn(r)).FirstOrDefault(p => p != null);
                foreach (var role in changer == null ? Enumerable.Empty<Precept_Role>() : RitualUtility.AllRolesForPawn(changer).Where(r => r.Active && r.RequirementsMet(changer)))
                    choices.Add(new { operation = "role", role_id = role.def.defName, label = role.LabelCap.ToString(),
                        disabled_work = role.DisabledWorkTypes.Select(w => w.defName).ToList(), apparel = role.apparelRequirements?.Select(a => a.ToString()).ToList() });
            }
            if (dialog is Dialog_BeginPsychicRitual psychicDialog) {
                var assignments = Field<PsychicRitualRoleAssignments>(psychicDialog, "assignments");
                var def = Field<PsychicRitualDef>(psychicDialog, "psychicRitualDef");
                foreach (var role in def.Roles) foreach (var pawn in def.FindCandidatePool().AllCandidatePawns)
                    if (assignments.ForcedRole(pawn) == null && assignments.RoleForPawn(pawn)!=role && !SpecialistNativeSafety.Protected(pawn) && assignments.PawnNotAssignableReason(pawn, role).NullOrEmpty())
                        choices.Add(new { operation = "assign", role_id = role.defName, pawn_id = pawn.thingIDNumber,
                            label = pawn.LabelShortCap + " → " + role.LabelCap, pawn_job = pawn.CurJob?.def.defName,
                            pawn_health = pawn.health.summaryHealth.SummaryHealthPercent });
                foreach (var pawn in assignments.AllAssignedPawns.Where(p => assignments.ForcedRole(p) == null))
                    choices.Add(new { operation = "remove", pawn_id = pawn.thingIDNumber, label = "Remove " + pawn.LabelShortCap });
            }
            if (dialog is Dialog_BeginGravshipLaunch launchDialog)
                foreach (string policy in new[] { "forceVisitorsToLeave", "boardColonyAnimals", "boardColonyMechs" }) {
                    if (policy == "boardColonyMechs" && !ModsConfig.BiotechActive) continue;
                    bool value = Field<bool>(launchDialog, policy);
                    choices.Add(new { operation = "policy", policy, value = !value, label = policy + " → " + (!value),
                        consequence = "Explicit gravship passenger/visitor boarding policy; omitted animals/mechs or visitors may be left behind." });
                }
            var blockers = dialog == null ? new List<string>() : ((IEnumerable<string>)AccessTools.Method(dialog.GetType(), "BlockingIssues").Invoke(dialog, null))?.ToList();
            object quality = null;
            if (dialog != null) {
                object[] args = { new FloatRange() };
                AccessTools.Method(dialog.GetType(), "PopulateQualityFactors").Invoke(dialog, args);
                var range = (FloatRange)args[0];
                quality = new { minimum = range.min, maximum = range.max, duration = dialog.ExpectedDurationLabel(range).ToString() };
            }
            await context.SendJsonResponse(ApiResult<object>.Ok(new { available = ModsConfig.IdeologyActive || ModsConfig.AnomalyActive,
                configuring = dialog != null, session_id=SpecialistWindowSessionHelper.Token(dialog),
                map_id=dialog==null ? mapId : Field<Map>(dialog,"map").uniqueID, configuration=Configuration(dialog), label = dialog?.HeaderLabel.ToString(), description = dialog?.DescriptionLabel.ToString(),
                can_begin = (dialog?.CanBegin ?? false) && !ParticipantsProtected(dialog), blockers, quality, commands = starts, choices,
                warning = "Ritual assignments may remove doctors, defenders and workers from current jobs. Quality and psychic power are uncertain, offerings consumed and some target effects irreversible. Explicit native confirmation remains required." }));
        }
        [Post("/api/v1/specialists/rituals")]
        [EndpointMetadata("Open or configure a native ritual, or invoke its normal Begin handler after live CanBegin validation")]
        public async Task Act(HttpListenerContext context) {
            if (!RequestParser.GetBooleanParameter(context, "confirmed")) { await context.SendJsonResponse(ApiResult<string>.Fail("Unconfirmed ritual decision")); return; }
            string operation = RequestParser.GetStringParameter(context, "operation");
            var dialog = Dialog;
            if (operation == "open" && dialog == null) {
                int map = RequestParser.GetIntParameter(context, "map_id"), id = RequestParser.GetIntParameter(context, "thing_id");
                string label = RequestParser.GetStringParameter(context, "label");
                var thing = Find.Maps.FirstOrDefault(m => m.uniqueID == map)?.listerThings.AllThings.FirstOrDefault(t => t.thingIDNumber == id && (t.Faction == Faction.OfPlayer || t.Spawned && !t.Position.Fogged(t.Map) && t.TryGetComp<CompTreeConnection>() != null));
                var command = thing == null ? null : Commands(thing).FirstOrDefault(c => c.defaultLabel == label && !c.Disabled && !c.defaultLabel.StartsWith("DEV"));
                if (command != null) { command.ProcessInput(new Event()); await context.SendJsonResponse(ApiResult<string>.Ok("ritual_native_command_requested")); return; }
            }
            if (dialog == null) { await context.SendJsonResponse(ApiResult<string>.Fail("Ritual stage changed")); return; }
            if(!SpecialistWindowSessionHelper.Matches(dialog,context)) { await context.SendJsonResponse(ApiResult<string>.Fail("Ritual dialog session changed"));return; }
            if (operation == "cancel") {
                AccessTools.Method(dialog.GetType(), "Cancel").Invoke(dialog, null);
                await context.SendJsonResponse(ApiResult<string>.Ok("ritual_cancelled")); return;
            }
            if (operation == "begin" && dialog.CanBegin && !ParticipantsProtected(dialog)) {
                AccessTools.Method(dialog.GetType(), "Start").Invoke(dialog, null);
                await context.SendJsonResponse(ApiResult<string>.Ok("ritual_begin_requested")); return;
            }
            int pawnId = new[]{"assign","remove","spectate"}.Contains(operation) ? RequestParser.GetIntParameter(context, "pawn_id") : -1;
            string roleId = operation=="assign" || operation=="role" ? RequestParser.GetStringParameter(context, "role_id") : null;
            bool applied = false;
            if (operation == "policy" && dialog is Dialog_BeginGravshipLaunch launchDialog) {
                string policy = RequestParser.GetStringParameter(context, "policy");
                if (new[] { "forceVisitorsToLeave", "boardColonyAnimals", "boardColonyMechs" }.Contains(policy) && (policy != "boardColonyMechs" || ModsConfig.BiotechActive)) {
                    if(!bool.TryParse(RequestParser.GetStringParameter(context,"value"),out bool desired)) { await context.SendJsonResponse(ApiResult<string>.Fail("Explicit boarding boolean required"));return; }
                    AccessTools.Field(typeof(Dialog_BeginGravshipLaunch), policy).SetValue(launchDialog, desired);
                    applied = true;
                }
            }
            if (dialog is Dialog_BeginRitual ordinary) {
                var assignments = Field<RitualRoleAssignments>(ordinary, "assignments");
                var pawn = assignments.AllCandidatePawns.FirstOrDefault(p => p.thingIDNumber == pawnId);
                if (operation == "remove" && pawn != null && !assignments.Forced(pawn)) applied = assignments.TryUnassignAnyRole(pawn);
                if (operation == "spectate" && pawn != null && !assignments.Forced(pawn) && !assignments.SpectatorsForReading.Contains(pawn) && !SpecialistNativeSafety.Protected(pawn)) applied = assignments.TryAssignSpectate(pawn);
                if (operation == "assign" && pawn != null) {
                    var role = assignments.GetRole(roleId);
                    if (role != null && assignments.RoleForPawn(pawn)!=role && !assignments.Forced(pawn) && !SpecialistNativeSafety.Protected(pawn)) applied = assignments.TryAssign(pawn, role, out var reason);
                }
                if (operation == "role") {
                    var changer = assignments.AllRolesForReading.OfType<RitualRoleIdeoRoleChanger>().Select(r => assignments.FirstAssignedPawn(r)).FirstOrDefault(p => p != null);
                    var role = changer == null ? null : RitualUtility.AllRolesForPawn(changer).FirstOrDefault(r => r.def.defName == roleId && r.Active && r.RequirementsMet(changer));
                    if (role != null) { ordinary.SetRoleToChangeTo(role); applied = true; }
                }
            } else if (dialog is Dialog_BeginPsychicRitual psychic) {
                var assignments = Field<PsychicRitualRoleAssignments>(psychic, "assignments");
                var def = Field<PsychicRitualDef>(psychic, "psychicRitualDef");
                var pawn = def.FindCandidatePool().AllCandidatePawns.FirstOrDefault(p => p.thingIDNumber == pawnId);
                if (pawn != null && assignments.ForcedRole(pawn) == null) {
                    if (operation == "remove") applied = assignments.TryUnassignAnyRole(pawn);
                    var role = def.Roles.FirstOrDefault(r => r.defName == roleId);
                    if (operation == "assign" && role != null && assignments.RoleForPawn(pawn)!=role && !SpecialistNativeSafety.Protected(pawn)) applied = assignments.TryAssign(pawn, role, out var reason);
                }
            }
            await context.SendJsonResponse(applied ? ApiResult<string>.Ok("ritual_assignment_updated") : ApiResult<string>.Fail("Ritual role or participant requirements changed"));
        }
        private static object Configuration(Dialog_BeginLordJob dialog)
        {
            if(dialog is Dialog_BeginRitual ordinary) {
                var a=Field<RitualRoleAssignments>(ordinary,"assignments");
                return new {participants=a.Participants.OrderBy(p=>p.thingIDNumber).Select(p=>new {pawn_id=p.thingIDNumber,role=a.RoleForPawn(p)?.id,spectator=a.SpectatorsForReading.Contains(p)}).ToList(),
                    role=a.RoleChangeSelection?.def.defName,
                    boarding=dialog is Dialog_BeginGravshipLaunch ? new[]{Field<bool>(dialog,"forceVisitorsToLeave"),Field<bool>(dialog,"boardColonyAnimals"),Field<bool>(dialog,"boardColonyMechs")} : null};
            }
            if(dialog is Dialog_BeginPsychicRitual psychic) {
                var a=Field<PsychicRitualRoleAssignments>(psychic,"assignments");
                return new {participants=a.AllAssignedPawns.OrderBy(p=>p.thingIDNumber).Select(p=>new {pawn_id=p.thingIDNumber,role=a.RoleForPawn(p)?.defName}).ToList()};
            }
            return null;
        }
        private static bool ParticipantsProtected(Dialog_BeginLordJob dialog) {
            if (dialog is Dialog_BeginRitual ordinary) return Field<RitualRoleAssignments>(ordinary, "assignments").Participants.Any(SpecialistNativeSafety.Protected);
            if (dialog is Dialog_BeginPsychicRitual psychic) return Field<PsychicRitualRoleAssignments>(psychic, "assignments").AllAssignedPawns.Any(SpecialistNativeSafety.Protected);
            return false;
        }
    }
}

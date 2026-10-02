using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Threading.Tasks;
using HarmonyLib;
using RIMAPI.Core;
using RIMAPI.Helpers;
using RIMAPI.Http;
using RimWorld;
using Verse;

namespace RIMAPI.Controllers
{
    public class SpecialistMechBossController
    {
        private static Command_CallBossgroup Command(Pawn pawn) => pawn.mechanitor == null ? null : new Command_CallBossgroup(pawn.mechanitor);
        private static bool Enabled(Command_CallBossgroup command) {
            if (command == null) return false;
            object[] args = { null };
            return !(bool)AccessTools.Method(typeof(Command_CallBossgroup), "IsDisabled").Invoke(command, args);
        }
        private static IEnumerable<FloatMenuOption> Options(Command_CallBossgroup command) =>
            (IEnumerable<FloatMenuOption>)AccessTools.Property(typeof(Command_CallBossgroup), "FloatMenuOptions").GetValue(command, null);
        [Get("/api/v1/specialists/mech-bosses")]
        [EndpointMetadata("Read native mechanitor boss summon requirements and current eligible summon jobs; escalation is never automatic")]
        public async Task Context(HttpListenerContext context) {
            var options = new List<object>();
            if (ModsConfig.BiotechActive) foreach (var pawn in PawnsFinder.AllMaps_FreeColonistsSpawned.Where(p => p.mechanitor != null && !SpecialistNativeSafety.Protected(p) && !p.Drafted)) {
                var command = Command(pawn);
                if (!Enabled(command)) continue;
                foreach (var option in Options(command).Where(o => !o.Disabled && o.action != null))
                    options.Add(new { pawn_id = pawn.thingIDNumber, map_id = pawn.Map.uniqueID, label = option.Label,
                        description = command.DescPostfix, pawn = pawn.LabelShortCap.ToString(), current_job = pawn.CurJob?.def.defName,
                        hostile_pawns = pawn.Map.mapPawns.AllPawnsSpawned.Count(p => p.HostileTo(Faction.OfPlayer) && !p.Dead),
                        mobile_defenders = pawn.Map.mapPawns.FreeColonistsSpawned.Count(p => !p.Downed && !p.InMentalState && !p.WorkTagIsDisabled(WorkTags.Violent)) });
            }
            await context.SendJsonResponse(ApiResult<object>.Ok(new { available = ModsConfig.BiotechActive, options,
                warning = "Summoning deliberately brings a hostile boss wave. Rewards unlock higher mech technology only after combat, loot and real research. Compare current defense, healing, resources and waste capacity; summon is not victory." }));
        }
        [Post("/api/v1/specialists/mech-bosses")]
        [EndpointMetadata("Request one normal boss summon job from the freshly generated native command menu")]
        public async Task Act(HttpListenerContext context) {
            int id = RequestParser.GetIntParameter(context, "pawn_id");
            string label = RequestParser.GetStringParameter(context, "label");
            var pawn = PawnsFinder.AllMaps_FreeColonistsSpawned.FirstOrDefault(p => p.thingIDNumber == id && !SpecialistNativeSafety.Protected(p) && !p.Drafted);
            var command = pawn == null ? null : Command(pawn);
            var option = Enabled(command) ? Options(command).FirstOrDefault(o => o.Label == label && !o.Disabled && o.action != null) : null;
            if (!ModsConfig.BiotechActive || !RequestParser.GetBooleanParameter(context, "confirmed") || option == null) {
                await context.SendJsonResponse(ApiResult<string>.Fail("Boss summon conditions changed or unconfirmed")); return;
            }
            option.action();
            await context.SendJsonResponse(ApiResult<string>.Ok("boss_summon_job_requested"));
        }
    }
}

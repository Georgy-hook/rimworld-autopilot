using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Helpers;
using RIMAPI.Http;
using RimWorld;
using Verse;

namespace RIMAPI.Controllers
{
    public class SpecialistPermitController
    {
        private static IEnumerable<FloatMenuOption> Options(Pawn pawn, FactionPermit permit) => permit.Permit.Worker.GetRoyalAidOptions(pawn.Map, pawn, permit.Faction);
        [Get("/api/v1/specialists/permits")]
        [EndpointMetadata("Read owned Royalty permit options, cooldown/honor costs and native targeting/confirmation requirements")]
        public async Task Context(HttpListenerContext context) {
            var options = new List<object>();
            if (ModsConfig.RoyaltyActive) foreach (var pawn in PawnsFinder.AllMaps_FreeColonistsSpawned.Where(p => p.royalty != null && !SpecialistNativeSafety.Protected(p)))
                foreach (var permit in pawn.royalty.AllFactionPermits.Where(p => !p.Faction.HostileTo(Faction.OfPlayer)))
                    foreach (var option in Options(pawn, permit).Where(o => o.action != null && !o.Disabled))
                        options.Add(new { pawn_id = pawn.thingIDNumber, map_id = pawn.Map.uniqueID, permit = permit.Permit.defName,
                            faction_id = permit.Faction.loadID, label = option.Label, description = permit.Permit.description,
                            favor = pawn.royalty.GetFavor(permit.Faction), on_cooldown = permit.OnCooldown,
                            current_job = pawn.CurJob?.def.defName, pawn = pawn.LabelShortCap.ToString(),
                            worker = permit.Permit.Worker.GetType().Name });
            await context.SendJsonResponse(ApiResult<object>.Ok(new { available = ModsConfig.RoyaltyActive, options,
                warning = "The native option label includes free/cooldown or honor payment conditions. Aid can consume honor needed for title progression. Shuttle/resources/strike permits may next require an explicit native local target; calling a permit never guarantees rescue or combat success." }));
        }
        [Post("/api/v1/specialists/permits")]
        [EndpointMetadata("Invoke one owned, currently enabled native Royalty aid option; preserve normal target selection and confirmations")]
        public async Task Act(HttpListenerContext context) {
            int pawnId = RequestParser.GetIntParameter(context, "pawn_id"), factionId = RequestParser.GetIntParameter(context, "faction_id");
            string def = RequestParser.GetStringParameter(context, "permit"), label = RequestParser.GetStringParameter(context, "label");
            var pawn = PawnsFinder.AllMaps_FreeColonistsSpawned.FirstOrDefault(p => p.thingIDNumber == pawnId && p.royalty != null && !SpecialistNativeSafety.Protected(p));
            var permit = pawn?.royalty.AllFactionPermits.FirstOrDefault(p => p.Permit.defName == def && p.Faction.loadID == factionId && !p.Faction.HostileTo(Faction.OfPlayer));
            var option = permit == null ? null : Options(pawn, permit).FirstOrDefault(o => o.Label == label && !o.Disabled && o.action != null);
            if (!ModsConfig.RoyaltyActive || !RequestParser.GetBooleanParameter(context, "confirmed") || option == null) {
                await context.SendJsonResponse(ApiResult<string>.Fail("Permit requirements changed or unconfirmed")); return;
            }
            option.action();
            await context.SendJsonResponse(ApiResult<string>.Ok("permit_native_action_requested"));
        }
    }
}

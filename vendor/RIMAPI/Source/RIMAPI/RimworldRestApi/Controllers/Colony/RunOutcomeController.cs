using System.Net;
using System.Linq;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Http;
using Verse;
using RimWorld;
namespace RIMAPI.Controllers
{
    public class RunOutcomeController
    {
        [Get("/api/v1/colony/ending-evidence")]
        public async Task Evidence(HttpListenerContext context)
        {
            var evidence=Current.Game?.GetComponent<EndingEvidence>();
            var ended = Current.Game != null && Find.GameEnder.gameEnding
                ? Find.LetterStack.LettersListForReading.FirstOrDefault(letter => letter.def == LetterDefOf.GameEnded) : null;
            await context.SendJsonResponse(ApiResult<object>.Ok(new {
                campaign_id=evidence?.CampaignId,
                loaded_map_count=Find.Maps?.Count ?? 0,
                game_tick=Find.TickManager?.TicksGame ?? 0,
                is_paused=Find.TickManager?.Paused ?? true,
                player_caravans=Find.WorldObjects?.Caravans?.Count(c => c.Faction == Faction.OfPlayer) ?? 0,
                victory_verified=evidence != null && evidence.Tick >= 0,
                ending_tick=evidence?.Tick ?? -1, ending_route=evidence?.Route,
                ending_text=evidence?.Text, exits_to_main_menu=evidence?.ExitsToMainMenu ?? false,
                game_over_verified=ended != null, game_over_tick=ended?.arrivalTick ?? -1
            }));
        }
    }
}

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
                victory_verified=evidence != null && evidence.Tick >= 0,
                ending_tick=evidence?.Tick ?? -1, ending_route=evidence?.Route,
                ending_text=evidence?.Text, exits_to_main_menu=evidence?.ExitsToMainMenu ?? false,
                game_over_verified=ended != null, game_over_tick=ended?.arrivalTick ?? -1
            }));
        }
    }
}

using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Helpers;
using RIMAPI.Http;
namespace RIMAPI.Controllers
{
    public class AutonomySafetyController
    {
        [Get("/api/v1/society/autonomy-safety")]
        public async Task Context(HttpListenerContext context) => await context.SendJsonResponse(ApiResult<object>.Ok(new {
            available=true,active=AutonomyDrugSafety.Active,until_utc=AutonomyDrugSafety.UntilUtc,
            blocked_doses=AutonomyDrugSafety.BlockedDoses,last_blocked_tick=AutonomyDrugSafety.LastBlockedTick,
            last_pawn_id=AutonomyDrugSafety.LastPawnId,last_drug=AutonomyDrugSafety.LastDrug,
            limits="Only fresh autonomous joy/scheduled nonmedical drug jobs; medical drugs, addiction/dependency doses and current effects are preserved."}));
        [Post("/api/v1/society/autonomy-safety")]
        public async Task Lease(HttpListenerContext context)
        {
            AutonomyDrugSafety.Lease(RequestParser.GetBooleanParameter(context,"enabled"));
            await context.SendJsonResponse(ApiResult<object>.Ok(new {active=AutonomyDrugSafety.Active,lease_seconds=60}));
        }
    }
}

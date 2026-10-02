using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Http;
using RIMAPI.Helpers;
namespace RIMAPI.Controllers
{
    public class AffordanceOrder
    {
        public int MapId { get; set; }
        public string Kind { get; set; }
        public int PawnId { get; set; }
        public int TargetId { get; set; }
        public string Ability { get; set; }
        public string Label { get; set; }
    }
    public class AffordanceController
    {
        [Get("/api/v1/affordances/targeting")]
        public async Task Targeting(HttpListenerContext context)
        { await context.SendJsonResponse(AffordanceTargetingHelper.Context()); }
        [Post("/api/v1/affordances/targeting")]
        public async Task Target(HttpListenerContext context)
        {
            await context.SendJsonResponse(AffordanceTargetingHelper.Order(
                RequestParser.GetIntParameter(context,"session_id"),RequestParser.GetIntParameter(context,"map_id"),
                RequestParser.GetIntParameter(context,"target_id"),RequestParser.GetIntParameter(context,"x"),
                RequestParser.GetIntParameter(context,"z"),RequestParser.GetBooleanParameter(context,"cancel")));
        }
        [Get("/api/v1/affordances/context")]
        public async Task Context(HttpListenerContext context)
        { await context.SendJsonResponse(AffordanceAutomationHelper.Context(RequestParser.GetMapId(context))); }
        [Post("/api/v1/affordances/order")]
        public async Task Order(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<AffordanceOrder>();
            await context.SendJsonResponse(r == null ? ApiResult<object>.Fail("Body required.")
                : AffordanceAutomationHelper.Execute(r.MapId,r.Kind,r.PawnId,r.TargetId,r.Ability,r.Label));
        }
    }
}

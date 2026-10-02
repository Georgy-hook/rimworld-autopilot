using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Http;
using RIMAPI.Helpers;
using RIMAPI.Models;
namespace RIMAPI.Controllers
{
    public class SocietyController : BaseController
    {
        [Post("/api/v1/society/order")]
        public async Task NativeOrder(HttpListenerContext context)
        { await context.SendJsonResponse(SocietyNativeHelper.Execute(await context.Request.ReadBodyAsync<SocietyNativeRequestDto>())); }
        [Get("/api/v1/society/pending")]
        public async Task Pending(HttpListenerContext context)
        { await context.SendJsonResponse(ApiResult<bool>.Ok(SocietyGrowthHelper.Pending())); }
        [Get("/api/v1/society/context")]
        public async Task Context(HttpListenerContext context)
        { await context.SendJsonResponse(SocietyAutomationHelper.Context(RequestParser.GetMapId(context))); }
        [Post("/api/v1/society/policy")]
        public async Task Policy(HttpListenerContext context)
        { await context.SendJsonResponse(SocietyAutomationHelper.Configure(await context.Request.ReadBodyAsync<SocietyPolicyRequestDto>())); }
    }
}

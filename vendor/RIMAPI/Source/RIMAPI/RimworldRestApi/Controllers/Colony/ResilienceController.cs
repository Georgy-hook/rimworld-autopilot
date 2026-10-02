using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Http;
using RIMAPI.Helpers;
using RIMAPI.Models;
namespace RIMAPI.Controllers
{
    public class ResilienceController : BaseController
    {
        [Get("/api/v1/resilience/context")]
        public async Task Context(HttpListenerContext context)
        { await context.SendJsonResponse(ResilienceAutomationHelper.Context(RequestParser.GetMapId(context))); }
        [Post("/api/v1/resilience/order")]
        public async Task Order(HttpListenerContext context)
        { await context.SendJsonResponse(ResilienceAutomationHelper.Execute(await context.Request.ReadBodyAsync<ResilienceOrderRequestDto>())); }
    }
}

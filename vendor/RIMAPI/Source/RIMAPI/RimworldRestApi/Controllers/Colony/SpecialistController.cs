using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Http;
using RIMAPI.Helpers;
using RIMAPI.Models;
namespace RIMAPI.Controllers
{
    public class SpecialistController : BaseController
    {
        [Get("/api/v1/specialists/context")]
        public async Task Context(HttpListenerContext context)
        { await context.SendJsonResponse(SpecialistAutomationHelper.Context(RequestParser.GetMapId(context))); }
        [Post("/api/v1/specialists/order")]
        public async Task Order(HttpListenerContext context)
        { await context.SendJsonResponse(SpecialistAutomationHelper.Execute(await context.Request.ReadBodyAsync<SpecialistOrderRequestDto>())); }
    }
}

using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core; using RIMAPI.Http; using RIMAPI.Helpers; using RIMAPI.Models;
namespace RIMAPI.Controllers { public class MentalSafetyController : BaseController {
 [Get("/api/v1/mental-safety/context")] public async Task Context(HttpListenerContext c) { await c.SendJsonResponse(MentalSafetyHelper.Context(RequestParser.GetMapId(c))); }
 [Post("/api/v1/mental-safety/order")] public async Task Order(HttpListenerContext c) { await c.SendJsonResponse(MentalSafetyHelper.Order(await c.Request.ReadBodyAsync<MentalSafetyOrderDto>())); }
} }
using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Http;
using RIMAPI.Helpers;
using RIMAPI.Models;
namespace RIMAPI.Controllers { public class SustenanceController : BaseController {
 [Get("/api/v1/sustenance/context")] public async Task Context(HttpListenerContext c) { await c.SendJsonResponse(SustenanceHelper.Context(RequestParser.GetMapId(c))); }
 [Post("/api/v1/sustenance/policy")] public async Task Policy(HttpListenerContext c) { await c.SendJsonResponse(SustenanceHelper.Policy(await c.Request.ReadBodyAsync<SustenancePolicyDto>())); }
} }

using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Http;
using RIMAPI.Models;
using RIMAPI.Helpers;
namespace RIMAPI.Controllers { public class InspirationController : BaseController {
 [Get("/api/v1/inspirations/context")] public async Task Context(HttpListenerContext c) { await c.SendJsonResponse(InspirationAutomationHelper.Context(RequestParser.GetMapId(c))); }
 [Get("/api/v1/inspirations/taming")] public async Task Taming(HttpListenerContext c) { await c.SendJsonResponse(InspirationAutomationHelper.Taming(RequestParser.GetMapId(c))); }
 [Get("/api/v1/inspirations/recruitment")] public async Task Recruitment(HttpListenerContext c) { await c.SendJsonResponse(InspirationAutomationHelper.Recruitment(RequestParser.GetMapId(c))); }
 [Post("/api/v1/inspirations/tame")] public async Task Tame(HttpListenerContext c) { await c.SendJsonResponse(InspirationAutomationHelper.Tame(await c.Request.ReadBodyAsync<InspirationOrderDto>())); }
 [Post("/api/v1/inspirations/recruit")] public async Task Recruit(HttpListenerContext c) { await c.SendJsonResponse(InspirationAutomationHelper.Recruit(await c.Request.ReadBodyAsync<InspirationOrderDto>())); }
} }

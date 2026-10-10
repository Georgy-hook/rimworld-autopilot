using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Http;
using RIMAPI.Helpers;
using RIMAPI.Models;
namespace RIMAPI.Controllers { public class MiningController:BaseController {
 [Get("/api/v1/mining/context")]public async Task Context(HttpListenerContext c){await c.SendJsonResponse(MiningAutomationHelper.Context(RequestParser.GetMapId(c)));}
 [Post("/api/v1/mining/order")]public async Task Order(HttpListenerContext c){await c.SendJsonResponse(MiningAutomationHelper.Order(await c.Request.ReadBodyAsync<MiningOrderDto>()));}
} }

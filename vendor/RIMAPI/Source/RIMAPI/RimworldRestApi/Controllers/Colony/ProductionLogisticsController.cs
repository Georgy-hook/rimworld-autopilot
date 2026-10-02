using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Http;
using RIMAPI.Helpers;
using RIMAPI.Models;
namespace RIMAPI.Controllers { public class ProductionLogisticsController : BaseController {
 [Get("/api/v1/production/logistics")] public async Task Context(HttpListenerContext c) { await c.SendJsonResponse(ProductionLogisticsHelper.Context(RequestParser.GetMapId(c))); }
 [Post("/api/v1/production/logistics")] public async Task Policy(HttpListenerContext c) { await c.SendJsonResponse(ProductionLogisticsHelper.Policy(await c.Request.ReadBodyAsync<ProductionRecipePolicyDto>())); }
} }

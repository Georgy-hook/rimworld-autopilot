using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Http;
using RIMAPI.Helpers;
using RIMAPI.Models;
namespace RIMAPI.Controllers {
 public class ProductionController : BaseController {
  [Get("/api/v1/production/context")]
  public async Task Context(HttpListenerContext c) { await c.SendJsonResponse(ProductionHelper.Context(RequestParser.GetMapId(c))); }
  [Post("/api/v1/production/policy")]
  public async Task Policy(HttpListenerContext c) { await c.SendJsonResponse(ProductionHelper.Policy(await c.Request.ReadBodyAsync<ProductionPolicyDto>())); }
 }
}

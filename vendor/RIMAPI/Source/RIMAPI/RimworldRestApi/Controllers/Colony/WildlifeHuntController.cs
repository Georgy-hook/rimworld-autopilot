using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Http;
using RIMAPI.Models;
using RIMAPI.Helpers;
namespace RIMAPI.Controllers {
 public class WildlifeHuntController : BaseController {
  [Get("/api/v1/wildlife/hunt-context")]
  public async Task Context(HttpListenerContext c) { await c.SendJsonResponse(WildlifeHuntHelper.Context(RequestParser.GetMapId(c))); }
  [Get("/api/v1/wildlife/hunt-status")]
  public async Task Status(HttpListenerContext c) { await c.SendJsonResponse(WildlifeHuntHelper.Status(RequestParser.GetMapId(c))); }
  [Get("/api/v1/wildlife/training-context")]
  public async Task Training(HttpListenerContext c) { await c.SendJsonResponse(WildlifeHuntHelper.Training(RequestParser.GetMapId(c))); }
  [Post("/api/v1/wildlife/hunt-order")]
  public async Task Order(HttpListenerContext c) { await c.SendJsonResponse(WildlifeHuntHelper.Order(await c.Request.ReadBodyAsync<WildlifeHuntOrderDto>())); }
 }
}

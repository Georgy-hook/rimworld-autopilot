using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Http;
using RIMAPI.Helpers;
using RIMAPI.Models;
namespace RIMAPI.Controllers { public class ProductionRecipeController : BaseController {
 [Get("/api/v1/production/recipes")] public async Task Context(HttpListenerContext c) { await c.SendJsonResponse(ProductionRecipeHelper.Context(RequestParser.GetMapId(c))); }
 [Post("/api/v1/production/recipe-bill")] public async Task Policy(HttpListenerContext c) { await c.SendJsonResponse(ProductionRecipeHelper.Policy(await c.Request.ReadBodyAsync<ProductionRecipePolicyDto>())); }
} }

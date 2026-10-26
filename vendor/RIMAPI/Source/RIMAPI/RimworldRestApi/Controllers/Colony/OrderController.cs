using System.Threading.Tasks;
using System.Net;
using RIMAPI.Core;
using RIMAPI.Models;
using RIMAPI.Services;
using RIMAPI.Helpers;
using RIMAPI.Http;
using System.Linq;
using Verse;
using RimWorld;

namespace RIMAPI.Controllers
{
    public class OrderController
    {
        private readonly IOrderService _orderService;

        public OrderController(IOrderService orderService)
        {
            _orderService = orderService;
        }

        [Post("/api/v1/order/designate/area")]
        public async Task DesignateArea(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<DesignateRequestDto>();
            var result = _orderService.DesignateArea(body);
            await context.SendJsonResponse(result);
        }

        [Get("/api/v1/map/fire/situation")]
        [EndpointMetadata("List live fires and whether their cells belong to the Home area")]
        public async Task GetFireSituation(HttpListenerContext context)
        {
            var map = MapHelper.GetMapByID(RequestParser.GetMapId(context));
            if (map == null)
            {
                await context.SendJsonResponse(ApiResult.Fail("Map not found"));
                return;
            }
            var fires = map.listerThings.AllThings.OfType<Fire>().Select(fire => new
            {
                id = fire.thingIDNumber,
                x = fire.Position.x,
                z = fire.Position.z,
                size = fire.fireSize,
                in_home = map.areaManager.Home[fire.Position],
                nearby_player_buildings = map.listerBuildings.allBuildingsColonist.Count(
                    building => (building.Position - fire.Position).LengthHorizontalSquared <= 64),
            }).ToList();
            await context.SendJsonResponse(ApiResult<object>.Ok(new { fires, burning_pawns_available=true,
                burning_pawns=BurningPawnSafetyHelper.Facts(map) }));
        }
    }
}

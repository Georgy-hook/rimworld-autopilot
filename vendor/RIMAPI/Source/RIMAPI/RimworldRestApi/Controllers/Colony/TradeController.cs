using System.Threading.Tasks;
using System.Net;
using RIMAPI.Core;
using RIMAPI.Services;
using System;
using RIMAPI.Helpers;
using RIMAPI.Models;
using RIMAPI.Http;

namespace RIMAPI.Controllers
{
    public class TradeController
    {
        private readonly ITradeService _tradeService;
        private readonly ICachingService _cachingService;

        public TradeController(ITradeService tradeService, ICachingService cachingService)
        {
            _tradeService = tradeService;
            _cachingService = cachingService;
        }

        [Get("/api/v1/traders/defs")]
        public async Task GetTradersDefs(HttpListenerContext context)
        {
            await _cachingService.CacheAwareResponseAsync(
                context,
                "/api/v1/traders/defs",
                dataFactory: () => Task.FromResult(_tradeService.GetAllTraderDefs()),
                expiration: TimeSpan.FromMinutes(5),
                priority: CachePriority.Normal,
                expirationType: CacheExpirationType.Absolute
            );
        }

        [Get("/api/v1/trade/opportunities")]
        [EndpointMetadata("List live visiting and orbital traders with remaining time and visible stock")]
        public async Task GetTradeOpportunities(HttpListenerContext context)
        {
            var mapId = RequestParser.GetMapId(context);
            await context.SendJsonResponse(LiveTradeAutomationHelper.GetOpportunities(mapId));
        }

        [Get("/api/v1/trade/preview")]
        [EndpointMetadata("List sale and purchase categories verified against a live trade session and silver reserves")]
        public async Task GetTradePreview(HttpListenerContext context)
        {
            var mapId = RequestParser.GetMapId(context);
            var traderId = RequestParser.GetStringParameter(context, "trader_id");
            var reserve = RequestParser.GetIntParameter(context, "minimum_silver_reserve");
            var spend = RequestParser.GetIntParameter(context, "maximum_spend");
            // Initial previews have no sale selected yet. Only the second preview
            // supplies this optional filter to price a sale-funded purchase.
            var saleCategory = context.Request.QueryString["sale_category"] ?? "";
            await context.SendJsonResponse(LiveTradeAutomationHelper.GetPreview(mapId, traderId, reserve, spend, saleCategory));
        }

        [Post("/api/v1/trade/execute")]
        [EndpointMetadata("Execute a reserve-aware normal trade with a selected live trader")]
        public async Task ExecuteTrade(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<LiveTradeRequestDto>();
            await context.SendJsonResponse(LiveTradeAutomationHelper.Execute(body));
        }
    }
}

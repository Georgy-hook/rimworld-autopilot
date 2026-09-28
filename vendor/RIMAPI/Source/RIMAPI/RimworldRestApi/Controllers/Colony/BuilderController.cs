using System.Threading.Tasks;
using System.Net;
using RIMAPI.Core;
using RIMAPI.Helpers;
using RIMAPI.Models;
using RIMAPI.Services;
using RIMAPI.Http;

namespace RIMAPI.Controllers
{
    public class BuilderController
    {
        private readonly IBuilderService _builderService;

        public BuilderController(IBuilderService builderService)
        {
            _builderService = builderService;
        }

        [Post("/api/v1/builder/copy")]
        public async Task CopyArea(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<CopyAreaRequestDto>();
            var result = _builderService.CopyArea(body);
            await context.SendJsonResponse(result);
        }

        [Post("/api/v1/builder/paste")]
        public async Task PasteArea(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<PasteAreaRequestDto>();
            var result = _builderService.PasteArea(body);
            await context.SendJsonResponse(result);
        }

        [Post("/api/v1/builder/blueprint")]
        public async Task PlaceBlueprints(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<PasteAreaRequestDto>();
            var result = _builderService.PlaceBlueprints(body);
            await context.SendJsonResponse(result);
        }

        [Post("/api/v1/builder/site-options")]
        [EndpointMetadata("Find valid sites for one loaded building using RimWorld's own placement rules without changing the map")]
        public async Task GetBuildingSiteOptions(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<BuildingSiteOptionsRequestDto>();
            var result = _builderService.GetBuildingSiteOptions(body);
            await context.SendJsonResponse(result);
        }

        [Post("/api/v1/builder/check-zone")]
        public async Task CheckZone(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<CheckZoneRequestDto>();
            var result = _builderService.CheckZone(body);
            await context.SendJsonResponse(result);
        }

        [Post("/api/v1/builder/install-minified")]
        public async Task InstallMinified(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<InstallMinifiedRequestDto>();
            var result = BuilderAutomationHelper.InstallMinified(body);
            await context.SendJsonResponse(result);
        }

        [Post("/api/v1/builder/storage/configure")]
        public async Task ConfigureStorageBuildings(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<ConfigureStorageBuildingsRequestDto>();
            var result = BuilderAutomationHelper.ConfigureStorageBuildings(body);
            await context.SendJsonResponse(result);
        }

        [Get("/api/v1/builder/projects")]
        [EndpointMetadata("List exact unfinished construction blueprints and frames")]
        public async Task GetConstructionProjects(HttpListenerContext context)
        {
            var result = _builderService.GetConstructionProjects(RequestParser.GetMapId(context));
            await context.SendJsonResponse(result);
        }

        [Post("/api/v1/builder/prioritize")]
        [EndpointMetadata("Order a selected colonist to work on one exact construction project")]
        public async Task PrioritizeConstruction(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<PrioritizeConstructionRequestDto>();
            var result = _builderService.PrioritizeConstruction(body);
            await context.SendJsonResponse(result);
        }
    }
}

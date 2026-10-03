using System.Threading.Tasks;
using System.Net;
using RIMAPI.Core;
using RIMAPI.Helpers;
using RIMAPI.Models;
using RIMAPI.Services;
using RIMAPI.Http;
using System.Linq;
using RimWorld;
using Verse;

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

        [Post("/api/v1/builder/refuel")]
        [EndpointMetadata("Order one capable hauler to refuel a completed building using normal game fuel and reservation rules")]
        public async Task RefuelBuilding(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<BuildingRefuelRequestDto>();
            await context.SendJsonResponse(BuildingMaintenanceHelper.Refuel(body));
        }

        [Post("/api/v1/builder/projects/cancel")]
        [EndpointMetadata("Cancel one exact player construction blueprint or frame after checking its ID and expected building definition")]
        public async Task CancelConstructionProject(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<CancelConstructionProjectRequestDto>();
            var map = body == null ? null : MapHelper.GetMapByID(body.MapId);
            if (map == null || body.ProjectThingId <= 0 || string.IsNullOrWhiteSpace(body.ExpectedDefName))
            {
                await context.SendJsonResponse(ApiResult.Fail("Map, project ID and expected definition are required"));
                return;
            }
            var project = map.listerThings.AllThings.FirstOrDefault(thing =>
                thing.thingIDNumber == body.ProjectThingId && (thing is Blueprint || thing is Frame));
            if (project == null || project.Faction != Faction.OfPlayer ||
                project.def.entityDefToBuild?.defName != body.ExpectedDefName)
            {
                await context.SendJsonResponse(ApiResult.Fail("Matching player construction project not found"));
                return;
            }
            if (!string.IsNullOrWhiteSpace(body.ReplacementStuffDefName))
            {
                ThingDef target = project.def.entityDefToBuild as ThingDef;
                ThingDef stuff = DefDatabase<ThingDef>.GetNamedSilentFail(body.ReplacementStuffDefName);
                if (target == null || stuff == null || !target.MadeFromStuff
                    || !GenStuff.AllowedStuffsFor(target).Contains(stuff) || project.Stuff == stuff)
                {
                    await context.SendJsonResponse(ApiResult.Fail("Compatible different replacement material required"));
                    return;
                }
                var placement = GenConstruct.CanPlaceBlueprintAt(target, project.Position, project.Rotation,
                    map, false, project, null, stuff);
                var costs = target.CostListAdjusted(stuff);
                var reserved = map.listerThings.AllThings.Where(t => t != project && t.Faction == Faction.OfPlayer
                    && (t is Blueprint || t is Frame)).OfType<IConstructible>().ToList();
                bool budget = costs.All(cost => map.listerThings.AllThings.Where(t => t.def == cost.thingDef
                    && !t.IsForbidden(Faction.OfPlayer) && !t.Position.Fogged(map)).Sum(t => t.stackCount)
                    - reserved.Sum(t => System.Math.Max(0, t.ThingCountNeeded(cost.thingDef))) >= cost.count);
                if (!placement.Accepted || !budget)
                {
                    await context.SendJsonResponse(ApiResult.Fail("Replacement placement or unreserved budget unavailable; original retained"));
                    return;
                }
                var cell = project.Position;
                var rotation = project.Rotation;
                // The request is dispatched on RimApiServerProcess's main thread.
                // Validate before cancellation; no yielded work between these mutations.
                project.Destroy(DestroyMode.Cancel);
                var replacement = GenConstruct.PlaceBlueprintForBuild(target, cell, map, rotation, Faction.OfPlayer, stuff);
                await context.SendJsonResponse(ApiResult<object>.Ok(new { replaced_project_id = body.ProjectThingId,
                    replacement_project_id = replacement?.thingIDNumber, completion = "unverified" }));
                return;
            }
            project.Destroy(DestroyMode.Cancel);
            await context.SendJsonResponse(ApiResult.Ok());
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

using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using HarmonyLib;
using RIMAPI.Core;
using RIMAPI.Helpers;
using RIMAPI.Http;
using RimWorld;
using RimWorld.Planet;
using Verse;

namespace RIMAPI.Controllers
{
    public class EndingWorldTargetController
    {
        private static T Field<T>(string name) => (T)AccessTools.Field(typeof(WorldTargeter), name).GetValue(Find.WorldTargeter);
        private static string Session => RuntimeHelpers.GetHashCode(Field<Func<GlobalTargetInfo, bool>>("action")).ToString();
        private static bool Valid(GlobalTargetInfo target) => Field<Func<GlobalTargetInfo, bool>>("canSelectTarget")?.Invoke(target) ?? true;
        [Get("/api/v1/colony/endings/pending")]
        [EndpointMetadata("Cheap native ending navigation state; does not enumerate sites, destinations or colony choices")]
        public async Task Pending(HttpListenerContext context) {
            string title = Find.TilePicker.Active ? (string)AccessTools.Field(typeof(TilePicker), "title").GetValue(Find.TilePicker) : null;
            bool pending = Find.WorldTargeter.IsTargeting || Find.TilePicker.Active && (title == "ChooseNextColonySite".Translate().ToString() || title == "ChooseWhereToLand".Translate().ToString()) ||
                ModsConfig.OdysseyActive && Find.GravshipController.LandingAreaConfirmationInProgress;
            await context.SendJsonResponse(ApiResult<bool>.Ok(pending));
        }
        [Get("/api/v1/colony/endings/world-targeting")]
        [EndpointMetadata("Read a current native world targeting session and native selectable world objects/tiles for abilities, permits and travel")]
        public async Task Context(HttpListenerContext context) {
            if (!Find.WorldTargeter.IsTargeting) { await context.SendJsonResponse(ApiResult<object>.Ok(new { active = false })); return; }
            var options = new List<object>();
            var label = Field<Func<GlobalTargetInfo, TaggedString>>("extraLabelGetter");
            foreach (var obj in Find.WorldObjects.AllWorldObjects.Where(o => o.Tile.Valid)) {
                var target = new GlobalTargetInfo(obj);
                if (Valid(target)) options.Add(new { operation = "object", object_id = obj.ID, tile_id = obj.Tile.tileId, layer_id = obj.Tile.Layer.LayerID,
                    label = obj.Label, native_info = label?.Invoke(target).ToString(), world_object = obj.def.defName });
            }
            if (Field<bool>("canTargetTiles")) {
                var origin = Find.CurrentMap?.Tile ?? Find.WorldGrid[0].tile;
                foreach (int id in Enumerable.Range(0, Find.WorldGrid.TilesCount).OrderBy(i => Find.WorldGrid.ApproxDistanceInTiles(origin, i)).Take(20)) {
                    var tile = Find.WorldGrid[id].tile; var target = new GlobalTargetInfo(tile);
                    if (Valid(target)) options.Add(new { operation = "tile", tile_id = id, layer_id = tile.Layer.LayerID,
                        label = tile.Tile.PrimaryBiome.label + " " + id, native_info = label?.Invoke(target).ToString() });
                }
            }
            await context.SendJsonResponse(ApiResult<object>.Ok(new { active = true, session = Session, options,
                source = Field<Func<GlobalTargetInfo, bool>>("action").Method.DeclaringType.FullName,
                warning = "Native world target callback may still reject the target or open another explicit choice. Travel consumes resources and can strand people; target selection does not prove arrival or completion." }));
        }
        [Post("/api/v1/colony/endings/world-targeting")]
        [EndpointMetadata("Choose one freshly validated target in the exact current native WorldTargeter session or explicitly cancel it")]
        public async Task Act(HttpListenerContext context) {
            string session = RequestParser.GetStringParameter(context, "session"), operation = RequestParser.GetStringParameter(context, "operation");
            if (!Find.WorldTargeter.IsTargeting || !RequestParser.GetBooleanParameter(context, "confirmed") || session != Session) {
                await context.SendJsonResponse(ApiResult<string>.Fail("World target session changed or unconfirmed")); return;
            }
            if (operation == "cancel") { Find.WorldTargeter.StopTargeting(); await context.SendJsonResponse(ApiResult<string>.Ok("world_target_cancelled")); return; }
            GlobalTargetInfo target = GlobalTargetInfo.Invalid;
            if (operation == "object") {
                int id = RequestParser.GetIntParameter(context, "object_id");
                var obj = Find.WorldObjects.AllWorldObjects.FirstOrDefault(o => o.ID == id);
                if (obj != null) target = new GlobalTargetInfo(obj);
            } else if (operation == "tile" && Field<bool>("canTargetTiles")) {
                int id = RequestParser.GetIntParameter(context, "tile_id"), layerId = RequestParser.GetIntParameter(context, "layer_id");
                if (Find.WorldGrid.PlanetLayers.TryGetValue(layerId, out var layer) && id >= 0 && id < layer.TilesCount) target = new GlobalTargetInfo(new PlanetTile(id, layer));
            }
            if (target.IsValid && Valid(target) && Field<Func<GlobalTargetInfo, bool>>("action")(target)) {
                Find.WorldTargeter.StopTargeting(); await context.SendJsonResponse(ApiResult<string>.Ok("world_target_chosen")); return;
            }
            await context.SendJsonResponse(ApiResult<string>.Fail("Native world target rejected or conditions changed"));
        }
    }
}

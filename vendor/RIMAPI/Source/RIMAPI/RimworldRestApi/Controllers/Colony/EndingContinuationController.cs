using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
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
    public class EndingContinuationController
    {
        private static T Field<T>(object target, string name) => (T)AccessTools.Field(target.GetType(), name).GetValue(target);
        private static Dialog_ConfigureIdeo Ideology => Find.WindowStack.Windows.OfType<Dialog_ConfigureIdeo>().FirstOrDefault(d => Field<bool>(d, "forArchonexusRestart"));
        private static bool ChoosingTile => Find.TilePicker.Active && Field<string>(Find.TilePicker, "title") == "ChooseNextColonySite".Translate().ToString();
        [Get("/api/v1/colony/endings/continuation")]
        [EndpointMetadata("Read native post-sale tile selection and ideology continuation, with feasible settlement alternatives")]
        public async Task Context(HttpListenerContext context) {
            var dialog = Ideology;
            var tiles = new List<object>();
            if (ChoosingTile) {
                int total = Find.WorldGrid.TilesCount;
                int origin = Find.Maps.FirstOrDefault(m => m.IsPlayerHome)?.Tile.tileId ?? 0;
                // Present nearby and geographically spread choices. All world tiles remain
                // queryable through the world API and selectable by explicit tile_id.
                var nearby = new List<int>();
                var pending = new Queue<PlanetTile>();
                var visited = new HashSet<int>();
                var neighbors = new List<PlanetTile>();
                pending.Enqueue(Find.WorldGrid[origin].tile); visited.Add(origin);
                // Native neighbor BFS bounds this read to 2048 inspected tiles,
                // rather than validating/sorting every tile on every poll.
                int inspected = 0;
                while (pending.Count > 0 && nearby.Count < 12 && inspected++ < 2048) {
                    var tile = pending.Dequeue();
                    if (TileFinder.IsValidTileForNewSettlement(tile)) nearby.Add(tile.tileId);
                    neighbors.Clear(); Find.WorldGrid.GetTileNeighbors(tile, neighbors);
                    foreach (var neighbor in neighbors) if (visited.Add(neighbor.tileId)) pending.Enqueue(neighbor);
                }
                var spread = Enumerable.Range(0, 24).Select(i => i * Math.Max(1, total / 24)).Where(i => i < total && TileFinder.IsValidTileForNewSettlement(Find.WorldGrid[i].tile));
                foreach (int id in nearby.Concat(spread).Distinct()) tiles.Add(new { tile_id = id, facts = TileHelper.GetTile(id) });
            }
            await context.SendJsonResponse(ApiResult<object>.Ok(new {
                cinematic = Find.WindowStack.Windows.OfType<Screen_ArchonexusSettlementCinematics>().Any(),
                choosing_tile = ChoosingTile, tiles, configuring_ideology = dialog != null,
                primary_ideology = dialog?.CurrentPrimaryIdeo?.name,
                ideologies = dialog == null ? null : Find.IdeoManager.IdeosListForReading.Select(i => new { id = i.id, label = i.name,
                    memes = i.memes.Select(m => m.defName).ToList(), precepts = i.PreceptsListForReading.Select(p => p.def.defName).ToList() }).ToList()
            }));
        }
        [Post("/api/v1/colony/endings/continuation")]
        [EndpointMetadata("Choose a native post-sale settlement tile or explicitly continue with a chosen existing ideology")]
        public async Task Act(HttpListenerContext context) {
            if (!RequestParser.GetBooleanParameter(context, "confirmed")) { await context.SendJsonResponse(ApiResult<string>.Fail("Unconfirmed continuation")); return; }
            string operation = RequestParser.GetStringParameter(context, "operation");
            if (operation == "tile" && ChoosingTile) {
                int id = RequestParser.GetIntParameter(context, "tile_id");
                if (id < 0 || id >= Find.WorldGrid.TilesCount) { await context.SendJsonResponse(ApiResult<string>.Fail("Invalid tile")); return; }
                PlanetTile tile = Find.WorldGrid[id].tile;
                var picker = Find.TilePicker;
                if (!TileFinder.IsValidTileForNewSettlement(tile) || !Field<Func<PlanetTile, bool>>(picker, "validator")(tile)) {
                    await context.SendJsonResponse(ApiResult<string>.Fail("Native tile requirements changed")); return;
                }
                var callback = Field<Action<PlanetTile>>(picker, "tileChosen");
                AccessTools.Method(typeof(TilePicker), "StopTargetingInt").Invoke(picker, null);
                callback(tile);
                await context.SendJsonResponse(ApiResult<string>.Ok("settlement_tile_chosen")); return;
            }
            var dialog = Ideology;
            if (operation == "ideology" && dialog != null) {
                int id = RequestParser.GetIntParameter(context, "ideology_id");
                var ideology = Find.IdeoManager.IdeosListForReading.FirstOrDefault(i => i.id == id);
                if (ideology == null) { await context.SendJsonResponse(ApiResult<string>.Fail("Ideology changed")); return; }
                AccessTools.Method(typeof(Dialog_ConfigureIdeo), "CheckRemoveNewIdeoAndMakePrimary").Invoke(dialog, new object[] { ideology });
                // Mirrors the native Next handler after the explicitly selected ideology.
                if (Faction.OfPlayer.ideos.PrimaryIdeo != dialog.CurrentPrimaryIdeo) Faction.OfPlayer.ideos.SetPrimary(dialog.CurrentPrimaryIdeo);
                var assignments = Field<Dictionary<Pawn, Ideo>>(dialog, "pawnConvertToIdeo");
                foreach (var pawn in Field<List<Pawn>>(dialog, "pawns")) if (assignments[pawn] != null) pawn.ideo.SetIdeo(assignments[pawn]);
                var callback = Field<Action>(dialog, "nextAction");
                dialog.Close(); callback();
                await context.SendJsonResponse(ApiResult<string>.Ok("ideology_continuation_requested")); return;
            }
            await context.SendJsonResponse(ApiResult<string>.Fail("Native continuation stage changed"));
        }
    }
}

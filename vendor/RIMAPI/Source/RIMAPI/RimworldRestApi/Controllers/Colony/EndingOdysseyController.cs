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
    [HarmonyPatch(typeof(CompPilotConsole), nameof(CompPilotConsole.StartChoosingDestination_NewTemp))]
    public static class EndingGravshipDestinationHook
    {
        public static CompPilotConsole Console;
        public static void Postfix(CompPilotConsole __instance, bool launching) { if (launching && Find.TilePicker.Active) Console = __instance; }
    }
    public class EndingOdysseyController
    {
        // Cache search progress, never native validity: every emitted footprint is
        // revalidated. Bounded work matters while a paused landing is polled.
        private static string LandingSearchKey;
        private static int LandingSearchCursor;
        private static DateTime LandingSearchExhaustedAt;
        private static readonly List<IntVec3> LandingSearchCells = new List<IntVec3>();
        private static T Field<T>(object target, string name) => (T)AccessTools.Field(target.GetType(), name).GetValue(target);
        private static bool Picking => ModsConfig.OdysseyActive && Find.TilePicker.Active && Field<string>(Find.TilePicker, "title") == "ChooseWhereToLand".Translate().ToString() &&
            Field<bool>(Find.TilePicker, "showNextButton");
        private static string Session(object callback) => RuntimeHelpers.GetHashCode(callback).ToString();
        private static Building_GravEngine Engine => EndingGravshipDestinationHook.Console == null ? null : Field<Building_GravEngine>(EndingGravshipDestinationHook.Console, "engine");
        private static bool ValidDestination(PlanetTile tile, Building_GravEngine engine, out float fuel, out int distance) {
            fuel = 0; distance = 0;
            if (engine == null || !engine.Spawned || DebugSettings.ignoreGravshipRange || DebugSettings.skipGravshipTileSelection) return false;
            if (!GravshipUtility.TryGetPathFuelCost(engine.Tile, tile, out fuel, out distance, 10f, engine.FuelUseageFactor) || fuel > engine.TotalFuel) return false;
            var console = EndingGravshipDestinationHook.Console;
            int max = (int)AccessTools.Method(typeof(CompPilotConsole), "GetMaxLaunchDistance").Invoke(console, new object[] { tile.Layer });
            if (distance > max || tile == engine.Tile && !engine.Map.listerThings.AnyThingWithDef(ThingDefOf.GravAnchor)) return false;
            var map = Find.WorldObjects.MapParentAt(tile);
            if (map != null && map.RequiresSignalJammerToReach && !engine.HasSignalJammer) return false;
            return map != null && map.HasMap || TileFinder.IsValidTileForNewSettlement(tile, null, forGravship: true);
        }
        [Get("/api/v1/colony/endings/odyssey")]
        [EndpointMetadata("Read native gravship launch conditions, fuel, explicit destination alternatives and landing placement stage; unavailable without Odyssey")]
        public async Task Context(HttpListenerContext context) {
            if (!ModsConfig.OdysseyActive) { await context.SendJsonResponse(ApiResult<object>.Ok(new { available = false, validation = "Odyssey data absent/inactive; assembly support is static only" })); return; }
            var launches = new List<object>();
            foreach (var map in Find.Maps) foreach (var consoleThing in map.listerThings.AllThings.Where(t => t.TryGetComp<CompPilotConsole>() != null && t.Faction == Faction.OfPlayer)) {
                var console = consoleThing.TryGetComp<CompPilotConsole>();
                var engine = Field<Building_GravEngine>(console, "engine");
                if (engine == null) continue;
                foreach (var pawn in map.mapPawns.FreeColonistsSpawned.Where(p => !SpecialistNativeSafety.Protected(p)))
                    foreach (var option in console.CompFloatMenuOptions(pawn).Where(o => o.action != null && !o.Disabled))
                        launches.Add(new { map_id = map.uniqueID, thing_id = consoleThing.thingIDNumber, pawn_id = pawn.thingIDNumber,
                            label = option.Label, operation = "pilot", fuel = engine.TotalFuel, maximum_fuel = engine.MaxFuel,
                            range = engine.MaxLaunchDistance, missing_components = engine.MissingComponents.Select(d => d.defName).ToList(),
                            orbital_warnings = engine.GetOrbitalWarnings().Select(t => t.ToString()).ToList(), current_job = pawn.CurJob?.def.defName,
                            colonists_on_ship = map.mapPawns.FreeColonistsSpawned.Where(engine.OnValidSubstructure).Select(p => p.LabelShortCap.ToString()).ToList(),
                            colonists_outside_ship = map.mapPawns.FreeColonistsSpawned.Where(p => !engine.OnValidSubstructure(p)).Select(p => p.LabelShortCap.ToString()).ToList() });
            }
            var destinations = new List<object>();
            if (Picking && Engine != null) {
                var engine = Engine;
                var objects = Find.WorldObjects.AllWorldObjects.Where(o => o.Tile.Valid).Select(o => o.Tile);
                var origin = engine.Tile;
                var local = Enumerable.Range(0, Find.WorldGrid.TilesCount).Select(i => Find.WorldGrid[i].tile)
                    .Where(t => Find.WorldGrid.ApproxDistanceInTiles(origin, t) <= engine.MaxLaunchDistance).Take(400);
                foreach (var tile in objects.Concat(local).Distinct()) if (ValidDestination(tile, engine, out float fuel, out int distance)) {
                    var obj = Find.WorldObjects.MapParentAt(tile);
                    destinations.Add(new { operation = "destination", tile_id = tile.tileId, layer_id = tile.Layer.LayerID,
                        label = obj?.Label ?? tile.Tile.PrimaryBiome.label, fuel_cost = fuel, distance,
                        biome = tile.Tile.PrimaryBiome.defName, world_object = obj?.def.defName,
                        requires_signal_jammer = obj?.RequiresSignalJammerToReach ?? false });
                    if (destinations.Count >= 40) break;
                }
                destinations.Add(new { operation = "cancel", label = "Cancel gravship destination selection" });
            }
            var landings = new List<object>();
            var controller = Find.GravshipController;
            string landingSession = null, landingBlocker = null; int? landingMapId = null;
            if (controller.LandingAreaConfirmationInProgress) {
                var designator = controller.MoveDesignator();
                var marker = designator.marker;
                landingSession = Session(marker); landingMapId = designator.map.uniqueID;
                if (Find.CurrentMap != designator.map) landings.Add(new { operation = "view_landing_map", map_id = designator.map.uniqueID, rotation = marker.GravshipRotation.AsInt, label = "Show required gravship landing map" });
                if (Find.CurrentMap == designator.map) {
                    int coarseChecks = 0;
                    for (int x = 8; x < designator.map.Size.x && landings.Count < 24 && coarseChecks < 256; x += 12)
                        for (int z = 8; z < designator.map.Size.z && landings.Count < 24 && coarseChecks < 256; z += 12) {
                            coarseChecks++;
                            var cell = new IntVec3(x, 0, z);
                            if (designator.CanDesignateCell(cell).Accepted) landings.Add(new { operation = "place", x, z,
                                rotation = marker.GravshipRotation.AsInt, map_id = designator.map.uniqueID, label = "Place gravship " + cell,
                                warning = "Landing footprint can destroy vegetation and displace obstacles; choose doors/thruster access and defense." });
                        }
                    if (landings.Count == 0) {
                        string searchKey = landingSession + ":" + designator.map.uniqueID + ":" + marker.GravshipRotation.AsInt;
                        int totalCells = designator.map.Size.x * designator.map.Size.z;
                        if (LandingSearchKey != searchKey || LandingSearchCursor >= totalCells &&
                            (DateTime.UtcNow - LandingSearchExhaustedAt).TotalSeconds >= 30) {
                            LandingSearchKey = searchKey; LandingSearchCursor = 0; LandingSearchExhaustedAt = default(DateTime); LandingSearchCells.Clear();
                        }
                        LandingSearchCells.RemoveAll(cell => !designator.CanDesignateCell(cell).Accepted);
                        if (LandingSearchCells.Count == 0) {
                            int stop = Math.Min(totalCells, LandingSearchCursor + 256);
                            while (LandingSearchCursor < stop && LandingSearchCells.Count < 24) {
                                int index = LandingSearchCursor++;
                                var cell = new IntVec3(index / designator.map.Size.z, 0, index % designator.map.Size.z);
                                if (designator.CanDesignateCell(cell).Accepted) LandingSearchCells.Add(cell);
                            }
                            if (LandingSearchCursor >= totalCells && LandingSearchExhaustedAt == default(DateTime)) LandingSearchExhaustedAt = DateTime.UtcNow;
                        }
                        foreach (var cell in LandingSearchCells)
                            landings.Add(new { operation = "place", x = cell.x, z = cell.z, rotation = marker.GravshipRotation.AsInt,
                                map_id = designator.map.uniqueID, label = "Place gravship " + cell });
                        if (landings.Count == 0) landingBlocker = LandingSearchCursor < totalCells
                            ? "Searching native landing footprints; bounded search continues on next observation"
                            : "Native footprint search exhausted; retry in at most 30 seconds or after session/map/rotation change";
                    }
                    if (marker.Spawned && Find.DesignatorManager.SelectedDesignator != designator)
                        landings.Add(new { operation = "land", label = "Confirm the currently placed gravship landing", map_id = marker.Map.uniqueID,
                            x = marker.Position.x, z = marker.Position.z, rotation = marker.GravshipRotation.AsInt });
                }
            }
            if (controller.LandingAreaConfirmationInProgress && landings.Count == 0 && landingBlocker == null) landingBlocker = "Native landing has no currently viable footprint or confirmable marker; await native map readiness";
            await context.SendJsonResponse(ApiResult<object>.Ok(new { available = true, launches, destinations, landings,
                picking_destination = Picking, destination_session = Picking ? Session(Field<Func<PlanetTile, bool>>(Find.TilePicker, "validator")) : null,
                landing_session = landingSession, landing_map_id = landingMapId, landing_blocker = landingBlocker,
                landing = controller.LandingAreaConfirmationInProgress, cutscene = WorldComponent_GravshipController.CutsceneInProgress,
                warning = "Launching transports only boarded people and the connected substructure. Fuel is consumed by the native callback. Space requires native sealed/oxygen/temperature preparedness; gravship travel does not complete the mechhive ending." }));
        }
        [Post("/api/v1/colony/endings/odyssey")]
        [EndpointMetadata("Request native gravship piloting, validated destination selection, footprint placement or normal landing confirmation; never instant launches or forced completion")]
        public async Task Act(HttpListenerContext context) {
            if (!ModsConfig.OdysseyActive || !RequestParser.GetBooleanParameter(context, "confirmed") || DebugSettings.ignoreGravshipRange || DebugSettings.skipGravshipTileSelection) {
                await context.SendJsonResponse(ApiResult<string>.Fail("Odyssey inactive, unconfirmed or debug range/launch override enabled")); return;
            }
            string operation = RequestParser.GetStringParameter(context, "operation");
            if (operation == "pilot") {
                int thingId = RequestParser.GetIntParameter(context, "thing_id"), pawnId = RequestParser.GetIntParameter(context, "pawn_id");
                var pawn = PawnsFinder.AllMaps_FreeColonistsSpawned.FirstOrDefault(p => p.thingIDNumber == pawnId && !SpecialistNativeSafety.Protected(p));
                var thing = pawn?.Map.listerThings.AllThings.FirstOrDefault(t => t.thingIDNumber == thingId && t.Faction == Faction.OfPlayer);
                string label = RequestParser.GetStringParameter(context, "label");
                var option = thing?.TryGetComp<CompPilotConsole>()?.CompFloatMenuOptions(pawn).FirstOrDefault(o => o.Label == label && !o.Disabled && o.action != null);
                if (option != null) { option.action(); await context.SendJsonResponse(ApiResult<string>.Ok("gravship_pilot_job_requested")); return; }
            }
            if (operation == "destination" && Picking) {
                var validator = Field<Func<PlanetTile, bool>>(Find.TilePicker, "validator");
                string session = RequestParser.GetStringParameter(context, "session");
                int id = RequestParser.GetIntParameter(context, "tile_id"), layerId = RequestParser.GetIntParameter(context, "layer_id");
                if (session == Session(validator) && Find.WorldGrid.PlanetLayers.TryGetValue(layerId, out var layer) && id >= 0 && id < layer.TilesCount) {
                    var tile = new PlanetTile(id, layer);
                    if (ValidDestination(tile, Engine, out var fuel, out var distance) && validator(tile)) {
                        var callback = Field<Action<PlanetTile>>(Find.TilePicker, "tileChosen");
                        AccessTools.Method(typeof(TilePicker), "StopTargetingInt").Invoke(Find.TilePicker, null); callback(tile);
                        await context.SendJsonResponse(ApiResult<string>.Ok("gravship_destination_chosen")); return;
                    }
                }
            }
            if (operation == "cancel" && Picking) { Find.TilePicker.StopTargeting(); await context.SendJsonResponse(ApiResult<string>.Ok("gravship_destination_cancelled")); return; }
            var controller = Find.GravshipController;
            if (controller.LandingAreaConfirmationInProgress) {
                var designator = controller.MoveDesignator(); var marker = designator.marker;
                if (RequestParser.GetStringParameter(context, "session") != Session(marker)) { await context.SendJsonResponse(ApiResult<string>.Fail("Landing session changed")); return; }
                if (operation == "view_landing_map" && RequestParser.GetIntParameter(context, "map_id") == designator.map.uniqueID) {
                    Current.Game.CurrentMap = designator.map;
                    await context.SendJsonResponse(ApiResult<string>.Ok("gravship_landing_map_selected")); return;
                }
                int x = RequestParser.GetIntParameter(context, "x"), z = RequestParser.GetIntParameter(context, "z");
                if (RequestParser.GetIntParameter(context, "map_id") != designator.map.uniqueID || RequestParser.GetIntParameter(context, "rotation") != marker.GravshipRotation.AsInt) { await context.SendJsonResponse(ApiResult<string>.Fail("Landing map or rotation changed")); return; }
                if (operation == "place" && Find.CurrentMap == designator.map && designator.CanDesignateCell(new IntVec3(x, 0, z)).Accepted) {
                    designator.DesignateSingleCell(new IntVec3(x, 0, z));
                    await context.SendJsonResponse(ApiResult<string>.Ok("gravship_landing_marker_placed")); return;
                }
                if (operation == "land" && marker.Spawned && marker.Position.x == x && marker.Position.z == z && Find.DesignatorManager.SelectedDesignator != designator) {
                    marker.BeginLanding(controller);
                    AccessTools.Field(typeof(WorldComponent_GravshipController), "landingMarker").SetValue(controller, null);
                    await context.SendJsonResponse(ApiResult<string>.Ok("gravship_landing_requested")); return;
                }
            }
            await context.SendJsonResponse(ApiResult<string>.Fail("Native gravship stage, destination or footprint requirements changed"));
        }
    }
}

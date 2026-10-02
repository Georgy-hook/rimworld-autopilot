using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Helpers;
using RIMAPI.Http;
using RIMAPI.Models;
using RimWorld;
using Verse;

namespace RIMAPI.Controllers
{
    // Native placement observation only. No temporary blueprints, IDs, map edits or reservations.
    public class BlueprintPreviewController : BaseController
    {
        public sealed class Element
        {
            public int index;
            public string kind;
            public string def_name;
            public int x;
            public int z;
            public int rotation;
            public bool accepted;
            public string reason;
            internal HashSet<IntVec3> footprint;
            internal IntVec3? interaction;
        }

        [Post("/api/v1/builder/blueprint/preview")]
        public async Task Preview(HttpListenerContext context)
        {
            await context.SendJsonResponse(Check(await context.Request.ReadBodyAsync<PasteAreaRequestDto>()));
        }

        public static ApiResult<object> Check(PasteAreaRequestDto request)
        {
            if (request?.Blueprint == null || request.Position == null)
                return ApiResult<object>.Fail("Blueprint and position are required.");
            Map map = MapHelper.GetMapByID(request.MapId);
            if (map == null) return ApiResult<object>.Fail("Map missing.");
            var rows = new List<Element>();
            foreach (var floor in request.Blueprint.Floors ?? new List<SavedTerrainDto>())
            {
                var row = new Element { index = rows.Count, kind = "terrain", def_name = floor?.DefName,
                    x = request.Position.X + (floor?.RelX ?? 0), z = request.Position.Z + (floor?.RelZ ?? 0), rotation = 0 };
                rows.Add(row);
                try
                {
                    TerrainDef def = floor == null ? null : DefDatabase<TerrainDef>.GetNamedSilentFail(floor.DefName);
                    if (def?.designationCategory == null) { row.reason = "Unknown or non-player terrain definition"; continue; }
                    if (def.researchPrerequisites?.Any(r => r != null && !r.IsFinished) == true)
                    { row.reason = "Research not finished"; continue; }
                    IntVec3 cell = new IntVec3(row.x, 0, row.z);
                    row.footprint = new HashSet<IntVec3> { cell };
                    if (!cell.InBounds(map)) { row.reason = "Outside map"; continue; }
                    var native = GenConstruct.CanPlaceBlueprintAt(def, cell, Rot4.North, map, false, null);
                    row.accepted = native.Accepted;
                    row.reason = native.Accepted ? "native_placement_accepted" : native.Reason;
                }
                catch (Exception error) { row.accepted = false; row.reason = error.Message; }
            }
            foreach (var part in request.Blueprint.Buildings ?? new List<SavedBuildingDto>())
            {
                var row = new Element { index = rows.Count, kind = "building", def_name = part?.DefName,
                    x = request.Position.X + (part?.RelX ?? 0), z = request.Position.Z + (part?.RelZ ?? 0), rotation = part?.Rotation ?? 0 };
                rows.Add(row);
                try
                {
                    ThingDef def = part == null ? null : DefDatabase<ThingDef>.GetNamedSilentFail(part.DefName);
                    if (def == null || def.category != ThingCategory.Building || def.designationCategory == null)
                    { row.reason = "Unknown or non-player building definition"; continue; }
                    if (row.rotation < 0 || row.rotation > 3) { row.reason = "Invalid rotation"; continue; }
                    if (def.researchPrerequisites?.Any(r => r != null && !r.IsFinished) == true)
                    { row.reason = "Research not finished"; continue; }
                    ThingDef stuff = string.IsNullOrEmpty(part.StuffDefName) ? null : DefDatabase<ThingDef>.GetNamedSilentFail(part.StuffDefName);
                    if (def.costStuffCount > 0 && (stuff?.stuffProps?.categories == null || def.stuffCategories == null
                        || !stuff.stuffProps.categories.Any(def.stuffCategories.Contains)))
                    { row.reason = "Compatible stuff required"; continue; }
                    var pos = new IntVec3(row.x, 0, row.z);
                    var rot = new Rot4(row.rotation);
                    row.footprint = new HashSet<IntVec3>(GenAdj.OccupiedRect(pos, rot, def.Size));
                    if (row.footprint.Any(c => !c.InBounds(map))) { row.reason = "Footprint outside map"; continue; }
                    bool conduit = def.defName == "PowerConduit" || def.defName == "HiddenConduit" || def.defName == "WaterproofConduit";
                    if (!conduit && row.footprint.Any(c => c.GetThingList(map).Any(t =>
                        t is Building || ((t is Blueprint || t is Frame) && t.def.entityDefToBuild is ThingDef))))
                    { row.reason = "Footprint overlaps existing building or plan"; continue; }
                    if (def.hasInteractionCell) row.interaction = pos + def.interactionCellOffset.RotatedBy(rot);
                    var native = GenConstruct.CanPlaceBlueprintAt(def, pos, rot, map, false, null, null, stuff);
                    row.accepted = native.Accepted;
                    row.reason = native.Accepted ? "native_placement_accepted" : native.Reason;
                }
                catch (Exception error) { row.accepted = false; row.reason = error.Message; }
            }
            // Individual native checks cannot see other proposed elements. Detect compound
            // conflicts without materializing those elements into the live map.
            var owners = new Dictionary<IntVec3, Element>();
            var floors = new Dictionary<IntVec3, Element>();
            foreach (var row in rows.Where(r => r.kind == "terrain" && r.footprint != null))
                foreach (var cell in row.footprint)
                    if (floors.TryGetValue(cell, out Element other))
                    { row.accepted = other.accepted = false; row.reason = other.reason = "Proposed floor cells overlap"; }
                    else floors[cell] = row;
            foreach (var row in rows.Where(r => r.kind == "building" && r.footprint != null))
            {
                bool conduit = row.def_name == "PowerConduit" || row.def_name == "HiddenConduit" || row.def_name == "WaterproofConduit";
                if (conduit) continue;
                foreach (var cell in row.footprint)
                    if (owners.TryGetValue(cell, out Element other))
                    { row.accepted = other.accepted = false; row.reason = other.reason = "Proposed building footprints overlap"; }
                    else owners[cell] = row;
            }
            foreach (var row in rows.Where(r => r.interaction.HasValue))
                if (owners.TryGetValue(row.interaction.Value, out Element blocker) && blocker != row)
                { row.accepted = false; row.reason = "Proposed building blocks interaction cell"; }
            return ApiResult<object>.Ok(new { all_placeable = rows.Count > 0 && rows.All(r => r.accepted),
                placed_count = 0, requested_count = rows.Count, accepted_count = rows.Count(r => r.accepted),
                position = request.Position, elements = rows, roof_requested = request.Blueprint.Roof,
                reason = rows.Count == 0 ? "empty_blueprint" : "Read-only native placement preview; proposed prerequisites are not simulated" });
        }
    }
}

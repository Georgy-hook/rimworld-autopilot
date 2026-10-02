using System;
using System.Collections.Generic;
using System.Linq;
using RIMAPI.Core;
using RIMAPI.Helpers;
using RIMAPI.Models;
using RimWorld;
using UnityEngine;
using Verse;
using Verse.AI;

namespace RIMAPI.Services
{
    public class BuilderService : IBuilderService
    {
        public ApiResult<ConstructionProjectsDto> GetConstructionProjects(int mapId)
        {
            try
            {
                var map = MapHelper.GetMapByID(mapId);
                if (map == null) return ApiResult<ConstructionProjectsDto>.Fail($"Map {mapId} not found.");
                // Count loose usable stock once, rather than rescanning the map
                // for each blueprint. These counts do not assert path reachability.
                var available = map.listerThings.AllThings
                    .Where(t => t.def.category == ThingCategory.Item && !t.IsForbidden(Faction.OfPlayer))
                    .GroupBy(t => t.def.defName)
                    .ToDictionary(g => g.Key, g => g.Sum(t => t.stackCount));
                var projects = map.listerThings.AllThings
                    .Where(t => t is Blueprint || t is Frame)
                    .Select(t =>
                    {
                        var target = t.def.entityDefToBuild;
                        var frame = t as Frame;
                        var constructible = t as IConstructible;
                        var needed = constructible?.TotalMaterialCost();
                        return new ConstructionProjectDto
                        {
                            ThingId = t.thingIDNumber,
                            Rotation = t.Rotation.AsInt,
                            DefName = target?.defName,
                            Label = target?.label ?? t.LabelCap,
                            Kind = t is Frame ? "frame" : "blueprint",
                            StuffDefName = constructible?.EntityToBuildStuff()?.defName ?? t.Stuff?.defName,
                            PercentComplete = frame?.PercentComplete ?? 0f,
                            MinimumConstructionSkill = (target as ThingDef)?.constructionSkillPrerequisite ?? 0,
                            MaterialsNeeded = needed?.Select(cost => new ConstructionMaterialDto
                            {
                                DefName = cost.thingDef.defName,
                                RequiredCount = constructible.ThingCountNeeded(cost.thingDef),
                                AvailableCount = available.TryGetValue(cost.thingDef.defName, out var count) ? count : 0,
                            }).Where(cost => cost.RequiredCount > 0).ToList(),
                            Position = new PositionDto { X = t.Position.x, Y = t.Position.y, Z = t.Position.z },
                        };
                    })
                    .OrderBy(p => p.Kind == "frame" ? 0 : 1)
                    .ThenByDescending(p => p.PercentComplete)
                    .ToList();
                return ApiResult<ConstructionProjectsDto>.Ok(new ConstructionProjectsDto { Projects = projects });
            }
            catch (Exception ex)
            {
                return ApiResult<ConstructionProjectsDto>.Fail(ex.Message);
            }
        }

        public ApiResult<PrioritizeConstructionResultDto> PrioritizeConstruction(PrioritizeConstructionRequestDto request)
        {
            try
            {
                if (request == null) return ApiResult<PrioritizeConstructionResultDto>.Fail("Construction request is required.");
                var map = MapHelper.GetMapByID(request.MapId);
                if (map == null) return ApiResult<PrioritizeConstructionResultDto>.Fail($"Map {request.MapId} not found.");
                var project = map.listerThings.AllThings.FirstOrDefault(t =>
                    t.thingIDNumber == request.ProjectThingId && (t is Blueprint || t is Frame));
                if (project == null) return ConstructionNotApplied("Construction project no longer exists.");
                var pawn = map.mapPawns.FreeColonists.FirstOrDefault(p => p.thingIDNumber == request.PawnId);
                if (pawn == null || pawn.Dead || pawn.Downed) return ConstructionNotApplied("Selected builder is unavailable.");
                if (pawn.WorkTypeIsDisabled(WorkTypeDefOf.Construction))
                    return ConstructionNotApplied("Selected pawn cannot do Construction.");

                Job job = null;
                if (project is Frame)
                {
                    var finish = DefDatabase<WorkGiverDef>.GetNamedSilentFail("ConstructFinishFrames")?.Worker as WorkGiver_Scanner;
                    job = finish?.JobOnThing(pawn, project, true);
                    if (job == null)
                    {
                        var deliver = DefDatabase<WorkGiverDef>.GetNamedSilentFail("ConstructDeliverResourcesToFrames")?.Worker as WorkGiver_Scanner;
                        job = deliver?.JobOnThing(pawn, project, true);
                    }
                }
                else
                {
                    var deliver = DefDatabase<WorkGiverDef>.GetNamedSilentFail("ConstructDeliverResourcesToBlueprints")?.Worker as WorkGiver_Scanner;
                    job = deliver?.JobOnThing(pawn, project, true);
                }
                if (job == null) return ConstructionNotApplied("The project is blocked, lacks reachable material, or exceeds the builder's skill.");
                if (!pawn.jobs.TryTakeOrderedJob(job)) return ConstructionNotApplied("Selected builder could not accept the construction job.");
                return ApiResult<PrioritizeConstructionResultDto>.Ok(new PrioritizeConstructionResultDto { Applied = true });
            }
            catch (Exception ex)
            {
                return ApiResult<PrioritizeConstructionResultDto>.Fail(ex.Message);
            }
        }

        private static ApiResult<PrioritizeConstructionResultDto> ConstructionNotApplied(string reason)
        {
            return ApiResult<PrioritizeConstructionResultDto>.Ok(new PrioritizeConstructionResultDto
            {
                Applied = false,
                Reason = reason,
            });
        }

        public ApiResult<BlueprintDto> CopyArea(CopyAreaRequestDto request)
        {
            try
            {
                var map = MapHelper.GetMapByID(request.MapId);
                if (map == null) return ApiResult<BlueprintDto>.Fail($"Map {request.MapId} not found.");

                // Normalize Coordinates (ensure min/max are correct regardless of A/B order)
                int minX = Mathf.Min(request.PointA.X, request.PointB.X);
                int minZ = Mathf.Min(request.PointA.Z, request.PointB.Z);
                int maxX = Mathf.Max(request.PointA.X, request.PointB.X);
                int maxZ = Mathf.Max(request.PointA.Z, request.PointB.Z);

                var blueprint = new BlueprintDto
                {
                    Width = (maxX - minX) + 1,
                    Height = (maxZ - minZ) + 1
                };

                // Track added things to avoid duplicates for multi-tile buildings (like Geothermal Generators)
                HashSet<Thing> addedThings = new HashSet<Thing>();

                CellRect rect = new CellRect(minX, minZ, blueprint.Width, blueprint.Height);

                // Iterate every cell
                foreach (IntVec3 cell in rect)
                {
                    if (!cell.InBounds(map)) continue;

                    // 1. Save Terrain (Floor)
                    TerrainDef terrain = map.terrainGrid.TerrainAt(cell);
                    if (terrain != null && terrain.Removable) // Only copy constructed floors, not soil/sand
                    {
                        blueprint.Floors.Add(new SavedTerrainDto
                        {
                            DefName = terrain.defName,
                            RelX = cell.x - minX,
                            RelZ = cell.z - minZ
                        });
                    }

                    // 2. Save Buildings
                    List<Thing> things = cell.GetThingList(map);
                    foreach (var thing in things)
                    {
                        // We only want Buildings, created by players, that we haven't added yet
                        if (thing.def.category == ThingCategory.Building &&
                            thing.def.saveCompressible == false && // Skip filth/motes
                            !addedThings.Contains(thing))
                        {
                            // Important: For multi-tile buildings, only add them if their "InteractionCell" or "Position" is inside or near our rect.
                            // To be safe, we just check if it's the first time we see it.
                            addedThings.Add(thing);

                            blueprint.Buildings.Add(new SavedBuildingDto
                            {
                                DefName = thing.def.defName,
                                StuffDefName = thing.Stuff?.defName, // Material (WoodLog, Steel, etc)
                                RelX = thing.Position.x - minX, // Save relative to anchor
                                RelZ = thing.Position.z - minZ,
                                Rotation = thing.Rotation.AsInt
                            });
                        }
                    }
                }

                return ApiResult<BlueprintDto>.Ok(blueprint);
            }
            catch (Exception ex)
            {
                LogApi.Error($"Copy Error: {ex}");
                return ApiResult<BlueprintDto>.Fail(ex.Message);
            }
        }

        public ApiResult PasteArea(PasteAreaRequestDto request)
        {
            try
            {
                if (request.Blueprint == null) return ApiResult.Fail("Blueprint is null");

                var map = MapHelper.GetMapByID(request.MapId);
                if (map == null) return ApiResult.Fail($"Map {request.MapId} not found.");

                int anchorX = request.Position.X;
                int anchorZ = request.Position.Z;

                // 1. Paste Floors
                foreach (var floorDto in request.Blueprint.Floors)
                {
                    IntVec3 pos = new IntVec3(anchorX + floorDto.RelX, 0, anchorZ + floorDto.RelZ);
                    if (pos.InBounds(map))
                    {
                        var terrainDef = DefDatabase<TerrainDef>.GetNamedSilentFail(floorDto.DefName);
                        if (terrainDef != null)
                        {
                            map.terrainGrid.SetTerrain(pos, terrainDef);
                        }
                    }
                }

                // 2. Paste Buildings
                foreach (var buildDto in request.Blueprint.Buildings)
                {
                    IntVec3 pos = new IntVec3(anchorX + buildDto.RelX, 0, anchorZ + buildDto.RelZ);

                    if (!pos.InBounds(map)) continue;

                    // Resolve Definitions
                    ThingDef thingDef = DefDatabase<ThingDef>.GetNamedSilentFail(buildDto.DefName);
                    if (thingDef == null) continue;

                    ThingDef stuffDef = null;
                    if (!string.IsNullOrEmpty(buildDto.StuffDefName))
                    {
                        stuffDef = DefDatabase<ThingDef>.GetNamedSilentFail(buildDto.StuffDefName);
                    }

                    // Optional: Clear obstacles in the spot before spawning
                    if (request.ClearObstacles)
                    {
                        var obstacles = pos.GetThingList(map).ToList(); // Copy list
                        foreach (var obs in obstacles)
                        {
                            // Destroy items/buildings in the way. Don't destroy pawns.
                            if (obs.def.category == ThingCategory.Building || obs.def.category == ThingCategory.Item || obs.def.category == ThingCategory.Plant)
                            {
                                obs.Destroy();
                            }
                        }
                    }

                    // Create & Spawn
                    Thing thing = ThingMaker.MakeThing(thingDef, stuffDef);
                    thing.Rotation = new Rot4(buildDto.Rotation);

                    // Force the faction to be the player's
                    if (thing.def.CanHaveFaction)
                    {
                        thing.SetFaction(Faction.OfPlayer);
                    }

                    GenSpawn.Spawn(thing, pos, map, thing.Rotation);
                }

                return ApiResult.Ok();
            }
            catch (Exception ex)
            {
                LogApi.Error($"Paste Error: {ex}");
                return ApiResult.Fail(ex.Message);
            }
        }

        public ApiResult<BuildingSiteOptionsDto> GetBuildingSiteOptions(BuildingSiteOptionsRequestDto request)
        {
            if (request == null || string.IsNullOrWhiteSpace(request.DefName))
                return ApiResult<BuildingSiteOptionsDto>.Fail("A building def_name is required.");
            var map = MapHelper.GetMapByID(request.MapId);
            if (map == null)
                return ApiResult<BuildingSiteOptionsDto>.Fail($"Map {request.MapId} not found.");
            var def = DefDatabase<ThingDef>.GetNamedSilentFail(request.DefName);
            if (def != null && (def.category != ThingCategory.Building || def.designationCategory == null)) def = null;
            var terrain = def == null ? DefDatabase<TerrainDef>.GetNamedSilentFail(request.DefName) : null;
            if (def == null && (terrain == null || terrain.designationCategory == null))
                return ApiResult<BuildingSiteOptionsDto>.Fail($"{request.DefName} is not a loaded player construction def.");
            var result = new BuildingSiteOptionsDto { DefName = request.DefName, StuffDefName = request.StuffDefName };
            bool researchLocked = def != null
                ? def.researchPrerequisites != null && def.researchPrerequisites.Any(project => project != null && !project.IsFinished)
                : terrain.researchPrerequisites != null && terrain.researchPrerequisites.Any(project => project != null && !project.IsFinished);
            if (researchLocked)
            {
                result.Reason = "Required research is not finished.";
                return ApiResult<BuildingSiteOptionsDto>.Ok(result);
            }
            ThingDef stuff = null;
            if (def != null && def.costStuffCount > 0)
            {
                stuff = DefDatabase<ThingDef>.GetNamedSilentFail(request.StuffDefName);
                if (stuff?.stuffProps?.categories == null || def.stuffCategories == null
                    || !stuff.stuffProps.categories.Any(def.stuffCategories.Contains))
                {
                    result.Reason = "A compatible construction material is required.";
                    return ApiResult<BuildingSiteOptionsDto>.Ok(result);
                }
            }
            int nearX = Mathf.Clamp(request.Near?.X ?? map.Size.x / 2, 0, map.Size.x - 1);
            int nearZ = Mathf.Clamp(request.Near?.Z ?? map.Size.z / 2, 0, map.Size.z - 1);
            int radius = Mathf.Clamp(request.Radius, 1, 250);
            int limit = Mathf.Clamp(request.Limit, 1, 12);
            bool instantSpot = def != null && IsInstantBuildingSpot(def);
            var rejectionCounts = new Dictionary<string, int>();
            var cells = new List<IntVec3>();
            for (int z = Mathf.Max(0, nearZ - radius); z <= Mathf.Min(map.Size.z - 1, nearZ + radius); z++)
                for (int x = Mathf.Max(0, nearX - radius); x <= Mathf.Min(map.Size.x - 1, nearX + radius); x++)
                    cells.Add(new IntVec3(x, 0, z));
            foreach (var cell in cells.OrderBy(pos => (pos.x - nearX) * (pos.x - nearX) + (pos.z - nearZ) * (pos.z - nearZ)))
            {
                for (int rotation = 0; rotation < (terrain == null ? 4 : 1); rotation++)
                {
                    var rot = new Rot4(rotation);
                    try
                    {
                        bool accepted;
                        if (instantSpot)
                        {
                            var rect = GenAdj.OccupiedRect(cell, rot, def.Size);
                            accepted = rect.All(pos => pos.InBounds(map) && !pos.GetThingList(map).Any(thing =>
                                thing is Building || thing is Blueprint || thing is Frame));
                        }
                        else
                        {
                            var report = terrain == null
                                ? GenConstruct.CanPlaceBlueprintAt(def, cell, rot, map, false, null)
                                : GenConstruct.CanPlaceBlueprintAt(terrain, cell, rot, map, false, null);
                            accepted = report.Accepted;
                            if (!accepted && !string.IsNullOrEmpty(report.Reason))
                            {
                                rejectionCounts.TryGetValue(report.Reason, out int previous);
                                rejectionCounts[report.Reason] = previous + 1;
                            }
                        }
                        if (!accepted) continue;
                        result.Sites.Add(new BuildingSiteOptionDto
                        {
                            Position = new PositionDto { X = cell.x, Y = 0, Z = cell.z },
                            Rotation = rotation,
                            Distance = Math.Abs(cell.x - nearX) + Math.Abs(cell.z - nearZ),
                        });
                        break;
                    }
                    catch (Exception error)
                    {
                        rejectionCounts.TryGetValue(error.Message, out int previous);
                        rejectionCounts[error.Message] = previous + 1;
                    }
                }
                if (result.Sites.Count >= limit) break;
            }
            if (result.Sites.Count == 0)
                result.Reason = rejectionCounts.OrderByDescending(row => row.Value)
                    .Select(row => row.Key).FirstOrDefault() ?? "No valid site was found in the search radius.";
            return ApiResult<BuildingSiteOptionsDto>.Ok(result);
        }

        private static bool IsInstantBuildingSpot(ThingDef def)
        {
            return def.defName == "SleepingSpot" || def.defName == "AnimalSleepingSpot"
                || def.defName == "ButcherSpot";
        }

        public ApiResult PlaceBlueprints(PasteAreaRequestDto request)
        {
            try
            {
                if (request?.Blueprint == null || request.Position == null)
                    return ApiResult.Fail("Blueprint and position are required.");

                var map = MapHelper.GetMapByID(request.MapId);
                if (map == null) return ApiResult.Fail($"Map {request.MapId} not found.");

                int anchorX = request.Position.X;
                int anchorZ = request.Position.Z;
                int count = 0;
                var warnings = new List<string>();
                int requested = (request.Blueprint.Floors?.Count ?? 0) + (request.Blueprint.Buildings?.Count ?? 0);
                if (requested == 0) return ApiResult.Fail("Blueprint contains no buildings or floors.");

                // 1. Place Floor Blueprints
                foreach (var floorDto in request.Blueprint.Floors ?? new List<SavedTerrainDto>())
                {
                    try
                    {
                        IntVec3 pos = new IntVec3(anchorX + floorDto.RelX, 0, anchorZ + floorDto.RelZ);
                        if (!pos.InBounds(map)) { warnings.Add($"{floorDto.DefName}: outside map."); continue; }
                        TerrainDef terrainDef = DefDatabase<TerrainDef>.GetNamedSilentFail(floorDto.DefName);
                        if (terrainDef == null) { warnings.Add($"{floorDto.DefName}: unknown floor."); continue; }
                        var report = GenConstruct.CanPlaceBlueprintAt(terrainDef, pos, Rot4.North, map, false, null);
                        if (!report.Accepted) { warnings.Add($"{floorDto.DefName}: {report.Reason}"); continue; }
                        GenConstruct.PlaceBlueprintForBuild(terrainDef, pos, map, Rot4.North, Faction.OfPlayer, null);
                        if (pos.GetThingList(map).Any(t => t is Blueprint && t.def.entityDefToBuild == terrainDef)) count++;
                        else warnings.Add($"{floorDto.DefName}: no floor blueprint was created.");
                    }
                    catch (Exception error) { warnings.Add($"{floorDto?.DefName}: {error.Message}"); }
                }

                // 2. Place Building Blueprints
                foreach (var buildDto in request.Blueprint.Buildings ?? new List<SavedBuildingDto>())
                {
                    try
                    {
                    IntVec3 pos = new IntVec3(anchorX + buildDto.RelX, 0, anchorZ + buildDto.RelZ);

                    if (!pos.InBounds(map)) { warnings.Add($"{buildDto.DefName}: outside map."); continue; }

                    // Resolve Definitions
                    ThingDef thingDef = DefDatabase<ThingDef>.GetNamedSilentFail(buildDto.DefName);
                    if (thingDef == null || thingDef.category != ThingCategory.Building || thingDef.designationCategory == null)
                    { warnings.Add($"{buildDto.DefName}: unknown or non-player building."); continue; }
                    if (thingDef.researchPrerequisites != null
                        && thingDef.researchPrerequisites.Any(project => project != null && !project.IsFinished))
                    { warnings.Add($"{buildDto.DefName}: research is not finished."); continue; }

                    ThingDef stuffDef = null;
                    if (!string.IsNullOrEmpty(buildDto.StuffDefName))
                    {
                        stuffDef = DefDatabase<ThingDef>.GetNamedSilentFail(buildDto.StuffDefName);
                    }
                    if (thingDef.costStuffCount > 0 && (stuffDef?.stuffProps?.categories == null
                        || thingDef.stuffCategories == null
                        || !stuffDef.stuffProps.categories.Any(thingDef.stuffCategories.Contains)))
                    { warnings.Add($"{buildDto.DefName}: compatible stuff is required."); continue; }

                    Rot4 rotation = new Rot4(buildDto.Rotation);
                    CellRect occupied = GenAdj.OccupiedRect(pos, rotation, thingDef.Size);
                    if (occupied.Any(cell => !cell.InBounds(map)))
                    { warnings.Add($"{buildDto.DefName}: footprint extends outside map."); continue; }
                    bool isInstantSpot = IsInstantBuildingSpot(thingDef);
                    Thing existingThing = occupied
                        .SelectMany(cell => cell.GetThingList(map))
                        .FirstOrDefault(t =>
                        t.Position == pos && (t.def == thingDef
                        || ((t is Blueprint || t is Frame) && t.def.entityDefToBuild == thingDef)));
                    if (existingThing != null)
                    {
                        if (isInstantSpot && (existingThing is Blueprint || existingThing is Frame))
                        {
                            // Migrate invalid spot blueprints created by older RIMAPI builds.
                            existingThing.Destroy(DestroyMode.Cancel);
                        }
                        else
                        {
                            if (isInstantSpot && existingThing.Faction != Faction.OfPlayer)
                                existingThing.SetFaction(Faction.OfPlayer);
                            count++;
                            continue;
                        }
                    }

                    // A planned floor is a Blueprint/Frame too. It must not
                    // block beds, lamps or workstations in the same room;
                    // only an existing building or another *thing* plan does.
                    bool isConduit = thingDef.defName == "PowerConduit"
                        || thingDef.defName == "HiddenConduit"
                        || thingDef.defName == "WaterproofConduit";
                    bool conflictsWithPlan = !isConduit && occupied.Any(cell => cell.InBounds(map) && cell.GetThingList(map).Any(t =>
                        t is Building || ((t is Blueprint || t is Frame)
                            && t.def.entityDefToBuild is ThingDef)));
                    if (conflictsWithPlan)
                    { warnings.Add($"{buildDto.DefName}: footprint overlaps another building or plan."); continue; }

                    // These are architect "spots", not construction projects in vanilla.
                    // Spawning only these zero-cost markers avoids invalid frames and
                    // the misleading "Construction botched" message.
                    if (isInstantSpot)
                    {
                        Thing spot = ThingMaker.MakeThing(thingDef);
                        spot.SetFaction(Faction.OfPlayer);
                        GenSpawn.Spawn(spot, pos, map, rotation);
                        count++;
                        continue;
                    }

                    // Create Blueprint
                    var placement = GenConstruct.CanPlaceBlueprintAt(thingDef, pos, rotation, map, false, null);
                    if (!placement.Accepted)
                    { warnings.Add($"{buildDto.DefName}: {placement.Reason}"); continue; }
                    Precept_ThingStyle styleSource = null;
                    if (ModsConfig.IdeologyActive && Faction.OfPlayer?.ideos?.PrimaryIdeo != null)
                    {
                        styleSource = Faction.OfPlayer.ideos.PrimaryIdeo.PreceptsListForReading
                            .OfType<Precept_ThingStyle>()
                            .FirstOrDefault(precept => precept.ThingDef == thingDef);
                    }
                    GenConstruct.PlaceBlueprintForBuild(
                        thingDef,
                        pos,
                        map,
                        rotation,
                        Faction.OfPlayer,
                        stuffDef,
                        styleSource
                    );
                    if (pos.GetThingList(map).Any(t => t is Blueprint && t.def.entityDefToBuild == thingDef)) count++;
                    else warnings.Add($"{buildDto.DefName}: no building blueprint was created.");
                    }
                    catch (Exception error) { warnings.Add($"{buildDto?.DefName}: {error.Message}"); }
                }

                if (count == 0) return ApiResult.Fail(string.Join("; ", warnings.Take(8)));
                if (request.Blueprint.Roof)
                {
                    for (int dx = 1; dx < request.Blueprint.Width - 1; dx++)
                    for (int dz = 1; dz < request.Blueprint.Height - 1; dz++)
                    {
                        var cell = new IntVec3(request.Position.X + dx, 0, request.Position.Z + dz);
                        if (cell.InBounds(map)) map.areaManager.BuildRoof[cell] = true;
                    }
                }
                return warnings.Count == 0 ? ApiResult.Ok() : ApiResult.Partial(warnings);
            }
            catch (Exception ex)
            {
                LogApi.Error($"Blueprint Error: {ex}");
                return ApiResult.Fail(ex.Message);
            }
        }

        public ApiResult<CheckZoneResultDto> CheckZone(CheckZoneRequestDto request)
        {
            try
            {
                var map = MapHelper.GetMapByID(request.MapId);
                if (map == null) return ApiResult<CheckZoneResultDto>.Fail($"Map {request.MapId} not found.");

                if (request.PointA == null || request.PointB == null)
                    return ApiResult<CheckZoneResultDto>.Fail("PointA and PointB are required.");

                int minX = Mathf.Min(request.PointA.X, request.PointB.X);
                int minZ = Mathf.Min(request.PointA.Z, request.PointB.Z);
                int maxX = Mathf.Max(request.PointA.X, request.PointB.X);
                int maxZ = Mathf.Max(request.PointA.Z, request.PointB.Z);

                var issues = new CheckZoneIssuesDto();
                HashSet<Thing> processedThings = new HashSet<Thing>();

                CellRect rect = new CellRect(minX, minZ, (maxX - minX) + 1, (maxZ - minZ) + 1);

                foreach (IntVec3 cell in rect)
                {
                    if (!cell.InBounds(map)) continue;

                    // 1. Check Terrain (affordances)
                    TerrainDef terrain = map.terrainGrid.TerrainAt(cell);
                    if (terrain != null)
                    {
                        bool hasHeavyAffordance = terrain.affordances != null && 
                            terrain.affordances.Contains(TerrainAffordanceDefOf.Heavy);
                        if (!hasHeavyAffordance)
                        {
                            issues.Terrain.Add(new CheckZoneIssueDto
                            {
                                X = cell.x,
                                Z = cell.z,
                                DefName = terrain.defName,
                                Label = terrain.label
                            });
                        }
                    }

                    // 2. Check Things (Ores and Buildings)
                    List<Thing> things = cell.GetThingList(map);
                    foreach (var thing in things)
                    {
                        if (processedThings.Contains(thing)) continue;

                        // Check for mineable ores
                        if (thing.def.mineable)
                        {
                            processedThings.Add(thing);
                            issues.Ores.Add(new CheckZoneIssueDto
                            {
                                X = thing.Position.x,
                                Z = thing.Position.z,
                                DefName = thing.def.defName,
                                Label = thing.def.label
                            });
                        }
                        // Check for buildings
                        else if (thing.def.category == ThingCategory.Building)
                        {
                            processedThings.Add(thing);
                            issues.Buildings.Add(new CheckZoneIssueDto
                            {
                                X = thing.Position.x,
                                Z = thing.Position.z,
                                DefName = thing.def.defName,
                                Label = thing.def.label
                            });
                        }
                    }
                }

                // 3. Check Zones (Growing and Stockpile)
                foreach (Zone zone in map.zoneManager.AllZones)
                {
                    if (zone is Zone_Growing || zone is Zone_Stockpile)
                    {
                        foreach (IntVec3 cell in zone.cells)
                        {
                            if (cell.x >= minX && cell.x <= maxX && cell.z >= minZ && cell.z <= maxZ)
                            {
                                issues.Zones.Add(new CheckZoneIssueDto
                                {
                                    X = cell.x,
                                    Z = cell.z,
                                    DefName = zone.GetType().Name,
                                    Label = zone.label,
                                    ZoneType = zone is Zone_Growing ? "Growing" : "Stockpile"
                                });
                                break;
                            }
                        }
                    }
                }

                bool canBuild = issues.Terrain.Count == 0 && 
                                issues.Ores.Count == 0 && 
                                issues.Buildings.Count == 0 && 
                                issues.Zones.Count == 0;

                return ApiResult<CheckZoneResultDto>.Ok(new CheckZoneResultDto
                {
                    CanBuild = canBuild,
                    Issues = issues
                });
            }
            catch (Exception ex)
            {
                LogApi.Error($"CheckZone Error: {ex}");
                return ApiResult<CheckZoneResultDto>.Fail(ex.Message);
            }
        }
    }
}

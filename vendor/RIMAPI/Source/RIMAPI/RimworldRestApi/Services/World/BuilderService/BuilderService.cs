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
                var projects = map.listerThings.AllThings
                    .Where(t => t is Blueprint || t is Frame)
                    .Select(t =>
                    {
                        var target = t.def.entityDefToBuild;
                        var frame = t as Frame;
                        return new ConstructionProjectDto
                        {
                            ThingId = t.thingIDNumber,
                            DefName = target?.defName,
                            Label = target?.label ?? t.LabelCap,
                            Kind = t is Frame ? "frame" : "blueprint",
                            StuffDefName = t.Stuff?.defName,
                            PercentComplete = frame?.PercentComplete ?? 0f,
                            Position = new PositionDto { X = t.Position.x, Y = t.Position.y, Z = t.Position.z },
                        };
                    })
                    .OrderBy(p => p.Kind == "frame" ? 0 : 1)
                    .ThenByDescending(p => p.PercentComplete)
                    .Take(100)
                    .ToList();
                return ApiResult<ConstructionProjectsDto>.Ok(new ConstructionProjectsDto { Projects = projects });
            }
            catch (Exception ex)
            {
                return ApiResult<ConstructionProjectsDto>.Fail(ex.Message);
            }
        }

        public ApiResult PrioritizeConstruction(PrioritizeConstructionRequestDto request)
        {
            try
            {
                var map = MapHelper.GetMapByID(request.MapId);
                if (map == null) return ApiResult.Fail($"Map {request.MapId} not found.");
                var project = map.listerThings.AllThings.FirstOrDefault(t =>
                    t.thingIDNumber == request.ProjectThingId && (t is Blueprint || t is Frame));
                if (project == null) return ApiResult.Fail("Construction project not found.");
                var pawn = map.mapPawns.FreeColonists.FirstOrDefault(p => p.thingIDNumber == request.PawnId);
                if (pawn == null || pawn.Dead || pawn.Downed) return ApiResult.Fail("Selected builder is unavailable.");
                if (pawn.WorkTypeIsDisabled(WorkTypeDefOf.Construction))
                    return ApiResult.Fail("Selected pawn cannot do Construction.");

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
                if (job == null) return ApiResult.Fail("The project is blocked, lacks reachable material, or exceeds the builder's skill.");
                if (!pawn.jobs.TryTakeOrderedJob(job)) return ApiResult.Fail("Selected builder could not accept the construction job.");
                return ApiResult.Ok();
            }
            catch (Exception ex)
            {
                return ApiResult.Fail(ex.Message);
            }
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

        public ApiResult PlaceBlueprints(PasteAreaRequestDto request)
        {
            try
            {
                if (request.Blueprint == null) return ApiResult.Fail("Blueprint is null");

                var map = MapHelper.GetMapByID(request.MapId);
                if (map == null) return ApiResult.Fail($"Map {request.MapId} not found.");

                int anchorX = request.Position.X;
                int anchorZ = request.Position.Z;
                int count = 0;

                // 1. Place Floor Blueprints
                foreach (var floorDto in request.Blueprint.Floors)
                {
                    IntVec3 pos = new IntVec3(anchorX + floorDto.RelX, 0, anchorZ + floorDto.RelZ);
                    if (pos.InBounds(map))
                    {
                        TerrainDef terrainDef = DefDatabase<TerrainDef>.GetNamedSilentFail(floorDto.DefName);
                        if (terrainDef != null)
                        {
                            // PlaceBlueprintForBuild works for TerrainDefs too
                            GenConstruct.PlaceBlueprintForBuild(terrainDef, pos, map, Rot4.North, Faction.OfPlayer, null);
                            count++;
                        }
                    }
                }

                // 2. Place Building Blueprints
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

                    Rot4 rotation = new Rot4(buildDto.Rotation);
                    CellRect occupied = GenAdj.OccupiedRect(pos, rotation, thingDef.Size);
                    bool isInstantSpot = thingDef.defName == "SleepingSpot"
                        || thingDef.defName == "AnimalSleepingSpot"
                        || thingDef.defName == "ButcherSpot";
                    Thing existingThing = occupied
                        .Where(cell => cell.InBounds(map))
                        .SelectMany(cell => cell.GetThingList(map))
                        .FirstOrDefault(t =>
                        t.def == thingDef
                        || ((t is Blueprint || t is Frame) && t.def.entityDefToBuild == thingDef));
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
                            continue;
                        }
                    }

                    // A planned floor is a Blueprint/Frame too. It must not
                    // block beds, lamps or workstations in the same room;
                    // only an existing building or another *thing* plan does.
                    bool conflictsWithPlan = occupied.Any(cell => cell.InBounds(map) && cell.GetThingList(map).Any(t =>
                        t is Building || ((t is Blueprint || t is Frame)
                            && t.def.entityDefToBuild is ThingDef)));
                    if (conflictsWithPlan)
                        continue;

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
                    // Note: GenConstruct handles checking if it can be placed, checking affordance, etc.
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
                    count++;
                }

                return ApiResult.Ok();
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

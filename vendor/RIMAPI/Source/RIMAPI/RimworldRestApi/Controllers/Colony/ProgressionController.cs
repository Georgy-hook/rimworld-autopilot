using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Helpers;
using RIMAPI.Http;
using RimWorld;
using Verse;

namespace RIMAPI.Controllers
{
    public class ProgressionController
    {
        [Get("/api/v1/colony/progression")]
        [EndpointMetadata("Read connected escape-ship parts and engine launch blockers; does not start a reactor or launch")]
        public async Task GetProgression(HttpListenerContext context)
        {
            var ships = new List<ProgressionShipDto>();
            var visited = new HashSet<int>();
            bool filterMap = int.TryParse(context.Request.QueryString["map_id"], out int requestedMap);
            foreach (var map in Find.Maps.Where(m => !filterMap || m.uniqueID == requestedMap))
            {
                foreach (var root in map.listerBuildings.allBuildingsColonist.Where(b => b.def.building.shipPart))
                {
                    if (visited.Contains(root.thingIDNumber)) continue;
                    var attached = ShipUtility.ShipBuildingsAttachedTo(root).ToList();
                    foreach (var part in attached) visited.Add(part.thingIDNumber);
                    ships.Add(new ProgressionShipDto {
                        MapId = map.uniqueID, RootId = root.thingIDNumber,
                        Parts = attached.GroupBy(b => b.def.defName).ToDictionary(g => g.Key, g => g.Count()),
                        RequiredParts = ShipUtility.RequiredParts().ToDictionary(p => p.Key.defName, p => p.Value),
                        LaunchBlockers = ShipUtility.LaunchFailReasons(root).ToList(),
                        HasHibernatingParts = ShipUtility.HasHibernatingParts(root),
                        Countdown = ShipCountdown.CountingDown,
                        StartupDays = attached.Select(b => b.TryGetComp<CompHibernatable>()).Where(c => c != null).Select(c => c.Props.startupDays).DefaultIfEmpty(0f).Max(),
                        Passengers = attached.OfType<Building_CryptosleepCasket>().Where(c => c.HasAnyContents).Select(c => c.ContainedThing.LabelCap.ToString()).ToList(),
                        ColonistsAtHome = map.mapPawns.FreeColonistsSpawned.Select(p => p.LabelShortCap.ToString()).ToList(),
                        MobileCombatColonists = map.mapPawns.FreeColonistsSpawned.Count(p => !p.Downed && !p.InMentalState && !p.WorkTagIsDisabled(WorkTags.Violent)),
                        ArmedMobileCombatColonists = map.mapPawns.FreeColonistsSpawned.Count(p => !p.Downed && !p.InMentalState && !p.WorkTagIsDisabled(WorkTags.Violent) && p.equipment?.Primary != null),
                        DownedColonists = map.mapPawns.FreeColonistsSpawned.Count(p => p.Downed),
                        HostilePawns = map.mapPawns.AllPawnsSpawned.Count(p => !p.Dead && p.HostileTo(Faction.OfPlayer)),
                        TotalItemNutrition = map.listerThings.AllThings.Where(t => t.def.ingestible != null && t.def.IsNutritionGivingIngestible && t.def.category == ThingCategory.Item).Sum(t => t.GetStatValue(StatDefOf.Nutrition) * t.stackCount),
                        BoardingOptions = ProgressionBoardingHelper.Options(root)
                    });
                }
            }
            await context.SendJsonResponse(ApiResult<List<ProgressionShipDto>>.Ok(ships));
        }

        [Post("/api/v1/colony/progression/ship")]
        [EndpointMetadata("Perform a validated ordinary escape ship startup or launch, after explicit decision confirmation")]
        public async Task ActOnShip(HttpListenerContext context)
        {
            var id = RequestParser.GetIntParameter(context, "root_id");
            var mapId = RequestParser.GetIntParameter(context, "map_id");
            var action = RequestParser.GetStringParameter(context, "action");
            var confirmed = RequestParser.GetBooleanParameter(context, "confirmed");
            var root = Find.Maps.FirstOrDefault(m => m.uniqueID == mapId)?.listerBuildings.allBuildingsColonist.FirstOrDefault(b => b.thingIDNumber == id && b.def.building.shipPart);
            if (!confirmed || root == null || ShipCountdown.CountingDown) {
                await context.SendJsonResponse(ApiResult<string>.Fail("Unconfirmed, stale ship or launch already counting down")); return;
            }
            if (action == "start" && ShipUtility.HasHibernatingParts(root)) {
                var parts = ShipUtility.ShipBuildingsAttachedTo(root).ToList();
                if (!ShipUtility.RequiredParts().All(p => parts.Count(b => b.def == p.Key) >= p.Value)) {
                    await context.SendJsonResponse(ApiResult<string>.Fail("Connected ship parts changed")); return;
                }
                ShipUtility.StartupHibernatingParts(root);
                await context.SendJsonResponse(ApiResult<string>.Ok(!ShipUtility.HasHibernatingParts(root) ? "reactor_start_requested" : "reactor_not_started")); return;
            }
            if (action == "launch" && !ShipUtility.LaunchFailReasons(root).Any()) {
                var computer = ShipUtility.ShipBuildingsAttachedTo(root).OfType<Building_ShipComputerCore>().FirstOrDefault();
                var command = computer?.GetGizmos().OfType<Command_Action>().FirstOrDefault(c => c.defaultLabel == "CommandShipLaunch".Translate().ToString() && !c.Disabled);
                if (command != null) {
                    command.action();
                    await context.SendJsonResponse(ApiResult<string>.Ok(ShipCountdown.CountingDown ? "launch_countdown_started" : "launch_not_started")); return;
                }
            }
            await context.SendJsonResponse(ApiResult<string>.Fail("Engine ship conditions changed or action unsupported"));
        }

        [Post("/api/v1/colony/progression/board")]
        [EndpointMetadata("Order ordinary enter or carry-to ship cryptosleep job after live reservation/reachability/defense validation")]
        public async Task BoardShip(HttpListenerContext context)
        {
            var rootId = RequestParser.GetIntParameter(context, "root_id");
            var mapId = RequestParser.GetIntParameter(context, "map_id");
            var pawnId = RequestParser.GetIntParameter(context, "pawn_id");
            var workerId = RequestParser.GetIntParameter(context, "worker_id");
            var casketId = RequestParser.GetIntParameter(context, "casket_id");
            var root = Find.Maps.FirstOrDefault(m => m.uniqueID == mapId)?.listerBuildings.allBuildingsColonist.FirstOrDefault(b => b.thingIDNumber == rootId && b.def.building.shipPart);
            var confirmed = RequestParser.GetBooleanParameter(context, "confirmed");
            await context.SendJsonResponse(ApiResult<string>.Ok(confirmed && ProgressionBoardingHelper.Order(root, pawnId, workerId, casketId) ? "boarding_job_started" : "boarding_not_started"));
        }
    }

    public class ProgressionShipDto
    {
        public int MapId { get; set; }
        public int RootId { get; set; }
        public Dictionary<string, int> Parts { get; set; }
        public Dictionary<string, int> RequiredParts { get; set; }
        public List<string> LaunchBlockers { get; set; }
        public bool HasHibernatingParts { get; set; }
        public bool Countdown { get; set; }
        public float StartupDays { get; set; }
        public List<string> Passengers { get; set; }
        public List<string> ColonistsAtHome { get; set; }
        public int MobileCombatColonists { get; set; }
        public int ArmedMobileCombatColonists { get; set; }
        public int DownedColonists { get; set; }
        public int HostilePawns { get; set; }
        public float TotalItemNutrition { get; set; }
        public List<ProgressionBoardingDto> BoardingOptions { get; set; }
    }
}

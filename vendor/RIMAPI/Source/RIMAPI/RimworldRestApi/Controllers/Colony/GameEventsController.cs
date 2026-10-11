using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Http;
using RIMAPI.Models;
using RIMAPI.Services;
using RIMAPI.Helpers;
using System.Linq;
using RimWorld;
using Verse;

namespace RIMAPI.Controllers
{
    public class GameEventsController
    {
        private readonly IIncidentService _incidentService;

        public GameEventsController(IIncidentService incidentService)
        {
            _incidentService = incidentService;
        }

        [Get("/api/v1/quests")]
        public async Task GetQuestsData(HttpListenerContext context)
        {
            var mapId = RequestParser.GetMapId(context);
            var result = _incidentService.GetQuestsData(mapId);
            await context.SendJsonResponse(result);
        }

        [Get("/api/v1/incidents")]
        [EndpointMetadata("Get map incidents")]
        public async Task GetIncidentsData(HttpListenerContext context)
        {
            var mapId = RequestParser.GetMapId(context);
            var result = _incidentService.GetIncidentsData(mapId);
            await context.SendJsonResponse(result);
        }

        [Get("/api/v1/lords")]
        [EndpointMetadata("Get lords on map (AI raid managing objects)")]
        public async Task GetLordsData(HttpListenerContext context)
        {
            var mapId = RequestParser.GetMapId(context);
            var result = _incidentService.GetLordsData(mapId);
            await context.SendJsonResponse(result);
        }

        [Post("/api/v1/incident/trigger")]
        [EndpointMetadata("Trigger game incident")]
        public async Task TriggerIncident(HttpListenerContext context)
        {
            var requestData = await context.Request.ReadBodyAsync<TriggerIncidentRequestDto>();
            var result = _incidentService.TriggerIncident(requestData);
            await context.SendJsonResponse(result);
        }

        [Get("/api/v1/incidents/top")]
        public async Task GetIncidentsTopChance(HttpListenerContext context)
        {
            var result = _incidentService.GetTopIncidents();
            await context.SendJsonResponse(result);
        }

        [Get("/api/v1/incident/chance")]
        public async Task GetIncidentChance(HttpListenerContext context)
        {
            var requestData = await context.Request.ReadBodyAsync<IncidentChanceRequestDto>();
            var result = _incidentService.GetIncidentChance(requestData);
            await context.SendJsonResponse(result);
        }

        [Get("/api/v1/events/catalog")]
        [EndpointMetadata("List every loaded vanilla, DLC and mod incident definition")]
        public async Task GetEventCatalog(HttpListenerContext context)
        {
            await context.SendJsonResponse(GameEventAutomationHelper.GetCatalog());
        }

        [Get("/api/v1/quests/catalog")]
        [EndpointMetadata("Every loaded quest script, including DLC, mods and internal utility scripts; never generates quests")]
        public async Task QuestCatalog(HttpListenerContext context)
        {
            await context.SendJsonResponse(ApiResult<object>.Ok(DefDatabase<QuestScriptDef>.AllDefsListForReading
                .Select(d => new { quest_def = d.defName, mod = d.modContentPack?.Name,
                    root = d.root?.GetType().Name, auto_accept = d.autoAccept,
                    hidden = d.defaultHidden, random_offer = d.randomlySelectable,
                    special = d.isRootSpecial, increases_population = d.rootIncreasesPopulation,
                    description_rules = d.questDescriptionRules?.Rules.Select(r => r.ToString()).ToArray(),
                    name_description_rules = d.questDescriptionAndNameRules?.Rules.Select(r => r.ToString()).ToArray() }).ToArray()));
        }

        [Get("/api/v1/quest/offer")]
        [EndpointMetadata("Fresh public quest terms, exact reward groups, eligible accepters and stable offer version")]
        public async Task QuestOffer(HttpListenerContext context)
        {
            int id = RequestParser.GetIntParameter(context, "quest_id");
            var quest = Find.QuestManager.QuestsListForReading.FirstOrDefault(q => q != null && q.id == id && !q.hidden && !q.hiddenInUI);
            if (quest == null) { await context.SendJsonResponse(ApiResult<QuestDto>.Fail("quest_no_longer_active")); return; }
            QuestDto offer=null;var errors=new System.Collections.Generic.Dictionary<string,string>();
            if(!ObservationBoundary.Read("quest:"+id,()=>quest.Historical ? null : GameEventAutomationHelper.ToQuestDto(quest),row=>offer=row,errors,
                error=>Log.ErrorOnce($"[RIMAPI] Public quest offer {id} failed: {error}",("RIMAPI.quest.offer."+id).GetHashCode())))
                offer=new QuestDto{Id=id,ReadStatus="unavailable",ReadError=errors["quest:"+id],CanAccept=false,
                    AcceptanceReason="quest_read_unavailable",Disclosure="Cannot read complete fresh terms; acceptance prohibited."};
            await context.SendJsonResponse(offer == null ? ApiResult<QuestDto>.Fail("quest_no_longer_active") : ApiResult<QuestDto>.Ok(offer));
        }

        [Get("/api/v1/events/context")]
        [EndpointMetadata("Get recent incidents, active conditions, quests, letters, kidnapped pawns and live traders")]
        public async Task GetEventContext(HttpListenerContext context)
        {
            var mapId = RequestParser.GetMapId(context);
            await context.SendJsonResponse(GameEventAutomationHelper.GetContext(mapId));
        }

        [Post("/api/v1/quest/accept")]
        [EndpointMetadata("Accept a selected live quest through the normal quest system")]
        public async Task AcceptQuest(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<QuestActionRequestDto>();
            await context.SendJsonResponse(GameEventAutomationHelper.AcceptQuest(body));
        }

        [Post("/api/v1/events/letter/choose")]
        [EndpointMetadata("Choose one enabled option from a live quest or joiner letter")]
        public async Task ChooseLetterOption(HttpListenerContext context)
        {
            var body = await context.Request.ReadBodyAsync<LetterChoiceRequestDto>();
            await context.SendJsonResponse(GameEventAutomationHelper.ChooseLetterOption(body));
        }
    }
}

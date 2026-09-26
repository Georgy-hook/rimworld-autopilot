using System;
using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using RIMAPI.Core;
using RIMAPI.Models;
using RimWorld;
using RimWorld.Planet;
using Verse;

namespace RIMAPI.Helpers
{
    public static class GameEventAutomationHelper
    {
        public static ApiResult<List<EventCatalogDto>> GetCatalog()
        {
            try
            {
                return ApiResult<List<EventCatalogDto>>.Ok(DefDatabase<IncidentDef>.AllDefsListForReading
                    .Select(def => new EventCatalogDto
                    {
                        DefName = def.defName,
                        Label = def.LabelCap,
                        Description = def.description,
                        Category = def.category?.defName,
                        Worker = def.workerClass?.Name,
                        GameCondition = def.gameCondition?.defName,
                        QuestScript = def.questScriptDef?.defName,
                        IsAnomalyIncident = def.IsAnomalyIncident,
                        Hidden = def.hidden,
                        EarliestDay = def.earliestDay,
                        MinimumPopulation = def.minPopulation,
                        Mod = def.modContentPack?.Name,
                        Tags = def.tags?.ToList() ?? new List<string>(),
                    })
                    .OrderBy(row => row.Category).ThenBy(row => row.Label).ToList());
            }
            catch (Exception ex)
            {
                return ApiResult<List<EventCatalogDto>>.Fail(ex.Message);
            }
        }

        public static ApiResult<EventContextDto> GetContext(int mapId)
        {
            try
            {
                Map map = MapHelper.GetMapByID(mapId);
                if (map == null) return ApiResult<EventContextDto>.Fail($"Map {mapId} not found.");
                QuestsDto quests = GameEventsHelper.GetQuestsDto(map);
                var result = new EventContextDto
                {
                    MapId = map.uniqueID,
                    GameTick = Find.TickManager?.TicksGame ?? 0,
                    RecentIncidents = GameEventsHelper.GetIncidentsLog(map)
                        .Where(row => row.DaysSinceOccurred <= 1.25f).ToList(),
                    ActiveConditions = map.gameConditionManager.ActiveConditions.Select(condition => new ActiveConditionDto
                    {
                        Id = condition.uniqueID,
                        DefName = condition.def?.defName,
                        Label = condition.LabelCap,
                        Description = condition.Description,
                        StartedTick = condition.startTick,
                        TicksLeft = condition.TicksLeft,
                        Permanent = condition.Permanent,
                        ElectricityDisabled = condition.ElectricityDisabled,
                        TemperatureOffset = condition.def?.temperatureOffset ?? 0f,
                    }).ToList(),
                    ActiveQuests = quests.ActiveQuests,
                    Letters = Find.LetterStack.LettersListForReading
                        .Skip(Math.Max(0, Find.LetterStack.LettersListForReading.Count - 20))
                        .Select(letter => new EventLetterDto
                    {
                        Id = letter.ID,
                        Label = letter.Label,
                        Text = letter is ChoiceLetter choice ? choice.Text : null,
                        LetterDef = letter.def?.defName,
                        ArrivalTick = letter.arrivalTick,
                        EnabledOptions = letter is ChoiceLetter choiceLetter
                            ? ReadLetterOptions(choiceLetter)
                            : new List<string>(),
                    }).ToList(),
                    KidnappedPawns = Find.WorldPawns.AllPawnsAlive
                        .Where(p => p != null && p.RaceProps?.Humanlike == true && KidnapUtility.IsKidnapped(p))
                        .Select(p => new KidnappedPawnDto
                        {
                            Id = p.thingIDNumber,
                            Name = p.Name?.ToStringShort ?? p.LabelShortCap,
                            Faction = p.Faction?.Name,
                            Health = p.health?.summaryHealth?.SummaryHealthPercent ?? 0f,
                            IsKidnapped = true,
                            Holder = p.ParentHolder?.GetType().Name,
                        }).ToList(),
                };
                ApiResult<List<LiveTraderDto>> trade = LiveTradeAutomationHelper.GetOpportunities(mapId);
                if (trade.Success) result.TradeOpportunities = trade.Data;
                return ApiResult<EventContextDto>.Ok(result);
            }
            catch (Exception ex)
            {
                return ApiResult<EventContextDto>.Fail(ex.Message);
            }
        }

        private static List<string> ReadLetterOptions(ChoiceLetter letter)
        {
            try
            {
                var options = Traverse.Create(letter).Property("Choices").GetValue<IEnumerable<DiaOption>>();
                return options?.Where(option => option != null && !option.disabled)
                    .Select(option => Traverse.Create(option).Field("text").GetValue<string>())
                    .Where(label => !string.IsNullOrWhiteSpace(label)).ToList() ?? new List<string>();
            }
            catch
            {
                return new List<string>();
            }
        }

        public static ApiResult ChooseLetterOption(LetterChoiceRequestDto request)
        {
            try
            {
                if (request == null || string.IsNullOrWhiteSpace(request.OptionLabel))
                    return ApiResult.Fail("Letter ID and option label are required.");
                var letter = Find.LetterStack.LettersListForReading.OfType<ChoiceLetter>()
                    .SingleOrDefault(row => row.ID == request.LetterId);
                if (letter == null) return ApiResult.Fail("Choice letter is no longer present.");
                var options = Traverse.Create(letter).Property("Choices").GetValue<IEnumerable<DiaOption>>()
                    ?.Where(option => option != null && !option.disabled
                        && Traverse.Create(option).Field("text").GetValue<string>() == request.OptionLabel).ToList();
                if (options == null || options.Count != 1)
                    return ApiResult.Fail("Requested enabled letter choice is no longer unique.");
                // DiaOption.Activate assumes an owning Dialog_NodeTree when resolveTree is set.
                // ChoiceLetter builds options without a dialog, so invoke its action directly.
                Action action = Traverse.Create(options[0]).Field("action").GetValue<Action>();
                if (action == null)
                    return ApiResult.Fail("Selected letter choice has no direct action.");
                action();
                return ApiResult.Ok();
            }
            catch (Exception ex)
            {
                Exception cause = ex.GetBaseException();
                Verse.Log.Error($"[RIMAPI] Letter choice failed: {ex}");
                return ApiResult.Fail($"Letter choice failed: {cause.GetType().Name}: {cause.Message}");
            }
        }

        public static ApiResult AcceptQuest(QuestActionRequestDto request)
        {
            try
            {
                Quest quest = Find.QuestManager.QuestsListForReading.FirstOrDefault(q => q.id == request.QuestId && !q.Historical);
                if (quest == null) return ApiResult.Fail("The selected active quest no longer exists.");
                if (quest.EverAccepted) return ApiResult.Ok();
                Pawn accepter = request.AccepterPawnId.HasValue ? PawnHelper.FindPawnById(request.AccepterPawnId.Value) : null;
                if (quest.RequiresAccepter && accepter == null)
                {
                    accepter = Find.Maps.SelectMany(m => m.mapPawns.FreeColonistsSpawned)
                        .Where(p => !p.Dead && !p.Downed && !p.InMentalState)
                        .OrderByDescending(p => p.skills?.GetSkill(SkillDefOf.Social)?.Level ?? 0)
                        .FirstOrDefault();
                }
                if (quest.RequiresAccepter && accepter == null)
                    return ApiResult.Fail("This quest requires an accepter, but no healthy colonist is available.");
                quest.Accept(accepter);
                return ApiResult.Ok();
            }
            catch (Exception ex)
            {
                return ApiResult.Fail(ex.Message);
            }
        }

        public static QuestDto ToQuestDto(Quest quest)
        {
            return new QuestDto
            {
                Id = quest.id,
                QuestDef = quest.root?.defName ?? "Unknown",
                Name = quest.name,
                Description = quest.description.ToString(),
                State = quest.State.ToString(),
                ExpiryHours = GameTypesHelper.TicksToDays(quest.TicksUntilExpiry) * 24,
                Reward = GameEventsHelper.GetQuestRewardString(quest),
                EverAccepted = quest.EverAccepted,
                RequiresAccepter = quest.RequiresAccepter,
                IncreasesPopulation = quest.IncreasesPopulation,
                Tags = quest.tags?.ToList() ?? new List<string>(),
                InvolvedFactions = quest.InvolvedFactions.Select(f => f?.Name).Where(s => !string.IsNullOrEmpty(s)).ToList(),
                LookTargets = quest.QuestLookTargets.Select(target =>
                {
                    WorldObject world = target.WorldObject;
                    Site site = world as Site;
                    return new QuestTargetDto
                    {
                        WorldObjectId = world?.ID,
                        ThingId = target.HasThing ? (int?)target.Thing.thingIDNumber : null,
                        Tile = target.Tile.Valid ? (int?)target.Tile : null,
                        Label = world?.LabelCap ?? target.Thing?.LabelCap,
                        WorldObjectType = world?.GetType().Name,
                        EstimatedThreatPoints = site?.ActualThreatPoints ?? 0f,
                    };
                }).ToList(),
            };
        }
    }
}

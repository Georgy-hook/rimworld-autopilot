using System.Collections.Generic;
using System.Linq;
using RIMAPI.Models;
using RimWorld;
using Verse;

namespace RIMAPI.Helpers
{
    class GameEventsHelper
    {
        public static QuestsDto GetQuestsDto(Map map)
        {
            var dto = new QuestsDto();

            List<Quest> allQuests = Find.QuestManager.QuestsListForReading.ToList();

            dto.HistoricalQuests.AddRange(
                allQuests
                    .Where(quest => quest.Historical && !quest.hidden && !quest.hiddenInUI)
                    .Select(GameEventAutomationHelper.ToQuestDto)
            );

            dto.ActiveQuests.AddRange(
                allQuests
                    .Where(quest => !quest.Historical && !quest.hidden && !quest.hiddenInUI)
                    .Select(GameEventAutomationHelper.ToQuestDto)
            );
            return dto;
        }

        public static List<string> GetQuestRewardString(Quest quest)
        {
            return quest
                .PartsListForReading.ToArray().OfType<QuestPart_Choice>()
                .SelectMany(choicePart => choicePart.choices)
                .SelectMany(choice => choice.rewards)
                .Select(reward => reward?.ToString() ?? "Unknown")
                .ToList();
        }

        public static string GetIncidentImportance(IncidentDef def)
        {
            if (def.category == IncidentCategoryDefOf.ThreatBig)
                return "ThreatBig";
            if (def.category == IncidentCategoryDefOf.ThreatSmall)
                return "ThreatSmall";
            if (def.category == IncidentCategoryDefOf.DeepDrillInfestation)
                return "DeepDrillInfestation";
            if (def.category == IncidentCategoryDefOf.DiseaseHuman)
                return "DiseaseHuman";
            if (def.category == IncidentCategoryDefOf.GiveQuest)
                return "GiveQuest";
            if (def.category == IncidentCategoryDefOf.Misc)
                return "Misc";
            if (def.category == IncidentCategoryDefOf.Special)
                return "Special";
            return "None";
        }

        public static List<IncidentDto> GetIncidentsLog(Map map)
        {
            List<IncidentDto> incidentLog = new List<IncidentDto>();

            if (map?.storyState?.lastFireTicks == null)
                return incidentLog;

            foreach (KeyValuePair<IncidentDef, int> entry in map.storyState.lastFireTicks)
            {
                incidentLog.Add(
                    new IncidentDto
                    {
                        IncidentDef = entry.Key.defName,
                        Label = entry.Key.label,
                        Category = GetIncidentImportance(entry.Key),
                        IncidentHour = GameTypesHelper.TicksToDays(entry.Value) * 24,
                        DaysSinceOccurred = (
                            Find.TickManager.TicksGame - entry.Value
                        ).TicksToDays(),
                    }
                );
            }

            // Sort by most recent first
            incidentLog.Sort((a, b) => b.IncidentHour.CompareTo(a.IncidentHour));

            return incidentLog;
        }
    }
}

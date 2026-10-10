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

            foreach (var quest in allQuests.Where(q => q != null && !q.hidden && !q.hiddenInUI))
            {
                string key = "quest:" + quest.id;
                bool historical = false;
                if (!ObservationBoundary.Read(key, () => { historical=quest.Historical; return GameEventAutomationHelper.ToQuestDto(quest); },
                    row => (historical ? dto.HistoricalQuests : dto.ActiveQuests).Add(row), dto.ReadErrors,
                    error => Log.ErrorOnce($"[RIMAPI] Public quest read {quest.id} failed: {error}",
                        ("RIMAPI.quest.read." + quest.id).GetHashCode())))
                    (historical ? dto.HistoricalQuests : dto.ActiveQuests).Add(new QuestDto { Id = quest.id, QuestDef = quest.root?.defName,
                        Name = quest.name, State = historical ? "HistoricalUnavailable" : "Unavailable",
                        ReadStatus = "unavailable", ReadError = dto.ReadErrors[key],
                        CanAccept = false, AcceptanceReason = "quest_read_unavailable",
                        OfferVersion = null, Disclosure = "Public quest terms could not be read; do not accept or infer rewards." });
            }
            if (dto.ReadErrors.Count > 0) dto.ReadStatus = "partial";
            return dto;
        }

        public static List<string> GetQuestRewardString(Quest quest)
        {
            return quest
                .PartsListForReading.ToArray().OfType<QuestPart_Choice>()
                .SelectMany(choicePart => choicePart.choices ?? new List<QuestPart_Choice.Choice>())
                .Where(choice => choice != null)
                .SelectMany(choice => choice.rewards ?? new List<Reward>())
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

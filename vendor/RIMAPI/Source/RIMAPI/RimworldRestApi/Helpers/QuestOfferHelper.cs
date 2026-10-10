using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Newtonsoft.Json;
using RIMAPI.Models;
using RimWorld;
using Verse;

namespace RIMAPI.Helpers
{
    public static class QuestOfferHelper
    {
        public static List<QuestRewardGroupDto> Rewards(Quest quest)
        {
            return quest.PartsListForReading.ToArray().OfType<QuestPart_Choice>()
                .Where(part => part.choices != null).Select(part =>
                new QuestRewardGroupDto {
                    PartIndex = part.Index, ChoiceUsed = part.choiceUsed,
                    Choices = part.choices.Select((choice, index) => new {choice, index})
                      .Where(row => row.choice != null).Select(row => new QuestRewardChoiceDto {
                        ChoiceIndex = row.index,
                        // GetDescription is the player-visible reward, unlike the debug ToString.
                        Rewards = (row.choice.rewards ?? new List<Reward>()).Select(PublicRewardDescription).ToList(),
                        PopulationRewardPossible = (row.choice.rewards ?? new List<Reward>()).OfType<Reward_Pawn>().Any()
                    }).ToList()
                }).ToList();
        }

        public static QuestDto Describe(Quest quest)
        {
            QuestDto dto = GameEventAutomationHelper.BasicQuestDto(quest);
            bool offered = !quest.Historical && quest.State == QuestState.NotYetAccepted;
            if (offered && quest.PartsListForReading.OfType<QuestPart_Choice>().Any(p =>
                    p.choices == null || p.choices.Any(c => c == null || c.rewards == null)))
                throw new InvalidOperationException("quest_reward_terms_unavailable");
            dto.CanAccept = false;
            dto.AcceptanceReason = "quest_not_offered";
            if (offered)
            {
                var report = QuestUtility.CanAcceptQuest(quest);
                dto.CanAccept = report.Accepted && (quest.acceptanceExpireTick < 0 || quest.TicksUntilExpiry > 0);
                dto.AcceptanceReason = report.Reason;
            }
            dto.RewardGroups = Rewards(quest);
            dto.Reward = dto.RewardGroups.SelectMany(g => g.Choices).SelectMany(c => c.Rewards).ToList();
            dto.PopulationRewardPossible = dto.RewardGroups.Any(g => g.Choices.Any(c => c.PopulationRewardPossible));
            dto.IncreasesPopulation = !quest.Historical && (dto.IncreasesPopulation || dto.PopulationRewardPossible);
            dto.EligibleAccepters = !offered || !quest.RequiresAccepter ? new List<QuestAccepterDto>() : PawnsFinder.AllMaps_FreeColonistsSpawned
                .Where(p => !p.Dead && QuestUtility.CanPawnAcceptQuest(p, quest))
                .Select(p => new QuestAccepterDto { PawnId = p.thingIDNumber,
                    Name = p.LabelShortCap, Downed = p.Downed, InMentalState = p.InMentalState,
                    CurrentJob = p.CurJob?.def.defName, Social = p.skills?.GetSkill(SkillDefOf.Social)?.Level ?? 0 })
                .OrderBy(p => p.PawnId).ToList();
            // Accepted/historical quests remain public commitments, but their
            // expired acceptance parts may refer to destroyed targets. Do not
            // rerun irrelevant acceptance callbacks on every context read.
            dto.Requirements = !offered ? new List<string>() : quest.PartsListForReading.ToArray().OfType<QuestPart_RequirementsToAccept>()
                .Where(p => p.ShowInRequirementBox).Select(p => {
                    var acceptance = p.CanAccept();
                    return $"{p.GetType().Name}: {(acceptance.Accepted ? "met" : "not met")}; {p.DescriptionPart}; {acceptance.Reason}";
                }).ToList();
            // Only unconditional acceptance consequences. Future betrayal and
            // hidden signals are not player knowledge and must not leak here.
            dto.AcceptanceDiplomacy = quest.Historical ? new List<QuestDiplomacyDto>() : quest.PartsListForReading.ToArray().OfType<QuestPart_FactionGoodwillChange>()
                .Where(p => p.inSignal == quest.InitiateSignal && quest.root?.hideInvolvedFactionsInfo != true)
                .Select(p => new QuestDiplomacyDto { Faction = p.faction?.Name,
                    FactionDef = p.faction?.def.defName, GoodwillChange = p.change,
                    MakesHostile = p.ensureMakesHostile,
                    CurrentGoodwill = p.faction?.GoodwillWith(Faction.OfPlayer),
                    CurrentRelation = p.faction?.RelationKindWith(Faction.OfPlayer).ToString() }).ToList();
            dto.Disclosure = quest.Historical
                ? "Historical record only. Discarded actors and live target/population/acceptance callbacks are not read; past arrival, income or completion cannot be inferred from reward text."
                : "Offer and native requirements only. Hidden outcomes remain unknown; possible pawn rewards are not guaranteed permanent workers. Reward groups are alternatives, not cumulative rewards.";
            using (var sha = SHA256.Create())
            {
                // Expiry counts and current jobs drift normally. Bind the actual
                // terms, reward indices, requirements and eligible identities.
                var terms = JsonConvert.SerializeObject(new { dto.Id, dto.QuestDef, dto.Description,
                    dto.RequiresAccepter, dto.RewardGroups, dto.Requirements, dto.AcceptanceDiplomacy,
                    dto.InvolvedFactions, dto.LookTargets,
                    Accepters = dto.EligibleAccepters.Select(p => p.PawnId).ToArray() });
                dto.OfferVersion = BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(terms))).Replace("-", "").ToLowerInvariant();
            }
            return dto;
        }

        public static string Validate(Quest quest, QuestActionRequestDto request, Pawn pawn)
        {
            var dto = Describe(quest);
            string error = QuestOfferBoundary.ValidateOffer(request.OfferVersion, dto.OfferVersion,
                quest.State == QuestState.NotYetAccepted, dto.CanAccept,
                !quest.RequiresAccepter || pawn != null && QuestUtility.CanPawnAcceptQuest(pawn, quest));
            if (error != null) return error;
            return QuestOfferBoundary.ValidateRewards(dto.RewardGroups.Where(g => !g.ChoiceUsed)
                .ToDictionary(g => g.PartIndex, g => g.Choices.Select(c => c.ChoiceIndex).ToArray()),
                request.RewardChoices?.Select(s => s == null ? null : new[] { s.PartIndex, s.ChoiceIndex }).ToList());
        }

        private static string PublicRewardDescription(Reward reward)
        {
            if (reward == null) return "Unknown reward";
            try { return reward.GetDescription(new RewardsGeneratorParams()) ?? "Public reward details unavailable"; }
            catch { return $"Public reward details unavailable ({reward.GetType().Name}); do not assume value or safety"; }
        }

        public static void SelectRewards(Quest quest, QuestActionRequestDto request)
        {
            // Choose may remove/add quest parts and change subsequent Index
            // values. Resolve ALL part/choice objects before the first mutation.
            var bindings = quest.PartsListForReading.ToArray().OfType<QuestPart_Choice>().Where(p => !p.choiceUsed)
                .Select(part => new { Part = part,
                    Choice = part.choices[request.RewardChoices.FirstOrDefault(s => s.PartIndex == part.Index)?.ChoiceIndex ?? 0] }).ToArray();
            foreach (var binding in bindings) binding.Part.Choose(binding.Choice);
        }
    }
}

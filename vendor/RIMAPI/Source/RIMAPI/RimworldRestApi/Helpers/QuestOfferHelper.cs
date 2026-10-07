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
            return quest.PartsListForReading.ToArray().OfType<QuestPart_Choice>().Select(part =>
                new QuestRewardGroupDto {
                    PartIndex = part.Index, ChoiceUsed = part.choiceUsed,
                    Choices = part.choices.Select((choice, index) => new QuestRewardChoiceDto {
                        ChoiceIndex = index,
                        // GetDescription is the player-visible reward, unlike the debug ToString.
                        Rewards = choice.rewards.Select(PublicRewardDescription).ToList(),
                        PopulationRewardPossible = choice.rewards.OfType<Reward_Pawn>().Any()
                    }).ToList()
                }).ToList();
        }

        public static QuestDto Describe(Quest quest)
        {
            QuestDto dto = GameEventAutomationHelper.BasicQuestDto(quest);
            var report = QuestUtility.CanAcceptQuest(quest);
            dto.CanAccept = quest.State == QuestState.NotYetAccepted && report.Accepted
                && (quest.acceptanceExpireTick < 0 || quest.TicksUntilExpiry > 0);
            dto.AcceptanceReason = report.Reason;
            dto.RewardGroups = Rewards(quest);
            dto.Reward = dto.RewardGroups.SelectMany(g => g.Choices).SelectMany(c => c.Rewards).ToList();
            dto.PopulationRewardPossible = dto.RewardGroups.Any(g => g.Choices.Any(c => c.PopulationRewardPossible));
            dto.IncreasesPopulation = dto.IncreasesPopulation || dto.PopulationRewardPossible;
            dto.EligibleAccepters = PawnsFinder.AllMaps_FreeColonistsSpawned
                .Where(p => quest.RequiresAccepter && quest.State == QuestState.NotYetAccepted)
                .Where(p => !p.Dead && QuestUtility.CanPawnAcceptQuest(p, quest))
                .Select(p => new QuestAccepterDto { PawnId = p.thingIDNumber,
                    Name = p.LabelShortCap, Downed = p.Downed, InMentalState = p.InMentalState,
                    CurrentJob = p.CurJob?.def.defName, Social = p.skills?.GetSkill(SkillDefOf.Social)?.Level ?? 0 })
                .OrderBy(p => p.PawnId).ToList();
            dto.Requirements = quest.PartsListForReading.ToArray().OfType<QuestPart_RequirementsToAccept>()
                .Where(p => p.ShowInRequirementBox).Select(p => {
                    var acceptance = p.CanAccept();
                    return $"{p.GetType().Name}: {(acceptance.Accepted ? "met" : "not met")}; {p.DescriptionPart}; {acceptance.Reason}";
                }).ToList();
            // Only unconditional acceptance consequences. Future betrayal and
            // hidden signals are not player knowledge and must not leak here.
            dto.AcceptanceDiplomacy = quest.PartsListForReading.ToArray().OfType<QuestPart_FactionGoodwillChange>()
                .Where(p => p.inSignal == quest.InitiateSignal && quest.root?.hideInvolvedFactionsInfo != true)
                .Select(p => new QuestDiplomacyDto { Faction = p.faction?.Name,
                    FactionDef = p.faction?.def.defName, GoodwillChange = p.change,
                    MakesHostile = p.ensureMakesHostile,
                    CurrentGoodwill = p.faction?.GoodwillWith(Faction.OfPlayer),
                    CurrentRelation = p.faction?.RelationKindWith(Faction.OfPlayer).ToString() }).ToList();
            dto.Disclosure = "Offer and native requirements only. Hidden outcomes remain unknown; possible pawn rewards are not guaranteed permanent workers. Reward groups are alternatives, not cumulative rewards.";
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

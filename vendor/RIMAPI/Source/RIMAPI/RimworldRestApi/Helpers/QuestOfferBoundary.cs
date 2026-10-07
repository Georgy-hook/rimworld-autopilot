using System.Collections.Generic;
using System.Linq;

namespace RIMAPI.Helpers
{
    // Dependency-free validation, exercised offline. No quest is mutated until
    // every choice binding and the observed offer version have passed.
    public static class QuestOfferBoundary
    {
        public static string ValidateOffer(string observed, string current, bool offered,
            bool canAccept, bool accepterValid)
        {
            if (string.IsNullOrEmpty(observed)) return "quest_offer_review_required";
            if (observed != current) return "quest_offer_changed";
            if (!offered) return "quest_not_offered";
            if (!canAccept) return "quest_requirements_not_met_or_expired";
            if (!accepterValid) return "quest_accepter_not_eligible";
            return null;
        }

        public static string ValidateRewards(Dictionary<int, int[]> groups, IList<int[]> selections)
        {
            if (selections == null || selections.Any(s => s == null || s.Length != 2))
                return "quest_reward_binding_invalid";
            if (selections.GroupBy(s => s[0]).Any(g => g.Count() != 1))
                return "quest_reward_binding_duplicate";
            foreach (var s in selections)
                if (!groups.TryGetValue(s[0], out var choices) || !choices.Contains(s[1]))
                    return "quest_reward_choice_changed";
            foreach (var group in groups)
                if (group.Value.Length == 0 || (group.Value.Length > 1 && !selections.Any(s => s[0] == group.Key)))
                    return "quest_reward_choice_required";
            return null;
        }
    }
}

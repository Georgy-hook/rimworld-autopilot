import unittest
from unittest.mock import patch
import colony_director as d
import colony_reasoning as reasoning


class DecisionSummaryReadinessTests(unittest.TestCase):
    def test_unavailable_or_disabled_high_skill_is_not_advertised_as_usable(self):
        people = [{"name": "Unavailable", "in_mental_state": True, "skills": {"Medicine": {"level": 20}}},
                  {"name": "Disabled", "skills": {"Medicine": {"level": 18, "disabled": True}}},
                  {"name": "Doctor", "skills": {"Medicine": {"level": 6}}}]
        with patch.object(d.laya_preferences, "load_preferences", return_value={}):
            state = d.build_decision_state({"colonists": people, "development": {}, "map": {}, "game": {}})
        self.assertEqual(state["capabilities"]["Medicine"]["best"], "Doctor")
        self.assertEqual(state["capabilities"]["Medicine"]["level"], 6)

    def test_past_native_expedition_blocker_projects_exact_fields_and_expires(self):
        snapshot = {"game": {"tick": 1500}}
        memory = {"expedition_readiness": {"observed_tick": 1000, "reason": "Insufficient nutrition",
            "readiness": {"required_nutrition": 36, "acceptable_stock_nutrition": 8,
                "required_food_days": 12, "home_defenders": 2, "pawn_ids": list(range(1000))}}}
        d.project_expedition_readiness(snapshot, memory)
        view = snapshot["development"]["last_expedition_attempt"]
        self.assertEqual(view["required_nutrition"], 36)
        self.assertEqual(view["acceptable_stock_nutrition"], 8)
        self.assertEqual(view["required_food_days"], 12)
        self.assertNotIn("pawn_ids", view)
        self.assertEqual(view["ticks_ago"], 500)
        self.assertIn("past preview", view["meaning"])
        self.assertEqual(reasoning.decision_facts({"last_expedition_attempt": view})["last_expedition_attempt"], view)
        snapshot["game"]["tick"] = 61000
        d.project_expedition_readiness(snapshot, memory)
        self.assertNotIn("last_expedition_attempt", snapshot["development"])
        self.assertNotIn("expedition_readiness", memory)

    def test_rollback_or_malformed_attempt_is_discarded(self):
        for record in ("bad", {"observed_tick": "bad"}, {"observed_tick": 1000, "readiness": []}):
            snapshot = {"game": {"tick": 900}}
            memory = {"expedition_readiness": record}
            d.project_expedition_readiness(snapshot, memory)
            self.assertNotIn("expedition_readiness", memory)

if __name__ == "__main__":
    unittest.main()

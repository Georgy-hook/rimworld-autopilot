"""Keep the observation tool from reporting infrastructure as success."""
import unittest
from tools.colony_verification import evidence_card, layout_svg


class ColonyVerificationTests(unittest.TestCase):
    def card(self, snapshot=None, **kwargs):
        return evidence_card(snapshot or {"development": {}},
                             {"native_ending": {"campaign_id": "run", "game_over_verified": False}},
                             {"campaign_id": "run"}, kwargs.get("timeline", []),
                             kwargs.get("decisions", []), {}, kwargs.get("review", {}),
                             kwargs.get("baseline", {}))

    def test_generator_and_flowers_do_not_establish_food_power_or_raid_success(self):
        card = self.card({"map": {"enemies": 0, "resources": {"food": 0}}, "development": {
            "buildings": [{"id": 1, "def": "WoodFiredGenerator", "position": {"x": 10, "z": 10}},
                          {"id": 2, "def": "Cooler", "power_on": False, "position": {"x": 12, "z": 10}}],
            "zones": [{"id": 3, "type": "Zone_Growing", "plant_def_name": "Plant_Rose"}],
            "farm": {"total_expected_yield": 0}}})
        self.assertFalse(card["settlement"]["buildings"][1]["power_on"])
        self.assertEqual(0, card["agriculture"]["farm"]["total_expected_yield"])
        self.assertEqual([], card["raids"]["verified_outcomes"])
        self.assertIsNone(card["economy"]["verified_income"])

    def test_missing_coverage_stays_unknown_instead_of_zero(self):
        card = self.card()
        self.assertIsNone(card["settlement"]["counts"])
        self.assertIsNone(card["agriculture"]["zones"])
        self.assertIsNone(card["nutrition"]["max_meals"])
        self.assertIn("not a complete", card["animals"]["coverage"])

    def test_mixed_campaign_refused(self):
        with self.assertRaises(ValueError):
            evidence_card({}, {"native_ending": {"campaign_id": "other"}},
                          {"campaign_id": "run"}, [], [], {}, {}, {})

    def test_bounded_decisions_and_rejected_tend_not_reported_as_treatment(self):
        decisions = [{"mode": "post-combat-care", "decision": {"choice": "self_tend_985"},
                      "result": {"applied": False, "reason": "care_actor_or_patient_changed"}}] * 16
        card = self.card(decisions=decisions)
        self.assertEqual(16, card["priorities"]["rejection_reasons"]["care_actor_or_patient_changed"])
        self.assertEqual([], card["population"]["verified_status_changes"])
        with self.assertRaises(ValueError):
            self.card(decisions=decisions * 7)

    def test_initial_structures_are_not_attributed_to_laya(self):
        ruin = {"id": 1, "def": "Wall", "position": {"x": 1, "z": 1}}
        bed = {"id": 2, "def": "Bed", "position": {"x": 2, "z": 2}}
        card = self.card({"development": {"buildings": [ruin, bed]}},
                         baseline={"development": {"buildings": [ruin]}})
        self.assertEqual({"Bed": 1}, card["settlement"]["new_since_baseline"])
        self.assertIn("Observed coordinates", layout_svg(card))


if __name__ == "__main__":
    unittest.main()

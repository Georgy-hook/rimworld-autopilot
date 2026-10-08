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

    def test_development_records_unassigned_roles_and_unfinished_outcomes(self):
        pawn = {"id": 1, "name": "Worker", "age": 24, "gender": "Female", "relations": [],
                "skills": {"Intellectual": {"level": 0}}, "current_job": "Repair",
                "work_priorities": {"Research": {"priority": 0, "disabled": False},
                                    "Warden": {"priority": 0, "disabled": True}}}
        snapshot = {"colonists": [pawn], "combat": {"colonists": [
            {"id": 1, "can_fight": True, "has_ranged_weapon": False, "armor_sharp": 0}]},
            "development": {"buildings": [{"id": 2, "def": "SleepingSpot", "for_prisoners": True,
                                           "roofed": True, "current_temperature": 21}],
                            "current_research": {"name": "Battery", "progress": 2},
                            "work_tables": [{"id": 3, "thing_def": "TableSculpting", "bills_count": 0}]}}
        status = self.card(snapshot)["development_status"]
        self.assertIn("Research", status["workforce"]["unassigned_roles"])
        self.assertIn("Warden", status["workforce"]["missing_roles"])
        self.assertEqual(0, status["armament"][0]["armor_sharp"])
        self.assertEqual(2, status["prison"]["beds"][0]["id"])
        self.assertIsNone(status["prison"]["patients"])
        self.assertIn("Unknown", status["family"]["eligibility"])
        self.assertEqual(0, status["workshops"][0]["bills_count"])

    def test_absent_population_and_combat_are_not_reported_as_zero_deficits(self):
        status = self.card()["development_status"]
        self.assertIsNone(status["workforce"])
        self.assertIsNone(status["work_assignments"])
        self.assertIsNone(status["armament"])
        self.assertIsNone(status["prison"]["beds"])
        self.assertIsNone(status["family"]["people"])

    def test_rock_wall_and_partial_roof_coverage_do_not_establish_mountain_safety(self):
        rooms = [{"id": 1, "cells_count": 1, "cells": [{"x": 10, "z": 10}]},
                 {"id": 2, "cells_count": 1, "cells": [{"x": 20, "z": 20}]}]
        status = self.card({"development": {"rooms": rooms, "buildings": [],
            "resilience": {"available": True, "environment": {
                "rooms": [{"id": 1, "mountain_cells": 0}], "hives": []}}}})["underground_status"]
        self.assertEqual(0, status["rooms"][0]["mountain_cells"])
        self.assertIsNone(status["rooms"][1]["mountain_cells"])
        self.assertEqual([1], status["native_roof_room_ids"])
        self.assertEqual(0, status["hive_count"])
        self.assertFalse(status["rooms"][0]["escape_routes_verified"])

    def test_two_building_doors_are_not_two_exits_from_one_bedroom(self):
        rooms = [{"id": 80, "cells_count": 2,
                  "cells": [{"x": 124, "z": 145}, {"x": 125, "z": 145}]},
                 {"id": 81, "cells_count": 1, "cells": [{"x": 137, "z": 152}]}]
        doors = [{"id": 36054, "def": "Door", "position": {"x": 125, "z": 144}},
                 {"id": 41473, "def": "Door", "position": {"x": 137, "z": 151}}]
        status = self.card({"development": {"rooms": rooms, "buildings": doors}})["underground_status"]
        self.assertEqual([36054], [d["id"] for d in status["rooms"][0]["adjacent_doors"]])
        self.assertEqual([41473], [d["id"] for d in status["rooms"][1]["adjacent_doors"]])
        self.assertIsNone(status["rooms"][0]["mountain_cells"])

    def test_incomplete_cells_and_large_door_remain_unverified(self):
        rooms = [{"id": 1, "cells_count": 12, "cells": [{"x": 10, "z": 10}]},
                 {"id": 2, "cells_count": 1, "cells": [{"x": 20, "z": 20}]}]
        door = {"id": 3, "type": "Building_Door", "position": {"x": 20, "z": 19},
                "size": {"x": 3, "z": 1}}
        status = self.card({"development": {"rooms": rooms, "buildings": [door]}})["underground_status"]
        self.assertIsNone(status["rooms"][0]["adjacent_doors"])
        self.assertIn("partial", status["rooms"][1]["door_coverage"])
        self.assertFalse(status["rooms"][1]["escape_routes_verified"])
        # A modded Building_Door without a footprint is not a vanilla 1x1 door.
        door.pop("size")
        status = self.card({"development": {"rooms": rooms, "buildings": [door]}})["underground_status"]
        self.assertIn("partial", status["rooms"][1]["door_coverage"])

    def test_unavailable_native_module_does_not_certify_absence_of_hives(self):
        status = self.card({"development": {"resilience": {
            "available": False, "environment": {"hives": [], "rooms": []}}}})["underground_status"]
        self.assertIsNone(status["hive_count"])
        self.assertIsNone(status["native_roof_room_ids"])
        self.assertIsNone(status["rooms"])


if __name__ == "__main__":
    unittest.main()

"""Failures from the terminal Tium continuation on 30 September 2026."""
import unittest
from unittest import mock

import colony_combat as combat
import colony_director as director
import stream_observer as observer
from tests.test_combat_scenarios import fighter, raid
import rimworld_laya as bridge


def hot_colony(wood=0):
    return {
        "game": {"tick": 1000000}, "map": {"id": 0, "resources": {
            "food": 220, "raw_food": 220, "nutrition": 11, "meals": 0}},
        "colonists": [
            {"id": 1, "name": "Sunny", "health": 1, "hunger": 0.7,
             "position": {"x": 10, "z": 10}, "current_job": "Wait",
             "work_priorities": {name: {"priority": 1} for name in (
                 "PlantCutting", "Hauling", "Doctor", "Construction", "Cooking")}},
            {"id": 2, "name": "Rowe", "health": 1, "hunger": 0.3, "downed": True,
             "patient_feeding_eligible": True, "patient_raw_food_allowed": False,
             "position": {"x": 13, "z": 14}, "current_job": "LayDown",
             "health_conditions": [{"def_name": "Heatstroke", "severity": 0.6}]}],
        "animals": [], "wild_animals": [], "combat": {},
        "development": {
            "building_counts": {"Bed": 2, "Campfire": 1, "PassiveCooler": 1},
            "item_counts": {"WoodLog": wood}, "weather": {"temperature": 46},
            "work_tables": [{"id": 51, "thing_def": "Campfire"}],
            "buildings": [{"id": 22, "def": "Bed", "position": {"x": 13, "z": 14}},
                          {"id": 23, "def": "Bed", "position": {"x": 12, "z": 14}},
                          {"id": 50, "def": "PassiveCooler", "position": {"x": 14, "z": 14},
                           "requires_fuel": True, "current_fuel": 0, "fuel_capacity": 50,
                           "fuel_type": "WoodLog", "auto_refuel": True}],
            "rooms": [{"id": 24, "temperature": 46, "open_roof_count": 0,
                       "cells_count": 4, "contained_beds_ids": [22, 23],
                       "contained_thing_defs": ["Bed", "PassiveCooler"],
                       "cells": [{"x": 13, "z": 14}, {"x": 14, "z": 14}],
                       "light_placement_cells": [{"x": 14, "z": 14}]}],
            "plants": [{"thing_id": 401, "def_name": "Plant_SaguaroCactus", "label": "saguaro cactus",
                        "harvestable_now": True, "harvested_thing_def": "WoodLog",
                        "harvest_yield": 15, "position": {"x": 14, "z": 10}}]}}


class HourlyRegressionTests(unittest.TestCase):
    def test_sowable_wood_species_still_can_be_harvested_with_full_catalog(self):
        snapshot = hot_colony()
        snapshot["development"]["plant_catalog"] = {"plants": [
            {"def_name": "Plant_SaguaroCactus", "sowable": True, "category": "wood"}], "growers": []}
        snapshot["development"]["plants"][0]["is_cultivated"] = True
        choices, details = director.candidate_actions(None, snapshot, {"anchor": {"x": 10, "z": 10}, "issued": {}})
        self.assertIn("harvest_nearby_trees", choices)
        self.assertEqual(details["tree_options"]["Plant_SaguaroCactus"]["ids"], [401])

    def test_saguaro_is_an_available_fuel_source_with_no_construction_projects(self):
        snapshot = hot_colony()
        choices, details = director.candidate_actions(None, snapshot, {"anchor": {"x": 10, "z": 10}, "issued": {}})
        self.assertIn("harvest_nearby_trees", choices)
        self.assertEqual(details["tree_options"]["Plant_SaguaroCactus"]["expected_yield"], 15)
        self.assertTrue(snapshot["development"]["heatstroke_focus"])
        self.assertNotIn("prioritize_research", choices)
        self.assertNotIn("build_passive_cooler", choices)

    def test_heat_control_fuel_is_needed_even_with_ready_food_and_no_kitchen(self):
        snapshot = hot_colony()
        snapshot["map"]["resources"].update(meals=100, raw_food=0)
        snapshot["development"]["building_counts"].pop("Campfire")
        snapshot["development"]["work_tables"] = []
        choices, _ = director.candidate_actions(None, snapshot, {"anchor": {"x": 10, "z": 10}, "issued": {}})
        self.assertIn("harvest_nearby_trees", choices)

    def test_existing_empty_cooler_can_be_refueled_without_building_another(self):
        snapshot = hot_colony(wood=20)
        state = {"anchor": {"x": 10, "z": 10}, "issued": {}}
        choices, details = director.candidate_actions(None, snapshot, state)
        self.assertIn("refuel_building", choices)
        self.assertEqual(snapshot["development"]["heat_threat"]["empty_coolers"], 1)
        questions = director.subchoice_questions_for_action("refuel_building", snapshot)
        self.assertEqual(set(questions["refuel_target"]["criteria"]), {"50"})
        client = mock.Mock()
        client.post.return_value = {"applied": True, "reason": "refuel_job_assigned"}
        result = director.execute_action(client, snapshot, state, "refuel_building",
                                         {**details, "refuel_target": "50", "worker_pawn": "1"})
        self.assertTrue(result["applied"])
        client.post.assert_called_once_with("/api/v1/builder/refuel", body={
            "map_id": 0, "building_id": 50, "worker_pawn_id": 1})
        choices, _ = director.candidate_actions(None, snapshot, state)
        self.assertNotIn("refuel_building", choices)

    def test_no_eligible_patient_food_is_a_skipped_order_not_a_success(self):
        snapshot = hot_colony()
        client = mock.Mock()
        client.post.return_value = {"applied": False, "reason": "no_eligible_food_or_patient_reserved"}
        result = director.execute_action(client, snapshot, {"anchor": {"x": 10, "z": 10}, "issued": {}},
                                         "feed_hungry_colonist", {"hungry_colonist_id": 2})
        self.assertFalse(result["applied"])
        self.assertEqual(result["reason"], "no_eligible_food_or_patient_reserved")

    def test_raw_only_patient_feeding_respects_actual_game_food_category(self):
        snapshot = hot_colony()
        state = {"anchor": {"x": 10, "z": 10}, "issued": {}}
        choices, _ = director.candidate_actions(None, snapshot, state)
        self.assertNotIn("feed_hungry_colonist", choices)
        snapshot["colonists"][1]["patient_raw_food_allowed"] = True
        choices, _ = director.candidate_actions(None, snapshot, state)
        self.assertIn("feed_hungry_colonist", choices)
        snapshot["colonists"][1]["patient_raw_food_allowed"] = False
        snapshot["map"]["resources"]["meals"] = 1
        choices, _ = director.candidate_actions(None, snapshot, state)
        self.assertIn("feed_hungry_colonist", choices)

    def test_aiming_assault_raiders_do_not_turn_back_into_preparing_raiders(self):
        for job in ("Wait_Combat", "Wait_Wander"):
            hostile = {"id": 99, "current_job": job, "lord_toil_name": "LordToil_AssaultColony",
                       "position": {"x": 100, "z": 100}}
            self.assertFalse(combat.hostile_is_preparing(hostile))
            gunner = fighter(1, distance=50, range_cells=37)
            gunner.update(is_drafted=True, current_job="Wait_Combat")
            criteria = bridge.make_questions(raid([gunner], [hostile]))["threat_action"]["criteria"]
            self.assertNotIn("prepare_undrafted", criteria)
            self.assertNotIn("preemptive_strike", criteria)

    def test_dangerous_nonimmune_temperature_condition_slows_the_observer(self):
        for name in ("Heatstroke", "Hypothermia"):
            rows = [{"health": 1, "detailes": {"medical_info": {"hediffs": [{
                "def_name": name, "severity": 0.6, "immunity": None}]}}}]
            self.assertTrue(observer._critical_disease(rows))
            rows[0]["detailes"]["medical_info"]["hediffs"][0]["severity"] = 0.1
            self.assertFalse(observer._critical_disease(rows))

    def test_advancing_shooter_is_not_undrafted_on_the_next_distant_raid_cycle(self):
        hostile = {"id": 99, "current_job": "Wait_Wander", "lord_toil_name": "LordToil_Stage",
                   "position": {"x": 100, "z": 100}}
        for job in ("Goto", "AttackStatic", "Wait_Combat"):
            gunner = fighter(1, distance=105, range_cells=26)
            gunner.update(is_drafted=True, current_job=job)
            criteria = bridge.make_questions(raid([gunner], [hostile]))["threat_action"]["criteria"]
            self.assertNotIn("prepare_undrafted", criteria)

    def test_research_redirection_cannot_hide_heatstroke_response(self):
        snapshot = hot_colony()
        snapshot["development"].update(research_misalignment={"current": "Machining"},
                                        heat_threat={"patients": [{"name": "Rowe", "severity": 0.6}]})
        choices = ["advance_doctrine_research", "harvest_nearby_trees"]
        self.assertEqual(director.focus_misaligned_research_choice(snapshot, choices), choices)

    def test_no_feasible_worker_is_filtered_before_a_model_subchoice(self):
        snapshot = hot_colony()
        snapshot["development"]["work_types"] = [{"def_name": "Hauling"}]
        snapshot["colonists"][0]["in_mental_state"] = True
        self.assertEqual(director.worker_criteria(snapshot, "Hauling"), {})
        self.assertEqual(director.live_work_options(snapshot), {})
        snapshot["colonists"][0]["in_mental_state"] = False
        self.assertIn("Hauling", director.live_work_options(snapshot))

    def test_observer_pauses_only_a_confirmed_terminal_colony(self):
        api = mock.Mock()
        api.request.return_value = {"letters": [{"letter_def": "GameEnded", "text": "Игра окончена"}]}
        self.assertTrue(observer._pause_if_colony_ended(api, {"colonist_count": 0}, 0))
        self.assertEqual(api.request.call_args_list[-1], mock.call("/api/v1/game/speed?speed=0", post=True))
        api.reset_mock()
        self.assertFalse(observer._pause_if_colony_ended(api, {"colonist_count": 1}, 0))
        api.request.assert_not_called()
        api.request.return_value = {"letters": [], "caravans": [{"colonists": 2}]}
        self.assertFalse(observer._pause_if_colony_ended(api, {"colonist_count": 0}, 0))
        self.assertEqual(api.request.call_count, 1)


if __name__ == "__main__":
    unittest.main()

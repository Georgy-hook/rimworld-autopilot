import copy
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import colony_combat
import colony_events
import colony_growth
import colony_strategy


ROOT = pathlib.Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("colony_director", ROOT / "colony_director.py")
director = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = director
SPEC.loader.exec_module(director)


class DirectorTests(unittest.TestCase):
    def test_nested_decisions_reach_executor_without_manual_key_list(self):
        details = {"emergency_medical_bed_options": {"44461": "Safe bed"}}
        decision = {"choice": "prepare_emergency_medical_bed", "confidence": 0.4,
                    "emergency_medical_bed": "44461", "fire_target": "92",
                    "bed_assignment": "248|44461", "raw": {"answers": {}}}
        merged = director.merge_decision_details(details, decision)
        self.assertEqual(merged["emergency_medical_bed"], "44461")
        self.assertEqual(merged["fire_target"], "92")
        self.assertEqual(merged["bed_assignment"], "248|44461")
        self.assertEqual(merged["emergency_medical_bed_options"], details["emergency_medical_bed_options"])
        self.assertNotIn("raw", merged)

    def test_first_house_budget_defers_expansions_but_keeps_survival_choices(self):
        actions = ["build_starter_base", "build_sleeping_spots", "unforbid_supplies",
                   "equip_colonists", "create_growing_zone", "harvest_nearby_trees",
                   "build_prison", "build_cemetery", "build_killbox", "build_freezer",
                   "income_drugs", "plan_architecture", "prioritize_construction"]
        snapshot = {"map": {"enemies": 0}, "colonists": [{"id": 1}, {"id": 2}, {"id": 3}],
                    "development": {"buildings": [], "rooms": []}}
        result = director.defer_discretionary_work_until_shelter(snapshot, {"issued": {}}, actions)
        self.assertIn("build_starter_base", result)
        self.assertIn("equip_colonists", result)
        self.assertIn("harvest_nearby_trees", result)
        self.assertNotIn("build_prison", result)
        self.assertNotIn("build_cemetery", result)
        self.assertNotIn("build_killbox", result)
        self.assertNotIn("income_drugs", result)
        self.assertIn("build_freezer", snapshot["development"]["deferred_until_shelter"])

    def test_live_threat_keeps_defense_available_before_shelter(self):
        snapshot = {"map": {"enemies": 1}, "colonists": [{"id": 1}],
                    "development": {"buildings": [], "rooms": []}}
        result = director.defer_discretionary_work_until_shelter(
            snapshot, {"issued": {}}, ["build_starter_base", "build_fallback_defense", "build_prison"]
        )
        self.assertIn("build_fallback_defense", result)
        self.assertNotIn("build_prison", result)

    def test_roofed_ground_spots_do_not_unlock_expansion_before_real_beds(self):
        snapshot = {"map": {"enemies": 0}, "colonists": [{"id": 1}],
                    "development": {"buildings": [{"id": 7, "def": "SleepingSpot"}],
                                    "rooms": [{"contained_beds_ids": [7],
                                               "open_roof_count": 0,
                                               "touches_map_edge": False}]}}
        result = director.defer_discretionary_work_until_shelter(
            snapshot, {"issued": {}}, ["build_basic_beds", "build_freezer"]
        )
        self.assertEqual(result, ["build_basic_beds"])

    def test_outdoor_real_bed_does_not_unlock_expansion(self):
        snapshot = {"map": {"enemies": 0}, "colonists": [{"id": 1}],
                    "development": {"buildings": [{"id": 7, "def": "SleepingSpot"},
                                                  {"id": 8, "def": "Bed"}],
                                    "rooms": [{"contained_beds_ids": [7],
                                               "open_roof_count": 0,
                                               "touches_map_edge": False}]}}
        result = director.defer_discretionary_work_until_shelter(
            snapshot, {"issued": {}}, ["build_basic_beds", "build_freezer"]
        )
        self.assertEqual(result, ["build_basic_beds"])
        self.assertEqual(director.sheltered_real_bed_count(snapshot["development"]), 0)

    def test_remote_roofed_bed_does_not_count_as_starter_house(self):
        development = {"buildings": [{"id": 8, "def": "Bed", "position": {"x": 158, "z": 131}}],
                       "rooms": [{"contained_beds_ids": [8], "open_roof_count": 0,
                                  "touches_map_edge": False}]}
        self.assertEqual(director.sheltered_real_bed_count(development), 1)
        self.assertEqual(director.sheltered_real_bed_count(development, {"x": 124, "z": 146}), 0)
        snapshot = {"map": {"enemies": 0}, "colonists": [{"id": 1}],
                    "development": development}
        actions = director.defer_discretionary_work_until_shelter(
            snapshot, {"anchor": {"x": 124, "z": 146}}, ["build_basic_beds", "build_freezer"])
        self.assertEqual(actions, ["build_basic_beds"])

    def test_short_laya_context_keeps_materials_with_building_backlog(self):
        class TinyAgent:
            cfg = {"max_len": 512, "head_max_len": 192}

            @staticmethod
            def tok(value, **_kwargs):
                return {"input_ids": list(range((len(value) + 3) // 4))}

        state = {
            "goal": "Develop the colony", "threats": 0, "people": 3,
            "needs": {"food": 14, "pending_blueprints": 54, "active_builders": 0,
                      "construction_workers": 0,
                      "patients": [], "low_mood": []},
            "stock": {"WoodLog": 0, "Steel": 28, "ComponentIndustrial": 0},
            "course": {"primary_direction": "research_starflight"},
            "risks": ["Construction is queued but wood is zero"],
            "extra_mod_metadata": "x" * 12000,
        }
        fitted = director.fit_model_context(TinyAgent(), state)
        self.assertEqual(fitted["needs"]["pending_blueprints"], 54)
        self.assertEqual(fitted["needs"]["active_builders"], 0)
        self.assertEqual(fitted["needs"]["construction_workers"], 0)
        self.assertEqual(fitted["stock"]["WoodLog"], 0)

    def test_crowded_context_keeps_director_running_with_tiny_window(self):
        class TinyAgent:
            cfg = {"max_len": 300, "head_max_len": 192}

            @staticmethod
            def tok(value, **_kwargs):
                return {"input_ids": list(range((len(value) + 3) // 4))}

        state = {"goal": "Develop the colony", "people": 2, "threats": 1,
                 "home": {"roofed_real_beds": 0, "exposed_days": 4},
                 "needs": {"food": 12, "meals": 0, "least_hunger": 0.15,
                           "downed": 1, "idle_workers": 1,
                           "patients": [{"name": "A" * 1000}],
                           "low_mood": [{"reason": "B" * 1000}]},
                 "stock": {"WoodLog": 0}, "risks": ["R" * 1000],
                 "course": {"primary_direction": "research_starflight"}}
        fitted = director.fit_model_context(TinyAgent(), state)
        self.assertEqual(fitted["people"], 2)
        self.assertEqual(fitted["threats"], 1)
        self.assertLessEqual(len(TinyAgent.tok(json.dumps(fitted))["input_ids"]), 100)

    def test_queued_buildings_without_builder_are_reported_to_laya(self):
        snapshot = {"map": {"resources": {"food": 30}}, "colonists": [
            {"id": 1, "name": "Ivy", "health": 1, "work_priorities": {"Cooking": {"priority": 3}}},
        ], "development": {"construction_projects": [{"def_name": "Wall"}],
                           "item_counts": {"WoodLog": 250}}}
        context = director.model_decision_context(snapshot)
        self.assertEqual(context["needs"]["pending_blueprints"], 1)
        self.assertEqual(context["needs"]["construction_workers"], 0)
        self.assertTrue(any("No living colonist can do Construction" in risk for risk in context["risks"]))

    def test_raw_food_is_not_presented_as_stable_meals(self):
        snapshot = {"map": {"resources": {"food": 90, "meals": 5, "raw_food": 85,
                                          "nutrition_rotting_soon": 12.3}},
                    "colonists": [{"id": 1, "name": "Ivy", "health": 1}],
                    "development": {"building_counts": {}}}
        context = director.model_decision_context(snapshot)
        self.assertEqual(context["needs"]["meals"], 5)
        self.assertEqual(context["needs"]["raw_food"], 85)
        self.assertTrue(any("rot soon" in risk for risk in context["risks"]))

    def test_real_and_medical_beds_are_choices_when_spots_are_still_used(self):
        beds = [{"id": 10, "def": "SleepingSpot", "position": {"x": 10, "z": 10}},
                {"id": 20, "def": "Bed", "label": "good wooden bed", "position": {"x": 12, "z": 10}},
                {"id": 21, "def": "Bed", "label": "normal wooden bed", "position": {"x": 14, "z": 10}}]
        snapshot = {"game": {"tick": 1000}, "map": {"id": 0, "resources": {"food": 30}},
                    "colonists": [{"id": 1, "name": "Sleeper", "health": 1,
                                   "current_job": "LayDown"},
                                  {"id": 2, "name": "Patient", "health": 0.6,
                                   "downed": True, "current_job": "LayDown"}],
                    "combat": {"colonists": [{"id": 1, "current_job_target_id": 10}],
                               "available_weapons": []},
                    "animals": [], "wild_animals": [],
                    "development": {"buildings": beds, "rooms": [{"contained_beds_ids": [20, 21],
                        "cells": [{"x": x, "z": z} for x in range(12, 16) for z in range(10, 13)],
                        "open_roof_count": 0, "touches_map_edge": False}],
                                    "building_counts": {"Bed": 2, "SleepingSpot": 1},
                                    "zones": [], "item_counts": {}, "forbidden": [], "plants": []}}
        state = {"anchor": {"x": 10, "z": 10}, "issued": {}}
        actions, _ = director.candidate_actions(None, snapshot, state)
        self.assertIn("assign_real_bed", actions)
        self.assertIn("prepare_emergency_medical_bed", actions)
        client = mock.Mock()
        client.post.return_value = {"success": True}
        result = director.execute_action(client, snapshot, state, "assign_real_bed",
                                         {"bed_assignment": "1|20"})
        self.assertTrue(result["applied"])
        client.post.assert_called_with("/api/v1/pawn/medical/bed-rest", body={
            "patient_pawn_id": 1, "bed_building_id": 20,
        })
        result = director.execute_action(client, snapshot, state, "prepare_emergency_medical_bed",
                                         {"emergency_medical_bed": "21"})
        self.assertTrue(result["applied"])
        self.assertEqual(client.post.call_args.args[0], "/api/v1/map/beds/configure")

    def test_outdoor_bed_sleeper_can_claim_finished_indoor_bed(self):
        snapshot = {"game": {"tick": 2000}, "map": {"id": 0, "resources": {"food": 30}},
                    "colonists": [{"id": 1, "name": "Sleeper", "health": 1,
                                   "current_job": "LayDown"}],
                    "combat": {"colonists": [{"id": 1, "current_job_target_id": 20}]},
                    "animals": [], "wild_animals": [],
                    "development": {"buildings": [
                        {"id": 20, "def": "Bed", "position": {"x": 20, "z": 20}},
                        {"id": 21, "def": "Bed", "position": {"x": 11, "z": 11}}],
                        "rooms": [{"contained_beds_ids": [21],
                                   "cells": [{"x": x, "z": z} for x in range(10, 14) for z in range(10, 14)],
                                   "open_roof_count": 0, "touches_map_edge": False}],
                        "building_counts": {"Bed": 2}, "zones": [], "item_counts": {},
                        "forbidden": [], "plants": []}}
        state = {"anchor": {"x": 11, "z": 11}, "issued": {},
                 "assigned_real_beds": {"1": 20}}
        actions, _ = director.candidate_actions(None, snapshot, state)
        self.assertIn("assign_real_bed", actions)
        self.assertEqual(snapshot["development"]["bed_assignment_options"].keys(), {"1|21"})

    def test_prison_can_be_prepared_before_raid_and_unflagged_bed_is_capture_ready(self):
        room_cells = [{"x": x, "z": z} for x in range(10, 14) for z in range(10, 14)]
        snapshot = {"game": {"tick": 20000},
                    "map": {"id": 0, "resources": {"food": 50, "meals": 20}, "enemies": 0},
                    "colonists": [{"id": 1, "name": "Builder", "health": 1,
                                   "skills": {"Construction": {"level": 7}},
                                   "work_priorities": {"Construction": {"priority": 2}}}],
                    "combat": {"colonists": [], "hostiles": [], "prisoners": []},
                    "animals": [], "wild_animals": [],
                    "development": {"buildings": [{"id": 20, "def": "Bed", "position": {"x": 11, "z": 11}}],
                        "rooms": [{"id": 1, "contained_beds_ids": [20], "cells": room_cells,
                                   "open_roof_count": 0, "touches_map_edge": False}],
                        "building_counts": {"Bed": 1}, "item_counts": {"WoodLog": 200},
                        "construction_projects": [], "zones": [], "plants": [], "forbidden": []}}
        state = {"anchor": {"x": 11, "z": 11}, "issued": {}}
        actions, _ = director.candidate_actions(None, snapshot, state)
        self.assertIn("build_prison", actions)
        state["prison_site"] = {"x": 30, "z": 30}
        snapshot["development"]["buildings"].append(
            {"id": 30, "def": "SleepingSpot", "position": {"x": 32, "z": 33},
             "for_prisoners": False})
        snapshot["development"]["rooms"].append({"id": 2, "contained_beds_ids": [30],
            "cells": [{"x": x, "z": z} for x in range(30, 37) for z in range(30, 37)],
            "open_roof_count": 0, "touches_map_edge": False})
        self.assertEqual([bed["id"] for bed in director.ready_prison_beds(
            snapshot["development"], state["prison_site"])], [30])
        actions, _ = director.candidate_actions(None, snapshot, state)
        self.assertNotIn("build_prison", actions)

    def test_downed_neutral_arrival_is_a_real_rescue_choice(self):
        snapshot = {"game": {"tick": 20000},
                    "map": {"id": 0, "resources": {"food": 50, "meals": 20}},
                    "colonists": [{"id": 1, "name": "Medic", "health": 1,
                                   "capacities": {"moving": 1}, "position": {"x": 10, "z": 10}}],
                    "combat": {"colonists": [], "hostiles": [],
                               "neutral_downed": [{"id": 30, "name": "Visitor", "is_downed": True,
                                                   "health": 0.5, "position": {"x": 15, "z": 15}}]},
                    "animals": [], "wild_animals": [],
                    "development": {"buildings": [{"id": 20, "def": "Bed", "position": {"x": 11, "z": 11}}],
                                    "building_counts": {"Bed": 1}, "item_counts": {},
                                    "construction_projects": [], "zones": [], "plants": [], "forbidden": []}}
        state = {"anchor": {"x": 10, "z": 10}, "issued": {}}
        actions, _ = director.candidate_actions(None, snapshot, state)
        self.assertIn("rescue_neutral_arrival", actions)
        client = mock.Mock()
        client.post.return_value = {"success": True}
        result = director.execute_action(client, snapshot, state, "rescue_neutral_arrival", {})
        self.assertTrue(result["applied"])
        client.post.assert_called_with("/api/v1/pawn/job", body={
            "pawn_id": 1, "job_def": "Rescue", "target_thing_id": 30, "target_thing_id_b": 20})

    def test_ordinary_wandering_counts_as_idle_but_mental_wandering_does_not(self):
        self.assertTrue(director.colonist_is_idle({"current_job": "Wait_Wander"}))
        self.assertTrue(director.colonist_is_idle({"current_job": "GotoWander"}))
        self.assertFalse(director.colonist_is_idle({"current_job": "GotoWander", "in_mental_state": True}))
        self.assertFalse(director.colonist_is_idle({"current_job": "LayDown"}))
        self.assertTrue(director.requires_builder_now("build_weapon_shelves"))
        self.assertFalse(director.requires_builder_now("build_sleeping_spots"))
        self.assertFalse(director.requires_builder_now("create_growing_zone"))
        snapshot = {"map": {"resources": {"food": 40}}, "colonists": [
            {"id": 1, "name": "Sleepy", "current_job": "Wait_Wander", "health": 1},
        ], "development": {"building_counts": {}}}
        context = director.model_decision_context(snapshot)
        self.assertEqual(context["needs"]["idle_workers"], 1)
        self.assertTrue(any("idle" in risk.lower() for risk in context["risks"]))

    class FakeAgent:
        def __init__(self, choices):
            self.choices = iter(choices)
            self.calls = []
            self.states = []

        def predict(self, state, questions):
            self.calls.append(questions)
            self.states.append(state)
            answers = {}
            for question_id, question in questions.items():
                if question.get("type") == "choice":
                    assert len(question["criteria"]) >= 2, f"Fake model received one-option question {question_id}"
                requested = next(self.choices)
                self.assert_choice(requested, question["criteria"])
                answers[question_id] = {
                    "choice": requested,
                    "confidence": 0.9,
                    "probabilities": {name: 1.0 if name == requested else 0.0 for name in question["criteria"]},
                }
            return {"answers": answers}

        @staticmethod
        def assert_choice(choice, criteria):
            if choice not in criteria:
                raise AssertionError(f"{choice!r} not in {list(criteria)!r}")

    def test_combat_catalog_contains_distinct_positioning_and_threat_tactics(self):
        required = {
            "kite", "melee_block", "wide_flank", "staggered_retreat", "drop_pod_encircle",
            "infestation_choke", "cluster_poke", "intercept_kidnapper", "psycast_control",
        }
        self.assertTrue(required.issubset(colony_combat.TACTICS))
        self.assertGreaterEqual(len(colony_combat.TACTICS), 25)

    def test_psycast_options_include_focus_and_neural_heat_context(self):
        snapshot = {"combat": {"colonists": [{
            "id": 7, "name": "Psy", "health": 1, "is_dead": False, "is_downed": False,
            "psyfocus": 0.62, "neural_heat": 12, "neural_heat_limit": 50,
            "psycasts": [{"def_name": "Stun", "label": "Stun", "description": "brief stun", "hostile": True,
                           "can_cast": True, "psyfocus_cost": 0.02, "entropy_gain": 8}],
        }]}}
        options = colony_combat.psycast_options(snapshot, hostile=True)
        self.assertIn("7:Stun", options)
        self.assertIn("heat 12/50", options["7:Stun"]["summary"])

    def test_combat_tactics_use_existing_defenses_and_focus_kidnapper(self):
        snapshot = {"combat": {
            "colonists": [{"id": 1, "health": 1, "has_ranged_weapon": True, "is_dead": False,
                            "is_downed": False, "distance_to_nearest_opponent": 12}],
            "hostiles": [{"id": 9, "health": 1, "is_dead": False, "is_downed": False,
                           "current_job": "Kidnap", "carrying_pawn_id": 3}],
            "defenses": [{"kind": "trap"}, {"kind": "door"}], "available_weapons": [],
        }}
        options = colony_combat.available_tactics(snapshot)
        self.assertIn("focus_fire", options)
        self.assertNotIn("intercept_kidnapper", options)
        self.assertNotIn("killbox_hold", options)
        self.assertIn("fallback_line", options)

    def test_unknown_mod_event_gets_safe_generic_handler(self):
        event = {"def_name": "MyMod_RealityFold", "label": "Reality fold", "category": "MyModSpecial"}
        self.assertEqual(colony_events.classify_event(event), "unknown")
        options = colony_events.response_options({"family": "unknown"}, {})
        self.assertIn("ask_laya_generic", options)
        self.assertIn("observe_event", options)

    def test_rescue_event_only_offers_mission_after_acceptance_and_site(self):
        event = {"family": "kidnap_rescue"}
        offered = {"active_quests": [{"quest_def": "PrisonerRescue", "ever_accepted": False, "look_targets": [{"world_object_id": 5}]}]}
        self.assertNotIn("prepare_rescue_mission", colony_events.response_options(event, offered))
        accepted = {"active_quests": [{"quest_def": "PrisonerRescue", "ever_accepted": True, "look_targets": [{"world_object_id": 5}]}]}
        self.assertIn("prepare_rescue_mission", colony_events.response_options(event, accepted))
        self.assertNotIn("accept_rescue_quest", colony_events.response_options(event, accepted))

    def test_kidnapped_colonist_is_not_matched_to_unrelated_refugee(self):
        context = {"active_quests": [{"id": 1, "quest_def": "OpportunitySite_DownedRefugee",
                                      "name": "Makoto's Rescue", "description": "Rescue Makoto",
                                      "ever_accepted": True,
                                      "look_targets": [{"world_object_id": 103}]}],
                   "kidnapped_pawns": [{"id": 285, "name": "Lee", "is_kidnapped": True}]}
        lee = {"source": "kidnapped", "family": "kidnap_rescue", "id": 285, "name": "Lee"}
        self.assertEqual(colony_events.matching_rescue_quests(lee, context), [])
        self.assertIsNone(director._event_quest(context, lee))
        pending = colony_events.pending_events(context, set())
        self.assertTrue(any(row["source"] == "quest" for row in pending))
        self.assertFalse(any(row["source"] == "kidnapped" for row in pending))
        context["active_quests"].append({"id": 2, "quest_def": "PrisonerRescue",
                                          "name": "Rescue Lee", "description": "Lee is held captive.",
                                          "ever_accepted": False})
        self.assertEqual(director._event_quest(context, lee)["id"], 2)
        self.assertIn("accept_rescue_quest", colony_events.response_options(lee, context))

    def test_event_history_deduplicates_same_occurrence(self):
        context = {"recent_incidents": [{"incident_def": "HeatWave", "incident_hour": 100, "label": "Heat wave"}]}
        first = colony_events.pending_events(context, set())
        self.assertEqual(len(first), 1)
        self.assertEqual(colony_events.pending_events(context, {first[0]["signature"]}), [])

    def test_bandaged_animal_is_not_retreated_for_low_health_alone(self):
        self.assertFalse(director.animal_needs_tending({
            "health": 0.42,
            "bleeding_rate": 0.0,
            "tendable_now": False,
        }))
        self.assertTrue(director.animal_needs_tending({
            "health": 0.95,
            "bleeding_rate": 0.0,
            "tendable_now": True,
        }))

    def test_hungry_mobile_animal_is_not_forced_into_patient_feeding(self):
        self.assertFalse(director.animal_needs_assisted_feeding({
            "hunger": 0.2,
            "downed": False,
            "current_job": "GotoWander",
        }))
        self.assertTrue(director.animal_needs_assisted_feeding({
            "hunger": 0.0,
            "downed": True,
            "current_job": "LayDown",
        }))
        self.assertTrue(director.animal_needs_assisted_feeding({
            "hunger": 0.2,
            "downed": True,
            "current_job": "LayDown",
        }))

    def test_only_downed_hungry_colonist_is_force_fed(self):
        self.assertFalse(director.colonist_needs_assisted_feeding({"hunger": 0.0, "downed": False}))
        self.assertTrue(director.colonist_needs_assisted_feeding({"hunger": 0.0, "downed": True}))
        self.assertFalse(director.colonist_needs_assisted_feeding({"hunger": 0.8, "downed": True}))

    def test_successful_patient_feed_has_a_real_completion_cooldown(self):
        state = {"issued": {"animal_feed:7": 1000, "colonist_feed:8": 1000}}
        self.assertTrue(director.issued_recently(
            state, "animal_feed:7", 1000 + director.PATIENT_FEED_RETRY_TICKS - 1,
            retry_ticks=director.PATIENT_FEED_RETRY_TICKS,
        ))
        self.assertTrue(director.issued_recently(
            state, "colonist_feed:8", 1000 + director.PATIENT_FEED_RETRY_TICKS - 1,
            retry_ticks=director.PATIENT_FEED_RETRY_TICKS,
        ))

    def test_model_state_discards_verbose_mod_metadata_and_stays_bounded(self):
        skills = {
            f"Skill{index}": {"level": index, "passion": index % 3, "disabled": False}
            for index in range(20)
        }
        colonists = [{
            "id": index, "name": f"Colonist {index}", "health": 1.0, "hunger": 0.5,
            "rest": 0.6, "mood": 0.7, "downed": False, "current_job": "Work",
            "traits": [{"label": f"Trait {item}"} for item in range(8)],
            "capacities": {"moving": 1.0, "manipulation": 1.0, "sight": 1.0},
            "health_conditions": [{"label": f"Condition {item}", "part": "arm"} for item in range(10)],
            "skills": skills,
        } for index in range(16)]
        directions = {
            f"direction_{index}": {
                "label": "direction " + ("x" * 200), "fit_score": 100 - index,
                "people": [{"pawn": "A", "skill": "Crafting", "level": 10, "flame": "++"}],
                "work_types": ["Crafting"] * 20, "building_programs": ["factory"] * 20,
            }
            for index in range(30)
        }
        snapshot = {
            "game": {"date": "5500", "wealth": 1000},
            "map": {"resources": {"food": 20}, "enemies": 0},
            "colonists": colonists,
            "animals": [{"hunger": 0.0}],
            "development": {
                "building_counts": {f"Building{index}": index for index in range(200)},
                "zones": [{"label": f"Zone {index}"} for index in range(100)],
                "current_research": {"name": "Electricity"},
                "finished_research": [f"Research{index}" for index in range(200)],
                "corpses": [], "item_counts": {}, "rooms": [],
                "active_mods": [{
                    "name": f"Mod {index}", "package_id": f"mod.{index}",
                    "description": "verbose metadata " * 1000,
                } for index in range(40)],
                "profession_context": {
                    "directions": directions,
                    "work_types": [{
                        "def_name": f"Work{index}", "label": "work " + ("y" * 200),
                        "relevant_skills": ["Crafting"],
                    } for index in range(100)],
                },
                "building_catalog_summary": {
                    "total_player_buildings": 500, "available_now": 300,
                    "categories": {f"Category{index}": index for index in range(50)},
                    "worktables": [f"Bench{index}" for index in range(100)],
                    "programs": {f"Program{index}": {"label": "program"} for index in range(50)},
                },
                "user_preferences": {},
            },
        }
        encoded = json.dumps(director.build_decision_state(snapshot), ensure_ascii=False, separators=(",", ":"))
        self.assertLessEqual(len(encoded), 12000)
        self.assertNotIn("verbose metadata", encoded)
        self.assertEqual(json.loads(encoded)["colony_animals"]["hungry"], 1)

    def test_doctrine_execution_uses_strategy_module_without_name_shadowing(self):
        map_state = {"anchor": {"x": 10, "z": 10}, "issued": {}}
        result = director.execute_action(
            None,
            {"map": {"id": 1}, "game": {"tick": 50}},
            map_state,
            "choose_colony_doctrine",
            {
                "doctrine_selection": {"economy_product": "art"},
                "doctrine_direction_audit": {"coverage": {}, "expansions": {}, "available": {}, "unavailable": {}},
            },
        )
        self.assertTrue(result["applied"])
        self.assertEqual(map_state["income_strategy"], "art")

    def test_failed_action_uses_bounded_exponential_backoff(self):
        state = {}
        first = director.register_action_failure(state, "build_freezer", "missing component", now=100.0)
        self.assertEqual(first["count"], 1)
        self.assertEqual(director.action_backoff_remaining(state, "build_freezer", now=100.0), 30.0)
        second = director.register_action_failure(state, "build_freezer", "still missing", now=131.0)
        self.assertEqual(second["count"], 2)
        self.assertEqual(director.action_backoff_remaining(state, "build_freezer", now=131.0), 60.0)
        for index in range(8):
            final = director.register_action_failure(state, "build_freezer", f"failure {index}", now=200.0 + index)
        self.assertEqual(float(final["retry_after"]) - 207.0, 300.0)

    def test_success_clears_action_backoff(self):
        state = {}
        director.register_action_failure(state, "build_freezer", "temporary", now=100.0)
        director.clear_action_failure(state, "build_freezer")
        self.assertEqual(director.action_backoff_remaining(state, "build_freezer", now=100.0), 0.0)

    def test_backed_off_event_option_is_removed_without_hiding_alternatives(self):
        state = {}
        director.register_action_failure(state, "event:heat:pause_sowing", "rejected")
        available, blocked = director.filter_backed_off_choices(
            state,
            {"pause_sowing": "Pause", "emergency_harvest": "Harvest"},
            prefix="event:heat:",
        )
        self.assertEqual(available, ["emergency_harvest"])
        self.assertIn("pause_sowing", blocked)

    def test_cycle_errors_back_off_but_missing_game_stays_responsive(self):
        delay, count = director.cycle_retry_policy("error", 0, 10.0)
        self.assertEqual((delay, count), (10.0, 1))
        delay, count = director.cycle_retry_policy("error", 5, 10.0)
        self.assertEqual((delay, count), (300.0, 6))
        delay, count = director.cycle_retry_policy("waiting", 5, 10.0)
        self.assertEqual((delay, count), (10.0, 0))

    def test_combat_signature_does_not_reissue_order_while_pawns_walk(self):
        snapshot = {"combat": {
            "colonists": [{
                "id": 1, "health": 1.0, "is_dead": False, "is_downed": False,
                "is_drafted": True, "weapon_def": "Gun_Revolver", "current_job": "Goto",
                "position": {"x": 10, "z": 10}, "distance_to_nearest_opponent": 20,
            }],
            "hostiles": [{
                "id": 9, "health": 1.0, "is_dead": False, "is_downed": False,
                "current_job": "AttackStatic", "position": {"x": 60, "z": 60},
            }],
        }}
        first = director.combat_order_signature(snapshot)
        snapshot["combat"]["colonists"][0]["position"] = {"x": 35, "z": 32}
        snapshot["combat"]["colonists"][0]["current_job"] = "Wait_Combat"
        snapshot["combat"]["hostiles"][0]["position"] = {"x": 49, "z": 47}
        self.assertEqual(first, director.combat_order_signature(snapshot))
        snapshot["combat"]["hostiles"][0]["health"] = 0.79
        self.assertEqual(first, director.combat_order_signature(snapshot))
        snapshot["combat"]["colonists"][0]["health"] = 0.79
        self.assertNotEqual(first, director.combat_order_signature(snapshot))

    def test_combat_order_has_minimum_and_maximum_replan_intervals(self):
        first = ("active", 1)
        changed = ("active", 2)
        self.assertTrue(director.combat_replan_due(first, None, 0, False))
        self.assertFalse(director.combat_replan_due(changed, first, 2, True))
        self.assertTrue(director.combat_replan_due(changed, first, 5, True))
        self.assertFalse(director.combat_replan_due(first, first, 29, True))
        self.assertTrue(director.combat_replan_due(first, first, 30, True))
        self.assertTrue(director.combat_replan_due(changed, first, 1, True, urgent=True))

    def test_preemptive_advance_is_short_hop_then_replans_on_assault(self):
        snapshot = {"combat": {
            "colonists": [{"id": 1, "health": 1.0, "current_job": "Wait_Combat"},
                          {"id": 2, "health": 1.0, "current_job": "Wait_Combat"}],
            "hostiles": [{"id": 9, "current_job": "GotoWander", "health": 1.0}],
        }}
        record = {
            "decision": {"choice": "preemptive_strike"},
            "action": {"commands": [{"endpoint": "/api/v1/combat/tactic", "body": {
                "tactic": "preemptive_strike", "fighter_ids": [1, 2], "target_pawn_id": 9,
            }}]},
            "result": {"responses": [{"positioned_pawn_ids": [1, 2], "attacking_pawn_ids": []}]},
        }
        self.assertEqual(director.preemptive_advance_state(snapshot, record, 1)[0], "wait")
        self.assertEqual(director.preemptive_advance_state(snapshot, record, 3)[0], "advance")
        snapshot["combat"]["colonists"][0]["current_job"] = "Goto"
        self.assertEqual(director.preemptive_advance_state(snapshot, record, 3)[0], "wait")
        snapshot["combat"]["hostiles"][0]["current_job"] = "AttackMelee"
        self.assertEqual(director.preemptive_advance_state(snapshot, record, 3)[0], "replan")

    def test_laya_can_resume_colony_decisions_during_raid_staging(self):
        snapshot = {"combat": {
            "colonists": [{"id": 1, "is_drafted": False}],
            "hostiles": [{"id": 9, "current_job": "Wait_Wander", "is_dead": False, "is_downed": False,
                          "distance_to_nearest_opponent": 80}],
        }, "map": {"enemies": 1, "resources": {}}, "development": {}, "colonists": [], "animals": []}
        prepared = {"decision": {"choice": "prepare_undrafted"}}
        self.assertTrue(director.staging_development_allowed(snapshot, prepared))
        context = director.model_decision_context(snapshot)
        self.assertEqual(context["threat_state"], {"phase": "preparing", "nearest": 80})
        snapshot["combat"]["colonists"][0]["is_drafted"] = True
        self.assertFalse(director.staging_development_allowed(snapshot, prepared))
        snapshot["combat"]["colonists"][0]["is_drafted"] = False
        snapshot["combat"]["hostiles"][0]["current_job"] = "AttackMelee"
        self.assertFalse(director.staging_development_allowed(snapshot, prepared))
        self.assertEqual(director.model_decision_context(snapshot)["threat_state"]["phase"], "active")

    def test_locked_heartbeat_replace_falls_back_without_crashing(self):
        with tempfile.TemporaryDirectory() as folder:
            target = pathlib.Path(folder) / "runtime-status.json"
            with mock.patch.object(pathlib.Path, "replace", side_effect=PermissionError("locked")):
                written = director.write_runtime_status(target, "running", "healthy")
            self.assertTrue(written)
            self.assertIn('"state": "running"', target.read_text(encoding="utf-8"))

    def test_loading_older_save_discards_orders_from_future_ticks(self):
        state = {"issued": {"priority:Hunting": 5000, "growing": 6000, "old": 50}}
        removed = director.reconcile_issued_timeline(state, 1000)
        self.assertEqual(set(removed), {"priority:Hunting", "growing"})
        self.assertEqual(state["issued"], {"old": 50})
        state["issued"]["future"] = 2000
        self.assertFalse(director.issued_recently(state, "future", 1000))
        self.assertNotIn("future", state["issued"])

    def test_starving_colony_offers_food_actions_before_waiting(self):
        snapshot = {
            "game": {"tick": 1000},
            "map": {"resources": {"food": 0, "raw_food": 0, "meals": 0}},
            "colonists": [{"id": 1, "hunger": 0.05, "position": {"x": 10, "z": 10}}],
            "animals": [],
            "wild_animals": [{
                "id": 9, "def": "Hare", "predator": False, "harm_revenge_chance": 0,
                "combat_power": 33, "meat_amount": 31, "position": {"x": 20, "z": 20},
            }],
            "combat": {"colonists": [{
                "id": 1, "has_ranged_weapon": True, "is_downed": False,
                "health": 1.0, "shooting_skill": 8,
            }]},
            "development": {
                "building_counts": {}, "zones": [], "finished_research": [], "current_research": {},
                "item_counts": {}, "forbidden": [], "corpses": [], "plants": [{
                    "thing_id": 7, "def_name": "Plant_Berry", "label": "berry bush",
                    "harvestable_now": True, "harvest_yield": 10, "harvested_thing_def": "RawBerries",
                    "position": {"x": 30, "z": 20},
                }],
            },
        }
        candidates, details = director.candidate_actions(None, snapshot, {"anchor": {"x": 10, "z": 10}, "issued": {}})
        self.assertIn("harvest_local_plants", candidates)
        self.assertIn("designate_safe_hunting", candidates)
        self.assertNotIn("hold_survival", candidates)
        self.assertIn("create_food_stockpile", candidates)
        self.assertIn("choose_colony_doctrine", candidates)
        self.assertTrue(details["food_emergency_context"]["safe_hunt_targets"])

        stocked = copy.deepcopy(snapshot)
        stocked["map"]["resources"] = {"food": 30, "meals": 30, "raw_food": 0}
        stocked["development"]["things"] = [{
            "thing_id": 55, "categories": ["FoodMeals"], "stack_count": 30,
            "position": {"x": 11, "z": 10}, "is_forbidden": False,
        }]
        stocked["wild_animals"][0]["position"] = {"x": 160, "z": 10}
        stocked_choices, stocked_details = director.candidate_actions(
            None, stocked, {"anchor": {"x": 10, "z": 10}, "issued": {}})
        self.assertNotIn("designate_safe_hunting", stocked_choices)
        self.assertEqual(stocked_details["food_emergency_context"]["safe_hunt_targets"], 0)

        medical = copy.deepcopy(snapshot)
        medical["map"]["resources"] = {"food": 50, "raw_food": 20, "meals": 10, "medicine": 1}
        medical["development"]["zones"] = [
            {"type": "Stockpile", "label": "Laya Food"},
            {"id": 7, "type": "Growing", "label": "Growing zone"},
        ]
        medical["development"]["building_counts"] = {"SleepingSpot": 2}
        medical["development"]["work_tables"] = []
        medical["development"]["current_research"] = {"name": "Electricity"}
        medical["development"]["weather"] = {"growth_season_now": True}
        medical["colonists"][0].update(hunger=0.8, health=0.55, bleeding_rate=0.12, downed=False)
        doctor = {"id": 2, "name": "Doctor", "health": 1.0, "hunger": 0.8,
                  "position": {"x": 12, "z": 10}}
        medical["colonists"].append(doctor)
        with mock.patch.object(director.bridge, "choose_worker", return_value=doctor):
            choices, _ = director.candidate_actions(
                None, medical, {"anchor": {"x": 10, "z": 10}, "issued": {}},
            )
        self.assertIn("prioritize_doctor", choices)
        self.assertIn("harvest_local_plants", choices)

    def test_owned_meals_do_not_hide_starvation_or_long_food_trip(self):
        snapshot = {
            "game": {"tick": 1000}, "map": {"id": 1, "resources": {"food": 30, "meals": 30}},
            "colonists": [
                {"id": 1, "name": "Ada", "hunger": 0.08, "current_job": "FinishFrame",
                 "position": {"x": 10, "z": 10}, "capacities": {"moving": 1}},
                {"id": 2, "name": "Bo", "hunger": 0.21, "current_job": "HaulToCell",
                 "position": {"x": 12, "z": 10}, "capacities": {"moving": 1}},
            ],
            "animals": [], "wild_animals": [], "combat": {"colonists": [], "available_weapons": []},
            "development": {"building_counts": {}, "zones": [{"type": "Stockpile", "label": "Laya Food Freezer"}],
                            "current_research": {"name": "none"}, "work_tables": [], "forbidden": [],
                            "item_counts": {}, "plants": [], "things": [
                                {"thing_id": 91, "label": "survival meals x10", "def_name": "MealSurvivalPack",
                                 "categories": ["FoodMeals"], "stack_count": 10, "is_forbidden": False,
                                 "position": {"x": 100, "z": 10}},
                            ]},
        }
        state = {"anchor": {"x": 10, "z": 10}, "issued": {}}
        candidates, details = director.candidate_actions(None, snapshot, state)
        self.assertIn("create_nearby_food_cache", candidates)
        self.assertNotIn("eat_available_meal", candidates)
        self.assertNotIn("hold_survival", candidates)
        context = director.model_decision_context(snapshot)
        self.assertEqual(context["needs"]["nearest_meal_to_base"], 90)
        self.assertTrue(any("malnutrition" in risk for risk in context["risks"]))
        snapshot["development"]["things"][0]["position"]["x"] = 30
        candidates, details = director.candidate_actions(None, snapshot, state)
        self.assertIn("eat_available_meal", candidates)
        self.assertEqual(len(director.subchoice_questions_for_action("eat_available_meal", snapshot)["hungry_eater"]["criteria"]), 2)
        client = mock.Mock()
        client.post.return_value = {"success": True}
        result = director.execute_action(client, snapshot, state, "eat_available_meal",
                                         {**details, "hungry_eater": 2})
        self.assertTrue(result["applied"])
        self.assertEqual(client.post.call_args.args[0], "/api/v1/pawn/job")
        self.assertEqual(client.post.call_args.kwargs["body"],
                         {"pawn_id": 2, "job_def": "Ingest", "target_thing_id": 91})
        self.assertEqual(director.candidate_actions(None, snapshot, state)[1]["hungry_eater_options"].keys(), {"1"})

    def test_research_requires_a_bench_suitable_for_the_project(self):
        snapshot = {"game": {"tick": 1000}, "map": {"resources": {"food": 10}},
                    "colonists": [{"id": 1, "hunger": 0.8, "position": {"x": 10, "z": 10}}],
                    "animals": [], "wild_animals": [], "combat": {"colonists": [], "available_weapons": []},
                    "development": {"building_counts": {"SimpleResearchBench": 1}, "zones": [],
                                    "current_research": {"name": "none"}, "work_tables": [],
                                    "research_tree": [{"name": "Smithing", "can_start_now": True,
                                                       "player_has_any_appropriate_research_bench": False}],
                                    "forbidden": [], "item_counts": {}, "plants": []}}
        self.assertNotIn("select_research", director.candidate_actions(
            None, snapshot, {"anchor": {"x": 10, "z": 10}, "issued": {}},
        )[0])
        snapshot["development"]["research_tree"][0]["player_has_any_appropriate_research_bench"] = True
        self.assertIn("select_research", director.candidate_actions(
            None, snapshot, {"anchor": {"x": 10, "z": 10}, "issued": {}},
        )[0])

    def test_new_colony_with_same_seed_does_not_inherit_old_orders_or_swamp_anchor(self):
        state = {}
        first = {"game": {"tick": 45000}, "map": {"seed": "shared", "tile_id": 7, "id": 1},
                 "colonists": [{"id": 10}, {"id": 11}]}
        old = director.map_state_for_snapshot(state, first)
        old["issued"]["sleeping_spots"] = 40000
        old["anchor"] = {"x": 20, "z": 20}
        old["doctrine"] = {"material": "WoodLog"}
        second = {"game": {"tick": 900}, "map": {"seed": "shared", "tile_id": 7, "id": 1},
                  "colonists": [{"id": 501}, {"id": 502}]}
        fresh = director.map_state_for_snapshot(state, second)
        self.assertEqual(fresh["issued"], {})
        self.assertNotIn("anchor", fresh)
        self.assertNotIn("doctrine", fresh)
        self.assertEqual(director.map_state_for_snapshot(state, second)["known_colonist_ids"], [501, 502])

    def test_reloaded_base_anchor_stays_near_structures_and_food_when_pawns_roam(self):
        snapshot = {"colonists": [{"position": {"x": 18, "z": 20}},
                                  {"position": {"x": 190, "z": 180}}],
                    "development": {"buildings": [
                        {"def": "Wall", "position": {"x": x, "z": 29}}
                        for x in range(20, 26)
                    ], "things": []}}
        self.assertEqual(director.anchor_from_snapshot(snapshot), {"x": 35, "z": 41})
        snapshot["development"]["buildings"] = []
        snapshot["development"]["things"] = [
            {"thing_id": index, "categories": ["FoodMeals"], "stack_count": 1,
             "position": {"x": x, "z": 30}}
            for index, x in enumerate((21, 22, 23), 1)
        ]
        self.assertEqual(director.anchor_from_snapshot(snapshot), {"x": 34, "z": 42})

    def test_first_base_uses_forbidden_landing_food_not_unlanded_pawn_coordinates(self):
        snapshot = {"colonists": [{"position": {"x": 0, "z": 0}}],
                    "development": {"buildings": [], "things": [
                        {"def_name": "MealSurvivalPack", "categories": ["FoodMeals"],
                         "is_forbidden": True, "position": {"x": x, "z": 115}}
                        for x in (103, 104, 105)
                    ]}}
        self.assertEqual(director.anchor_from_snapshot(snapshot), {"x": 116, "z": 127})
        snapshot["development"]["things"] = []
        self.assertEqual(director.anchor_from_snapshot(snapshot), {"x": 125, "z": 125})

    def test_first_base_uses_full_crashlanded_cargo_not_scattered_single_meals(self):
        things = [
            {"def_name": "MealSurvivalPack", "categories": ["FoodMeals"],
             "is_forbidden": True, "stack_count": 1, "position": {"x": x, "z": 80}}
            for x in (73, 74, 75, 76)
        ] + [
            {"def_name": "MealSurvivalPack", "categories": ["FoodMeals"],
             "is_forbidden": True, "stack_count": 10, "position": {"x": x, "z": 135}}
            for x in (146, 147, 148)
        ]
        snapshot = {"colonists": [{"position": {"x": 0, "z": 0}}],
                    "development": {"buildings": [], "things": things}}
        self.assertEqual(director.anchor_from_snapshot(snapshot), {"x": 159, "z": 147})

    def test_freezer_door_does_not_share_cell_with_wall(self):
        plan = director.freezer_blueprint()
        doors = [item for item in plan["buildings"] if item["def_name"] == "Door"]
        walls = {(item["rel_x"], item["rel_z"]) for item in plan["buildings"]
                 if item["def_name"] == "Wall"}
        self.assertEqual(len(doors), 1)
        self.assertNotIn((doors[0]["rel_x"], doors[0]["rel_z"]), walls)

    def test_legacy_sealed_freezer_offers_normal_deconstruction_then_door(self):
        walls = []
        for x in range(6):
            walls.extend([(x, 0), (x, 5)])
        for z in range(1, 5):
            walls.append((0, z))
            if z != 2:
                walls.append((5, z))
        buildings = [{"id": index, "def": "Wall", "position": {"x": x, "z": z}}
                     for index, (x, z) in enumerate(walls, 10)]
        buildings.append({"id": 99, "def": "Cooler", "position": {"x": 5, "z": 2}})
        snapshot = {"game": {"tick": 1000}, "map": {"id": 1, "resources": {"food": 10, "meals": 10}},
                    "colonists": [{"id": 1, "name": "Ada", "hunger": 0.1, "health": 1.0, "downed": False,
                                   "position": {"x": 3, "z": 7}, "skills": {"Construction": {"level": 6}},
                                   "capacities": {"moving": 1, "manipulation": 1},
                                   "work_priorities": {"Construction": {"priority": 1, "disabled": False}}}],
                    "animals": [], "wild_animals": [], "combat": {"colonists": [], "available_weapons": []},
                    "development": {"building_counts": {"Cooler": 1, "Wall": len(walls)},
                                    "buildings": buildings, "zones": [], "forbidden": [],
                                    "work_tables": [], "item_counts": {"WoodLog": 60}, "plants": [],
                                    "things": [{"thing_id": 90, "categories": ["FoodMeals"],
                                                "stack_count": 10, "position": {"x": 2, "z": 2}}]}}
        state = {"anchor": {"x": 0, "z": 0}, "issued": {}}
        self.assertEqual(director.legacy_freezer_entrance(snapshot)["status"], "sealed")
        self.assertEqual(director.reachable_meals(snapshot), [])
        candidates, details = director.candidate_actions(None, snapshot, state)
        self.assertIn("open_sealed_food_store", candidates)
        self.assertNotIn("eat_available_meal", candidates)
        client = mock.Mock()
        client.post.return_value = {"success": True}
        result = director.execute_action(client, snapshot, state, "open_sealed_food_store",
                                         {**details, "worker_pawn": 1})
        self.assertTrue(result["applied"])
        self.assertEqual(client.post.call_args.args[0], "/api/v1/pawn/job")
        self.assertEqual(client.post.call_args.kwargs["body"]["job_def"], "Deconstruct")
        snapshot["development"]["buildings"] = [row for row in buildings
                                                  if (row["position"]["x"], row["position"]["z"]) != (3, 5)]
        self.assertEqual(director.legacy_freezer_entrance(snapshot)["status"], "open")
        self.assertEqual(len(director.reachable_meals(snapshot)), 1)
        candidates, details = director.candidate_actions(None, snapshot, state)
        self.assertIn("finish_freezer_entrance", candidates)
        result = director.execute_action(client, snapshot, state, "finish_freezer_entrance", details)
        self.assertTrue(result["applied"])
        self.assertEqual(client.post.call_args.args[0], "/api/v1/builder/blueprint")
        self.assertEqual(client.post.call_args.kwargs["body"]["blueprint"]["buildings"][0]["def_name"], "Door")
        snapshot["game"]["tick"] = 14000
        candidates, _ = director.candidate_actions(None, snapshot, state)
        self.assertNotIn("finish_freezer_entrance", candidates)
        snapshot["game"]["tick"] = 16000
        candidates, _ = director.candidate_actions(None, snapshot, state)
        self.assertIn("finish_freezer_entrance", candidates)

    def test_idle_starving_colony_sees_forbidden_food_but_not_wait_or_unusable_research(self):
        snapshot = {
            "game": {"tick": 1000}, "map": {"resources": {"food": 0, "meals": 0, "raw_food": 0}},
            "colonists": [{"id": 1, "name": "Ada", "health": 1, "hunger": 0.08,
                           "current_job": "Wait", "position": {"x": 10, "z": 10}}],
            "animals": [], "wild_animals": [], "combat": {"colonists": [], "available_weapons": []},
            "development": {"building_counts": {}, "zones": [], "forbidden": [{
                "thing_id": 91, "def_name": "MealSurvivalPack", "position": {"x": 15, "z": 10},
            }], "research_tree": [{"name": "Electricity", "can_start_now": True}],
                "work_tables": [], "current_research": {"name": "none"}, "item_counts": {}, "plants": []},
        }
        candidates, _ = director.candidate_actions(None, snapshot, {"anchor": {"x": 10, "z": 10}, "issued": {}})
        self.assertIn("unforbid_supplies", candidates)
        self.assertNotIn("select_research", candidates)
        self.assertNotIn("advance_doctrine_research", candidates)
        self.assertNotIn("hold_survival", candidates)
        context = director.model_decision_context(snapshot)
        self.assertEqual(context["needs"]["forbidden_stacks"], 1)
        self.assertEqual(context["needs"]["idle_workers"], 1)
        ready = copy.deepcopy(snapshot)
        ready["development"]["building_counts"]["SimpleResearchBench"] = 1
        ready["map"]["resources"]["food"] = 20
        ready["development"]["forbidden"] = []
        ready["colonists"][0]["hunger"] = 0.8
        research_choices, _ = director.candidate_actions(
            None, ready, {"anchor": {"x": 10, "z": 10}, "issued": {}},
        )
        self.assertIn("select_research", research_choices)

    def test_direct_rescue_and_tending_are_real_model_choices(self):
        patient = {"id": 1, "name": "Ada", "health": 0.38, "hunger": 0.4,
                   "downed": True, "tendable_now": True, "bleeding_rate": 0.1,
                   "position": {"x": 10, "z": 10}}
        doctor = {"id": 2, "name": "Bo", "health": 1, "downed": False,
                  "position": {"x": 12, "z": 10}, "capacities": {"moving": 1},
                  "work_priorities": {"Doctor": {"priority": 3, "disabled": False}},
                  "skills": {"Medicine": {"level": 8}}}
        snapshot = {"game": {"tick": 1000}, "map": {"id": 1, "resources": {"food": 10, "meals": 3}},
                    "colonists": [patient, doctor], "animals": [], "wild_animals": [],
                    "combat": {"colonists": [], "available_weapons": []},
                    "development": {"building_counts": {"SleepingSpot": 1}, "zones": [],
                        "buildings": [{"id": 77, "def": "SleepingSpot", "position": {"x": 8, "z": 10}}],
                        "forbidden": [], "work_tables": [], "item_counts": {}, "plants": []}}
        state = {"anchor": {"x": 10, "z": 10}, "issued": {}}
        candidates, _ = director.candidate_actions(None, snapshot, state)
        self.assertIn("rescue_downed_colonist", candidates)
        self.assertIn("tend_colonist", candidates)
        client = mock.Mock()
        client.post.return_value = {"ok": True}
        director.execute_action(client, snapshot, state, "rescue_downed_colonist", {})
        self.assertEqual(client.post.call_args.args[0], "/api/v1/pawn/job")
        self.assertEqual(client.post.call_args.kwargs["body"]["job_def"], "Rescue")
        self.assertEqual(client.post.call_args.kwargs["body"]["target_thing_id"], 1)
        director.execute_action(client, snapshot, state, "tend_colonist", {})
        self.assertEqual(client.post.call_args.args[0], "/api/v1/pawn/medical/tend")
        self.assertEqual(client.post.call_args.kwargs["body"]["doctor_pawn_id"], 2)

    def test_paralyzed_recruit_already_in_bed_is_not_rescued_again(self):
        patient = {"id": 51, "name": "Recruited wanderer", "downed": True,
                   "health": 1, "position": {"x": 10, "z": 10}}
        bed = {"id": 77, "def": "Bed", "position": {"x": 10, "z": 10}}
        snapshot = {"combat": {"colonists": [{"id": 51, "current_job": "LayDown",
                                              "current_job_target_id": 77}]}}
        self.assertTrue(director.patient_in_completed_bed(patient, snapshot, [bed]))
        self.assertFalse(director.patient_in_completed_bed(
            {**patient, "position": {"x": 12, "z": 10}},
            {"combat": {"colonists": []}}, [bed]))

    def test_loose_rifle_is_offered_before_any_raid_or_doctrine(self):
        snapshot = {"game": {"tick": 500}, "map": {"id": 1, "resources": {"food": 10, "meals": 2}},
                    "colonists": [{"id": 1, "name": "Ada", "health": 1, "hunger": 0.9,
                                   "position": {"x": 10, "z": 10}}],
                    "animals": [], "wild_animals": [],
                    "combat": {"colonists": [{"id": 1, "name": "Ada", "has_ranged_weapon": False,
                                            "health": 1, "manipulation": 1, "shooting_skill": 7,
                                            "position": {"x": 10, "z": 10}}],
                               "available_weapons": [{"id": 70, "label": "rifle", "is_ranged": True,
                                                      "is_forbidden": True, "position": {"x": 11, "z": 10}}]},
                    "development": {"building_counts": {}, "zones": [], "forbidden": [],
                                    "work_tables": [], "item_counts": {}, "plants": []}}
        state = {"anchor": {"x": 10, "z": 10}, "issued": {}}
        choices, _ = director.candidate_actions(None, snapshot, state)
        self.assertIn("equip_colonists", choices)
        client = mock.Mock()
        client.post.return_value = {"ok": True}
        result = director.execute_action(client, snapshot, state, "equip_colonists", {})
        self.assertTrue(result["applied"])
        self.assertEqual([call.args[0] for call in client.post.call_args_list],
                         ["/api/v1/things/set-forbidden", "/api/v1/pawn/job"])

    def test_low_mood_context_names_observed_needs_without_claiming_exact_thoughts(self):
        snapshot = {"map": {"resources": {"food": 0}}, "colonists": [{
            "id": 1, "name": "Ada", "mood": 0.2, "hunger": 0.1, "joy": 0.1,
            "rest": 0.8, "pain": 0.4, "current_job": "Wait",
        }], "development": {"building_counts": {}}}
        signals = director.model_decision_context(snapshot)["needs"]["low_mood"][0]["signals"]
        self.assertIn("hungry", signals)
        self.assertIn("bored", signals)
        self.assertIn("pain", signals)

    def test_unimpressive_barracks_and_discomfort_reach_model_context(self):
        snapshot = {"map": {"resources": {"food": 35}}, "colonists": [{
            "id": 1, "name": "Pepe", "mood": 0.26, "hunger": 0.6,
            "joy": 0.62, "comfort": 0.0, "beauty": 0.25, "rest": 0.8,
            "current_job": "GotoWander",
        }], "development": {"building_counts": {}, "rooms": [{
            "role_label": "barracks", "impressiveness": -23, "cells_count": 25,
            "temperature": 12, "average_glow": 0.5, "contained_beds_ids": [],
        }]}}
        context = director.model_decision_context(snapshot)
        self.assertIn("uncomfortable", context["needs"]["low_mood"][0]["signals"])
        self.assertIn("ugly surroundings", context["needs"]["low_mood"][0]["signals"])
        self.assertEqual(context["needs"]["worst_barracks"][0]["impressiveness"], -23)
        self.assertTrue(any("barracks" in risk for risk in context["risks"]))

    def test_mental_break_does_not_trigger_repeated_forced_meal_job(self):
        colonists = [{"id": 1, "name": "Pepe", "hunger": 0.0, "position": {"x": 10, "z": 10},
                      "current_job": "GotoWander"}]
        director.bridge.annotate_mental_states(
            colonists, [{"id": 1, "is_in_mental_state": True}]
        )
        self.assertTrue(colonists[0]["in_mental_state"])
        snapshot = {"game": {"tick": 1000}, "map": {"id": 1, "resources": {"food": 20}},
                    "colonists": colonists, "animals": [], "wild_animals": [], "combat": {},
                    "development": {"building_counts": {}, "zones": [], "item_counts": {},
                                    "forbidden": [], "things": [{"id": 99, "def_name": "MealSurvivalPack",
                                                              "stack_count": 5, "position": {"x": 12, "z": 10}}],
                                    "plants": [], "current_research": {"name": "none"}}}
        choices, _ = director.candidate_actions(None, snapshot, {"anchor": {"x": 10, "z": 10}, "issued": {}})
        self.assertNotIn("eat_available_meal", choices)
        self.assertTrue(any("mental break" in risk for risk in director.model_decision_context(snapshot)["risks"]))

    def test_repeated_unfulfilled_meal_jobs_offer_one_adjacent_exit_wall(self):
        snapshot = {"game": {"tick": 6000}, "map": {"id": 1, "resources": {"food": 20}},
                    "colonists": [
                        {"id": 1, "name": "Pepe", "hunger": 0.0, "position": {"x": 162, "z": 114}},
                        {"id": 2, "name": "Builder", "hunger": 0.8,
                         "work_priorities": {"Construction": {"priority": 2, "disabled": False}},
                         "position": {"x": 159, "z": 114}},
                    ], "animals": [], "wild_animals": [], "combat": {},
                    "development": {"building_counts": {}, "zones": [], "item_counts": {},
                                    "forbidden": [], "current_research": {"name": "none"},
                                    "buildings": [{"id": 90, "def": "Wall", "position": {"x": 161, "z": 114}}],
                                    "things": [{"thing_id": 99, "def_name": "MealSurvivalPack",
                                                "stack_count": 5, "position": {"x": 140, "z": 114}}],
                                    "plants": []}}
        state = {"anchor": {"x": 160, "z": 114}, "issued": {},
                 "meal_attempts": {"1": {"tick": 3000, "hunger": 0.0,
                                         "checked_tick": 3000, "failures": 2}}}
        with mock.patch.object(director, "reachable_meals", return_value=[
            {"thing_id": 99, "label": "meal", "position": {"x": 140, "z": 114}}
        ]):
            choices, details = director.candidate_actions(None, snapshot, state)
        self.assertIn("open_blocked_food_path", choices)
        self.assertEqual(details["blocked_food_wall_options"][0]["id"], 90)
        client = mock.Mock()
        result = director.execute_action(client, snapshot, state, "open_blocked_food_path",
                                         {**details, "blocked_food_wall": 90, "worker_pawn": 2})
        self.assertTrue(result["applied"])
        client.post.assert_called_once_with("/api/v1/pawn/job", body={
            "pawn_id": 2, "job_def": "Deconstruct", "target_thing_id": 90,
        })

    def test_bed_shortage_and_rest_are_visible_to_laya(self):
        snapshot = {"map": {"resources": {"food": 50}}, "colonists": [
            {"id": 1, "name": "Ada", "rest": 0.18, "hunger": 0.7, "current_job": "LayDown"},
            {"id": 2, "name": "Bo", "rest": 0.6, "hunger": 0.8, "current_job": "Haul"},
        ], "development": {"building_counts": {"SleepingSpot": 0, "Bed": 0}}}
        context = director.model_decision_context(snapshot)
        self.assertEqual(context["needs"]["least_rest"], 0.18)
        self.assertEqual(context["needs"]["beds"], 0)
        self.assertTrue(any("sleeping places" in risk for risk in context["risks"]))

    def test_outdoor_spots_do_not_hide_sheltered_bed_shortage(self):
        buildings = [
            {"id": 10, "def": "SleepingSpot", "position": {"x": 126, "z": 107}, "size": {"x": 1, "z": 2}},
            {"id": 11, "def": "SleepingSpot", "position": {"x": 128, "z": 107}, "size": {"x": 1, "z": 2}},
            *({"id": 20 + i, "def": "SleepingSpot", "position": {"x": 137 + i * 2, "z": 120},
               "size": {"x": 1, "z": 2}} for i in range(4)),
        ]
        rooms = [{"id": 1, "touches_map_edge": False, "is_prison_cell": False,
                  "open_roof_count": 0, "cells_count": 25,
                  "contained_beds_ids": [10, 11],
                  "cells": [{"x": x, "z": z} for x in range(125, 130) for z in range(105, 110)]},
                 {"id": 2, "touches_map_edge": True, "open_roof_count": 59000,
                  "contained_beds_ids": [20, 21, 22, 23], "cells": []}]
        snapshot = {
            "game": {"tick": 10000}, "map": {"id": 1, "resources": {"food": 45}},
            "colonists": [{"id": i, "name": f"Colonist {i}", "hunger": 0.8} for i in range(3)],
            "animals": [], "wild_animals": [],
            "combat": {"colonists": [], "available_weapons": []},
            "development": {"building_counts": {"SleepingSpot": 6}, "buildings": buildings,
                            "rooms": rooms, "zones": [], "item_counts": {}, "forbidden": [],
                            "things": [], "plants": []},
        }
        context = director.model_decision_context(snapshot)
        self.assertEqual(context["needs"]["beds"], 6)
        self.assertEqual(context["needs"]["sheltered_beds"], 2)
        self.assertTrue(any("roofed sleeping places" in risk for risk in context["risks"]))
        map_state = {"anchor": {"x": 120, "z": 100}, "issued": {}}
        candidates, details = director.candidate_actions(None, snapshot, map_state)
        self.assertIn("build_sleeping_spots", candidates)
        self.assertEqual(details["indoor_sleeping_spot"], {"x": 127, "z": 107})
        client = mock.Mock()
        client.post.return_value = {"success": True}
        client.get.side_effect = [{}, [{"def": "SleepingSpot", "position": {"x": 127, "z": 107}}]]
        with mock.patch.object(director, "open_bed_site", return_value=None):
            result = director.execute_action(client, snapshot, map_state, "build_sleeping_spots", details)
        self.assertTrue(result["applied"])
        self.assertEqual(client.post.call_args.kwargs["body"]["position"],
                         {"x": 127, "y": 0, "z": 107})
        self.assertEqual([row["def_name"] for row in
                          client.post.call_args.kwargs["body"]["blueprint"]["buildings"]], ["SleepingSpot"])

    def test_distant_ruin_is_not_a_colony_sleeping_site(self):
        far_room = {"touches_map_edge": False, "is_prison_cell": False,
                    "is_doorway": False, "open_roof_count": 0,
                    "contained_beds_ids": [], "cells_count": 2,
                    "cells": [{"x": 150, "z": 40}, {"x": 150, "z": 41}]}
        self.assertIsNone(director.empty_indoor_sleeping_spot(
            {"buildings": [], "rooms": [far_room]}, {"x": 140, "z": 140}))

    def test_nearby_ancient_danger_is_not_a_bedroom(self):
        danger = {"id": 22, "role_label": "dining room", "touches_map_edge": False,
                  "is_prison_cell": False, "is_doorway": False, "open_roof_count": 0,
                  "contained_beds_ids": [], "cells_count": 4,
                  "contained_thing_defs": ["AncientCryptosleepCasket", "Mech_Scyther"],
                  "light_placement_cells": [{"x": 150, "z": 130}],
                  "dark_cells_percent": 96,
                  "cells": [{"x": 150, "z": z} for z in range(130, 134)]}
        self.assertTrue(director.room_is_ancient_danger(danger))
        self.assertIsNone(director.empty_indoor_sleeping_spot(
            {"buildings": [], "rooms": [danger]}, {"x": 151, "z": 143}))

    def test_roofed_ruin_outside_starter_house_is_not_a_bedroom(self):
        nearby_ruin = {"touches_map_edge": False, "is_prison_cell": False,
                       "is_doorway": False, "open_roof_count": 0,
                       "contained_beds_ids": [], "cells_count": 4,
                       "cells": [{"x": x, "z": z} for x in (150, 151) for z in (129, 130)]}
        self.assertIsNone(director.empty_indoor_sleeping_spot(
            {"buildings": [], "rooms": [nearby_ruin]}, {"x": 151, "z": 143}))

    def test_sleeping_spot_api_success_without_placement_is_not_reported_as_applied(self):
        client = mock.Mock()
        client.post.return_value = {"success": True}
        client.get.side_effect = [{}, []]
        snapshot = {"map": {"id": 0}, "game": {"tick": 1000},
                    "development": {"buildings": []}, "colonists": [{"id": 1}]}
        map_state = {"anchor": {"x": 140, "z": 140}, "issued": {}}
        with mock.patch.object(director, "open_bed_site", return_value={"x": 141, "z": 149}):
            result = director.execute_action(client, snapshot, map_state, "build_sleeping_spots", {})
        self.assertFalse(result["applied"])
        self.assertIn("placed no sleeping spot", result["reason"])

    def test_failed_build_project_is_held_until_materials_change(self):
        snapshot = {
            "game": {"tick": 12000}, "map": {"id": 1, "resources": {"food": 40}},
            "colonists": [{"id": 1, "name": "Builder", "hunger": 0.8,
                           "work_priorities": {"Construction": {"priority": 3, "disabled": False}}}],
            "animals": [], "wild_animals": [],
            "combat": {"colonists": [], "available_weapons": []},
            "development": {"building_counts": {}, "zones": [], "item_counts": {"WoodLog": 20},
                            "forbidden": [], "things": [], "plants": [],
                            "work_tables": [{"id": 2, "thing_def": "TableStonecutter"}],
                            "construction_projects": [{"thing_id": 91, "def_name": "Wall", "kind": "blueprint"}]},
        }
        state = {"anchor": {"x": 10, "z": 10}, "issued": {},
                 "failed_construction_projects": {"91": {"tick": 11000, "wood": 20}}}
        candidates, _ = director.candidate_actions(None, snapshot, state)
        self.assertNotIn("prioritize_construction_project", candidates)
        self.assertNotIn("configure_food_bills", candidates)
        snapshot["development"]["item_counts"]["WoodLog"] = 30
        candidates, _ = director.candidate_actions(None, snapshot, state)
        self.assertIn("prioritize_construction_project", candidates)
        snapshot["development"]["work_tables"] = [{"id": 3, "thing_def": "FueledStove"}]
        candidates, _ = director.candidate_actions(None, snapshot, state)
        self.assertIn("configure_food_bills", candidates)

    def test_campfire_is_survival_choice_until_cooking_station_exists(self):
        snapshot = {
            "game": {"tick": 12000}, "map": {"id": 1, "resources": {"food": 5, "raw_food": 5}},
            "colonists": [{"id": 1, "name": "Builder", "health": 1, "hunger": 0.5,
                           "work_priorities": {"Construction": {"priority": 2}}}],
            "animals": [], "wild_animals": [], "combat": {},
            "development": {"building_counts": {}, "buildings": [], "rooms": [],
                            "zones": [], "forbidden": [], "things": [], "plants": [],
                            "work_tables": [], "item_counts": {"WoodLog": 20},
                            "construction_projects": []},
        }
        state = {"anchor": {"x": 10, "z": 10}, "issued": {}}
        actions, _ = director.candidate_actions(None, snapshot, state)
        self.assertIn("build_campfire", actions)
        snapshot["development"]["construction_projects"] = [{"def_name": "Campfire"}]
        actions, _ = director.candidate_actions(None, snapshot, state)
        self.assertNotIn("build_campfire", actions)
        snapshot["development"]["construction_projects"] = []
        snapshot["development"]["work_tables"] = [{"id": 5, "thing_def": "Campfire"}]
        snapshot["development"]["building_counts"]["Campfire"] = 1
        actions, _ = director.candidate_actions(None, snapshot, state)
        self.assertNotIn("build_campfire", actions)
        self.assertIn("configure_food_bills", actions)

    def test_work_priority_choices_require_a_workstation_for_cooking_and_research(self):
        snapshot = {"colonists": [{"id": 1, "work_priorities": {
            "Research": {"priority": 3}, "Cooking": {"priority": 3},
            "Construction": {"priority": 3}}}], "development": {
            "building_counts": {}, "work_types": ["Research", "Cooking", "Construction"]}}
        self.assertEqual(director.live_work_options(snapshot).keys(), {"Construction"})
        snapshot["development"]["building_counts"] = {"Campfire": 1, "SimpleResearchBench": 1}
        self.assertEqual(director.live_work_options(snapshot).keys(),
                         {"Research", "Cooking", "Construction"})

    def test_zero_priority_builder_can_be_reenabled_and_backlog_is_visible(self):
        snapshot = {"map": {"resources": {"food": 30}}, "colonists": [
            {"id": 1, "name": "Buck", "current_job": "FinishFrame", "health": 1,
             "work_priorities": {"Construction": {"priority": 1, "disabled": False}}},
            {"id": 2, "name": "Kelly", "current_job": "GotoWander", "health": 1,
             "work_priorities": {"Construction": {"priority": 0, "disabled": False}}},
        ], "development": {
            "work_types": ["Construction"], "item_counts": {"WoodLog": 250},
            "construction_projects": [{"def_name": "Wall"} for _ in range(16)],
        }}
        self.assertIn("Construction", director.live_work_options(snapshot))
        self.assertEqual(set(director.worker_criteria(snapshot, "Construction")), {"1", "2"})
        context = director.model_decision_context(snapshot)
        self.assertEqual(context["needs"]["active_builders"], 1)
        self.assertEqual(context["needs"]["construction_workers"], 1)
        self.assertEqual(context["needs"]["eligible_builders"], 2)
        self.assertTrue(any("16 unfinished building jobs" in risk for risk in context["risks"]))

    def test_construction_shortlist_keeps_bed_visible_among_wall_frames(self):
        snapshot = {
            "game": {"tick": 12000}, "map": {"id": 1, "resources": {"food": 40}},
            "colonists": [{"id": 1, "name": "Builder", "hunger": 0.8,
                           "work_priorities": {"Construction": {"priority": 1, "disabled": False}}}],
            "animals": [], "wild_animals": [], "combat": {},
            "development": {"building_counts": {}, "zones": [], "item_counts": {"Steel": 100},
                            "forbidden": [], "things": [], "plants": [], "work_tables": [],
                            "construction_projects": [
                                *[{"thing_id": i, "def_name": "Wall", "kind": "frame",
                                   "position": {"x": i, "z": 10}} for i in range(100, 145)],
                                {"thing_id": 200, "def_name": "Bed", "kind": "blueprint",
                                 "position": {"x": 12, "z": 12}}]},
        }
        choices, details = director.candidate_actions(None, snapshot,
                                                      {"anchor": {"x": 10, "z": 10}, "issued": {}})
        self.assertIn("prioritize_construction_project", choices)
        self.assertIn(200, [row["thing_id"] for row in details["construction_project_options"]])
        self.assertLessEqual(len(details["construction_project_options"]), 16)
        self.assertIn("shelter", director.action_description("prioritize_construction_project", snapshot))
        self.assertIn("0 colonists are building", director.action_description("hold_survival", snapshot))
        context = director.model_decision_context(snapshot)
        self.assertEqual(context["needs"]["pending_blueprints"], 46)
        self.assertEqual(context["needs"]["active_builders"], 0)

    def test_construction_shortlist_ignores_sealed_danger_blueprints(self):
        danger = {"contained_thing_defs": ["AncientCryptosleepCasket"],
                  "cells": [{"x": 20, "z": 20}], "open_roof_count": 0}
        snapshot = {
            "game": {"tick": 12000}, "map": {"id": 1, "resources": {"food": 40}},
            "colonists": [{"id": 1, "name": "Builder", "hunger": 0.8,
                           "work_priorities": {"Construction": {"priority": 1, "disabled": False}}}],
            "animals": [], "wild_animals": [], "combat": {},
            "development": {"building_counts": {}, "zones": [], "item_counts": {"Steel": 100},
                            "forbidden": [], "things": [], "plants": [], "work_tables": [],
                            "rooms": [danger],
                            "construction_projects": [
                                {"thing_id": 1, "def_name": "Bed", "kind": "blueprint",
                                 "position": {"x": 20, "z": 20}},
                                {"thing_id": 2, "def_name": "Wall", "kind": "frame",
                                 "position": {"x": 11, "z": 11}}]},
        }
        choices, details = director.candidate_actions(None, snapshot,
                                                      {"anchor": {"x": 10, "z": 10}, "issued": {}})
        self.assertIn("prioritize_construction_project", choices)
        self.assertEqual([row["thing_id"] for row in details["construction_project_options"]], [2])

    def test_decodes_rle_terrain(self):
        width, height, cells = director.decode_terrain({
            "width": 3,
            "height": 2,
            "palette": ["Soil", "Sand"],
            "grid": [3, 0, 3, 1],
        })
        self.assertEqual((width, height), (3, 2))
        self.assertEqual(cells, ["Soil"] * 3 + ["Sand"] * 3)

    def test_finds_fertile_rectangle(self):
        result = director.find_terrain_rect(
            {"width": 6, "height": 6, "palette": ["Sand", "Soil"], "grid": [7, 0, 4, 1, 2, 0, 4, 1, 19, 0]},
            {"x": 2, "z": 2},
            2,
            2,
            {"Soil"},
            radius=5,
        )
        self.assertEqual(result, {"x": 2, "z": 1})

    def test_starter_site_moves_off_marsh_to_full_dry_footprint(self):
        width, height = 30, 25
        cells = [1 if 5 <= x < 20 and 5 <= z < 16 else 0
                 for z in range(height) for x in range(width)]
        encoded = []
        for cell in cells:
            if encoded and encoded[-1] == cell:
                encoded[-2] += 1
            else:
                encoded.extend([1, cell])
        terrain = {"width": width, "height": height,
                   "palette": ["Marsh", "Soil"], "grid": encoded}
        self.assertEqual(director.find_dry_starter_site(terrain, {"x": 10, "z": 9}),
                         {"x": 10, "z": 9})

    def test_single_feasible_action_does_not_call_model(self):
        decision = director.choose_action(None, {}, ["create_stockpile"])
        self.assertEqual(decision["choice"], "create_stockpile")
        self.assertEqual(decision["raw"]["mode"], "single_feasible_action")

    def test_domain_choice_describes_feasible_actions_not_generic_promise(self):
        snapshot = {"map": {"resources": {"food": 53}, "enemies": 0},
                    "colonists": [], "animals": [], "development": {"corpses": [], "trade_value": 0}}
        candidates = ["hold_survival", "build_sleeping_spots", "build_basic_beds",
                      "build_hospital", "build_prison", "prioritize_hauling", "create_stockpile"]
        agent = self.FakeAgent(["strategy"])
        decision = director.choose_action(agent, snapshot, candidates)
        criteria = agent.calls[0]["colony_goal_domain"]["criteria"]
        self.assertIn("Issue no new project", criteria["strategy"])
        self.assertNotIn("research, doctrine, supplies", criteria["strategy"])
        self.assertIn("prison", criteria["care"].lower())
        self.assertIn("clinic", criteria["care"].lower())
        self.assertEqual(decision["choice"], "hold_survival")

    def test_starving_colony_exposes_food_cost_in_hierarchical_choices(self):
        snapshot = {"map": {"resources": {"food": 0}, "enemies": 0},
                    "colonists": [{"id": 7, "name": "Ada", "hunger": 0.02,
                                   "health": 0.8, "rest": 0.6, "current_job": "Wait_Wander"}],
                    "animals": [], "development": {"corpses": [], "trade_value": 0}}
        candidates = ["harvest_local_plants", "designate_safe_hunting",
                      "prioritize_plant_cutting", "prioritize_hunting", "prioritize_burial",
                      "start_stonecutting", "harvest_nearby_trees", "prioritize_growing",
                      "prioritize_cleaning", "hold_survival"]
        agent = self.FakeAgent(["work_orders", "harvest_nearby_trees"])
        decision = director.choose_action(agent, snapshot, candidates)
        self.assertEqual(decision["choice"], "harvest_nearby_trees")
        domain = agent.calls[0]["colony_goal_domain"]["criteria"]
        family = agent.calls[1]["colony_goal_family"]["criteria"]
        self.assertIn("food is empty", domain["work_orders"])
        self.assertIn("cannot be eaten", family["harvest_nearby_trees"])
        self.assertIn("edible wild plants", family["harvest_local_plants"])

    def test_overlay_uses_real_family_probabilities_after_singleton_narrowing(self):
        snapshot = {"map": {"resources": {"food": 39}, "enemies": 0},
                    "colonists": [], "animals": [], "development": {"corpses": [], "trade_value": 0}}
        decision = {"choice": "choose_colony_doctrine", "raw": {
            "answers": {"colony_goal_action": {"choice": "choose_colony_doctrine",
                                                "probabilities": {"choose_colony_doctrine": 1.0}}},
            "family": {"answers": {"colony_goal_family": {
                "choice": "choose_colony_doctrine",
                "probabilities": {"choose_colony_doctrine": 0.3, "hold_survival": 0.7},
            }}},
        }}
        with mock.patch.object(director, "show_overlay") as overlay:
            director.publish_overlay(None, snapshot, ["choose_colony_doctrine"], decision)
        bars = overlay.call_args.kwargs["bars"]
        self.assertEqual(len(bars), 2)
        self.assertEqual({bar["value"] for bar in bars}, {0.3, 0.7})
        self.assertTrue(next(bar for bar in bars if bar["selected"])["value"] < 1.0)

    def test_overlay_shortens_labels_without_changing_probabilities(self):
        bars = director.probability_bars(
            {"trade_now": 0.43, "skip_trade": 0.57},
            {"trade_now": "A very long trader option explaining every possible detail of the transaction",
             "skip_trade": "Skip trade"},
            "skip_trade", 5,
        )
        self.assertLessEqual(len(bars[1]["label"]), 44)
        self.assertEqual([bar["value"] for bar in bars], [0.57, 0.43])

    def test_english_game_overlay_has_no_cyrillic(self):
        class Client:
            def __init__(self):
                self.body = None

            def get(self, path):
                self.assert_path = path
                return {"language": "English"}

            def post(self, path, body):
                self.body = body

        client = Client()
        snapshot = {"map": {"resources": {"food": 39}, "enemies": 0},
                    "colonists": [], "animals": [], "development": {"corpses": [], "trade_value": 0}}
        decision = {"choice": "build_starter_base", "raw": {"answers": {
            "colony_goal_action": {"choice": "build_starter_base", "probabilities": {
                "build_starter_base": 0.62, "hold_survival": 0.38,
            }}}}}
        director.publish_overlay(client, snapshot, ["build_starter_base", "hold_survival"], decision)
        self.assertEqual(client.assert_path, "/api/v1/game/settings")
        self.assertIn("Chosen: Starter base", client.body["text"])
        self.assertFalse(any("\u0400" <= char <= "\u04ff" for char in client.body["text"]))
        self.assertFalse(any("\u0400" <= char <= "\u04ff"
                             for bar in client.body["bars"] for char in bar["label"]))

    def test_live_moded_research_is_a_model_choice_not_ship_route(self):
        snapshot = {"colonists": [], "game": {}, "map": {"resources": {}}, "development": {
            "building_counts": {}, "zones": [], "research_tree": [
                {"name": "ShipBasics", "can_start_now": False, "is_finished": False},
                {"name": "Mod_AlgaePower", "label": "Algae generators", "can_start_now": True, "research_points": 350},
            ], "current_research": {"name": "none"},
        }}
        options = director.live_research_options(snapshot)
        self.assertEqual(set(options), {"Mod_AlgaePower"})
        agent = self.FakeAgent(["select_research"])
        snapshot["development"]["live_research_options"] = options
        decision = director.choose_action(agent, snapshot, ["hold_survival", "select_research"])
        self.assertEqual(decision["research_target"], "Mod_AlgaePower")
        self.assertEqual(len(agent.calls), 1)  # no fake one-option target question

    def test_live_mod_work_asks_work_then_worker_then_priority(self):
        colonists = [{"id": 7, "name": "Ada", "health": 0.8, "pain": 0.1, "downed": False,
                      "work_priorities": {"Mod_AlgaeFarming": {"priority": 3, "disabled": False}},
                      "skills": {"Plants": {"level": 12, "passion": 2}}, "traits": []}]
        snapshot = {"colonists": colonists, "game": {}, "map": {"resources": {}}, "development": {
            "building_counts": {}, "zones": [], "work_types": [{"def_name": "Mod_AlgaeFarming", "label": "Algae farming", "relevant_skills": ["Plants"]}],
        }}
        snapshot["development"]["live_work_options"] = director.live_work_options(snapshot)
        self.assertIn("Mod_AlgaeFarming", snapshot["development"]["live_work_options"])
        agent = self.FakeAgent(["set_work_priority", "1"])
        decision = director.choose_action(agent, snapshot, ["hold_survival", "set_work_priority"])
        self.assertEqual((decision["work_type"], decision["worker_pawn"], decision["work_priority"]),
                         ("Mod_AlgaeFarming", 7, 1))
        self.assertEqual(len(agent.calls), 2)  # one-option work/worker resolved by code
        self.assertIn("Plants 12", director.worker_criteria(snapshot, "Mod_AlgaeFarming")["7"])

        class Client:
            def __init__(self):
                self.calls = []
            def post(self, endpoint, **kwargs):
                self.calls.append((endpoint, kwargs))
                return {"success": True}

        client = Client()
        result = director.execute_action(client, {**snapshot, "map": {"id": 1, "resources": {}}},
                                         {"issued": {}, "anchor": {"x": 10, "z": 10}},
                                         "set_work_priority", decision)
        self.assertTrue(result["applied"])
        self.assertEqual(client.calls[0][1]["body"], {"id": 7, "work": "Mod_AlgaeFarming", "priority": 1})

    def test_large_option_set_keeps_last_option_reachable(self):
        options = {f"option_{index}": f"Project {index}" for index in range(17)}
        class TailAgent:
            def __init__(self):
                self.calls = []
            def predict(self, state, questions):
                self.calls.append(questions)
                question_id, question = next(iter(questions.items()))
                criteria = question["criteria"]
                chosen = "option_16" if "option_16" in criteria else next(iter(criteria))
                return {"answers": {question_id: {"choice": chosen, "confidence": 0.9}}}
        agent = TailAgent()
        selected, raw = director.ask_laya_choice(agent, {}, "project", "Choose a project", options)
        self.assertEqual(selected, "option_16")
        self.assertEqual(len(agent.calls), 4)
        self.assertEqual(len(raw["narrowing"]), 3)
        self.assertEqual(set().union(*(set(next(iter(call.values()))["criteria"]) for call in agent.calls[:-1])), set(options))

    def test_rejected_hunting_does_not_ask_for_a_target(self):
        agent = self.FakeAgent(["hold_survival"])
        snapshot = {"colonists": [], "game": {}, "map": {"resources": {}}, "development": {
            "hunt_options": [{"id": 7, "def": "Hare"}], "fighter_context": {}, "building_counts": {}, "zones": [],
        }}
        result = director.choose_action(agent, snapshot, ["designate_safe_hunting", "hold_survival"])
        self.assertEqual(result["choice"], "hold_survival")
        self.assertEqual(len(agent.calls), 1)
        self.assertEqual(set(agent.calls[0]), {"colony_goal_action"})

    def test_selected_hunting_asks_target_in_second_stage_only(self):
        agent = self.FakeAgent(["designate_safe_hunting", "7"])
        snapshot = {"colonists": [], "game": {}, "map": {"resources": {}}, "development": {
            "hunt_options": [{"id": 7, "def": "Hare", "gender": "Female", "combat_power": 10, "harm_revenge_chance": 0,
                              "meat_amount": 18, "leather_amount": 8, "market_value": 60},
                             {"id": 8, "def": "Deer", "gender": "Male", "combat_power": 30, "harm_revenge_chance": 0.02,
                              "meat_amount": 55, "leather_amount": 20, "market_value": 150}],
            "wild_plant_options": {"Plant_Ambrosia": {"count": 4}}, "fighter_context": {}, "building_counts": {}, "zones": [],
        }}
        result = director.choose_action(agent, snapshot, ["designate_safe_hunting", "hold_survival"])
        self.assertEqual(result["hunt_target"], 7)
        self.assertEqual(len(agent.calls), 2)
        self.assertEqual(set(agent.calls[1]), {"hunt_target"})
        self.assertNotIn("wild_plant_type", agent.calls[1])

    def test_rhinoceros_is_not_mislabelled_safe_hunting(self):
        snapshot = {
            "game": {"tick": 1000}, "map": {"id": 1, "resources": {"food": 39, "meals": 39}},
            "colonists": [{"id": 1, "name": "Hunter", "health": 1, "hunger": 0.8, "joy": 0.8,
                           "mood": 0.6, "position": {"x": 20, "z": 20}}],
            "animals": [], "wild_animals": [
                {"id": 9, "def": "Rhinoceros", "position": {"x": 25, "z": 20}, "combat_power": 270,
                 "harm_revenge_chance": 0.5, "meat_amount": 420},
                {"id": 10, "def": "Hare", "position": {"x": 24, "z": 20}, "combat_power": 33,
                 "harm_revenge_chance": 0, "meat_amount": 31},
            ],
            "combat": {"colonists": [{"id": 1, "has_ranged_weapon": True, "is_downed": False,
                                       "health": 1, "shooting_skill": 7}]},
            "development": {"building_counts": {}, "zones": [], "current_research": {"name": "none"},
                            "item_counts": {}, "work_tables": [], "forbidden": [], "plants": [], "things": []},
        }
        candidates, details = director.candidate_actions(None, snapshot, {"anchor": {"x": 20, "z": 20}, "issued": {}})
        self.assertIn("consider_dangerous_hunt", candidates)
        self.assertEqual([row["id"] for row in details["hunt_options"]], [10])
        self.assertEqual([row["id"] for row in details["risky_hunt_options"]], [9])

    def test_wood_shortage_offers_exact_tree_cutting_and_tracks_designations(self):
        snapshot = {
            "game": {"tick": 1000}, "map": {"id": 1, "resources": {"food": 30}},
            "colonists": [{"id": 1, "name": "Builder", "health": 1, "hunger": 0.8,
                           "position": {"x": 10, "z": 10}}],
            "animals": [], "wild_animals": [], "combat": {},
            "development": {
                "building_counts": {}, "zones": [], "item_counts": {}, "forbidden": [],
                "current_research": {"name": "none"},
                "construction_projects": [{"thing_id": 44, "label": "wall"}],
                "plants": [
                    {"thing_id": 20, "def_name": "Plant_TreeOak", "label": "oak tree",
                     "harvestable_now": True, "harvest_yield": 25,
                     "harvested_thing_def": "WoodLog", "position": {"x": 12, "z": 10}},
                    {"thing_id": 21, "def_name": "Plant_TreeOak", "label": "oak tree",
                     "harvestable_now": True, "harvest_yield": 25,
                     "harvested_thing_def": "WoodLog", "position": {"x": 18, "z": 10}},
                ],
            },
        }
        state = {"anchor": {"x": 10, "z": 10}, "issued": {}}
        choices, details = director.candidate_actions(None, snapshot, state)
        self.assertIn("harvest_nearby_trees", choices)
        self.assertEqual(details["tree_options"]["Plant_TreeOak"]["count"], 2)
        client = mock.Mock()
        result = director.execute_action(client, snapshot, state, "harvest_nearby_trees",
                                         {**details, "tree_type": "Plant_TreeOak"})
        self.assertTrue(result["applied"])
        client.post.assert_called_once_with("/api/v1/map/plants/harvest",
                                            body={"map_id": 1, "plant_ids": [20, 21]})
        self.assertIn("tree:20", state["issued"])
        state["issued"].pop("wood_harvest")
        choices, _ = director.candidate_actions(None, snapshot, state)
        self.assertNotIn("harvest_nearby_trees", choices)

    def test_real_bed_waits_for_roofed_room_and_needs_only_one_bed_material_cost(self):
        snapshot = {
            "game": {"tick": 1000}, "map": {"id": 1, "resources": {"food": 30}},
            "colonists": [{"id": 1, "name": "Builder", "health": 1,
                           "skills": {"Construction": {"level": 5}}, "hunger": 0.8,
                           "work_priorities": {"Construction": {"priority": 3}},
                           "position": {"x": 10, "z": 10}}],
            "animals": [], "wild_animals": [], "combat": {},
            "development": {"building_counts": {"SleepingSpot": 1}, "zones": [],
                            "item_counts": {"WoodLog": 45}, "forbidden": [], "plants": [],
                            "current_research": {"name": "none"}, "construction_projects": []},
        }
        state = {"anchor": {"x": 10, "z": 10}, "issued": {}}
        choices, details = director.candidate_actions(None, snapshot, state)
        self.assertNotIn("build_basic_beds", choices)
        snapshot["development"]["rooms"] = [{
            "contained_beds_ids": [],
            "cells": [{"x": x, "z": z} for x in range(10, 14) for z in range(10, 14)],
            "open_roof_count": 0, "touches_map_edge": False,
        }]
        choices, details = director.candidate_actions(None, snapshot, state)
        self.assertIn("build_basic_beds", choices)
        self.assertEqual(details["basic_bed_count"], 1)
        snapshot["development"]["construction_projects"] = [{"def_name": "Bed", "thing_id": 44,
                                                                  "position": {"x": 11, "z": 11}}]
        choices, _ = director.candidate_actions(None, snapshot, state)
        self.assertNotIn("build_basic_beds", choices)
        snapshot["development"]["construction_projects"] = []
        snapshot["development"]["item_counts"] = {"Steel": 45}
        choices, details = director.candidate_actions(None, snapshot, state)
        self.assertIn("build_basic_beds", choices)
        self.assertEqual(list(details["basic_bed_materials"]), ["Steel"])

    def test_outdoor_bed_does_not_block_roofed_bed_upgrade(self):
        indoor_cells = [{"x": x, "z": z} for x in range(10, 14) for z in range(10, 14)]
        snapshot = {
            "game": {"tick": 7000}, "map": {"id": 1, "resources": {"food": 30}},
            "colonists": [{"id": 1, "name": "Builder", "health": 1,
                           "skills": {"Construction": {"level": 8}},
                           "work_priorities": {"Construction": {"priority": 3}},
                           "position": {"x": 10, "z": 10}}],
            "animals": [], "wild_animals": [], "combat": {},
            "development": {"buildings": [
                {"id": 10, "def": "SleepingSpot", "position": {"x": 10, "z": 10}},
                {"id": 20, "def": "Bed", "position": {"x": 20, "z": 20}},
            ], "rooms": [{"contained_beds_ids": [10], "cells": indoor_cells,
                          "open_roof_count": 0, "touches_map_edge": False}],
                "building_counts": {"Bed": 1, "SleepingSpot": 1},
                "zones": [], "item_counts": {"Steel": 90}, "forbidden": [],
                "plants": [], "construction_projects": [],
                "current_research": {"name": "none"}},
        }
        actions, details = director.candidate_actions(None, snapshot,
                                                       {"anchor": {"x": 11, "z": 11}, "issued": {}})
        self.assertIn("build_basic_beds", actions)
        self.assertIn("indoor_bed_site", details)
        self.assertIn(details["indoor_bed_site"], indoor_cells)

    def test_unplaced_bed_order_retries_and_uses_clear_two_cell_site(self):
        terrain = {"width": 30, "height": 30, "palette": ["Soil"], "grid": [900, 0]}
        development = {"buildings": [{"position": {"x": 11, "z": 20}, "size": {"x": 1, "z": 2}}],
                       "construction_projects": [], "things": []}
        site = director.open_bed_site(terrain, {"x": 10, "z": 10}, development)
        self.assertIsNotNone(site)
        self.assertNotEqual(site, {"x": 11, "z": 20})
        self.assertNotIn((11, 20), {(site["x"], site["z"]), (site["x"], site["z"] + 1)})
        snapshot = {"game": {"tick": 7000}, "map": {"id": 1, "resources": {"food": 30}},
                    "colonists": [{"id": 1, "name": "Builder", "health": 1,
                                   "skills": {"Construction": {"level": 5}}, "hunger": 0.8,
                                   "work_priorities": {"Construction": {"priority": 3}},
                                   "position": {"x": 10, "z": 10}}],
                    "animals": [], "wild_animals": [], "combat": {},
                    "development": {**development, "building_counts": {"SleepingSpot": 1},
                                    "rooms": [{"contained_beds_ids": [],
                                        "cells": [{"x": x, "z": z} for x in range(10, 14) for z in range(10, 14)],
                                        "open_roof_count": 0, "touches_map_edge": False}],
                                    "zones": [], "item_counts": {"WoodLog": 45},
                                    "forbidden": [], "plants": [],
                                    "current_research": {"name": "none"}}}
        choices, _ = director.candidate_actions(None, snapshot,
                                                {"anchor": {"x": 10, "z": 10},
                                                 "issued": {"basic_beds": 1000}})
        self.assertIn("build_basic_beds", choices)

    def test_bed_blueprint_noop_is_reported_and_next_site_is_tried(self):
        terrain = {"width": 30, "height": 30, "palette": ["Soil"], "grid": [900, 0]}
        snapshot = {"game": {"tick": 7000}, "map": {"id": 1},
                    "colonists": [{"id": 1}],
                    "development": {"buildings": [], "construction_projects": [], "things": [],
                                    "rooms": [{"contained_beds_ids": [],
                                        "cells": [{"x": x, "z": z} for x in range(10, 14) for z in range(10, 14)],
                                        "open_roof_count": 0, "touches_map_edge": False}]}}
        state = {"anchor": {"x": 10, "z": 10}, "issued": {}}
        client = mock.Mock()
        client.post.return_value = {"success": True}
        client.get.side_effect = [{"projects": []}, [], {"projects": []}, []]
        first = director.execute_action(client, snapshot, state, "build_basic_beds",
                                        {"basic_bed_materials": {"Steel": "500 available"},
                                         "bed_material": "Steel"})
        second = director.execute_action(client, snapshot, state, "build_basic_beds",
                                         {"basic_bed_materials": {"Steel": "500 available"},
                                          "bed_material": "Steel"})
        self.assertFalse(first["applied"])
        self.assertFalse(second["applied"])
        self.assertNotEqual(first["site"], second["site"])
        self.assertEqual(len(state["failed_bed_sites"]), 2)

    def test_dangerous_hunt_requires_separate_model_commitment(self):
        rhino = {"id": 9, "def": "Rhinoceros", "combat_power": 270,
                 "harm_revenge_chance": 0.5, "meat_amount": 420}
        snapshot = {"game": {"tick": 1000}, "map": {"id": 1, "resources": {"food": 39}},
                    "colonists": [{"id": 1}], "development": {
                        "risky_hunt_options": [rhino], "fighter_context": {"healthy_ranged": 1, "food": 39},
                        "building_counts": {}, "zones": [],
                    }}
        agent = self.FakeAgent(["consider_dangerous_hunt", "defer"])
        decision = director.choose_action(agent, snapshot, ["consider_dangerous_hunt", "hold_survival"])
        self.assertEqual(decision["risky_hunt_target"], 9)
        self.assertEqual(decision["dangerous_hunt_decision"], "defer")
        self.assertEqual(len(agent.calls), 2)
        self.assertEqual(set(agent.calls[-1]), {"dangerous_hunt_decision"})
        state = {"anchor": {"x": 20, "z": 20}, "issued": {}}
        client = mock.Mock()
        result = director.execute_action(client, snapshot, state, "consider_dangerous_hunt",
                                         {"risky_hunt_options": [rhino], **decision})
        self.assertFalse(result["applied"])
        client.post.assert_not_called()

    def test_rejected_wild_harvest_does_not_ask_which_plant(self):
        agent = self.FakeAgent(["hold_survival"])
        snapshot = {"colonists": [], "game": {}, "map": {"resources": {}}, "development": {
            "wild_plant_options": {"Plant_Ambrosia": {"label": "ambrosia", "count": 4, "expected_yield": 16, "harvested_thing": "Ambrosia"}},
            "building_counts": {}, "zones": [],
        }}
        director.choose_action(agent, snapshot, ["harvest_local_plants", "hold_survival"])
        self.assertEqual(len(agent.calls), 1)

    def test_starter_blueprint_is_a_compact_floored_shared_house(self):
        layout = director.starter_base_blueprint(3)
        defs = [row["def_name"] for row in layout["buildings"]]
        self.assertEqual(defs.count("Bed"), 3)
        self.assertIn("Door", defs)
        self.assertNotIn("FueledStove", defs)
        self.assertNotIn("SimpleResearchBench", defs)
        self.assertEqual(len(layout["floors"]), 25)
        self.assertEqual((layout["width"], layout["height"]), (7, 7))

    def test_emergency_sleeping_spots_do_not_consume_materials(self):
        layout = director.sleeping_spots_blueprint(3)
        self.assertEqual(
            [row["def_name"] for row in layout["buildings"]],
            ["SleepingSpot", "SleepingSpot", "SleepingSpot", "SleepingSpot"],
        )
        self.assertTrue(all("stuff_def_name" not in row for row in layout["buildings"]))

    def test_low_joy_offers_a_model_chosen_recreation_schedule(self):
        snapshot = {
            "game": {"tick": 1000}, "map": {"id": 1, "resources": {"food": 30, "meals": 10}},
            "colonists": [{"id": 7, "name": "Ari", "mood": 0.25, "joy": 0.18,
                           "health": 1.0, "hunger": 0.8, "rest": 0.8}],
            "animals": [], "wild_animals": [], "combat": {"colonists": [], "available_weapons": []},
            "development": {"building_counts": {}, "zones": [], "current_research": {"name": "none"},
                            "item_counts": {}, "work_tables": [], "forbidden": [], "plants": [], "things": []},
        }
        state = {"anchor": {"x": 10, "z": 10}, "issued": {}}
        candidates, details = director.candidate_actions(None, snapshot, state)
        self.assertIn("schedule_recreation", candidates)
        self.assertEqual(set(details["recreation_schedule_options"]), {"7"})
        agent = self.FakeAgent(["schedule_recreation", "midday"])
        decision = director.choose_action(agent, snapshot, ["schedule_recreation", "hold_survival"])
        self.assertEqual(decision["recreation_pawn"], 7)
        self.assertEqual(decision["recreation_slot"], "midday")
        self.assertEqual(len(agent.calls), 2)
        client = mock.Mock()
        client.post.return_value = {"success": True}
        result = director.execute_action(client, snapshot, state, "schedule_recreation", {**details, **decision})
        self.assertEqual(result["hours"], [12, 13])
        self.assertEqual(state["recreation_schedules"], [7])
        self.assertEqual(client.post.call_count, 2)

    def test_recreation_pin_uses_dry_unoccupied_site_and_not_pending_duplicate(self):
        terrain = {"width": 30, "height": 30, "palette": ["Soil"], "grid": [900, 0]}
        development = {"buildings": [{"position": {"x": 18, "z": 18}, "size": {"x": 1, "z": 1}}],
                       "construction_projects": [], "things": []}
        site = director.open_recreation_site(terrain, {"x": 10, "z": 10}, development)
        self.assertIsNotNone(site)
        self.assertNotEqual(site, {"x": 18, "z": 18})
        snapshot = {
            "game": {"tick": 1000}, "map": {"id": 1, "resources": {"food": 30, "meals": 10}},
            "colonists": [{"id": 1, "name": "Builder", "health": 1,
                           "work_priorities": {"Construction": {"priority": 3}}}],
            "animals": [], "wild_animals": [],
            "combat": {"colonists": [], "available_weapons": []},
            "development": {**development, "building_counts": {}, "zones": [], "current_research": {"name": "none"},
                            "item_counts": {"WoodLog": 15}, "work_tables": [], "forbidden": [], "plants": []},
        }
        state = {"anchor": {"x": 10, "z": 10}, "issued": {}}
        candidates, _ = director.candidate_actions(None, snapshot, state)
        self.assertIn("build_recreation_pin", candidates)
        snapshot["development"]["construction_projects"] = [{"def_name": "HorseshoesPin"}]
        candidates, _ = director.candidate_actions(None, snapshot, state)
        self.assertNotIn("build_recreation_pin", candidates)

    def test_animal_sleeping_spots_are_free_markers(self):
        layout = director.animal_spots_blueprint(2)
        self.assertEqual(
            [row["def_name"] for row in layout["buildings"]],
            ["AnimalSleepingSpot", "AnimalSleepingSpot"],
        )
        self.assertTrue(all("stuff_def_name" not in row for row in layout["buildings"]))

    def test_cemetery_contains_spaced_real_graves(self):
        layout = director.cemetery_blueprint(8)
        self.assertEqual(len(layout["buildings"]), 8)
        self.assertTrue(all(row["def_name"] == "Grave" for row in layout["buildings"]))
        self.assertEqual(len({(row["rel_x"], row["rel_z"]) for row in layout["buildings"]}), 8)

    def test_prison_is_enclosed_and_uses_normal_sleeping_spots(self):
        layout = director.prison_blueprint()
        defs = [row["def_name"] for row in layout["buildings"]]
        self.assertEqual(defs.count("SleepingSpot"), 2)
        self.assertEqual(defs.count("Door"), 1)
        self.assertGreaterEqual(defs.count("Wall"), 20)

    def test_room_floor_blueprint_uses_only_real_room_cells(self):
        layout, origin = director.room_floor_blueprint(
            [{"x": 10, "z": 20}, {"x": 11, "z": 20}, {"x": 10, "z": 21}],
            "Concrete",
        )
        self.assertEqual(origin, {"x": 10, "z": 20})
        self.assertEqual(len(layout["floors"]), 3)
        self.assertTrue(all(row["def_name"] == "Concrete" for row in layout["floors"]))

    def test_sterile_floor_requires_large_reserves_and_skill(self):
        scarce = director.affordable_floor_options(
            {"Steel": 100, "Silver": 200}, {"SterileMaterials"}, 20, 6
        )
        rich = director.affordable_floor_options(
            {"Steel": 1000, "Silver": 2000}, {"SterileMaterials", "Smithing"}, 20, 6
        )
        self.assertNotIn("SterileTile", scarce)
        self.assertIn("SterileTile", rich)

    def test_outdoor_paths_never_offer_steel_floors(self):
        options = director.affordable_floor_options(
            {"Steel": 5000, "BlocksGranite": 1000}, {"Stonecutting", "Smithing"}, 60, 12, pathway=True
        )
        self.assertNotIn("Concrete", options)
        self.assertNotIn("MetalTile", options)
        self.assertIn("FlagstoneGranite", options)

    def test_freezer_can_reuse_existing_generator(self):
        layout = director.freezer_blueprint(include_generator=False)
        defs = [row["def_name"] for row in layout["buildings"]]
        self.assertIn("Cooler", defs)
        self.assertNotIn("WoodFiredGenerator", defs)

    def test_freezer_is_not_offered_without_components(self):
        missing = director.freezer_resource_plan(
            {}, {"Steel": 500, "WoodLog": 500, "ComponentIndustrial": 2}, 8, {"Electricity"}
        )
        powered = director.freezer_resource_plan(
            {"SolarGenerator": 1}, {"Steel": 500, "WoodLog": 500, "ComponentIndustrial": 3}, 8, {"Electricity"}
        )
        self.assertIsNone(missing)
        self.assertFalse(powered["include_generator"])

    def test_basic_beds_are_real_beds(self):
        layout = director.basic_beds_blueprint(2)
        self.assertEqual([row["def_name"] for row in layout["buildings"]], ["Bed", "Bed"])

    def test_temple_is_floored_and_has_no_beds_or_worktables(self):
        layout = director.temple_blueprint("Altar_Small", "BlocksGranite")
        defs = [row["def_name"] for row in layout["buildings"]]
        self.assertIn("Altar_Small", defs)
        self.assertEqual(len(layout["floors"]), 49)
        self.assertTrue(all(row["def_name"] == "TileGranite" for row in layout["floors"]))
        self.assertFalse(any(name in {"Bed", "SleepingSpot", "FueledStove", "SimpleResearchBench"} for name in defs))

    def test_killbox_keeps_an_open_entrance_and_uses_traps(self):
        layout = director.killbox_blueprint()
        defs = [row["def_name"] for row in layout["buildings"]]
        self.assertIn("TrapSpike", defs)
        self.assertIn("Barricade", defs)
        self.assertFalse(any(row["def_name"] == "Wall" and row["rel_x"] == 4 and row["rel_z"] == 0 for row in layout["buildings"]))

    def test_structure_materials_exclude_scarce_wood_and_offer_fireproof_stone(self):
        scarce = director.structure_material_options({"WoodLog": 180, "BlocksGranite": 160})
        stocked = director.structure_material_options({"WoodLog": 500, "BlocksGranite": 400})
        self.assertNotIn("WoodLog", scarce)
        self.assertNotIn("BlocksGranite", scarce)
        self.assertIn("WoodLog", stocked)
        self.assertIn("BlocksGranite", stocked)
        self.assertIn("fireproof", stocked["BlocksGranite"])

    def test_private_bedroom_is_enclosed_and_uses_selected_material(self):
        layout = director.private_bedroom_blueprint("BlocksGranite", powered=True, complex_furniture=True)
        walls = [row for row in layout["buildings"] if row["def_name"] == "Wall"]
        self.assertEqual(len(walls), 23)
        self.assertTrue(all(row["stuff_def_name"] == "BlocksGranite" for row in walls))
        self.assertIn("Bed", [row["def_name"] for row in layout["buildings"]])
        self.assertIn("Dresser", [row["def_name"] for row in layout["buildings"]])

    def test_animal_barn_can_use_straw_and_sleeping_spots(self):
        layout = director.animal_barn_blueprint("BlocksLimestone", 3, straw_floor=True, powered=True, climate="cold")
        defs = [row["def_name"] for row in layout["buildings"]]
        self.assertIn("AnimalFlap", defs)
        self.assertGreaterEqual(defs.count("AnimalSleepingSpot"), 3)
        self.assertIn("Heater", defs)
        self.assertTrue(layout["floors"])
        self.assertTrue(all(row["def_name"] == "StrawMatting" for row in layout["floors"]))

    def test_mountain_bedroom_requires_full_verified_rock_block(self):
        cells = [z * 20 + x for z in range(4, 11) for x in range(5, 12)]
        rect = director.mining_bedroom_rect({
            "map_width": 20,
            "ores": {"MineableGranite": {"cells": cells}},
        }, {"x": 8, "z": 8})
        self.assertEqual(rect, ({"x": 5, "y": 0, "z": 4}, {"x": 11, "y": 0, "z": 10}))

    def test_architect_generates_twenty_four_distinct_lit_houses(self):
        candidates = director.architect.generate_house_candidates(
            "BlocksGranite",
            [],
            {"Stonecutting", "Electricity", "ComplexFurniture"},
            {"BlocksGranite": 5000, "WoodLog": 2000},
            powered=True,
            climate="temperate",
            seed=91,
        )
        self.assertEqual(len(candidates), 24)
        signatures = {
            (row["style"], row["width"], row["height"], row["summary"])
            for row in candidates.values()
        }
        self.assertEqual(len(signatures), 24)
        for row in candidates.values():
            defs = [item["def_name"] for item in row["layout"]["buildings"]]
            self.assertIn("Door", defs)
            self.assertIn("StandingLamp", defs)
            self.assertTrue("Bed" in defs or "DoubleBed" in defs)

    def test_house_generation_is_deterministic_for_saved_seed(self):
        args = ("WoodLog", [], {"Electricity"}, {"WoodLog": 4000})
        first = director.architect.generate_house_candidates(*args, powered=True, climate="cold", seed=7)
        second = director.architect.generate_house_candidates(*args, powered=True, climate="cold", seed=7)
        self.assertEqual(first, second)

    def test_house_entrance_is_laya_chosen_but_door_offset_varies_by_seed(self):
        context = {"material": "BlocksGranite", "entry_side": "west", "building_catalog": [],
                   "finished_research": [], "item_counts": {"BlocksGranite": 2000, "WoodLog": 1000},
                   "powered": False, "climate": "temperate"}
        door_positions = set()
        for seed in range(8):
            variants = director.architect.generate_program_variants("residence", context, seed=seed)
            layout = variants["house_compact_1"]["layout"]
            door = next(row for row in layout["buildings"] if row["def_name"] == "Door")
            self.assertEqual(door["rel_x"], 0)
            self.assertTrue(all(row["stuff_def_name"] == "BlocksGranite"
                                for row in layout["buildings"] if row["def_name"] == "Wall"))
            door_positions.add((door["rel_x"], door["rel_z"]))
            self.assertEqual(variants, director.architect.generate_program_variants("residence", context, seed=seed))
        self.assertGreater(len(door_positions), 1)

    def test_architecture_materials_exclude_unfinishable_wall_plans(self):
        context = {"building_catalog": [], "finished_research": [], "item_counts": {"WoodLog": 205},
                   "material": "WoodLog", "powered": False, "climate": "temperate"}
        options = director.architect.affordable_material_options("residence", context,
                                                                   {"WoodLog": "205 wood"}, seed=1)
        self.assertEqual(options, {})
        context["item_counts"]["WoodLog"] = 1000
        options = director.architect.affordable_material_options("residence", context,
                                                                   {"WoodLog": "1000 wood"}, seed=1)
        self.assertIn("WoodLog", options)

    def test_generated_architecture_has_no_overlapping_anchors(self):
        base = {"building_catalog": [], "finished_research": ["Electricity"],
                "item_counts": {"WoodLog": 9000, "Steel": 5000},
                "material": "WoodLog", "powered": True, "climate": "cold"}
        for program in director.architect.PROGRAM_CATALOG:
            for entry_side in ("north", "east", "south", "west"):
                for seed in range(4):
                    variants = director.architect.generate_program_variants(
                        program, {**base, "entry_side": entry_side}, seed=seed)
                    self.assertTrue(variants)
                    for key, variant in variants.items():
                        with self.subTest(program=program, side=entry_side, seed=seed, variant=key):
                            self.assertEqual(director.architect.layout_anchor_conflicts(
                                variant["layout"]), [])

    def test_freezer_cooler_does_not_replace_selected_east_entrance(self):
        context = {"building_catalog": [], "finished_research": [],
                   "item_counts": {"WoodLog": 9000}, "material": "WoodLog",
                   "entry_side": "east", "powered": False, "climate": "temperate"}
        for seed in range(8):
            layout = director.architect.generate_program_variants("freezer", context, seed=seed)["freezer_1"]["layout"]
            door = next(item for item in layout["buildings"] if item["def_name"] == "Door")
            cooler = next(item for item in layout["buildings"] if item["def_name"] == "Cooler")
            self.assertEqual(door["rel_x"], layout["width"] - 1)
            self.assertNotEqual((door["rel_x"], door["rel_z"]),
                                (cooler["rel_x"], cooler["rel_z"]))

    def test_freezer_plan_needs_unlocked_cooler_and_components(self):
        context = {"building_catalog": [{"def_name": "Cooler", "available_now": False,
                                         "cost_list": [{"thing_def": "Steel", "count": 90},
                                                       {"thing_def": "ComponentIndustrial", "count": 3}]}],
                   "finished_research": [],
                   "item_counts": {"WoodLog": 2000, "Steel": 500, "ComponentIndustrial": 2},
                   "material": "WoodLog", "powered": True, "climate": "temperate"}
        self.assertEqual(director.architect.generate_program_variants("freezer", context), {})
        context["building_catalog"][0]["available_now"] = True
        variants = director.architect.generate_program_variants("freezer", context)
        self.assertEqual(director.architect.affordable_variants(variants, context), {})
        context["item_counts"]["ComponentIndustrial"] = 4
        feasible = director.architect.affordable_variants(variants, context)
        self.assertTrue(feasible)
        self.assertEqual(feasible["freezer_1"]["estimated_stuff_cost"]["ComponentIndustrial"], 3)

    def test_architecture_cost_includes_known_floor_materials(self):
        layout = director.architect.blueprint(
            [director.architect.building("Wall", 0, 0, stuff="BlocksGranite")], 2, 2,
            [director.architect.floor("TileGranite", 1, 1)])
        self.assertEqual(director.architect.estimated_stuff_cost(layout, []), {"BlocksGranite": 9})

    def test_stone_throne_room_uses_compatible_fabric_drapes(self):
        context = {"building_catalog": [{"def_name": "Drape", "available_now": True,
                                         "cost_stuff_count": 20, "stuff_categories": ["Fabric"]}],
                   "finished_research": [], "item_counts": {"BlocksGranite": 9000, "Cloth": 1000},
                   "material": "BlocksGranite", "powered": False}
        layout = director.architect.generate_program_variants("throne_room", context)["throne_room_1"]["layout"]
        drapes = [item for item in layout["buildings"] if item["def_name"] == "Drape"]
        self.assertTrue(drapes)
        self.assertTrue(all(item["stuff_def_name"] == "Cloth" for item in drapes))
        context["item_counts"].pop("Cloth")
        context["item_counts"]["ComponentIndustrial"] = 10000
        self.assertEqual(director.architect.generate_program_variants("throne_room", context), {})

    def test_selected_wall_material_is_not_silently_replaced(self):
        context = {"building_catalog": [{"def_name": "Wall", "available_now": True,
                                         "cost_stuff_count": 5, "stuff_categories": ["Woody", "Stony"]}],
                   "finished_research": [], "item_counts": {"WoodLog": 2000},
                   "material": "BlocksGranite", "powered": False}
        self.assertEqual(director.architect.generate_program_variants("residence", context), {})

    def test_hospital_variant_upgrades_beds_monitor_floor_and_light(self):
        catalog = [
            {"def_name": name, "available_now": True}
            for name in ("HospitalBed", "VitalsMonitor", "StandingLamp", "Shelf", "Wall", "Door")
        ]
        variants = director.architect.generate_program_variants("hospital", {
            "building_catalog": catalog,
            "finished_research": ["Electricity", "SterileMaterials"],
            "item_counts": {"Silver": 10000, "Steel": 5000},
            "material": "BlocksGranite",
            "powered": True,
            "climate": "temperate",
        })
        expanded = variants["hospital_3"]["layout"]
        defs = [row["def_name"] for row in expanded["buildings"]]
        self.assertGreaterEqual(defs.count("HospitalBed"), 4)
        self.assertIn("VitalsMonitor", defs)
        self.assertIn("StandingLamp", defs)
        self.assertTrue(expanded["floors"])
        self.assertTrue(all(row["def_name"] == "SterileTile" for row in expanded["floors"]))

    def test_throne_room_never_contains_beds_or_workbenches(self):
        catalog = [
            {"def_name": name, "available_now": True}
            for name in ("Throne", "GrandThrone", "Brazier", "Column", "Drape", "StandingLamp")
        ]
        layout = director.architect.generate_program_variants("throne_room", {
            "building_catalog": catalog,
            "finished_research": ["Electricity", "Stonecutting"],
            "item_counts": {"BlocksGranite": 10000},
            "material": "BlocksGranite",
            "powered": True,
            "royalty": {"colonists": [{"title_def_name": "Count"}]},
        })["throne_room_2"]["layout"]
        defs = {row["def_name"] for row in layout["buildings"]}
        self.assertIn("GrandThrone", defs)
        self.assertFalse(defs & {"Bed", "HospitalBed", "SimpleResearchBench", "FueledStove"})

    def test_profession_direction_uses_large_passion_not_level_alone(self):
        colonists = [
            {"id": 1, "name": "Veteran", "health": 1, "skills": {"Crafting": {"level": 9, "passion": 0}}},
            {"id": 2, "name": "Apprentice", "health": 1, "skills": {"Crafting": {"level": 5, "passion": 2}}},
        ]
        work = [{"def_name": "Crafting", "label": "Craft", "relevant_skills": ["Crafting"]}]
        context = director.professions.profession_context(colonists, work)
        craft_people = context["directions"]["craft_industry"]["people"]
        self.assertEqual(craft_people[0]["pawn"], "Apprentice")
        self.assertEqual(context["skills"]["Crafting"]["learning_percent"], 150)

    def test_training_plan_maps_skill_to_live_modded_work_type(self):
        colonists = [{
            "id": 3, "name": "Learner", "health": 1, "downed": False,
            "skills": {"Crafting": {"level": 4, "passion": 2, "disabled": False}},
            "work_priorities": {"ModdedFabrication": {"disabled": False}}, "traits": [], "capacities": {},
        }]
        work = [{"def_name": "ModdedFabrication", "relevant_skills": ["Crafting"], "natural_priority": 10}]
        options = director.professions.training_options(colonists, work)
        self.assertEqual(next(iter(options.values()))["work_type"], "ModdedFabrication")
        self.assertEqual(next(iter(options.values()))["xp_percent"], 150)

    def test_night_owl_schedule_sleeps_in_daytime_window(self):
        schedule = director.professions.night_owl_schedule()
        self.assertTrue(all(schedule[hour] == "Sleep" for hour in range(11, 19)))
        self.assertTrue(all(schedule[hour] == "Anything" for hour in list(range(0, 11)) + list(range(19, 24))))

    def test_workbench_upgrade_waits_for_research_and_costs(self):
        base = {
            "building_counts": {"FueledStove": 1},
            "item_counts": {"Steel": 200, "ComponentIndustrial": 5},
            "building_catalog": [{
                "def_name": "ElectricStove", "available_now": False,
                "cost_list": [{"thing_def": "Steel", "count": 80}, {"thing_def": "ComponentIndustrial", "count": 2}],
            }],
        }
        self.assertNotIn("FueledStove|ElectricStove", director.architect.workbench_upgrade_options(base))
        base["building_catalog"][0]["available_now"] = True
        self.assertIn("FueledStove|ElectricStove", director.architect.workbench_upgrade_options(base))

    def test_rejected_architecture_does_not_ask_program_or_layout(self):
        agent = self.FakeAgent(["hold_survival"])
        snapshot = {"colonists": [], "game": {}, "map": {"resources": {}}, "development": {
            "building_counts": {}, "zones": [],
            "architecture_program_options": {"residence": "housing shortage"},
            "architecture_context": {},
        }}
        result = director.choose_action(agent, snapshot, ["plan_architecture", "hold_survival"])
        self.assertEqual(result["choice"], "hold_survival")
        self.assertEqual(len(agent.calls), 1)

    def test_selected_residence_uses_program_style_variant_hierarchy(self):
        agent = self.FakeAgent(["plan_architecture", "south", "compact", "house_compact_1"])
        snapshot = {"colonists": [], "game": {}, "map": {"resources": {}}, "development": {
            "building_counts": {}, "zones": [],
            "architecture_program_options": {"residence": "housing shortage"},
            "architecture_context": {
                "building_catalog": [], "finished_research": [], "item_counts": {"WoodLog": 2000},
                "material": "WoodLog", "powered": False, "climate": "temperate", "variant_seed": 1,
            },
        }}
        result = director.choose_action(agent, snapshot, ["plan_architecture", "hold_survival"])
        self.assertEqual(result["architecture_program"], "residence")
        self.assertEqual(result["architecture_material"], "WoodLog")
        self.assertEqual(result["architecture_entry"], "south")
        self.assertEqual(result["architecture_house_style"], "compact")
        self.assertEqual(result["architecture_variant"], "house_compact_1")
        self.assertEqual(len(agent.calls), 4)

    def test_laya_selects_wall_material_before_layout(self):
        agent = self.FakeAgent(["plan_architecture", "BlocksGranite", "west",
                                "compact", "house_compact_1"])
        context = {"building_catalog": [], "finished_research": [],
                   "item_counts": {"WoodLog": 2000, "BlocksGranite": 2000},
                   "material_options": {"WoodLog": "wood", "BlocksGranite": "fireproof stone"},
                   "material": "WoodLog", "powered": False, "climate": "temperate", "variant_seed": 5}
        snapshot = {"colonists": [], "game": {}, "map": {"resources": {}}, "development": {
            "building_counts": {}, "zones": [], "architecture_program_options": {"residence": "need homes"},
            "architecture_context": context}}
        result = director.choose_action(agent, snapshot, ["plan_architecture", "hold_survival"])
        self.assertEqual(result["architecture_material"], "BlocksGranite")
        self.assertEqual(result["architecture_entry"], "west")
        self.assertEqual(len(agent.calls), 5)

    def test_architecture_execution_uses_layas_saved_design(self):
        context = {"building_catalog": [], "finished_research": [],
                   "item_counts": {"WoodLog": 2000, "BlocksGranite": 2000},
                   "material_options": {"WoodLog": "wood", "BlocksGranite": "stone"},
                   "material": "WoodLog", "powered": False, "climate": "temperate", "variant_seed": 5}
        agent = self.FakeAgent(["plan_architecture", "BlocksGranite", "west",
                                "compact", "house_compact_1"])
        snapshot = {"colonists": [], "game": {"tick": 500}, "map": {"id": 1, "resources": {}},
                    "development": {"building_counts": {}, "zones": [],
                                    "architecture_program_options": {"residence": "need homes"},
                                    "architecture_context": context}}
        decision = director.choose_action(agent, snapshot, ["plan_architecture", "hold_survival"])

        class Client:
            def __init__(self):
                self.posts = []

            def get(self, endpoint, **kwargs):
                return {}

            def post(self, endpoint, **kwargs):
                self.posts.append((endpoint, kwargs))
                return {"success": True}

        client = Client()
        with mock.patch.object(director, "find_terrain_rect", return_value={"x": 40, "z": 20}), \
             mock.patch.object(director, "prioritize", return_value={"applied": True}):
            result = director.execute_action(client, snapshot, {"issued": {}, "anchor": {"x": 10, "z": 10}},
                                             "plan_architecture", {**decision, "architecture_context": context})
        self.assertTrue(result["applied"])
        self.assertEqual(result["project"]["material"], "BlocksGranite")
        self.assertEqual(result["project"]["entry"], "west")
        endpoint, request = client.posts[0]
        self.assertEqual(endpoint, "/api/v1/builder/blueprint")
        buildings = request["body"]["blueprint"]["buildings"]
        self.assertTrue(all(item["stuff_def_name"] == "BlocksGranite"
                            for item in buildings if item["def_name"] == "Wall"))
        self.assertEqual(next(item for item in buildings if item["def_name"] == "Door")["rel_x"], 0)

    def test_architecture_execution_refuses_stale_material(self):
        context = {"building_catalog": [], "finished_research": [],
                   "item_counts": {"WoodLog": 2000}, "material_options": {"WoodLog": "wood"},
                   "material": "WoodLog", "powered": False, "variant_seed": 2}
        result = director.execute_action(None, {"map": {"id": 1}, "game": {"tick": 1}},
                                         {"anchor": {"x": 5, "z": 5}, "issued": {}}, "plan_architecture",
                                         {"architecture_program": "residence", "architecture_variant": "house_compact_1",
                                          "architecture_material": "BlocksGranite", "architecture_entry": "south",
                                          "architecture_context": context})
        self.assertFalse(result["applied"])

    def test_architecture_site_reserves_existing_rooms_and_door_clearance(self):
        terrain = {"width": 40, "height": 40, "palette": ["Soil"], "grid": [1600, 0]}
        state = {"architecture_projects": [{"origin": {"x": 15, "z": 15},
                                              "width": 9, "height": 7}]}
        development = {"buildings": [{"def": "Door", "position": {"x": 19, "z": 15}}],
                       "construction_projects": [{"def_name": "Wall", "position": {"x": 24, "z": 18}}]}
        occupied = director.architecture_occupied_cells(development, state)
        self.assertIn((19, 16), occupied)
        site = director.find_terrain_rect(terrain, {"x": 17, "z": 16}, 7, 7,
                                          {"Soil"}, radius=20, blocked=occupied, clearance=1)
        self.assertIsNotNone(site)
        self.assertTrue(all((x, z) not in occupied
                            for x in range(site["x"] - 1, site["x"] + 8)
                            for z in range(site["z"] - 1, site["z"] + 8)))
        self.assertIsNone(director.find_terrain_rect(terrain, {"x": 17, "z": 16},
                                                       7, 7, {"Soil"}, blocked={
                                                           (x, z) for x in range(40) for z in range(40)}))

    def test_architecture_never_falls_back_to_blocked_desired_site(self):
        context = {"item_counts": {"WoodLog": 2000}, "material_options": {"WoodLog": "wood"},
                   "building_catalog": [], "finished_research": [], "variant_seed": 1}
        snapshot = {"game": {"tick": 100}, "map": {"id": 1}, "development": {}}
        client = mock.Mock()
        with mock.patch.object(director, "find_terrain_rect", return_value=None):
            result = director.execute_action(client, snapshot, {"anchor": {"x": 10, "z": 10}, "issued": {}},
                "plan_architecture", {"architecture_program": "residence",
                                      "architecture_variant": "house_compact_1",
                                      "architecture_material": "WoodLog", "architecture_entry": "south",
                                      "architecture_context": context})
        self.assertFalse(result["applied"])
        client.post.assert_not_called()

    def test_roaming_animal_requires_completed_pen_before_taming(self):
        animal = {"id": 9, "def": "Horse", "gender": "Female", "position": {"x": 16, "z": 10},
                  "can_tame": True, "minimum_handling_skill": 1,
                  "requires_pen": True, "has_suitable_enclosed_pen": False}
        snapshot = {"game": {"tick": 1000}, "map": {"id": 1, "resources": {"food": 30}},
                    "colonists": [{"id": 1, "name": "Handler", "health": 1.0,
                                   "position": {"x": 10, "z": 10},
                                   "skills": {"Animals": {"level": 8}},
                                   "work_priorities": {"Construction": {"priority": 2}}}],
                    "animals": [], "wild_animals": [animal], "combat": {},
                    "development": {"building_counts": {"Bed": 1}, "zones": [], "buildings": [
                        {"id": 7, "def": "Bed", "position": {"x": 10, "z": 10}}],
                        "rooms": [{"contained_beds_ids": [7], "open_roof_count": 0,
                                   "touches_map_edge": False}],
                        "item_counts": {"WoodLog": 140}, "things": [], "plants": [],
                        "work_tables": [], "forbidden": [], "current_research": {"name": "none"}}}
        state = {"anchor": {"x": 10, "z": 10}, "issued": {}}
        choices, _ = director.candidate_actions(None, snapshot, state)
        self.assertNotIn("start_taming", choices)
        self.assertIn("build_animal_pen", choices)
        animal["has_suitable_enclosed_pen"] = True
        choices, _ = director.candidate_actions(None, snapshot, state)
        self.assertIn("start_taming", choices)

    def test_pen_blueprint_has_closed_fence_gate_and_marker(self):
        plan = director.animal_pen_blueprint(9, "WoodLog")
        cells = {(row["rel_x"], row["rel_z"]): row["def_name"] for row in plan["buildings"]}
        self.assertEqual(cells[(4, 0)], "FenceGate")
        self.assertEqual(cells[(4, 4)], "PenMarker")
        self.assertTrue(all(cells[(x, 0)] in {"Fence", "FenceGate"} for x in range(9)))
        self.assertTrue(all(cells[(x, 8)] == "Fence" for x in range(9)))

    def test_trade_previews_hide_unaffordable_or_unaccepted_categories(self):
        class Client:
            def get(self, _endpoint, **params):
                if params["trader_id"] == "pawn:1":
                    return {"sale_options": [{"category": "leather", "example": "plainleather",
                                              "maximum_units": 3, "unit_price": 4}],
                            "purchase_options": []}
                return {"sale_options": [], "purchase_options": []}
        context = {"trade_opportunities": [{"id": "pawn:1"}, {"id": "pawn:2"}]}
        traders = director.preview_live_traders(Client(), context, 0, 300)
        self.assertEqual([row["id"] for row in traders], ["pawn:1"])
        self.assertEqual(set(director.verified_trade_options(traders[0]["preview"], "sale")), {"leather"})

    def test_unavailable_trade_is_recorded_without_fake_single_choice(self):
        snapshot = {"map": {"id": 0, "seed": "trade-qa", "tile_id": 4},
                    "game": {"tick": 1200}, "colonists": [{"id": 1}],
                    "development": {}}
        event = {"family": "trade", "signature": "trade:pawn:9", "urgency": 55}
        state = {"maps": {}}
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(director.bridge, "collect_snapshot", return_value=snapshot), \
                mock.patch.object(director, "collect_development", return_value=snapshot), \
                mock.patch.object(director.bridge, "safe_get", return_value={"trade_opportunities": []}), \
                mock.patch.object(director.events, "pending_events", return_value=[event]):
            record = director.run_event_cycle(mock.Mock(), self.FakeAgent([]), state,
                                              pathlib.Path(folder) / "state.json",
                                              pathlib.Path(folder) / "events.jsonl")
        self.assertEqual(record["decision"]["choice"], "trade_unavailable")
        self.assertFalse(record["result"]["applied"])
        self.assertEqual(next(iter(state["maps"].values()))["handled_events"][event["signature"]], 1200)

    def test_trade_model_context_keeps_food_prices_without_raw_stock_dump(self):
        trader = {"id": "pawn:9", "name": "Caravan", "stock": [{"label": "irrelevant"} for _ in range(90)],
                  "preview": {"colony_silver": 675, "minimum_silver_reserve": 300,
                              "trader_silver": 1000, "sale_options": [],
                              "purchase_options": [{"category": "food", "example": "pemmican",
                                                    "maximum_units": 50, "unit_price": 1.9}]}}
        snapshot = {"map": {"resources": {"food": 11, "meals": 10, "medicine": 2}},
                    "colonists": [{"hunger": 0.31} for _ in range(3)], "combat": {"hostiles": []}}
        context = colony_events.event_context_for_model(
            {"family": "trade", "name": "Caravan", "stock": trader["stock"]},
            {"trade_opportunities": [trader]}, snapshot)
        self.assertEqual(context["colony"]["food"], 11)
        self.assertIn("food pemmican x50 @ 1.9 silver", context["traders"][0]["can_buy"])
        self.assertNotIn("stock", context["event"])
        self.assertLess(len(json.dumps(context)), 700)

    def test_trade_population_context_counts_workers_not_only_heads(self):
        snapshot = {
            "map": {"resources": {"food": 45, "meals": 20}},
            "colonists": [
                {"name": "Shooter", "downed": False, "capacities": {"moving": 0.9}},
                {"name": "Builder", "downed": False, "capacities": {"moving": 0.6}},
                {"name": "Patient", "downed": True, "capacities": {"moving": 0.1}},
            ],
        }
        context = colony_growth.trade_population_context(snapshot)
        self.assertEqual((context["population"], context["able_workers"], context["bedbound"]),
                         (3, 2, 1))
        self.assertNotIn("routes", context)
        offer = {"name": "Applicant", "age": 24, "unit_price": 600,
                 "skills": ["Construction:9:Major"], "health_conditions": []}
        self.assertIn("Construction:9", colony_growth.brief_humanlike_offer_description(offer))

    def test_verified_trade_decision_executes_real_transaction(self):
        client = mock.Mock()
        client.post.return_value = {"executed": True, "bought_units": 20}
        preview = {"sale_options": [], "purchase_options": [
            {"category": "medicine", "example": "neutroamine", "maximum_units": 20, "unit_price": 8.2}]}
        result = director._execute_event_response(
            client, {"map": {"id": 0}, "game": {"tick": 100},
                     "colonists": [{"id": 1}, {"id": 2}, {"id": 3}]}, {},
            {"family": "trade"}, {"trade_opportunities": [{"id": "pawn:9", "preview": preview}]},
            "trade_now", {"trader_id": "pawn:9", "sale_category": "none",
                          "purchase_priority": "medicine", "trade_budget": 500})
        self.assertTrue(result["applied"])
        client.post.assert_called_once_with("/api/v1/trade/execute", body={
            "map_id": 0, "trader_id": "pawn:9", "sale_categories": [],
            "purchase_priorities": ["medicine"], "minimum_silver_reserve": 300,
            "maximum_spend": 500})

    def test_slaver_trade_can_sell_surplus_to_fund_specific_recruit(self):
        initial = {
            "colony_silver": 450, "minimum_silver_reserve": 300, "trader_silver": 1900,
            "sale_options": [{"category": "leather", "example": "plainleather",
                              "maximum_units": 75, "unit_price": 10}],
            "purchase_options": [], "humanlike_offers": [],
        }
        funded = {
            **initial, "planned_sale_value": 750,
            "purchase_options": [{"category": "slaves", "example": "Ada",
                                  "maximum_units": 1, "unit_price": 800}],
            "humanlike_offers": [{"pawn_id": 45, "name": "Ada", "unit_price": 800,
                                  "health": 0.97, "age": 29, "gender": "Female",
                                  "skills": ["Plants:8:Major", "Medicine:6:Minor"],
                                  "traits": [], "health_conditions": [], "disabled_work": []}],
        }
        class Client:
            def __init__(self):
                self.posts = []

            def get(self, endpoint, **params):
                self_outer.assertEqual(endpoint, "/api/v1/trade/preview")
                return funded if params.get("sale_category") == "leather" else initial

            def post(self, endpoint, **kwargs):
                self.posts.append((endpoint, kwargs))
                return {"executed": True}

        self_outer = self
        client = Client()
        snapshot = {"map": {"id": 9, "seed": "slaver-qa", "resources": {"food": 75, "meals": 15}},
                    "game": {"tick": 1200},
                    "colonists": [{"id": 1, "skills": {"Plants": {"level": 1}}},
                                  {"id": 2, "skills": {"Plants": {"level": 3}}}],
                    "combat": {}, "development": {"item_counts": {"Silver": 450}}}
        trader = {"id": "pawn:9", "name": "Slaver", "stock": [{"humanlike": True}],
                  "preview": initial}
        event = {"family": "trade", "signature": "trade:pawn:9", "urgency": 58}
        context = {"trade_opportunities": [trader]}
        agent = self.FakeAgent(["trade_now", "300", "slaves", "45", "1800"])
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(director.bridge, "collect_snapshot", return_value=snapshot), \
                mock.patch.object(director, "collect_development", return_value=snapshot), \
                mock.patch.object(director.bridge, "safe_get", return_value=context), \
                mock.patch.object(director.events, "pending_events", return_value=[event]), \
                mock.patch.object(director, "publish_event_overlay"):
            record = director.run_event_cycle(client, agent, {"maps": {}},
                                              pathlib.Path(folder) / "state.json",
                                              pathlib.Path(folder) / "events.jsonl")
        trade_posts = [kwargs["body"] for endpoint, kwargs in client.posts
                       if endpoint == "/api/v1/trade/execute"]
        self.assertEqual(len(trade_posts), 1)
        self.assertEqual(trade_posts[0]["sale_categories"], ["leather"])
        self.assertEqual(trade_posts[0]["purchase_priorities"], ["slaves"])
        self.assertEqual(trade_posts[0]["purchase_pawn_id"], 45)
        self.assertEqual(record["decision"]["purchase_pawn_id"], 45)
        self.assertTrue(record["result"]["applied"])

    def test_laya_can_spend_early_silver_on_real_slaver_offer(self):
        preview = {
            "colony_silver": 800, "minimum_silver_reserve": 0,
            "trader_silver": 1000, "sale_options": [],
            "purchase_options": [{"category": "slaves", "example": "Kees",
                                  "maximum_units": 1, "unit_price": 616}],
            "humanlike_offers": [{"pawn_id": 45, "name": "Kees", "unit_price": 616,
                                  "health": 1, "age": 30, "gender": "Female",
                                  "skills": [], "traits": [], "health_conditions": [],
                                  "disabled_work": []}],
        }
        client = mock.Mock()
        client.get.return_value = preview
        client.post.return_value = {"executed": True}
        snapshot = {
            "map": {"id": 9, "seed": "early-slaver", "resources": {"food": 65, "meals": 12}},
            "game": {"tick": 1200},
            "colonists": [{"id": 1}, {"id": 2}, {"id": 3, "downed": True}],
            "combat": {}, "development": {"item_counts": {"Silver": 800}},
        }
        event = {"family": "trade", "signature": "trade:pawn:9", "urgency": 58}
        context = {"trade_opportunities": [{"id": "pawn:9", "name": "Slaver",
                                            "stock": [{"humanlike": True}]}]}
        agent = self.FakeAgent(["trade_now", "0", "slaves", "45", "1800"])
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(director.bridge, "collect_snapshot", return_value=snapshot), \
                mock.patch.object(director, "collect_development", return_value=snapshot), \
                mock.patch.object(director.bridge, "safe_get", return_value=context), \
                mock.patch.object(director.events, "pending_events", return_value=[event]), \
                mock.patch.object(director, "publish_event_overlay"):
            record = director.run_event_cycle(client, agent, {"maps": {}},
                                              pathlib.Path(folder) / "state.json",
                                              pathlib.Path(folder) / "events.jsonl")
        body = next(kwargs["body"] for endpoint, kwargs in
                    ((call.args[0], call.kwargs) for call in client.post.call_args_list)
                    if endpoint == "/api/v1/trade/execute")
        self.assertEqual(body["minimum_silver_reserve"], 0)
        self.assertEqual(body["purchase_pawn_id"], 45)
        self.assertTrue(record["result"]["applied"])
        purchase_state = next(state for state, question in zip(agent.states, agent.calls)
                              if "purchase_priority" in question)
        self.assertEqual(purchase_state["growth"]["able_workers"], 2)
        self.assertEqual(purchase_state["growth"]["bedbound"], 1)

    def test_strategy_catalog_covers_core_and_every_official_expansion(self):
        expansions = {row.get("expansion") or "core" for row in colony_strategy.DIRECTIONS.values()}
        self.assertEqual(expansions, {"core", "royalty", "ideology", "biotech", "anomaly", "odyssey"})
        self.assertGreaterEqual(len(colony_strategy.DIRECTIONS), 30)
        self.assertEqual(set(colony_strategy.DOMAIN_LABELS), {row["domain"] for row in colony_strategy.DIRECTIONS.values()})

    def test_direction_audit_filters_inactive_content(self):
        core = colony_strategy.audit_directions({"active_mods": [{"package_id": "ludeon.rimworld"}]})
        self.assertIn("research_starflight", core["available"])
        self.assertIn("gravship_nomads", core["unavailable"])
        odyssey = colony_strategy.audit_directions({"active_mods": [
            {"package_id": "ludeon.rimworld"}, {"package_id": "ludeon.rimworld.odyssey"},
        ]})
        self.assertIn("gravship_nomads", odyssey["available"])

    def test_doctrine_is_a_conditional_cascade(self):
        choices = [
            "choose_colony_doctrine", "prosperity", "industrial_manufacturing",
            "compact", "manufacturing", "industrial", "industrial", "ranged_firepower", "pragmatic",
            "ship_escape", "peaceful_trade", "expansionist", "peaceful_trade", "balanced", "components",
        ]
        agent = self.FakeAgent(choices)
        context = {
            "material_options": {"WoodLog": "wood"}, "profession_choices": {},
            "active_mods": [{"package_id": "ludeon.rimworld"}], "research_tree": [],
            "building_catalog": [], "profession_directions": {},
        }
        context["direction_audit"] = colony_strategy.audit_directions(context)
        snapshot = {"colonists": [], "game": {}, "map": {"resources": {}}, "development": {
            "building_counts": {}, "zones": [], "doctrine_context": context,
        }}
        result = director.choose_action(agent, snapshot, ["choose_colony_doctrine", "hold_survival"])
        doctrine = result["doctrine_selection"]
        self.assertEqual(doctrine["primary_direction"], "industrial_manufacturing")
        self.assertEqual(doctrine["economy_family"], "manufacturing")
        self.assertEqual(doctrine["economy_product"], "components")
        self.assertNotIn("doctrine_mining_product", result["raw"]["answers"])
        direction_question = agent.calls[2]["doctrine_primary_direction"]["criteria"]
        self.assertTrue(direction_question)
        self.assertTrue(all(colony_strategy.DIRECTIONS[key]["domain"] == "prosperity" for key in direction_question))

    def test_doctrine_research_uses_only_live_startable_projects(self):
        doctrine = {"primary_direction": "industrial_manufacturing", "technology": "industrial", "economy_product": "components"}
        tree = [
            {"name": "Fabrication", "label": "Fabrication", "description": "Make advanced components", "can_start_now": True, "is_finished": False, "research_points": 4000},
            {"name": "BlockedMachining", "label": "Machining", "can_start_now": False, "is_finished": False, "research_points": 1000},
            {"name": "FinishedComponents", "label": "Components", "can_start_now": True, "is_finished": True, "research_points": 1000},
        ]
        options = colony_strategy.doctrine_research_candidates(doctrine, tree)
        self.assertIn("Fabrication", options)
        self.assertNotIn("BlockedMachining", options)
        self.assertNotIn("FinishedComponents", options)

    def test_architecture_includes_strategic_building_programs(self):
        options = director.architect.program_options({
            "building_counts": {"SimpleResearchBench": 1}, "rooms": [], "colonists": [], "animals": [],
            "buildings": [], "storage": {}, "professions": {"directions": {}},
            "doctrine": {"primary_direction": "industrial_manufacturing", "building_programs": ["factory"]},
            "finished_research": [], "building_catalog": [],
        })
        self.assertIn("factory", options)

    def test_unavailable_rimapi_is_waiting_not_a_laya_cycle_error(self):
        state, detail, prefix = director.classify_runtime_problem(
            "/api/v1/game/state: <urlopen error [WinError 10061] connection refused>"
        )
        self.assertEqual(state, "waiting")
        self.assertIn("RimWorld", detail)
        self.assertEqual(prefix, "Waiting for RimWorld/RIMAPI")

    def test_real_cycle_failure_remains_an_error(self):
        state, detail, prefix = director.classify_runtime_problem("invalid combat target")
        self.assertEqual(state, "error")
        self.assertEqual(detail, "invalid combat target")
        self.assertEqual(prefix, "Decision cycle problem")

    def test_post_combat_care_selects_patient_and_doctor_then_avoids_duplicate_job(self):
        class Client:
            def __init__(self):
                self.posts = []

            def post(self, endpoint, body=None, query=None):
                self.posts.append((endpoint, body, query))
                return {"success": True}

        patient = {"id": 1, "name": "Patient", "health": 0.51, "bleeding_rate": 0.2,
                   "tendable_now": True, "is_down": False, "is_downed": True}
        doctor = {"id": 2, "name": "Doctor", "health": 1.0, "medicine_skill": 9,
                  "moving": 1.0, "manipulation": 1.0, "tendable_now": False}
        snapshot = {"combat": {"hostiles": [], "colonists": [patient, doctor]},
                    "game": {"is_paused": False}, "map": {"resources": {"medicine": 1}}}
        self.assertIn("tend_1_2", director.post_combat_care_options(snapshot))
        client = Client()
        with tempfile.TemporaryDirectory() as folder:
            record = director.run_post_combat_care_cycle(
                client, self.FakeAgent(["tend_1_2"]), snapshot, pathlib.Path(folder) / "care.jsonl"
            )
        self.assertEqual(record["decision"]["choice"], "tend_1_2")
        self.assertEqual(client.posts[-1][1]["patient_pawn_id"], 1)
        self.assertEqual(client.posts[-1][1]["doctor_pawn_id"], 2)
        doctor.update(current_job="TendPatient", current_job_target_id=1)
        self.assertEqual(director.post_combat_care_options(snapshot), {})
        self.assertTrue(director.treatment_job_in_progress(snapshot))
        patient["tendable_now"] = False
        self.assertFalse(director.treatment_job_in_progress(snapshot))

    def test_post_combat_care_excludes_doctor_with_disabled_medicine(self):
        snapshot = {"combat": {"colonists": [
            {"id": 1, "name": "Patient", "tendable_now": True, "is_downed": True},
            {"id": 2, "name": "Belken", "medicine_skill": 5, "moving": 1, "manipulation": 1},
            {"id": 3, "name": "Four Eyes", "medicine_skill": 0, "moving": 1, "manipulation": 1},
        ]}, "colonists": [
            {"id": 2, "skills": {"Medicine": {"disabled": False}}},
            {"id": 3, "skills": {"Medicine": {"disabled": True}}},
        ]}
        options = director.post_combat_care_options(snapshot)
        self.assertIn("tend_1_2", options)
        self.assertNotIn("tend_1_3", options)

    def test_post_combat_care_offers_rescue_and_executes_selected_job(self):
        class Client:
            def __init__(self):
                self.posts = []

            def get(self, endpoint, **_query):
                if endpoint == "/api/v1/map/buildings":
                    return [{"id": 99, "def": "Bed", "medical": True,
                             "position": {"x": 12, "z": 12}}]
                return {}

            def post(self, endpoint, body=None, query=None):
                self.posts.append((endpoint, body))
                return {"success": True}

        snapshot = {"combat": {"hostiles": [], "colonists": [
            {"id": 1, "name": "Patient", "health": 0.4, "bleeding_rate": 0.8,
             "tendable_now": True, "is_downed": True, "position": {"x": 50, "z": 50}},
            {"id": 2, "name": "Doctor", "health": 1, "medicine_skill": 8,
             "moving": 1, "manipulation": 1, "position": {"x": 45, "z": 45}},
        ]}, "game": {"is_paused": False}, "map": {"id": 0, "resources": {"medicine": 2}}}
        client = Client()
        agent = self.FakeAgent(["rescue_1_2"])
        with tempfile.TemporaryDirectory() as folder:
            record = director.run_post_combat_care_cycle(
                client, agent, snapshot,
                pathlib.Path(folder) / "care.jsonl",
            )
        self.assertEqual(record["decision"]["choice"], "rescue_1_2")
        self.assertIn("tend_1_2", agent.calls[0]["post_combat_care"]["criteria"])
        endpoint, body = next((endpoint, body) for endpoint, body in client.posts
                              if endpoint == "/api/v1/pawn/job")
        self.assertEqual(body["job_def"], "Rescue")
        self.assertEqual(body["pawn_id"], 2)
        self.assertEqual(body["target_thing_id"], 1)
        self.assertEqual(body["target_thing_id_b"], 99)
        self.assertEqual(record["plan"]["kind"], "rescue")
        self.assertTrue(record["result"]["applied"])
        self.assertIn("not a completed treatment", agent.states[0]["triage"])

    def test_post_combat_rescue_avoids_occupied_and_reserved_beds(self):
        beds = [{"id": 99, "def": "Bed", "position": {"x": 10, "z": 10}},
                {"id": 100, "def": "Bed", "position": {"x": 12, "z": 10}},
                {"id": 101, "def": "Bed", "position": {"x": 14, "z": 10}}]
        snapshot = {"combat": {"colonists": [
            {"id": 1, "name": "Bedbound", "is_downed": True,
             "current_job": "LayDown", "current_job_target_id": 99,
             "position": {"x": 10, "z": 10}},
            {"id": 2, "name": "Reserved patient", "is_downed": True,
             "position": {"x": 30, "z": 30}},
            {"id": 3, "name": "Bleeding patient", "is_downed": True,
             "bleeding_rate": 4.5, "position": {"x": 35, "z": 30}},
            {"id": 4, "name": "Rescuer", "current_job": "Rescue",
             "current_job_target_id": 2, "current_job_target_id_b": 100,
             "moving": 1, "manipulation": 1},
            {"id": 5, "name": "Free helper", "moving": 1, "manipulation": 1,
             "position": {"x": 32, "z": 30}},
        ]}}
        options = director.post_combat_care_options(snapshot, beds)
        self.assertNotIn("rescue_1_5", options)
        self.assertNotIn("rescue_2_5", options)
        self.assertEqual(options["rescue_3_5"]["bed_id"], 101)
        self.assertIn("Critical bleeding", options["rescue_3_5"]["summary"])

    def test_infection_risk_is_visible_even_with_full_health_and_no_bleeding(self):
        snapshot = {"combat": {"hostiles": [], "colonists": [
            {"id": 1, "name": "Patient", "health": 1, "bleeding_rate": 0,
             "tendable_now": True, "is_downed": True},
            {"id": 2, "name": "Doctor", "moving": 1, "manipulation": 1,
             "medicine_skill": 5},
        ]}, "colonists": [{"id": 1, "health_conditions": [
            {"def_name": "WoundInfection", "part": "arm", "severity": 0.82,
             "tendable_now": True},
        ]}], "game": {"is_paused": False}, "map": {"resources": {"medicine": 2}}}
        option = director.post_combat_care_options(snapshot)["tend_1_2"]["summary"]
        self.assertIn("infection", option.lower())
        self.assertIn("0.82", option)
        client = mock.Mock()
        client.post.return_value = {"success": True}
        agent = self.FakeAgent(["defer_care"])
        with tempfile.TemporaryDirectory() as folder:
            director.run_post_combat_care_cycle(client, agent, snapshot,
                                                pathlib.Path(folder) / "care.jsonl")
        self.assertIn("infection", agent.calls[0]["post_combat_care"]["criteria"]["defer_care"].lower())

    def test_chosen_treatment_keeps_mobile_bleeding_patient_in_doctor_reach(self):
        class Client:
            def __init__(self):
                self.posts = []

            def post(self, endpoint, body=None, query=None):
                self.posts.append((endpoint, body))
                return {"success": True}

        snapshot = {"combat": {"hostiles": [], "colonists": [
            {"id": 1, "name": "Patient", "health": 0.5, "bleeding_rate": 1.4,
             "tendable_now": True, "is_downed": False, "current_job": "HaulToCell"},
            {"id": 2, "name": "Doctor", "medicine_skill": 5,
             "moving": 1, "manipulation": 1, "current_job": "Sow"},
        ]}, "game": {"is_paused": False}, "map": {"resources": {"medicine": 2}}}
        client = Client()
        with tempfile.TemporaryDirectory() as folder:
            record = director.run_post_combat_care_cycle(
                client, self.FakeAgent(["tend_1_2"]), snapshot,
                pathlib.Path(folder) / "care.jsonl",
            )
        self.assertEqual([endpoint for endpoint, _ in client.posts[-2:]],
                         ["/api/v1/pawn/job", "/api/v1/pawn/medical/tend"])
        self.assertEqual(client.posts[-2][1]["job_def"], "Wait_MaintainPosture")
        self.assertTrue(record["result"]["patient_hold"]["success"])

    def test_completed_short_advance_requests_a_new_shooting_decision(self):
        record = {"action": {"commands": [{"endpoint": "/api/v1/combat/tactic", "body": {
            "tactic": "focus_fire", "fighter_ids": [1], "target_pawn_id": 99,
        }}]}, "result": {"responses": [{"positioned_pawn_ids": [1]}]}}
        snapshot = {"combat": {"colonists": [{"id": 1, "current_job": "Goto"}]}}
        self.assertFalse(director.combat_positioning_finished(snapshot, record, 1.0))
        self.assertFalse(director.combat_positioning_finished(snapshot, record, 3.0))
        snapshot["combat"]["colonists"][0]["current_job"] = "Wait"
        self.assertTrue(director.combat_positioning_finished(snapshot, record, 3.0))

    def test_post_combat_care_can_be_deferred_even_if_only_one_treatment_exists(self):
        class Client:
            def __init__(self):
                self.posts = []

            def post(self, endpoint, body=None, query=None):
                self.posts.append((endpoint, body, query))

        snapshot = {"combat": {"hostiles": [], "colonists": [
            {"id": 1, "name": "Patient", "health": 0.6, "bleeding_rate": 0.1,
             "tendable_now": True, "is_downed": True},
            {"id": 2, "name": "Doctor", "health": 1, "moving": 1, "manipulation": 1,
             "medicine_skill": 8},
        ]}, "game": {"is_paused": False}, "map": {"resources": {"medicine": 0}}}
        client = Client()
        agent = self.FakeAgent(["defer_care"])
        with tempfile.TemporaryDirectory() as folder:
            record = director.run_post_combat_care_cycle(
                client, agent, snapshot, pathlib.Path(folder) / "care.jsonl"
            )
        self.assertTrue(record["result"]["deferred"])
        self.assertTrue(record["result"]["revisit"])
        self.assertFalse(any(endpoint == "/api/v1/pawn/medical/tend" for endpoint, _, _ in client.posts))
        self.assertTrue(any(endpoint == "/api/v1/ui/announce" for endpoint, _, _ in client.posts))
        self.assertIn("tend_1_2", agent.calls[0]["post_combat_care"]["criteria"])
        self.assertIn("resume_colony_decisions", agent.calls[0]["post_combat_care"]["criteria"])

    def test_returning_to_colony_decisions_does_not_force_another_care_prompt(self):
        class Client:
            def post(self, endpoint, body=None, query=None):
                if endpoint != "/api/v1/ui/announce":
                    raise AssertionError("No treatment or pause command is needed")
                return {"success": True}

        snapshot = {"combat": {"hostiles": [], "colonists": [
            {"id": 1, "name": "Patient", "health": 0.6, "bleeding_rate": 0.1,
             "tendable_now": True, "is_downed": True},
            {"id": 2, "name": "Doctor", "health": 1, "moving": 1, "manipulation": 1,
             "medicine_skill": 8},
        ]}, "game": {"is_paused": False}, "map": {"resources": {"medicine": 0}}}
        with tempfile.TemporaryDirectory() as folder:
            record = director.run_post_combat_care_cycle(
                Client(), self.FakeAgent(["resume_colony_decisions"]),
                snapshot, pathlib.Path(folder) / "care.jsonl",
            )
        self.assertTrue(record["result"]["deferred"])
        self.assertFalse(record["result"]["revisit"])

    def test_live_naming_dialogue_uses_model_choice_and_exact_api_target(self):
        class Client:
            def __init__(self):
                self.posts = []

            def get(self, endpoint, **_query):
                self.endpoint = endpoint
                return [{"window_type": "Dialog_NamePlayerSettlement", "force_pause": True,
                         "suggested_names": ["Ember Vale", "Three Pines", "New Dawn"]}]

            def post(self, endpoint, body=None):
                self.posts.append((endpoint, body))
                return {"success": True}

        client = Client()
        agent = self.FakeAgent(["option_1"])
        snapshot = {"map": {"id": 1, "resources": {"food": 20}},
                    "game": {"tick": 1200}, "colonists": [{"id": 1, "name": "Ada"}]}
        with tempfile.TemporaryDirectory() as folder:
            record = director.run_window_cycle(client, agent, snapshot, {}, pathlib.Path(folder) / "test.jsonl")
        self.assertEqual(client.endpoint, "/api/v1/ui/windows")
        self.assertEqual(client.posts, [("/api/v1/ui/window/name", {
            "window_type": "Dialog_NamePlayerSettlement", "suggested_name": "Three Pines"})])
        self.assertEqual(record["decision"]["choice"], "option_1")
        self.assertNotIn("defer", agent.calls[0]["live_dialogue"]["criteria"])

    def test_choice_letter_presents_accept_and_reject_to_laya(self):
        class Client:
            def __init__(self):
                self.posts = []

            def get(self, endpoint, **_query):
                self.endpoint = endpoint
                return {"letters": [{"id": 17, "arrival_tick": 1000,
                                     "label": "Joiner", "text": "A refugee asks to stay.",
                                     "enabled_options": ["Accept", "Reject"]}]}

            def post(self, endpoint, body=None):
                self.posts.append((endpoint, body))
                return {"success": True}

        client = Client()
        snapshot = {"map": {"id": 1, "resources": {"food": 35}},
                    "game": {"tick": 1200}, "colonists": [{"id": 1}]}
        with tempfile.TemporaryDirectory() as folder:
            record = director.run_letter_cycle(client, self.FakeAgent(["option_0"]),
                                               snapshot, {}, pathlib.Path(folder) / "test.jsonl")
        self.assertEqual(client.posts, [("/api/v1/events/letter/choose", {
            "letter_id": 17, "option_label": "Accept"})])
        self.assertEqual(record["decision"]["choice"], "option_0")

    def test_paralyzed_joiner_letter_exposes_labor_cost_without_forcing_answer(self):
        client = mock.Mock()
        client.get.return_value = {"letters": [{
            "id": 18, "arrival_tick": 1000, "label": "Transport pod crash",
            "text": "The joiner has paralytic abasia and will be unable to walk for many days.",
            "enabled_options": ["Accept", "Reject"],
        }]}
        client.post.return_value = {"success": True}
        snapshot = {"map": {"id": 1, "resources": {"food": 35}},
                    "game": {"tick": 1200},
                    "colonists": [{"id": 1, "downed": False}, {"id": 2, "downed": True}]}
        agent = self.FakeAgent(["option_1"])
        with tempfile.TemporaryDirectory() as folder:
            record = director.run_letter_cycle(client, agent, snapshot, {},
                                               pathlib.Path(folder) / "test.jsonl")
        self.assertEqual(record["decision"]["choice"], "option_1")
        self.assertEqual(agent.states[0]["able_workers"], 1)
        self.assertIn("cannot work", agent.states[0]["incoming_labor"])
        self.assertEqual(set(agent.calls[0]["letter_response"]["criteria"]),
                         {"option_0", "option_1", "defer"})

    def test_notification_letter_does_not_interrupt_colony_work(self):
        class Client:
            def get(self, endpoint, **_query):
                return {"letters": [{"id": 0, "arrival_tick": 1000,
                                     "label": "Raid", "enabled_options": ["Close", "Jump to location"]}]}

            def post(self, *_args, **_kwargs):
                self.fail("Notification is not a choice")

        snapshot = {"map": {"id": 1}, "game": {"tick": 1200}, "colonists": []}
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(director.run_letter_cycle(
                Client(), self.FakeAgent([]), snapshot, {}, pathlib.Path(folder) / "test.jsonl"))

    def test_failed_letter_reply_is_deferred_without_stopping_cycle(self):
        class Client:
            def get(self, endpoint, **_query):
                return {"letters": [{"id": 17, "arrival_tick": 1000,
                                     "label": "Joiner", "text": "Needs shelter",
                                     "enabled_options": ["Accept", "Reject"]}]}

            def post(self, *_args, **_kwargs):
                raise director.bridge.RimApiError("letter reply failed")

        snapshot = {"map": {"id": 1, "resources": {}},
                    "game": {"tick": 1200}, "colonists": []}
        state = {}
        with tempfile.TemporaryDirectory() as folder:
            result = director.run_letter_cycle(
                Client(), self.FakeAgent(["option_0"]), snapshot, state,
                pathlib.Path(folder) / "test.jsonl")
        self.assertFalse(result["result"]["applied"])
        self.assertIn("17", next(iter(state["maps"].values()))["deferred_letters"])

    def test_slave_trader_exposes_population_choice_only_when_stocked(self):
        trader = {"stock": [
            {"def_name": "Human", "label": "Young medic", "count": 1,
             "humanlike": True, "market_value": 1400, "health": 0.92,
             "skills": ["Medicine 8", "Plants 6"]},
            {"def_name": "Horse", "label": "Horse", "count": 2,
             "animal": True, "market_value": 480},
        ]}
        options = director.live_purchase_options(trader, population=2)
        self.assertIn("slaves", options)
        self.assertIn("Medicine 8", options["slaves"])
        self.assertIn("livestock", options)
        self.assertEqual(director.live_purchase_options({"stock": []}, population=2),
                         {"none": "Buy nothing; sell surplus or preserve silver."})


if __name__ == "__main__":
    unittest.main()

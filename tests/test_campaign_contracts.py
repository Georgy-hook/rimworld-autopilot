"""Offline campaign transitions using actual server JSON names, not game simulation."""
import copy
import json
import unittest
from unittest.mock import patch

import colony_director as director
import colony_sessions as sessions
import colony_shipbuilding as shipbuilding
import colony_strategy as strategy
import colony_affordances as affordances
import colony_modules as modules
import rimworld_laya as bridge
import laya_decisions
from tools.audit_api_contracts import inventory
from tests.test_module_architecture import Agent


class CampaignContracts(unittest.TestCase):
    def test_roster_is_local_on_visit_and_does_not_count_caravans_as_workers(self):
        data = {"/api/v1/game/state": {"game_tick": 500000, "colonist_count": 4},
            "/api/v1/maps": [{"id": 1, "is_player_home": True, "free_colonists": 2},
                             {"id": 2, "is_current_map": True, "free_colonists": 1}],
            "/api/v2/colonists/detailed": [{"pawn": {"id": i, "map_id": m, "spawned": m is not None}, "detailes": {}}
                                            for i, m in ((1, 1), (2, 1), (3, 2), (4, None))],
            "/api/v1/combat/state": {"colonists": [{"id": 3}], "hostiles": []}}
        class Client:
            def get(self, path, **query):
                return copy.deepcopy(data.get(path))
        snap = bridge.collect_snapshot(Client())
        self.assertEqual(snap["map"]["id"], 2)
        self.assertEqual([p["id"] for p in snap["colonists"]], [3])
        self.assertEqual(snap["game"]["colonist_count"], 4)

    def test_archonexus_and_expedition_share_goal_but_not_spatial_orders(self):
        state = {}
        sessions.bind_campaign(state, {"campaign_id": "native-game-A"})
        home = {"map": {"id": 1, "seed": "a", "tile_id": 10}, "game": {"tick": 500}, "colonists": [{"id": 3}]}
        memory = director.map_state_for_snapshot(state, home)
        memory.update(doctrine={"endgame": "archonexus"}, doctrine_tick=400, anchor={"x": 100, "z": 100})
        memory["issued"]["starter_base"] = 450
        sessions.remember_campaign(state, memory)
        destination = {"map": {"id": 2, "seed": "b", "tile_id": 20}, "game": {"tick": 900}, "colonists": [{"id": 3}]}
        next_memory = director.map_state_for_snapshot(state, destination)
        self.assertEqual(next_memory["doctrine"]["endgame"], "archonexus")
        self.assertNotIn("anchor", next_memory)
        self.assertEqual(next_memory["issued"], {})
        sessions.bind_campaign(state, {"campaign_id": "native-game-B"})
        self.assertNotIn("maps", state)
        self.assertNotIn("doctrine", state["campaign"])

    def test_rollback_cannot_resurrect_future_campaign_goal_later(self):
        state = {"campaign": {"id": "a", "doctrine": {"endgame": "ship_journey"}, "doctrine_tick": 900}}
        director.map_state_for_snapshot(state, {"map": {"id": 1}, "game": {"tick": 500}})
        self.assertNotIn("doctrine", state["campaign"])

    def test_expedition_arrival_exposes_endings_and_care_instead_of_idling(self):
        self.assertEqual(director.expedition_candidates(["build_temple", "progression_ending", "progression_ship",
            "affordances_interaction", "resilience_tend", "hold_survival"]),
            ["progression_ending", "progression_ship", "affordances_interaction", "resilience_tend", "hold_survival"])

    def test_native_ending_is_not_hidden_by_missing_beds_at_destination(self):
        snap = {"map": {"is_temp_incident_map": True}, "colonists": [{"id": 3}],
                "development": {"beds": [], "buildings": []}}
        with patch.object(director, "sleeping_place_counts", return_value=(0, 0)), \
             patch.object(director, "sheltered_real_bed_count", return_value=0):
            actions = director.defer_discretionary_work_until_shelter(snap, {},
                ["progression_ending", "progression_boardship", "progression_ship", "build_temple", "hold_survival"])
        self.assertIn("progression_boardship", actions)
        self.assertIn("progression_ending", actions)
        self.assertNotIn("build_temple", actions)

    def test_last_boarded_pawn_does_not_hide_away_ship_behind_empty_or_populated_home(self):
        home = {"id": 1, "is_player_home": True, "free_colonists": 2}
        ship = {"id": 2, "is_temp_incident_map": True, "free_colonists": 0, "player_ship_passengers": 3}
        self.assertEqual(bridge.select_work_map([home, ship])["id"], 2)
        home["free_colonists"] = 0
        self.assertEqual(bridge.select_work_map([home, ship])["id"], 2)
        home.update(free_colonists=2, hostiles=1)
        self.assertEqual(bridge.select_work_map([home, ship])["id"], 1)

    def test_old_rescue_plan_cannot_return_from_an_unrelated_ending_site(self):
        from pathlib import Path
        class Client:
            def get(self, path, **query):
                return {"site_id": 20, "can_return_home": True}
            def post(self, *args, **kwargs):
                raise AssertionError("Unrelated site must not receive a rescue or return command")
        state = {"maps": {"home": {"rescue_mission": {"site_id": 10}}}}
        snap = {"map": {"id": 2, "is_temp_incident_map": True}}
        self.assertIsNone(director.run_rescue_site_cycle(Client(), state, Path("unused"), Path("unused"), snap))
        self.assertIn("rescue_mission", state["maps"]["home"])

    def test_goal_shortages_are_shared_with_other_modules(self):
        snap = {"development": {"doctrine": {"endgame": "ship_journey"},
            "ship_construction": {"shortages": {"AIPersonaCore": 1}},
            "progression": {"ending_journey": {"readiness": [{"route": "ship_journey", "object_id": 20,
                "blockers": ["insufficient travel medicine"]}]}}}}
        needs = modules.goal_requirements(snap)
        self.assertEqual(needs["ship_materials"], {"AIPersonaCore": 1})
        self.assertIn("travel medicine missing", needs["journey"]["blockers"])
        self.assertEqual(modules.signals(snap)["journey_blockers"], 1)

    def test_native_royal_requirements_reach_architecture_and_research(self):
        person = {"pawn_id": 7, "requires_bedroom": True, "has_unmet_bedroom_requirements": True,
            "minimum_bedroom_impressiveness": 180, "bedroom_required_bed_defs": ["RoyalBed"]}
        snap = {"development": {"royalty": {"colonists": []}, "specialists": {"royalty_context": {
            "active": True, "colonists": [person]}}, "building_catalog": [{"def_name": "RoyalBed",
            "available_now": False, "research_prerequisites": ["ComplexFurniture"]}],
            "research_tree": [{"name": "ComplexFurniture", "can_start_now": True,
                               "player_has_any_appropriate_research_bench": True}]}}
        director.integrate_native_goal_context(snap)
        dev = snap["development"]
        self.assertEqual(dev["royalty"]["colonists"], [person])
        self.assertIn("ComplexFurniture", dev["progression"]["support_research"]["royal_ascent"]["frontier"])
        self.assertEqual(director.room_impressiveness_target({"role_def_name": "Bedroom", "role_label": "Спальня"}, dev), 180)
        self.assertTrue(modules.goal_requirements(snap)["royal"]["rooms"])

    def test_care_environment_unwraps_native_room_envelope_and_localized_label(self):
        class Client:
            def get(self, path, **kwargs):
                return {"rooms": [{"id": 4, "role_label": "Спальня", "role_def_name": "Bedroom",
                    "temperature": -20}]} if path.endswith("rooms") else []
        snapshot = {"map": {"id": 1}}
        director.collect_care_environment(Client(), snapshot)
        room = snapshot["development"]["rooms"][0]
        self.assertEqual(room["temperature"], -20)
        self.assertEqual(room["role_label"], "Bedroom")
        self.assertEqual(room["role_display_label"], "Спальня")

    def test_literal_client_routes_exist_with_correct_http_method(self):
        audit = inventory()
        self.assertFalse(audit["missing"], audit["missing"])
        self.assertFalse(audit["duplicate_routes"])
        self.assertGreater(len(audit["literal_calls"]), 200)

    def test_unbounded_legacy_state_is_explicitly_packed_before_encoder(self):
        agent = Agent()
        _, raw = laya_decisions.ask_laya_choice(agent, {"decision_facts": {"goal": "archonexus"}, "huge": "x" * 10000},
            "legacy", "Choose a useful step", {"a": "study", "b": "wait"})
        self.assertLessEqual(len(agent.tok(json.dumps(raw["visible_state"]))["input_ids"]), 312)
        self.assertIn("archonexus", raw["visible_state"]["decision_facts"])

    def test_every_strategy_comparison_sees_intended_goal_and_downside(self):
        agent = Agent()
        strategy._ask(agent, {"chosen_so_far": {"endgame": "archonexus", "primary_direction": "industrial_manufacturing"},
                              "ending_progress": {"long": "x" * 20000}},
                      "doctrine_economy_family", "Choose supporting income", {"manufacturing": "Промышленность", "animals": "Животные"})
        for state, questions in agent.calls:
            self.assertIn("archonexus", state["facts"])
            self.assertTrue(all(card["risk"] and card["cost"] for card in state["effects"].values()))
            self.assertTrue(all(not any('\u0400' <= c <= '\u04ff' for c in text)
                                for q in questions.values() for text in q["criteria"].values()))

    def test_affordance_ordinary_need_drift_does_not_starve_execution(self):
        a = {"pawn": {"pawn_id": 1, "job": "HaulToCell", "food": .6, "mood": .7, "health": .9,
                      "food_category": "Fed", "downed": False}, "cost": {"psyfocus": .1}}
        b = copy.deepcopy(a); b["pawn"].update(job="Wait_Wander", food=.58, mood=.69, health=.905)
        self.assertFalse(affordances.evidence_changed(affordances.evidence(a), affordances.evidence(b)))
        b["pawn"]["downed"] = True
        self.assertTrue(affordances.evidence_changed(affordances.evidence(a), affordances.evidence(b)))


class ShipStages(unittest.TestCase):
    def fixture(self):
        layout = {"width": 3, "height": 8, "roof": False, "floors": [], "buildings": [
            {"def_name": "Ship_Beam", "rel_x": 0, "rel_z": 0, "rotation": 0},
            {"def_name": "Ship_ComputerCore", "rel_x": 2, "rel_z": 0, "rotation": 0},
            {"def_name": "Ship_CryptosleepCasket", "rel_x": 0, "rel_z": 4, "rotation": 0}]}
        catalog = [{"def_name": row["def_name"], "cost_list": [{"thing_def": "AIPersonaCore" if "Computer" in row["def_name"] else "Steel", "count": 1}]} for row in layout["buildings"]]
        snap = {"map": {"id": 1}, "game": {"tick": 800000}, "development": {"building_catalog": catalog,
            "item_counts": {"Steel": 5, "AIPersonaCore": 1}, "buildings": [], "construction_projects": []}}
        return layout, snap, {"anchor": {"x": 30, "z": 30}}

    def test_caskets_wait_for_completed_beams_and_missing_parts_are_retried(self):
        layout, snap, memory = self.fixture()
        plan = shipbuilding.prepare(snap, memory, layout)
        self.assertEqual(len(plan["ready_layout"]["buildings"]), 2)
        memory["ship_project"] = {"origin": plan["origin"], "layout": layout}
        beam = {"def_name": "Ship_Beam", "position": {"x": 25, "z": 55}}
        core = {"def_name": "Ship_ComputerCore", "position": {"x": 27, "z": 55}}
        snap["development"]["construction_projects"] = [beam, core]
        self.assertFalse(shipbuilding.prepare(snap, memory, layout)["ready_layout"]["buildings"])
        snap["development"]["buildings"] = [beam]
        snap["development"]["construction_projects"] = [core]
        ready = shipbuilding.prepare(snap, memory, layout)["ready_layout"]["buildings"]
        self.assertEqual([r["def_name"] for r in ready], ["Ship_CryptosleepCasket"])
        snap["development"]["construction_projects"] = []
        ready = shipbuilding.prepare(snap, memory, layout)["ready_layout"]["buildings"]
        self.assertIn("Ship_ComputerCore", [r["def_name"] for r in ready])

    def test_core_missing_stock_is_visible_and_cannot_be_funded(self):
        layout, snap, memory = self.fixture()
        snap["development"]["item_counts"].pop("AIPersonaCore")
        plan = shipbuilding.prepare(snap, memory, layout)
        self.assertEqual(plan["shortages"], {"AIPersonaCore": 1})
        self.assertNotIn("Ship_ComputerCore", [r["def_name"] for r in plan["ready_layout"]["buildings"]])


if __name__ == "__main__":
    unittest.main()

"""Regression for the hive pickup and untreated casualty seen in the long run."""

import copy
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import colony_combat
import colony_director as director
import rimworld_laya as bridge


def hive_snapshot():
    fumiko = {"id": 984, "name": "Fumiko", "position": {"x": 161, "z": 134},
              "is_dead": False, "is_downed": False, "can_fight": False,
              "is_drafted": False, "moving": 1.0, "manipulation": 1.0,
              "current_job": "LayDown", "distance_to_nearest_opponent": 26,
              "medicine_skill": 3, "weapon_def": None}
    kings = {"id": 987, "name": "Kings", "position": {"x": 167, "z": 123},
             "is_dead": False, "is_downed": True, "tendable_now": True,
             "bleeding_rate": 5.8, "health": 0.35}
    mitch = {"id": 990, "name": "Mitch", "position": {"x": 169, "z": 116},
             "is_dead": False, "is_downed": True, "tendable_now": True,
             "bleeding_rate": 3.8, "health": 0.42}
    insects = [{"id": 1500 + index, "kind_def": "Megaspider",
                "position": {"x": 180 + index, "z": 115},
                "lord_job_type": "LordJob_DefendAndExpandHive"}
               for index in range(3)]
    return {
        "game": {"is_paused": False}, "map": {"id": 1, "enemies": 3, "resources": {"medicine": 1}},
        "colonists": [{"id": 984, "name": "Fumiko", "skills": {"Medicine": {"disabled": False}},
                       "position": fumiko["position"]}],
        "combat": {"available": True, "colonists": [fumiko, kings, mitch],
                   "hostiles": insects, "available_weapons": [
                       {"id": 34892, "label": "bolt-action rifle", "is_ranged": True,
                        "position": {"x": 170, "z": 116}},
                       {"id": 34893, "label": "revolver", "is_ranged": True,
                        "position": {"x": 168, "z": 123}},
                   ]},
        "development": {"forbidden": [], "things": [], "corpses": []},
    }


class ChoosingAgent:
    def __init__(self, choice):
        self.choice = choice
        self.questions = []

    def predict(self, state, questions):
        self.questions.append(questions)
        question_id = next(iter(questions))
        assert self.choice in questions[question_id]["criteria"]
        return {"answers": {question_id: {"choice": self.choice, "confidence": 0.9,
                                         "probabilities": {self.choice: 1.0}}}}


class RecordingClient:
    def __init__(self, things=()):
        self.things = list(things)
        self.posts = []

    def get(self, endpoint, **query):
        if endpoint == "/api/v1/map/things":
            return self.things
        if endpoint == "/api/v1/map/buildings":
            return []
        if endpoint == "/api/v1/game/settings":
            return {"language": "English"}
        raise AssertionError(endpoint)

    def post(self, endpoint, *, body=None, query=None):
        self.posts.append((endpoint, body, query))
        return {"success": True}


class HiveSurvivalTests(unittest.TestCase):
    def test_hive_weapons_are_not_offered_or_assigned_even_if_forced(self):
        snapshot = hive_snapshot()
        for pawn in snapshot["combat"]["colonists"][1:]:
            pawn.update(is_downed=False, can_fight=True, weapon_def=None,
                        has_ranged_weapon=False, moving=1.0, manipulation=1.0,
                        sight=1.0, distance_to_nearest_opponent=20,
                        tendable_now=False, bleeding_rate=0)
        criteria = bridge.make_questions(snapshot)["threat_action"]["criteria"]
        self.assertEqual(set(criteria), {"civilian_retreat"})
        self.assertNotIn("equip_ranged_weapon", criteria)
        self.assertNotIn("prepare_undrafted", criteria)
        action = bridge.plan_action(snapshot, {"choice": "equip_ranged_weapon"})
        self.assertFalse(any(command.get("body", {}).get("job_def") == "Equip"
                             for command in action.get("commands", [])))
        self.assertTrue(colony_combat.errand_exposed(
            snapshot, {"x": 170, "z": 116}, {"x": 140, "z": 140}))
        snapshot["combat"]["available_weapons"] = [{"id": 10, "is_ranged": True,
                                                       "position": {"x": 130, "z": 140}}]
        self.assertFalse(colony_combat.errand_exposed(
            snapshot, {"x": 130, "z": 140}, {"x": 140, "z": 140}))

    def test_sleeping_pacifist_can_choose_field_tending_without_bed(self):
        snapshot = hive_snapshot()
        self.assertTrue(director.live_threat_care_needed(snapshot))
        criteria = bridge.make_questions(snapshot)["threat_action"]["criteria"]
        self.assertNotIn("civilian_retreat", criteria)
        self.assertEqual(bridge.plan_action(snapshot, {"choice": "civilian_retreat"})["kind"], "noop")
        client = RecordingClient()
        agent = ChoosingAgent("tend_987_984")
        with tempfile.TemporaryDirectory() as folder:
            record = director.run_post_combat_care_cycle(
                client, agent, snapshot, pathlib.Path(folder) / "care.jsonl",
                live_threat=True)
        self.assertEqual(record["decision"]["choice"], "tend_987_984")
        self.assertIn("defer_care", agent.questions[0]["post_combat_care"]["criteria"])
        self.assertNotIn("withdraw_civilian", agent.questions[0]["post_combat_care"]["criteria"])
        self.assertTrue(any(endpoint == "/api/v1/pawn/medical/tend"
                            and body["patient_pawn_id"] == 987
                            and body["doctor_pawn_id"] == 984
                            for endpoint, body, _ in client.posts))

    def test_civilian_inside_hive_guard_area_can_withdraw(self):
        snapshot = hive_snapshot()
        snapshot["combat"]["colonists"][0]["position"] = {"x": 168, "z": 129}
        criteria = bridge.make_questions(snapshot)["threat_action"]["criteria"]
        self.assertIn("civilian_retreat", criteria)
        retreat = bridge.plan_action(snapshot, {"choice": "civilian_retreat"})
        tactic = next(command["body"] for command in retreat["commands"]
                      if command["endpoint"] == "/api/v1/combat/tactic")
        self.assertEqual(tactic["fighter_ids"], [984])
        client = RecordingClient()
        agent = ChoosingAgent("withdraw_civilian")
        with tempfile.TemporaryDirectory() as folder:
            record = director.run_post_combat_care_cycle(
                client, agent, snapshot, pathlib.Path(folder) / "care.jsonl", live_threat=True)
        self.assertTrue(record["result"]["applied"])

    def test_remote_hive_does_not_delay_safe_treatment_of_bleeding_colonist(self):
        snapshot = hive_snapshot()
        snapshot["combat"]["colonists"] = [
            {"id": 928, "name": "Fixer", "position": {"x": 128, "z": 121},
             "is_downed": False, "moving": 1.0, "manipulation": 1.0,
             "can_fight": False, "is_drafted": False, "weapon_def": None},
            {"id": 50204, "name": "Glasses", "position": {"x": 155, "z": 124},
             "is_downed": True, "tendable_now": True, "bleeding_rate": 2.77},
        ]
        snapshot["colonists"] = [{"id": 928, "skills": {"Medicine": {"disabled": False}}}]
        snapshot["combat"]["hostiles"] = [
            {"id": 48599, "kind_def": "Spelopede", "position": {"x": 194, "z": 108},
             "lord_job_type": "LordJob_DefendAndExpandHive", "current_job": "LayDown"},
        ]
        client = RecordingClient()
        agent = ChoosingAgent("tend_50204_928")
        with tempfile.TemporaryDirectory() as folder:
            record = director.run_post_combat_care_cycle(
                client, agent, snapshot, pathlib.Path(folder) / "care.jsonl", live_threat=True)
        self.assertEqual(set(record["decision"]["raw"]["question"]["criteria"]),
                         {"tend_50204_928"})
        self.assertEqual(agent.questions, [])
        self.assertTrue(record["result"]["applied"])
        self.assertTrue(any(endpoint == "/api/v1/pawn/medical/tend"
                            and body["patient_pawn_id"] == 50204
                            for endpoint, body, _ in client.posts))

    def test_started_critical_treatment_is_not_replaced_by_retreat(self):
        snapshot = hive_snapshot()
        snapshot["combat"]["colonists"][0].update(
            current_job="TendPatient", current_job_target_id=987)
        self.assertEqual(colony_combat.protected_emergency_care_ids(snapshot), {984})
        self.assertNotIn("civilian_retreat", bridge.make_questions(snapshot)["threat_action"]["criteria"])
        self.assertEqual(bridge.combat_reserve_commands(snapshot, set()), [])
        forced = bridge.plan_action(snapshot, {"choice": "civilian_retreat"})
        self.assertFalse(any(command["endpoint"] == "/api/v1/combat/tactic"
                             for command in forced.get("commands", [])))

    def test_distant_guarding_insects_do_not_freeze_safe_colony_work(self):
        snapshot = hive_snapshot()
        snapshot["combat"]["colonists"] = [snapshot["combat"]["colonists"][0]]
        snapshot["combat"]["colonists"][0].update(
            distance_to_nearest_opponent=60, current_job="CookFillHopper")
        criteria = bridge.make_questions(snapshot)["threat_action"]["criteria"]
        self.assertIn("continue_safe_colony_work", criteria)
        self.assertNotIn("prepare_undrafted", criteria)
        decision = {"decision": {"choice": "continue_safe_colony_work"}}
        self.assertTrue(director.staging_development_allowed(snapshot, decision))
        snapshot["combat"]["colonists"][0]["distance_to_nearest_opponent"] = 25
        self.assertFalse(director.staging_development_allowed(snapshot, decision))

    def test_armed_colonists_do_not_advance_into_passive_hive_for_a_firing_line(self):
        snapshot = hive_snapshot()
        for index, pawn in enumerate(snapshot["combat"]["colonists"][1:]):
            pawn.update(is_downed=False, tendable_now=False, bleeding_rate=0,
                        can_fight=True, is_drafted=index == 0,
                        has_ranged_weapon=True, weapon_def="Gun_Revolver",
                        weapon_range=26, manipulation=1.0, sight=1.0,
                        position={"x": 142 + index, "z": 134},
                        distance_to_nearest_opponent=37 + index)
        for hostile in snapshot["combat"]["hostiles"]:
            hostile.update(current_job="GotoWander", distance_to_nearest_opponent=37)
        self.assertTrue(colony_combat.guarded_hive_outside_contact(snapshot))
        criteria = bridge.make_questions(snapshot)["threat_action"]["criteria"]
        self.assertNotIn("focus_fire", criteria)
        self.assertNotIn("hold_cover", criteria)
        self.assertNotIn("preemptive_strike", criteria)
        self.assertIn("prepare_undrafted", criteria)
        self.assertEqual(bridge.plan_action(snapshot, {"choice": "focus_fire"})["kind"], "noop")
        snapshot["combat"]["available_weapons"] = [
            {"id": 10, "label": "safe spare rifle", "is_ranged": True,
             "position": {"x": 140, "z": 134}},
        ]
        snapshot["combat"]["colonists"][2].update(
            has_ranged_weapon=False, weapon_def=None)
        self.assertIn("equip_ranged_weapon", bridge.make_questions(snapshot)["threat_action"]["criteria"])
        self.assertTrue(any(command.get("body", {}).get("job_def") == "Equip"
                            for command in bridge.plan_action(
                                snapshot, {"choice": "equip_ranged_weapon"}).get("commands", [])))
        snapshot["combat"]["hostiles"][0].update(
            current_job="AttackMelee", distance_to_nearest_opponent=4)
        self.assertFalse(colony_combat.guarded_hive_outside_contact(snapshot))
        self.assertTrue(any(command.get("body", {}).get("tactic") == "focus_fire"
                            for command in bridge.plan_action(
                                snapshot, {"choice": "focus_fire"}).get("commands", [])))

    def test_passive_hive_guard_keeps_nearby_home_food_usable(self):
        snapshot = hive_snapshot()
        snapshot["combat"]["hostiles"] = [{
            "id": 1, "kind_def": "Megascarab", "position": {"x": 171, "z": 121},
            "lord_job_type": "LordJob_DefendAndExpandHive", "current_job": "GotoWander",
        }]
        self.assertTrue(colony_combat.errand_exposed(
            snapshot, {"x": 168, "z": 123}, {"x": 140, "z": 134}))
        self.assertFalse(colony_combat.errand_exposed(
            snapshot, {"x": 150, "z": 133}, {"x": 140, "z": 134}))

    def test_non_hive_threat_is_targeted_before_passive_hive_guards(self):
        snapshot = hive_snapshot()
        for hostile in snapshot["combat"]["hostiles"]:
            hostile.update(current_job="GotoWander", distance_to_nearest_opponent=20,
                           combat_power=100)
        snapshot["combat"]["hostiles"].append({
            "id": 2222, "kind_def": "Monkey", "current_job": "AttackMelee",
            "position": {"x": 140, "z": 134}, "distance_to_nearest_opponent": 2,
            "combat_power": 1,
        })
        self.assertEqual(colony_combat.choose_default_target(snapshot, "focus_fire"), 2222)

    def test_forbid_hive_jelly_and_break_existing_fetch_order(self):
        snapshot = hive_snapshot()
        snapshot["combat"]["colonists"][0].update(
            current_job="Ingest", current_job_target_id=49400)
        items = [{"thing_id": 49400, "def_name": "InsectJelly",
                  "position": {"x": 180, "z": 113}, "is_forbidden": False},
                 {"thing_id": 34892, "def_name": "Gun_BoltActionRifle",
                  "position": {"x": 170, "z": 116}, "is_forbidden": False}]
        client = RecordingClient(items)
        with tempfile.TemporaryDirectory() as folder:
            record = director.run_hazard_exclusion_cycle(
                client, snapshot, pathlib.Path(folder) / "guard.jsonl")
        self.assertEqual({row["id"] for row in record["items"]}, {49400, 34892})
        self.assertEqual(record["stopped"][0]["pawn_id"], 984)
        self.assertTrue(any(endpoint == "/api/v1/pawn/job"
                            and body["job_def"] == "Wait_MaintainPosture"
                            and body["pawn_id"] == 984
                            for endpoint, body, _ in client.posts))
        self.assertTrue(any(endpoint == "/api/v1/things/set-forbidden"
                            and set(body["thing_ids"]) == {49400, 34892}
                            for endpoint, body, _ in client.posts))
        snapshot["development"]["forbidden"] = [
            {"thing_id": 49400, "def_name": "InsectJelly", "categories": ["AnimalProductRaw"],
             "position": {"x": 180, "z": 113}},
        ]
        self.assertEqual(director.relevant_forbidden(snapshot), [])
        safe = copy.deepcopy(snapshot)
        safe["combat"]["hostiles"] = []
        self.assertEqual(len(director.relevant_forbidden(safe)), 1)


if __name__ == "__main__":
    unittest.main()

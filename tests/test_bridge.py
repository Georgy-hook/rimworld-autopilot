import importlib.util
import pathlib
import sys
import types
import unittest
from unittest import mock


MODULE_PATH = pathlib.Path(__file__).parents[1] / "rimworld_laya.py"
SPEC = importlib.util.spec_from_file_location("rimworld_laya", MODULE_PATH)
bridge = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = bridge
SPEC.loader.exec_module(bridge)


class FakeAgent:
    def __init__(self, choice="prioritize_cooking", confidence=0.9):
        self.choice = choice
        self.confidence = confidence

    def predict(self, state, questions):
        question_id = next(iter(questions))
        return {
            "answers": {
                question_id: {
                    "choice": self.choice,
                    "confidence": self.confidence,
                    "probabilities": {self.choice: 1.0},
                }
            }
        }


class RosterAgent:
    def __init__(self):
        self.calls = []

    def predict(self, state, questions):
        self.calls.append(questions)
        answers = {}
        for question_id, question in questions.items():
            if question_id == "threat_action":
                choice = "focus_fire"
            elif question_id == "combat_team":
                choice = next(key for key in question["criteria"] if key == "team_11")
            else:
                choice = "deploy"
            answers[question_id] = {"choice": choice, "confidence": 0.9, "probabilities": {choice: 1.0}}
        return {"answers": answers}


class BridgeTests(unittest.TestCase):
    def test_disappeared_combat_target_does_not_stop_director(self):
        client = mock.Mock()
        client.post.side_effect = [
            {"success": True},
            bridge.RimApiError('/api/v1/pawn/job: HTTP 404: Target thing not found on the worker\'s map: 53491'),
        ]
        action = {"kind": "commands", "commands": [
            {"endpoint": "/api/v1/pawn/edit/status", "body": {"pawn_id": 1, "is_drafted": True}},
            {"endpoint": "/api/v1/pawn/job", "body": {"pawn_id": 1, "job_def": "AttackMelee", "target_thing_id": 53491}},
        ]}
        result = bridge.apply_action(client, action)
        self.assertTrue(result["stale_target"])
        self.assertTrue(result["applied"])
        self.assertEqual(len(result["responses"]), 1)

        client.post.side_effect = bridge.RimApiError("/api/v1/pawn/job: HTTP 400: Job is not allowed")
        with self.assertRaises(bridge.RimApiError):
            bridge.apply_action(client, {"kind": "commands", "commands": [action["commands"][1]]})

    def test_food_summary_preserves_short_term_spoilage(self):
        summary = {"critical_resources": {"food_summary": {
            "food_total": 90, "meals_count": 5, "raw_food_count": 85,
            "rot_status_info": {"nutrition_rotating_soon": 12.345},
        }}}
        normalized = bridge.normalize_resource_summary(summary)
        self.assertEqual(normalized["meals"], 5)
        self.assertEqual(normalized["raw_food"], 85)
        self.assertEqual(normalized["nutrition_rotting_soon"], 12.35)

    def test_download_model_command_prefetches_without_loading_weights_or_game(self):
        with mock.patch.object(sys, "argv", ["rimworld_laya.py", "download-model"]):
            with mock.patch.object(bridge, "resolve_model_source", return_value="cached") as prefetch:
                with mock.patch.object(bridge, "load_agent", side_effect=AssertionError("should not load")):
                    with mock.patch.object(bridge, "RimApiClient", side_effect=AssertionError("should not need game")):
                        self.assertEqual(bridge.main(), 0)
        prefetch.assert_called_once_with(bridge.DEFAULT_MODEL)

    def test_first_run_downloads_root_laya_model_when_cache_is_empty(self):
        calls = []
        inner = object()
        def download(name, **kwargs):
            calls.append((name, kwargs))
            if kwargs.get("local_files_only"):
                raise OSError("cache empty")
            return "downloaded-root-model"
        fake_hub = types.SimpleNamespace(snapshot_download=download)
        fake_laya = types.SimpleNamespace(load=lambda path, device: (path, device, inner))
        with mock.patch.dict(sys.modules, {"huggingface_hub": fake_hub, "laya": fake_laya}):
            with mock.patch.object(pathlib.Path, "is_file", return_value=True):
                agent = bridge.load_agent(bridge.DEFAULT_MODEL, "cpu")
        self.assertEqual(agent.inner, ("downloaded-root-model", "cpu", inner))
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0][1]["local_files_only"])
        self.assertNotIn("local_files_only", calls[1][1])
        self.assertEqual(calls[1][1]["allow_patterns"], ["model.safetensors", "rl_agent_config.json", "encoder/*", "tokenizer/*"])

    def test_first_run_download_failure_is_actionable(self):
        def download(name, **kwargs):
            raise OSError("offline")
        with mock.patch.dict(sys.modules, {
            "huggingface_hub": types.SimpleNamespace(snapshot_download=download),
            "laya": types.SimpleNamespace(load=lambda *args, **kwargs: None),
        }):
            with self.assertRaisesRegex(RuntimeError, "Internet connection"):
                bridge.load_agent(bridge.DEFAULT_MODEL, "cpu")

    def test_single_option_is_resolved_without_calling_laya(self):
        class RecordingAgent:
            def __init__(self):
                self.calls = []

            def predict(self, state, questions):
                self.calls.append(questions)
                return {
                    "model": "fake",
                    "answers": {
                        "real_choice": {
                            "choice": "second",
                            "probabilities": {"first": 0.2, "second": 0.8},
                            "confidence": 0.6,
                        }
                    },
                }

        inner = RecordingAgent()
        agent = bridge.SafeDecisionAgent(inner)
        result = agent.predict({}, {
            "only_choice": {"type": "choice", "instructions": "No decision exists", "criteria": {"automatic": "the sole feasible option"}},
            "real_choice": {"type": "choice", "instructions": "Choose", "criteria": {"first": "A", "second": "B"}},
        })
        self.assertEqual(len(inner.calls), 1)
        self.assertEqual(set(inner.calls[0]), {"real_choice"})
        self.assertEqual(result["answers"]["only_choice"]["choice"], "automatic")
        self.assertTrue(result["answers"]["only_choice"]["resolved_without_model"])

    def test_all_single_option_questions_skip_laya_entirely(self):
        class ExplodingAgent:
            def predict(self, state, questions):
                raise AssertionError("Laya must not receive a one-option question")

        result = bridge.SafeDecisionAgent(ExplodingAgent()).predict({}, {
            "target": {"type": "choice", "instructions": "Choose", "criteria": {"42": "only valid target"}},
        })
        self.assertEqual(result["answers"]["target"]["probabilities"], {"42": 1.0})

    def snapshot(self):
        return {
            "game": {"is_paused": False},
            "map": {
                "id": 0,
                "enemies": 0,
                "growing_zones": 1,
                "plants": 10,
                "expected_yield": 50,
                "resources": {"food": 5, "meals": 1},
            },
            "colonists": [
                {
                    "id": 10,
                    "name": "Ada",
                    "health": 1.0,
                    "mood": 0.8,
                    "hunger": 0.5,
                    "rest": 0.9,
                    "joy": 0.7,
                    "bleeding_rate": 0.0,
                    "current_job": "Hauling",
                    "skills": {"Cooking": {"level": 10, "passion": 1, "disabled": False}},
                    "work_priorities": {"Cooking": {"priority": 3, "disabled": False}},
                }
            ],
            "combat": {"available": True, "colonists": [], "hostiles": []},
        }

    def test_low_confidence_becomes_noop(self):
        decision = bridge.decide(FakeAgent(confidence=0.2), self.snapshot(), 0.6)
        self.assertEqual(decision["choice"], "keep_current_plan")

    def test_post_combat_context_does_not_send_entire_crowded_map(self):
        snapshot = self.snapshot()
        snapshot["combat"]["colonists"] = [{"id": 10, "is_drafted": True, "health": 0.8}]
        snapshot["map"]["plants"] = [{"description": "x" * 10000}]
        decision = bridge.decide(FakeAgent(choice="stand_down"), snapshot, 0.0)
        self.assertEqual(decision["choice"], "stand_down")
        state = decision["raw"]["visible_state"]
        self.assertEqual(state["hostiles"], 0)
        self.assertEqual(state["drafted"], 1)
        self.assertNotIn("plants", state)
        self.assertLess(len(str(state)), 3000)
        self.assertIn("farm", state)
        self.assertIn("resources", state)

    def test_threat_without_target_ids_undrafts_instead_of_exhausting_colonists(self):
        snapshot = self.snapshot()
        snapshot["map"]["enemies"] = 2
        snapshot["combat"] = {"available": False, "colonists": [], "hostiles": []}
        decision = bridge.decide(None, snapshot, 0.6)
        self.assertEqual(decision["choice"], "prepare_undrafted")

    def test_staging_raid_keeps_both_preparation_and_combat_options(self):
        snapshot = self.snapshot()
        snapshot["map"]["enemies"] = 2
        snapshot["combat"] = {
            "available": True,
            "colonists": [{
                "id": 10, "name": "Ada", "health": 1.0, "is_dead": False,
                "is_downed": False, "is_drafted": True, "has_ranged_weapon": True,
                "distance_to_nearest_opponent": 90, "weapon_range": 30, "current_job": "Wait_Combat",
            }, {
                "id": 11, "name": "Bo", "health": 1.0, "is_dead": False,
                "is_downed": False, "is_drafted": False, "has_ranged_weapon": True,
                "distance_to_nearest_opponent": 92, "weapon_range": 30, "current_job": "Wait",
            }],
            "hostiles": [
                {"id": 99, "current_job": "GotoWander"},
                {"id": 100, "current_job": "Wait_Wander"},
            ],
            "available_weapons": [],
        }
        criteria = bridge.make_questions(snapshot)["threat_action"]["criteria"]
        self.assertTrue({"prepare_undrafted", "hold_and_observe", "preemptive_strike",
                         "advance_to_range", "hold_cover"}.issubset(criteria))
        action = bridge.plan_action(snapshot, {"choice": "prepare_undrafted"})
        self.assertEqual(action["commands"][0]["body"], {"pawn_id": 10, "is_drafted": False})

    def test_melee_contact_keeps_distant_shooter_firing(self):
        snapshot = self.snapshot()
        snapshot["map"]["enemies"] = 1
        snapshot["combat"] = {
            "available": True,
            "colonists": [
                {"id": 10, "name": "Ivy", "health": 0.8, "melee_skill": 3,
                 "has_ranged_weapon": True, "weapon_def": "Revolver",
                 "distance_to_nearest_opponent": 1,
                 "position": {"x": 10, "z": 10}},
                {"id": 11, "name": "Bo", "health": 1, "melee_skill": 2,
                 "has_ranged_weapon": True, "weapon_def": "BoltActionRifle",
                 "distance_to_nearest_opponent": 12,
                 "position": {"x": 22, "z": 10}},
            ],
            "hostiles": [{"id": 99, "name": "Raider", "health": 1,
                          "position": {"x": 11, "z": 10}}],
        }
        action = bridge.plan_action(snapshot, {"choice": "engage_melee"})
        self.assertEqual(action["kind"], "commands")
        self.assertTrue(any(command["endpoint"] == "/api/v1/pawn/job"
                            and command["body"].get("pawn_id") == 10
                            and command["body"].get("job_def") == "AttackMelee"
                            for command in action["commands"]))
        self.assertTrue(any(command["endpoint"] == "/api/v1/combat/tactic"
                            and command["body"].get("fighter_ids") == [11]
                            and command["body"].get("tactic") == "focus_fire"
                            for command in action["commands"]))

    def test_preemptive_strike_does_not_reset_same_attack_order(self):
        snapshot = self.snapshot()
        snapshot["game"]["is_paused"] = False
        snapshot["map"]["enemies"] = 1
        snapshot["combat"] = {
            "available": True,
            "colonists": [
                {"id": 10, "name": "Ada", "health": 1.0, "has_ranged_weapon": True,
                 "weapon_range": 36, "moving": 1.0, "is_drafted": True,
                 "current_job": "AttackStatic", "current_job_target_id": 99,
                 "shooting_skill": 10, "distance_to_nearest_opponent": 70, "position": {"x": 10, "z": 10}},
                {"id": 11, "name": "Bo", "health": 1.0, "has_ranged_weapon": True,
                 "weapon_range": 26, "moving": 1.0, "is_drafted": True,
                 "current_job": "AttackStatic", "current_job_target_id": 99,
                 "shooting_skill": 8, "distance_to_nearest_opponent": 72, "position": {"x": 9, "z": 10}},
            ],
            "hostiles": [{"id": 99, "name": "Raider", "health": 1.0, "position": {"x": 80, "z": 10}}],
        }
        self.assertEqual(bridge.plan_action(snapshot, {"choice": "preemptive_strike"})["kind"], "noop")

    def test_work_priority_is_whitelisted(self):
        decision = bridge.decide(FakeAgent(), self.snapshot(), 0.6)
        action = bridge.plan_action(self.snapshot(), decision)
        self.assertEqual(action["kind"], "work_priority")
        self.assertEqual(action["body"], {"id": 10, "work": "Cooking", "priority": 1})

    def test_missing_or_disabled_work_type_excludes_pawn(self):
        pawn = self.snapshot()["colonists"][0]
        self.assertIsNone(bridge.choose_worker([pawn], "Cleaning"))
        pawn["work_priorities"]["Cleaning"] = {"priority": 3, "disabled": True}
        self.assertIsNone(bridge.choose_worker([pawn], "Cleaning"))
        pawn["work_priorities"]["Cleaning"]["disabled"] = False
        self.assertEqual(bridge.choose_worker([pawn], "Cleaning")["id"], pawn["id"])

    def test_laya_combat_choice_targets_real_hostile(self):
        snapshot = self.snapshot()
        snapshot["map"]["enemies"] = 1
        snapshot["combat"] = {
            "available": True,
            "colonists": [
                {
                    "id": 10,
                    "name": "Ada",
                    "health": 1.0,
                    "is_dead": False,
                    "is_downed": False,
                    "has_ranged_weapon": True,
                    "weapon_range": 20,
                    "shooting_skill": 12,
                    "melee_skill": 3,
                    "distance_to_nearest_opponent": 8,
                    "position": {"x": 10, "z": 10},
                }
            ],
            "hostiles": [
                {"id": 99, "name": "Raider", "health": 1.0, "is_dead": False, "is_downed": False, "position": {"x": 18, "z": 10}}
            ],
        }
        decision = bridge.decide(FakeAgent(choice="focus_fire"), snapshot, 0.0)
        action = bridge.plan_action(snapshot, decision)
        tactic = next(command["body"] for command in action["commands"] if command["endpoint"] == "/api/v1/combat/tactic")
        self.assertEqual(tactic["fighter_ids"], [10])
        self.assertEqual(tactic["target_pawn_id"], 99)

    def test_paused_threat_resumes_after_combat_order(self):
        snapshot = self.snapshot()
        snapshot["game"]["is_paused"] = True
        snapshot["map"]["enemies"] = 1
        snapshot["combat"] = {
            "available": True,
            "colonists": [{
                "id": 10, "name": "Ada", "health": 1.0, "is_dead": False,
                "is_downed": False, "has_ranged_weapon": True,
                "shooting_skill": 12, "melee_skill": 3,
                "distance_to_nearest_opponent": 30, "position": {"x": 10, "z": 10},
            }],
            "hostiles": [{
                "id": 99, "name": "Raider", "health": 1.0,
                "is_dead": False, "is_downed": False, "position": {"x": 40, "z": 10},
            }],
            "available_weapons": [],
        }
        action = bridge.plan_action(snapshot, {"choice": "engage_ranged"})
        self.assertEqual(action["commands"][-1], {
            "endpoint": "/api/v1/game/speed", "query": {"speed": 1}
        })
        self.assertEqual(action["commands"][1]["body"]["job_def"], "AttackStatic")

    def test_ranged_engagement_equips_before_attacking(self):
        snapshot = self.snapshot()
        snapshot["map"]["enemies"] = 1
        snapshot["combat"] = {
            "available": True,
            "colonists": [{
                "id": 10, "name": "Ada", "health": 1.0, "is_dead": False,
                "is_downed": False, "has_ranged_weapon": False,
                "shooting_skill": 12, "melee_skill": 3,
                "distance_to_nearest_opponent": 8, "position": {"x": 10, "z": 10},
            }],
            "hostiles": [{
                "id": 99, "name": "Raider", "health": 1.0,
                "is_dead": False, "is_downed": False, "position": {"x": 40, "z": 10},
            }],
            "available_weapons": [{
                "id": 77, "label": "rifle", "is_ranged": True,
                "is_forbidden": True, "position": {"x": 11, "z": 10},
            }],
        }
        action = bridge.plan_action(snapshot, {"choice": "engage_ranged"})
        self.assertIn("Ada -> rifle", action["description"])
        self.assertEqual(action["commands"][-1]["endpoint"], "/api/v1/pawn/job")
        self.assertEqual(action["commands"][-1]["body"]["job_def"], "Equip")

    def test_ranged_defense_uses_all_healthy_shooters(self):
        snapshot = self.snapshot()
        snapshot["map"]["enemies"] = 1
        snapshot["combat"] = {
            "available": True,
            "colonists": [
                {"id": 10, "name": "Ada", "health": 1.0, "is_dead": False, "is_downed": False,
                 "has_ranged_weapon": True, "shooting_skill": 12, "melee_skill": 3,
                 "weapon_range": 20,
                 "distance_to_nearest_opponent": 8, "position": {"x": 10, "z": 10}},
                {"id": 11, "name": "Bo", "health": 0.9, "is_dead": False, "is_downed": False,
                 "has_ranged_weapon": True, "shooting_skill": 8, "melee_skill": 5,
                 "weapon_range": 20,
                 "distance_to_nearest_opponent": 9, "position": {"x": 9, "z": 10}},
            ],
            "hostiles": [{"id": 99, "name": "Squirrel", "health": 1.0, "is_dead": False,
                          "is_downed": False, "position": {"x": 18, "z": 10}}],
            "available_weapons": [],
        }
        action = bridge.plan_action(snapshot, {"choice": "engage_ranged"})
        attack_commands = [command for command in action["commands"] if command.get("body", {}).get("job_def") == "AttackStatic"]
        self.assertEqual({command["body"]["pawn_id"] for command in attack_commands}, {10, 11})
        self.assertTrue(all(command["body"]["target_thing_id"] == 99 for command in attack_commands))

    def test_regular_attack_includes_all_available_fighters_without_a_roster_subchoice(self):
        snapshot = self.snapshot()
        snapshot["map"]["enemies"] = 1
        snapshot["combat"] = {
            "available": True,
            "colonists": [
                {"id": 10, "name": "Ada", "health": 0.9, "is_dead": False, "is_downed": False,
                 "has_ranged_weapon": True, "shooting_skill": 12, "melee_skill": 3,
                 "manipulation": 0.45, "moving": 1.0, "sight": 1.0, "pain": 0.2,
                 "health_conditions": ["MissingBodyPart:Arm"], "traits": [],
                 "distance_to_nearest_opponent": 8, "position": {"x": 10, "z": 10}},
                {"id": 11, "name": "Bo", "health": 1.0, "is_dead": False, "is_downed": False,
                 "has_ranged_weapon": True, "shooting_skill": 8, "melee_skill": 5,
                 "weapon_range": 20,
                 "manipulation": 1.0, "moving": 1.0, "sight": 1.0, "pain": 0.0,
                 "health_conditions": [], "traits": ["Tough"],
                 "distance_to_nearest_opponent": 9, "position": {"x": 9, "z": 10}},
            ],
            "hostiles": [{"id": 99, "name": "Raider", "health": 1.0, "is_dead": False,
                          "is_downed": False, "position": {"x": 18, "z": 10}, "current_job": "AttackStatic"}],
            "available_weapons": [],
        }
        agent = RosterAgent()
        decision = bridge.decide(agent, snapshot, 0.0)
        self.assertIsNone(decision["selected_fighter_ids"])
        self.assertEqual(len(agent.calls), 1)
        action = bridge.plan_action(snapshot, decision)
        attacks = [c for c in action["commands"] if c.get("body", {}).get("tactic") == "focus_fire"]
        self.assertEqual(attacks[0]["body"]["fighter_ids"], [11])

    def test_remote_api_is_rejected(self):
        with self.assertRaises(ValueError):
            bridge.RimApiClient("https://example.com:8765")


if __name__ == "__main__":
    unittest.main()

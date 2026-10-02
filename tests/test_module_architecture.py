import copy
import json
import types
import unittest
from unittest.mock import patch

import colony_modules as modules
import colony_outcomes as outcomes
import colony_reasoning as reasoning
import laya_decisions as decisions


class Tokenizer:
    def __call__(self, text, **kwargs):
        # Deterministic budget pressure. An additional real-tokenizer check is
        # recorded in the audit; normal tests need no checkpoint or torch load.
        return {"input_ids": list(range((len(text) + 2) // 3))}


class Agent:
    tok = Tokenizer()
    cfg = {"max_len": 512, "head_max_len": 192}

    def __init__(self):
        self.calls = []

    def predict(self, state, questions):
        self.calls.append((copy.deepcopy(state), copy.deepcopy(questions)))
        qid, question = next(iter(questions.items()))
        return {"answers": {qid: {"choice": next(iter(question["criteria"]))}}}


class ModuleArchitectureTests(unittest.TestCase):
    def test_benefit_cannot_evict_risk_cost_or_waiting_for_any_alternative(self):
        agent = Agent()
        choices = {f"action_{i}": "Useful progress " * 100 for i in range(9)}
        effects = {key: {"benefit": "PROGRESS " * 1000, "risk": "INJURY " * 100,
                         "cost": "MEDICINE " * 100, "inaction": "DECLINE " * 100,
                         "uncertainty": "UNVERIFIED " * 100} for key in choices}
        original = {"option_effects": effects, "decision_facts": {"downed": 2, "history": "x" * 10000}}
        before = copy.deepcopy(original)
        _, raw = decisions.ask_laya_choice(agent, original, "action", "Choose wisely", choices)
        seen = set()
        for state, _ in agent.calls:
            seen.update(state["effects"])
            self.assertLessEqual(len(agent.tok(json.dumps(state, ensure_ascii=False))["input_ids"]), 312)
            for card in state["effects"].values():
                for field, first in {"benefit": "PROGRESS", "risk": "INJURY", "cost": "MEDICINE",
                                     "inaction": "DECLINE", "uncertainty": "UNVERIFIED"}.items():
                    self.assertTrue(card[field].startswith(first), card)
        self.assertEqual(set(choices), seen)
        self.assertEqual(before, original)
        self.assertEqual(raw["visible_state"], agent.calls[-1][0])
        self.assertLessEqual(len(agent.calls), len(choices) - 1)

    def test_collection_error_removes_stale_targets_but_records_the_error(self):
        broken = types.SimpleNamespace(collect=lambda *_: {"available": False, "reason": "API unavailable"})
        snapshot = {"development": {"production": {"old_target": 99}}}
        with patch.object(modules, "modules", return_value=(broken,)):
            modules.collect(None, snapshot)
        self.assertEqual(snapshot["development"]["production"], {})
        self.assertFalse(snapshot["development"]["module_status"]["production"]["available"])
        self.assertIn("API unavailable", snapshot["warnings"][0])

    def test_last_order_survives_long_general_context_and_positive_prose(self):
        agent = Agent()
        effect = {field: "progress " * 200 for field in reasoning.FIELDS}
        state = {"decision_facts": {"history": "history " * 1000},
                 "last_outcome": "not_applied; completion unverified; previous_order",
                 "option_effects": {"a": effect, "b": effect}}
        decisions.ask_laya_choice(agent, state, "next", "Choose", {"a": "work", "b": "wait"})
        visible = agent.calls[-1][0]
        self.assertIn("not_applied", visible["last_outcome"])
        self.assertIn("unverified", visible["last_outcome"])
        self.assertLessEqual(len(agent.tok(json.dumps(visible))["input_ids"]), 312)

    def test_explicit_native_facts_are_used_by_detailed_comparison(self):
        agent = Agent()
        decisions.ask_laya_choice(agent, {"decision_facts": {"native_blocker": "missing_reactor"},
                                         "large_colony": "x" * 5000},
                                   "ship", "Choose", {"a": "start", "b": "wait"}, detailed=True)
        self.assertIn("missing_reactor", agent.calls[-1][0]["decision_facts"])

    def test_unavailable_domain_cannot_propose_stale_orders(self):
        def forbidden_prepare(*_):
            self.fail("unavailable observation reached proposal generation")
        broken = types.SimpleNamespace(prepare=forbidden_prepare)
        snapshot = {"development": {"module_status": {"production": {"available": False}}}}
        with patch.object(modules, "modules", return_value=(broken,)):
            self.assertEqual(modules.prepare(snapshot, {}), [])

    def test_modules_must_use_known_domains_and_installed_runtime_files(self):
        import install_payload
        allowed = {"strategy", "work_orders", "construction", "care", "corpse_management", "economy_diplomacy", "defense"}
        for module in modules.modules():
            self.assertIn(module.__name__ + ".py", install_payload.RUNTIME_FILES)
            self.assertTrue(set(module.DOMAINS.values()) <= allowed)

    def test_executor_cannot_misreport_arbitrary_api_payload_as_success(self):
        module = types.SimpleNamespace(execute=lambda *_: {"message": "ok"})
        with patch.object(modules, "owner", return_value=module):
            with self.assertRaises(TypeError):
                modules.execute(None, {}, {}, "production_test", {})

    def test_outcomes_do_not_invent_completion_or_cause(self):
        snapshot = {"game": {"tick": 100}, "colonists": [{"id": 1}],
                    "map": {"resources": {"meals": 0}}, "development": {}}
        memory = {}
        outcomes.record(snapshot, memory, "production_feed_batch", {"applied": True})
        self.assertEqual(outcomes.reconcile(snapshot, memory)["status"], "awaiting_game_progress")
        self.assertEqual(snapshot["development"]["outcome_feedback"]["status"], "awaiting_game_progress")
        snapshot["game"]["tick"] = 200
        feedback = outcomes.reconcile(snapshot, memory)
        self.assertEqual(feedback["status"], "no_measured_change")
        self.assertEqual(feedback["command"], "accepted")
        snapshot["map"]["resources"]["meals"] = 4
        feedback = outcomes.reconcile(snapshot, memory)
        self.assertEqual(feedback["status"], "observed_changes")
        self.assertEqual(feedback["causation"], "not_established")
        self.assertEqual(feedback["completion"], "unverified")
        self.assertEqual(feedback["changes"]["meals"], {"before": 0, "after": 4})

    def test_replay_discards_outcome_from_future_timeline(self):
        snapshot = {"game": {"tick": 100}, "development": {}}
        memory = {}
        outcomes.record(snapshot, memory, "start_ship", {"applied": True})
        snapshot["game"]["tick"] = 90
        self.assertEqual(outcomes.reconcile(snapshot, memory)["status"], "timeline_reset")
        self.assertNotIn("last_action_observation", memory)

    def test_failed_order_is_visible_in_next_same_action_comparison(self):
        snapshot = {"development": {"outcome_feedback": {
            "action": "build_power", "command": "not_applied", "status": "no_measured_change"}}}
        result = reasoning.effects("build_power", snapshot, "Build power", "construction")
        self.assertIn("not_applied", result["uncertainty"])
        self.assertIn("unverified", result["uncertainty"])


if __name__ == "__main__":
    unittest.main()

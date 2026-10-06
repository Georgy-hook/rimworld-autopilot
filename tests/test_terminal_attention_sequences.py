"""Clinical and recreation facts from the terminal colony's failure sequence."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import Mock

import colony_director as director
import colony_reasoning as reasoning
import laya_decisions as decisions


def snapshot():
    return {"game": {"tick": 2720000}, "map": {"id": 0, "resources": {
        "meals": 0, "raw_food": 14, "food": 14, "nutrition": .7}},
        "colonists": [{"id": 1, "downed": True, "hunger": 0, "bleeding_rate": 5.76,
                       "health_conditions": [{"def_name": "Malnutrition", "severity": .994}]},
                      {"id": 2, "current_job": "Harvest", "joy": .05, "mood": .15,
                       "hunger": .2, "health_conditions": []}],
        "development": {"construction_projects": [], "rooms": [], "weather": {"temperature": 31}}}


class TerminalAttentionSequences(unittest.TestCase):
    def test_nonthermal_clinical_facts_reopen_for_new_patient_and_close_on_recovery(self):
        s = snapshot()
        facts = reasoning.attention_facts(s)["care_risks"]
        self.assertNotIn("thermal", facts)
        self.assertEqual((facts["malnutrition_max"], facts["bleed_rate_max"], facts["dependent_hungry"]),
                         (.994, 5.76, 1))
        self.assertEqual(facts["recreation_deprived"], {"people": 1, "joy_min": .05, "mood_min": .15})
        s["colonists"][0].update(hunger=.8, downed=False, bleeding_rate=0, health_conditions=[])
        s["colonists"][1].update(joy=.7, mood=.7)
        self.assertNotIn("care_risks", reasoning.attention_facts(s))
        s["colonists"].append({"id": 3, "downed": True, "hunger": .02, "health_conditions": []})
        self.assertEqual(reasoning.attention_facts(s)["care_risks"]["dependent_hungry"], 1)

    def test_food_focus_retains_acute_recreation_but_no_automatic_order(self):
        s = snapshot()
        choices = ["harvest_local_plants", "schedule_recreation", "society_free_time",
                   "build_recreation_pin", "build_sculpture", "resilience_feed"]
        focused = director.focus_imminent_food_choices(s, choices)
        self.assertEqual(focused, [c for c in choices if c != "build_sculpture"])
        s["colonists"][1].update(joy=.7, mood=.7)
        self.assertEqual(director.focus_imminent_food_choices(s, choices),
                         ["harvest_local_plants", "resilience_feed"])
        s["colonists"][1].update(joy=.05, mood=.15, in_mental_state=True)
        self.assertNotIn("schedule_recreation", director.focus_imminent_food_choices(s, choices))

    def test_unknown_and_dead_needs_do_not_invent_recreation_pressure(self):
        s = snapshot()
        s["colonists"][1].pop("joy")
        self.assertIsNone(reasoning.recreation_pressure(s))
        s["colonists"][1].update(joy=.05, is_dead=True)
        self.assertIsNone(reasoning.recreation_pressure(s))
        s["colonists"][1].update(is_dead=False, joy=float("nan"))
        self.assertIsNone(reasoning.recreation_pressure(s))

    def test_wait_reports_unavailable_then_observed_worker_without_mutating_jobs(self):
        s = snapshot()
        s["colonists"][1].update(in_mental_state=True)
        self.assertEqual(reasoning.survival_wait_state(s)["unavailable"], 2)
        description = director.action_description("hold_survival", s)
        self.assertIn("2/2 people are unavailable", description)
        self.assertNotIn("already issued", description)
        client = Mock()
        before = copy.deepcopy(s)
        result = director.execute_action(client, s, {"anchor": {"x": 1, "z": 1}}, "hold_survival", {})
        self.assertFalse(result["applied"])
        self.assertEqual(result["completion"], "unverified")
        self.assertEqual(result["observed_workers"]["unavailable"], 2)
        self.assertEqual(s, before)
        client.get.assert_not_called()
        client.post.assert_not_called()
        s["colonists"][1]["in_mental_state"] = False
        self.assertEqual(reasoning.survival_wait_state(s)["jobs_observed"], 1)
        s["combat"] = {"colonists": [{"id": 2, "is_drafted": True}]}
        self.assertEqual(reasoning.survival_wait_state(s)["unavailable"], 2)

    def test_actual_tokenizer_retains_all_critical_facts_in_each_comparison(self):
        try:
            from tokenizers import Tokenizer
        except ImportError:
            self.skipTest("tokenizers unavailable")
        paths = list((Path.home() / ".cache/huggingface/hub/models--convaiinnovations--laya/snapshots").glob("*/tokenizer/tokenizer.json"))
        if not paths:
            self.skipTest("cached Laya tokenizer unavailable")
        tok = Tokenizer.from_file(str(sorted(paths)[0]))

        class Agent:
            cfg = {"max_len": 512, "head_max_len": 192}
            seen = []
            def tok(self, text, **kwargs):
                ids = tok.encode(text, add_special_tokens=False).ids
                if kwargs.get("truncation"):
                    ids = ids[:kwargs["max_length"]]
                return {"input_ids": ids}
            def predict(self, state, questions):
                self.seen.append(state)
                qid, question = next(iter(questions.items()))
                return {"answers": {qid: {"choice": next(iter(question["criteria"]))}}}

        s = snapshot()
        for include_thermal in (False, True):
            if include_thermal:
                s["colonists"][0]["health_conditions"].extend([
                    {"def_name": "Heatstroke", "severity": .62, "cur_stage_index": 4},
                    {"def_name": "Hypothermia", "severity": .37, "cur_stage_index": 3}])
            expected = reasoning.attention_facts(s, roofed_sleeping_places=0)["care_risks"]
            state = {"decision_facts": {"care_risks": expected, "unrelated": "huge " * 1000}}
            options = {"harvest_local_plants": "Harvest", "schedule_recreation": "Recreation",
                       "resilience_tend": "Tend patient", "resilience_feed": "Feed patient"}
            state["option_effects"] = {key: {field: "long text " * 1000 for field in reasoning.FIELDS}
                                       for key in options}
            agent = Agent()
            agent.seen = []
            _, raw = decisions.ask_laya_choice(agent, state, "action", "Compare needs and costs", options)
            stages = [*raw["narrowing"], raw]
            self.assertEqual(len(stages), 3)
            for stage in stages:
                self.assertEqual(stage["visible_state"]["facts"]["care_risks"], expected)
                self.assertLessEqual(stage["prompt_budget"]["state_tokens"], 312)
            self.assertEqual(agent.seen, [stage["visible_state"] for stage in stages])


if __name__ == "__main__":
    unittest.main()

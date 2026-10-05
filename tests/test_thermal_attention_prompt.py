import json
import unittest
from pathlib import Path

import colony_director as director
import colony_reasoning as reasoning
import laya_decisions as decisions


def snapshot():
    return {"map": {"enemies": 0, "resources": {"meals": 17}},
            "colonists": [{"hunger": .21, "bleeding_rate": 1.7,
                           "health_conditions": [{"def_name": "Hypothermia", "severity": .37,
                                                  "cur_stage_index": 3}]}],
            "development": {"weather": {"temperature": -8}, "rooms": []}}


class ThermalAttentionPromptTests(unittest.TestCase):
    def test_native_facts_remain_bounded_and_room_unverified(self):
        s = snapshot()
        s["colonists"] *= 100
        facts = reasoning.attention_facts(s, roofed_sleeping_places=0)["care_risks"]
        self.assertEqual(facts["thermal"], {"Hypothermia": {"severity": .37, "stage": 3, "life_threatening": False}})
        self.assertEqual(facts["roofed_bed_room_c"], "unverified")
        self.assertEqual(facts["bleed_rate_max"], 1.7)
        self.assertLess(len(json.dumps(facts)), 450)

    def test_native_roof_and_heat_evidence_do_not_claim_completed_shelter(self):
        s = snapshot()
        s["colonists"][0]["health_conditions"][0].update(def_name="Heatstroke", cur_stage_index=4, life_threatening=True)
        s["development"]["rooms"] = [{"temperature": 21, "open_roof_count": 5, "contained_beds_ids": [1]},
                                           {"temperature": 39, "open_roof_count": 0, "contained_beds_ids": [2]}]
        facts = reasoning.attention_facts(s, roofed_sleeping_places=1)["care_risks"]
        self.assertEqual(facts["roofed_bed_room_c"], [39, 39])
        self.assertTrue(facts["thermal"]["Heatstroke"]["life_threatening"])
        for key in ("is_dead", "dead"):
            s["colonists"][0][key] = True
            self.assertNotIn("care_risks", reasoning.attention_facts(s))
            s["colonists"][0].pop(key)

    def test_actual_cached_tokenizer_fit_and_multiple_choice_prompt(self):
        try:
            from tokenizers import Tokenizer
        except ImportError:
            self.skipTest("tokenizers unavailable")
        paths = list((Path.home() / ".cache/huggingface/hub/models--convaiinnovations--laya/snapshots").glob("*/tokenizer/tokenizer.json"))
        if not paths:
            self.skipTest("cached Laya tokenizer unavailable")
        native_tokenizer = Tokenizer.from_file(str(sorted(paths)[0]))

        class Agent:
            cfg = {"max_len": 512, "head_max_len": 192}
            seen = []
            def tok(self, text, **kwargs):
                ids = native_tokenizer.encode(text, add_special_tokens=False).ids
                if kwargs.get("truncation"):
                    ids = ids[:kwargs["max_length"]]
                return {"input_ids": ids}
            def predict(self, state, questions):
                self.seen.append(state)
                key, question = next(iter(questions.items()))
                return {"answers": {key: {"choice": next(iter(question["criteria"]))}}}

        agent = Agent()
        fitted = director.fit_model_context(agent, {"needs": {"patients": []}, "risks": ["verbose " * 100],
            "stock": {}, "course": {}, "guidance": "explanation " * 100, "recent": []})
        snap = snapshot()
        snap["map"]["enemies"] = 2
        snap["development"]["fire_situation"] = {"fires": [
            {"in_home": True}, {"in_home": True}, {"in_home": False}]}
        snap["colonists"][0]["health_conditions"].append(
            {"def_name": "Heatstroke", "severity": .62, "cur_stage_index": 4, "life_threatening": True})
        fitted["decision_facts"] = reasoning.attention_facts(snap, roofed_sleeping_places=0)
        fitted["decision_facts"]["module_signals"] = {"unrelated": "huge " * 1000}
        options = {"build_starter_base": "Warm shelter", "resilience_rest": "Patient rest",
                   "resilience_tend": "Treat bleeding", "eat_available_meal": "Eat meal"}
        fitted["option_effects"] = {key: {field: "long explanation " * 1000
            for field in ("benefit", "risk", "cost", "inaction", "uncertainty")} for key in options}
        _, raw = decisions.ask_laya_choice(agent, fitted, "action", "Compare care and shelter", options)
        visible = raw["visible_state"]
        facts = visible["facts"]["care_risks"]
        self.assertEqual(facts["thermal"]["Hypothermia"]["stage"], 3)
        self.assertEqual((facts["meals"], facts["least_food_level"], facts["bleed_rate_max"]), (17, .21, 1.7))
        self.assertEqual((facts["outside_c"], facts["roofed_sleepers"], facts["roofed_bed_room_c"]), (-8, 0, "unverified"))
        self.assertLessEqual(raw["prompt_budget"]["state_tokens"], 312)
        self.assertEqual((facts["threats"], facts["home_fires"]), (2, 2))
        stages = [*raw["narrowing"], raw]
        self.assertEqual(len(stages), 3)
        offered = set()
        for stage in stages:
            visible_stage = stage["visible_state"]
            evidence = visible_stage["facts"]["care_risks"]
            self.assertEqual(evidence, facts)
            self.assertLessEqual(stage["prompt_budget"]["state_tokens"], 312)
            offered.update(stage["question"]["criteria"])
        self.assertEqual(offered, set(options))
        self.assertEqual([stage["visible_state"] for stage in stages], agent.seen)

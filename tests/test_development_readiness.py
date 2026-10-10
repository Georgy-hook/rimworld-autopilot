"""Regressions from the October colony audits, using native-shaped records."""
import json
from pathlib import Path
import unittest

import colony_director as director
import colony_growth as growth
import colony_reasoning as reasoning
import laya_decisions as decisions


def prepared_colony():
    return {"game": {"tick": 20000}, "map": {"id": 0, "enemies": 0,
        "resources": {"food": 20, "meals": 20, "raw_food": 0, "nutrition": 18}},
        "colonists": [{"id": 1, "name": "Builder", "health": 1, "hunger": .9, "rest": .9,
                       "skills": {"Construction": {"level": 7}, "Intellectual": {"level": 0}},
                       "work_priorities": {"Construction": {"priority": 2},
                                           "Research": {"priority": 0}}}],
        "combat": {"colonists": [{"id": 1, "can_fight": True, "has_ranged_weapon": True}],
                   "hostiles": [], "prisoners": []},
        "animals": [], "wild_animals": [],
        "development": {"buildings": [{"id": 20, "def": "SleepingSpot", "position": {"x": 11, "z": 11}}],
                        "rooms": [{"id": 1, "contained_beds_ids": [20], "open_roof_count": 0,
                                   "touches_map_edge": False, "temperature": 22,
                                   "cells": [{"x": x, "z": z} for x in range(10, 14) for z in range(10, 14)]}],
                        "building_counts": {"SleepingSpot": 1}, "item_counts": {"WoodLog": 200, "Steel": 200},
                        "construction_projects": [], "zones": [], "plants": [], "forbidden": [],
                        "building_catalog": [{"def_name": "SimpleResearchBench", "available_now": True,
                            "designation_category": "Production", "cost_list": [{"thing_def": "Steel", "count": 25}],
                            "cost_stuff_count": 75, "allowed_stuff_defs": ["WoodLog", "Steel"],
                            "size_x": 3, "size_z": 2, "is_work_table": False}]}}


class DevelopmentReadinessTests(unittest.TestCase):
    def test_blocked_research_project_can_enter_the_action_comparison(self):
        snapshot = prepared_colony()
        snapshot["development"]["construction_projects"] = [{
            "thing_id": 77, "def_name": "SimpleResearchBench", "stuff_def_name": "Silver",
            "position": {"x": 15, "z": 15}, "rotation": 0,
            "materials_needed": [{"def_name": "Silver", "required_count": 75}],
        }]
        actions, details = director.candidate_actions(None, snapshot,
            {"anchor": {"x": 11, "z": 11}, "issued": {}})
        self.assertIn("repair_research_bench", actions)
        self.assertIn("77|WoodLog", details["research_bench_repair_options"])
        # The real comparison asks for this description before model inference.
        # A missing entry used to crash the director and leave the observer paused.
        self.assertTrue(director.action_description("repair_research_bench", snapshot))
        for language in ("ru", "en"):
            self.assertNotEqual("repair_research_bench",
                director.action_label("repair_research_bench", snapshot, language))

    def test_roofed_spots_expose_research_prison_and_cover_before_a_raid(self):
        snapshot = prepared_colony()
        actions, _ = director.candidate_actions(None, snapshot, {"anchor": {"x": 11, "z": 11}, "issued": {}})
        for action in ("build_prison", "build_research_bench", "build_fallback_defense", "build_basic_beds"):
            self.assertIn(action, actions)
        self.assertNotIn("prioritize_construction", actions)
        self.assertEqual(snapshot["development"]["population_growth_context"]["roofed_sleepers"], 1)

    def test_low_native_nutrition_cannot_be_overruled_by_meal_item_count(self):
        snapshot = prepared_colony()
        snapshot["map"]["resources"].update(meals=100, food=100, nutrition=.5)
        actions, _ = director.candidate_actions(None, snapshot, {"anchor": {"x": 11, "z": 11}, "issued": {}})
        self.assertNotIn("build_prison", actions)

    def test_pending_project_can_restore_construction_staffing(self):
        snapshot = prepared_colony()
        snapshot["development"]["construction_projects"] = [{"id": 77, "def_name": "Wall"}]
        actions, _ = director.candidate_actions(None, snapshot, {"anchor": {"x": 11, "z": 11}, "issued": {}})
        self.assertIn("prioritize_construction", actions)

    def test_shared_human_bed_has_two_places_but_prison_and_animal_beds_do_not(self):
        snapshot = prepared_colony()
        snapshot["colonists"].append({"id": 2})
        dev = snapshot["development"]
        dev["buildings"][0]["def"] = "DoubleBed"
        dev["buildings"] += [{"id": 21, "def": "RoyalBed", "for_prisoners": True},
                             {"id": 22, "def": "AnimalBed"}]
        dev["rooms"][0]["contained_beds_ids"] += [21, 22]
        self.assertEqual((2, 2), director.sleeping_place_counts(dev, {"x": 11, "z": 11}))
        self.assertEqual(["build_research_bench", "hold_survival"],
                         director.defer_discretionary_work_until_shelter(snapshot, {},
                             ["build_research_bench", "hold_survival"]))

    def test_live_predator_does_not_get_filtered_out_of_emergency_defense(self):
        snapshot = prepared_colony()
        snapshot["development"]["rooms"][0]["open_roof_count"] = 1
        snapshot["combat"]["hostiles"] = [{"id": 90, "is_animal": True}]
        result = director.defer_discretionary_work_until_shelter(snapshot, {},
            ["build_starter_base", "build_fallback_defense", "build_prison"])
        self.assertEqual(result, ["build_starter_base", "build_fallback_defense"])

    def test_novice_researcher_is_distinct_from_incapable_and_unknown(self):
        snapshot = prepared_colony()
        worker = snapshot["colonists"][0]
        context = growth.workforce_context(snapshot)
        self.assertEqual(context["capable"]["Research"], 1)
        self.assertIn("Research", context["unassigned_roles"])
        self.assertNotIn("Research", context["missing_roles"])
        worker["work_priorities"]["Research"]["disabled"] = True
        self.assertIn("Research", growth.workforce_context(snapshot)["missing_roles"])
        del worker["work_priorities"]["Research"]
        del worker["skills"]["Intellectual"]
        context = growth.workforce_context(snapshot)
        self.assertIsNone(context["capable"]["Research"])
        self.assertNotIn("Research", context["missing_roles"])

    def test_quest_wrapper_and_history_are_not_counted_as_live_opportunities(self):
        snapshot = prepared_colony()
        snapshot["development"]["quests"] = {"active_quests": [
            {"id": 1, "state": "Ongoing"},
            {"id": 2, "state": "NotYetAccepted", "increases_population": True, "can_accept": True},
            {"id": 3, "state": "EndedOfferExpired", "increases_population": True, "can_accept": False}],
            "historical_quests": [{"id": 4, "state": "EndedSuccess"}]}
        self.assertEqual(growth.population_context(snapshot)["live_signals"]["active_quests"], 2)
        self.assertEqual(growth.development_briefing(snapshot)["recruit_offers"], 1)

    def test_incomplete_combat_observation_does_not_claim_unarmed_workers(self):
        snapshot = prepared_colony()
        snapshot["combat"]["colonists"] = [{"id": 1}]
        self.assertNotIn("ranged_fighters", growth.development_briefing(snapshot))
        snapshot["combat"]["colonists"] = []
        self.assertNotIn("ranged_fighters", growth.development_briefing(snapshot))

    def test_bedbound_researcher_is_temporarily_unavailable_not_incapable(self):
        snapshot = prepared_colony()
        snapshot["colonists"][0]["downed"] = True
        briefing = growth.development_briefing(snapshot)
        self.assertIn("Research", briefing["unavailable_roles"])
        self.assertNotIn("Research", briefing.get("missing_roles", []))

    def test_root_comparison_retains_development_and_starvation_with_real_tokenizer(self):
        from tokenizers import Tokenizer
        paths = list((Path.home() / '.cache/huggingface/hub/models--convaiinnovations--laya/snapshots').glob('*/tokenizer/tokenizer.json'))
        if not paths:
            self.skipTest('cached Laya tokenizer unavailable')
        tokenizer = Tokenizer.from_file(str(paths[0]))
        class Agent:
            cfg = {"max_len": 512, "head_max_len": 192}
            def tok(self, text, **kwargs):
                return {"input_ids": tokenizer.encode(text, add_special_tokens=False).ids}
        snapshot = prepared_colony()
        snapshot["map"]["resources"].update(nutrition=0, meals=0, food=0)
        snapshot["colonists"][0]["work_priorities"]["Research"]["disabled"] = True
        facts = reasoning.attention_facts(snapshot, roofed_sleeping_places=1)
        agent = Agent()
        options = {"build_fallback_defense": "Prepare cover", "harvest_local_plants": "Gather food"}
        visible = decisions._consequence_state(agent, {"decision_facts": facts,
            "option_effects": {k: {field: "ordinary consequence " * 50 for field in
                ("benefit", "risk", "cost", "inaction", "uncertainty")} for k in options}}, options)
        self.assertEqual(visible["facts"]["development"], facts["development"])
        self.assertEqual(visible["facts"]["care_risks"]["food_days"], 0)
        self.assertLessEqual(len(agent.tok(json.dumps(visible))["input_ids"]), 312)


if __name__ == '__main__':
    unittest.main()

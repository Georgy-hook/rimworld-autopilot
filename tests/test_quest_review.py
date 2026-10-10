import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import colony_director as director
import colony_events as events
import colony_progression as progression
import colony_affordances as affordances
import colony_quests as quests


def snapshot():
    return {"map": {"id": 0, "enemies": 0, "resources": {"food": 0, "meals": 0, "medicine": 0}},
            "game": {"tick": 500}, "development": {},
            "colonists": [{"id": 1, "name": "Patient", "downed": True,
                "hunger": 0, "bleeding_rate": 3.65, "current_job": "LayDown"}]}


def offer():
    return {"id": 4, "quest_def": "Intro_Deserter", "name": "The Deserter",
            "description": "A deserter wishes to join. There is a psychic reward at an outpost. "
                "If accepted, the Empire becomes hostile and a pursuing loyalty squad will attack immediately.",
            "state": "NotYetAccepted", "ever_accepted": False, "can_accept": True,
            "offer_version": "observed-terms", "expiry_hours": 23, "requires_accepter": False,
            "reward_groups": [{"part_index": 3, "choice_used": False, "choices": [
                {"choice_index": 0, "rewards": ["Deserter joins"], "population_reward_possible": True}]}],
            "acceptance_diplomacy": [{"faction_def": "Empire", "goodwill_change": -100, "makes_hostile": True}]}


class QuestReviewTests(unittest.TestCase):
    def agent(self, select=None):
        from tokenizers import Tokenizer
        paths = list((Path.home() / '.cache/huggingface/hub/models--convaiinnovations--laya/snapshots').glob('*/tokenizer/tokenizer.json'))
        if not paths:
            self.skipTest("cached Laya tokenizer unavailable")
        tokenizer = Tokenizer.from_file(str(paths[0]))
        class Agent:
            cfg = {"max_len": 512, "head_max_len": 192}
            def __init__(self): self.seen = []
            def tok(self, text, **kwargs): return {"input_ids": tokenizer.encode(text, add_special_tokens=False).ids}
            def predict(self, state, questions):
                self.seen.append(state)
                key, q = next(iter(questions.items()))
                choice = select(state, q) if select else next(iter(q["criteria"]))
                return {"answers": {key: {"choice": choice}}}
        return Agent()

    def test_late_diplomacy_and_raid_reach_actual_predict_next_to_patient(self):
        source = offer()
        source["description"] = "reward narrative " * 240 + source["description"]
        agent = self.agent(lambda state, q: "defer" if "attack immediately" in json.dumps(state) else "accept")
        chosen, raw, plan = quests.review(agent, source, snapshot(), {"doctrine": {"endgame": "imperial_ascension"}})
        self.assertEqual(chosen, "defer")
        self.assertIsNone(plan)
        self.assertTrue(raw["all_terms_seen"])
        text = quests.reconstruct_field(agent.seen, "description")
        self.assertEqual(text, source["description"])
        for row in agent.seen:
            self.assertEqual(row["colony"]["downed"], 1)
            self.assertEqual(row["colony"]["bleeding"], 3.65)
            self.assertEqual(row["colony"]["mobile"], 0)
            self.assertEqual(row["colony"]["food"], 0)
            self.assertEqual(row["ending"], "imperial_ascension")
            self.assertLessEqual(len(agent.tok(json.dumps(row, ensure_ascii=False))["input_ids"]), 312)

    def test_all_disclosed_fields_survive_pagination_including_modded_offer(self):
        source = offer()
        source.update(quest_def="UnknownMod_LongQuest", name="имя " * 200,
            description="日本語 описание " * 400 + "late diplomatic cost", requirements=["requirement " * 150],
            look_targets=[{"tile": 4321, "estimated_threat_points": 12000}],
            disclosure="hidden outcomes unknown")
        agent = self.agent()
        fields = quests.offer_fields(source, snapshot(), {"endgame": "archonexus"})
        pages = quests.review_pages(agent, source, snapshot(), {"endgame": "archonexus"})
        for field, value in fields:
            self.assertEqual(quests.reconstruct_field(pages, field), quests.public_text(value))
        self.assertTrue(all(quests._size(agent, page) <= 312 for page in pages))

    def test_reward_and_accepter_are_exact_model_choices_not_first_defaults(self):
        source = offer()
        source["requires_accepter"] = True
        source["eligible_accepters"] = [{"pawn_id": 7, "social": 0}, {"pawn_id": 9, "social": 15}]
        source["reward_groups"][0]["choices"].append({"choice_index": 1, "rewards": ["Medicine x30"]})
        def select(state, q):
            return list(q["criteria"])[1] if state.get("field") in {"reward_alternatives", "accepters"} else "accept"
        chosen, raw, plan = quests.review(self.agent(select), source, snapshot())
        self.assertEqual(chosen, "accept")
        self.assertEqual(plan["accepter_pawn_id"], 9)
        self.assertEqual(plan["reward_choices"], [{"part_index": 3, "choice_index": 1}])
        client = Mock()
        client.get.return_value = source
        client.post.return_value = {"success": True}
        result = quests.accept_reviewed(client, plan, snapshot())
        self.assertTrue(result["applied"])
        self.assertNotIn("victory_verified", result)
        self.assertEqual(client.post.call_args.kwargs["body"]["reward_choices"], plan["reward_choices"])

    def test_changed_terms_expiry_or_clinical_state_prevents_any_accept_post(self):
        source = offer()
        _, _, plan = quests.review(self.agent(), source, snapshot())
        for mutation in ("version", "expiry", "patient", "unreviewed"):
            client = Mock()
            fresh, current = copy.deepcopy(source), snapshot()
            current_plan = plan
            if mutation == "version": fresh["offer_version"] = "different reward"
            if mutation == "expiry": fresh["can_accept"] = False
            if mutation == "patient": current["colonists"][0]["bleeding_rate"] = 4.2
            if mutation == "unreviewed": current_plan = None
            client.get.return_value = fresh
            self.assertFalse(quests.accept_reviewed(client, current_plan, current)["applied"], mutation)
            client.post.assert_not_called()

    def test_absent_observations_remain_unknown(self):
        facts = quests.colony_facts({})
        for key in ("alive", "mobile", "downed", "bleeding", "defenders", "food", "meals", "medicine"):
            self.assertIsNone(facts[key])

    def test_replaced_resident_invalidates_review_even_with_unchanged_counts(self):
        _, _, plan = quests.review(self.agent(), offer(), snapshot())
        current = snapshot()
        current["colonists"][0]["id"] = 999
        self.assertEqual(quests.colony_facts(current), plan["reviewed_colony"])
        client = Mock()
        self.assertFalse(quests.accept_reviewed(client, plan, current)["applied"])
        client.post.assert_not_called()

    def test_late_letter_warning_cannot_be_outvoted_by_reward_pages(self):
        agent = self.agent(lambda state, q: "option_1" if "attacks immediately" in json.dumps(state) else "option_0")
        text = "valuable reward " * 400 + "Accepting makes the Empire hostile and it attacks immediately."
        selected, raw = quests.choose_letter(agent, {"id": 20, "text": text}, snapshot(), {},
            {"option_0": "Accept", "option_1": "Reject", "defer": "Wait"}, {"endgame": "imperial_ascension"})
        self.assertEqual(selected, "defer")
        self.assertGreater(raw["page_count"], 2)
        self.assertEqual(''.join(p['text'] for p in agent.seen), quests.public_text({
            "full_offer": text, "labor": {}, "responses": {"option_0": "Accept", "option_1": "Reject", "defer": "Wait"}}))
        self.assertTrue(all(p["ending"] == "imperial_ascension" for p in agent.seen))

    def test_ordinary_consumption_drift_does_not_create_acceptance_retry_loop(self):
        source = snapshot()
        source["map"]["resources"].update(food=100, meals=70, medicine=20)
        before = quests.colony_facts(source)
        source["map"]["resources"].update(food=99, meals=69, medicine=19)
        source["colonists"][0]["bleeding_rate"] = 2.2
        self.assertFalse(quests.readiness_changed(before, quests.colony_facts(source)))
        source["map"]["resources"]["food"] = 0
        self.assertTrue(quests.readiness_changed(before, quests.colony_facts(source)))

    def test_offer_countdown_does_not_change_loop_memory_identity(self):
        first = {"kind": "accept", "quest_offer": {**offer(), "expiry_hours": 20}, "quest_id": 4}
        later = {**first, "quest_offer": {**offer(), "expiry_hours": 19}}
        self.assertEqual(progression._transition_row(first), progression._transition_row(later))

    def test_native_interaction_stage_prompts_keep_zero_food_and_blood_loss(self):
        source = snapshot()
        row = {"key": "study", "kind": "menu", "pawn_id": 1, "target_id": 19,
               "label": "Investigate fallen monolith", "description": "Study the monolith.", "pawn": {}}
        source["development"]["affordances"] = {"options": [row]}
        affordances.prepare(source, {})
        agent = self.agent()
        affordances.choose(agent, {"endgame": "anomaly_void"}, "affordances_interaction", source)
        for seen in agent.seen:
            self.assertEqual(seen["facts"]["quest_colony"]["food"], 0)
            self.assertEqual(seen["facts"]["quest_colony"]["bleeding"], 3.65)
            self.assertEqual(seen["facts"]["quest_colony"]["ending"], "anomaly_void")
            self.assertLessEqual(quests._size(agent, seen), 312)

    def test_temporary_mobile_guest_is_exposed_as_unable_to_do_colony_work(self):
        source = snapshot()
        source["colonists"][0].update(downed=False, work_priorities={"Doctor": {"disabled": True}, "Hauling": {"disabled": True}})
        people = dict(quests.offer_fields(offer(), source, {}))["patients_and_work"]
        self.assertTrue(people[0]["work"]["Doctor"])
        self.assertTrue(people[0]["work"]["Hauling"])

    def test_combined_critical_conditions_fit_native_job_keys_without_losing_danger(self):
        import colony_reasoning as reasoning
        from laya_decisions import ask_laya_choice
        source = snapshot()
        source["colonists"][0]["health_conditions"] = [
            {"def_name": name, "severity": .75, "cur_stage_index": stage, "life_threatening": True}
            for name, stage in (("Hypothermia", 4), ("Heatstroke", 3), ("Malnutrition", 4))]
        source["colonists"] = [{**source["colonists"][0], "id": i + 1} for i in range(3)]
        choices = {"job_0_20952_22921_Investigate fallen monolith": "Investigate the monolith", "defer": "Keep caring for patients"}
        agent = self.agent()
        ask_laya_choice(agent, {"decision_facts": {
            "care_risks": reasoning.attention_facts(source).get("care_risks"),
            "quest_colony": {**quests.colony_facts(source), "ending": "anomaly_void"}},
            "option_effects": {key: {"benefit": label, "risk": "Interrupt urgent care", "cost": "Worker time", "inaction": "Delay", "uncertainty": "Unverified"}
                               for key, label in choices.items()}}, "ending_job", "Compare care and investigation", choices)
        for seen in agent.seen:
            self.assertLessEqual(quests._size(agent, seen), 312)
            self.assertEqual(seen["facts"]["quest_colony"]["food"], 0)
            self.assertEqual(seen["facts"]["quest_colony"]["bleeding"], 10.95)
            self.assertEqual(seen["facts"]["care_risks"]["bleed_rate_max"], 3.65)
            thermal = json.dumps(seen["facts"]["care_risks"]["thermal"])
            for name in ("Hypothermia", "Heatstroke", "life_threatening", "stage", "0.75"):
                self.assertIn(name, thermal)

    def test_runtime_history_is_not_serialized_as_doctrine(self):
        fields = dict(quests.offer_fields(offer(), snapshot(), {"doctrine": {"endgame": "royal_ascent"},
                         "issued": {str(i): i for i in range(10000)}}))
        self.assertEqual(fields["strategy"], {"doctrine": {"endgame": "royal_ascent"}})

    def test_expired_accepted_and_unsupported_quests_offer_no_accept_option(self):
        for changes in ({"can_accept": False}, {"state": "EndedSuccess"}, {"ever_accepted": True},
                        {"quest_def": "Decree_BuildMonument"}):
            source = {**offer(), **changes, "family": "quest"}
            self.assertNotIn("accept_quest", events.response_options(source, {}))

    def test_quest_letter_cannot_bypass_event_review(self):
        client = Mock()
        context = {"letters": [{"id": 10, "quest_id": 4, "text": "quest", "enabled_options": ["Accept"], "arrival_tick": 1}],
                   "active_quests": [offer()]}
        with tempfile.TemporaryDirectory() as folder, patch.object(director.bridge, "safe_get", return_value=context):
            self.assertIsNone(director.run_letter_cycle(client, self.agent(), snapshot(), {}, Path(folder)/"log.jsonl"))
        client.post.assert_not_called()

    def test_ending_offer_countdown_drift_is_tolerated_but_changed_terms_are_not(self):
        before = {"kind": "accept", "quest_offer": {**offer(), "expiry_hours": 20}}
        after = {"kind": "accept", "quest_offer": {**offer(), "expiry_hours": 19}}
        self.assertTrue(progression._ending_unchanged(before, after))
        after["quest_offer"]["offer_version"] = "different diplomatic price"
        self.assertFalse(progression._ending_unchanged(before, after))

    def test_same_unverified_investigation_cannot_restart_with_another_worker(self):
        row = {"key": "first", "kind": "menu", "pawn_id": 1, "target_id": 19,
               "label": "Investigate fallen monolith", "risk": "study", "cost": "labor", "pawn": {}}
        source = {**snapshot(), "game": {"tick": 100}, "development": {"affordances": {"options": [row]}}}
        client = Mock()
        client.get.return_value = {"options": [row]}
        client.post.return_value = {"applied": True, "completion": "unverified"}
        memory = {}
        with patch('colony_retry.time.time', return_value=1000):
            self.assertTrue(affordances.execute(client, source, memory, "affordances_interaction", row)["applied"])
        other = {**row, "key": "second", "pawn_id": 2}
        source["game"]["tick"] = 60100
        source["development"]["affordances"]["options"] = [other]
        with patch('colony_retry.time.time', return_value=1006):
            self.assertNotIn("affordances_interaction", affordances.prepare(source, memory))
            self.assertFalse(affordances.execute(client, source, memory, "affordances_interaction", other)["applied"])
            site = {"map_id": 0, "thing_id": 19, "pawn_id": 2, "label": row["label"], "kind": "job"}
            context = {"endings": {"site_jobs": [site]}, "_interaction_pending": memory["interaction_pending"], "_game_tick": 60100}
            self.assertFalse(progression.ending_options(context))
        self.assertEqual(client.post.call_count, 1)
        # A genuinely new native effect is reachable during the pending period.
        source["development"]["affordances"]["options"] = [{**other, "label": "Activate monolith"}]
        with patch('colony_retry.time.time', return_value=1006):
            self.assertIn("affordances_interaction", affordances.prepare(source, memory))


if __name__ == '__main__': unittest.main()

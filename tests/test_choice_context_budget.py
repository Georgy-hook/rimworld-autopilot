"""Full clinical observations must fit or defer locally, never stop the director."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import colony_director as director
import laya_decisions as decisions


FIELDS = ('benefit', 'risk', 'cost', 'inaction', 'uncertainty')


def care_facts():
    # Synthetic shape of the observed live-threat care overflow. Include every
    # simultaneous need: heat, patient and animal blood, food, and recreation.
    return {'care_risks': {
        'thermal': {'Hypothermia': {'severity': .862, 'stage': 4, 'life_threatening': True}},
        'outside_c': -19.362, 'roofed_sleepers': None,
        'roofed_bed_room_c': [-17.442, -16.08], 'meals': 1,
        'least_food_level': 0., 'bleed_rate_max': 1.37, 'downed': 1,
        'threats': 1, 'food_days': .3, 'stored_nutrition': .8,
        'animal_bleed_max': .561, 'downed_animals': 0,
        'malnutrition_max': .682, 'dependent_hungry': 1,
        'recreation_deprived': {'people': 1, 'joy_min': .112, 'mood_min': .073},
        'home_fires': 0}}


class BudgetAgent:
    cfg = {'max_len': 512, 'head_max_len': 192}

    def __init__(self, tokenizer):
        self.tokenizer = tokenizer
        self.calls = []

    def tok(self, text, **kwargs):
        ids = self.tokenizer.encode(text, add_special_tokens=False).ids
        return {'input_ids': ids[:kwargs.get('max_length', len(ids))]}

    def predict(self, state, questions):
        self.calls.append((copy.deepcopy(state), copy.deepcopy(questions)))
        qid, question = next(iter(questions.items()))
        key = next(iter(question['criteria']))
        return {'answers': {qid: {'choice': key}}}


class ChoiceContextBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tokenizers import Tokenizer
        paths = list((Path.home()/'.cache/huggingface/hub/models--convaiinnovations--laya/snapshots').glob('*/tokenizer/tokenizer.json'))
        if not paths:
            raise unittest.SkipTest('cached actual tokenizer unavailable')
        cls.tokenizer = Tokenizer.from_file(str(paths[0]))

    def agent(self):
        return BudgetAgent(self.tokenizer)

    def test_live_threat_care_preserves_every_fact_and_both_options(self):
        options = {'tend_610_42015': 'Treat patient', 'self_tend_42015': 'Treat caregiver'}
        state = {'decision_facts': care_facts(), 'option_effects': {
            key: {'benefit': 'Treat current wounds and reduce bleeding',
                  'risk': 'Tending does not remove cold exposure; preserve urgent bleeding/infection care.',
                  'cost': 'Uses the selected caregiver; compare available warmth work.',
                  'inaction': 'Untreated blood loss and hypothermia can kill',
                  'uncertainty': 'Native route and reservation are rechecked at execution.'}
            for key in options}}
        before = copy.deepcopy(state)
        for criteria in (options, dict(reversed(list(options.items())))):
            agent = self.agent()
            _, raw = decisions.ask_laya_choice(agent, state, 'care_action', 'Compare current care.', criteria)
            visible = raw['visible_state']
            self.assertEqual(visible['facts']['care_risks'], state['decision_facts']['care_risks'])
            self.assertEqual(set(visible['effects']), set(criteria))
            if 'effect_fields' in visible:
                self.assertEqual(visible['effect_fields'], list(FIELDS))
                for row in visible['effects'].values():
                    self.assertEqual(len(row), len(FIELDS))
                    self.assertTrue(all(row))
            self.assertLessEqual(raw['prompt_budget']['state_tokens'], 312)
        self.assertEqual(state, before)

    def test_unrepresentable_clinical_record_is_not_silently_cut_or_inferred(self):
        agent = self.agent()
        facts = {'care_risks': {f'patient_{n}': {'bleeding': n+.25, 'immunity': .1,
                  'disease': .8, 'temperature': -30, 'in_bed': False} for n in range(50)}}
        state = {'decision_facts': facts, 'option_effects': {
            key: {field: 'Consider observed patient safety' for field in FIELDS} for key in ('tend', 'rescue')}}
        before = copy.deepcopy(state)
        with self.assertRaises(decisions.ChoiceContextOverflow) as caught:
            decisions.ask_laya_choice(agent, state, 'care_action', 'Compare', {'tend': 'Tend', 'rescue': 'Rescue'})
        self.assertEqual(caught.exception.question_id, 'care_action')
        self.assertGreater(caught.exception.minimum_tokens, caught.exception.budget)
        self.assertEqual(caught.exception.options, ['tend', 'rescue'])
        self.assertEqual(agent.calls, [])
        self.assertEqual(state, before)

    def test_narrowing_overflow_records_exact_comparison_stage(self):
        agent = self.agent()
        state = {'decision_facts': {'care_risks': {'observation': 'nontruncatable clinical value '*500}},
                 'option_effects': {key: {field: 'Observe' for field in FIELDS} for key in ('a','b','c')}}
        with self.assertRaises(decisions.ChoiceContextOverflow) as caught:
            decisions.ask_laya_choice(agent, state, 'care', 'Compare', {'a':'Tend','b':'Rescue','c':'Feed'})
        self.assertEqual(caught.exception.question_id, 'care_round_0_0')
        self.assertEqual(caught.exception.options, ['a','b'])
        self.assertEqual(agent.calls, [])

    def test_oversized_plan_is_an_explicit_unavailable_choice(self):
        agent = self.agent()
        with self.assertRaises(decisions.ChoiceContextOverflow) as caught:
            decisions.ask_laya_choice(agent, {'planning_context': {'critical': 'full fact '*1000}},
                'colony_goal_domain', 'Compare', {'care':'Care','work':'Work'})
        self.assertEqual(caught.exception.question_id, 'colony_goal_domain')
        self.assertEqual(caught.exception.reason, 'complete_planning_context_unavailable')
        self.assertFalse(agent.calls)

    def test_independent_cycle_runs_after_unavailable_choice_without_game_orders(self):
        client = Mock()
        overflow = decisions.ChoiceContextOverflow('complete_consequence_context_unavailable',312,313,{'a':'Tend','b':'Rescue'})
        overflow.question_id = 'post_combat_care_round_0_0'
        def unavailable(client, log_path):
            raise overflow
        calls = []
        def independent(client, log_path):
            calls.append('defense')
            return {'decision': {'choice': 'native_defense'}, 'result': {'applied': False}}
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder)/'log.jsonl'
            record = director.bounded_decision_cycle(unavailable)(client,log)
            next_record = director.bounded_decision_cycle(independent)(client,log)
            saved = json.loads(log.read_text(encoding='utf-8'))
        self.assertEqual(record['decision']['choice'],'defer')
        self.assertFalse(record['blocks_development'])
        self.assertFalse(record['result']['applied'])
        self.assertEqual(saved['result']['comparison']['question_id'],overflow.question_id)
        self.assertEqual(next_record['decision']['choice'],'native_defense')
        self.assertEqual(calls,['defense'])
        client.post.assert_not_called()

    def test_real_care_boundary_defers_oversized_choice(self):
        error = decisions.ChoiceContextOverflow('complete_consequence_context_unavailable',312,313,{'a':'Tend','b':'Rescue'})
        error.question_id = 'post_combat_care'
        with patch.object(director,'ask_laya_choice',side_effect=error), \
             patch.object(director,'post_combat_care_options',return_value={'a':{'kind':'tend','patient_id':2,'helper_id':1,'summary':'Tend'}}), \
             patch.object(director,'routine_care_refuel_options',return_value={}):
            snapshot={'game':{'tick':100},'map':{'id':0,'resources':{}},'colonists':[],
                      'combat':{'colonists':[],'hostiles':[]},'development':{}}
            client=Mock()
            with tempfile.TemporaryDirectory() as folder:
                record=director.run_post_combat_care_cycle(client,self.agent(),snapshot,Path(folder)/'log.jsonl')
        self.assertEqual(record['mode'],'choice-unavailable')
        self.assertFalse(record['result']['applied'])
        client.post.assert_not_called()

    def test_non_budget_errors_still_surface(self):
        def faulty(client,log_path):raise ValueError('different programming error')
        with self.assertRaisesRegex(ValueError,'different programming error'):
            director.bounded_decision_cycle(faulty)(Mock(),Path('unused'))


if __name__ == '__main__':
    unittest.main()

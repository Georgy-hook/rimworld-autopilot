import json
from pathlib import Path
import unittest
from unittest.mock import patch

import colony_director as director
import colony_reasoning as reasoning
import laya_decisions as decisions
from test_equipment_sequence import replay_snapshot


class ParameterContextTests(unittest.TestCase):
    def agent(self):
        try:
            from tokenizers import Tokenizer
        except ImportError:
            self.skipTest('tokenizers unavailable')
        paths = list((Path.home() / '.cache/huggingface/hub/models--convaiinnovations--laya/snapshots').glob('*/tokenizer/tokenizer.json'))
        if not paths:
            self.skipTest('cached Laya tokenizer unavailable')
        tokenizer = Tokenizer.from_file(str(paths[0]))

        class Agent:
            cfg = {'max_len': 512, 'head_max_len': 192}
            def __init__(self): self.seen = []
            def tok(self, text, **kwargs):
                return {'input_ids': tokenizer.encode(text, add_special_tokens=False).ids}
            def predict(self, state, questions):
                self.seen.append(state)
                key, question = next(iter(questions.items()))
                return {'answers': {key: {'choice': next(iter(question['criteria']))}}}
        return Agent()

    def snapshot(self):
        snapshot = replay_snapshot()
        snapshot['development'].update(item_counts={'Steel': 776},
            weather={'temperature': 37.576}, construction_projects=[{'def_name': 'Wall'}])
        snapshot['map']['resources']['meals'] = 38
        return snapshot

    def test_detailed_comparisons_keep_complete_small_facts_in_every_round(self):
        agent = self.agent()
        facts = reasoning.parameter_facts(self.snapshot(), 'harvest_nearby_trees', roofed_sleeping_places=0)
        options = {str(i): ('ordinary plant description ' * 1000) for i in range(4)}
        decisions.ask_laya_choice(agent, {'decision_facts': facts, 'irrelevant': 'strategy ' * 2000},
                                  'resource', 'Choose a feasible source', options, detailed=True)
        self.assertEqual(len(agent.seen), 3)
        for visible in agent.seen:
            self.assertEqual(visible['decision_facts'], facts)
            self.assertLessEqual(len(agent.tok(json.dumps(visible, ensure_ascii=False))['input_ids']), 312)
        self.assertEqual((facts['wood'], facts['steel'], facts['roofed_beds'], facts['unfinished']), (0, 776, 0, 1))

    def test_legacy_parameter_branch_receives_facts_after_root_choice(self):
        agent = self.agent()
        questions = {'refuel_target': {'instructions': 'Choose facility', 'criteria': {'1': 'stove', '2': 'cooler'}}}
        with patch.object(director, 'subchoice_questions_for_action', return_value=questions):
            decision = director.choose_action(agent, self.snapshot(), ['refuel_building'])
        steps = decision['raw']['details']['steps']
        self.assertTrue(steps)
        state = steps[-1]['visible_state']
        facts = state.get('decision_facts') or {}
        self.assertIsInstance(facts, dict)
        self.assertEqual((facts['wood'], facts['steel'], facts['unfinished']), (0, 776, 1))

    def test_absent_observation_is_unknown_not_zero_stock(self):
        facts = reasoning.parameter_facts({}, 'harvest_nearby_trees')
        self.assertIsNone(facts['wood'])
        self.assertIsNone(facts['roofed_beds'])


if __name__ == '__main__': unittest.main()

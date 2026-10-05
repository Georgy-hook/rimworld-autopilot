import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from unittest.mock import patch
import colony_director as d
import colony_capabilities as caps
from test_equipment_sequence import Chooser, Orders, replay_snapshot


class CompactResultLoggingTests(unittest.TestCase):
    def setup_choice(self):
        snapshot = replay_snapshot()
        memory = {'anchor': {'x': 120, 'z': 120}, 'growing_anchor': {'x': 90, 'z': 90},
                  'issued': {'starter_base': 1}, 'starter_site_verified': True}
        candidates, details = d.candidate_actions(None, snapshot, memory)
        decision = d.choose_action(Chooser(), snapshot, candidates)
        details['doctrine_context'] = {'all_definitions': 'D' * 800000}
        details['architecture_context'] = {'catalog': 'A' * 600000}
        return snapshot, memory, details, decision

    def test_execution_success_defer_stale_unchanged_and_state_identical(self):
        for mode in ('success', 'defer', 'stale', 'unchanged'):
            with self.subTest(mode=mode):
                snapshot, memory, details, decision = self.setup_choice()
                if mode == 'defer': decision['weapon_defer'] = True
                if mode == 'stale': decision['weapon_item'] = '9999999'
                if mode == 'unchanged':
                    pawn = next(p for p in snapshot['combat']['colonists'] if str(p['id']) == str(decision['weapon_pawn']))
                    pawn['weapon_info'] = {'id': int(decision['weapon_item'])}
                selected = d.merge_decision_details(details, decision)
                first_client, second_client = Orders(), Orders()
                first_snapshot, second_snapshot = copy.deepcopy(snapshot), copy.deepcopy(snapshot)
                first_memory, second_memory = copy.deepcopy(memory), copy.deepcopy(memory)
                raw = d.execute_action(first_client, first_snapshot, first_memory, 'equip_colonists', selected)
                raw_before = copy.deepcopy(raw); selection_before = copy.deepcopy(selected)
                compact = d.result_for_logging('equip_colonists', raw, decision)
                control = d.execute_action(second_client, second_snapshot, second_memory, 'equip_colonists', selected)
                self.assertEqual(first_client.calls, second_client.calls)
                self.assertEqual(first_memory, second_memory)
                self.assertEqual(raw, control); self.assertEqual(raw, raw_before)
                self.assertEqual(selected, selection_before)
                self.assertEqual(compact['applied'], raw['applied'])
                self.assertEqual(compact['reason'], raw['reason'])
                self.assertEqual(compact['selection']['weapon_pawn'], decision['weapon_pawn'])
                self.assertNotIn('doctrine_context', compact['selection'])
                self.assertNotIn('architecture_context', compact['selection'])
                self.assertLess(len(json.dumps(compact)), 8000)
                if mode == 'success':
                    self.assertEqual(first_client.calls[0][1]['body']['target_thing_id'], 5062)
                    self.assertEqual(first_client.calls[0][1]['body']['pawn_id'], 257)
                    self.assertTrue(compact['applied'])
                else:
                    self.assertFalse(first_client.calls); self.assertFalse(compact['applied'])

    def test_evidence_only_from_shown_final_question_not_live_or_merged_catalog(self):
        raw = {'applied': False, 'reason': 'stale', 'selection': {
            'weapon_pawn': '1', 'weapon_item': '2', 'shown_subjects': {'weapon_item': ['2', 'NEVER_SHOWN']},
            'weapon_catalog': {'NEVER_SHOWN': {'description': 'not visible'}}}}
        decision = {'raw': {'details': {'steps': [
            {'question': {'id': 'weapon_pawn', 'criteria': {'1': 'actually shown pawn'}}},
            {'question': {'id': 'weapon_item', 'criteria': {'2': 'actually shown selected weapon', '3': 'shown alternative'}}},
            {'question': {'id': 'unrelated', 'criteria': {'99': 'unrelated'}}}]}}}
        result = d.result_for_logging('equip_colonists', raw, decision)
        self.assertEqual(result['selection']['shown_subjects'], {'weapon_pawn': ['1'], 'weapon_item': ['2', '3']})
        self.assertEqual(result['selection']['shown_evidence'][1]['evidence'], 'actually shown selected weapon')
        self.assertNotIn('NEVER_SHOWN', json.dumps(result))
        self.assertNotIn('unrelated', json.dumps(result))
        self.assertEqual(result['selection']['evidence_reference'], 'decision.raw.details')
        self.assertEqual(raw['selection']['shown_subjects']['weapon_item'], ['2', 'NEVER_SHOWN'])

    def test_real_development_logging_boundary_default_and_technical_opt_in(self):
        for technical in (False, True):
            with self.subTest(technical=technical), tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
                snapshot, memory, details, decision = self.setup_choice()
                log = Path(folder) / 'decisions.jsonl'
                client = Orders(); observed = []
                real_execute = d.execute_action
                def capture_execute(*args):
                    result = real_execute(*args); observed.append(result); return result
                stack.enter_context(patch.object(d.bridge, 'collect_snapshot', return_value=snapshot))
                stack.enter_context(patch.object(d, 'collect_development', side_effect=lambda client, s: s))
                stack.enter_context(patch.object(d, 'map_state_for_snapshot', return_value=memory))
                stack.enter_context(patch.object(d, 'retire_starter_sleeping_spots'))
                stack.enter_context(patch.object(d, 'candidate_actions', return_value=(['equip_colonists'], details)))
                stack.enter_context(patch.object(d, 'choose_action', return_value=decision))
                stack.enter_context(patch.object(d, 'execute_action', side_effect=capture_execute))
                stack.enter_context(patch.object(d, 'publish_overlay'))
                stack.enter_context(patch.object(d.laya_preferences, 'load_preferences', return_value={'technical_logging': technical}))
                stack.enter_context(patch.object(d.colony_sessions, 'remember_campaign'))
                with patch.object(d.colony_outcomes, 'record', wraps=d.colony_outcomes.record) as outcomes:
                    record = d.run_development_cycle(client, None, {}, Path(folder) / 'state.json', log)
                logged = json.loads(log.read_text(encoding='utf-8'))
                self.assertIs(outcomes.call_args.args[3], observed[0])
                self.assertIn('doctrine_context', observed[0]['selection'])
                self.assertIn('weapon_assignments', memory)
                self.assertEqual(logged['decision'], decision)
                self.assertEqual(record['result'], logged['result'])
                self.assertLess(len(json.dumps(logged['result'])), 8000)
                if technical:
                    self.assertEqual(logged['technical']['result'], observed[0])
                    self.assertGreater(log.stat().st_size, 1400000)
                else:
                    self.assertNotIn('technical', logged)
                    self.assertLess(log.stat().st_size, 50000)
                console = io.StringIO()
                with redirect_stdout(console): print(d.stdout_result(record['result']))
                self.assertLessEqual(len(console.getvalue()), 1601)
                self.assertNotIn('doctrine_context', console.getvalue())

    def test_real_agent_questions_and_states_untouched_by_projection(self):
        class CapturedChooser(Chooser):
            def __init__(self): super().__init__(); self.inputs = []
            def predict(self, state, questions):
                self.inputs.append(copy.deepcopy((state, questions)))
                return super().predict(state, questions)
        snapshot, memory, details, _ = self.setup_choice()
        candidates, _ = d.candidate_actions(None, snapshot, {})
        agent = CapturedChooser()
        decision = d.choose_action(agent, snapshot, candidates)
        inputs = copy.deepcopy(agent.inputs); decision_before = copy.deepcopy(decision)
        selected = d.merge_decision_details(details, decision)
        raw = d.execute_action(Orders(), snapshot, memory, 'equip_colonists', selected)
        d.result_for_logging('equip_colonists', raw, decision)
        self.assertEqual(agent.inputs, inputs)
        self.assertEqual(decision, decision_before)
        self.assertTrue(any('weapon_pawn' in questions for _, questions in inputs))
        self.assertTrue(any('weapon_item' in questions for _, questions in inputs))

    def test_stdout_all_results_bounded_counts_and_string_truncation(self):
        for result in ({'applied': True, 'reason': 'r' * 1000000, 'response': {'nested': ['x'] * 100000},
                        'responses': [{'data': 'x' * 1000}] * 10000, 'selection': {'doctrine_context': 'D' * 1000000}},
                       ['x'] * 1000000, 'x' * 1000000):
            text = d.stdout_result(result)
            self.assertLessEqual(len(text), 1600)
            self.assertNotIn('x' * 1000, text)
        summary = json.loads(d.stdout_result({'applied': False, 'reason': 'native rejected', 'responses': [1, 2, 3]}))
        self.assertEqual(summary['responses'], {'count': 3})
        self.assertEqual(summary['reason'], 'native rejected')

if __name__ == '__main__': unittest.main()

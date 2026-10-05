"""Feeding must finish when every optional worker choice disappears."""
import copy
import json
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import colony_director as d
from laya_decisions import NoFeasibleChoice, ask_laya_choice
from tests.test_hourly_regressions import hot_colony


def care_snapshot():
    snapshot = hot_colony()
    pawn = snapshot['colonists'][0]
    pawn.update(current_job='FeedPatient', care_target_id=2)
    snapshot['development']['work_types'] = [
        {'def_name': name} for name in pawn['work_priorities']]
    snapshot['development']['weather']['temperature'] = 20
    snapshot['development']['rooms'][0]['temperature'] = 20
    snapshot['colonists'][1]['health_conditions'] = [{'def_name': 'Malnutrition', 'severity': .8}]
    return snapshot


class Pick:
    def predict(self, state, questions):
        key, question = next(iter(questions.items()))
        criteria = question['criteria']
        selected = next((k for k in ('set_work_priority', '1') if k in criteria), next(iter(criteria)))
        return {'answers': {key: {'choice': selected, 'confidence': 1}}}


class WorkerChoiceRecovery(unittest.TestCase):
    def test_care_job_hides_all_work_choices_then_releases_without_reset(self):
        s = care_snapshot()
        memory = {'anchor': {'x': 10, 'z': 10}, 'issued': {}}
        for cycle in range(8):
            s['game']['tick'] += 1000
            candidates, _ = d.candidate_actions(None, s, memory)
            self.assertNotIn('set_work_priority', candidates)
            self.assertEqual(d.live_work_options(s), {})
            self.assertEqual(d.worker_criteria(s, 'Cooking'), {})
            memory = json.loads(json.dumps(memory))
        s['colonists'][0].update(current_job='Wait', care_target_id=None)
        candidates, _ = d.candidate_actions(None, s, memory)
        self.assertTrue(s['development']['live_work_options'])
        self.assertIn('Cooking', d.live_work_options(s))
        self.assertNotIn('selection_unavailable', d.choose_action(Pick(), s, ['set_work_priority']))

    def test_old_options_cannot_force_a_protected_worker(self):
        s = care_snapshot()
        s['development']['live_work_options'] = {'Cooking': 'Stale worker available'}
        decision = d.choose_action(Pick(), s, ['set_work_priority'])
        self.assertEqual(decision['selection_unavailable'],
                         {'question_id': 'work_type', 'action': 'set_work_priority'})
        # Another healthy worker does not make the selected caregiver eligible.
        spare = copy.deepcopy(s['colonists'][0])
        spare.update(id=3, current_job='Wait', care_target_id=None)
        s['colonists'].append(spare)
        client = Mock()
        with self.assertRaises(d.bridge.RimApiError):
            d.execute_action(client, s, {'anchor': {'x': 10, 'z': 10}, 'issued': {}},
                'set_work_priority', {'work_type': 'Cooking', 'worker_pawn': 1, 'work_priority': 2})
        client.post.assert_not_called()

    def test_empty_choice_is_logged_without_order_and_next_cycle_runs(self):
        s = care_snapshot()
        memory = {'anchor': {'x': 10, 'z': 10}, 'growing_anchor': {'x': 5, 'z': 5},
                  'starter_site_verified': True, 'issued': {}}
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            stack.enter_context(patch.object(d.bridge, 'collect_snapshot', side_effect=lambda c: copy.deepcopy(s)))
            stack.enter_context(patch.object(d, 'collect_development', side_effect=lambda c, row: row))
            stack.enter_context(patch.object(d, 'map_state_for_snapshot', return_value=memory))
            stack.enter_context(patch.object(d, 'retire_starter_sleeping_spots'))
            stack.enter_context(patch.object(d, 'candidate_actions', return_value=(['set_work_priority'], {})))
            stack.enter_context(patch.object(d, 'publish_overlay'))
            stack.enter_context(patch.object(d.laya_preferences, 'load_preferences', return_value={}))
            stack.enter_context(patch.object(d.colony_sessions, 'remember_campaign'))
            orders = stack.enter_context(patch.object(d, 'execute_action', return_value={'applied': False, 'deliberate_defer': True}))
            log = Path(tmp) / 'decisions.jsonl'
            first = d.run_development_cycle(Mock(), Pick(), {}, Path(tmp) / 'memory.json', log)
            self.assertEqual(first['result']['reason'], 'selection_unavailable')
            self.assertEqual(first['order_outcome'], 'rejected')
            orders.assert_not_called()
            second = d.run_development_cycle(Mock(), Pick(), {}, Path(tmp) / 'memory.json', log)
            self.assertEqual(second['decision']['choice'], 'hold_survival')
            self.assertEqual(orders.call_count, 1)
            rows = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['result']['selection']['question_id'], 'work_type')

    def test_inference_failure_is_not_mislabeled_as_an_empty_choice(self):
        with self.assertRaises(NoFeasibleChoice):
            ask_laya_choice(None, {}, 'worker', 'Choose', {})
        s = care_snapshot()
        with patch.object(d, '_choose_action', side_effect=ValueError('invalid model answer')):
            with self.assertRaisesRegex(ValueError, 'invalid model answer'):
                d.choose_action(None, s, ['set_work_priority'])

    def test_small_food_deliveries_need_fuel_and_unpowered_stove_does_not_solve_it(self):
        s = care_snapshot()
        for raw in (0, 7, 33):
            s['map']['resources'].update(raw_food=raw, food=raw, meals=0)
            self.assertTrue(d.needs_cooking_fuel_reserve(s))
        s['development']['building_counts']['ElectricStove'] = 1
        s['development']['buildings'].append({'def': 'ElectricStove', 'power_on': False})
        self.assertTrue(d.needs_cooking_fuel_reserve(s))
        s['development']['buildings'][-1]['power_on'] = True
        self.assertFalse(d.needs_cooking_fuel_reserve(s))

    def test_already_assigned_alternative_does_not_hide_worker_needing_priority(self):
        s = care_snapshot()
        s['colonists'][0].update(current_job='Wait', care_target_id=None)
        s['colonists'][0]['work_priorities']['Cooking']['priority'] = 3
        s['colonists'][0]['skills'] = {'Cooking': {'level': 14}}
        assigned = copy.deepcopy(s['colonists'][0])
        assigned['id'] = 3
        assigned['work_priorities']['Cooking']['priority'] = 1
        assigned['skills'] = {'Cooking': {'level': 2}}
        s['colonists'].append(assigned)
        self.assertEqual([p['id'] for p in d.priority_deficit_workers(s, 'Cooking', avoid_ids={1})], [1])

    def test_lights_need_real_service_and_existing_unpowered_light_is_not_duplicated(self):
        s = care_snapshot()
        dev = s['development']
        dev.update(finished_research=['Electricity'], power_info={'current_power': 0}, building_catalog=[
            {'def_name': 'StandingLamp', 'available_now': True, 'cost_list': [{'thing_def': 'Steel', 'count': 20}]},
            {'def_name': 'TorchLamp', 'available_now': True, 'cost_list': [{'thing_def': 'WoodLog', 'count': 20}]}])
        room = dev['rooms'][0]
        self.assertIsNone(d.room_light_plan(None, s, room))
        dev['item_counts']['WoodLog'] = 140
        plan = d.room_light_plan(None, s, room)
        self.assertEqual(plan['light_def'], 'TorchLamp')
        room['contained_thing_defs'].append('StandingLamp')
        self.assertIsNone(d.room_light_plan(None, s, room))
        room['contained_thing_defs'].remove('StandingLamp')
        dev['construction_projects'] = [{'def_name': 'StandingLamp', 'position': {'x': 13, 'z': 14}}]
        self.assertIsNone(d.room_light_plan(None, s, room))

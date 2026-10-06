import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import colony_director as director
import colony_resilience as care


def fixture():
    patients = [{'pawn_id': pid, 'name': 'Patient', 'food': 0.0,
                 'downed': True, 'in_bed': pid == 2,
                 'conditions': [{'def_name': 'Malnutrition', 'severity': severity,
                                 'visible': True, 'lethal_severity': 1.0}]}
                for pid, severity in ((2, .85), (3, .912))]
    rows = [{'kind': 'rescue', 'worker_id': 1, 'target_id': 3, 'giver': 'DoctorRescue',
             'food_feasible': True, 'travel_distance': 3.0, 'starvation_ticks': 10500},
            {'kind': 'feed', 'worker_id': 1, 'target_id': 2, 'giver': 'DoctorFeedHumanlikes',
             'food_feasible': True, 'travel_distance': 4.0, 'starvation_ticks': 18000}]
    snapshot = {'game': {'tick': 10000}, 'map': {'id': 0}, 'colonists': [
        {'id': 1, 'downed': False, 'current_job': 'Harvest',
         'work_priorities': {'Doctor': {'priority': 0, 'disabled': False}}},
        *[{'id': p['pawn_id'], 'downed': True, 'health_conditions': copy.deepcopy(p['conditions'])} for p in patients]]}
    return snapshot, {'patients': patients, 'options': rows, 'active_orders': []}


class Client:
    def __init__(self, context):
        self.context, self.posts = context, []

    def get(self, path, **kwargs):
        if path != '/api/v1/resilience/context':
            raise AssertionError(path)
        return copy.deepcopy(self.context)

    def post(self, path, **kwargs):
        if path != '/api/v1/resilience/order':
            raise AssertionError(path)
        body = kwargs['body']
        self.posts.append(body)
        self.context['active_orders'] = [body]
        return {'applied': True, 'reason': 'actual_job_observed; feeding_not_complete'}


class StarvationSchedulerTests(unittest.TestCase):
    def run_cycle(self, snapshot, client, state):
        with tempfile.TemporaryDirectory() as directory:
            return director.run_urgent_nutrition_cycle(client, None, snapshot, state, Path(directory) / 'decisions.jsonl')

    @patch('colony_retry.time.time', return_value=100)
    def test_unwounded_patient_rescue_precedes_wound_only_pass_and_keeps_job(self, clock):
        snapshot, context = fixture()
        client, state = Client(context), {}
        with patch.object(director, 'ask_laya_choice', return_value=('1:3:DoctorRescue', {})) as ask:
            result = self.run_cycle(snapshot, client, state)
        self.assertTrue(result['result']['applied'])
        self.assertEqual(client.posts[0]['target_id'], 3)
        self.assertNotIn('tendable_now', snapshot['colonists'][2])
        self.assertIn('Malnutrition 0.912', ask.call_args.args[4]['1:3:DoctorRescue'])
        self.assertIn('defer', ask.call_args.args[4])
        context['options'] = [context['options'][0]]
        for step in range(8):
            snapshot['game']['tick'] += 1
            self.assertIsNone(self.run_cycle(snapshot, client, state))
        self.assertEqual(len(client.posts), 1)
        # A different newly urgent patient is never locked by that accepted job.
        snapshot['colonists'].append({'id': 4, 'downed': True,
            'health_conditions': [{'def_name': 'Malnutrition', 'severity': .96}]})
        context['options'].append(dict(context['options'][0], target_id=4))
        with patch.object(director, 'ask_laya_choice', return_value=('1:4:DoctorRescue', {})):
            self.assertTrue(self.run_cycle(snapshot, client, state)['result']['applied'])
        self.assertEqual(len(client.posts), 2)

    @patch('colony_retry.time.time', return_value=100)
    def test_defer_is_finite_patient_scoped_and_worsening_reopens(self, clock):
        snapshot, context = fixture()
        context['options'] = [context['options'][0]]
        client, state = Client(context), {}
        with patch.object(director, 'ask_laya_choice', return_value=('defer', {})):
            self.assertFalse(self.run_cycle(snapshot, client, state)['result']['applied'])
        for step in range(5):
            snapshot['game']['tick'] += 1
            self.assertIsNone(self.run_cycle(snapshot, client, state))
        snapshot['colonists'][2]['health_conditions'][0]['severity'] = .96
        context['patients'][1]['conditions'][0]['severity'] = .96
        with patch.object(director, 'ask_laya_choice', return_value=('1:3:DoctorRescue', {})):
            self.assertTrue(self.run_cycle(snapshot, client, state)['result']['applied'])

    def test_no_native_food_or_job_never_fabricates_rescue(self):
        snapshot, context = fixture()
        for row in context['options']:
            row['food_feasible'] = False
        client = Client(context)
        with patch.object(director, 'ask_laya_choice') as ask:
            self.assertIsNone(self.run_cycle(snapshot, client, {}))
        ask.assert_not_called()
        self.assertEqual(client.posts, [])

    def test_changed_care_patient_refuses_stale_reassignment(self):
        snapshot, context = fixture()
        context['options'] = [dict(context['options'][0],
            expected_current_job='TendPatient', expected_care_patient_id=8)]
        client = Client(context)
        def change_before_apply(*args, **kwargs):
            client.context['options'][0]['expected_care_patient_id'] = 9
            return '1:3:DoctorRescue', {}
        with patch.object(director, 'ask_laya_choice', side_effect=change_before_apply):
            result = self.run_cycle(snapshot, client, {})
        self.assertFalse(result['result']['applied'])
        self.assertEqual(client.posts, [])


if __name__ == '__main__':
    unittest.main()

import copy
import json
import re
import unittest
from unittest.mock import patch

import colony_resilience as care


class ClinicalAgent:
    cfg = {'max_len': 512, 'head_max_len': 192}

    def __init__(self):
        self.seen = []

    def tok(self, value, **kwargs):
        return {'input_ids': list(range((len(value) + 3) // 4))}

    def predict(self, visible, questions):
        self.seen.append(copy.deepcopy(visible))
        effects = visible['effects']
        def severity(key):
            match = re.search(r'Malnutrition ([0-9.]+)', effects[key]['benefit'])
            return float(match[1]) if match else -1
        choice = max(effects, key=severity)
        return {'answers': {next(iter(questions)): {'choice': choice}}}


def fixture():
    rows = [{'kind': 'feed', 'worker_id': 1, 'target_id': pid,
             'giver': 'DoctorFeedHumanlikes', 'worker': 'Caregiver',
             'medicine_skill': 0, 'food_feasible': True} for pid in (2, 3)]
    people = [{'pawn_id': pid, 'name': 'Patient', 'food': 0.0, 'in_bed': True,
               'downed': True, 'temperature': 21, 'roof': 'RoofConstructed',
               'conditions': [{'def_name': 'Malnutrition', 'severity': severity,
                               'lethal_severity': 1.0, 'visible': True}]} for pid, severity in ((2, .77), (3, .992))]
    return {'game': {'tick': 10000}, 'map': {'id': 0},
            'development': {'resilience': {'options': rows, 'patients': people}}}


class StarvationContextTests(unittest.TestCase):
    def test_severity_and_lethal_limit_survive_both_choices_and_budget(self):
        for reverse in (False, True):
            snapshot = fixture()
            if reverse:
                snapshot['development']['resilience']['options'].reverse()
            care.prepare(snapshot, {})
            agent = ClinicalAgent()
            selected, raw = care.choose(agent, {}, 'resilience_feed', snapshot)
            self.assertEqual(selected['target_id'], 3)
            self.assertGreaterEqual(len(agent.seen), 2)
            for visible in agent.seen:
                self.assertLessEqual(len(agent.tok(json.dumps(visible, default=str))['input_ids']), 312)
            critical = [v for v in agent.seen if any('Malnutrition 0.992' in e['benefit'] for e in v['effects'].values())]
            self.assertTrue(critical)
            self.assertIn('lethal 1.000', critical[-1]['effects'][next(k for k in critical[-1]['effects'] if k != 'defer')]['benefit'])
            self.assertIn('defer', agent.seen[-1]['effects'])

    def test_feeding_skill_is_distinct_from_treatment_quality(self):
        snapshot = fixture()
        care.prepare(snapshot, {})
        with patch.object(care, 'ask_laya_choice', side_effect=[('3', {}), ('1:3:DoctorFeedHumanlikes', {})]) as choose:
            care.choose(None, {}, 'resilience_feed', snapshot)
        context = choose.call_args.args[1]
        option = context['option_effects']['1:3:DoctorFeedHumanlikes']
        self.assertIn('Medicine skill does not determine', option['cost'])
        self.assertIn('tending wounds supplies no calories', option['inaction'])
        self.assertAlmostEqual(context['decision_facts']['nutrition']['remaining_margin'], .008)

    @patch('colony_retry.time.time', return_value=100)
    def test_defer_retains_dwell_but_reopens_when_lethal_margin_shrinks(self, clock):
        snapshot, state = fixture(), {}
        context = snapshot['development']['resilience']
        context['options'] = [context['options'][1]]
        context['patients'][1]['conditions'][0]['severity'] = .91
        care.prepare(snapshot, state)
        care.execute(None, snapshot, state, 'resilience_feed', {'defer': True})
        context['patients'][1]['conditions'][0]['severity'] = .92
        self.assertEqual(care.prepare(snapshot, state), [])
        context['patients'][1]['conditions'][0]['severity'] = .96
        self.assertEqual(care.prepare(snapshot, state), ['resilience_feed'])
        care.execute(None, snapshot, state, 'resilience_feed', {'defer': True})
        self.assertEqual(care.prepare(snapshot, state), [])
        context['options'].append(dict(context['options'][0], target_id=4))
        self.assertEqual(care.prepare(snapshot, state), ['resilience_feed'])
        self.assertEqual([r['target_id'] for r in context['plans']['resilience_feed'].values()], [4])

    def test_unknown_severity_is_not_a_zero_death_risk(self):
        facts = care.nutrition_facts({'food': 0, 'conditions': [{'def_name': 'Malnutrition', 'lethal_severity': 1}]})
        self.assertIsNone(facts['malnutrition'])
        self.assertIsNone(facts['remaining_margin'])
        self.assertIn('unknown', care.nutrition_description({'food': 0}))

    @patch('colony_retry.time.time', return_value=100)
    def test_new_scoped_care_yield_reopens_deferred_patient(self, clock):
        snapshot, state = fixture(), {}
        context = snapshot['development']['resilience']
        context['options'] = [context['options'][0]]
        care.prepare(snapshot, state)
        care.execute(None, snapshot, state, 'resilience_feed', {'defer': True})
        self.assertEqual(care.prepare(snapshot, state), [])
        context['options'][0].update(expected_current_job='TendPatient', expected_care_patient_id=7)
        self.assertEqual(care.prepare(snapshot, state), ['resilience_feed'])
        care.execute(None, snapshot, state, 'resilience_feed', {'defer': True})
        self.assertEqual(care.prepare(snapshot, state), [])
        context['options'][0]['expected_care_patient_id'] = 8
        self.assertEqual(care.prepare(snapshot, state), ['resilience_feed'])

    def test_scoped_reassignment_identity_is_forwarded_and_freshly_checked(self):
        row = dict(fixture()['development']['resilience']['options'][0],
                   expected_current_job='TendPatient', expected_care_patient_id=7)
        class Client:
            def __init__(self, fresh):
                self.fresh, self.posts = fresh, []
            def get(self, path, **kwargs):
                return {'options': self.fresh}
            def post(self, path, **kwargs):
                self.posts.append(kwargs['body'])
                return {'applied': True, 'reason': 'job_observed; consumption_unverified'}
        snapshot = fixture()
        changed = Client([dict(row, expected_care_patient_id=8)])
        self.assertFalse(care.execute(changed, snapshot, {}, 'resilience_feed', row)['applied'])
        self.assertEqual(changed.posts, [])
        fresh = Client([row])
        self.assertTrue(care.execute(fresh, snapshot, {}, 'resilience_feed', row)['applied'])
        self.assertEqual(fresh.posts[0]['expected_current_job'], 'TendPatient')
        self.assertEqual(fresh.posts[0]['expected_care_patient_id'], 7)


if __name__ == '__main__':
    unittest.main()

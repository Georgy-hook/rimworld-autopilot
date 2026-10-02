import unittest
from unittest.mock import patch
import colony_resilience as resilience


class Client:
    def __init__(self, options):
        self.options = options
        self.posts = []
    def get(self, path, **kwargs):
        return {'options': self.options}
    def post(self, path, **kwargs):
        self.posts.append((path, kwargs))
        return {'applied': True, 'reason': 'normal_job_scheduled; completion_unobserved'}


class ResilienceTests(unittest.TestCase):
    def setUp(self):
        self.row = {'kind': 'rescue', 'worker_id': 1, 'target_id': 2, 'giver': 'DoctorRescue'}
        self.snapshot = {'map': {'id': 3}, 'game': {'tick': 10000}, 'development': {'resilience': {'options': [self.row]}}}

    def test_prepares_live_options_and_cooldown(self):
        self.assertEqual(resilience.prepare(self.snapshot, {}), ['resilience_rescue'])
        self.assertEqual(resilience.prepare(self.snapshot, {'issued': {'resilience:resilience_rescue': 9800}}), [])

    def test_loading_older_save_does_not_disable_emergency_rescue(self):
        self.assertEqual(resilience.prepare(self.snapshot, {'issued': {'resilience:resilience_rescue': 900000}}), ['resilience_rescue'])
        self.assertEqual(resilience.prepare(self.snapshot, {'issued': None}), ['resilience_rescue'])

    def test_worker_became_unavailable_does_not_order(self):
        client = Client([])
        self.assertFalse(resilience.execute(client, self.snapshot, {}, 'resilience_rescue', self.row)['applied'])
        self.assertEqual(client.posts, [])

    def test_cross_action_and_partial_selection_are_rejected(self):
        client = Client([self.row])
        for action, selection in [('resilience_tend', self.row), ('resilience_rescue', {'kind': 'rescue'})]:
            self.assertFalse(resilience.execute(client, self.snapshot, {}, action, selection)['applied'])
        self.assertEqual(client.posts, [])

    def test_scheduled_is_not_recovery_and_records_cooldown(self):
        client, state = Client([self.row]), {}
        result = resilience.execute(client, self.snapshot, state, 'resilience_rescue', self.row)
        self.assertTrue(result['applied'])
        self.assertIn('completion_unobserved', result['reason'])
        self.assertEqual(state['issued']['resilience:resilience_rescue'], 10000)

    def test_model_can_defer_with_tradeoffs(self):
        resilience.prepare(self.snapshot, {})
        with patch.object(resilience, 'ask_laya_choice', return_value=('defer', {})) as choice:
            selected, _ = resilience.choose(None, {}, 'resilience_rescue', self.snapshot)
        self.assertTrue(selected['defer'])
        visible = choice.call_args.args[1]
        self.assertIn('inaction', visible['option_effects']['defer'])
        self.assertIn('defer', choice.call_args.args[4])

    def test_immunity_and_nontendable_illness_remain_visible(self):
        self.snapshot['development']['resilience']['patients'] = [
            {'pawn_id': 2, 'downed': True, 'conditions': [{'def_name': 'Heatstroke', 'severity': .8}]},
            {'pawn_id': 3, 'conditions': [{'def_name': 'Infection', 'severity': .7, 'immunity': .5}]},
            {'pawn_id': 4, 'conditions': [{'def_name': 'FoodPoisoning', 'severity': .3}]},
        ]
        summary = resilience.summary(self.snapshot)
        self.assertEqual(summary['immunity_races']['count'], 1)
        self.assertEqual(summary['resilience_patients']['count'], 1)
    def test_exposed_nonbleeding_rescue_is_a_real_choice(self):
        self.snapshot['development']['resilience']['patients'] = [{'pawn_id': 2, 'downed': True, 'temperature': -35, 'comfortable_min': -5, 'comfortable_max': 30, 'roof': None, 'gases': {'ToxGas': 20}, 'conditions': [{'def_name': 'Hypothermia', 'severity': .5}]}]
        self.assertEqual(resilience.summary(self.snapshot)['environmental_exposure']['count'], 1)
        resilience.prepare(self.snapshot, {})
        with patch.object(resilience, 'ask_laya_choice', side_effect=[('2', {}), ('1:2:DoctorRescue', {})]) as choice:
            selected, _ = resilience.choose(None, {}, 'resilience_rescue', self.snapshot)
        self.assertEqual(selected, self.row)
        self.assertIn('rescuer exposure', choice.call_args.args[3])

    def test_twentieth_critical_patient_evidence_survives_512_token_budget(self):
        import json
        class Agent:
            cfg = {'max_len': 512, 'head_max_len': 192}
            seen = []
            def tok(self, value, **kwargs):
                return {'input_ids': list(range((len(value)+3)//4))}
            def predict(self, visible, questions):
                self.seen.append(visible)
                question = next(iter(questions))
                effects = visible['effects']
                selected = next((k for k, v in effects.items() if 'Plague' in v['benefit']), next(iter(effects)))
                return {'answers': {question: {'choice': selected}}}
        agent = Agent()
        patients, rows = [], []
        for i in range(20):
            patients.append({'pawn_id': 100+i, 'conditions': [{'def_name': 'Plague' if i == 19 else 'Scratch', 'severity': .9 if i == 19 else .1, 'immunity': .4 if i == 19 else None, 'life_threatening': i == 19, 'treatment_ticks_left': 123, 'next_tend_ticks': 0}]})
            rows.append({'kind': 'tend', 'worker_id': 1, 'target_id': 100+i, 'giver': 'DoctorTendEmergency', 'medicine_skill': 14})
        self.snapshot['development']['resilience'] = {'patients': patients, 'options': rows}
        resilience.prepare(self.snapshot, {})
        selected, _ = resilience.choose(agent, {}, 'resilience_tend', self.snapshot)
        self.assertEqual(selected['target_id'], 119)
        critical = [v for v in agent.seen if any('Plague' in row['benefit'] for row in v['effects'].values())]
        self.assertTrue(critical)
        for visible in agent.seen:
            self.assertLessEqual(len(agent.tok(json.dumps(visible, ensure_ascii=False, default=str))['input_ids']), 312)
            for row in visible['effects'].values():
                self.assertEqual(set(row), {'benefit', 'risk', 'cost', 'inaction', 'uncertainty'})

    def test_roof_guard_and_thermostat_do_not_require_a_fake_worker(self):
        rows = [{'kind': 'roof_guard', 'worker_id': 0, 'target_id': 20, 'giver': 'Mine'}, {'kind': 'temperature', 'worker_id': 0, 'target_id': 30, 'giver': '21'}]
        self.snapshot['development']['resilience']['options'] = rows
        self.assertEqual(set(resilience.prepare(self.snapshot, {})), {'resilience_roof_guard', 'resilience_temperature'})
        self.assertEqual(resilience.summary(self.snapshot)['unsafe_roof_removals']['count'], 1)
        for row in rows:
            self.assertTrue(resilience.execute(Client(rows), self.snapshot, {}, 'resilience_' + row['kind'], row)['applied'])

    def test_hidden_implant_is_not_diagnosed_or_sent_to_model(self):
        import json
        self.snapshot['development']['resilience']['patients'] = [{'pawn_id': 2, 'conditions': [{'def_name': 'MetalhorrorImplant', 'visible': False, 'severity': .9, 'life_threatening': True}, {'def_name': 'Scratch', 'visible': True, 'severity': .1}]}]
        self.assertNotIn('MetalhorrorImplant', json.dumps(resilience.summary(self.snapshot)))
        resilience.prepare(self.snapshot, {})
        with patch.object(resilience, 'ask_laya_choice', return_value=('defer', {})) as choice:
            resilience.choose(None, {}, 'resilience_rescue', self.snapshot)
        self.assertNotIn('MetalhorrorImplant', json.dumps(choice.call_args.args[1]))

    def test_inspection_exposes_costs_and_infected_doctor_uncertainty(self):
        row = {'kind': 'inspect', 'worker_id': 1, 'target_id': 2, 'giver': '30', 'medicine_skill': 12, 'room_cleanliness': .4, 'current_temperature': 21, 'surgery_success': .95}
        self.snapshot['development']['resilience'] = {'options': [row], 'patients': [{'pawn_id': 2, 'name': 'Patient', 'conditions': []}]}
        resilience.prepare(self.snapshot, {})
        with patch.object(resilience, 'ask_laya_choice', side_effect=[('2', {}), ('1:2:30', {})]) as choice:
            selected, _ = resilience.choose(None, {}, 'resilience_inspect', self.snapshot)
        self.assertEqual(selected['giver'], '30')
        effects = choice.call_args.args[1]['option_effects']['1:2:30']
        self.assertIn('anesthesia60000', effects['cost'])
        self.assertIn('doctor can lie', effects['risk'])
        self.assertIn('matching sample analysis', effects['uncertainty'])
        self.assertEqual(resilience.prepare(self.snapshot, {'issued': {'resilience:resilience_inspect': 9000}}), [])


if __name__ == '__main__':
    unittest.main()

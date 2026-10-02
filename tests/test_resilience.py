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
        self.assertEqual(resilience.prepare(self.snapshot, {'resilience_memory': {'issued': {'resilience_rescue:2': {'tick': 9800}}}}), [])

    def test_loading_older_save_does_not_disable_emergency_rescue(self):
        self.assertEqual(resilience.prepare(self.snapshot, {'resilience_memory': {'issued': {'resilience_rescue:2': {'tick': 900000}}}}), ['resilience_rescue'])
        self.assertEqual(resilience.prepare(self.snapshot, {'issued': None}), ['resilience_rescue'])

    def test_cooldown_is_patient_scoped_not_doctor_scoped(self):
        state = {}
        resilience.execute(Client([self.row]), self.snapshot, state, 'resilience_rescue', self.row)
        self.snapshot['game']['tick'] += 1
        self.snapshot['development']['resilience']['options'] = [dict(self.row, worker_id=5), dict(self.row, target_id=99)]
        self.assertEqual(resilience.prepare(self.snapshot, state), ['resilience_rescue'])
        self.assertEqual([r['target_id'] for r in self.snapshot['development']['resilience']['plans']['resilience_rescue'].values()], [99])

    def test_defer_does_not_hide_new_or_discretely_worse_patient(self):
        state = {}
        context = self.snapshot['development']['resilience']
        context['patients'] = [{'pawn_id': 2, 'downed': False, 'food': .5, 'conditions': []}]
        resilience.prepare(self.snapshot, state)
        resilience.execute(Client([]), self.snapshot, state, 'resilience_rescue', {'defer': True})
        context['patients'][0]['food'] = .49
        self.assertEqual(resilience.prepare(self.snapshot, state), [])
        context['patients'][0]['downed'] = True
        self.assertEqual(resilience.prepare(self.snapshot, state), ['resilience_rescue'])
        context['options'].append(dict(self.row, target_id=99))
        self.assertIn('resilience_rescue', resilience.prepare(self.snapshot, state))

    @patch('colony_retry.time.time')
    def test_failure_suppresses_only_exact_option_and_expires(self, clock):
        clock.return_value = 100
        state = {}
        resilience.execute(Client([]), self.snapshot, state, 'resilience_rescue', self.row)
        self.snapshot['development']['resilience']['options'].append(dict(self.row, worker_id=5))
        resilience.prepare(self.snapshot, state)
        self.assertEqual([r['worker_id'] for r in self.snapshot['development']['resilience']['plans']['resilience_rescue'].values()], [5])
        clock.return_value = 116
        self.snapshot['game']['tick'] += 60
        resilience.prepare(self.snapshot, state)
        self.assertEqual(len(self.snapshot['development']['resilience']['plans']['resilience_rescue']), 2)

    @patch('colony_retry.time.time')
    def test_transport_exception_preserves_specific_retry_suppression(self, clock):
        clock.return_value = 100
        state = {}
        client = Client([self.row])
        with patch.object(client, 'post', side_effect=RuntimeError('offline transport failure')):
            with self.assertRaises(RuntimeError):
                resilience.execute(client, self.snapshot, state, 'resilience_rescue', self.row)
        self.assertEqual(resilience.prepare(self.snapshot, state), [])
        clock.return_value = 116
        self.snapshot['game']['tick'] += 60
        self.assertEqual(resilience.prepare(self.snapshot, state), ['resilience_rescue'])

    def test_feed_choice_preserves_native_hunger(self):
        row = dict(self.row, kind='feed', giver='DoctorFeedHumanlikes')
        self.snapshot['development']['resilience'] = {'options': [row], 'patients': [{'pawn_id': 2, 'food': .01, 'in_bed': True, 'downed': True}]}
        resilience.prepare(self.snapshot, {})
        with patch.object(resilience, 'ask_laya_choice', return_value=('defer', {})) as choice:
            resilience.choose(None, {}, 'resilience_feed', self.snapshot)
        self.assertIn('food=0.01', choice.call_args.args[1]['option_effects']['2']['benefit'])

    def test_native_clean_kitchen_and_doctor_bed_feasibility_source(self):
        from pathlib import Path
        helpers = Path(__file__).resolve().parents[1] / 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers'
        source = (helpers / 'ResilienceAutomationHelper.cs').read_text()
        care = source[source.index('var careRooms='):source.index('result.Environment =')]
        self.assertIn('ElectricStove', care)
        self.assertIn('FueledStove', care)
        diagnosis = (helpers / 'ResilienceDiagnosisHelper.cs').read_text()
        self.assertNotIn('.Take(3)', diagnosis)
        self.assertIn('beds.Where(b => doctor.CanReach', diagnosis)

    def test_memory_json_roundtrip_rollback_and_expired_history_pruning(self):
        import json
        state = {}
        resilience.prepare(self.snapshot, state)
        resilience.execute(Client([]), self.snapshot, state, 'resilience_rescue', {'defer': True})
        state = json.loads(json.dumps(state))
        self.assertEqual(resilience.prepare(self.snapshot, state), [])
        self.snapshot['game']['tick'] -= 1
        self.assertEqual(resilience.prepare(self.snapshot, state), ['resilience_rescue'])
        self.assertNotIn('resilience_memory', state)
        state = {'resilience_memory': {
            'issued': {'resilience_clean:' + str(i): {'tick': 0} for i in range(10000)},
            'deferred': {'resilience_inspect:7': {'tick': 9900, 'state': 'old'}, 'resilience_feed:8': {'tick': 0}},
            'failed': {'clean:1:' + str(i): {'tick': 0} for i in range(10000)}}}
        resilience.prepare(self.snapshot, state)
        self.assertEqual(set(state['resilience_memory']), {'deferred'})
        self.assertEqual(set(state['resilience_memory']['deferred']), {'resilience_inspect:7'})
        self.snapshot['game']['tick'] = 69900
        resilience.prepare(self.snapshot, state)
        self.assertNotIn('resilience_memory', state)

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
        self.assertEqual(state['resilience_memory']['issued']['resilience_rescue:2']['tick'], 10000)

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

    def test_thermostat_preserves_existing_target_power_and_room_evidence(self):
        row = {'kind': 'temperature', 'worker_id': 0, 'target_id': 30, 'giver': '21',
               'current_temperature': -5, 'current_target_temperature': 5, 'power_on': False}
        self.snapshot['development']['resilience']['options'] = [row]
        resilience.prepare(self.snapshot, {})
        with patch.object(resilience, 'ask_laya_choice', return_value=('defer', {})) as choice:
            resilience.choose(None, {}, 'resilience_temperature', self.snapshot)
        risk = choice.call_args.args[1]['option_effects']['30']['risk']
        self.assertIn('Room=-5C', risk)
        self.assertIn('existing_target=5C', risk)
        self.assertIn('power=False', risk)

    def test_native_thermostat_admission_prevents_rotation_and_freezer_reset(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi'
        source = (root / 'Helpers/ResilienceAutomationHelper.cs').read_text()
        guard = source[source.index('private static bool ThermalCorrectionNeeded'):source.index('public static ApiResult<ResilienceContextDto> Context')]
        self.assertIn('control.TargetTemperature >= 18f && control.TargetTemperature <= 26f', guard)
        self.assertIn('cooler.TargetTemperature < 0f', guard)
        self.assertIn('p.RaceProps.Humanlike', guard)
        self.assertIn('(p.InBed() || NeedsCare(p))', guard)
        self.assertIn('RestUtility.CanUseBedEver(p,b.def)', guard)
        self.assertIn('device.def.defName=="Heater" && room.Temperature < 10f', guard)
        self.assertIn('device.def.defName=="Cooler" && room.Temperature > 32f', guard)
        self.assertNotIn('PowerOn', guard)  # An unpowered device can be corrected once, then its safe target blocks rotation.
        self.assertIn('.Where(ThermalCorrectionNeeded)', source)
        self.assertIn('&& ThermalCorrectionNeeded(device)', source)
        self.assertIn('CurrentTargetTemperature', (root / 'Models/ResilienceDtos.cs').read_text())

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
        self.assertEqual(resilience.prepare(self.snapshot, {'resilience_memory': {'issued': {'resilience_inspect:2': {'tick': 9000}}}}), [])


if __name__ == '__main__':
    unittest.main()

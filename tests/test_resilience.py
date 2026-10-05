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

    @patch("colony_retry.time.time", return_value=100)
    def test_memory_json_roundtrip_rollback_and_expired_history_pruning(self, clock):
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
        clock.return_value = 221  # Expire both the game horizon and new wall floor.
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
            {'pawn_id': 3, 'conditions': [{'def_name': 'Infection', 'severity': .7, 'immunity': .5, 'lethal_severity': 1.0}]},
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




class ResilienceDeferReplayTests(unittest.TestCase):
    def setUp(self):
        self.row = {'kind':'rest','worker_id':361,'target_id':361,'food_feasible':False}
        self.patient = {'pawn_id':361,'downed':False,'life_threatening':False,'in_bed':False,
                        'bed_rest_priority':3,'food':.9,'bleeding_total':.1,'temperature':0,
                        'comfortable_min':5.88,'comfortable_max':29.96,'current_job':'GotoWander',
                        'conditions':[{'def_name':'Bite','severity':2,'tendable_now':False},
                                      {'def_name':'Hypothermia','severity':.25}]}
        self.snapshot={'game':{'tick':10000},'map':{'id':0},'development':{'resilience':{
            'patients':[self.patient],'options':[self.row]}}}
        self.memory={}

    def defer_once(self):
        resilience.prepare(self.snapshot,self.memory)
        with patch.object(resilience,'ask_laya_choice',return_value=('defer',{})):
            selected,_=resilience.choose(None,{},'resilience_rest',self.snapshot)
        client=Client([])
        result=resilience.execute(client,self.snapshot,self.memory,'resilience_rest',selected)
        self.assertEqual('laya_deferred',result['reason']);self.assertFalse(client.posts)

    @patch('colony_retry.time.time',return_value=100)
    def test_eight_accelerated_prepare_choose_execute_cycles_persisted_and_drift_quiet(self, clock):
        import json
        asks=0
        for cycle in range(9):
            clock.return_value=100+cycle*10
            self.snapshot['game']['tick']=10000+cycle*4500
            self.patient['current_job']='GotoWander' if cycle%2 else 'WaitWander'
            self.patient['mood']=.4+cycle*.01
            self.patient['bleeding_total']=.1+cycle*.001
            next(row for row in self.patient['conditions'] if row['def_name']=='Hypothermia')['severity']=.25+cycle*.001
            self.patient['conditions'].reverse() if cycle%2 else None
            actions=resilience.prepare(self.snapshot,self.memory)
            if 'resilience_rest' in actions:
                asks+=1
                self.defer_once()
            self.memory=json.loads(json.dumps(self.memory))
        self.assertEqual(1,asks)
        clock.return_value=220
        self.assertIn('resilience_rest',resilience.prepare(self.snapshot,self.memory))

    @patch('colony_retry.time.time',return_value=100)
    def test_clinical_new_risk_and_new_target_bypass_floor_immediately(self, clock):
        for field,value in (('downed',True),('life_threatening',True),('tendable_now',True),
                            ('bleeding_total',1.5)):
            with self.subTest(field=field):
                self.setUp();self.defer_once();self.patient[field]=value
                self.assertIn('resilience_rest',resilience.prepare(self.snapshot,self.memory))
        self.setUp();self.defer_once()
        self.patient['conditions'][1]['severity']=.36
        self.assertIn('resilience_rest',resilience.prepare(self.snapshot,self.memory))
        self.setUp();self.defer_once()
        self.snapshot['development']['resilience']['options'].append({**self.row,'worker_id':99,'target_id':99})
        resilience.prepare(self.snapshot,self.memory)
        plans=self.snapshot['development']['resilience']['plans']['resilience_rest']
        self.assertEqual([99],[row['target_id'] for row in plans.values()])

    @patch('colony_retry.time.time',return_value=100)
    def test_legacy_defer_migrates_once_and_rollback_or_bad_record_cannot_hide_patient(self, clock):
        import json
        legacy={'tick':9999,'state':repr(resilience._state(self.row,self.snapshot['development']['resilience']))}
        self.memory={'resilience_memory':{'deferred':{'resilience_rest:361':legacy}}}
        self.assertEqual([],resilience.prepare(self.snapshot,self.memory))
        self.memory=json.loads(json.dumps(self.memory))
        self.snapshot['game']['tick']+=4500;clock.return_value=110
        self.assertEqual([],resilience.prepare(self.snapshot,self.memory))
        self.snapshot['game']['tick']=9998
        self.assertIn('resilience_rest',resilience.prepare(self.snapshot,self.memory))
        for bad in ({'tick':'bad','state':'old'}, {'tick':100,'state':'old','retry_until':'bad'},
                    {'tick':True,'state':'old'}, {'tick':100,'state':None}):
            self.memory={'resilience_memory':{'deferred':{'resilience_rest:361':bad}}}
            self.assertIn('resilience_rest',resilience.prepare(self.snapshot,self.memory))

    @patch('colony_retry.time.time',return_value=100)
    def test_readiness_new_worker_and_option_order(self, clock):
        context=self.snapshot['development']['resilience']
        context['options'].append({**self.row,'worker_id':362})
        self.defer_once();context['options'].reverse()
        self.assertEqual([],resilience.prepare(self.snapshot,self.memory))
        context['options'].append({**self.row,'worker_id':363})
        self.assertIn('resilience_rest',resilience.prepare(self.snapshot,self.memory))

    @patch('colony_retry.time.time',return_value=100)
    def test_temporarily_failed_helper_does_not_change_defer_fingerprint(self, clock):
        context=self.snapshot['development']['resilience']
        blocked={**self.row,'worker_id':362}
        context['options'].append(blocked)
        self.memory={'resilience_memory':{'failed':{resilience._option(blocked):resilience.failure_record(10000,15)}}}
        self.defer_once()
        self.assertEqual([],resilience.prepare(self.snapshot,self.memory))
        clock.return_value=116;self.snapshot['game']['tick']+=4500
        self.assertEqual([],resilience.prepare(self.snapshot,self.memory))

    @patch('colony_retry.time.time',return_value=100)
    def test_tick_rewind_above_issue_tick_still_reopens_deferred_patient(self, clock):
        self.defer_once()
        self.snapshot['game']['tick']=20000
        self.assertEqual([],resilience.prepare(self.snapshot,self.memory))
        self.snapshot['game']['tick']=15000
        self.assertIn('resilience_rest',resilience.prepare(self.snapshot,self.memory))


class KittyRestClinicalReplayTests(unittest.TestCase):
    def setUp(self):
        # Actual Kitty rows from material-defer-paused snapshot tick143482.
        self.patient={'pawn_id':782,'name':'Kitty','downed':False,'in_bed':False,
          'tendable_now':False,'life_threatening':False,'bed_rest_priority':3,'medical_care':'Best',
          'food':.992,'temperature':36.9872742,'comfortable_min':5.9800005,'comfortable_max':29.86,
          'conditions':[{'def_name':'Asthma','part':'left lung','severity':.001,'immunity':0.,
                         'lethal_severity':-1.,'tendable_now':False},
                        {'def_name':'Asthma','part':'right lung','severity':.166625366,'immunity':0.,
                         'lethal_severity':-1.,'tendable_now':False}]}
        self.row={'kind':'rest','worker_id':782,'target_id':782,'food_feasible':False}
        self.snapshot={'game':{'tick':143482},'map':{'id':0},'development':{'resilience':{
          'patients':[self.patient],'options':[self.row]}}}
        self.memory={}

    def defer(self):
        resilience.prepare(self.snapshot,self.memory)
        with patch.object(resilience,'ask_laya_choice',return_value=('defer',{})):
            selected,_=resilience.choose(None,{},'resilience_rest',self.snapshot)
        self.assertFalse(resilience.execute(Client([]),self.snapshot,self.memory,'resilience_rest',selected)['applied'])

    @patch('colony_retry.time.time',return_value=100)
    def test_eight_persisted_cycles_asthma_eating_sleep_and_other_medplans_quiet(self,clock):
        import json
        asks=0
        for cycle in range(8):
            self.snapshot['game']['tick']=143482+4500*cycle;clock.return_value=100+10*cycle
            self.patient.update(in_bed=bool(cycle%2), food=.09 if cycle%2 else .99,
                                current_job='LayDown' if cycle%2 else 'HaulToCell',
                                bed_rest_priority=1 if cycle%2 else 3,medical_care='Best' if cycle%2 else 'HerbalOrWorse')
            self.patient['conditions'][1]['severity']=.1666+cycle*.001
            self.snapshot['development']['resilience']['options'].append(
                {'kind':'tend','worker_id':767+cycle,'target_id':770,'giver':'DoctorTendHumanlike'})
            if 'resilience_rest' in resilience.prepare(self.snapshot,self.memory):
                asks+=1;self.defer()
            self.memory=json.loads(json.dumps(self.memory))
        self.assertEqual(asks,1)
        clock.return_value=221
        self.assertIn('resilience_rest',resilience.prepare(self.snapshot,self.memory))

    @patch('colony_retry.time.time',return_value=100)
    def test_heat_and_hypo_worsening_bypass_but_improvement_does_not(self,clock):
        for name in ('Heatstroke','Hypothermia'):
            with self.subTest(name=name):
                self.setUp()
                self.patient['conditions'].append({'def_name':name,'severity':.36,'cur_stage_index':3})
                self.defer();clock.return_value=110
                self.patient['conditions'][-1].update(severity=.19,cur_stage_index=1)
                self.assertNotIn('resilience_rest',resilience.prepare(self.snapshot,self.memory))
                self.patient['conditions'][-1].update(severity=.36,cur_stage_index=3)
                self.assertNotIn('resilience_rest',resilience.prepare(self.snapshot,self.memory))
                self.patient['conditions'][-1].update(severity=.63,cur_stage_index=4)
                self.assertIn('resilience_rest',resilience.prepare(self.snapshot,self.memory))

    @patch('colony_retry.time.time',return_value=100)
    def test_new_emergency_and_new_subject_or_helper_bypass(self,clock):
        for field in ('downed','life_threatening','tendable_now','bleeding_total'):
            with self.subTest(field=field):
                self.setUp();self.defer();clock.return_value=110
                self.patient[field]=.2 if field=='bleeding_total' else True
                self.assertIn('resilience_rest',resilience.prepare(self.snapshot,self.memory))
        self.setUp();self.defer()
        self.snapshot['development']['resilience']['options'].append({**self.row,'target_id':770,'worker_id':770})
        self.assertIn('resilience_rest',resilience.prepare(self.snapshot,self.memory))

    @patch('colony_retry.time.time',return_value=100)
    def test_v1_persisted_sleeping_signature_upgrades_without_reasking(self,clock):
        import json
        context=self.snapshot['development']['resilience']
        self.patient['in_bed']=True
        old=resilience._state(self.row,context)
        oldsignature=repr((old,(('Asthma',0),('Asthma',0)),False,False,True,3,'Best',[('rest',782,782,None,False)]))
        self.memory={'resilience_memory':{'deferred':{'resilience_rest:782':{
          'tick':143482,'retry_started_at':100,'retry_until':220,'state':oldsignature}}}}
        self.patient.update(in_bed=False,food=.05)
        clock.return_value=110
        self.assertNotIn('resilience_rest',resilience.prepare(self.snapshot,self.memory))
        record=self.memory['resilience_memory']['deferred']['resilience_rest:782']
        self.assertEqual(json.loads(record['state'])['rest_version'],2)

    @patch('colony_retry.time.time',return_value=100)
    def test_rest_defer_leaves_blocked_material_action_executable_eight_cycles(self,clock):
        import copy,json
        from unittest.mock import Mock
        import colony_director as director
        s=self.snapshot;s['colonists']=[];s['combat']={}
        s['development']['plants']=[{'thing_id':90,'position':{'x':10,'z':10},'harvestable_now':True}]
        s['development']['construction_projects']=[{'thing_id':12,'def_name':'Wall',
          'materials_needed':[{'def_name':'WoodLog','required_count':5,'available_count':0}]}]
        memory={'anchor':{'x':10,'z':10}}
        self.memory=memory;self.defer()
        client=Mock();posts=[]
        client.get.side_effect=lambda ep,**kw:copy.deepcopy(s['development']['plants'])
        def post(ep,**kw):
            posts.append((ep,kw))
            for p in s['development']['plants']:p['is_designated_for_harvest']=True
            return {'applied':True}
        client.post.side_effect=post
        for cycle in range(8):
            clock.return_value=110+10*cycle;s['game']['tick']+=4500
            self.patient.update(in_bed=bool(cycle%2),food=.09 if cycle%2 else .99)
            self.assertNotIn('resilience_rest',resilience.prepare(s,self.memory))
            if cycle==0:
                self.assertFalse(director.construction_has_materials(s['development']['construction_projects'][0]))
                result=director.execute_action(client,s,self.memory,'harvest_nearby_trees',
                    {'tree_type':'Oak','tree_options':{'Oak':{'ids':[90]}}})
                self.assertTrue(result['applied'])
            elif cycle==1:
                # The following observed harvest supplies the exact blocked wall.
                s['development']['plants']=[]
                s['development']['construction_projects'][0]['materials_needed'][0]['available_count']=20
                self.assertTrue(director.construction_has_materials(s['development']['construction_projects'][0]))
            self.memory=json.loads(json.dumps(self.memory))
        self.assertEqual([ep for ep,_ in posts],['/api/v1/map/plants/harvest'])


class ResilienceImmunityEvidenceTests(unittest.TestCase):
    def test_explicit_nonlethal_asthma_is_not_an_immunity_race(self):
        asthma={'def_name':'Asthma','severity':.166625366,'immunity':0.,'lethal_severity':-1.}
        for condition in (asthma,{**asthma,'can_ever_kill':False}):
            snapshot={'development':{'resilience':{'patients':[{'pawn_id':782,'conditions':[condition]}]}}}
            self.assertEqual(resilience.summary(snapshot)['immunity_races'],{'count':0,'unknown_count':0})
            self.assertIs(resilience._immunity_race(condition),False)

    def test_lethal_or_native_can_kill_establishes_race_unknown_remains_unknown(self):
        for evidence in ({'lethal_severity':1.0},{'can_ever_kill':True}):
            h={'def_name':'Infection','severity':.7,'immunity':.5,**evidence}
            self.assertIs(resilience._immunity_race(h),True)
        unknown={'def_name':'ModdedCondition','severity':.7,'immunity':.5}
        self.assertIsNone(resilience._immunity_race(unknown))
        s={'development':{'resilience':{'patients':[{'pawn_id':1,'conditions':[unknown]}]}}}
        self.assertEqual(resilience.summary(s)['immunity_races'],{'count':0,'unknown_count':1})

    def test_chooser_uses_actual_lethal_race_not_asthma_immunity_zero(self):
        asthma={'def_name':'Asthma','severity':.16,'immunity':0.,'lethal_severity':-1.}
        infection={'def_name':'WoundInfection','severity':.7,'immunity':.5,'can_ever_kill':True}
        row={'kind':'rest','worker_id':782,'target_id':782}
        s={'game':{'tick':100},'map':{'id':1},'development':{'resilience':{
          'patients':[{'pawn_id':782,'conditions':[asthma,infection]}],'options':[row]}}}
        resilience.prepare(s,{})
        with patch.object(resilience,'ask_laya_choice',return_value=('defer',{})) as ask:
            resilience.choose(None,{},'resilience_rest',s)
        benefit=ask.call_args.args[1]['option_effects']['782']['benefit']
        self.assertIn('WoundInfection',benefit);self.assertIn('immunity_race=yes',benefit)
        s['development']['resilience']['patients'][0]['conditions']=[asthma]
        with patch.object(resilience,'ask_laya_choice',return_value=('defer',{})) as ask:
            resilience.choose(None,{},'resilience_rest',s)
        self.assertIn('immunity_race=no',ask.call_args.args[1]['option_effects']['782']['benefit'])


if __name__ == "__main__":
    unittest.main()

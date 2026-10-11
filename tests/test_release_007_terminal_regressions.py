"""Offline regressions from the ended release run; no game or model is launched."""
import copy
import unittest
import pathlib
import tempfile
from unittest import mock

import colony_combat as combat
import colony_director as director
import colony_medical_recovery as medical_recovery
import colony_society as society
import rimworld_laya as bridge
from test_hive_survival import hive_snapshot
from test_hourly_regressions import hot_colony
from test_society import snapshot as society_snapshot
from care_transport import bind_care_readback
import test_director as director_tests


class TerminalCareRegressions(unittest.TestCase):
    def care_snapshot(self, job='TendPatient'):
        snap = hive_snapshot()
        doctor = snap['combat']['colonists'][0]
        doctor.update(current_job=job, current_job_target_id=987,
                      current_job_target_id_b=987, care_target_id=987,
                      care_at_bedside=False, distance_to_nearest_opponent=0,
                      tendable_now=True, moving=1, can_fight=True,
                      position=copy.deepcopy(snap['combat']['hostiles'][0]['position']))
        return snap, doctor

    def test_group_retreat_cannot_take_clinical_worker_at_contact_or_en_route(self):
        for job in ('TendPatient', 'Rescue', 'FeedPatient'):
            snap, doctor = self.care_snapshot(job)
            for distance in (0, 3, 8, 40):
                doctor['distance_to_nearest_opponent'] = distance
                self.assertIn(doctor['id'], combat.protected_emergency_care_ids(snap))
                for tactic in ('civilian_retreat', 'withdraw_and_regroup', 'focus_fire'):
                    action = bridge.plan_action(snap, {'choice': tactic})
                    self.assertFalse(any(doctor['id'] in command.get('body', {}).get('fighter_ids', [])
                                         for command in action.get('commands', [])), (job, distance, tactic))

    def test_existing_tending_feeding_and_rescue_are_not_self_tend_candidates(self):
        for job in ('TendPatient', 'Rescue', 'FeedPatient'):
            snap, doctor = self.care_snapshot(job)
            doctor['distance_to_nearest_opponent'] = 12
            self.assertNotIn(doctor, combat.self_tend_candidates(snap))
            self.assertNotIn('emergency_self_tend', bridge.make_questions(snap)['threat_action']['criteria'])
            action = bridge.plan_action(snap, {'choice': 'emergency_self_tend', 'medical_target_id': doctor['id']})
            self.assertEqual(action['kind'], 'noop')

    def test_new_self_tend_still_available_after_old_care_finishes(self):
        snap, doctor = self.care_snapshot()
        doctor.update(current_job='Wait', distance_to_nearest_opponent=12)
        self.assertIn(doctor, combat.self_tend_candidates(snap))
        action = bridge.plan_action(snap, {'choice': 'emergency_self_tend', 'medical_target_id': doctor['id']})
        self.assertTrue(any(c['endpoint'] == '/api/v1/pawn/medical/tend' for c in action['commands']))

    def test_medicine_inability_blocks_self_tend_but_priority_zero_does_not(self):
        snap, doctor = self.care_snapshot()
        doctor.update(current_job='Wait', distance_to_nearest_opponent=12)
        snap['colonists'] = [{'id': doctor['id'], 'skills': {'Medicine': {'disabled': False}},
                             'work_priorities': {'Doctor': {'priority': 0, 'disabled': False}}}]
        self.assertIn(doctor, combat.self_tend_candidates(snap))
        snap['colonists'][0]['skills']['Medicine']['disabled'] = True
        self.assertNotIn(doctor, combat.self_tend_candidates(snap))
        snap['colonists'][0]['skills']['Medicine']['disabled'] = False
        doctor['manipulation'] = 0
        self.assertNotIn(doctor, combat.self_tend_candidates(snap))

    def test_no_hostiles_does_not_cancel_a_drafted_rescue(self):
        snap, doctor = self.care_snapshot('Rescue')
        doctor['is_drafted'] = True
        snap['combat']['hostiles'] = []
        action = bridge.plan_action(snap, {'choice': 'stand_down'})
        self.assertFalse(any(c.get('body', {}).get('pawn_id') == doctor['id'] for c in action.get('commands', [])))

    def test_care_escape_requires_the_offered_exact_actor_and_patient(self):
        snap, doctor = self.care_snapshot()
        option = {'tactic': 'caregiver_retreat', 'fighter_id': doctor['id'],
                  'target_id': snap['combat']['hostiles'][0]['id'], 'expected_current_job': 'TendPatient',
                  'expected_care_patient_id': 987, 'label': 'Suspend care to escape', 'effects': {}}
        snap['combat']['native_options'] = [option]
        self.assertIn('caregiver_retreat', bridge.make_questions(snap)['threat_action']['criteria'])
        action = bridge.plan_action(snap, {'choice': 'caregiver_retreat', 'native_plan': option})
        body = action['commands'][0]['body']
        self.assertEqual(body['fighter_ids'], [doctor['id']])
        self.assertEqual(body['expected_care_patient_id'], 987)
        self.assertEqual(body['expected_current_job'], 'TendPatient')
        doctor['care_target_id'] = 999
        self.assertEqual(bridge.plan_action(snap, {'choice': 'caregiver_retreat', 'native_plan': option})['kind'], 'noop')

    def test_escape_does_not_drop_a_carried_patient(self):
        snap, doctor = self.care_snapshot('Rescue')
        doctor['carrying_pawn_id'] = 987
        snap['combat']['native_options'] = [{'tactic': 'caregiver_retreat', 'fighter_id': doctor['id'],
            'target_id': snap['combat']['hostiles'][0]['id'], 'expected_current_job': 'Rescue',
            'expected_care_patient_id': 987}]
        self.assertEqual(combat.native_tactical_options(snap, 'caregiver_retreat'), {})

    def test_rejected_escape_route_does_not_repeat_and_new_patient_can_reopen_it(self):
        import json
        snap, doctor = self.care_snapshot()
        option = {'tactic': 'caregiver_retreat', 'fighter_id': doctor['id'],
                  'target_id': snap['combat']['hostiles'][0]['id'], 'expected_current_job': 'TendPatient',
                  'expected_care_patient_id': 987, 'effects': {}}
        snap['combat']['native_options'] = [option]
        decision = {'choice': 'caregiver_retreat', 'native_plan': option}
        action = bridge.plan_action(snap, decision)
        memory = {}
        rejected = {'responses': [{'positioned_pawn_ids': [], 'attacking_pawn_ids': [],
                                  'notes': ['No checked escape route; current care retained.']}]}
        with mock.patch('time.time', return_value=100):
            for _ in range(2):
                bridge._combat_retry_record(memory, 'same', decision, action, rejected)
            memory = json.loads(json.dumps(memory))
            for _ in range(10):
                snap['combat']['native_options'] = [copy.deepcopy(option)]
                bridge._combat_retry_prepare(snap, memory, 'same')
                self.assertEqual(combat.native_tactical_options(snap, 'caregiver_retreat'), {})
                stale = bridge._combat_retry_filter_action(snap, decision, copy.deepcopy(action))
                self.assertEqual(stale['commands'], [])
            doctor['care_target_id'] = 999
            snap['combat']['native_options'] = [{**option, 'expected_care_patient_id': 999}]
            bridge._combat_retry_prepare(snap, memory, 'same')
            self.assertTrue(combat.native_tactical_options(snap, 'caregiver_retreat'))

    def test_exact_care_escape_survives_the_building_only_threat_filter(self):
        snap, doctor = self.care_snapshot()
        snap['combat']['hostiles'] = []
        snap['combat']['hostile_buildings'] = [{'id': 90, 'is_turret': True,
            'position': copy.deepcopy(doctor['position']), 'weapon_range': 30}]
        option = {'tactic': 'caregiver_retreat', 'fighter_id': doctor['id'], 'target_id': 90,
            'expected_current_job': 'TendPatient', 'expected_care_patient_id': 987, 'effects': {}}
        snap['combat']['native_options'] = [option]
        self.assertIn('caregiver_retreat', bridge.make_questions(snap)['threat_action']['criteria'])
        action = bridge.plan_action(snap, {'choice': 'caregiver_retreat', 'native_plan': option})
        self.assertEqual(action['commands'][0]['body']['target_pawn_id'], 90)

    def test_undraft_preparation_preserves_an_exposed_retreat_route(self):
        snap, doctor = self.care_snapshot()
        doctor.update(current_job='Goto', is_drafted=True)
        action = bridge.plan_action(snap, {'choice': 'prepare_undrafted'})
        self.assertFalse(any(c.get('body', {}).get('pawn_id') == doctor['id'] for c in action.get('commands', [])))
        doctor.update(position={'x': 1, 'z': 1}, distance_to_nearest_opponent=100)
        action = bridge.plan_action(snap, {'choice': 'prepare_undrafted'})
        self.assertTrue(any(c.get('body', {}).get('pawn_id') == doctor['id'] for c in action.get('commands', [])))

    def test_native_care_escape_keeps_its_actor_until_the_exact_move_finishes(self):
        snap, doctor = self.care_snapshot()
        doctor.update(current_job='Goto', is_drafted=False, distance_to_nearest_opponent=12)
        snap['combat']['care_retreat_pawn_ids'] = [doctor['id']]
        snap['colonists'] = [{**doctor, 'work_priorities': {
            'Doctor': {'priority': 1}, 'Hauling': {'priority': 1}}}]
        for _ in range(10):
            self.assertNotIn(doctor, combat.self_tend_candidates(snap))
            self.assertNotIn(str(doctor['id']), director.worker_criteria(snap, 'Hauling'))
            self.assertNotIn(doctor['id'], [p['id'] for p in medical_recovery.helpers(snap, 987, doctor=True)])
            self.assertFalse(any(o.get('doctor_id') == doctor['id']
                                 for o in director.post_combat_care_options(snap).values()))
            for tactic in ('civilian_retreat', 'withdraw_and_regroup', 'focus_fire', 'prepare_undrafted', 'stand_down'):
                action = bridge.plan_action(snap, {'choice': tactic})
                self.assertFalse(any(command.get('body', {}).get('pawn_id') == doctor['id']
                                     or doctor['id'] in command.get('body', {}).get('fighter_ids', [])
                                     for command in action.get('commands', [])), tactic)

    def test_completed_care_escape_does_not_lock_the_actor_or_a_later_move(self):
        snap, doctor = self.care_snapshot()
        doctor.update(current_job='Wait', is_drafted=False, distance_to_nearest_opponent=12)
        snap['combat']['care_retreat_pawn_ids'] = [doctor['id']]
        snap['colonists'] = [{**doctor, 'work_priorities': {'Hauling': {'priority': 1}}}]
        self.assertIn(doctor, combat.self_tend_candidates(snap))
        self.assertIn(str(doctor['id']), director.worker_criteria(snap, 'Hauling'))
        snap['combat']['care_retreat_pawn_ids'] = []
        doctor['current_job'] = 'Goto'
        self.assertNotIn(doctor['id'], combat.protected_care_retreat_ids(snap))

    def test_escape_ownership_does_not_stop_another_doctor_treating_the_patient(self):
        snap = director_tests.DirectorTests.disease_snapshot()
        patient, doctor = snap['combat']['colonists']
        patient.update(tendable_now=True, bleeding_rate=2)
        doctor.update(current_job='Goto', is_drafted=False)
        backup = {**doctor, 'id': 3, 'name': 'Backup', 'current_job': 'Wait'}
        snap['combat']['colonists'].append(backup)
        snap['colonists'].append(copy.deepcopy(backup))
        snap['combat']['care_retreat_pawn_ids'] = [2]
        offers = director.post_combat_care_options(snap)
        self.assertFalse(any(o.get('doctor_id') == 2 for o in offers.values()))
        self.assertTrue(any(o.get('doctor_id') == 3 and o.get('patient_id') == 1 for o in offers.values()))

    def test_rest_does_not_reclaim_a_patient_in_an_accepted_escape(self):
        snap = director_tests.DirectorTests.disease_snapshot()
        snap['combat']['colonists'][0]['current_job'] = 'Goto'
        snap['combat']['care_retreat_pawn_ids'] = [1]
        buildings = snap['development']['buildings']
        self.assertNotIn('rest_1_10', director.post_combat_care_options(snap, buildings))
        snap['combat']['colonists'][0]['current_job'] = 'Wait'
        self.assertIn('rest_1_10', director.post_combat_care_options(snap, buildings))

    def test_fresh_care_readback_rejects_a_stale_plan_after_an_escape_started(self):
        snap = director_tests.DirectorTests.disease_snapshot()
        plan = director.post_combat_care_options(snap, snap['development']['buildings'])['rest_1_10']
        fresh = copy.deepcopy(snap['combat'])
        fresh['colonists'][0]['current_job'] = 'Goto'
        fresh['care_retreat_pawn_ids'] = [1]
        client = mock.Mock()
        client.get.return_value = fresh
        result, _ = medical_recovery.validate_post_combat_plan(client, snap, plan, director.post_combat_care_options)
        self.assertEqual(result['reason'], 'care_escape_in_progress')
        self.assertFalse(result['assignment_accepted'])
        self.assertFalse(result['job_observed'])
        self.assertTrue(result['escape_job_observed'])
        client.post.assert_not_called()

    def test_already_resting_patient_gets_policy_once_without_restarting_rest(self):
        snap = director_tests.DirectorTests.disease_snapshot()
        patient = snap['colonists'][0]
        snap['combat']['colonists'][0].update(current_job='LayDown', current_job_target_id=10)
        client = mock.Mock()
        def accept(endpoint, **kwargs):
            if endpoint == '/api/v1/colonist/work-priority':
                patient['work_priorities'][kwargs['body']['work']]['priority'] = 1
            return {'success': True}
        client.post.side_effect = accept
        bind_care_readback(client, snap)
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(director, 'publish_post_combat_care_overlay'):
            first = director.run_post_combat_care_cycle(client, director_tests.DirectorTests.FakeAgent([]),
                snap, pathlib.Path(folder) / 'care.jsonl', focus_downed=True)
            self.assertTrue(first['result']['policy_configured'])
            self.assertFalse(first['result']['assignment_accepted'])
            self.assertTrue(first['result']['job_observed'])
            calls = client.post.call_count
            for _ in range(10):
                self.assertIsNone(director.run_post_combat_care_cycle(client, director_tests.DirectorTests.FakeAgent([]),
                    snap, pathlib.Path(folder) / 'care.jsonl', focus_downed=True))
        self.assertEqual(client.post.call_count, calls)
        self.assertEqual(calls, 2)
        self.assertFalse(any(c.args[0] == '/api/v1/pawn/medical/bed-rest' for c in client.post.call_args_list))


class MedicalPolicyRegressions(unittest.TestCase):
    def patient_snapshot(self, care='NoMeds'):
        snap = society_snapshot({'pawn_id': 2, 'medical_attention': True, 'medical_care': care,
            'care_options': ['NoMeds', 'HerbalOrWorse', 'NormalOrWorse', 'Best'],
            'needs': [{'def_name': 'Food', 'level': .8}],
            'conditions': [{'def_name': 'WoundInfection', 'severity': .35, 'immunity': .2,
                            'immunity_can_develop': True, 'tend_quality': .098, 'tend_ticks_left': 0}]})
        snap['development']['society']['medicine'] = {'MedicineIndustrial': 38}
        return snap

    def test_best_ceiling_and_adequate_stock_do_not_generate_44_downgrades(self):
        snap = self.patient_snapshot('Best')
        state = {}
        for tick in range(50000, 160000, 2500):
            snap['game']['tick'] = tick
            snap['development']['society']['people'][0]['needs'][0]['level'] = (tick % 10000) / 10000
            self.assertNotIn('society_medical_care', society.prepare(snap, state))

    def test_ceiling_upgrade_stays_available_when_it_unblocks_stocked_medicine(self):
        snap = self.patient_snapshot()
        self.assertIn('society_medical_care', society.prepare(snap, {}))
        offers = snap['development']['society']['options']['society_medical_care'].values()
        self.assertEqual({o['value'] for o in offers}, {'NormalOrWorse', 'Best'})

    def test_modded_medicine_uses_native_permissions_instead_of_name_guessing(self):
        snap = self.patient_snapshot('NormalOrWorse')
        snap['development']['society']['medicine_catalog'] = [
            {'def_name': 'CustomMedicine', 'count': 6, 'potency': 2, 'allowed_care': ['Best']}]
        society.prepare(snap, {})
        self.assertEqual({o['value'] for o in snap['development']['society']['options']['society_medical_care'].values()}, {'Best'})

    def test_medical_defer_survives_hunger_change_game_speed_and_json_roundtrip(self):
        import json
        snap = self.patient_snapshot()
        state = {}
        society.prepare(snap, state)
        with mock.patch('colony_retry.time.time', return_value=1000):
            society.execute(None, snap, state, 'society_medical_care', {'defer': True})
        state = json.loads(json.dumps(state))
        snap['game']['tick'] += 30001
        snap['development']['society']['people'][0]['needs'][0]['level'] = .01
        with mock.patch('colony_retry.time.time', return_value=1080):
            self.assertNotIn('society_medical_care', society.prepare(snap, state))
        with mock.patch('colony_retry.time.time', return_value=1121):
            self.assertIn('society_medical_care', society.prepare(snap, state))

    def test_new_clinical_danger_can_reopen_a_deferred_policy(self):
        snap = self.patient_snapshot()
        state = {}
        society.prepare(snap, state)
        society.execute(None, snap, state, 'society_medical_care', {'defer': True})
        snap['development']['society']['people'][0]['conditions'][0]['severity'] = .91
        self.assertIn('society_medical_care', society.prepare(snap, state))

    def test_real_scarcity_remains_a_choice_with_explicit_critical_patient_risk(self):
        snap = self.patient_snapshot('Best')
        context = snap['development']['society']
        context['medicine'] = {'MedicineIndustrial': 1}
        context['people'][0]['conditions'] = [{'def_name': 'Bruise', 'severity': .05}]
        self.assertIn('society_medical_care', society.prepare(snap, {}))
        context['people'][0]['conditions'][0].update(life_threatening=True)
        self.assertIn('society_medical_care', society.prepare(snap, {}))
        offer = next(iter(context['options']['society_medical_care'].values()))
        risk = society._effects(offer, 'society_medical_care', context)['risk']
        self.assertIn('critical_patient=True', risk)
        self.assertIn('kill a critical patient', risk)

    def test_no_stock_cannot_make_a_ceiling_downgrade_useful(self):
        snap = self.patient_snapshot('Best')
        context = snap['development']['society']
        context['medicine'] = {}
        context['people'][0]['conditions'] = [{'def_name': 'Bruise', 'severity': .05}]
        self.assertNotIn('society_medical_care', society.prepare(snap, {}))


class RefuelRegressions(unittest.TestCase):
    def test_observed_refueling_is_not_reoffered_after_assignment_cooldown(self):
        snap = hot_colony(wood=161)
        snap['combat']['colonists'] = [{'id': 1, 'current_job': 'Refuel', 'current_job_target_id': 50}]
        state = {'anchor': {'x': 10, 'z': 10}, 'issued': {'refuel:50': snap['game']['tick'] - 4000}}
        choices, _ = director.candidate_actions(None, snap, state)
        self.assertNotIn('refuel_building', choices)
        snap['combat']['colonists'][0]['current_job'] = 'Wait'
        choices, _ = director.candidate_actions(None, snap, state)
        self.assertIn('refuel_building', choices)

    def test_recovering_mobile_worker_can_choose_urgent_thermal_refuel(self):
        snap = hot_colony(wood=161)
        snap['colonists'][0]['health_conditions'] = [{'def_name': 'WoundInfection', 'severity': .4,
            'immunity': .3, 'immunity_can_develop': True, 'tendable_now': False}]
        state = {'anchor': {'x': 10, 'z': 10}, 'issued': {}}
        choices, _ = director.candidate_actions(None, snap, state)
        self.assertNotIn('1', director.worker_criteria(snap, 'Hauling'))
        self.assertIn('refuel_building', choices)
        self.assertIn('1', director.refuel_worker_criteria(snap))
        snap['colonists'][0]['current_job'] = 'TendPatient'
        self.assertNotIn('1', director.refuel_worker_criteria(snap))

    def test_recovery_exception_does_not_admit_routine_generator_refuel(self):
        snap = hot_colony(wood=161)
        snap['colonists'][0]['health_conditions'] = [{'def_name': 'WoundInfection', 'severity': .4, 'immunity': .3}]
        snap['development']['cold_threat'] = {'outside_c': 4}
        options = {'50': {'def': 'WoodFiredGenerator', 'current_fuel': 0}}
        self.assertNotIn('1', director.refuel_worker_criteria(snap, options))

    def test_failed_refuel_is_not_remembered_as_a_completed_or_issued_job(self):
        snap = hot_colony(wood=161)
        state = {'anchor': {'x': 10, 'z': 10}, 'issued': {}}
        _, details = director.candidate_actions(None, snap, state)
        client = mock.Mock()
        client.post.return_value = {'applied': False, 'reason': 'fuel_unavailable_or_building_reserved'}
        result = director.execute_action(client, snap, state, 'refuel_building',
            {**details, 'refuel_target': '50', 'worker_pawn': '1'})
        self.assertFalse(result['applied'])
        self.assertNotIn('refuel:50', state['issued'])
        client.post.return_value = {'applied': False, 'in_progress': True, 'reason': 'refueling_in_progress'}
        result = director.execute_action(client, snap, state, 'refuel_building',
            {**details, 'refuel_target': '50', 'worker_pawn': '1'})
        self.assertFalse(result['applied'])
        self.assertTrue(result['in_progress'])
        self.assertEqual(result['completion'], 'unverified')
        self.assertIn('refuel:50', state['issued'])


if __name__ == '__main__':
    unittest.main()

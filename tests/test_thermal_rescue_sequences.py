"""Recorded DTO-shaped offline transitions; these are not live warming evidence."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import colony_director as d
import colony_medical_recovery as care
import colony_resilience as r
import rimworld_laya as bridge
from test_routine_care_thermal import state as cold_state


def snapshot():
    patient = {'id': 1, 'name': 'Patient', 'downed': True, 'bleeding_rate': 0,
        'position': {'x': 145, 'z': 166}, 'hunger': .8,
        'health_conditions': [{'def_name': 'Hypothermia', 'severity': .643, 'life_threatening': True,
                              'tendable_now': False, 'immunity_can_develop': False},
                             {'def_name': 'Frostbite', 'severity': 3, 'tendable_now': True}]}
    worker = {'id': 2, 'name': 'Caregiver', 'current_job': 'TendPatient',
        'capacities': {'moving': 1, 'manipulation': 1}, 'health_conditions': [],
        'work_priorities': {'Doctor': {'disabled': False, 'priority': 0}}}
    row = {'kind': 'rescue', 'worker_id': 2, 'target_id': 1, 'giver': 'DoctorRescue',
        'expected_current_job': 'TendPatient', 'expected_care_patient_id': 1,
        'care_yield_reason': 'nonbleeding_tend_to_thermal_rescue_same_patient',
        'food_feasible': False, 'thermal_rescue': True, 'bed_id': 100,
        'current_temperature': -25, 'destination_temperature': 22, 'travel_distance': 40}
    return {'game': {'tick': 31000}, 'map': {'id': 0}, 'colonists': [patient, worker],
        'combat': {'colonists': [{'id': 1, 'is_downed': True, 'bleeding_rate': 0},
            {'id': 2, 'current_job': 'TendPatient', 'current_job_target_id': 1, 'care_target_id': 1}]},
        'development': {'resilience': {'available': True, 'options': [row],
            'patients': [{'pawn_id': 1, 'downed': True, 'in_bed': False, 'current_bed_id': None, 'bleeding_total': 0,
                         'conditions': copy.deepcopy(patient['health_conditions']), 'temperature': -25}],
            'active_orders': [{'kind': 'tend', 'job_def': 'TendPatient', 'worker_id': 2, 'target_id': 1}]}}}


class Agent:
    def predict(self, state, questions):
        key, q = next(iter(questions.items()))
        return {'answers': {key: {'choice': next(k for k in q['criteria'] if k != 'defer')}}}


class World:
    def __init__(self, snap): self.snap, self.orders, self.stale = snap, [], False
    def get(self, path, **kw):
        assert path == '/api/v1/resilience/context'
        result = copy.deepcopy(self.snap['development']['resilience'])
        if self.stale: result['options'] = []
        return result
    def post(self, path, **kw):
        assert path == '/api/v1/resilience/order'
        self.orders.append(copy.deepcopy(kw['body']))
        wid, pid = kw['body']['worker_id'], kw['body']['target_id']
        next(p for p in self.snap['combat']['colonists'] if p['id'] == wid).update(
            current_job='Rescue', current_job_target_id=pid, current_job_target_id_b=100, care_target_id=pid)
        next(p for p in self.snap['colonists'] if p['id'] == wid)['current_job'] = 'Rescue'
        self.snap['development']['resilience'].update(options=[], active_orders=[
            {'kind': 'rescue', 'job_def': 'Rescue', 'worker_id': 2, 'target_id': 1}])
        return {'applied': True, 'reason': 'native_job_scheduled'}


class ThermalRescueSequences(unittest.TestCase):
    def test_tend_yields_to_same_patient_thermal_rescue_without_food(self):
        s = snapshot()
        row = s['development']['resilience']['options'][0]
        self.assertIsNotNone(care.offered_care_yield(s, row))
        plans = care.build_options(None, s, {})
        self.assertEqual(set(plans['rescue_downed_colonist']['1']['helpers']), {'2'})
        self.assertEqual(plans['feed_hungry_colonist'], {})

    def test_eight_cycles_persist_native_rescue_and_carried_patient(self):
        s = snapshot(); client = World(s); memory = {}
        with patch.object(bridge, 'append_log'):
            first = d.run_urgent_thermal_cycle(client, Agent(), s, memory, Path('unused'))
            self.assertTrue(first['result']['applied'])
            for cycle in range(8):
                s['game']['tick'] += 600
                memory = json.loads(json.dumps(memory))
                if cycle >= 2:
                    s['combat']['colonists'][1].update(carrying_pawn_id=1, carrying_player_pawn=True)
                    s['development']['resilience']['active_orders'][0]['carried_thing_id'] = 1
                self.assertIsNone(d.run_urgent_thermal_cycle(client, Agent(), s, memory, Path('unused')))
        self.assertEqual(len(client.orders), 1)
        self.assertEqual(client.orders[0]['expected_current_job'], 'TendPatient')
        self.assertEqual(client.orders[0]['expected_care_patient_id'], 1)
        self.assertEqual(s['combat']['colonists'][1]['current_job'], 'Rescue')

    def test_fresh_native_route_or_bed_loss_prevents_post(self):
        s = snapshot(); client = World(s); memory = {}
        r.prepare(s, memory)
        client.stale = True
        result = r.execute(client, s, memory, 'resilience_rescue', r.order_fields(s['development']['resilience']['options'][0]))
        self.assertFalse(result['applied'])
        self.assertEqual(client.orders, [])

    def test_thermal_pass_does_not_preempt_real_wound_or_disease_care(self):
        for state in ('bleeding', 'plague', 'heart_crisis'):
            s = snapshot(); native = s['development']['resilience']['patients'][0]
            if state == 'bleeding': native['bleeding_total'] = .01
            else: native['conditions'].append({'def_name': 'Plague' if state == 'plague' else 'HeartArteryBlockage',
                                               'life_threatening': True, 'immunity': .3 if state == 'plague' else 0,
                                               'immunity_can_develop': state == 'plague'})
            client = World(s)
            self.assertIsNone(d.run_urgent_thermal_cycle(client, Agent(), s, {}, Path('unused')))
            self.assertEqual(client.orders, [])

    def test_bleeding_infection_feeding_carrying_and_other_patient_are_protected(self):
        for mutation in ('bleed', 'worker_bleed', 'immune', 'other_disease', 'feed', 'carry', 'other_patient', 'changed_job', 'in_bed'):
            with self.subTest(mutation=mutation):
                s = snapshot(); row = s['development']['resilience']['options'][0]
                if mutation == 'bleed': s['colonists'][0]['bleeding_rate'] = .01
                if mutation == 'worker_bleed': s['combat']['colonists'][1]['bleeding_rate'] = .01
                if mutation == 'immune': s['colonists'][0]['health_conditions'].append({'def_name': 'WoundInfection', 'immunity': .3, 'immunity_can_develop': True})
                if mutation == 'other_disease': s['colonists'][0]['health_conditions'].append({'def_name': 'LungRot', 'life_threatening': True})
                if mutation in ('feed', 'changed_job'): s['combat']['colonists'][1]['current_job'] = 'FeedPatient' if mutation == 'feed' else 'Goto'
                if mutation == 'carry': s['combat']['colonists'][1]['carrying_pawn_id'] = 1
                if mutation == 'other_patient': row['target_id'] = 3
                if mutation == 'in_bed': s['development']['resilience']['patients'][0].update(in_bed=True, current_bed_id=row['bed_id'])
                self.assertIsNone(care.offered_care_yield(s, row))

    def test_target_bed_and_laydown_job_are_not_physical_arrival(self):
        s = snapshot(); s['colonists'][0]['current_job'] = 'LayDown'
        s['colonists'][0]['current_job_target_id'] = 100
        bed = {'id': 100, 'def': 'SleepingSpot', 'position': {'x': 184, 'z': 174}}
        self.assertFalse(d.patient_in_completed_bed(s['colonists'][0], s, [bed]))
        s['development']['resilience']['patients'][0].update(in_bed=True, current_bed_id=100)
        s['colonists'][0]['position'] = bed['position']
        self.assertTrue(d.patient_in_completed_bed(s['colonists'][0], s, [bed]))

    def test_prompt_front_contains_actual_temperature_and_nonwarming_tend_cost(self):
        s = snapshot(); row = s['development']['resilience']['options'][0]
        effects = r.thermal_rescue_effects(s['development']['resilience']['patients'][0], row)
        self.assertIn('-25C', effects['benefit'])
        self.assertIn('22C', effects['benefit'])
        self.assertIn('Tending frostbite does not remove cold', effects['inaction'])

    def test_refuel_prompt_has_actual_cold_room_and_not_only_auto_refuel(self):
        s = {'development': {'refuel_options': {'99': {'def': 'Campfire', 'current_temperature': -23,
                 'roofed': True, 'current_fuel': 0, 'fuel_capacity': 20, 'fuel_type': 'WoodLog', 'auto_refuel': True}}}}
        text = d.action_description('refuel_building', s)
        self.assertIn('-23C', text)
        self.assertIn('hypothermia can return', text)
        self.assertIn('Auto-refuel is a setting, not delivered fuel', text)

    def test_detailed_downed_doctor_is_excluded_when_combat_view_is_older(self):
        s = cold_state()
        s['colonists'][0]['downed'] = True
        self.assertNotIn('tend_358_361', d.post_combat_care_options(s))
        self.assertEqual(care.helpers(s, 358, doctor=True), [])

    def test_zero_local_population_offers_no_building_or_new_doctrine(self):
        s = {'game': {'tick': 934000}, 'map': {'id': 0}, 'colonists': [],
             'combat': {'colonists': []}, 'development': {}}
        actions, details = d.candidate_actions(None, s, {})
        self.assertEqual(actions, ['hold_survival'])
        self.assertNotIn('game_over', details)  # Native ending is still authoritative.

    def test_failed_pair_suppressed_while_other_patient_care_continues(self):
        s = cold_state(); s['combat']['colonists'][0].update(current_job='Wander', current_job_target_id=None)
        s['combat']['colonists'][2]['tendable_now'] = True
        for p in s['colonists']: p['health_conditions'] = [{'def_name': 'Cut', 'tendable_now': True}]
        memory = {}; client = Mock()
        client.get.return_value = []
        client.get.side_effect = lambda ep, **kw: copy.deepcopy(s['combat']) if ep.endswith('/combat/state') else []
        client.post.side_effect = bridge.RimApiError('Selected doctor cannot reserve and reach patient')
        with patch.object(d, 'collect_care_environment', return_value=[]), patch.object(d, 'collect_medical_thermal_context'), \
             patch.object(d, 'publish_post_combat_care_overlay'), patch.object(bridge, 'append_log'), patch('time.time', return_value=100):
            record = d.run_post_combat_care_cycle(client, Agent(), s, Path('unused'), map_state=memory)
            self.assertFalse(record['result']['applied'])
            failed_choice = record['decision']['choice']
            memory = json.loads(json.dumps(memory))
            record2 = d.run_post_combat_care_cycle(client, Agent(), s, Path('unused'), map_state=memory)
            self.assertNotEqual(record2['decision']['choice'], failed_choice)
            self.assertIn(failed_choice, memory['care_assignment_failures'])
            # Any new bleeding is material even below the coarse magnitude band.
            old = memory['care_assignment_failures'][failed_choice]['state']
            failed_plan = d.post_combat_care_options(s)[failed_choice]
            next(p for p in s['combat']['colonists'] if p['id'] == failed_plan['patient_id'])['bleeding_rate'] = .01
            self.assertNotEqual(care.care_failure_state(s, failed_plan), old)


if __name__ == '__main__': unittest.main()

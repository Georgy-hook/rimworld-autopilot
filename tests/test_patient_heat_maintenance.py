"""Cold bedside care and rejected cache footprints from Southern Thialdos."""
import copy
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import colony_director as d
import colony_medical_recovery as medical
from tests.test_hourly_regressions import hot_colony


def cold_bedside():
    s = hot_colony(wood=53)
    s['game']['tick'] = 220895
    s['development']['weather']['temperature'] = -10
    s['development']['rooms'][0].update(temperature=-3.38)
    s['development']['buildings'][-1].update({'def': 'Campfire'}, current_fuel=0,
        fuel_capacity=20, room_id=24, current_temperature=-3.38, roofed=True)
    s['colonists'][0].update(current_job='TendPatient', current_job_target_id=2,
        care_target_id=2, bleeding_rate=0, health_conditions=[])
    s['colonists'][1].update(current_bed_id=22, current_job_target_id=22,
        bleeding_rate=0, health_conditions=[{'def_name': 'Hypothermia', 'severity': .9},
                                          {'def_name': 'Frostbite', 'severity': 2, 'tendable_now': True}])
    s['combat'] = {'hostiles': [], 'colonists': [
        {**s['colonists'][0], 'is_dead': False, 'is_downed': False},
        {**s['colonists'][1], 'is_dead': False, 'is_downed': True}]}
    return s


class PatientHeatMaintenance(unittest.TestCase):
    def test_cold_room_keeps_completed_fire_ahead_of_new_heater(self):
        s = cold_bedside()
        memory = {'anchor': {'x': 10, 'z': 10}, 'issued': {}}
        choices, details = d.candidate_actions(None, s, memory)
        self.assertIn('refuel_building', choices)
        self.assertEqual(s['development']['cold_start_focus'], 'refuel_occupied_room')
        self.assertIn('1', d.refuel_worker_criteria(s))
        self.assertNotIn('1', d.worker_criteria(s, 'Hauling'))
        self.assertEqual(details['refuel_options']['50']['current_fuel'], 0)

    def test_nonempty_low_fuel_is_visible_before_fire_stops(self):
        s = cold_bedside()
        s['development']['buildings'][-1]['current_fuel'] = 4.9
        self.assertIn('50', d.routine_care_refuel_options(s, 1))
        s['development']['buildings'][-1]['current_fuel'] = 6
        self.assertFalse(d.routine_care_refuel_options(s, 1))

    def test_combat_display_labels_do_not_overwrite_clinical_cold_facts(self):
        s = cold_bedside()
        for pawn in s['combat']['colonists']:
            pawn['health_conditions'] = [h['def_name'] for h in pawn['health_conditions']]
        s['colonists'].reverse()
        s['combat']['colonists'].reverse()
        self.assertIn('50', d.routine_care_refuel_options(s, 1))
        choices, _ = d.candidate_actions(None, s, {'anchor': {'x': 10, 'z': 10}, 'issued': {}})
        self.assertIn('refuel_building', choices)

    def test_warm_routine_tend_with_combat_labels_does_not_crash(self):
        s = cold_bedside()
        s['colonists'][1]['health_conditions'] = [
            {'def_name': 'Bruise', 'severity': 4, 'tendable_now': True}]
        s['combat']['colonists'][0]['health_conditions'] = ['scratch scar']
        s['combat']['colonists'][1]['health_conditions'] = ['bruise (club head)']
        self.assertFalse(d.routine_care_refuel_options(s, 1))
        self.assertNotIn('1', d.refuel_worker_criteria(s))

    def test_display_labels_preserve_severe_hunger_for_either_exact_pawn(self):
        for index in (0, 1):
            with self.subTest(index=index):
                s = cold_bedside()
                s['colonists'][index]['health_conditions'].append(
                    {'def_name': 'Malnutrition', 'severity': .8})
                for pawn in s['combat']['colonists']:
                    pawn['health_conditions'] = ['display only']
                self.assertFalse(d.routine_care_refuel_options(s, 1))

    def test_display_labels_preserve_fresh_blood_and_protected_jobs(self):
        for change in (
                lambda s: s['combat']['colonists'][1].update(bleeding_rate=.2),
                lambda s: s['combat']['colonists'][0].update(current_job='FeedPatient'),
                lambda s: s['combat']['colonists'][0].update(current_job='Rescue'),
                lambda s: s['colonists'][1]['health_conditions'].append(
                    {'def_name': 'WoundInfection', 'immunity_can_develop': True,
                     'immunity': .4, 'tendable_now': True})):
            with self.subTest(change=change):
                s = cold_bedside()
                for pawn in s['combat']['colonists']:
                    pawn['health_conditions'] = ['display only']
                change(s)
                self.assertFalse(d.routine_care_refuel_options(s, 1))

    def test_unknown_clinical_conditions_defer_only_the_heat_transfer(self):
        for index in (0, 1):
            for conditions in (None, ['Hypothermia'], [{'def_name': 'Hypothermia', 'severity': .9}, 'unknown']):
                with self.subTest(index=index, conditions=conditions):
                    s = cold_bedside()
                    s['colonists'][index]['health_conditions'] = conditions
                    self.assertFalse(d.routine_care_refuel_options(s, 1))

    def test_heat_does_not_replace_protected_care_or_supplyless_errands(self):
        changes = [
            lambda s: s['combat']['colonists'][0].update(current_job='FeedPatient'),
            lambda s: s['combat']['colonists'][0].update(current_job='Rescue'),
            lambda s: s['combat']['colonists'][1].update(bleeding_rate=.2),
            lambda s: s['colonists'][1]['health_conditions'].append({'def_name': 'WoundInfection',
                'immunity_can_develop': True, 'immunity': .4, 'tendable_now': True}),
            lambda s: s['development']['rooms'][0].update(temperature=20),
            lambda s: s['development']['item_counts'].update(WoodLog=0),
            lambda s: s['combat']['colonists'][1].update(current_bed_id=None, current_job_target_id=None),
            lambda s: s['development']['buildings'][-1].update(room_id=999, position={'x': 100, 'z': 100}),
            lambda s: s['combat']['colonists'][0].update(moving=.3),
        ]
        for change in changes:
            with self.subTest(change=change):
                s = cold_bedside(); change(s)
                self.assertFalse(d.routine_care_refuel_options(s, 1))

    def test_fresh_blood_cancels_previously_feasible_refuel(self):
        s = cold_bedside(); fresh = copy.deepcopy(s)
        fresh['combat']['colonists'][1]['bleeding_rate'] = .2
        client = Mock()
        def get(endpoint, **kwargs):
            key = {'weather': 'weather', 'rooms': 'rooms', 'projects': 'construction_projects',
                   'buildings': 'buildings'}.get(endpoint.rsplit('/', 1)[-1])
            if endpoint.endswith('/things'):
                return [{'def_name': 'WoodLog', 'stack_count': 53}]
            value = fresh['development'].get(key, [])
            return {'rooms': value} if key == 'rooms' else {'projects': value} if key == 'construction_projects' else value
        client.get.side_effect = get
        details = {'refuel_options': {'50': s['development']['buildings'][-1]},
                   'worker_pawn': '1', 'refuel_target': '50'}
        with patch.object(d.bridge, 'collect_snapshot', return_value=fresh):
            result = d.execute_action(client, s, {'anchor': {'x': 10, 'z': 10}}, 'refuel_building', details)
        self.assertFalse(result['applied'])
        client.post.assert_not_called()

    def test_assisted_food_focus_retains_clinical_heat_choice(self):
        s = cold_bedside()
        s['development'].update(cold_start_focus='refuel_occupied_room',
            medical_action_options={'feed_hungry_colonist': {'2': {'helpers': {'1': {'food_feasible': True}}}}})
        s['colonists'][1]['hunger'] = 0
        actions = ['refuel_building', 'feed_hungry_colonist', 'build_temple']
        self.assertEqual(medical.focus(s, actions), actions[:2])


def cache_state():
    return {'game': {'tick': 1000}, 'map': {'id': 1}, 'colonists': [], 'combat': {},
            'development': {'buildings': [], 'construction_projects': []}}


class CacheFootprints(unittest.TestCase):
    def test_entire_native_rectangle_must_be_available(self):
        s = cache_state(); available = [0] * 400
        for z in range(5, 9):
            for x in range(5, 9): available[z*20+x] = 1
        runs = []
        for cell in available:
            if runs and runs[-1] == cell: runs[-2] += 1
            else: runs.extend([1, cell])
        s['development']['food_cache_terrain'] = {'width': 20, 'height': 20, 'stockpile_available_grid': runs}
        memory = {'anchor': {'x': 10, 'z': 10}}
        self.assertEqual(d.nearby_food_cache_site(None, s, memory), {'x': 5, 'z': 5})
        s['development']['construction_projects'] = [{'position': {'x': 7, 'z': 7}}]
        self.assertIsNone(d.nearby_food_cache_site(None, s, memory))

    def test_changed_zone_cancels_before_mutation_and_failed_ack_is_not_issued(self):
        s = cache_state(); client = Mock()
        client.get.return_value = {'width': 20, 'height': 20, 'stockpile_available_grid': [400, 0]}
        state = {'anchor': {'x': 10, 'z': 10}, 'issued': {}}
        details = {'food_cache_site': {'x': 5, 'z': 5}}
        result = d.execute_action(client, s, state, 'create_nearby_food_cache', details)
        self.assertFalse(result['applied']); client.post.assert_not_called()
        client.get.return_value['stockpile_available_grid'] = [400, 1]
        client.post.return_value = {'success': False}
        self.assertFalse(d.execute_action(client, s, state, 'create_nearby_food_cache', details)['applied'])
        self.assertNotIn('nearby_food_cache', state['issued'])

    def test_missing_or_incomplete_observation_does_not_invent_a_site(self):
        s = cache_state(); memory = {'anchor': {'x': 10, 'z': 10}}
        self.assertIsNone(d.nearby_food_cache_site(None, s, memory))
        s['development']['food_cache_terrain'] = {'width': 20, 'height': 20, 'stockpile_available_grid': [399, 1]}
        self.assertIsNone(d.nearby_food_cache_site(None, s, memory))


if __name__ == '__main__':
    unittest.main()

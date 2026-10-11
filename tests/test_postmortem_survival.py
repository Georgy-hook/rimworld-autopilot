"""Regressions from exhausted fuel, starvation commitments and pet shelter."""
import copy
import unittest
from unittest.mock import Mock

import colony_architect as architect
import colony_capabilities as caps
import colony_director as director
import colony_labor as labor
from tests.test_food_commitment import fixture
from tests.test_husbandry import barn_context
from tests.test_sustenance import Client
import colony_sustenance as sustenance


class SurvivalRegressions(unittest.TestCase):
    def test_starving_researcher_can_take_ready_food_but_not_steal_other_food(self):
        s = fixture()
        p = s['colonists'][0]
        p.update(current_job='Research')
        s['development']['plants'] = [{'harvestable_now': True}]
        memory = {}
        labor.prepare(s, memory)
        labor.remember(s, p['id'], 'Research')
        self.assertTrue(labor.can_assign(s, p, 'PlantCutting'))
        s['development']['sustenance'] = {'tables': []}
        self.assertFalse(labor.can_assign(s, p, 'Cooking'))  # Empty native queue.
        s['development']['sustenance'] = {'tables': [{'usable': True, 'bills': [{
            'recipe': 'CookMealSimple', 'food_product': True, 'requested': True,
            'block_reason': 'ready_for_ordinary_work', 'capable_worker_ids': [p['id']]}]}]}
        self.assertTrue(labor.can_assign(s, p, 'Cooking'))
        p['current_job'] = 'Harvest'
        labor.remember(s, p['id'], 'PlantCutting')
        self.assertFalse(labor.can_assign(s, p, 'Cooking'))
        p['current_job'] = 'Research'
        labor.remember(s, p['id'], 'Research')
        p.update(hunger=.9, health_conditions=[])
        s['map']['resources']['nutrition'] = 100
        self.assertFalse(labor.can_assign(s, p, 'PlantCutting'))

    def test_food_assignment_demotes_hauling_tie_and_preserves_doctor(self):
        s = fixture(); p = s['colonists'][0]
        p['work_priorities'].update({name: {'priority': 1, 'disabled': False}
                                    for name in ('Hauling', 'Cleaning', 'Doctor', 'Firefighter')})
        adjustments = caps.food_work_adjustments(s, p, 'PlantCutting')
        self.assertEqual(adjustments['Hauling'], 2)
        self.assertEqual(adjustments['Research'], 2)
        self.assertNotIn('Doctor', adjustments)
        self.assertNotIn('Firefighter', adjustments)
        p['current_job'] = 'FeedPatient'
        self.assertEqual(caps.food_work_adjustments(s, p, 'PlantCutting'), {})

    def test_marked_fuel_still_exposes_cutting_assignment(self):
        s = fixture(); p = s['colonists'][0]
        p['work_priorities']['PlantCutting']['priority'] = 2
        s['development'].update(building_counts={'Campfire': 1}, item_counts={'WoodLog': 0},
            plants=[{'thing_id': 80, 'harvested_thing_def': 'WoodLog', 'harvestable_now': True,
                     'is_designated_for_harvest': True, 'position': {'x': 10, 'z': 10}}])
        self.assertIn('prioritize_plant_cutting', director.focus_imminent_food_choices(
            s, ['prioritize_plant_cutting', 'prioritize_research']))

    def test_exhausted_local_timber_search_expands_in_a_bounded_batch(self):
        s = fixture()
        s['colonists'][0]['current_job'] = 'Research'
        s['development'].update(building_counts={'Campfire': 1}, item_counts={'WoodLog': 0},
            plants=[{'thing_id': i, 'def_name': 'SmashedStump', 'label': 'stump',
                     'harvested_thing_def': 'WoodLog', 'harvestable_now': True,
                     'harvest_yield': 3, 'position': {'x': 56 + i, 'z': 10}}
                    for i in range(12)])
        memory = {'anchor': {'x': 10, 'z': 10}, 'issued': {}}
        actions, details = director.candidate_actions(None, s, memory)
        self.assertIn('harvest_nearby_trees', actions)
        plan = details['tree_options']['SmashedStump']
        self.assertLessEqual(plan['planned_batch_count'], 8)
        self.assertGreater(plan['max_travel_cells'], 45)
        self.assertLessEqual(plan['max_travel_cells'], 90)
        s['development']['plants'].append({**s['development']['plants'][0], 'thing_id': 30,
                                          'position': {'x': 20, 'z': 10}})
        _, details = director.candidate_actions(None, s, {'anchor': memory['anchor'], 'issued': {}})
        self.assertEqual(details['tree_options']['SmashedStump']['planned_batch_ids'], [30])

    def test_sleeping_cat_needs_actual_completed_bed_for_patient_feed(self):
        cat = {'id': 4, 'hunger': 0, 'downed': False, 'current_job': 'LayDown'}
        s = {'development': {'buildings': [{'id': 9, 'def': 'AnimalSleepingSpot'}],
                            'sustenance': {'husbandry': {'animals': [{'id': 4, 'current_bed_id': None}]}}}}
        self.assertFalse(director.animal_patient_feed_ready(s, cat))
        s['development']['sustenance']['husbandry']['animals'][0]['current_bed_id'] = 9
        self.assertTrue(director.animal_patient_feed_ready(s, cat))
        s['development']['buildings'] = []
        self.assertFalse(director.animal_patient_feed_ready(s, cat))
        cat['current_job'] = 'GotoWander'
        self.assertFalse(director.animal_patient_feed_ready(s, cat))

    def test_single_pet_room_is_compact_and_cold_room_needs_heat_plan(self):
        c = barn_context()
        c.update(animals=[{'id': 4, 'requires_pen': False, 'comfortable_min': -25, 'comfortable_max': 40}],
                 outside_c=-38)
        plans = architect.animal_shelter_variants(c)
        self.assertTrue(plans)
        for plan in plans.values():
            self.assertEqual((plan['width'], plan['height']), (5, 5))
            self.assertNotIn('no_heater', plan['id'])
            self.assertEqual(architect.layout_anchor_conflicts(plan['layout']), [])
        c['outside_c'] = 10
        c['sustenance']['husbandry']['seasonal_means'] = []
        self.assertTrue(any('no_heater' in p for p in architect.animal_shelter_variants(c)))

    def test_rotated_bed_blocks_its_native_occupied_cells(self):
        bed = {'id': 7, 'def': 'Bed', 'rotation': 1, 'position': {'x': 10, 'z': 10},
               'size': {'x': 1, 'z': 2}, 'occupied_cells': [{'x': 10, 'z': 10}, {'x': 11, 'z': 10}]}
        expected = {(10, 10), (11, 10)}
        self.assertEqual(director.building_occupied_cells(bed), expected)
        dev = {'buildings': [bed], 'construction_projects': [], 'rooms': [{'contained_beds_ids': [7],
               'open_roof_count': 0, 'cells': [{'x': x, 'z': z} for x in (10, 11) for z in (10, 11)]}]}
        self.assertEqual(director.architecture_occupied_cells(dev, {}), expected)
        self.assertIsNone(director.empty_indoor_sleeping_spot(dev))

    def test_shared_room_needs_no_builder_and_rechecks_native_availability(self):
        key = 'warmspot:4:21:21'
        native = {'available': True, 'options': [{'key': key, 'kind': 'warmspot',
                  'target_id': 4, 'value': '21,21', 'label': 'Share roofed room at 21C'}]}
        s = {'map': {'id': 0}, 'game': {'tick': 60000}, 'colonists': [],
             'development': {'sustenance': native, 'animal_barn_options': {'plans': {
                 'shared|' + key: {'kind': 'shared_shelter', 'sustenance_key': key}}}}}
        memory = {'anchor': {'x': 10, 'z': 10}}; sustenance.prepare(s, memory)
        self.assertFalse(director.requires_builder_now('build_animal_barn', s))
        details = {'animal_barn_plan': 'shared|' + key,
                   'animal_barn_options': s['development']['animal_barn_options']}
        client = Client(copy.deepcopy(native))
        result = director.execute_action(client, s, memory, 'build_animal_barn', details)
        self.assertTrue(result['applied'])
        self.assertEqual(client.posts, [{'map_id': 0, 'key': key}])
        client = Client({'available': True, 'options': []})
        result = director.execute_action(client, s, {'anchor': {'x': 10, 'z': 10}}, 'build_animal_barn', details)
        self.assertFalse(result['applied'])
        self.assertEqual(client.posts, [])

    def test_open_bed_site_respects_rotated_native_footprint(self):
        terrain = {'width': 30, 'height': 30, 'palette': ['Soil'], 'grid': [900, 0]}
        bed = {'position': {'x': 10, 'z': 10}, 'size': {'x': 1, 'z': 2},
               'occupied_cells': [{'x': 10, 'z': 10}, {'x': 11, 'z': 10}]}
        site = director.open_bed_site(terrain, {'x': 10, 'z': 0}, {'buildings': [bed]})
        self.assertIsNotNone(site)
        self.assertFalse({(site['x'], site['z']), (site['x'], site['z'] + 1)} & {(10, 10), (11, 10)})


if __name__ == '__main__':
    unittest.main()

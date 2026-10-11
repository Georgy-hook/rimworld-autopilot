"""Sequential food/crop regressions with native endpoint DTO shapes."""
import copy
import json
import unittest
from unittest.mock import patch

import colony_capabilities as caps
import colony_director as director
import stream_observer as observer
import colony_sustenance as sustenance
from tests.test_capabilities import snapshot, crop, growing_site, Client


def fixture():
    s = snapshot()
    s['map']['resources'] = {'food': 0, 'meals': 0, 'raw_food': 0, 'nutrition': 0}
    s['colonists'][0].update(hunger=0, current_job='Repair', health_conditions=[{'def_name': 'Malnutrition', 'severity': .6}])
    s['colonists'][0]['work_priorities'].update({name: {'priority': 1, 'disabled': False}
                                              for name in ('Cooking', 'Hunting', 'Construction', 'Research', 'Growing', 'PlantCutting')})
    s['combat'] = {'colonists': [], 'hostiles': []}
    rice = {**crop(), 'human_edible_product': True, 'product_nutrition': .05, 'legal_cells': 200}
    hops = {**crop('Plant_Hops'), 'category': 'beer', 'human_edible_product': False}
    site = growing_site(plant='Plant_Rice', plant_count=0, options=[rice, hops])
    s['development']['plant_catalog'] = {'plants': [rice, hops], 'growers': [site]}
    return s


class FoodCommitmentTests(unittest.TestCase):
    def test_first_field_deadline_includes_growth_before_reserve_runs_out(self):
        s = fixture()
        s['map']['resources']['nutrition'] = 6.4  # Four days, before starvation.
        s['colonists'][0].update(hunger=.9, health_conditions=[])
        s['development']['plant_catalog']['growers'] = [growing_site(kind='new_ground', plant=None, options=[crop()])]
        caps.prepare(s, {})
        actions = ['create_growing_zone', 'harvest_local_plants', 'prioritize_growing', 'society_ritual', 'advance_doctrine_research']
        self.assertEqual(director.focus_imminent_food_choices(s, actions), actions[:3])
        self.assertIn('Construction', director.food_work_adjustments(s, s['colonists'][0], 'Growing'))
        s['colonists'][0]['current_job'] = 'Sow'
        self.assertEqual(director.food_work_adjustments(s, s['colonists'][0], 'Growing'), {})
        s['map']['resources']['nutrition'] = 20
        self.assertEqual(director.focus_imminent_food_choices(s, actions), actions)

    def test_empty_policy_preparation_yields_to_food_and_new_patient_reopens(self):
        s = fixture()
        care = {'key': 'care:4:2', 'kind': 'care', 'target_id': 4, 'value': '2'}
        shelf = {'key': 'stockpile:1:4', 'kind': 'stockpile', 'target_id': 1, 'value': '4'}
        clean = {'key': 'job:CleanFilth:1:9', 'kind': 'job', 'target_id': 9, 'value': 'CleanFilth:1'}
        c = {'available': True, 'options': [care, shelf, clean], 'human_food': [],
             'animals': [{'id': 4, 'food': .9, 'downed': False, 'health': []}],
             'tables': [{'id': 8, 'usable': True, 'bills': [{'requested': True, 'block_reason': 'ingredients_short'}]}]}
        s['development']['sustenance'] = c
        memory = {}
        self.assertEqual(sustenance.prepare(s, memory), [])
        # Same options immediately become relevant for a new sick animal.
        c['animals'][0]['health'] = [{'def_name': 'Flu', 'severity': .5, 'life_threatening': True}]
        self.assertEqual(sustenance.prepare(s, memory), ['sustenance_animal_welfare'])
        c['human_food'] = [{'def_name': 'RawRice', 'fresh_eligible_nutrition': .5}]
        c['tables'][0]['bills'][0]['block_reason'] = 'ready_for_ordinary_work'
        self.assertEqual(set(sustenance.prepare(s, memory)), {'sustenance_animal_welfare', 'sustenance_food_batch', 'sustenance_preservation'})
        # A stale cleaning choice is declined after fresh ingredients disappear.
        class Transport:
            def __init__(self): self.posts = []
            def get(self, *args, **kwargs):
                return {**c, 'tables': [{'usable': True, 'bills': [{'requested': True, 'block_reason': 'ingredients_short'}]}], 'prepared_options': {}}
            def post(self, *args, **kwargs): self.posts.append(kwargs)
        client = Transport()
        result = sustenance.execute(client, s, memory, 'sustenance_food_batch', {'sustenance_policy': clean['key']})
        self.assertEqual(result['reason'], 'food_crisis_prerequisite_changed')
        self.assertEqual(client.posts, [])
        # Healthy animals and kitchen preparation are available again with a
        # real reserve; no hidden category cooldown prevents normal planning.
        c['animals'][0]['health'] = []
        s['map']['resources']['nutrition'] = 50
        s['colonists'][0].update(hunger=.9, health_conditions=[])
        self.assertIn('sustenance_animal_welfare', sustenance.prepare(s, memory))

    def test_future_capacity_cannot_release_empty_food_protection(self):
        s = fixture()
        need = caps.food_planning_facts(s)
        self.assertGreater(need['potential_crop_nutrition_per_day'], need['human_demand_per_day'])
        self.assertFalse(need['crop_capacity_gap'])
        self.assertTrue(need['protect_food_supply'])
        self.assertEqual(caps.crop_sites(s, False), {})
        # Accepted but unsown food is retained; more fields do not bridge today.
        s['development']['plant_catalog']['growers'].append(growing_site(kind='new_ground', plant=None, options=[crop()]))
        self.assertEqual(caps.crop_sites(s, True), {})

    def test_no_capacity_offers_only_native_human_food_and_climate_can_reopen(self):
        s = fixture()
        site = s['development']['plant_catalog']['growers'][0]
        site['plant_def'] = 'Plant_Hops'
        self.assertEqual(set(caps.crop_sites(s, False)[site['id']]['crop_options']), {'Plant_Rice'})
        site['plant_def'] = 'Plant_Rice'
        site['options'][0]['safe_sowing_now'] = False
        self.assertEqual(caps.crop_sites(s, False), {})  # No other viable human food.
        alternative = {**crop('ModWinterFood'), 'human_edible_product': True, 'product_nutrition': .05}
        s['development']['plant_catalog']['plants'].append(alternative)
        site['options'].append(alternative)
        self.assertIn('ModWinterFood', caps.crop_sites(s, False)[site['id']]['crop_options'])

    @patch('colony_retry.time.time', return_value=100)
    def test_configuration_dwell_spans_sites_actors_speed_and_rollback(self, clock):
        s = fixture()
        s['map']['resources']['nutrition'] = 50
        s['colonists'][0].update(hunger=1, health_conditions=[])
        site = s['development']['plant_catalog']['growers'][0]
        site['plant_def'] = 'Plant_Cotton'
        s['development']['plant_catalog']['growers'].append(growing_site(id='zone:8', zone_id=8, plant='Plant_Rice', options=site['options']))
        memory = {}
        caps.prepare(s, memory)
        result = caps.execute(Client(), s, memory, 'configure_crop', {'crop_site': site['id'], 'crop_type': 'Plant_Hops', 'crop_worker': '1'})
        self.assertTrue(result['applied'])
        site['plant_def'] = 'Plant_Hops'
        s['development']['plant_catalog']['growers'].append(growing_site(id='zone:9', zone_id=9, plant='Plant_Hops', options=site['options']))
        memory = json.loads(json.dumps(memory))
        s['game']['tick'] += 40000
        clock.return_value = 110
        self.assertNotIn('configure_crop', caps.prepare(s, memory))
        # Real new shortage releases a prior commercial choice immediately.
        s['map']['resources']['nutrition'] = 0
        self.assertNotIn('configure_crop', caps.prepare(s, memory))
        s['development']['plant_catalog']['growers'] = [row for row in s['development']['plant_catalog']['growers'] if row['id'] != 'zone:8']
        self.assertIn('configure_crop', caps.prepare(s, memory))
        self.assertTrue(all(set(v['crop_options']) == {'Plant_Rice'} for v in s['development']['capability_plans']['configure_crop'].values()))
        s['game']['tick'] = 1
        caps.prepare(s, memory)
        self.assertNotIn('crop_configuration', memory['capability_history'])

    def test_food_focus_keeps_immediate_sources_and_blocks_optional_work_without_source(self):
        s = fixture()
        actions = ['configure_crop', 'create_growing_zone', 'harvest_local_plants', 'advance_doctrine_research', 'resilience_feed']
        self.assertEqual(director.focus_imminent_food_choices(s, actions), ['harvest_local_plants', 'resilience_feed'])
        self.assertEqual(director.focus_imminent_food_choices(s, ['advance_doctrine_research', 'society_ritual']), ['hold_survival'])
        s['map']['resources']['nutrition'] = 50
        self.assertEqual(director.focus_imminent_food_choices(s, actions), actions)

    def test_fire_without_capable_actor_keeps_guarded_food_options(self):
        s = fixture()
        s['colonists'][0]['work_priorities']['Firefighter'] = {'priority': 1, 'disabled': True}
        actions = ['harvest_local_plants', 'resilience_feed', 'hold_survival', 'expand_home_area']
        self.assertEqual(director.focus_active_fire_choices(actions, True, s), actions[:-1])
        s['colonists'][0]['work_priorities']['Firefighter']['disabled'] = False
        self.assertNotIn('harvest_local_plants', director.focus_active_fire_choices(actions, True, s))

    def test_event_harvest_uses_native_harvestability_and_verified_edible_product(self):
        s = fixture()
        s['development']['plants'] = [
            {'thing_id': 11, 'def_name': 'Plant_Rice', 'harvestable_now': True, 'harvested_thing_def': 'Rice', 'harvest_yield': 6},
            {'thing_id': 12, 'def_name': 'Plant_Rice', 'harvestable_now': False, 'growth': 1, 'harvested_thing_def': 'Rice', 'harvest_yield': 6},
            {'thing_id': 13, 'def_name': 'Plant_Rice', 'harvestable_now': True, 'is_designated_for_harvest': True, 'harvested_thing_def': 'Rice', 'harvest_yield': 6},
            {'thing_id': 14, 'def_name': 'TreeOak', 'harvestable_now': True, 'harvested_thing_def': 'WoodLog', 'harvest_yield': 20}]
        client = Client()
        director._execute_event_response(client, s, {}, {}, {}, 'emergency_harvest', {})
        self.assertEqual(client.calls, [('/api/v1/map/plants/harvest', {'body': {'map_id': 0, 'plant_ids': [11]}})])

    def test_priority_one_collision_yields_only_selected_worker_and_does_not_restart_harvest(self):
        s = fixture()
        s['development']['plants'] = [{'thing_id': 11, 'harvestable_now': True}]
        pawn = s['colonists'][0]
        self.assertIn('Construction', director.food_work_adjustments(s, pawn, 'PlantCutting'))
        self.assertEqual([p['id'] for p in director.priority_deficit_workers(s, 'PlantCutting')], [1])
        class Transport:
            def __init__(self): self.posts = []
            def post(self, path, *, body):
                self.posts.append(body)
                pawn['work_priorities'][body['work']]['priority'] = body['priority']
                return {'success': True}
            def get(self, path):
                return [{'pawn': {'id': pawn['id'], 'name': 'Worker'}, 'detailes': {
                    'work_info': {'work_priorities': [{'work_type': name, 'priority': setting['priority'],
                                                      'is_totally_disabled': setting.get('disabled', False)}
                                                     for name, setting in pawn['work_priorities'].items()]}}}]
        client = Transport()
        result = director.prioritize(client, s, 'PlantCutting', 1)
        self.assertTrue(result['applied'])
        self.assertTrue(all(b['id'] == 1 for b in client.posts))
        self.assertFalse(any(b['work'] in {'Doctor', 'Patient', 'Firefighter'} for b in client.posts))
        pawn['current_job'] = 'HarvestDesignated'
        self.assertEqual(director.food_work_adjustments(s, pawn, 'PlantCutting'), {})
        self.assertEqual(director.priority_deficit_workers(s, 'PlantCutting'), [])
        pawn['current_job'] = 'FeedPatient'
        self.assertFalse(director.prioritize(client, s, 'PlantCutting', 1)['applied'])

    def test_death_queued_behind_another_overlay_has_one_caption(self):
        planner = observer.ObserverPlanner()
        s = {'game': {'game_tick': 100}, 'map': {'id': 0, 'seed': 1},
             'colonists': [{'id': 1, 'name': 'One'}, {'id': 2, 'name': 'Two'}]}
        planner.step(s, [], 0)
        event = {'id': 1, 'name': 'One', 'cause': 'Malnutrition', 'ticks': 101}
        s['game']['game_tick'] = 101
        s['colonists'] = [s['colonists'][1]]
        planner.step(s, [event], 1)
        s['colonists'] = []
        s['corpses'] = [{'label': 'Two corpse', 'def_name': 'Corpse_Human'}]
        for now in range(2, 12):
            planner.step(s, [], now)
        self.assertEqual([r['id'] for r in planner.death_queue], [2])
        actions = planner.step(s, [], 30)
        self.assertEqual(len([a for a in actions if a['kind'] == 'caption']), 1)
        self.assertFalse(any(a['kind'] == 'caption' for a in planner.step(s, [], 60)))


if __name__ == '__main__':
    unittest.main()

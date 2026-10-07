"""Sequences behind the 7 October playtest; no game or model is launched."""
import copy
import json
import unittest
from unittest.mock import Mock, patch

import colony_capabilities as caps
import colony_director as director
import colony_medical_recovery as medical
from test_capabilities import snapshot, crop, growing_site


class RoinorRecovery(unittest.TestCase):
    def test_exact_unstarted_rescue_can_yield_but_pickup_and_draft_block_tending(self):
        patient = {'id': 1, 'is_downed': True, 'tendable_now': True, 'bleeding_rate': 4.0,
                   'position': {'x': 10, 'z': 10}}
        doctor = {'id': 2, 'current_job': 'Rescue', 'current_job_target_id': 1,
                  'moving': 1, 'manipulation': 1, 'position': {'x': 11, 'z': 10}}
        s = {'map': {'id': 0}, 'colonists': [], 'combat': {'hostiles': [], 'colonists': [patient, doctor]}}
        plan = director.post_combat_care_options(s)['tend_1_2']
        self.assertEqual(plan['reassign_from_rescue_patient_id'], 1)
        client = Mock()
        client.get.side_effect = lambda *a, **kw: copy.deepcopy(s['combat'])
        changed, _ = medical.validate_post_combat_plan(client, s, plan, director.post_combat_care_options)
        self.assertIsNone(changed)
        doctor['carrying_pawn_id'] = 1
        self.assertNotIn('tend_1_2', director.post_combat_care_options(s))
        changed, _ = medical.validate_post_combat_plan(client, s, plan, director.post_combat_care_options)
        self.assertFalse(changed['assignment_accepted'])
        doctor.pop('carrying_pawn_id')
        doctor['is_drafted'] = True
        self.assertNotIn('tend_1_2', director.post_combat_care_options(s))
        self.assertFalse(medical.validate_post_combat_plan(client, s, plan, director.post_combat_care_options)[0]['assignment_accepted'])
        client.post.assert_not_called()

    def test_care_owns_actor_while_spare_worker_can_gather_food(self):
        s = snapshot()
        s['colonists'] = [
            {'id': 1, 'downed': True, 'hunger': .1},
            {'id': 2, 'current_job': 'FeedPatient'},
            {'id': 3, 'current_job': 'HarvestDesignated'}]
        s['combat']['colonists'] = [{'id': 2, 'current_job': 'FeedPatient', 'care_target_id': 1}]
        s['development']['resilience'] = {'active_orders': [{'worker_id': 2, 'target_id': 1, 'kind': 'feed'}]}
        choices = ['harvest_local_plants', 'create_growing_zone', 'hold_survival']
        self.assertEqual(medical.focus(s, choices), choices)
        s['colonists'].pop()
        self.assertEqual(medical.focus(s, choices), ['hold_survival'])

    def test_food_planning_survives_module_dispatch_and_shows_timber_yield(self):
        s = snapshot()
        s['map']['resources'] = {'food': 0, 'nutrition': 0}
        s['development']['capability_plans'] = {'harvest_at_risk_crops': {
            'products': {'WoodLog': 90}, 'expected_human_nutrition': 0}}
        text = director.action_description('harvest_at_risk_crops', s)
        self.assertIn('WoodLog', text)
        self.assertIn('nutrition 0', text)
        text = director.action_description('create_growing_zone', s)
        self.assertIn('human demand 1.6', text)
        self.assertIn('flowers supply zero', text)
        choices = ['harvest_local_plants', 'create_growing_zone', 'connect_power_consumer', 'care_for_injured_animal', 'build_sculpture']
        self.assertEqual(director.focus_imminent_food_choices(s, choices), choices[:-1])

    def test_dying_plant_batch_is_small_and_product_not_label_drives_food(self):
        s = snapshot()
        s['development']['plant_catalog']['plants'] = [
            {'def_name': 'Tree', 'harvested_thing': 'WoodLog', 'product_nutrition': 0},
            {'def_name': 'Hay', 'harvested_thing': 'Hay', 'human_edible_product': False, 'product_nutrition': .05},
            {'def_name': 'Berries', 'harvested_thing': 'RawBerries', 'human_edible_product': True, 'product_nutrition': .05}]
        s['development']['plants'] = [
            {'thing_id': i, 'def_name': 'Tree', 'harvested_thing_def': 'WoodLog', 'harvest_yield': 30,
             'harvestable_now': True, 'dying': True, 'position': {'x': 52+i, 'z': 50}}
            for i in range(30)]
        memory = {}
        caps.prepare(s, memory)
        plan = s['development']['capability_plans']['harvest_at_risk_crops']
        self.assertEqual(len(plan['plants']), 12)
        self.assertEqual(plan['expected_human_nutrition'], 0)
        self.assertEqual(caps.harvest_products(s, [{'def_name': 'Hay', 'harvested_thing_def': 'Hay', 'harvest_yield': 20}])['expected_human_nutrition'], 0)
        self.assertEqual(caps.harvest_products(s, [{'def_name': 'Berries', 'harvested_thing_def': 'RawBerries', 'harvest_yield': 20}])['expected_human_nutrition'], 1)

    def test_food_capacity_deficit_keeps_food_choices_and_later_unlocks_other_crops(self):
        s = snapshot()
        rice = {**crop(), 'human_edible_product': True, 'product_nutrition': .05}
        rose = {**crop('Plant_Rose'), 'human_edible_product': False, 'category': 'beauty'}
        s['development']['plant_catalog'] = {'plants': [rice, rose], 'growers': [
            growing_site('new_ground', options=[rice, rose]) ]}
        s['map']['resources'] = {'food': 0, 'nutrition': 0}
        self.assertEqual(set(caps.crop_sites(s, True)['new_indoor_ground']['crop_options']), {'Plant_Rice'})
        s['map']['resources'] = {'food': 30, 'nutrition': 27}
        self.assertEqual(set(caps.crop_sites(s, True)['new_indoor_ground']['crop_options']), {'Plant_Rice', 'Plant_Rose'})

    def test_deferral_persists_fast_clock_and_rollbacks_invalidate_future(self):
        s = snapshot()
        memory = {}
        with patch('time.time', return_value=1000):
            caps._remember(s, memory, 'plan_colonist_augmentation:1', 30000)
            memory['capability_history']['plan_colonist_augmentation:1'].update(
                {'retry_started_at': 1000, 'retry_until': 1120})
        memory = json.loads(json.dumps(memory))
        s['game']['tick'] += 45000
        with patch('time.time', return_value=1030):
            caps._prune(s, memory)
        self.assertIn('plan_colonist_augmentation:1', memory['capability_history'])
        s['game']['tick'] = 100
        caps._prune(s, memory)
        self.assertFalse(memory['capability_history'])

    def test_rejected_bed_assignment_does_not_claim_success(self):
        s = snapshot()
        s['development']['bed_assignment_options'] = {'1|20': {}}
        client = Mock()
        client.post.return_value = {'success': False}
        # Build real options using an occupied sleeping spot and a free bed.
        s['colonists'][0]['current_job'] = 'LayDown'
        s['combat']['colonists'][0].update(is_drafted=False, current_job_target_id=10)
        s['development']['buildings'] = [{'id': 10, 'def': 'SleepingSpot'}, {'id': 20, 'def': 'Bed'}]
        s['development']['real_bed_options'] = {'1|20': {'pawn_id': 1, 'bed_id': 20}}
        result = director.execute_action(client, s, {'anchor': {'x': 50, 'z': 50}}, 'assign_real_bed', {'bed_assignment': '1|20'})
        self.assertFalse(result['applied'])


if __name__ == '__main__':
    unittest.main()

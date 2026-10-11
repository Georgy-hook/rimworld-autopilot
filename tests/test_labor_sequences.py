import copy
import json
import unittest
from unittest.mock import patch
import colony_director as director
import colony_labor as labor
import rimworld_laya as bridge
from tests.test_food_commitment import fixture


class LaborSequences(unittest.TestCase):
    def queue(self, s, recipe='CookMealSimple', reason='ready_for_ordinary_work'):
        s['development']['sustenance'] = {'available': True, 'tables': [{'usable': True, 'bills': [
            {'recipe': recipe, 'food_product': recipe.startswith('Cook'), 'requested': True,
             'block_reason': reason, 'capable_worker_ids': [1]}]}]}

    @patch('colony_retry.time.time', return_value=100)
    def test_assignment_prevents_opposite_role_until_both_clocks_or_source_change(self, clock):
        s, memory = fixture(), {}
        self.queue(s)
        labor.prepare(s, memory)
        labor.remember(s, 1, 'Cooking')
        self.assertEqual(director.priority_deficit_workers(s, 'Hunting'), [])
        s['game']['tick'] += 40000
        clock.return_value = 110
        memory = json.loads(json.dumps(memory))
        labor.prepare(s, memory)
        self.assertFalse(labor.can_assign(s, s['colonists'][0], 'Hunting'))
        clock.return_value = 230
        labor.prepare(s, memory)
        self.assertTrue(labor.can_assign(s, s['colonists'][0], 'Hunting'))
        labor.remember(s, 1, 'Cooking')
        self.queue(s, reason='ingredients_short')
        labor.prepare(s, memory)
        self.assertTrue(labor.can_assign(s, s['colonists'][0], 'Hunting'))
        self.assertFalse(labor.can_assign(s, s['colonists'][0], 'Cooking'))
        self.queue(s)
        self.assertTrue(labor.can_assign(s, s['colonists'][0], 'Cooking'))

    def test_current_hunt_and_care_are_not_restarted_or_stolen(self):
        s = fixture()
        self.queue(s)
        s['colonists'][0]['current_job'] = 'Hunt'
        self.assertEqual(director.priority_deficit_workers(s, 'Cooking'), [])
        s['colonists'][0]['current_job'] = 'FeedPatient'
        self.assertEqual(director.priority_deficit_workers(s, 'Cooking'), [])

    def test_burn_only_and_empty_queues_are_not_cooking(self):
        s = fixture()
        self.queue(s, recipe='BurnApparel')
        self.assertEqual(director.priority_deficit_workers(s, 'Cooking'), [])
        s['development']['sustenance']['tables'][0]['bills'] = []
        self.assertEqual(director.priority_deficit_workers(s, 'Cooking'), [])
        self.queue(s, reason='work_disabled')
        s['colonists'][0]['work_priorities']['Cooking']['priority'] = 0
        self.assertEqual([p['id'] for p in director.priority_deficit_workers(s, 'Cooking')], [1])

    @patch('colony_retry.time.time', return_value=100)
    def test_rollback_and_new_actor_do_not_inherit_commitment(self, clock):
        s, memory = fixture(), {}
        self.queue(s)
        labor.prepare(s, memory)
        labor.remember(s, 1, 'Cooking')
        other = copy.deepcopy(s['colonists'][0]); other['id'] = 2
        self.assertTrue(labor.can_assign(s, other, 'Hunting'))
        s['game']['tick'] -= 1
        labor.prepare(s, memory)
        self.assertEqual(memory['labor_commitments'], {})

    def test_actual_capacity_replaces_aggregate_health_gate(self):
        s = fixture(); p = s['colonists'][0]
        p.update(health=.698, capacities={'moving':.8,'manipulation':.8,'consciousness':1}, bleeding_rate=0)
        self.assertEqual(bridge.choose_worker([p], 'Cooking'), p)
        p.update(health=1, capacities={'moving':.22,'manipulation':.34,'consciousness':1})
        self.assertIsNone(bridge.choose_worker([p], 'Hunting'))
        p['in_mental_state'] = True
        self.assertIsNone(bridge.choose_worker([p], 'Cooking'))

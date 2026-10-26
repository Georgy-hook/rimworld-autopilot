"""Replayable boundaries for firing, repeated services and stale targets."""
import copy
import unittest
from unittest.mock import patch

import colony_director as director
import colony_society as society
import colony_storage as storage
import rimworld_laya as bridge
from test_capabilities import snapshot


class Client:
    def __init__(self, things=None, terrain=None, error=None):
        self.things = things
        self.terrain = terrain
        self.error = error
        self.posts = []

    def get(self, endpoint, **kwargs):
        return self.terrain if endpoint == '/api/v1/map/terrain' else self.things

    def post(self, endpoint, **kwargs):
        self.posts.append((endpoint, kwargs))
        if self.error:
            raise director.bridge.RimApiError(self.error)
        return {'success': True}


def corpse_state():
    s = snapshot()
    s['development'].update(buildings=[], construction_projects=[], building_counts={},
        corpses=[{'thing_id':8, 'categories':['CorpsesAnimal'], 'rot_stage':'Fresh',
                  'is_forbidden':True, 'position':{'x':30, 'z':30}}])
    return s, {'anchor':{'x':10, 'z':10}, 'issued':{}}


class ServiceRegressions(unittest.TestCase):
    def test_generic_human_corpse_edibility_does_not_expand_native_food_reserve(self):
        s = snapshot()
        s['development']['production'] = {'perishables':[
            {'id':8,'def_name':'Corpse_Human','nutrition':5,'human_edible':True,'rot_stage':'Fresh'},
            {'id':9,'def_name':'RawRice','nutrition':10,'human_edible':True,'rot_stage':'Fresh'}]}
        s['development']['sustenance'] = {'available':True,'human_food':[
            {'def_name':'RawRice','fresh_eligible_nutrition':10}]}
        self.assertEqual(storage.food_condition_facts(s,1.6)['observed_food_nutrition'],10)
        s['development']['sustenance']['human_food'] = []
        self.assertEqual(storage.food_condition_facts(s,1.6)['observed_food_nutrition'],0)

    def test_remote_corpse_does_not_require_another_butchery(self):
        s, state = corpse_state()
        s['development']['corpses'][0]['is_forbidden'] = False
        s['development']['building_counts']['ButcherSpot'] = 1
        client = Client()
        result = director.execute_action(client, s, state, 'build_butcher_spot', {})
        self.assertFalse(result['applied'])
        self.assertEqual(client.posts, [])

    def test_unfinished_butcher_table_suppresses_duplicate_station(self):
        self.assertTrue(director.butchery_station_present({'construction_projects':[
            {'def_name':'TableButcher','kind':'frame'}]}))
        self.assertFalse(director.butchery_station_present({'construction_projects':[
            {'def_name':'Campfire','kind':'frame'}]}))

    def test_consumed_corpse_is_not_sent_to_the_action_api(self):
        s, state = corpse_state()
        client = Client(things=[])
        self.assertFalse(director.execute_action(client, s, state, 'unforbid_corpses', {})['applied'])
        self.assertEqual(client.posts, [])

    def test_fresh_unforbid_stays_with_the_selected_targets(self):
        s, state = corpse_state()
        client = Client(things=[{'thing_id':8,'is_forbidden':True},
                                {'thing_id':9,'is_forbidden':True}])
        self.assertTrue(director.execute_action(client, s, state, 'unforbid_corpses', {})['applied'])
        self.assertEqual(client.posts[0][1]['body']['thing_ids'], [8])

    def test_unavailable_fresh_read_is_not_empty_success(self):
        s, state = corpse_state()
        client = Client(things={'available':False,'error':'read failed'})
        result = director.execute_action(client, s, state, 'unforbid_corpses', {})
        self.assertFalse(result['applied'])
        self.assertIn('unavailable', result['reason'])
        self.assertEqual(client.posts, [])

    def test_disappearance_between_recheck_and_post_is_deferred(self):
        s, state = corpse_state()
        client = Client(things=[{'thing_id':8,'is_forbidden':True}],
                        error='HTTP 404: Thing 8 not found')
        result = director.execute_action(client, s, state, 'unforbid_corpses', {})
        self.assertFalse(result['applied'])
        self.assertEqual(result['reason'], 'corpse_changed_before_unforbid')

    def test_corrupt_terrain_never_creates_a_guessed_stockpile(self):
        s, state = corpse_state()
        client = Client(terrain={'width':30,'height':30})
        with patch('colony_storage.carcass_site', return_value=(10,10)):
            result = director.execute_action(client, s, state, 'create_animal_corpse_dump', {})
        self.assertFalse(result['applied'])
        self.assertIn('animal_corpse_dump', state['spatial_retries'])
        self.assertEqual(client.posts, [])


class CombatReadbackRegressions(unittest.TestCase):
    def test_already_drafted_without_an_order_is_not_applied(self):
        response = {'applied':False,'drafted_pawn_ids':[1],
                    'positioned_pawn_ids':[],'attacking_pawn_ids':[]}
        result = bridge.command_result([{'endpoint':'/api/v1/combat/tactic'}], [response])
        self.assertFalse(result['applied'])
        self.assertFalse(bridge.combat_tactical_acceptance(response))

    def test_preserved_exact_attack_is_not_a_failed_attempt_or_new_order(self):
        response = {'applied':False,'preserved_pawn_ids':[1],
                    'attacking_pawn_ids':[1],'positioned_pawn_ids':[]}
        self.assertTrue(bridge.combat_tactical_acceptance(response))
        result = bridge.command_result([{'endpoint':'/api/v1/combat/tactic'}], [response])
        self.assertFalse(result['applied'])
        self.assertTrue(result['order_preserved'])
        self.assertEqual(result['completion'], 'unverified')

    def test_preserved_id_without_observed_order_is_not_trusted(self):
        self.assertFalse(bridge.combat_tactical_acceptance(
            {'applied':False,'preserved_pawn_ids':[1],'attacking_pawn_ids':[]}))


class PolicyCommitmentRegressions(unittest.TestCase):
    def prepare_assignment(self):
        person = {'pawn_id':1,'needs':[{'def_name':'Food','level':.6}],
                  'drugs':{'policy_id':1,'entries':[]},'conditions':[]}
        context = {'available':True,'people':[person],
                   'native_options':[{'kind':'drug_policy','pawn_id':1,'value':'2'}]}
        s = {'game':{'tick':100},'map':{'id':0},'development':{'society':copy.deepcopy(context)}}
        state = {}
        class PolicyClient:
            def get(self, *args, **kwargs): return copy.deepcopy(context)
            def post(self, *args, **kwargs): return {'applied':True}
        with patch('colony_retry.time.time', return_value=1000):
            society.execute(PolicyClient(),s,state,'society_drug_policy',
                            {'kind':'drug_policy','pawn_id':1,'value':'2'})
        context['people'][0]['drugs']['policy_id'] = 2
        context['native_options'][0]['value'] = '1'
        s['development']['society'] = context
        return s, state

    def test_fast_ticks_do_not_permit_an_immediate_policy_switch_back(self):
        s, state = self.prepare_assignment()
        s['game']['tick'] = 90000
        with patch('colony_retry.time.time', return_value=1005):
            self.assertNotIn('society_drug_policy',society.prepare(s,state))

    def test_policy_review_reopens_after_both_clocks(self):
        s, state = self.prepare_assignment()
        s['game']['tick'] = 90000
        with patch('colony_retry.time.time', return_value=1121):
            self.assertIn('society_drug_policy',society.prepare(s,state))

    def test_new_dangerous_clinic_can_reopen_review_early(self):
        s, state = self.prepare_assignment()
        s['game']['tick'] = 101
        s['development']['society']['people'][0]['downed'] = True
        with patch('colony_retry.time.time', return_value=1005):
            self.assertIn('society_drug_policy',society.prepare(s,state))

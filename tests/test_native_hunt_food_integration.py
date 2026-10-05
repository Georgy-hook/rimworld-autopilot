import unittest
from unittest.mock import patch
import colony_director as director


class NativeHuntFoodIntegrationTests(unittest.TestCase):
    def snapshot(self, available=True):
        return {'game':{'tick':12000},'map':{'id':1,'resources':{'food':5,'meals':5,'raw_food':0,'nutrition':1}},
            'colonists':[{'id':1,'name':'Hunter','health':1,'hunger':.8,'joy':.8,'mood':.6,'position':{'x':20,'z':20},
              'skills':{'Construction':{'level':5}},'work_priorities':{'Construction':{'priority':1},'Cooking':{'priority':1}}}],
            'animals':[],'wild_animals':[{'id':10,'def':'Hare','position':{'x':24,'z':20},'combat_power':33,'harm_revenge_chance':0,'meat_amount':31}],
            'combat':{'colonists':[{'id':1,'has_ranged_weapon':True,'health':1,'shooting_skill':7}]},
            'development':{'building_counts':{'Campfire':1},'buildings':[],'rooms':[],'zones':[],
              'item_counts':{},'work_tables':[{'id':2,'thing_def':'Campfire','bills_count':1}],
              'forbidden':[],'plants':[],'things':[],'current_research':{'name':'none'},
              'wildlife':{'available':available,'targets':[{'id':10,'def':'Hare'}],
                 'actor_options':[{'target_id':10,'pawn_id':1,'solo_feasible':True}]}}}

    def candidates(self,snapshot,state=None):
        with patch.object(director,'estimated_food_runway_days',return_value=.5):
            return director.candidate_actions(None,snapshot,state or {'anchor':{'x':20,'z':20},'issued':{}})[0]

    def test_native_emergency_plan_survives_food_focus_and_removes_legacy(self):
        snapshot=self.snapshot()
        actions=self.candidates(snapshot)
        self.assertIn('wildlife_hunt_plan',actions)
        self.assertNotIn('designate_safe_hunting',actions)
        self.assertNotIn('consider_dangerous_hunt',actions)
        self.assertTrue(snapshot['development']['wildlife']['plans'])

    def test_native_new_hunt_disabled_until_existing_carcasses_can_be_butchered(self):
        snapshot=self.snapshot()
        snapshot['development']['corpses']=[{'thing_id':99,'label':'hare dead','position':{'x':25,'z':17},'categories':['CorpsesAnimal'],'is_forbidden':False}]
        with patch.object(director,'local_butcher_plan',return_value={'x':25,'z':17}):
            actions=self.candidates(snapshot)
        self.assertIn('build_butcher_spot',actions)
        self.assertNotIn('wildlife_hunt_plan',actions)
        self.assertNotIn('designate_safe_hunting',actions)

    def test_endpoint_unavailable_preserves_legacy_food_hunt_fallback(self):
        actions=self.candidates(self.snapshot(False))
        self.assertIn('designate_safe_hunting',actions)
        self.assertNotIn('wildlife_hunt_plan',actions)

    def test_actual_candidate_food_focus_keeps_cleanup_lifecycle_alongside_butchery(self):
        snapshot=self.snapshot()
        snapshot['development']['corpses']=[{'thing_id':99,'label':'hare dead','position':{'x':25,'z':17},'categories':['CorpsesAnimal'],'is_forbidden':False}]
        snapshot['development']['wildlife']['wild_status']=[{'id':10,'dead':True,'downed':True,'health':0}]
        state={'anchor':{'x':20,'z':20},'issued':{},'wildlife_hunt_group':{'map_id':1,'target_id':10,'pawn_ids':[1],'tick':12000}}
        with patch.object(director,'local_butcher_plan',return_value={'x':25,'z':17}):
            actions=self.candidates(snapshot,state)
        self.assertIn('wildlife_hunt_lifecycle',actions)
        self.assertNotIn('wildlife_hunt_plan',actions)
        self.assertIn('build_butcher_spot',actions)


if __name__=='__main__':unittest.main()

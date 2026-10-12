"""Observed failure shapes, with synthetic identities; no live gameplay transport."""
import copy
import unittest
from unittest.mock import patch
import colony_capabilities as crops
import colony_director as director
import colony_architect as architect
import colony_society as society
import stream_observer as observer


def food_snapshot():
    defs=[{'def_name':name,'human_edible_product':True,'category':'food','minimum_skill':0,
           'harvest_yield':yield_, 'product_nutrition':.05} for name,yield_ in [('Plant_Corn',22),('Plant_Rice',6)]]
    options=[{'def_name':name,'safe_sowing_now':True,'legal_cells':140,'calendar_days_to_harvest_estimate':days}
             for name,days in [('Plant_Corn',20.55),('Plant_Rice',5.45)]]
    return {'game':{'tick':800000},'map':{'id':0,'resources':{'nutrition':6.4,'food':8,'meals':8,'raw_food':0}},
        'colonists':[{'id':1,'downed':False,'hunger':.8,'current_job':'GotoWander','health_conditions':[],
          'skills':{'Plants':{'level':11}},'work_priorities':{k:{'disabled':False,'priority':1} for k in ('Growing','PlantCutting','Cooking','Firefighter')}}],
        'combat':{'colonists':[],'hostiles':[]},'development':{'plant_catalog':{'plants':defs,'growers':[
            {'id':'zone:1','kind':'ground','plant_def':'Plant_Corn','allow_sow':True,'plant_count':140,'pen_ids':[], 'options':copy.deepcopy(options)},
            {'id':'new_ground','kind':'new_ground','plant_def':None,'plant_count':0,'pen_ids':[],'options':copy.deepcopy(options)}]},
            'farm':{'crop_types':[{'plant_def_name':'Plant_Corn','total_plants':140,'harvestable_plants':0,'days_until_harvest':12.3,'grower_ids':['zone:1']}]}}}


class FirstHarvestRecovery(unittest.TestCase):
    def test_adequate_average_corn_output_does_not_cover_first_harvest(self):
        s=food_snapshot(); facts=crops.food_planning_facts(s)
        self.assertFalse(facts['crop_capacity_gap'])
        self.assertTrue(facts['first_harvest_gap'])
        self.assertEqual(facts['first_harvest_days_estimate'],12.3)
        self.assertTrue(facts['protect_food_supply'])
        plans=crops.crop_sites(s,True)['new_ground']['crop_options']
        self.assertEqual(set(plans),{'Plant_Rice'})
        self.assertAlmostEqual(plans['Plant_Rice']['bridge_food_days_needed'],3.45)
        self.assertEqual(crops.crop_sites(s,False),{})

    def test_pending_fast_plot_is_preserved_without_identical_plot_spam(self):
        s=food_snapshot(); rice=copy.deepcopy(s['development']['plant_catalog']['growers'][0])
        rice.update(id='zone:2',plant_def='Plant_Rice',plant_count=0)
        s['development']['plant_catalog']['growers'].append(rice)
        self.assertEqual(crops.food_planning_facts(s)['first_harvest_days_estimate'],5.45)
        self.assertEqual(crops.crop_sites(s,True),{})
        self.assertEqual(crops.crop_sites(s,False),{})

    def test_ready_standing_crop_remains_distinct_from_stored_food(self):
        s=food_snapshot(); s['development']['farm']['crop_types'][0]['harvestable_plants']=140
        s['map']['resources']['nutrition']=0
        facts=crops.food_planning_facts(s)
        self.assertEqual(facts['stored_food_days'],0)
        self.assertEqual(facts['ready_food_plants'],140)
        self.assertFalse(facts['first_harvest_gap'])
        self.assertEqual(crops.crop_sites(s,True),{})

    def test_unknown_stock_never_manufactures_a_delivery_deadline(self):
        s=food_snapshot(); s['map']['resources']={}
        facts=crops.food_planning_facts(s)
        self.assertIsNone(facts['stored_food_days'])
        self.assertFalse(facts['first_harvest_gap'])

    def test_existing_slow_field_does_not_hide_food_window(self):
        s=food_snapshot(); crops.prepare(s,{})
        actions=['create_growing_zone','harvest_local_plants','advance_doctrine_research']
        self.assertEqual(director.focus_imminent_food_choices(s,actions),actions[:2])

    def test_native_trait_gene_and_stage_demand_overrides_typical_count(self):
        s=food_snapshot();s['development']['sustenance']={'husbandry':{'human_demand_nutrition_day':2.4}}
        facts=crops.food_planning_facts(s)
        self.assertEqual(facts['human_demand_per_day'],2.4)
        self.assertAlmostEqual(facts['stored_food_days'],2.67)
        self.assertEqual(facts['demand_basis'],'native_current_pawns')
        s['map']['resources']['human_demand_nutrition_day']=2.4
        self.assertAlmostEqual(director.estimated_food_runway_days(s['map']['resources'],1),2.7)
    def test_invalid_native_demand_keeps_explicit_legacy_estimate(self):
        for value in (None,False,float('nan'),-1,0):
            s=food_snapshot();s['development']['sustenance']={'husbandry':{'human_demand_nutrition_day':value}}
            facts=crops.food_planning_facts(s)
            self.assertEqual(facts['human_demand_per_day'],1.6)
            self.assertEqual(facts['demand_basis'],'legacy_1.6_per_person_estimate')

    def test_capacity_shortfall_cannot_make_another_slow_corn_plot_immediate_food(self):
        s=food_snapshot();s['development']['plant_catalog']['growers'][0]['options'][0]['legal_cells']=45
        s['development']['sustenance']={'husbandry':{'human_demand_nutrition_day':2.4}}
        self.assertTrue(crops.food_planning_facts(s)['crop_capacity_gap'])
        self.assertEqual(set(crops.crop_sites(s,True)['new_ground']['crop_options']),{'Plant_Rice'})
        self.assertEqual(crops.crop_sites(s,False),{})
    def test_finite_reserve_admits_multiple_timely_crops_and_long_horizon_returns_corn(self):
        s=food_snapshot();s['development']['farm']['crop_types']=[]
        s['development']['plant_catalog']['growers']=s['development']['plant_catalog']['growers'][1:]
        s['map']['resources']['nutrition']=24 #15days
        option={'def_name':'ModFood','safe_sowing_now':True,'legal_cells':140,'calendar_days_to_harvest_estimate':10}
        definition={'def_name':'ModFood','human_edible_product':True,'category':'food','minimum_skill':0,'harvest_yield':10,'product_nutrition':.05}
        s['development']['plant_catalog']['plants'].append(definition)
        s['development']['plant_catalog']['growers'][0]['options'].append(option)
        self.assertEqual(set(crops.crop_sites(s,True)['new_ground']['crop_options']),{'Plant_Rice','ModFood'})
        s['map']['resources']['nutrition']=48
        self.assertIn('Plant_Corn',crops.crop_sites(s,True)['new_ground']['crop_options'])


class ConcurrentEmergencies(unittest.TestCase):
    def test_fire_leaves_safe_food_choices_for_free_actor(self):
        s=food_snapshot(); s['map']['resources']['nutrition']=0
        other=copy.deepcopy(s['colonists'][0]);other.update(id=2,current_job='BeatFire')
        s['colonists'].append(other)
        actions=['prioritize_firefighting','harvest_food_crops_early','sustenance_food_batch','advance_doctrine_research']
        self.assertEqual(director.focus_active_fire_choices(actions,True,s),actions[:3])

    def test_fire_does_not_reassign_only_busy_firefighter_to_food(self):
        s=food_snapshot();s['map']['resources']['nutrition']=0;s['colonists'][0]['current_job']='BeatFire'
        self.assertEqual(director.focus_active_fire_choices(['prioritize_firefighting','harvest_local_plants'],True,s),['prioritize_firefighting'])

    def test_care_owned_actor_keeps_feed_rescue_tend_jobs(self):
        for job in ('FeedPatient','Rescue','TendPatient'):
            s=food_snapshot();s['colonists'][0]['current_job']=job
            self.assertIn('1',director.active_care_pawn_ids(s))
            self.assertEqual(director.food_work_adjustments(s,s['colonists'][0],'PlantCutting'),{})

    def test_food_and_rot_cleanup_survive_both_filters(self):
        s=food_snapshot();s['map']['resources']['nutrition']=0
        s['development'].update(sanitation_urgent=True,early_crop_options={'Corn':{'count':45}})
        actions=['resilience_dispose_corpse','resilience_shelter','harvest_food_crops_early','sustenance_food_batch','advance_doctrine_research']
        first=director.focus_imminent_food_choices(s,actions)
        self.assertEqual(director.focus_contamination_choices(s,first),actions[:4])


class CapacityAndUtilityRecovery(unittest.TestCase):
    def person(self):
        return {'pawn_id':1,'drugs':{'policy_id':1,'capacities':{'consciousness':.53,'moving':.15},
            'entries':[{'drug':'SmokeleafJoint','allowed_joy':True,'capacity_risk':True}]}}
    def test_risky_sedation_is_non_elective_without_addiction_or_ideology(self):
        person=self.person(); self.assertTrue(society.drug_policy_relevant(person))
        s={'development':{'society':{'people':[person]}}}
        self.assertFalse(society.elective_drug_policy(s))
        person['drugs']['entries'][0]['allowed_joy']=False
        self.assertFalse(society.drug_policy_relevant(person))
    def test_capacity_change_reopens_previously_declined_policy(self):
        person=self.person(); context={'native_options':[]}
        risk=society._drug_guard('society_drug_entry',person,context)
        person['drugs']['entries'][0]['capacity_risk']=False
        self.assertNotEqual(risk,society._drug_guard('society_drug_entry',person,context))
    def test_drug_risk_is_retained_on_final_exact_option(self):
        effects=society._effects({'native':True,'person':self.person(),'effects':{'risk':'Withdrawal remains a cost'}},'society_drug_entry',{})
        self.assertIn('SmokeleafJoint',effects['risk']);self.assertIn('0.15',effects['risk'])
    def test_zero_pollution_pump_is_context_blocked_but_catalog_is_accounted(self):
        dev={'item_counts':{'Steel':100},'specialists':{'pollution_percent':0},'building_catalog':[
            {'def_name':'PollutionPump','available_now':True,'cost_list':[{'thing_def':'Steel','count':10}]}]}
        self.assertEqual(architect.catalog_construction_options(dev),{})
        audit=architect.catalog_access_audit(dev)
        self.assertIn('PollutionPump',audit['context_blockers']); self.assertEqual(audit['need_materials'],[])
        dev['specialists']['pollution_percent']=.1
        self.assertTrue(architect.catalog_construction_options(dev))
    def test_unknown_pollution_is_not_zero(self):
        dev={'building_catalog':[{'def_name':'PollutionPump','available_now':True}],'item_counts':{}}
        self.assertTrue(architect.catalog_construction_options(dev))

    def test_missing_safety_confirmation_holds_game_before_autonomy(self):
        class API:
            def __init__(self):self.posts=[]
            def request(self,path,**kwargs):self.posts.append(path);return {'active':False}
        api=API()
        with self.assertRaises(RuntimeError):observer.refresh_autonomy_safety(api,True)
        self.assertEqual(api.posts[-1],'/api/v1/game/speed?speed=0')
    def test_confirmed_lease_has_no_gameplay_or_speed_order(self):
        class API:
            def __init__(self):self.posts=[]
            def request(self,path,**kwargs):self.posts.append(path);return {'active':True}
        api=API();observer.refresh_autonomy_safety(api,True)
        self.assertEqual(len(api.posts),1)
        self.assertIn('enabled=true',api.posts[0])

if __name__=='__main__':unittest.main()

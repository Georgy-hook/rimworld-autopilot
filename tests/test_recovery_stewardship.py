"""Regressions for food/service failures and temporary safe areas; no game orders."""
import copy
import json
import unittest
from unittest.mock import patch
import colony_storage as storage
import colony_stewardship as steward
import colony_capabilities as caps
import colony_director as director
import colony_decision_context as facts
import colony_resilience as resilience
import colony_production as production
import colony_society as society
from test_capabilities import snapshot, crop, growing_site


def state():
    s=snapshot();s['map']['resources']={'nutrition':80,'human_demand_nutrition_day':5.6}
    rice={**crop(),'human_edible_product':True,'product_nutrition':.05,'harvest_yield':6}
    field=growing_site(plant='Plant_Rice',options=[{**rice,'legal_cells':300}]);field.update(zone_id=4,allow_sow=True)
    s['development']['plant_catalog']={'plants':[rice],'growers':[field]}
    s['development']['production']={'available':True,'buildings':[],'perishables':[{'id':7,'def_name':'RawCorn','nutrition':40,
        'human_edible':True,'rot_stage':'Fresh','hit_points':4,'max_hit_points':60,'deterioration_per_day':6,
        'protected_from_deterioration':False,'ticks_until_rot':4320000}]}
    s['development']['item_counts']={};s['development']['buildings']=[];s['development']['construction_projects']=[]
    s['development']['building_catalog']=[{'def_name':n,'available_now':True,'cost_list':cost,'cost_stuff_count':stuff}
        for n,cost,stuff in [('Wall',[],5),('Door',[],25),('Cooler',[{'thing_def':'Steel','count':90},{'thing_def':'ComponentIndustrial','count':3}],0),
            ('PowerConduit',[{'thing_def':'Steel','count':1}],0)]]
    return s


class Agent:
    class Tokenizer:
        def __call__(self,text,**kwargs):return {'input_ids':list(range((len(text)+2)//3))}
    tok=Tokenizer();cfg={'max_len':512,'head_max_len':192}
    def __init__(self):self.calls=[]
    def predict(self,visible,questions):
        self.calls.append(copy.deepcopy(visible));qid,q=next(iter(questions.items()))
        return {'answers':{qid:{'choice':next((k for k in q['criteria'] if k!='defer'),next(iter(q['criteria'])))}}}


class RecoveryTests(unittest.TestCase):
    def test_fresh_but_low_hp_food_is_urgent_and_not_long_reserve(self):
        s=state();condition=storage.food_condition_facts(s,5.6)
        self.assertIn(7,condition['critical_stack_ids']);self.assertGreater(condition['at_risk_nutrition'],30)
        self.assertLess(caps.food_planning_facts(s)['stored_food_days'],9)
        self.assertTrue(condition['estimate_not_delivery_or_exact_loss_time'])

    def test_shelf_or_roof_removes_deterioration_estimate_not_rot(self):
        s=state();s['development']['production']['perishables'][0].update(protected_from_deterioration=True,ticks_until_rot=60000)
        condition=storage.food_condition_facts(s,5.6)
        self.assertEqual(condition['critical_stack_ids'],[]);self.assertGreater(condition['at_risk_nutrition'],30)
        self.assertEqual(condition['stacks'][0]['rot_days'],1)

    def test_malformed_deadline_is_not_invented(self):
        s=state();s['development']['production']['perishables'][0].update(deterioration_per_day=float('nan'),ticks_until_rot=None)
        self.assertIsNone(storage.food_condition_facts(s,5.6)['stacks'][0]['deadline_days'])

    def test_future_sowing_pauses_excess_but_preserves_standing_plants(self):
        s=state();s['development']['production']['perishables']=[]
        plan=steward.sow_plans(s)['4'];self.assertFalse(plan['allow_sow']);self.assertTrue(plan['plant_preservation'])
        before=copy.deepcopy(s['development']['plant_catalog']);steward.prepare(s,{})
        self.assertEqual(before,s['development']['plant_catalog'])

    def test_paused_field_reopens_after_real_supply_gap(self):
        s=state();s['map']['resources']['nutrition']=1;s['development']['plant_catalog']['growers'][0]['allow_sow']=False
        self.assertTrue(steward.sow_plans(s)['4']['allow_sow'])

    def test_fallout_pauses_outdoor_sowing_without_crop_change(self):
        s=state();s['development']['resilience']={'environment':{'conditions':[{'def_name':'ToxicFallout'}]}}
        plan=steward.sow_plans(s)['4'];self.assertFalse(plan['allow_sow']);self.assertEqual(plan['plant_def'],'Plant_Rice')

    def test_goal_exists_before_components_and_passes_exact_need_to_mining(self):
        s=state();memory={};self.assertIn('stewardship_preservation_goal',steward.prepare(s,memory))
        plan=s['development']['stewardship']['plans']['stewardship_preservation_goal']['freezer']
        self.assertEqual(plan['requirements']['Steel'],92)
        result=steward.execute(None,s,memory,'stewardship_preservation_goal',{'key':'freezer','plan':copy.deepcopy(plan)})
        self.assertTrue(result['goal_selected']);steward.prepare(s,memory)
        self.assertEqual(facts.material_need(s,'ComponentIndustrial')['deficit'],3)
        self.assertEqual(s['development']['construction_projects'],[])

    def test_queued_freezer_cost_is_not_counted_twice(self):
        s=state();memory={'preservation_goal':{'map_id':0,'placed':True,'requirements':{'ComponentIndustrial':3}}}
        s['development']['construction_projects']=[{'thing_id':22,'materials_needed':[{'def_name':'ComponentIndustrial','required_count':3}]}]
        steward.prepare(s,memory);self.assertEqual(facts.material_need(s,'ComponentIndustrial')['deficit'],3)

    def test_broken_generator_has_a_separate_component_need(self):
        s=state();s['development']['production']['buildings']=[{'id':10,'broken_down':True,'repair_component_count':1,
            'repair_component_def':'ComponentIndustrial','switch_on':False,'auto_refuel':False,'can_set_auto_refuel':True,'fuel':30}]
        self.assertEqual(facts.material_need(s,'ComponentIndustrial')['deficit'],1)
        self.assertNotIn('10:switch_on',production.options(s['development']['production']))
        self.assertNotIn('10:enable_refuel',production.options(s['development']['production']))

    def test_freezer_shell_has_no_conduit_hole_and_no_heater(self):
        rows=director.freezer_blueprint()['buildings']
        actual={(r['rel_x'],r['rel_z']):r['def_name'] for r in rows if r['def_name']!='PowerConduit'}
        self.assertEqual(actual[(5,3)],'Wall');self.assertEqual(actual[(5,2)],'Cooler')
        self.assertFalse(any(r['def_name'] in {'Campfire','Heater'} for r in rows))

    def test_small_roster_gets_finite_meal_batch(self):
        s=state();self.assertEqual(storage.meal_batch_target(s),13)
        s['map']['resources']['human_demand_nutrition_day']=1.6;self.assertEqual(storage.meal_batch_target(s),4)

    def test_nonimmunizable_toxin_does_not_make_chronic_immunity_race(self):
        s=state();s['colonists'][0]['health_conditions']=[{'can_ever_kill':True,'immunity':0,'immunity_can_develop':False}]
        self.assertTrue(caps.workers(s,'Growing'))
        s['colonists'][0]['health_conditions'][0]['immunity_can_develop']=True;self.assertEqual(caps.workers(s,'Growing'),[])

    def test_actual_production_bill_can_yield_but_operation_cannot(self):
        s=state();s['colonists'][0].update(current_job='DoBill',current_job_is_care=False)
        self.assertTrue(caps.workers(s,'Growing'))
        s['colonists'][0]['current_job_is_care']=True;self.assertFalse(caps.workers(s,'Growing'))

    def test_safe_area_action_and_release_use_fresh_native_options(self):
        s=state();row={'kind':'area_shelter','worker_id':1,'target_id':1,'giver':'-1:fallout'}
        s['development']['resilience']={'available':True,'options':[row], 'environment':{'conditions':[{'def_name':'ToxicFallout'}]}}
        self.assertIn('resilience_area_shelter',resilience.prepare(s,{}))
        class Client:
            posts=[]
            def get(self,*args,**kwargs):return {'available':True,'options':[]}
            def post(self,*args,**kwargs):self.posts.append((args,kwargs));return {'applied':True}
        client=Client();result=resilience.execute(client,s,{},'resilience_area_shelter',row)
        self.assertFalse(result['applied']);self.assertEqual(client.posts,[])
        s['development']['resilience']['options']=[dict(row,kind='area_release',giver='9')]
        self.assertIn('resilience_area_release',resilience.prepare(s,{}))

    def test_sow_comparison_fits_model_budget_with_all_downsides(self):
        s=state();s['development']['production']['perishables']=[];steward.prepare(s,{})
        agent=Agent();selected,_=steward.choose(agent,{},'stewardship_crop_budget',s)
        self.assertNotEqual(selected['key'],'defer');self.assertTrue(agent.calls)
        for call in agent.calls:
            self.assertLessEqual(len(agent.tok(json.dumps(call,ensure_ascii=False))['input_ids']),312)
            for effect in call['effects'].values():self.assertEqual(set(effect),{'benefit','cost','risk','inaction','uncertainty'})

    def test_area_binding_has_food_sleep_and_restore_consequences(self):
        s=state();row={'kind':'area_shelter','worker_id':1,'target_id':1,'giver':'-1:fallout','worker':'Farmer'}
        s['development']['resilience']={'options':[row], 'patients':[{'pawn_id':1,'name':'Farmer','food':.2,'temperature':21,'roof':'RoofConstructed','conditions':[]}],
            'area_restrictions':[{'pawn_id':1,'hazards':'fallout','services':{'food_urgent':True,'rest_urgent':True}}]}
        resilience.prepare(s,{})
        agent=Agent();selected,_=resilience.choose(agent,{},'resilience_area_shelter',s)
        self.assertEqual(selected['kind'],'area_shelter')
        self.assertTrue(agent.calls)
        text=json.dumps(agent.calls,ensure_ascii=False)
        self.assertIn('food',text);self.assertIn('sleep',text)
        for call in agent.calls:self.assertLessEqual(len(agent.tok(json.dumps(call,ensure_ascii=False))['input_ids']),312)

    def test_one_selected_economic_field_requires_surplus_and_no_existing_matching_field(self):
        s=state();s['development']['production']['perishables']=[]
        tobacco={**crop('Plant_Smokeleaf'),'human_edible_product':False,'harvested_thing':'SmokeleafLeaves','product_nutrition':0}
        s['development']['plant_catalog']['plants'].append(tobacco)
        s['development']['plant_catalog']['growers'].append(growing_site('new_ground',options=[tobacco]))
        s['development']['pending_income_crop_goal']='drugs'
        self.assertTrue(caps.crop_sites(s,True))
        s['development']['plant_catalog']['growers'].append(growing_site(plant='Plant_Smokeleaf',options=[tobacco]))
        self.assertFalse(caps.crop_sites(s,True))


if __name__=='__main__':unittest.main()

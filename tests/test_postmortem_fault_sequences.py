import copy
import json
import unittest
from unittest.mock import patch
import colony_director as d
import colony_labor as labor
import colony_mining as mining
import colony_storage as storage
import colony_sustenance as sustain
import colony_events as events
import colony_quests as quests
import colony_medical_recovery as care
from tests.test_food_commitment import fixture
from tests.test_sustenance import Client


def mine_snapshot():
    s=fixture()
    s['development']['mining']={'available':True,'options':[
        {'key':'1:91,92','worker_id':1,'worker':'Miner','kind':'extract','product_def':'Jade','ore_def':'MineableJade',
         'thing_ids':[91,92],'cells':[{'x':15,'z':15},{'x':16,'z':15}],'vein_cells':18,'base_yield':80,
         'nominal_market_value':400,'remaining_hp':3000,'mining_speed':1.2,'mining_yield':1,'mining_skill':9,'travel_distance':10}],
        'product_stocks':[{'product_def':'Jade','count':0}]}
    return s


class MiningSequences(unittest.TestCase):
    @patch('colony_retry.time.time',return_value=100)
    def test_defer_reject_accept_new_vein_and_rollback(self,clock):
        s=mine_snapshot();memory={'doctrine':{'mining_product':'mineable_jade'},'income_strategy_tick':1}
        labor.prepare(s,memory)
        self.assertIn('mining_extract',mining.prepare(s,memory))
        self.assertTrue(s['development']['mining']['options'][0]['preferred_product'])
        mining.execute(None,s,memory,'mining_extract',{'mining_plan':'defer','shown_mining_options':['1:91,92']})
        s['game']['tick']+=40000
        clock.return_value=110
        self.assertEqual(mining.prepare(s,memory),[])
        new=copy.deepcopy(s['development']['mining']['options'][0]);new.update(key='1:101',thing_ids=[101])
        s['development']['mining']['options'].append(new)
        self.assertIn('mining_extract',mining.prepare(s,memory))
        clock.return_value=230
        mining.prepare(s,memory)
        transport=Client(s['development']['mining'])
        transport.context['options'][0]['thing_ids']=[99] # mutated native terms
        original=copy.deepcopy(transport.context['options'][0]);original['thing_ids']=[91,92]
        s['development']['mining']['prepared_options']['1:91,92']=original
        result=mining.execute(transport,s,memory,'mining_extract',{'mining_plan':'1:91,92'})
        self.assertFalse(result['applied']);self.assertEqual(transport.posts,[])
        transport.context['options'][0]['thing_ids']=[91,92]
        s['game']['tick']+=40000;clock.return_value=270
        mining.prepare(s,memory)
        result=mining.execute(transport,s,memory,'mining_extract',{'mining_plan':'1:91,92'})
        self.assertTrue(result['applied'])
        self.assertEqual(transport.posts,[{'map_id':s['map']['id'],'key':'1:91,92'}])
        memory=json.loads(json.dumps(memory))
        s['game']['tick']-=1
        mining.prepare(s,memory)
        self.assertNotIn('1:91,92',memory['mining_history'])

    def test_care_and_existing_food_assignment_keep_their_workers(self):
        s=mine_snapshot();memory={};labor.prepare(s,memory);labor.remember(s,1,'Cooking')
        self.assertEqual(mining.prepare(s,memory),[])
        memory['labor_commitments'].clear()
        s['colonists'][0]['current_job']='Mine'
        self.assertFalse(labor.can_assign(s,s['colonists'][0],'Cooking'))
        labor.remember(s,1,'Mining')
        self.assertFalse(labor.can_assign(s,s['colonists'][0],'Hunting'))
        self.assertTrue(labor.can_assign(s,s['colonists'][0],'Doctor'))

    def test_haul_is_a_separate_plan_not_income(self):
        s=mine_snapshot();p=copy.deepcopy(s['development']['mining']['options'][0]);p.update(kind='haul',key='haul:1:301',thing_ids=[301])
        s['development']['mining']['options']=[p]
        self.assertEqual(mining.prepare(s,{}),['mining_haul'])
        self.assertEqual(mining.plans(s,'mining_extract'),{})
        self.assertIn('sale',mining.effects(p)['uncertainty'])

    def test_unknown_ore_identity_is_not_output_and_finished_batch_releases_worker(self):
        s=mine_snapshot();memory={};labor.prepare(s,memory)
        labor.remember(s,1,'Mining',[91,92])
        memory['mining_intent']={'map_id':s['map']['id'],'tick':s['game']['tick'],
            'product_def':'Jade','product_stock':0,'thing_ids':[91,92]}
        s['development']['ores']={'ores':{'MineableJade':{'count':18}}}
        mining.prepare(s,memory);labor.prepare(s,memory)
        self.assertIsNone(s['development']['mining']['progress']['selected_blocks_no_longer_observed'])
        self.assertIn('1',memory['labor_commitments'])
        s['development']['ores']={'ores':{'MineableJade':{'thing_ids':[]}}}
        mining.prepare(s,memory);labor.prepare(s,memory)
        self.assertEqual(s['development']['mining']['progress']['selected_blocks_no_longer_observed'],2)
        self.assertNotIn('1',memory['labor_commitments'])

    @patch.object(mining,'ask_laya_choice',side_effect=[('Jade',{}),('v0',{})])
    def test_product_and_actor_are_chosen_without_gold_fallback(self,ask):
        s=mine_snapshot();mining.prepare(s,{'doctrine':{'mining_product':'mineable_jade'}})
        selected,_=mining.choose(None,{},'mining_extract',s)
        self.assertEqual(selected['mining_plan'],'1:91,92')
        self.assertIn('nominal',ask.call_args_list[0].args[1]['option_effects']['Jade']['benefit'])
        self.assertEqual(ask.call_args_list[0].args[1]['comparison_facts']['options']['Jade']['nominal_value'],400)
        self.assertIn('defer',ask.call_args_list[-1].args[4])


class FoodAndStorageSequences(unittest.TestCase):
    def test_bed_replacement_does_not_remove_an_occupied_neighbor(self):
        spot={'id':7,'def':'SleepingSpot','position':{'x':2,'z':2}}
        room={'open_roof_count':0,'contained_beds_ids':[7],
              'cells':[{'x':2,'z':2},{'x':2,'z':3}]}
        dev={'buildings':[spot,{'id':8,'def':'SleepingSpot','position':{'x':2,'z':3}}],
             'rooms':[room],'construction_projects':[]}
        anchor={'x':2,'z':2}
        self.assertIsNone(d.replaceable_indoor_sleeping_spot(dev,anchor,[]))
        dev['buildings']=[spot]
        self.assertEqual(d.replaceable_indoor_sleeping_spot(dev,anchor,[])['id'],7)
        dev['construction_projects']=[{'def_name':'Wall','position':{'x':2,'z':3}}]
        self.assertIsNone(d.replaceable_indoor_sleeping_spot(dev,anchor,[]))
        dev['construction_projects']=[]
        self.assertIsNone(d.replaceable_indoor_sleeping_spot(dev,anchor,[{'downed':True,'position':spot['position']}]))

    def test_lost_bed_reply_observes_paid_project_before_restoring_spot(self):
        spot={'id':7,'def':'SleepingSpot','position':{'x':2,'z':2},'size':{'x':1,'z':2}}
        s=fixture();s['development'].update(buildings=[spot],construction_projects=[],
            rooms=[{'open_roof_count':0,'contained_beds_ids':[7],'cells':[{'x':2,'z':2},{'x':2,'z':3}]}])
        memory={'anchor':{'x':2,'z':2},'issued':{}}
        class LostReply:
            def __init__(self):self.posts=[]
            def post(self,path,*,body):
                self.posts.append((path,body))
                if path.endswith('/blueprint'):raise d.bridge.RimApiError('lost reply after placement')
                return {'success':True}
            def get(self,path,**kwargs):
                return {'projects':[{'def_name':'Bed','position':spot['position']}]} if path.endswith('/projects') else []
        client=LostReply()
        result=d.execute_action(client,s,memory,'build_basic_beds',{'basic_bed_materials':{'WoodLog':'100'},'bed_material':'WoodLog'})
        self.assertTrue(result['applied'])
        self.assertEqual(len(client.posts),2)
        self.assertEqual(client.posts[-1][1]['blueprint']['buildings'][0]['def_name'],'Bed')

    def test_desiccated_and_unknown_corpses_are_not_food(self):
        for p in ({'rot_stage':'Desiccated','can_butcher':False},{'rot_stage':'Rotting'},{}):
            self.assertFalse(storage.fresh_carcass(p))
        self.assertTrue(storage.fresh_carcass({'rot_stage':'Fresh','can_butcher':True}))
        self.assertFalse(storage.fresh_carcass({'rot_stage':'Desiccated','can_butcher':True}))

    def test_pen_and_existing_zones_excluded_and_rejected_create_not_completed(self):
        s=fixture();s['development']['zones']=[{'cells':[{'x':35,'z':27}]}]
        s['development']['sustenance']={'pens':[{'enclosed':True,'cells':[{'x':x,'z':z} for x in range(30,43) for z in range(20,37)]}]}
        anchor={'x':20,'z':20};site=storage.carcass_site(s,anchor)
        forbidden={(c['x'],c['z']) for c in s['development']['sustenance']['pens'][0]['cells']}
        self.assertFalse(any((site[0]+x,site[1]+z) in forbidden for x in range(4) for z in range(3)))
        class Transport:
            def __init__(self):self.posts=[];self.success=False
            def post(self,path,*,body):self.posts.append(body);return {'success':self.success}
        client=Transport();memory={'anchor':anchor,'issued':{}}
        self.assertFalse(d.execute_action(client,s,memory,'create_animal_corpse_dump',{})['applied'])
        self.assertNotIn('animal_corpse_dump',memory['issued'])
        client.success=True
        self.assertTrue(d.execute_action(client,s,memory,'create_animal_corpse_dump',{})['applied'])
        self.assertEqual((client.posts[-1]['allow_fresh'],client.posts[-1]['allow_rotten']),(True,False))
        s['development']['sustenance']['pens'][0].pop('cells')
        self.assertIsNone(storage.carcass_site(s,anchor))

    @patch('colony_retry.time.time',return_value=100)
    def test_pen_feed_failure_and_changed_source_warm_patient_remain_independent(self,clock):
        feed={'key':'penfeed:9:1:33:30:25','kind':'penfeed','target_id':9,'value':'1,33,30,25,10','label':'finite feed haul'}
        warm={'key':'warmspot:4:21:21','kind':'warmspot','target_id':4,'value':'21,21','label':'warm animal spot'}
        context={'available':True,'options':[feed,warm],'pens':[{'id':9,'enclosed':True,'consumption_per_day':2,'pasture_nutrition_per_day':0,'stockpiled_nutrition':0}],
                 'animals':[{'id':4,'food':0,'downed':True,'health':[{'def_name':'Hypothermia','stage_index':3}]}]}
        s=fixture();s['development']['sustenance']=context;memory={}
        sustain.prepare(s,memory)
        class Refusing(Client):
            def post(self,*args,**kwargs): self.posts.append(kwargs['body']);return {'applied':False,'reason':'feed_haul_not_started'}
        client=Refusing(context)
        self.assertFalse(sustain.execute(client,s,memory,'sustenance_animal_welfare',{'sustenance_policy':feed['key']})['applied'])
        sustain.prepare(s,memory)
        self.assertNotIn(feed['key'],sustain.options(context,'sustenance_animal_welfare'))
        self.assertIn(warm['key'],sustain.options(context,'sustenance_animal_welfare'))
        context['options'][0]={**feed,'key':feed['key'].replace(':33:',':34:'),'value':'1,34,30,25,10'}
        sustain.prepare(s,memory)
        self.assertIn(context['options'][0]['key'],sustain.options(context,'sustenance_animal_welfare'))


class PartialQuestSequences(unittest.TestCase):
    def test_partial_collection_preserves_incident_and_blocks_incomplete_offer(self):
        context={'read_status':'partial','quest_read_status':'partial','active_quests':[{'id':1,'read_status':'unavailable','can_accept':True}],
                 'recent_incidents':[{'name':'Raid','def_name':'RaidEnemy','tick':100}],
                 'letters':[{'id':7,'label':'Raid','text':'Raid arrived','letter_def':'ThreatBig','arrival_tick':100}]}
        rows=events.pending_events(context,set())
        self.assertTrue(any(r['source']=='incident' for r in rows))
        self.assertEqual(context['letters'][0]['id'],7)
        self.assertFalse(any(r['source']=='quest' for r in rows))
        choice,record,plan=quests.review(None,context['active_quests'][0],{}, {})
        self.assertEqual((choice,plan),('defer',None));self.assertEqual(record['reason'],'quest_read_unavailable')

    def test_owned_animal_in_cold_bed_can_yield_exact_tend_to_warm_bed(self):
        patient={'id':3,'downed':True,'bleeding_rate':0,'health_conditions':[{'def_name':'Hypothermia','severity':.987,'immunity_can_develop':False}]}
        worker={'id':1,'current_job':'TendPatient','current_job_target_id':3,'work_priorities':{'Doctor':{'disabled':False}},'bleeding_rate':0}
        row={'kind':'rescue','worker_id':1,'target_id':3,'expected_current_job':'TendPatient','expected_care_patient_id':3,
             'care_yield_reason':'nonbleeding_tend_to_thermal_rescue_same_patient','thermal_rescue':True,'bed_id':9,
             'current_temperature':-22,'destination_temperature':21,'food_feasible':False}
        s={'colonists':[worker],'animals':[patient],'development':{'resilience':{'patients':[{'pawn_id':3,'in_bed':True,'current_bed_id':8,'downed':True,'bleeding_total':0}]}}}
        self.assertEqual(care.offered_care_yield(s,row),worker)
        s['development']['resilience']['patients'][0]['current_bed_id']=9
        self.assertIsNone(care.offered_care_yield(s,row))

import copy
import unittest
from unittest.mock import patch
import colony_production as p

class Client:
    def __init__(self, context, response=None):
        self.context=context; self.calls=[]; self.response=response or {}
    def get(self, *args, **kwargs): return copy.deepcopy(self.context)
    def post(self, *args, **kwargs): self.calls.append((args, kwargs)); return self.response

class ProductionTests(unittest.TestCase):
    def snapshot(self):
        return {"map":{"id":1}, "game":{"tick":20000}, "colonists":[{"id":4,"work_priorities":{"Cooking":{"disabled":False,"priority":1}}}], "development":{"production":{
            "animals":[{"species":"Muffalo","can_eat_kibble":True,"food_level":.2,"can_graze":True}],
            "buildings":[{"id":2,"def_name":"Cooler","switch_on":True,"flick_pending":False}],
            "stocks":[{"def_name":"Meat_Chicken","nutrition":1,"eligible_nutrition":1},{"def_name":"Hay","nutrition":1,"eligible_nutrition":1}],
            "feed_tables":[{"id":3,"usable":True,"existing_bill":False,"eligible_worker_ids":[4],"ingredients":[{"count":1,"allowed_defs":["Meat_Chicken"]},{"count":1,"allowed_defs":["Hay"]}]}]}}}
    def test_nutrition_groups_and_cook_gate(self):
        s=self.snapshot(); self.assertIn("production_feed_batch",p.prepare(s,{}))
        s['development']['production']['stocks'][1]['eligible_nutrition']=.99
        self.assertNotIn("production_feed_batch",p.prepare(s,{}))
    def test_no_animals_incompatible_diet_or_protected_cook(self):
        for change in ('none','diet','care','priority','skill'):
            s=self.snapshot()
            if change=='none':s['development']['production']['animals']=[]
            if change=='diet':s['development']['production']['animals'][0]['can_eat_kibble']=False
            if change=='care':s['colonists'][0]['current_job']='TendPatient'
            if change=='priority':s['colonists'][0]['work_priorities']['Cooking']['priority']=0
            if change=='skill':s['development']['production']['feed_tables'][0]['eligible_worker_ids']=[]
            self.assertNotIn('production_feed_batch',p.prepare(s,{}),change)
    def test_unsafe_or_missing_eligible_stock_never_proves_supply(self):
        s=self.snapshot();s['development']['production']['stocks'][0].pop('eligible_nutrition')
        self.assertNotIn('production_feed_batch',p.prepare(s,{}))
    def test_completed_bill_context_allows_next_finite_batch(self):
        s=self.snapshot();s['development']['production']['feed_tables'][0]['existing_bill']=False
        self.assertIn('production_feed_batch',p.prepare(s,{}))
    def test_feed_revalidation_supply_loss_blocks_post(self):
        s=self.snapshot();p.prepare(s,{})
        live=copy.deepcopy(s['development']['production']);live['stocks'][0]['eligible_nutrition']=0
        c=Client(live);r=p.execute(c,s,{},'production_feed_batch',{'production_policy':'3'})
        self.assertFalse(r['applied']);self.assertEqual([],c.calls)
    def test_unavailable_collection_is_error(self):
        with self.assertRaises(ValueError):p.collect(Client({'available':False}),self.snapshot())
        s=self.snapshot(); s['colonists'][0]['work_priorities']['Cooking']['disabled']=True
        self.assertNotIn("production_feed_batch",p.prepare(s,{}))
    def test_pending_flick_and_existing_bill_excluded(self):
        s=self.snapshot(); s['development']['production']['buildings'][0]['flick_pending']=True
        s['development']['production']['feed_tables'][0]['existing_bill']=True
        self.assertEqual([],p.prepare(s,{}))
    def test_revalidation_blocks_changed_policy(self):
        s=self.snapshot(); p.prepare(s,{})
        live=copy.deepcopy(s['development']['production']); live['buildings'][0]['switch_on']=False
        c=Client(live); r=p.execute(c,s,{},'production_utilities',{'production_policy':'2:switch_off'})
        self.assertFalse(r['applied']); self.assertEqual([],c.calls)
    def test_missing_applied_is_not_success(self):
        s=self.snapshot(); p.prepare(s,{})
        c=Client(s['development']['production']); r=p.execute(c,s,{},'production_utilities',{'production_policy':'2:switch_off'})
        self.assertFalse(r['applied']); self.assertEqual(1,len(c.calls))
    def test_invalid_native_response_and_string_success_are_rejected(self):
        for response in ('invalid', {'applied':'false'}):
            s=self.snapshot();p.prepare(s,{})
            c=Client(s['development']['production'], response); state={}
            result=p.execute(c,s,state,'production_utilities',{'production_policy':'2:switch_off'})
            self.assertFalse(result['applied'])
            self.assertNotIn('production_utilities',p.prepare(s,state))
    def test_defer_records_cooldown_without_api_mutation(self):
        s=self.snapshot(); c=Client({}); m={}
        r=p.execute(c,s,m,'production_feed_batch',{'production_policy':'defer'})
        self.assertFalse(r['applied']); self.assertEqual([],c.calls)
        self.assertEqual(20000,m['issued']['production:production_feed_batch'])
    def test_risk_and_defer_reach_native_choice(self):
        s=self.snapshot();p.prepare(s,{})
        with patch.object(p,'ask_laya_choice',return_value=('defer',{})) as ask:
            selected,_=p.choose(None,{},'production_utilities',s)
        args=ask.call_args.args
        self.assertIn('option_effects',args[1]);self.assertIn('risk',args[1]['option_effects']['o0']); self.assertIn('defer',args[4])
        self.assertEqual('defer',selected['production_policy'])

class RecipeProductionTests(unittest.TestCase):
    def plan(self, index=1):
        return {'key':f'8:Make_Component{index}:default','building_id':8,'recipe':f'Make_Component{index}','material':None,'category':'materials','label':f'Component recipe {index}','cost':'steel/components and labor','risk':'scarcity','worker_ids':[4]}
    def snapshot(self):
        return {'map':{'id':1},'game':{'tick':20000},'development':{'production':{'recipe_context':{'options':[self.plan()]}}}}
    def test_recipe_partition_requires_actual_workers(self):
        s=self.snapshot();self.assertIn('production_recipe_batch',p.prepare(s,{}))
        s['development']['production']['recipe_context']['options'][0]['worker_ids']=[]
        self.assertNotIn('production_recipe_batch',p.prepare(s,{}))
    def test_recipe_fresh_material_or_worker_loss_blocks_post(self):
        s=self.snapshot();live={'options':[{**self.plan(),'material':'Plasteel'}]}
        class RecipeClient(Client):
            def get(self,path,**kwargs):return copy.deepcopy(live) if path.endswith('/recipes') else {}
        c=RecipeClient({})
        self.assertFalse(p.execute(c,s,{},'production_recipe_batch',{'production_policy':self.plan()['key']})['applied'])
        self.assertEqual(c.calls,[])
    def test_late_recipe_cost_is_seen_with_many_alternatives(self):
        import json
        class Tokenizer:
            def __call__(self,text,**kwargs):return {'input_ids':list(range((len(text)+2)//3))}
        class Agent:
            tok=Tokenizer();cfg={'max_len':512,'head_max_len':192}
            def __init__(self):self.calls=[]
            def predict(self,state,questions):
                self.calls.append(copy.deepcopy(state));qid,q=next(iter(questions.items()))
                choice=next((k for k,v in state['effects'].items() if v['cost'].startswith('RARE_STEEL')),next(k for k in q['criteria'] if k!='defer'))
                return {'answers':{qid:{'choice':choice}}}
        s=self.snapshot();plans=[self.plan(i) for i in range(1,51)];plans[-1]['cost']='RARE_STEEL 80; component 3; real cost'
        s['development']['production']['recipe_context']['options']=plans
        agent=Agent();choice,_=p.choose(agent,{},'production_recipe_batch',s)
        self.assertEqual(choice['production_policy'],plans[-1]['key'])
        for call in agent.calls:
            self.assertLessEqual(len(agent.tok(json.dumps(call,ensure_ascii=False))['input_ids']),312)
            self.assertTrue(all(set(card)=={'benefit','cost','risk','inaction','uncertainty'} and all(card.values()) for card in call['effects'].values()))

class ProductionGoalTests(unittest.TestCase):
    def test_every_stage_retains_compact_ending_requirements_and_downsides(self):
        import json
        class Tokenizer:
            def __call__(self,text,**kwargs):return {'input_ids':list(range((len(text)+2)//3))}
        class Agent:
            tok=Tokenizer();cfg={'max_len':512,'head_max_len':192}
            def __init__(self):self.calls=[]
            def predict(self,visible,questions):
                self.calls.append(copy.deepcopy(visible));qid,q=next(iter(questions.items()))
                return {'answers':{qid:{'choice':next(k for k in q['criteria'] if k!='defer')}}}
        state={'endgame':'ship_escape','goal_requirements':{'journey':'Pemmican:40','ship_materials':{'ComponentSpacer':12}},
               'building_catalog':'unrelated catalog '*1000}
        for action in p.ACTIONS:
            snapshot=ProductionTests().snapshot()
            context=snapshot['development']['production']
            context['recipe_context']={'options':[RecipeProductionTests().plan()]}
            context['logistics_context']={'options':[LogisticsProductionTests().plan()]}
            p.prepare(snapshot,{})
            agent=Agent();p.choose(agent,state,action,snapshot)
            self.assertGreaterEqual(len(agent.calls),1,action)
            for call in agent.calls:
                facts=str(call['facts'])
                self.assertIn('ship_escape',facts,action)
                self.assertIn('Pemmican:40',facts,action)
                self.assertIn('ComponentSpacer',facts,action)
                self.assertNotIn('unrelated catalog',facts)
                self.assertLessEqual(len(agent.tok(json.dumps(call,ensure_ascii=False))['input_ids']),312)
                for effect in call['effects'].values():
                    self.assertEqual(set(effect),{'benefit','risk','cost','inaction','uncertainty'})
                    self.assertTrue(all(effect.values()))
    def test_direct_recipe_and_logistics_callers_can_omit_goal_state(self):
        with patch.object(p,'ask_laya_choice',return_value=('defer',{})):
            self.assertEqual(p.recipe_choose(None,{'recipe_context':{'options':[]}})[0]['production_policy'],'defer')
            self.assertEqual(p.logistics_choose(None,{'logistics_context':{'options':[]}})[0]['production_policy'],'defer')


class LogisticsProductionTests(unittest.TestCase):
    def plan(self):
        return {'key':'zone:8:Steel:1,1;1,2;1,3','kind':'zone','target_id':8,'worker_id':0,'value':'Steel','cells':[{'x':1,'z':1},{'x':1,'z':2},{'x':1,'z':3}],'label':'Roofed steel stockpile','cost':'3 indoor floor cells and hauling labor','risk':'Floor space and ordinary delivery delay'}
    def snapshot(self):
        return {'map':{'id':1},'game':{'tick':20000},'development':{'production':{'logistics_context':{'options':[self.plan()]}}}}
    def test_logistics_registered_and_cooldown(self):
        s=self.snapshot();self.assertIn('production_material_logistics',p.prepare(s,{}))
        self.assertNotIn('production_material_logistics',p.prepare(s,{'issued':{'production:production_material_logistics':19000}}))
    def test_changed_footprint_not_posted(self):
        s=self.snapshot();plan=self.plan();plan['cells'].pop()
        class LogisticsClient(Client):
            def get(self,path,**kwargs):return {'options':[plan]} if path.endswith('/logistics') else {}
        client=LogisticsClient({})
        result=p.execute(client,s,{},'production_material_logistics',{'production_policy':self.plan()['key']})
        self.assertFalse(result['applied']);self.assertEqual(client.calls,[])
    def test_defer_never_creates_zone_or_interrupts_worker(self):
        client=Client({});result=p.execute(client,self.snapshot(),{},'production_material_logistics',{'production_policy':'defer'})
        self.assertFalse(result['applied']);self.assertEqual(client.calls,[])

if __name__=='__main__':unittest.main()

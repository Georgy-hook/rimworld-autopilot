import unittest
from unittest.mock import patch
import colony_sustenance as module

class Client:
    def __init__(self, context): self.context=context; self.posts=[]
    def get(self,*args,**kwargs): return self.context
    def post(self,*args,**kwargs): self.posts.append(kwargs['body']); return {'applied':True,'reason':'ordinary_policy_changed'}

class SustenanceTests(unittest.TestCase):
    def setUp(self):
        self.plan={'key':'care:4:2','kind':'care','target_id':4,'value':'2','label':'Cow herbal','cost':'medicine','risk':'competes with humans'}
        self.context={'available':True,'options':[self.plan]}
        self.snapshot={'map':{'id':1},'game':{'tick':30000},'development':{'sustenance':self.context}}
    def test_registered_domains(self):
        self.assertEqual(module.ACTIONS,set(module.LABELS)); self.assertEqual(module.ACTIONS,set(module.DOMAINS))
    def test_partition_and_cooldown(self):
        self.assertEqual(module.prepare(self.snapshot,{}),['sustenance_animal_welfare'])
        self.assertEqual(module.prepare(self.snapshot,{'issued':{'sustenance_animal_welfare':25000}}),['sustenance_animal_welfare'])
    def test_fresh_target_revalidation(self):
        client=Client({'options':[{**self.plan,'value':'3'}]})
        self.assertFalse(module.execute(client,self.snapshot,{},'sustenance_animal_welfare',{'sustenance_policy':self.plan['key']})['applied'])
        self.assertEqual(client.posts,[])
    def test_stale_options_not_posted(self):
        client=Client({'options':[]})
        self.assertFalse(module.execute(client,self.snapshot,{},'sustenance_animal_welfare',{'sustenance_policy':self.plan['key']})['applied'])
    def test_defer_has_cooldown(self):
        state={};client=Client(self.context)
        self.assertFalse(module.execute(client,self.snapshot,state,'sustenance_animal_welfare',{'sustenance_policy':'defer','shown_sustenance_options':[self.plan['key']]})['applied'])
        self.assertEqual(state['sustenance_subject_history']['care:4']['tick'],30000);self.assertEqual(client.posts,[])
    def test_post_verified_key_only(self):
        client=Client(self.context)
        self.assertTrue(module.execute(client,self.snapshot,{},'sustenance_animal_welfare',{'sustenance_policy':self.plan['key']})['applied'])
        self.assertEqual(client.posts,[{'map_id':1,'key':'care:4:2'}])
    def test_rejected_native_order_cools_down(self):
        client=Client(self.context)
        client.post=lambda *args, **kwargs: {'applied':False,'reason':'ordinary_job_not_started'}
        state={}
        result=module.execute(client,self.snapshot,state,'sustenance_animal_welfare',{'sustenance_policy':self.plan['key']})
        self.assertFalse(result['applied'])
        self.assertNotIn('sustenance_animal_welfare',module.prepare(self.snapshot,state))
    def test_producer_food_rot_and_cooler_facts_reach_decision(self):
        context={'food':[{'def_name':'Rice','fresh_eligible_nutrition':2.5}],
                 'perishables':[{'ticks_until_rot':500,'eligible':True},{'ticks_until_rot':2,'eligible':False}],
                 'coolers':[{'id':7,'temperature':19,'powered':False,'target':4}]}
        plan={'kind':'cooler','target_id':7,'value':'-5','label':'Cooler -5 C','risk':'Native heat exhaust restriction'}
        effect=module._effects(context,plan)
        self.assertIn('powered=False',effect['cost'])
        self.assertEqual(effect['risk'],plan['risk'])
        with patch.object(module,'ask_laya_choice',return_value=('defer',{})) as ask:
            module._stage(None,context,[('7',plan['label'],effect)],'sustenance_subject','choose')
        facts=ask.call_args.args[1]['decision_facts']
        self.assertEqual(facts['fresh_nutrition'],2.5)
        self.assertEqual(facts['first_rot_ticks'],500)
        context['food'][0].pop('fresh_eligible_nutrition')
        with patch.object(module,'ask_laya_choice',return_value=('defer',{})) as ask:
            module._stage(None,context,[],'sustenance_subject','choose')
        self.assertIsNone(ask.call_args.args[1]['decision_facts']['fresh_nutrition'])
    def test_diet_effect_includes_actual_allowed_stock(self):
        context={'diets':[{'id':2,'allowed':['Rice']}], 'food':[{'def_name':'Rice','fresh_eligible_nutrition':.5},{'def_name':'Meat_Human','fresh_eligible_nutrition':10}]}
        effect=module._effects(context,{'kind':'diet','value':'2'})
        self.assertIn('Rice:0.5',effect['cost'])
        self.assertNotIn('Meat_Human',effect['cost'])
    def test_native_choice_receives_downsides_and_defer(self):
        with patch.object(module,'ask_laya_choice',return_value=('defer',{})) as choice:
            result,_=module.choose(None,{},'sustenance_animal_welfare',self.snapshot)
            self.assertEqual(result['sustenance_policy'],'defer')
            self.assertEqual(result['shown_sustenance_options'],[self.plan['key']])
            self.assertIn('defer',choice.call_args.args[4]);self.assertIn('risk',choice.call_args.args[1]['option_effects']['o0'])
    def test_loaded_additions_route_and_keep_actual_diet_risk(self):
        custom={**self.plan, 'key':'customdiet:4:Meat_Human:True', 'kind':'customdiet', 'value':'Meat_Human:True', 'risk':'ideology=Cannibal colony; human meat mood'}
        gather={**self.plan, 'key':'gather:4:Milk:2', 'kind':'gather'}
        fish={**self.plan, 'key':'fish:2:3', 'kind':'fish', 'value':'Fish:3'}
        fishzone={**self.plan, 'key':'fishzone:10,20;10,21', 'kind':'fishzone'}
        context={'options':[custom,gather,fish,fishzone], 'fishing':[{'id':3,'population':.75,'frozen':False}]}
        self.assertEqual(set(module.options(context,'sustenance_food_policy')), {custom['key']})
        self.assertEqual(set(module.options(context,'sustenance_animal_welfare')), {gather['key']})
        self.assertEqual(set(module.options(context,'sustenance_food_batch')), {fish['key'],fishzone['key']})
        self.assertIn('population=0.75',module._effects(context,fish)['cost'])
        self.assertIn('Cannibal colony', module._effects(context,custom)['risk'])
    def test_changed_loaded_edible_choice_rejected(self):
        original={**self.plan,'kind':'customdiet','key':'customdiet:4:Rice:True','value':'Rice:True'}
        self.context['options']=[original]
        client=Client({'options':[{**original,'value':'Rice:False'}]})
        result=module.execute(client,self.snapshot,{},'sustenance_food_policy',{'sustenance_policy':original['key']})
        self.assertFalse(result['applied']);self.assertEqual(client.posts,[])
    def test_hazards_distinguish_pasture_from_stored_feed(self):
        self.context.update(animals=[{'food':.1},{'food':None}],pens=[{'consumption_per_day':4,'pasture_nutrition_per_day':1,'stockpiled_nutrition':0},{'consumption_per_day':4,'pasture_nutrition_per_day':1,'stockpiled_nutrition':8}])
        self.assertEqual(module.summary(self.snapshot),{'hungry_animals':{'count':1},'underfed_pens':{'count':1}})
    def test_many_animals_late_subject_keeps_evidence_and_consequences(self):
        import copy, json
        class Tokenizer:
            def __call__(self, text, **kwargs): return {"input_ids": list(range((len(text)+2)//3))}
        class Agent:
            tok=Tokenizer(); cfg={"max_len":512,"head_max_len":192}
            def __init__(self): self.calls=[]
            def predict(self, visible, questions):
                self.calls.append(copy.deepcopy(visible))
                question, data=next(iter(questions.items()))
                choices=[k for k in data['criteria'] if k!='defer']
                chosen=next((k for k,v in visible['effects'].items() if 'food=0.001' in v['cost']),choices[0] if choices else 'defer')
                return {'answers':{question:{'choice':chosen}}}
        self.context['options']=[{**self.plan,'key':f'care:{i}:2','target_id':i,'label':f'Cow #{i} herbal'} for i in range(1,81)]
        self.context['animals']=[{'id':i,'food':0.001 if i==80 else .9,'rest':.5,'pregnant':False,'medical_care':'NoMeds'} for i in range(1,81)]
        agent=Agent(); result,_=module.choose(agent,{},'sustenance_animal_welfare',self.snapshot)
        self.assertEqual(result['sustenance_policy'],'care:80:2')
        self.assertTrue(any('food=0.001' in card['cost'] for call in agent.calls for card in call['effects'].values()))
        for call in agent.calls:
            self.assertLessEqual(len(agent.tok(json.dumps(call,ensure_ascii=False))['input_ids']),312)
            for card in call['effects'].values():
                self.assertEqual(set(card),{'benefit','risk','cost','inaction','uncertainty'})
                self.assertTrue(all(card.values()))
class SustenanceHistoryTests(unittest.TestCase):
    def setUp(self):
        self.plans = [{'key':f'care:{i}:2','kind':'care','target_id':i,'value':'2','label':f'Cow{i} herbal','risk':'Medicine competes with human reserves','cost':'Medicine/labor'} for i in (1,2)]
        self.context = {'available':True,'options':self.plans,'animals':[{'id':i,'food':.9,'downed':False,'pregnant':False,'health':[]} for i in (1,2)]}
        self.s = {'map':{'id':1},'game':{'tick':20000},'development':{'sustenance':self.context}}

    def execute(self, state, plan=None, client=None):
        return module.execute(client or Client(self.context), self.s, state, 'sustenance_animal_welfare', {'sustenance_policy':(plan or self.plans[0])['key']})

    def test_other_animal_not_starved_and_same_family_inverse_dwells(self):
        state={}; self.assertTrue(self.execute(state)['applied'])
        inverse={**self.plans[0],'key':'care:1:4','value':'4'}; self.context['options'].append(inverse)
        self.assertIn('sustenance_animal_welfare', module.prepare(self.s,state))
        available=module.options(self.context,'sustenance_animal_welfare')
        self.assertEqual(list(available),[self.plans[1]['key']])

    def test_new_health_stage_hunger_and_downed_reopen_without_float_drift(self):
        for field, value in [('food',.1),('downed',True),('pregnant',True),('health',[{'def_name':'ModDisease','severity':.5,'stage_index':2,'life_threatening':True}])]:
            state={}; self.context.pop('prepared_options',None)
            animal=self.context['animals'][0]; original=animal.get(field)
            self.execute(state)
            animal[field]=value
            module.prepare(self.s,state)
            self.assertIn(self.plans[0]['key'],module.options(self.context,'sustenance_animal_welfare'),field)
            animal[field]=original
        self.context['animals'][0]['health']=[{'def_name':'ModDisease','severity':.5,'stage_index':1,'life_threatening':False}]
        self.context.pop('prepared_options',None); state={}; self.execute(state)
        self.context['animals'][0]['health'][0]['severity']=.50001
        module.prepare(self.s,state)
        self.assertNotIn(self.plans[0]['key'],module.options(self.context,'sustenance_animal_welfare'))
        self.context['animals'][0]['health'][0]['stage_index']=2
        module.prepare(self.s,state)
        self.assertIn(self.plans[0]['key'],module.options(self.context,'sustenance_animal_welfare'))

    @patch('colony_retry.time.time')
    def test_stale_read_post_and_rejection_backoff_only_failed_option(self, clock):
        clock.return_value = 100
        for mode in ('stale','read','post','rejected','invalid'):
            clock.return_value = 100
            class Failed(Client):
                def get(inner,*args,**kwargs):
                    if mode=='read': raise RuntimeError('GET disconnected')
                    return {'options':[]} if mode=='stale' else self.context
                def post(inner,*args,**kwargs):
                    if mode=='post': raise RuntimeError('POST response lost')
                    return {'applied':False,'reason':'native reason'} if mode=='rejected' else {'applied':'false'}
            self.context.pop('prepared_options',None); state={}
            result=self.execute(state,client=Failed(self.context))
            self.assertFalse(result['applied'])
            self.assertEqual(result.get('outcome_unknown',False),mode in {'post','invalid'})
            if mode=='rejected':self.assertEqual(result['reason'],'native reason')
            module.prepare(self.s,state)
            self.assertEqual(list(module.options(self.context,'sustenance_animal_welfare')),[self.plans[1]['key']])
            clock.return_value = 131
            self.s['game']['tick']+=250; module.prepare(self.s,state)
            self.assertIn(self.plans[0]['key'],module.options(self.context,'sustenance_animal_welfare'))

    def test_shown_only_defer_new_animal_and_other_family_remain(self):
        with patch.object(module,'ask_laya_choice',return_value=('defer',{})):
            selected,_=module.choose(None,{},'sustenance_animal_welfare',self.s)
        state={}; module.execute(Client(self.context),self.s,state,'sustenance_animal_welfare',selected)
        # Purpose stage showed one representative, rather than every animal.
        module.prepare(self.s,state)
        self.assertEqual(list(module.options(self.context,'sustenance_animal_welfare')),[self.plans[1]['key']])
        self.s['game']['tick']+=250; module.prepare(self.s,state)
        self.assertEqual(len(module.options(self.context,'sustenance_animal_welfare')),2)

    @patch('colony_retry.time.time')
    def test_json_roundtrip_rollback_and_expiry(self, clock):
        clock.return_value = 100
        import json
        for failure, advance in [(False,-1),(False,15000),(True,-1),(True,250)]:
            clock.return_value = 100
            self.context.pop('prepared_options',None); state={}
            self.execute(state,client=Client({'options':[]}) if failure else None)
            restored=json.loads(json.dumps(state)); clock.return_value = 131
            self.s['game']['tick']+=advance
            module.prepare(self.s,restored)
            self.assertIn(self.plans[0]['key'],module.options(self.context,'sustenance_animal_welfare'))

    def test_scope_zone_zero_and_distinct_herd_species(self):
        self.assertEqual(module._scope({'kind':'stockpile','target_id':0,'value':'5'}),'stockpile:0')
        self.assertEqual(module._scope({'kind':'stockpile','target_id':0,'value':'2'}),'stockpile:0')
        self.assertNotEqual(module._scope({'kind':'herd','target_id':0,'value':'Cow:2'}),module._scope({'kind':'herd','target_id':0,'value':'Muffalo:2'}))

    def test_malformed_legacy_json_entries_are_pruned(self):
        import json
        state=json.loads('{"sustenance_subject_history":{"care:1":null,"care:2":{"duration":250}},"sustenance_option_backoff":{"sustenance_animal_welfare":{"care:1:2":null,"care:2:2":{"tick":20000}}}}')
        self.assertIn('sustenance_animal_welfare',module.prepare(self.s,state))
        self.assertEqual(state['sustenance_subject_history'],{})
        self.assertEqual(state['sustenance_option_backoff']['sustenance_animal_welfare'],{})

    def test_invalid_context_and_native_unavailable_retain_reason(self):
        for response in ({},'invalid',{'available':False,'reason':'native unavailable'}):
            with self.assertRaises(ValueError): module.collect(Client(response),self.s)
        result=self.execute({},client=Client({'available':False,'reason':'native unavailable'}))
        self.assertIn('native unavailable',result['error'])

    def test_native_cancel_bypasses_dwell_then_requeue_suppressed(self):
        for kind, queued, cancelled in [('sterilize','queue','cancel'),('release','True','False')]:
            plan={'key':kind+':1:'+queued,'kind':kind,'target_id':1,'value':queued}
            cancel={**plan,'key':kind+':1:'+cancelled,'value':cancelled}
            self.context.pop('prepared_options',None); self.context['options']=[plan]; state={}
            result=module.execute(Client(self.context),self.s,state,'sustenance_herd_policy',{'sustenance_policy':plan['key']})
            self.assertTrue(result['applied'])
            self.context['options']=[cancel]; module.prepare(self.s,state)
            self.assertIn(cancel['key'],module.options(self.context,'sustenance_herd_policy'))
            self.assertTrue(module.execute(Client(self.context),self.s,state,'sustenance_herd_policy',{'sustenance_policy':cancel['key']})['applied'])
            self.context['options']=[plan]; module.prepare(self.s,state)
            self.assertNotIn(plan['key'],module.options(self.context,'sustenance_herd_policy'))
            self.assertNotIn(cancel['key'],module.options(self.context,'sustenance_herd_policy'))

    def test_cancel_still_obeys_failed_option_backoff(self):
        cancel={'key':'sterilize:1:cancel','kind':'sterilize','target_id':1,'value':'cancel'}
        self.context['options']=[cancel]; state={}
        class Rejected(Client):
            def post(self,*args,**kwargs): return {'applied':False,'reason':'cancel unavailable'}
        module.execute(Rejected(self.context),self.s,state,'sustenance_herd_policy',{'sustenance_policy':cancel['key']})
        self.assertNotIn('sustenance_herd_policy',module.prepare(self.s,state))

    def test_cooler_thaw_reopens_but_small_drift_does_not(self):
        plan={'key':'cooler:5:-9','kind':'cooler','target_id':5,'value':'-9'}
        self.context.update(options=[plan],coolers=[{'id':5,'temperature':-2.,'powered':True}]);state={}
        module.execute(Client(self.context),self.s,state,'sustenance_preservation',{'sustenance_policy':plan['key']})
        self.context['coolers'][0]['temperature']=-1.999; module.prepare(self.s,state)
        self.assertNotIn('sustenance_preservation',module.prepare(self.s,state))
        self.context['coolers'][0]['temperature']=2.;module.prepare(self.s,state)
        self.assertIn('sustenance_preservation',module.prepare(self.s,state))

    def test_pen_shortfall_and_herd_growth_reopen_subject(self):
        pen={'key':'pen:9:Cow:True','kind':'pen','target_id':9,'value':'Cow:True'}
        self.context.update(options=[pen],pens=[{'id':9,'enclosed':True,'consumption_per_day':4.,'pasture_nutrition_per_day':5.,'stockpiled_nutrition':8.}]);state={}
        module.execute(Client(self.context),self.s,state,'sustenance_animal_welfare',{'sustenance_policy':pen['key']})
        self.context['pens'][0]['pasture_nutrition_per_day']=5.001;module.prepare(self.s,state)
        self.assertNotIn('sustenance_animal_welfare',module.prepare(self.s,state))
        self.context['pens'][0]['pasture_nutrition_per_day']=1.;module.prepare(self.s,state)
        self.assertIn('sustenance_animal_welfare',module.prepare(self.s,state))
        herd={'key':'herd:Cow:2','kind':'herd','target_id':0,'value':'Cow:2'}
        self.context.pop('prepared_options',None);self.context['options']=[herd]
        self.context['animals']=[{'id':1,'species':'Cow','food':.9}];state={}
        module.execute(Client(self.context),self.s,state,'sustenance_herd_policy',{'sustenance_policy':herd['key']})
        self.context['animals'].append({'id':2,'species':'Cow','food':.9});module.prepare(self.s,state)
        self.assertIn('sustenance_herd_policy',module.prepare(self.s,state))

    def test_food_pawn_new_hunger_reopens_diet(self):
        plan={'key':'diet:5:2','kind':'diet','target_id':5,'value':'2'}
        self.context.update(options=[plan],food_pawns=[{'id':5,'food':.9,'health':[]}]);state={}
        module.execute(Client(self.context),self.s,state,'sustenance_food_policy',{'sustenance_policy':plan['key']})
        self.context['food_pawns'][0]['food']=.1; module.prepare(self.s,state)
        self.assertIn('sustenance_food_policy',module.prepare(self.s,state))


class SustenanceVisibleFactsTests(unittest.TestCase):
    def test_goal_food_and_clinical_evidence_survive_real_bounded_adapter(self):
        import copy,json
        class Tokenizer:
            def __call__(self,text,**kwargs):return {'input_ids':list(range((len(text)+2)//3))}
        class Agent:
            tok=Tokenizer();cfg={'max_len':512,'head_max_len':192}
            def __init__(self):self.calls=[]
            def predict(self,state,questions):
                self.calls.append(copy.deepcopy(state));qid,q=next(iter(questions.items()))
                choice=next((k for k,v in state['effects'].items() if 'BloodLoss:0.7' in v['risk']),next(k for k in q['criteria'] if k!='defer'))
                return {'answers':{qid:{'choice':choice}}}
        plans=[{'key':f'care:{i}:2','kind':'care','target_id':i,'value':'2','label':f'Cow{i} herbal','risk':'Medicine competes with human reserves','cost':'normal tending'} for i in (1,2)]
        context={'options':plans,'food':[{'fresh_eligible_nutrition':2.5}],'perishables':[{'ticks_until_rot':200,'eligible':True}],
                 'animals':[{'id':1,'food':.9,'health':[]},{'id':2,'food':.1,'downed':True,'pregnant':True,'health':[{'def_name':'BloodLoss','severity':.7,'stage_index':2,'life_threatening':True}]}]}
        snapshot={'development':{'sustenance':context}}
        agent=Agent();chosen,_=module.choose(agent,{'endgame':'ship_escape','goal_requirements':{'journey':'Pemmican:40'}},'sustenance_animal_welfare',snapshot)
        self.assertEqual(chosen['sustenance_policy'],'care:2:2')
        for call in agent.calls:
            self.assertLessEqual(len(agent.tok(json.dumps(call,ensure_ascii=False))['input_ids']),312)
            self.assertIn('ship_escape',str(call['facts']));self.assertIn('Pemmican:40',str(call['facts']))
            self.assertIn('2.5',str(call['facts']));self.assertIn('200',str(call['facts']))
            self.assertTrue(all(set(card)=={'benefit','cost','risk','inaction','uncertainty'} for card in call['effects'].values()))
        cards=[card for call in agent.calls for card in call['effects'].values()]
        self.assertTrue(any('BloodLoss:0.7' in card['risk'] for card in cards))
        self.assertTrue(any('downed=True' in card['cost'] for card in cards))

if __name__=='__main__': unittest.main()

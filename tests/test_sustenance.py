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
        self.assertEqual(module.prepare(self.snapshot,{'issued':{'sustenance_animal_welfare':25000}}),[])
    def test_fresh_target_revalidation(self):
        client=Client({'options':[{**self.plan,'value':'3'}]})
        self.assertFalse(module.execute(client,self.snapshot,{},'sustenance_animal_welfare',{'sustenance_policy':self.plan['key']})['applied'])
        self.assertEqual(client.posts,[])
    def test_stale_options_not_posted(self):
        client=Client({'options':[]})
        self.assertFalse(module.execute(client,self.snapshot,{},'sustenance_animal_welfare',{'sustenance_policy':self.plan['key']})['applied'])
    def test_defer_has_cooldown(self):
        state={};client=Client(self.context)
        self.assertFalse(module.execute(client,self.snapshot,state,'sustenance_animal_welfare',{'sustenance_policy':'defer'})['applied'])
        self.assertEqual(state['issued']['sustenance_animal_welfare'],30000);self.assertEqual(client.posts,[])
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
            self.assertEqual(result,{'sustenance_policy':'defer'})
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
if __name__=='__main__': unittest.main()

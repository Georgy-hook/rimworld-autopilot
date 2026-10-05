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
        s=self.snapshot(); c=Client({}); m={};p.prepare(s,m)
        r=p.execute(c,s,m,'production_feed_batch',{'production_policy':'defer'})
        self.assertFalse(r['applied']); self.assertEqual([],c.calls)
        self.assertEqual(20000,m['production_selection_dwell']['production_feed_batch']['3']['tick'])
        self.assertNotIn('production_feed_batch',p.prepare(self.snapshot(),m))
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
        state={'issued':{'production:production_material_logistics':19000}}
        self.assertIn('production_material_logistics',p.prepare(s,state))
        self.assertNotIn('production:production_material_logistics',state['issued'])
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

class IndependentProductionTests(unittest.TestCase):
    def snapshot(self):
        s = ProductionTests().snapshot()
        s["development"]["production"]["buildings"].append({"id": 9, "def_name": "Heater", "switch_on": True})
        p.prepare(s, {})
        return s

    def client(self, s, fail=None, response=None):
        context = copy.deepcopy(s["development"]["production"])
        class IndependentClient(Client):
            def get(self, path, **kwargs):
                self.calls.append(("GET", path))
                if fail == path:
                    raise RuntimeError("endpoint disconnected")
                return copy.deepcopy(context) if path.endswith('/context') else {"available": True, "options": []}
            def post(self, path, **kwargs):
                self.calls.append(("POST", path))
                if fail == "POST":
                    raise RuntimeError("response lost")
                return response if response is not None else {"applied": True, "reason": "accepted"}
        return IndependentClient(context)

    def test_failed_recipes_preserve_utilities_feed_and_error(self):
        s = self.snapshot(); c = self.client(s, p.ENDPOINTS['recipes'])
        observed = p.collect(c, s)
        self.assertTrue(observed['available'])
        self.assertFalse(observed['endpoint_status']['recipes']['available'])
        self.assertIn('endpoint disconnected', observed['recipe_context']['reason'])
        s['development']['production'] = observed
        actions = p.prepare(s, {})
        self.assertIn('production_utilities', actions)
        self.assertIn('production_feed_batch', actions)
        self.assertNotIn('production_recipe_batch', actions)
        self.assertEqual(p.summary(s)['production_endpoint_failures'], 1)

    def test_context_failure_preserves_recipe_endpoint(self):
        s = self.snapshot()
        class RecipeOnly(Client):
            def get(self, path, **kwargs):
                if path.endswith('/context'): return {'available': False, 'reason': 'native blocked'}
                return {'options': [RecipeProductionTests().plan()]} if path.endswith('/recipes') else {'options': []}
        observed = p.collect(RecipeOnly({}), s)
        self.assertFalse(observed['endpoint_status']['context']['available'])
        self.assertIn('native blocked', observed['endpoint_status']['context']['error'])
        s['development']['production'] = observed
        self.assertEqual(p.prepare(s, {}), ['production_recipe_batch'])

    def test_invalid_endpoint_is_not_empty_success(self):
        s = self.snapshot()
        class InvalidRecipes(Client):
            def get(self, path, **kwargs):
                return {} if path.endswith('/recipes') else ({'buildings': []} if path.endswith('/context') else {'options': []})
        observed = p.collect(InvalidRecipes({}), s)
        self.assertFalse(observed['endpoint_status']['recipes']['available'])
        self.assertIn('invalid_response', observed['recipe_context']['reason'])

    def test_utilities_and_feed_read_only_context(self):
        for action, key in [('production_utilities', '2:switch_off'), ('production_feed_batch', '3')]:
            s = self.snapshot(); c = self.client(s, p.ENDPOINTS['recipes'])
            self.assertTrue(p.execute(c, s, {}, action, {'production_policy': key})['applied'])
            self.assertEqual(c.calls, [('GET', p.ENDPOINTS['context']), ('POST', '/api/v1/production/policy')])

    def test_recipe_and_logistics_read_only_own_endpoint(self):
        for action, fixture, endpoint, post in [
            ('production_recipe_batch', RecipeProductionTests(), 'recipes', '/api/v1/production/recipe-bill'),
            ('production_material_logistics', LogisticsProductionTests(), 'logistics', '/api/v1/production/logistics')]:
            s = fixture.snapshot(); plan = fixture.plan()
            class OnlyEndpoint(Client):
                def get(self, path, **kwargs):
                    self.calls.append(('GET', path))
                    if path != p.ENDPOINTS[endpoint]: raise AssertionError('unrelated read')
                    return {'options': [copy.deepcopy(plan)]}
                def post(self, path, **kwargs):
                    self.calls.append(('POST', path)); return {'applied': True}
            c = OnlyEndpoint({})
            self.assertTrue(p.execute(c, s, {}, action, {'production_policy': plan['key']})['applied'])
            self.assertEqual(c.calls, [('GET', p.ENDPOINTS[endpoint]), ('POST', post)])

    @patch('colony_retry.time.time')
    def test_stale_option_backoff_preserves_alternative_and_expires(self, clock):
        clock.return_value = 100
        s = self.snapshot(); c = self.client(s)
        c.context['buildings'][0]['switch_on'] = False
        # Use a live changed context without altering the observed projection.
        class Changed(Client):
            def get(self, *args, **kwargs):return copy.deepcopy(c.context)
        state = {}; result = p.execute(Changed({}), s, state, 'production_utilities', {'production_policy': '2:switch_off'})
        self.assertEqual(result['reason'], 'policy_no_longer_available')
        self.assertIn('production_utilities', p.prepare(s, state))
        plans = s['development']['production']['options']
        self.assertNotIn('2:switch_off', plans); self.assertIn('9:switch_off', plans)
        clock.return_value = 131
        s['game']['tick'] += p.BACKOFF_TICKS
        p.prepare(s, state)
        self.assertIn('2:switch_off', s['development']['production']['options'])

    def test_stale_recipe_and_logistics_filter_only_selected_option(self):
        for action, fixture, endpoint in [('production_recipe_batch', RecipeProductionTests(), 'recipes'),
                                          ('production_material_logistics', LogisticsProductionTests(), 'logistics')]:
            s = fixture.snapshot(); second = copy.deepcopy(fixture.plan()); second['key'] += ':alternate'
            context = s['development']['production'][('recipe_context' if endpoint == 'recipes' else 'logistics_context')]
            context['options'].append(second)
            class Changed(Client):
                def get(self, *args, **kwargs):return {'options': [copy.deepcopy(second)]}
            state = {}; p.execute(Changed({}), s, state, action, {'production_policy': fixture.plan()['key']})
            self.assertIn(action, p.prepare(s, state))
            plans = p.recipe_options(s['development']['production']) if endpoint == 'recipes' else p.logistics_options(s['development']['production'])
            self.assertEqual(list(plans), [second['key']])

    def test_read_and_post_failures_backoff_one_option_and_report_uncertainty(self):
        for fail, reason in [(p.ENDPOINTS['context'], 'production_observation_failed'), ('POST', 'production_transport_failed')]:
            s = self.snapshot(); state = {}; c = self.client(s, fail)
            result = p.execute(c, s, state, 'production_utilities', {'production_policy': '2:switch_off'})
            self.assertFalse(result['applied']); self.assertEqual(result['reason'], reason)
            self.assertIn('endpoint disconnected' if fail != 'POST' else 'response lost', result['error'])
            self.assertEqual(result.get('outcome_unknown', False), fail == 'POST')
            self.assertIn('production_utilities', p.prepare(s, state))
            self.assertNotIn('2:switch_off', s['development']['production']['options'])
            self.assertIn('9:switch_off', s['development']['production']['options'])

    def test_native_rejection_reason_retained_without_category_starvation(self):
        s = self.snapshot(); state = {}; c = self.client(s, response={'applied': False, 'reason': 'missing_switch_or_pending_flick'})
        result = p.execute(c, s, state, 'production_utilities', {'production_policy': '2:switch_off'})
        self.assertEqual(result['reason'], 'missing_switch_or_pending_flick')
        self.assertIn('production_utilities', p.prepare(s, state))
        self.assertNotIn('production:production_utilities', state.get('issued', {}))

    @patch('colony_retry.time.time')
    def test_failure_history_survives_json_and_expires_after_short_horizon(self, clock):
        clock.return_value = 100
        import json
        s = self.snapshot(); state = {}
        p.execute(self.client(s, 'POST'), s, state, 'production_utilities', {'production_policy': '2:switch_off'})
        restored = json.loads(json.dumps(state))
        s['game']['tick'] += 249
        p.prepare(s, restored)
        self.assertNotIn('2:switch_off', s['development']['production']['options'])
        clock.return_value = 131
        s['game']['tick'] += 1
        p.prepare(s, restored)
        self.assertIn('2:switch_off', s['development']['production']['options'])
        self.assertEqual(restored['production_option_backoff']['production_utilities'], {})

    def test_failure_history_from_future_is_pruned_after_tick_rollback(self):
        import json
        s = self.snapshot(); state = {}
        p.execute(self.client(s, 'POST'), s, state, 'production_utilities', {'production_policy': '2:switch_off'})
        restored = json.loads(json.dumps(state)); s['game']['tick'] -= 100
        p.prepare(s, restored)
        self.assertIn('2:switch_off', s['development']['production']['options'])
        self.assertEqual(restored['production_option_backoff']['production_utilities'], {})

    def test_storage_blockage_signals_distinguish_work_and_route(self):
        s = self.snapshot(); s['development']['production']['logistics_context'] = {'blocked': [
            {'def_name': 'Steel', 'reason': 'storage_capacity_exists_no_eligible_hauler'},
            {'def_name': 'WoodLog', 'reason': 'storage_capacity_exists_route_reservation_or_priority_blocked'}]}
        signals = p.summary(s)
        self.assertEqual(signals['production_storage_no_hauler'], 1)
        self.assertEqual(signals['production_storage_route_blocked'], 1)

class UtilityDwellTests(unittest.TestCase):
    def snapshot(self):
        s = IndependentProductionTests().snapshot()
        for building in s['development']['production']['buildings']:
            building['temperature'] = 20
        p.prepare(s, {})
        return s

    def accept(self, s, state, key='2:switch_off'):
        c = IndependentProductionTests().client(s)
        self.assertTrue(p.execute(c, s, state, 'production_utilities', {'production_policy': key})['applied'])

    def test_success_lamp_does_not_hide_new_urgent_heater(self):
        s = self.snapshot(); state = {}; self.accept(s, state)
        s['development']['production']['buildings'].append({'id': 12, 'def_name': 'Heater', 'switch_on': False, 'temperature': -20})
        s['game']['tick'] += 1
        self.assertIn('production_utilities', p.prepare(s, state))
        self.assertIn('12:switch_on', s['development']['production']['options'])
        self.assertNotIn('2:switch_off', s['development']['production']['options'])

    def test_inverse_same_building_family_dwell_refuel_independent(self):
        s = self.snapshot(); state = {}; self.accept(s, state)
        b = s['development']['production']['buildings'][0]
        b.update(switch_on=False, can_set_auto_refuel=True, auto_refuel=False)
        p.prepare(s, state)
        self.assertNotIn('2:switch_on', s['development']['production']['options'])
        self.assertIn('2:enable_refuel', s['development']['production']['options'])

    def test_thermal_band_change_reopens_without_float_drift(self):
        s = self.snapshot(); state = {}; self.accept(s, state)
        b = s['development']['production']['buildings'][0]; b['switch_on'] = False
        b['temperature'] = 20.001; p.prepare(s, state)
        self.assertNotIn('2:switch_on', s['development']['production']['options'])
        b['temperature'] = 9.9; p.prepare(s, state)
        self.assertIn('2:switch_on', s['development']['production']['options'])
        self.assertEqual(state['production_utility_dwell'], {})
        self.accept(s, state, '2:switch_on')
        b['temperature'] = 33; p.prepare(s, state)
        self.assertIn('2:switch_on', s['development']['production']['options'])

    def test_building_stage_defer_covers_current_subjects_not_new_building(self):
        s = self.snapshot(); state = {}
        b = s['development']['production']['buildings'][0]
        b.update(can_set_auto_refuel=True, auto_refuel=False)
        p.prepare(s, state)
        with patch.object(p, 'ask_laya_choice', return_value=('defer', {})):
            selected, _ = p.choose(None, {}, 'production_utilities', s)
        self.assertIn('2:switch_off', selected['shown_utility_options'])
        self.assertIn('2:enable_refuel', selected['shown_utility_options'])
        p.execute(Client({}), s, state, 'production_utilities', selected)
        s['development']['production']['buildings'].append({'id': 12, 'def_name': 'Heater', 'switch_on': False, 'temperature': -20})
        p.prepare(s, state)
        plans = s['development']['production']['options']
        self.assertIn('12:switch_on', plans); self.assertNotIn('2:enable_refuel', plans)
        self.assertNotIn('2:switch_off', plans)
        s['game']['tick'] += 250; p.prepare(s, state)
        self.assertNotIn('2:switch_off', s['development']['production']['options'])

    def test_success_dwell_json_rollback_and_expiry(self):
        import json
        for change in (-1, 15000):
            s = self.snapshot(); state = {}; self.accept(s, state)
            restored = json.loads(json.dumps(state))
            s['game']['tick'] += change; p.prepare(s, restored)
            self.assertIn('2:switch_off', s['development']['production']['options'])
            self.assertEqual(restored['production_utility_dwell'], {})

    def test_old_global_utility_lock_is_retired(self):
        s = self.snapshot(); state = {'issued': {'production:production_utilities': 20000}}
        self.assertIn('production_utilities', p.prepare(s, state))
        self.assertNotIn('production:production_utilities', state['issued'])

if __name__=='__main__':unittest.main()


class UtilityRuntimeRegressionTests(unittest.TestCase):
    def fixture(self):
        b={'id':7,'def_name':'Cooler','label':'Cooler','power_output':-200,'connected':True,
           'net_has_active_source':True,'net_stored_energy':0,'switch_on':True,'temperature':20,
           'fuel':5,'capacity':20,'eligible_fuel_count':0,'auto_refuel':True,'can_set_auto_refuel':True}
        c={'available':True,'buildings':[b],'stocks':[],'animals':[],'feed_tables':[]}
        return {'map':{'id':1},'game':{'tick':1000},'development':{'production':c,'sustenance':{'human_food':[{'fresh_eligible_nutrition':.35}]}}},b
    def test_disconnected_lamp_cannot_claim_restored_service(self):
        s,b=self.fixture();b.update(def_name='StandingLamp',switch_on=False,connected=False,fuel=None)
        self.assertNotIn('7:switch_on',p.options(s['development']['production']))
        b.update(connected=True,net_has_active_source=False)
        self.assertNotIn('7:switch_on',p.options(s['development']['production']))
        b['net_stored_energy']=.1
        self.assertIn('7:switch_on',p.options(s['development']['production']))
    @patch('colony_retry.time.time')
    def test_eight_defer_cycles_persist_both_clocks_and_new_fuel_resets(self,clock):
        import json
        s,b=self.fixture();state={};clock.return_value=100;p.prepare(s,state)
        p.execute(Client({}),s,state,'production_utilities',{'production_policy':'defer','shown_utility_options':list(s['development']['production']['options'])})
        for i in range(8):
            state=json.loads(json.dumps(state));clock.return_value=110+i*10;s['game']['tick']=40000+i*1000
            b.update(fuel=4-i*.1,temperature=20+i*.01)
            self.assertNotIn('production_utilities',p.prepare(s,state))
        b['eligible_fuel_count']=5
        self.assertIn('production_utilities',p.prepare(s,state))
    def test_first_comparison_exposes_human_food_and_empty_fuel(self):
        s,b=self.fixture();b['fuel']=0;p.prepare(s,{})
        with patch.object(p,'ask_laya_choice',return_value=('defer',{})) as ask:
            p.choose(None,{},'production_utilities',s)
        facts=ask.call_args.args[1]['decision_facts']
        self.assertEqual(facts['human_food'],.35);self.assertEqual(facts['animals'],0);self.assertEqual(facts['empty_fuel'],1)

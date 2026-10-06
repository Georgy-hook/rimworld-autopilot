import copy
import json
import unittest
from unittest.mock import patch
import colony_mental_safety as mental
import rimworld_laya as bridge
import colony_combat
import stream_observer


class Client:
    def __init__(self,data,acklost=False,getlost=False,decline=False):
        self.data=data;self.posts=[];self.acklost=acklost;self.getlost=getlost;self.decline=decline;self.gets=0
    def get(self,*args,**kwargs):
        self.gets+=1
        if self.getlost and self.gets>1:raise mental.bridge.RimApiError('GET lost')
        return copy.deepcopy(self.data)
    def post(self,endpoint,*,body):
        self.posts.append(body)
        if self.decline:return {'applied':False}
        if body.get('cancel'):self.data['orders'][0]['job']='TendPatient'
        else:self.data['orders'][0].update(job='Goto',cell={'x':20,'z':20})
        if self.acklost:raise mental.bridge.RimApiError('ACK lost')
        return {'applied':True}


class MentalSafetyTests(unittest.TestCase):
    def setUp(self):
        self.plan={'key':'evacuate:2:1:20:20','session':'rage-a','kind':'evacuate','actor_id':1,'victim_id':1,'aggressor_id':2,
                   'cell':{'x':20,'z':20},'label':'Evacuate victim','risk':'Pursuit; concurrent raid'}
        self.data={'available':True,'map_id':0,'options':[self.plan],'orders':[{'actor_id':1,'job':'Wait','position':{'x':0,'z':0}}],
                   'threats':[{'aggressor_id':2,'victim_id':1,'session':'rage-a'}]}
        self.snapshot={'game':{'tick':100},'map':{'id':0},'development':{'mental_safety':self.data},
                       'combat':{'colonists':[{'id':2,'is_in_mental_state':True,'mental_state_def':'MurderousRage','mental_state_session':'rage-a','mental_state_target_id':1}],
                                 'hostiles':[{'id':9,'is_dead':False,'is_downed':False}]}}
        self.state={};mental.prepare(self.snapshot,self.state)

    def test_named_target_preserved_without_adding_enemy(self):
        colonists=[{'id':2}];bridge.annotate_mental_states(colonists,self.snapshot['combat']['colonists'])
        self.assertEqual(1,colonists[0]['mental_state_target_id'])
        self.assertEqual([9],[p['id'] for p in colony_combat.live_hostiles(self.snapshot)])
        self.assertEqual(1,bridge.murderous_rage_context(self.snapshot['combat'])[0]['victim_id'])

    def test_unrelated_mental_break_and_dead_aggressor_not_named_threat(self):
        for changes in ({'mental_state_def':'SadWander'},{'is_dead':True},{'is_downed':True},{'mental_state_target_id':None}):
            combat={'colonists':[{**self.snapshot['combat']['colonists'][0],**changes}]}
            self.assertFalse(bridge.murderous_rage_context(combat))

    def test_observer_slowing_preserves_director_not_ready_pause(self):
        planner=stream_observer.ObserverPlanner()
        actions=planner.pacing_actions({'is_paused':False,'speed':3},100,critical_mental=True)
        self.assertEqual(1,actions[0]['speed'])
        actions=planner.pacing_actions({'is_paused':False,'speed':3},101,critical_mental=True,director_is_ready=False)
        self.assertEqual(0,actions[0]['speed'])

    @patch('colony_retry.time.time',return_value=1000)
    def test_exact_actual_job_lost_ack_recovers_without_second_actor(self,clock):
        client=Client(self.data,acklost=True)
        result=mental.execute(client,self.snapshot,self.state,'mental_safety_response',{'plan':self.plan})
        self.assertTrue(result['applied']);self.assertEqual('unverified',result['completion'])
        self.assertEqual([],mental.prepare(self.snapshot,self.state))
        self.assertFalse(mental.execute(client,self.snapshot,self.state,'mental_safety_response',{'plan':self.plan})['applied'])
        self.assertEqual(1,len(client.posts))

    @patch('colony_retry.time.time',return_value=1000)
    def test_unknown_readback_json_restart_retains_lease(self,clock):
        client=Client(self.data,acklost=True,getlost=True)
        self.assertTrue(mental.execute(client,self.snapshot,self.state,'mental_safety_response',{'plan':self.plan})['outcome_unknown'])
        self.state=json.loads(json.dumps(self.state))
        self.assertTrue(mental.reconcile(client,self.snapshot,self.state)['lease_retained'])
        self.assertEqual([],mental.prepare(self.snapshot,self.state))
        client.getlost=False
        self.assertTrue(mental.reconcile(client,self.snapshot,self.state)['in_progress'])
        self.assertEqual(1,len(client.posts))

    @patch('colony_retry.time.time',return_value=1000)
    def test_oscillation_stalls_and_matching_cancel_readback_releases(self,clock):
        client=Client(self.data)
        mental.execute(client,self.snapshot,self.state,'mental_safety_response',{'plan':self.plan})
        for i in range(4):
            self.data['orders'][0]['position']={'x':-(i%2),'z':0}
            self.snapshot['game']['tick']+=2000;clock.return_value=1000+i*31
            result=mental.reconcile(client,self.snapshot,self.state)
        self.assertEqual([],result['active_ids'])
        self.assertTrue(client.posts[-1]['cancel'])
        self.assertEqual('TendPatient',self.data['orders'][0]['job'])

    def test_fresh_stale_pair_rejected_before_post(self):
        client=Client({**self.data,'options':[]})
        result=mental.execute(client,self.snapshot,self.state,'mental_safety_response',{'plan':self.plan})
        self.assertFalse(result['applied']);self.assertEqual([],client.posts)

    @patch('colony_retry.time.time',return_value=1000)
    def test_refusal_and_success_ack_without_job_are_not_applied(self,clock):
        client=Client(self.data,decline=True)
        result=mental.execute(client,self.snapshot,self.state,'mental_safety_response',{'plan':self.plan})
        self.assertFalse(result['applied'])
        self.assertNotIn('active',self.state['mental_safety'])
        self.assertEqual(['mental_safety_response'],mental.prepare(self.snapshot,self.state))
        self.assertEqual({},self.data['plans'])

    def test_rescue_and_arrest_readback_require_exact_target_and_bed(self):
        for kind,job,target in [('arrest','Arrest',2),('rescue','Rescue',1)]:
            plan={**self.plan,'kind':kind,'bed_id':50}
            data={**self.data,'orders':[{'actor_id':1,'job':job,'target_id':target,'bed_id':50}]}
            self.assertTrue(mental._observed(data,plan))
            data['orders'][0]['bed_id']=51;self.assertFalse(mental._observed(data,plan))

    @patch('colony_retry.time.time',return_value=1000)
    def test_observe_no_options_dwell_new_target_and_new_plan_bypass(self,clock):
        self.data['options']=[]
        mental.execute(Client(self.data),self.snapshot,self.state,'mental_safety_response',{'plan':None})
        self.assertEqual([],mental.prepare(self.snapshot,self.state))
        self.data['options']=[self.plan]
        self.assertEqual(['mental_safety_response'],mental.prepare(self.snapshot,self.state))
        self.data['options']=[];self.data['threats'][0]['victim_id']=3
        self.assertEqual(['mental_safety_response'],mental.prepare(self.snapshot,self.state))

    @patch('colony_retry.time.time',return_value=1000)
    def test_ended_state_releases_lease_immediately_without_cancelling_normal_job(self,clock):
        client=Client(self.data);mental.execute(client,self.snapshot,self.state,'mental_safety_response',{'plan':self.plan})
        self.snapshot['combat']['colonists'][0]['is_in_mental_state']=False
        self.assertEqual([],mental.reconcile(client,self.snapshot,self.state)['active_ids'])
        self.assertEqual('Goto',self.data['orders'][0]['job']);self.assertEqual(1,len(client.posts))

    @patch('colony_retry.time.time',return_value=1000)
    def test_prolonged_unknown_readback_yields_defense_protection_without_double_order(self,clock):
        client=Client(self.data,getlost=True)
        mental.execute(client,self.snapshot,self.state,'mental_safety_response',{'plan':self.plan})
        self.snapshot['game']['tick']+=6000;clock.return_value=1091
        result=mental.reconcile(client,self.snapshot,self.state)
        self.assertEqual([],result['active_ids']);self.assertTrue(result['attention_required'])
        self.assertEqual([],mental.prepare(self.snapshot,self.state));self.assertEqual(1,len(client.posts))

    def test_model_receives_precise_native_arrest_chance_and_roles(self):
        plan={**self.plan,'kind':'arrest','arrest_chance':.37,'key':'arrest:2:3:50','actor_id':3,'bed_id':50}
        self.data['options']=[plan];mental.prepare(self.snapshot,self.state)
        with patch.object(mental,'ask_laya_choice',return_value=('o0',{})) as ask:
            selected,_=mental.choose(object(),{'decision_facts':{'care_risks':{'bleed':1.7}}},'mental_safety_response',self.snapshot)
        context=ask.call_args.args[1]
        self.assertIn('0.37',context['option_effects']['o0']['risk'])
        self.assertIn('actor#3',context['option_effects']['o0']['benefit'])
        self.assertEqual(1.7,context['decision_facts']['care_risks']['bleed'])
        self.assertEqual(plan,selected['plan'])

    def test_collect_without_named_rage_avoids_expensive_api(self):
        self.snapshot['combat']['colonists'][0]['mental_state_def']='SadWander'
        from unittest.mock import Mock
        client=Mock()
        self.assertEqual([],mental.collect(client,self.snapshot)['options'])
        client.get.assert_not_called()

    @patch('colony_retry.time.time',return_value=1000)
    def test_actual_director_helper_raid_observe_dwell_nonblocking(self,clock):
        import colony_director as director
        from pathlib import Path
        client=Client(self.data)
        with patch.object(mental,'ask_laya_choice',return_value=('observe',{})) as ask, patch.object(director.bridge,'append_log'):
            record=director.run_mental_safety_cycle(client,object(),self.snapshot,self.state,Path('unused.jsonl'))
            self.assertFalse(record['blocks_development'])
            self.assertEqual(1,ask.call_args.args[1]['decision_facts']['concurrent_hostiles'])
            self.assertIsNone(director.run_mental_safety_cycle(client,object(),self.snapshot,self.state,Path('unused.jsonl')))
            self.assertEqual(1,ask.call_count)
        self.assertEqual([],client.posts)
        self.assertEqual([9],[p['id'] for p in colony_combat.live_hostiles(self.snapshot)])

    @patch('colony_retry.time.time',return_value=1000)
    def test_actual_director_helper_raid_accepted_nextloop_preserves_job_without_blocking(self,clock):
        import colony_director as director
        from pathlib import Path
        client=Client(self.data)
        with patch.object(mental,'ask_laya_choice',return_value=('o0',{})) as ask, patch.object(director.bridge,'append_log'):
            record=director.run_mental_safety_cycle(client,object(),self.snapshot,self.state,Path('unused.jsonl'))
            self.assertTrue(record['result']['applied']);self.assertFalse(record['blocks_development'])
            self.snapshot=json.loads(json.dumps(self.snapshot));self.state=json.loads(json.dumps(self.state))
            self.assertIsNone(director.run_mental_safety_cycle(client,object(),self.snapshot,self.state,Path('unused.jsonl')))
            self.assertEqual([1],self.snapshot['development']['mental_safety_active_ids'])
            self.assertEqual(1,ask.call_count)
        self.assertEqual(1,len(client.posts));self.assertEqual('Goto',self.data['orders'][0]['job'])
        self.assertEqual([9],[p['id'] for p in colony_combat.live_hostiles(self.snapshot)])

    def response_snapshot(self):
        snapshot=copy.deepcopy(self.snapshot)
        snapshot['game']['is_paused']=False
        snapshot['map']['enemies']=1
        snapshot['combat']['colonists']=[
            {'id':1,'health':1,'is_drafted':True,'can_fight':True,'has_ranged_weapon':True,
             'current_job':'Goto','current_job_cell':{'x':20,'z':20},'position':{'x':0,'z':0}},
            {'id':2,'is_in_mental_state':True,'mental_state_def':'MurderousRage','mental_state_session':'rage-a','mental_state_target_id':1,'position':{'x':1,'z':1}},
            {'id':3,'health':1,'is_drafted':True,'can_fight':True,'has_ranged_weapon':True,'position':{'x':2,'z':0}}]
        snapshot['combat']['hostiles']=[{'id':9,'position':{'x':30,'z':30},'is_dead':False,'is_downed':False}]
        snapshot['combat']['protected_response_plans']=[self.plan]
        return snapshot

    def test_actual_bridge_run_cycle_raid_keeps_verified_response_actor(self):
        import rimworld_laya as live_bridge
        from pathlib import Path
        snapshot=self.response_snapshot()
        with patch.object(live_bridge,'collect_snapshot',return_value=snapshot), patch.object(live_bridge,'decide',return_value={'choice':'focus_fire'}), patch.object(live_bridge,'apply_action',return_value={'applied':True}) as apply, patch.object(live_bridge,'append_log'):
            record=live_bridge.run_cycle(object(),object(),apply=True,confidence=.8,log_path=Path('unused'),protected_response_plans=[self.plan])
        ids=[pid for c in record['action'].get('commands',[]) for pid in c.get('body',{}).get('fighter_ids',[])]
        self.assertNotIn(1,ids);self.assertIn(3,ids)
        self.assertEqual(record['action'],apply.call_args.args[1])

    def test_fresh_danger_or_urgent_medical_releases_and_stale_plan_never_protects(self):
        for change in ('danger','clinical','session','job','target'):
            snapshot=self.response_snapshot()
            if change=='danger':snapshot['combat']['hostiles'][0]['position']={'x':1,'z':0}
            elif change=='clinical':snapshot['combat']['colonists'][0].update(tendable_now=True,bleeding_rate=1.7)
            elif change=='session':snapshot['combat']['colonists'][1]['mental_state_session']='new-rage'
            elif change=='job':snapshot['combat']['colonists'][0]['current_job']='Wait_Combat'
            else:snapshot['combat']['colonists'][1]['mental_state_target_id']=3
            self.assertNotIn(1,colony_combat.protected_response_ids(snapshot))
        snapshot=self.response_snapshot()
        action=mental.bridge.plan_action(snapshot,{'choice':'stand_down'})
        self.assertNotIn(1,[c.get('body',{}).get('pawn_id') for c in action['commands']])

    def test_actual_bridge_run_cycle_immediate_enemy_releases_actor(self):
        import rimworld_laya as live_bridge
        from pathlib import Path
        snapshot=self.response_snapshot();snapshot['combat']['hostiles'][0]['position']={'x':1,'z':0}
        with patch.object(live_bridge,'collect_snapshot',return_value=snapshot), patch.object(live_bridge,'decide',return_value={'choice':'focus_fire'}), patch.object(live_bridge,'apply_action',return_value={'applied':True}), patch.object(live_bridge,'append_log'):
            record=live_bridge.run_cycle(object(),object(),apply=True,confidence=.8,log_path=Path('unused'),protected_response_plans=[self.plan])
        ids=[pid for c in record['action'].get('commands',[]) for pid in c.get('body',{}).get('fighter_ids',[])]
        self.assertIn(1,ids)

    def test_detailed_life_threat_not_erased_by_combat_string_conditions(self):
        snapshot=self.response_snapshot()
        snapshot['colonists']=[{'id':1,'health_conditions':[{'is_currently_life_threatening':True}]}]
        snapshot['combat']['colonists'][0]['health_conditions']=['infection']
        self.assertNotIn(1,colony_combat.protected_response_ids(snapshot))

    def test_filtered_native_actor_command_never_expands_empty_selection(self):
        snapshot=self.response_snapshot()
        action=mental.bridge.protect_response_commands(snapshot,{'kind':'commands','commands':[
            {'endpoint':'/api/v1/combat/tactic','body':{'fighter_ids':[1],'tactic':'focus_fire'}},
            {'endpoint':'/api/v1/pawn/edit/status','body':{'pawn_id':1,'is_drafted':False}}]})
        self.assertEqual('noop',action['kind']);self.assertEqual([],action['commands'])

    def test_no_eligible_options_still_exposes_risk_without_forced_violence(self):
        self.data['options']=[]
        self.assertEqual(['mental_safety_response'],mental.prepare(self.snapshot,self.state))
        self.assertFalse(any(p.get('kind')=='attack' for p in self.data['plans'].values()))


if __name__=='__main__':unittest.main()

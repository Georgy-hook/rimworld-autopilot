import copy
import unittest
from unittest.mock import Mock,patch
import colony_wildlife as w
class WildlifeTests(unittest.TestCase):
    def target(self,**kw):return dict({'def':'Thrumbo'},id=10,health=1,health_scale=8,armor_sharp=.6,move_speed=5.5,meat=560,nearby_pack_ids=[],pack_escalation_enabled=True,joint_group_actor_ids=[1,2,3,4,5,6,7,8],melee_strike=28,melee_cycle=2.6,**kw)
    def actor(self,id=1,strong=False):
        return dict(pawn_id=id,target_id=10,solo_feasible=True,group_feasible=True,weapon='ChargeRifle' if strong else 'Pistol',
            damage=20 if strong else 8,burst=3 if strong else 1,shooting_accuracy=.98 if strong else .5,weapon_accuracy=.9 if strong else .4,
            shooting=18 if strong else 4,health=1,rest=.9,food=.8,range=32 if strong else 15,armor_penetration=.7 if strong else .1,
            armor_sharp=.8 if strong else .05,armor_blunt=.5 if strong else .03,move_speed=6 if strong else 4.5,
            warmup=.5 if strong else 1,cooldown=.6 if strong else 1.2,shooter_factor_planned=.95 if strong else .15,planned_cover_pass=1,weather_accuracy=1,target_size_factor=2,apparel_sharp_weighted=.7 if strong else 0,apparel_blunt_weighted=.4 if strong else 0,effective_revenge_damage_event=.2,effective_revenge_planned=.03,firing_position={'x':id,'z':2},drafted=False)
    def context(self):return {'available':True,'targets':[self.target()],'actor_options':[self.actor(1,True),self.actor(2,True)]}
    def snapshot(self):return {'map':{'id':1},'game':{'tick':100},'development':{'wildlife':self.context()}}
    def lease(self):return {'wildlife_hunt_group':{'map_id':1,'target_id':10,'pawn_ids':[1,2],'owned_draft_ids':[1,2],'tick':100,'progress_tick':100,'cells':{'1':{'x':1,'z':2},'2':{'x':2,'z':2}}}}
    def status(self,downed=False):return {'available':True,'live_orders':[{'pawn_id':i,'drafted':True,'current_job':'Goto','target_id':None,'current_cell':{'x':i,'z':2},'queued_attack_ids':[10]} for i in [1,2]],'wild_status':[{'id':10,'dead':False,'downed':downed,'health':1,'position':{'x':9,'z':9}}]}
    def test_same_revenge_weak_and_strong_have_distinct_contextual_harm(self):
        weak=w.contextual_risk(self.target(),[self.actor()],'solo')
        strong=w.contextual_risk(self.target(),[self.actor(1,True),self.actor(2,True)],'group')
        self.assertEqual(weak['chance'],strong['chance']);self.assertEqual('high',weak['label']);self.assertEqual('manageable',strong['label'])
    def test_armor_pack_warmup_and_remaining_health_change_heuristic(self):
        actors=[self.actor(1,True),self.actor(2,True)];base=w.contextual_risk(self.target(),actors,'group')['pressure_index']
        t=self.target();t['nearby_pack_ids']=[11,12,13];self.assertLess(w.contextual_risk(t,actors,'group')['pressure_index'],base)
        t=self.target();t['health']=.2;self.assertGreater(w.contextual_risk(t,actors,'group')['pressure_index'],base)
        for a in actors:a['warmup']=10
        self.assertLess(w.contextual_risk(self.target(),actors,'group')['pressure_index'],base)
    def test_distance_hit_quality_and_actual_worn_armor_affect_risk(self):
        actors=[self.actor(1,True),self.actor(2,True)]
        base=w.contextual_risk(self.target(),actors,'group')['pressure_index']
        for a in actors:a['shooter_factor_planned']=.15
        self.assertLess(w.contextual_risk(self.target(),actors,'group')['pressure_index'],base)
        actors=[self.actor(1,True),self.actor(2,True)]
        for a in actors:a['apparel_sharp_weighted']=0;a['apparel_blunt_weighted']=0;a['armor_sharp']=0;a['armor_blunt']=0
        plain=w.contextual_risk(self.target(),actors,'group')['pressure_index']
        for a in actors:a['apparel_sharp_weighted']=.7;a['apparel_blunt_weighted']=.4
        self.assertGreater(w.contextual_risk(self.target(),actors,'group')['pressure_index'],plain)

    def test_bystanders_and_missing_equipment_not_counted(self):
        c=self.context();c['actor_options'][1]['group_feasible']=False;c['actor_options'][1]['solo_feasible']=False
        self.assertFalse(any(p['mode']=='group' for p in w.hunt_plans(c).values()))
        a=self.actor();a.pop('armor_penetration');self.assertEqual('unknown',w.contextual_risk(self.target(),[a],'solo')['label'])
    def test_incomplete_status_retains_lease_and_protection(self):
        s=self.snapshot();m=self.lease();c=Mock();c.get.return_value={'available':True}
        result=w.refresh_group(c,s,m)
        self.assertEqual([1,2],result['unresolved_actor_ids']);self.assertIn('wildlife_hunt_group',m);c.post.assert_not_called()
        c.post.return_value={'applied':True};result=w.cleanup(c,s,m)
        self.assertFalse(result['applied']);self.assertIn('wildlife_hunt_group',m)
    def test_exact_goto_queued_attack_protects_actual_ids_only(self):
        s=self.snapshot();m=self.lease();s['development']['wildlife'].update(self.status())
        self.assertEqual({1,2},w.active_group_actor_ids(s,m))
        s['development']['wildlife']['live_orders'][0]['queued_attack_ids']=[11]
        self.assertEqual({2},w.active_group_actor_ids(s,m))
    def test_moving_prey_does_not_reset_stall_clock(self):
        s=self.snapshot();m=self.lease();s['development']['wildlife'].update(self.status())
        s['game']['tick']=2601;s['development']['wildlife']['wild_status'][0]['position']={'x':10,'z':12}
        self.assertEqual('cleanup',w._lifecycle(s,m))
    def test_lost_post_ack_recovers_exact_group_jobs(self):
        s=self.snapshot();m={};w.prepare(s,m);c=Mock();c.get.side_effect=[self.context(),self.status()];c.post.side_effect=TimeoutError('ack lost')
        key=next(k for k,p in s['development']['wildlife']['plans'].items() if p['mode']=='group')
        r=w.execute(c,s,m,'wildlife_hunt_plan',{'key':key})
        self.assertTrue(r['outcome_unknown']);self.assertIn('wildlife_hunt_group',m);self.assertEqual([1,2],r['recovery']['active_ids'])
    def test_failed_cleanup_has_two_clocks_but_fresh_get_can_reconcile(self):
        s=self.snapshot();m=self.lease();c=Mock();c.get.return_value=self.status();c.post.side_effect=TimeoutError('lost')
        for i in range(8):
            with patch('colony_retry.time.time',return_value=1000+i*2):
                self.assertFalse(w.cleanup(c,s,m)['applied'])
            s['game']['tick']+=100
        self.assertEqual(1,c.post.call_count)
        empty=self.status();empty['live_orders']=[];c.get.return_value=empty
        with patch('colony_retry.time.time',return_value=1014):self.assertTrue(w.cleanup(c,s,m)['applied'])
        self.assertNotIn('wildlife_hunt_group',m);self.assertEqual(1,c.post.call_count)

    def test_cleanup_readback_required_and_owned_drafts_explicit(self):
        s=self.snapshot();m=self.lease();c=Mock();c.post.return_value={'applied':True};status=self.status();status['live_orders']=[];status['wild_status']=[];c.get.return_value=status
        self.assertTrue(w.cleanup(c,s,m)['applied']);self.assertNotIn('wildlife_hunt_group',m)
        self.assertEqual([1,2],c.post.call_args.kwargs['body']['owned_draft_ids'])
    def test_partial_group_is_stopped_instead_of_claiming_full_team_risk(self):
        s=self.snapshot();m={};w.prepare(s,m);c=Mock()
        empty=self.status();empty['live_orders']=[]
        c.get.side_effect=[self.context(),empty]
        c.post.side_effect=[{'applied':False,'partial':True,'accepted_ids':[1],'orders':[{'pawn_id':1,'goto_cell':{'x':1,'z':2},'was_drafted':False}]},{'applied':True}]
        key=next(k for k,p in s['development']['wildlife']['plans'].items() if p['mode']=='group')
        r=w.execute(c,s,m,'wildlife_hunt_plan',{'key':key})
        self.assertFalse(r['applied']);self.assertEqual('partial_group_stopped',r['reason']);self.assertNotIn('wildlife_hunt_group',m)

    def test_first_prey_choice_sees_actual_available_team_before_can_defer(self):
        s=self.snapshot();w.prepare(s,{})
        def ask(agent,state,key,instructions,criteria,**kwargs):
            self.assertEqual('wildlife_target',key)
            self.assertIn('available group 2 actors manageable',criteria['10'])
            self.assertIn('ChargeRifle',criteria['10'])
            self.assertIn('participants chosen next',criteria['10'])
            return 'defer',{'answers':{key:{'choice':'defer'}}}
        with patch.object(w,'ask_laya_choice',side_effect=ask):
            result,_=w.choose(None,{},'wildlife_hunt_plan',s)
        self.assertTrue(result['defer'])
        c=self.context();c['actor_options'][1]['group_feasible']=False
        text=w.target_plan_summary(c['targets'][0],w.hunt_plans(c))
        self.assertIn('available solo 1 actors',text)
        self.assertNotIn('group 2',text)

    def test_no_joint_positions_means_no_group_even_with_two_guns(self):
        c=self.context();c['targets'][0]['joint_group_actor_ids']=[]
        self.assertFalse(any(p['mode']=='group' for p in w.hunt_plans(c).values()))

    def test_already_hunting_target_not_offered_again(self):
        c=self.context();c['targets'][0]['hunting_pawn_ids']=[1]
        self.assertFalse(w.hunt_plans(c))

    def test_compact_commit_context_fits_actual_laya_tokenizer(self):
        import json
        from pathlib import Path
        try:from tokenizers import Tokenizer
        except ImportError:self.skipTest('tokenizers missing')
        paths=list((Path.home()/'.cache/huggingface/hub/models--convaiinnovations--laya/snapshots').glob('*/tokenizer/tokenizer.json'))
        if not paths:self.skipTest('cached tokenizer missing')
        tok=Tokenizer.from_file(str(paths[0]));c=self.context()
        c['actor_options']=[self.actor(i,True) for i in range(1,9)]
        for p in w.hunt_plans(c).values():
            facts=w.plan_facts(p)
            self.assertLessEqual(len(tok.encode(json.dumps(facts),add_special_tokens=False).ids),104)
            self.assertIn('harm',facts);self.assertIn('chance_per_hit',facts);self.assertIn('unknown',facts)

    def test_training_native_food_readiness_gates_requests_not_master_assignment(self):
        from tests.test_capabilities import snapshot,animal
        import colony_capabilities as caps
        s=snapshot();dog=animal(learned=False);dog['master_pawn_id']=None
        dog['training_context']={'handler_options':[{'pawn_id':1,'interaction_ready':False}]}
        s['animals']=[dog]
        self.assertNotIn('assign_animal_training',caps.prepare(s,{}))
        dog['training_context']['handler_options'][0]['interaction_ready']=True
        self.assertIn('assign_animal_training',caps.prepare(s,{}))
        dog['trainables']=[{'def_name':'Obedience','learned':True,'wanted':True,'can_train':True}]
        dog['training_context']['handler_options'][0]['interaction_ready']=False
        self.assertNotIn('assign_animal_training',caps.prepare(s,{}))
        self.assertIn('assign_animal_master',caps.prepare(s,{}))

    def test_training_readback_distinguishes_requested_from_learned(self):
        c=Mock();c.get.return_value={'available':True,'animals':[{'id':10,'degradation_period_ticks':360000,'trainables':[{'def_name':'Haul','wanted':True,'learned':False,'steps':1,'total_steps':7,'prerequisites':['Obedience']}]}]}
        r=w.training_readback(c,self.snapshot(),10,'Haul');self.assertTrue(r['observed']);self.assertEqual('learning_unverified',r['completion']);self.assertEqual(1,r['steps'])
        c.get.return_value['animals'][0]['trainables'][0]['wanted']=False;self.assertFalse(w.training_readback(c,self.snapshot(),10,'Haul')['observed'])
    def test_unknown_development_collect_keeps_group_worker_protection(self):
        s=self.snapshot();m=self.lease();s['development']['wildlife']={}
        w.prepare(s,m)
        self.assertEqual([1,2],s['development']['wildlife_active_group_ids'])
        self.assertEqual({1,2},w.protected_group_actor_ids(s,m))

    def test_training_merge_exposes_loaded_defs_previously_missing(self):
        s={'animals':[{'id':10,'trainables':[]}]}
        w.merge_training(s,{'available':True,'animals':[{'id':10,'trainables':[{'def_name':'Haul','can_train':True},{'def_name':'ModSkill','can_train':False}]}]})
        self.assertEqual({'Haul','ModSkill'},{r['def_name'] for r in s['animals'][0]['trainables']})

    def test_progress_merge_preserves_supported_and_wanted_guards(self):
        s={'animals':[{'id':10,'trainables':[{'def_name':'Haul','can_train':True,'wanted':False}]}]}
        w.merge_training(s,{'available':True,'animals':[{'id':10,'trainables':[{'def_name':'Haul','can_train':True,'wanted':True,'learned':False,'steps':2,'total_steps':7}]}]})
        self.assertTrue(s['animals'][0]['trainables'][0]['wanted']);self.assertEqual(2,s['animals'][0]['trainables'][0]['steps'])
if __name__=='__main__':unittest.main()

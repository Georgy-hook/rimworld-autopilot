import copy
import json
import unittest
from unittest.mock import patch
import colony_downed_combat as finish
import colony_director as director
import install_payload


class Client:
    def __init__(self, snapshot, *, accepted=True, flag=True, error=False):
        self.snapshot, self.accepted, self.flag, self.error = snapshot, accepted, flag, error
        self.posts = []
    def get(self, endpoint, **kwargs):
        return copy.deepcopy(self.snapshot['combat'])
    def post(self, endpoint, *, body):
        self.posts.append((endpoint, body))
        actor = next(p for p in self.snapshot['combat']['colonists'] if p['id'] == body['pawn_id'])
        if endpoint.endswith('/status'):
            actor['is_drafted'] = body['is_drafted']
        elif body.get('cancel_finishing_target_id') is not None:
            if finish.attacking(actor, body['cancel_finishing_target_id']):
                actor.update(current_job='Wait_Combat',current_job_target_id=None,current_job_kill_incapped_target=False)
        elif self.error:
            raise finish.bridge.RimApiError('Native rejected incapable actor')
        elif self.accepted:
            actor.update(is_drafted=True,current_job='AttackMelee', current_job_target_id=body['target_thing_id'],
                         current_job_kill_incapped_target=self.flag)
        return {'success': self.accepted}


class FinishDownedTests(unittest.TestCase):
    def setUp(self):
        self.vega = {'id':770,'name':'Vega','can_fight':False,'health':1.,'is_drafted':True,
                     'current_job':'Wait_Combat','position':{'x':123,'z':137}}
        self.holster = {'id':767,'name':'Holster','can_fight':True,'health':1.,'is_drafted':False,
                        'current_job':'Wait_Combat','position':{'x':128,'z':130}}
        self.target = {'id':21897,'name':'Rok','is_downed':True,'is_dead':False,
                       'health':.38,'position':{'x':122,'z':138}}
        self.snapshot = {'game':{'tick':327695},'map':{'id':0,'seed':16622162,'tile_id':55904,'resources':{}},
            'combat':{'colonists':[self.vega,self.holster],'hostiles':[self.target]},
            'colonists':[{'id':770},{'id':767}], 'development':{'item_counts':{}}}
        self.memory = {}

    def test_actual_vega_capability_excluded_and_other_fighter_available(self):
        self.assertEqual([767],[p['id'] for p in finish.available_fighters(self.snapshot,self.memory,21897)])
        for change in ({'is_dead':True},{'is_downed':True},{'is_in_mental_state':True},{'moving':0},{'manipulation':0}):
            with self.subTest(change=change):
                self.assertFalse(finish.eligible({**self.holster,**change}))
        self.assertFalse(finish.eligible(self.holster, {'767'}))

    @patch('colony_retry.time.time', return_value=1000)
    def test_eight_persisted_cycles_keep_real_job_without_duplicate_model_or_orders(self, clock):
        client=Client(self.snapshot)
        result=finish.issue(client,self.snapshot,self.memory,self.holster,self.target)
        self.assertTrue(result['applied']);self.assertEqual(result['completion'],'unverified')
        self.assertTrue(client.posts[-1][1]['kill_incapped_target'])
        for i in range(8):
            self.snapshot['game']['tick']+=4500;clock.return_value=1010+i*10
            self.holster['position']={'x':128,'z':130}
            self.target['health']-=.01
            self.memory=json.loads(json.dumps(self.memory))
            self.assertTrue(finish.prepare(self.snapshot,self.memory)['in_progress'])
        self.assertEqual(len(client.posts),1)

    @patch('colony_retry.time.time', return_value=1000)
    def test_success_ack_with_wrong_flag_is_not_execution(self, clock):
        client=Client(self.snapshot,flag=False)
        result=finish.issue(client,self.snapshot,self.memory,self.holster,self.target)
        self.assertFalse(result['applied']);self.assertEqual(result['reason'],'finishing_job_not_observed')
        self.assertFalse(finish.available_fighters(self.snapshot,self.memory,21897))

    @patch('colony_retry.time.time', return_value=1000)
    def test_lost_job_backs_off_actor_even_after_many_game_ticks(self, clock):
        client=Client(self.snapshot)
        finish.issue(client,self.snapshot,self.memory,self.holster,self.target)
        self.holster.update(current_job='Wait_Combat',current_job_target_id=None)
        self.assertIsNone(finish.prepare(self.snapshot,self.memory))
        for i in range(8):
            self.snapshot['game']['tick']+=4500;clock.return_value=1010+i*10
            self.memory=json.loads(json.dumps(self.memory))
            self.assertFalse(finish.available_fighters(self.snapshot,self.memory,21897))
        clock.return_value=1121
        self.assertEqual([767],[p['id'] for p in finish.available_fighters(self.snapshot,self.memory,21897)])

    @patch('colony_retry.time.time', return_value=1000)
    def test_native_refusal_or_exception_restores_only_our_draft(self, clock):
        for raises in (False,True):
            with self.subTest(raises=raises):
                self.setUp();client=Client(self.snapshot,accepted=False,error=raises)
                result=finish.issue(client,self.snapshot,self.memory,self.holster,self.target)
                self.assertFalse(result['applied'])
                self.assertFalse(self.holster['is_drafted'])
                self.assertTrue(self.vega['is_drafted'])

    @patch('colony_retry.time.time', return_value=1000)
    def test_dead_or_recovered_target_releases_pending_order_without_claiming_kill(self, clock):
        for change in ({'is_dead':True},{'is_downed':False}):
            self.setUp();client=Client(self.snapshot)
            finish.issue(client,self.snapshot,self.memory,self.holster,self.target)
            self.target.update(change)
            self.assertIsNone(finish.prepare(self.snapshot,self.memory))
            self.assertNotIn('active',self.memory['downed_combat'])

    @patch('colony_retry.time.time', return_value=1000)
    def test_stationary_undamaging_job_has_finite_progress_window(self, clock):
        client=Client(self.snapshot)
        finish.issue(client,self.snapshot,self.memory,self.holster,self.target)
        self.snapshot['game']['tick']+=10000;clock.return_value=1121
        self.assertTrue(finish.prepare(self.snapshot,self.memory)['in_progress'])
        self.assertIsNone(finish.reconcile(client,self.snapshot,self.memory))
        self.assertFalse(finish.available_fighters(self.snapshot,self.memory,21897))

    @patch('colony_retry.time.time', return_value=1000)
    def test_lost_ack_recovers_actual_job_and_unknown_readback_keeps_lease(self, clock):
        class LostAck(Client):
            unknown = True
            def post(inner, endpoint, *, body):
                super().post(endpoint, body=body)
                raise finish.bridge.RimApiError('ACK lost')
            def get(inner, endpoint, **kwargs):
                if inner.unknown:
                    raise finish.bridge.RimApiError('GET lost')
                return super().get(endpoint, **kwargs)
        client=LostAck(self.snapshot)
        result=finish.issue(client,self.snapshot,self.memory,self.holster,self.target)
        self.assertFalse(result['applied']);self.assertTrue(result['outcome_unknown'])
        self.assertFalse(finish.available_fighters(self.snapshot,self.memory,21897))
        self.memory=json.loads(json.dumps(self.memory))
        self.assertTrue(finish.reconcile(client,self.snapshot,self.memory)['in_progress'])
        self.assertNotIn('outcome_unknown',self.memory['downed_combat']['active'])
        self.assertEqual(1,len(client.posts))
        self.setUp();client=LostAck(self.snapshot);client.unknown=False
        self.assertTrue(finish.issue(client,self.snapshot,self.memory,self.holster,self.target)['applied'])

    @patch('colony_retry.time.time', return_value=1000)
    def test_oscillation_stalls_and_unknown_cancel_blocks_alternative(self, clock):
        client=Client(self.snapshot)
        finish.issue(client,self.snapshot,self.memory,self.holster,self.target)
        for i in range(5):
            self.holster['position']={'x':128+i%2,'z':130}
            self.snapshot['game']['tick']+=3000;clock.return_value=1000+i*31
            self.assertTrue(finish.prepare(self.snapshot,self.memory)['in_progress'])
        self.assertTrue(self.memory['downed_combat']['active']['stalled'])
        self.holster['health']=.6
        self.assertTrue(finish.prepare(self.snapshot,self.memory)['in_progress'])
        class UnknownCancel(Client):
            def post(inner, endpoint, *, body):
                inner.posts.append((endpoint,body))
                raise finish.bridge.RimApiError('cancel lost')
            def get(inner, endpoint, **kwargs):
                raise finish.bridge.RimApiError('GET lost')
        unknown=UnknownCancel(self.snapshot)
        self.assertTrue(finish.reconcile(unknown,self.snapshot,self.memory)['in_progress'])
        self.assertFalse(finish.available_fighters(self.snapshot,self.memory,21897))
        finish.reconcile(unknown,self.snapshot,self.memory)
        self.assertEqual(1,len(unknown.posts))
        clock.return_value+=11;self.snapshot['game']['tick']+=61
        self.assertIsNone(finish.reconcile(client,self.snapshot,self.memory))
        self.assertFalse(finish.attacking(self.holster,21897))
        self.vega['can_fight']=True
        self.assertEqual([770],[p['id'] for p in finish.available_fighters(self.snapshot,self.memory,21897)])

    @patch('colony_retry.time.time', return_value=1000)
    def test_existing_true_job_retained_without_new_order_even_low_health(self, clock):
        self.holster.update(current_job='AttackMelee',current_job_target_id=21897,
                            current_job_kill_incapped_target=True,health=.6)
        client=Client(self.snapshot)
        self.assertTrue(finish.issue(client,self.snapshot,self.memory,self.holster,self.target)['in_progress'])
        self.assertTrue(finish.prepare(self.snapshot,self.memory)['in_progress'])
        self.assertEqual([],client.posts)

    @patch('colony_retry.time.time', return_value=1000)
    def test_fresh_native_decline_keeps_care_and_draft_unchanged(self, clock):
        class NativeDecline(Client):
            def post(inner, endpoint, *, body):
                inner.posts.append((endpoint,body))
                return {'success':False}
        for change in ('care', 'dead_target'):
            self.setUp();client=NativeDecline(self.snapshot)
            if change=='care': self.holster['current_job']='TendPatient'
            else: self.target['is_dead']=True
            job=self.holster['current_job']
            self.assertFalse(finish.issue(client,self.snapshot,self.memory,self.holster,self.target)['applied'])
            self.assertFalse(self.holster['is_drafted']);self.assertEqual(job,self.holster['current_job'])
            self.assertEqual('/api/v1/pawn/job',client.posts[0][0])
            self.assertTrue(client.posts[0][1]['request_draft_for_finishing'])

    def test_runtime_payload_contains_new_controller(self):
        self.assertIn('colony_downed_combat.py',install_payload.RUNTIME_FILES)


if __name__=='__main__': unittest.main()

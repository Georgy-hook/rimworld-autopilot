import copy
import unittest
from colony_combat_continuation import continue_deferred


class Planner:
    @staticmethod
    def hostile_is_preparing(row): return row.get('preparing', False)


class Client:
    def __init__(self, state, replies): self.state=state;self.replies=list(replies);self.posts=[]
    def get(self, endpoint, **kwargs): return copy.deepcopy(self.state)
    def post(self, endpoint, body):
        self.posts.append(copy.deepcopy(body));return self.replies.pop(0)


class DeferredContinuationTests(unittest.TestCase):
    def setUp(self):
        self.action={'kind':'commands','commands':[{'endpoint':'/api/v1/combat/tactic',
            'body':{'map_id':0,'tactic':'hold_cover','fighter_ids':[1,2],'target_pawn_id':9}}]}
        self.result={'responses':[{'deferred':True,'review_complete':False,'applied':True,
            'drafted_pawn_ids':[1,2],'changed_pawn_ids':[1,2], 'positioned_pawn_ids':[],
            'attacking_pawn_ids':[],'preserved_pawn_ids':[]}]}
        self.state={'map_id':0,'game_tick':10,'colonists':[self.pawn(1),self.pawn(2)],'hostiles':[{'id':9}]}
    def pawn(self, pid): return {'id':pid,'is_drafted':True,'current_job':'Wait_Combat',
        'queued_job_count':0,'has_ranged_weapon':True}
    def test_draft_only_is_not_a_completed_tactical_job(self):
        c=Client(self.state,[{'applied':True,'attacking_pawn_ids':[1,2],'deferred':False,'review_complete':True}])
        out=continue_deferred(c,self.action,self.result,Planner)
        self.assertEqual(c.posts[0]['fighter_ids'],[1,2]);self.assertEqual(out['responses'][0]['attacking_pawn_ids'],[1,2])
        self.assertTrue(out['native_deferred_continuations'][0]['previous_native_response']['deferred'])
    def test_exact_native_draft_only_idle_can_finish_before_first_tick(self):
        for pawn in self.state['colonists']:pawn['current_job']=None
        self.result['responses'][0]['current_jobs']=[{'pawn_id':pid,'drafted':True,'owned':False,'queued_job_ids':[]} for pid in (1,2)]
        c=Client(self.state,[{'applied':True,'attacking_pawn_ids':[1,2],'deferred':False}])
        continue_deferred(c,self.action,self.result,Planner);self.assertEqual(c.posts[0]['fighter_ids'],[1,2])
    def test_missing_idle_readback_is_not_permission_to_claim_a_pawn(self):
        for pawn in self.state['colonists']:pawn['current_job']=None
        c=Client(self.state,[]);continue_deferred(c,self.action,self.result,Planner);self.assertFalse(c.posts)
    def test_accepted_actor_is_never_replayed(self):
        self.result['responses'][0]['attacking_pawn_ids']=[1]
        c=Client(self.state,[{'applied':True,'attacking_pawn_ids':[2],'deferred':False}])
        out=continue_deferred(c,self.action,self.result,Planner)
        self.assertEqual(c.posts[0]['fighter_ids'],[2]);self.assertEqual(out['responses'][0]['attacking_pawn_ids'],[1,2])
    def test_later_move_or_clinical_job_cancels_continuation(self):
        for patch in [{'current_job':'Goto'}, {'current_job':'TendPatient'}, {'current_job':'DoBill','has_care_job':True},
                      {'queued_job_count':1}, {'caregiver_recovery_protected':True}, {'carrying_player_pawn':True},
                      {'combat_plan':'hold_cover'}]:
            with self.subTest(patch=patch):
                state=copy.deepcopy(self.state);state['colonists']=[{**self.pawn(1),**patch}]
                c=Client(state,[]);continue_deferred(c,self.action,copy.deepcopy(self.result),Planner);self.assertFalse(c.posts)
    def test_preparing_raid_or_dead_target_is_not_restarted(self):
        for hostiles in [[],[{'id':9,'preparing':True}],[{'id':9,'is_dead':True}],[{'id':10}]]:
            c=Client({**self.state,'hostiles':hostiles},[])
            continue_deferred(c,self.action,copy.deepcopy(self.result),Planner);self.assertFalse(c.posts)
    def test_incomplete_http200_read_is_an_error(self):
        for state in [{},{**self.state,'colonists':None},{**self.state,'available':False}]:
            with self.subTest(state=state):
                c=Client(state,[])
                with self.assertRaises(ValueError):continue_deferred(c,self.action,copy.deepcopy(self.result),Planner)
                self.assertFalse(c.posts)
    def test_unknown_transport_outcome_is_never_retried(self):
        c=Client(self.state,[])
        continue_deferred(c,self.action,{**self.result,'outcome_unknown':True},Planner);self.assertFalse(c.posts)
    def test_passes_are_finite_and_no_pause_or_general_job_is_sent(self):
        c=Client(self.state,[copy.deepcopy(self.result['responses'][0]) for _ in range(2)])
        out=continue_deferred(c,self.action,self.result,Planner)
        self.assertEqual(len(c.posts),2);self.assertTrue(out['responses'][0]['deferred'])
        self.assertEqual(len(out['native_deferred_continuations']),2)
    def test_actor_outside_request_is_rejected(self):
        c=Client(self.state,[{'attacking_pawn_ids':[3]}])
        with self.assertRaises(ValueError):continue_deferred(c,self.action,self.result,Planner)


class ContinuationIntegrationTests(unittest.TestCase):
    def setUp(self):
        base=DeferredContinuationTests();base.setUp()
        self.action=base.action;self.state=base.state;self.deferred=base.result['responses'][0]
    def client(self,replies,state=None):
        class Integrated(Client):
            def __init__(self,state,replies):super().__init__(state,replies);self.endpoints=[]
            def post(self,endpoint,query=None,body=None):
                self.endpoints.append(endpoint)
                if endpoint=='/api/v1/game/speed':return {'success':True}
                return super().post(endpoint,body)
        return Integrated(state if state is not None else self.state,replies)
    def test_resume_follows_real_selected_job_acceptance(self):
        import rimworld_laya as bridge
        action=copy.deepcopy(self.action);action['commands'].append({'endpoint':'/api/v1/game/speed','query':{'speed':1}})
        c=self.client([copy.deepcopy(self.deferred),{'deferred':False,'review_complete':True,'applied':True,'attacking_pawn_ids':[1,2]}])
        out=bridge.apply_action(c,action,continue_combat=True)
        self.assertEqual(c.endpoints,['/api/v1/combat/tactic','/api/v1/combat/tactic','/api/v1/game/speed'])
        self.assertEqual(out['responses'][0]['attacking_pawn_ids'],[1,2]);self.assertEqual(len(out['native_deferred_continuations']),1)
    def test_incomplete_review_does_not_dispatch_followup_resume(self):
        import rimworld_laya as bridge
        action=copy.deepcopy(self.action);action['commands'].append({'endpoint':'/api/v1/game/speed','query':{'speed':1}})
        c=self.client([copy.deepcopy(self.deferred) for _ in range(3)])
        out=bridge.apply_action(c,action,continue_combat=True)
        self.assertTrue(out['deferred_review_pending']);self.assertEqual(c.endpoints,['/api/v1/combat/tactic']*3)
    def test_read_error_retains_original_partial_result(self):
        import rimworld_laya as bridge
        c=self.client([copy.deepcopy(self.deferred)],state={})
        out=bridge.apply_action(c,self.action,continue_combat=True)
        self.assertEqual(out['failed_command_index'],0);self.assertEqual(out['responses'][0]['drafted_pawn_ids'],[1,2])
        self.assertTrue(out['outcome_unknown']);self.assertIn('complete fresh',out['error'])
    def test_running_director_never_becomes_starting_for_later_defer(self):
        import colony_director as director
        record={'action':self.action,'result':{'responses':[self.deferred],'deferred_review_pending':True}}
        self.assertTrue(director.initial_defense_incomplete('starting',record))
        self.assertFalse(director.initial_defense_incomplete('running',record))
        good={'action':self.action,'result':{'responses':[{'applied':True,'attacking_pawn_ids':[1,2]}]}}
        self.assertFalse(director.initial_defense_incomplete('starting',good))


if __name__=='__main__':unittest.main()

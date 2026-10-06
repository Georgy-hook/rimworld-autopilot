import copy
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from care_transport import bind_care_readback
import colony_director as director
import colony_combat as combat
import colony_downed_combat as finish
import colony_mental_safety as mental
import colony_medical_recovery as care


class DefenceClient:
    """A lease is issued for one native job object, never a newly selected job."""
    def __init__(self):
        self.posts = []
        self.combat = {'colonists': [
            {'id': 1, 'is_drafted': True, 'current_job': 'AttackStatic', 'current_job_target_id': 2},
            {'id': 2, 'is_colonist': True, 'is_in_mental_state': True,
             'mental_state_def': 'Berserk', 'mental_state_session': 'a'}],
            'hostiles': [{'id': 9, 'is_downed': False}]}
        self.lease = {'key': 'exact-native-job-a', 'actor_id': 1, 'target_id': 2,
                      'session': 'a', 'job': 'AttackStatic', 'stale': False}
        self.race_to_new_job = False
        self.next_job = ('TendPatient', 3)
    def get(self, endpoint, **kwargs):
        if endpoint.endswith('/combat/state'):
            return copy.deepcopy(self.combat)
        return {'available': True, 'map_id': 0, 'options': [], 'orders': [], 'threats': [],
                'defence_orders': [copy.deepcopy(self.lease)] if self.lease else []}
    def post(self, endpoint, *, body):
        self.posts.append(body)
        actor = self.combat['colonists'][0]
        if self.race_to_new_job:
            actor.update(current_job=self.next_job[0], current_job_target_id=self.next_job[1])
            return {'applied': False}
        if body['defence_key'] == self.lease['key'] and self.lease['stale']:
            actor.update(current_job='Wait_Combat', current_job_target_id=None)
            self.lease = None
            return {'applied': True}
        return {'applied': False}


class AlliedDefenceSequences(unittest.TestCase):
    def test_accept_observe_downing_release_keeps_new_raid_and_draft(self):
        client = DefenceClient(); state = {}; snapshot = {'map': {'id': 0}, 'combat': client.combat}
        self.assertEqual([], mental.reconcile_defence(client, snapshot, state)['cancelled'])
        self.assertEqual([], client.posts)
        client.combat['colonists'][1]['is_downed'] = True
        client.lease['stale'] = True
        self.assertEqual([1], mental.reconcile_defence(client, snapshot, state)['cancelled'])
        self.assertTrue(snapshot['combat']['colonists'][0]['is_drafted'])
        self.assertIsNone(snapshot['combat']['colonists'][0]['current_job_target_id'])
        self.assertEqual([9], [p['id'] for p in combat.live_hostiles(snapshot)])
        mental.reconcile_defence(client, snapshot, state)
        self.assertEqual(1, len(client.posts))

    def test_recovered_session_stale_order_cannot_cancel_fresh_care_or_enemy_attack(self):
        for next_job in [('TendPatient', 3), ('AttackStatic', 9)]:
            with self.subTest(next_job=next_job):
                client = DefenceClient(); state = {}; snapshot = {'map': {'id': 0}, 'combat': client.combat}
                mental.reconcile_defence(client, snapshot, state)
                client.combat['colonists'][1].update(is_in_mental_state=False, mental_state_session=None)
                client.lease['stale'] = True; client.race_to_new_job = True; client.next_job = next_job
                self.assertEqual([], mental.reconcile_defence(client, snapshot, state)['cancelled'])
                self.assertEqual(next_job[0], client.combat['colonists'][0]['current_job'])
                self.assertEqual(next_job[1], client.combat['colonists'][0]['current_job_target_id'])

    def test_berserk_context_does_not_invent_named_victim(self):
        client = DefenceClient(); snapshot = {'map': {'id': 0}, 'combat': client.combat}
        self.assertEqual([2], [p['id'] for p in mental.allied_mental_threats(client.combat)])
        self.assertEqual([], mental.collect(client, snapshot)['threats'])
        self.assertNotIn('mental_state_target_id', client.combat['colonists'][1])

    def test_finish_allied_or_player_rejected_before_any_order_new_enemy_available(self):
        actor = {'id': 1}; snapshot = {'game': {'tick': 100}, 'map': {'id': 0}}; state = {}
        for identity in ({'is_colonist': True}, {'faction': 'PlayerColony'}, {'faction_goodwill': 80},
                         {'is_prisoner': True}, {'faction_relation_kind': 'Ally'}):
            target = {'id': 2, 'is_downed': True, 'is_hostile': True, **identity}
            client = DefenceClient()
            self.assertFalse(finish.issue(client, snapshot, state, actor, target)['applied'])
            self.assertEqual([], client.posts)
        self.assertTrue(finish.finishable_target({'id': 9, 'is_downed': True, 'is_hostile': True}))

    def test_native_exact_job_reference_and_faction_guards(self):
        root = Path(__file__).resolve().parents[1] / 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi'
        source = (root / 'Helpers/MentalSafetyHelper.cs').read_text(encoding='utf-8')
        cancel = source[source.index('private static ApiResult<object> CancelDefence'):source.index('public static Pawn Victim')]
        self.assertIn('!ExactDefence(d) || !Stale(d)', cancel)
        self.assertNotIn('Drafted', cancel)
        self.assertIn('ReferenceEquals(d.Actor.CurJob,d.Job)', source)
        self.assertIn('Session(d.Target)!=d.Session', source)
        self.assertIn('e!=aggressor', source)
        self.assertIn('if(accepted)TrackDefence(actor,job)', source)
        self.assertNotIn('TrackDefences(', source)
        self.assertIn('!ReferenceEquals(actor.CurJob,j)', source)
        self.assertIn('jobQueue.Any(q=>ReferenceEquals(q.job,j))', source)
        self.assertIn('named_victim=p.MentalState.def.defName=="MurderousRage"', source)
        job = (root / 'Services/Pawns/PawnJobService/PawnJobService.cs').read_text(encoding='utf-8')
        self.assertLess(job.index('MentalSafetyHelper.Allied(victim)'), job.index('if (draftedHere) pawn.drafter.Drafted = true'))


class CareClient:
    def __init__(self, combat): self.combat = combat; self.lost = False
    def get(self, *args, **kwargs):
        if self.lost: raise care.bridge.RimApiError('readback lost')
        return copy.deepcopy(self.combat)


class PostCombatCareSequences(unittest.TestCase):
    def setUp(self):
        self.plan = {'kind': 'tend', 'patient_id': 2, 'doctor_id': 1, 'self_tend': False}
        self.actor = {'id': 1, 'current_job': 'Wait_Combat'}
        self.client = CareClient({'colonists': [self.actor, {'id': 2, 'bleeding_rate': 5.76}]})
        self.snapshot = {'map': {'id': 0}, 'combat': self.client.combat}
    def test_accepted_wrong_patient_then_exact_job_is_preserved(self):
        admission, _ = care.validate_post_combat_plan(self.client, self.snapshot, self.plan,
                                                     lambda fresh: {'tend': self.plan})
        self.assertIsNone(admission)
        self.actor.update(current_job='TendPatient', current_job_target_id=3)
        result = care.observe_post_combat_assignment(self.client, self.snapshot, self.plan,
                                                    {'response': {'success': True}})
        self.assertTrue(result['assignment_accepted']); self.assertFalse(result['job_observed'])
        self.assertEqual('unverified', result['completion'])
        self.actor['current_job_target_id'] = 2
        self.client.combat['colonists'][1]['bleeding_rate'] = 0
        def no_restart(fresh): self.fail('Exact care must be preserved before replanning')
        admission, _ = care.validate_post_combat_plan(self.client, self.snapshot, self.plan, no_restart)
        self.assertTrue(admission['in_progress']); self.assertTrue(admission['job_observed'])
        self.assertFalse(admission['assignment_accepted'])
    def test_cached_option_cannot_override_fresh_actor_unavailability(self):
        for field in ('is_drafted', 'is_downed', 'is_in_mental_state'):
            with self.subTest(field=field):
                self.actor[field] = True
                result, _ = care.validate_post_combat_plan(self.client, self.snapshot, self.plan,
                                                          lambda fresh: {'cached': self.plan})
                self.assertFalse(result['applied'])
                self.assertEqual('care_actor_or_patient_changed', result['reason'])
                self.actor.pop(field)

    def test_cached_option_cannot_replace_fresh_other_patient_care(self):
        self.actor.update(current_job='TendPatient', current_job_target_id=3)
        result, _ = care.validate_post_combat_plan(self.client, self.snapshot, self.plan,
                                                  lambda fresh: {'cached': self.plan})
        self.assertFalse(result['applied'])
        self.assertEqual('care_actor_is_providing_other_care', result['reason'])
        self.assertEqual(3, self.actor['current_job_target_id'])

    def test_integrated_selection_state_change_refuses_then_new_patient_is_available(self):
        for field in ('is_drafted', 'is_downed', 'is_in_mental_state'):
            with self.subTest(field=field):
                world = {'map': {'id': 0}, 'game': {'is_paused': False}, 'combat': {'hostiles': [], 'colonists': [
                    {'id': 1, 'current_job': 'Sow', 'medicine_skill': 8, 'moving': 1, 'manipulation': 1},
                    {'id': 2, 'tendable_now': True, 'is_downed': True, 'bleeding_rate': 5.76}]}}
                client = Mock(); client.post.return_value = {'success': True}; client.get.return_value = []
                bind_care_readback(client, world)
                def changed_choice(*args, **kwargs):
                    world['combat']['colonists'][0][field] = True
                    return 'tend_2_1', {}
                with patch.object(director, 'ask_laya_choice', side_effect=changed_choice), \
                     patch.object(director, 'publish_post_combat_care_overlay'), patch.object(director.bridge, 'append_log'):
                    record = director.run_post_combat_care_cycle(client, object(), copy.deepcopy(world), Path('unused'))
                self.assertFalse(record['result']['applied']); client.post.assert_not_called()
                world['combat']['colonists'][0].pop(field)
                world['combat']['colonists'].append({'id': 3, 'tendable_now': True, 'is_downed': True, 'bleeding_rate': 2})
                with patch.object(director, 'ask_laya_choice', return_value=('tend_3_1', {})), \
                     patch.object(director, 'publish_post_combat_care_overlay'), patch.object(director.bridge, 'append_log'):
                    fresh_record = director.run_post_combat_care_cycle(client, object(), copy.deepcopy(world), Path('unused'))
                self.assertTrue(fresh_record['result']['assignment_accepted'])
                self.assertTrue(fresh_record['result']['job_observed'])
                self.assertEqual(3, world['combat']['colonists'][0]['current_job_target_id'])

    def test_fresh_plan_removed_and_unknown_readback_are_distinct(self):
        admission, _ = care.validate_post_combat_plan(self.client, self.snapshot, self.plan, lambda fresh: {})
        self.assertEqual('care_selection_changed', admission['reason'])
        self.client.lost = True
        result = care.observe_post_combat_assignment(self.client, self.snapshot, self.plan,
                                                    {'response': {'success': True}})
        self.assertTrue(result['assignment_accepted']); self.assertIsNone(result['job_observed'])
        self.assertTrue(result['outcome_unknown'])


if __name__ == '__main__': unittest.main()

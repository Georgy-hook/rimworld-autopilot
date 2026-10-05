"""Offline lease/dispatch boundary checks; no game orders."""
import copy
import unittest
from unittest.mock import Mock
import colony_wildlife as wildlife
import colony_downed_combat as finish


class WildlifeDirectorIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.snapshot={'map':{'id':0},'game':{'tick':100},'development':{},
                       'combat':{'colonists':[], 'hostiles':[]}}
        self.state={'wildlife_hunt_group':{'map_id':0,'target_id':9,'pawn_ids':[1],
                    'owned_draft_ids':[1],'tick':100,'progress_tick':100,'lowest_health':1}}
        self.status={'available':True,'live_orders':[{'pawn_id':1,'drafted':True,
                     'current_job':'AttackStatic','target_id':9,'queued_attack_ids':[]}],
                     'wild_status':[{'id':9,'downed':False,'dead':False,'health':1}]}

    def test_observed_peaceful_group_retains_lease_without_cleanup_orders(self):
        client=Mock();client.get.return_value=copy.deepcopy(self.status)
        result=wildlife.refresh_group(client,self.snapshot,self.state)
        self.assertEqual([1],result['active_ids'])
        self.assertEqual([1],self.snapshot['development']['wildlife_active_group_ids'])
        client.post.assert_not_called()
        self.assertIn('wildlife_hunt_group',self.state)

    def test_unknown_status_retains_lease_and_unresolved_protection(self):
        client=Mock();client.get.side_effect=finish.bridge.RimApiError('GET lost')
        result=wildlife.refresh_group(client,self.snapshot,self.state)
        self.assertTrue(result['lease_retained'])
        self.assertEqual([1],self.snapshot['development']['wildlife_active_group_ids'])
        self.assertIn('wildlife_hunt_group',self.state)
        client.post.assert_not_called()

    def test_takeover_cleanup_waits_for_observed_job_release(self):
        client=Mock();client.post.return_value={'applied':True}
        client.get.return_value=copy.deepcopy(self.status)
        result=wildlife.cleanup(client,self.snapshot,self.state,'combat_or_care_takeover')
        self.assertFalse(result['applied'])
        self.assertIn('wildlife_hunt_group',self.state)
        client.get.return_value={**self.status,'live_orders':[]}
        result=wildlife.cleanup(client,self.snapshot,self.state,'combat_or_care_takeover')
        self.assertTrue(result['applied']);self.assertNotIn('wildlife_hunt_group',self.state)
        self.assertEqual('cleanup',client.post.call_args.kwargs['body']['mode'])

    def test_explicit_available_only_status_retains_lease_without_cleanup(self):
        client=Mock();client.get.return_value={'available':True}
        result=wildlife.refresh_group(client,self.snapshot,self.state)
        self.assertTrue(result['lease_retained'])
        self.assertEqual([1],self.snapshot['development']['wildlife_active_group_ids'])
        self.assertIn('wildlife_hunt_group',self.state)
        client.post.assert_not_called()

    def test_finishing_unknown_incomplete_snapshot_never_releases_actor_lease(self):
        self.state={'downed_combat':{'active':{'actor_id':1,'target_id':9,'outcome_unknown':True}}}
        self.snapshot['combat']={}
        client=Mock()
        result=finish.reconcile(client,self.snapshot,self.state)
        self.assertTrue(result['in_progress'])
        self.assertFalse(finish.available_fighters(self.snapshot,self.state,9))
        client.post.assert_not_called()


if __name__=='__main__':unittest.main()

import unittest
from unittest.mock import Mock, patch
import colony_fire_safety as fire


class BurningPawnResponseTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.snapshot = {'map': {'id': 7}}
        self.facts = {'burning_pawns_available': True, 'burning_pawns': [{'pawn_id': 42, 'fire_id': 84}]}
        self.option = {'kind': 'extinguish', 'worker_id': 21, 'target_id': 42, 'giver': '84'}
        self.client.get.return_value = {'available': True, 'options': [self.option]}
        self.client.post.return_value = {'applied': True}
        self.hostiles = patch.object(fire.bridge.combat_planner, 'live_hostiles', return_value=[])
        self.hostiles.start()
        self.addCleanup(self.hostiles.stop)

    @patch.object(fire.bridge, 'append_log')
    @patch.object(fire, 'ask_laya_choice', return_value=('extinguish_1', 'raw'))
    def test_real_choice_contract_preserves_exact_native_identity(self, choose, log):
        record = fire.run_cycle(self.client, object(), self.snapshot, self.facts, 'ignored')
        self.assertEqual(record['decision']['choice'], 'extinguish_1')
        self.client.post.assert_called_once_with('/api/v1/resilience/order', body={'map_id': 7, **self.option})
        self.assertTrue(record['result']['applied'])

    @patch.object(fire.bridge, 'append_log')
    @patch.object(fire, 'ask_laya_choice', return_value=('defer', 'raw'))
    def test_defer_is_not_an_extinguishing_outcome(self, choose, log):
        record = fire.run_cycle(self.client, object(), self.snapshot, self.facts, 'ignored')
        self.assertFalse(record['result']['applied'])
        self.client.post.assert_not_called()

    @patch.object(fire.bridge, 'append_log')
    def test_read_error_is_explicit_and_never_posts(self, log):
        self.client.get.return_value = {'available': True, 'error': 'incomplete'}
        record = fire.run_cycle(self.client, object(), self.snapshot, self.facts, 'ignored')
        self.assertEqual(record['result']['error'], 'native_burning_pawn_options_unavailable')
        self.client.post.assert_not_called()

    def test_unknown_capability_and_live_combat_do_not_steal_actor(self):
        self.assertIsNone(fire.run_cycle(self.client, object(), self.snapshot, {}, 'ignored'))
        with patch.object(fire.bridge.combat_planner, 'live_hostiles', return_value=[{'id': 9}]):
            self.assertIsNone(fire.run_cycle(self.client, object(), self.snapshot, self.facts, 'ignored'))
        self.client.get.assert_not_called()


if __name__ == '__main__':
    unittest.main()

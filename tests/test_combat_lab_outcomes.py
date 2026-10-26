import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'combat_lab_outcomes', Path(__file__).parent / 'native_combat_lab' / 'combat_lab_outcomes.py')
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


class NativeHolderEvidence(unittest.TestCase):
    def test_released_captive_can_rescue_an_original_defender(self):
        state = {'allies': [{'id': 37294, 'spawned': False, 'dead': False}],
                 'enemies': [],
                 'captive': {'id': 37331, 'spawned': True, 'dead': False, 'carried_id': 37294}}
        self.assertEqual(evidence.observed_carriers(state), {37294: 37331})
        self.assertFalse(state['allies'][0]['spawned'])  # Holding does not prove arrival or stabilization.

    def test_enemy_holding_is_observed_until_the_holder_leaves(self):
        holder = {'id': 2, 'spawned': True, 'dead': False, 'carried_id': 1}
        state = {'allies': [], 'enemies': [holder]}
        self.assertEqual(evidence.observed_carriers(state), {1: 2})
        holder['spawned'] = False
        self.assertEqual(evidence.observed_carriers(state), {})

    def test_dead_holder_and_unheld_pawn_do_not_explain_absence(self):
        state = {'allies': [{'id': 3, 'spawned': True, 'dead': False}],
                 'enemies': [{'id': 2, 'spawned': True, 'dead': True, 'carried_id': 1}],
                 'captive': None}
        self.assertEqual(evidence.observed_carriers(state), {})


class ContinuousClearEvidence(unittest.TestCase):
    def test_clear_care_window_is_not_extended_by_each_poll(self):
        start = evidence.clear_window_start(False, None, 0)
        self.assertEqual(start, 0)
        self.assertEqual(evidence.clear_window_start(False, start, 50), 0)

    def test_recovered_enemy_ends_the_old_window(self):
        start = evidence.clear_window_start(False, None, 100)
        self.assertIsNone(evidence.clear_window_start(True, start, 350))

    def test_new_clear_gets_a_new_window_with_the_global_timeout_unchanged(self):
        start = evidence.clear_window_start(False, None, 100)
        start = evidence.clear_window_start(True, start, 350)
        self.assertEqual(evidence.clear_window_start(False, start, 400), 400)

class NativeInstanceEvidence(unittest.TestCase):
    def test_same_campaign_does_not_validate_a_new_repetition(self):
        read = {'campaign_id': 'same-fixture', 'native_process_id': 2, 'native_instance_id': 'new'}
        with self.assertRaises(ValueError):
            evidence.require_native_instance(read, 1, 'old')

    def test_reused_process_number_still_requires_the_same_instance(self):
        read = {'native_process_id': 1, 'native_instance_id': 'new'}
        with self.assertRaises(ValueError):
            evidence.require_native_instance(read, 1, 'old')

    def test_matching_instance_can_advance_and_missing_binding_is_not_success(self):
        read = {'native_process_id': 1, 'native_instance_id': 'bound', 'tick': 2500}
        self.assertIs(evidence.require_native_instance(read, 1, 'bound'), read)
        with self.assertRaises(ValueError):
            evidence.require_native_instance({}, None, None)


if __name__ == '__main__':
    unittest.main()

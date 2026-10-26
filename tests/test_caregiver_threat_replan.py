import unittest

import colony_director as director


class CaregiverThreatReplanTests(unittest.TestCase):
    def snapshot(self):
        return {'combat': {'colonists': [
            {'id': 1, 'health': .8, 'is_drafted': False, 'current_job': 'TendPatient',
             'care_target_id': 2, 'current_job_target_id': 2, 'weapon_def': 'Gun_Revolver',
             'position': {'x': 10, 'z': 10}},
            {'id': 2, 'health': .5, 'is_downed': True, 'current_job': 'LayDown'},
        ], 'hostiles': [{'id': 9, 'current_job': 'Wait_Combat',
                        'distance_to_nearest_opponent': 25}], 'native_options': []}}

    def add_threat(self, snapshot):
        snapshot['combat']['native_options'].append({
            'tactic': 'caregiver_retreat', 'fighter_id': 1, 'target_id': 9,
            'expected_current_job': 'TendPatient', 'expected_care_patient_id': 2})

    def test_new_native_care_threat_wakes_review_before_normal_interval(self):
        snapshot = self.snapshot()
        before = director.combat_order_signature(snapshot)
        self.add_threat(snapshot)
        after = director.combat_order_signature(snapshot)
        self.assertNotEqual(before, after)
        self.assertTrue(director.combat_replan_due(
            after, before, .1, True, urgent=bool(director.caregiver_threat_signature(snapshot))))

    def test_unchanged_care_threat_does_not_restart_orders_each_poll(self):
        snapshot = self.snapshot()
        self.add_threat(snapshot)
        before = director.combat_order_signature(snapshot)
        snapshot['combat']['colonists'][0]['position'] = {'x': 12, 'z': 11}
        after = director.combat_order_signature(snapshot)
        self.assertEqual(before, after)
        self.assertFalse(director.combat_replan_due(after, before, 2, True, urgent=True))

    def test_old_patient_binding_does_not_wake_review_after_care_changed(self):
        snapshot = self.snapshot()
        before = director.combat_order_signature(snapshot)
        self.add_threat(snapshot)
        snapshot['combat']['native_options'][0]['expected_care_patient_id'] = 3
        self.assertEqual(before, director.combat_order_signature(snapshot))

    def test_old_job_binding_does_not_interrupt_a_later_instruction(self):
        snapshot = self.snapshot()
        self.add_threat(snapshot)
        snapshot['combat']['colonists'][0]['current_job'] = 'Ingest'
        self.assertEqual((), director.caregiver_threat_signature(snapshot))

    def test_carrying_patient_keeps_existing_native_exclusion(self):
        snapshot = self.snapshot()
        self.add_threat(snapshot)
        snapshot['combat']['colonists'][0]['carrying_pawn_id'] = 2
        self.assertEqual((), director.caregiver_threat_signature(snapshot))

    def test_different_immediate_attacker_is_a_new_exact_review(self):
        snapshot = self.snapshot()
        self.add_threat(snapshot)
        before = director.combat_order_signature(snapshot)
        snapshot['combat']['native_options'][0]['target_id'] = 10
        after = director.combat_order_signature(snapshot)
        self.assertNotEqual(before, after)
        self.assertTrue(director.combat_failed_retry_due(after, before, .1))


if __name__ == '__main__':
    unittest.main()

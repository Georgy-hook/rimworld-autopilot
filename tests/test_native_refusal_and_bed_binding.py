import copy
import unittest
from unittest import mock
import colony_director as director
import colony_medical_recovery as care
import rimworld_laya as bridge
import test_tend_reservation_response as tend_fixture


class NativeRefusalBinding(unittest.TestCase):
    def test_all_expected_tend_reasons_remain_bound_false_without_post_retry(self):
        for reason in ('doctor_providing_care', 'patient_missing', 'caregiver_recovery_in_progress',
                       'doctor_queue_or_patient_carry', 'no_tendable_condition', 'tend_binding_changed'):
            with self.subTest(reason=reason):
                client = tend_fixture.Client()
                response = {'applied': False, 'blocked': True, 'reason': reason,
                            'patient_pawn_id': 8822, 'doctor_pawn_id': 8814}
                result = care.observe_post_combat_assignment(client, tend_fixture.TendReservationResponse.snapshot,
                         tend_fixture.TendReservationResponse.plan, {'response': {'success': True, 'data': response}})
                self.assertFalse(result['applied'])
                self.assertFalse(result['assignment_accepted'])
                self.assertFalse(result['job_observed'])
                self.assertEqual(result['native_refusal'], reason)
                self.assertEqual(client.posts, [])

    def test_unbound_or_ambiguous_refusal_cannot_supply_a_native_reason(self):
        original = {'applied': False, 'blocked': True, 'reason': 'doctor_providing_care',
                    'patient_pawn_id': 8822, 'doctor_pawn_id': 8814}
        for patch in ({'patient_pawn_id': 44}, {'doctor_pawn_id': True}, {'doctor_pawn_id': None},
                      {'blocked': False}, {'applied': None}, {'reason': ''}, {'reason': 7}):
            self.assertIsNone(care.bound_native_refusal({**original, **patch},
                              {'patient_pawn_id': 8822, 'doctor_pawn_id': 8814}))

    def test_stand_down_and_current_equip_are_explicit_nonactions(self):
        for endpoint, response in (
            ('/api/v1/combat/tactic', {'applied': False, 'review_complete': True,
                 'notes': ['hostiles_remain_current_state: defense retained']}),
            ('/api/v1/pawn/job', {'success': True, 'applied': False, 'in_progress': True,
                 'pawn_id': 1, 'target_thing_id': 20, 'reason': 'equip_already_in_progress'})):
            self.assertIs(bridge.command_acceptance({'endpoint': endpoint}, response), False)


class BedNativeBinding(unittest.TestCase):
    def execute(self, response):
        client = mock.Mock()
        client.post.return_value = response
        state = {'anchor': {'x': 50, 'z': 50}}
        snapshot = {'game': {'tick': 2000}, 'map': {'id': 0},
                    'development': {'bed_assignment_options': {'1|20': {}}}}
        result = director.execute_action(client, snapshot, state, 'assign_real_bed', {'bed_assignment': '1|20'})
        client.post.assert_called_once()
        return result, state

    def test_owned_bed_refusal_does_not_save_assignment_or_retry(self):
        result, state = self.execute({'applied': False, 'blocked': True,
            'patient_pawn_id': 1, 'bed_building_id': 20, 'reason': 'sleeping_bed_owned_or_incompatible'})
        self.assertFalse(result['applied'])
        self.assertTrue(result['blocked'])
        self.assertEqual(result['reason'], 'sleeping_bed_owned_or_incompatible')
        self.assertNotIn('assigned_real_beds', state)

    def test_exact_ongoing_assignment_records_owner_without_recounting_job(self):
        result, state = self.execute({'applied': False, 'assigned': True, 'in_progress': True,
            'patient_pawn_id': 1, 'bed_building_id': 20})
        self.assertFalse(result['applied'])
        self.assertTrue(result['in_progress'])
        self.assertEqual(state['assigned_real_beds'], {'1': 20})
        self.assertEqual(result['completion'], 'unverified')

    def test_job_ack_or_failed_claim_does_not_fabricate_ownership(self):
        for response in ({'success': True}, {'applied': True, 'assigned': False},
                         {'applied': True, 'assigned': True, 'patient_pawn_id': 2, 'bed_building_id': 20}):
            result, state = self.execute(response)
            self.assertNotIn('assigned_real_beds', state)
            self.assertEqual(result['completion'], 'unverified')

    def test_native_ownership_and_body_compatibility_are_required(self):
        bed = {'bed_owner_ids': [], 'bed_compatible_pawn_ids': [1]}
        self.assertTrue(care.ordinary_bed_candidate(bed, 1))
        self.assertTrue(care.ordinary_bed_candidate({**bed, 'bed_owner_ids': [1]}, 1))
        for patch in ({'bed_owner_ids': [2]}, {'bed_owner_ids': [1, 2]}, {'bed_owner_ids': None},
                      {'bed_owner_ids': [True]}, {'bed_compatible_pawn_ids': []},
                      {'bed_compatible_pawn_ids': [True]}, {'medical': True}, {'for_prisoners': True}):
            self.assertFalse(care.ordinary_bed_candidate({**bed, **patch}, 1))
        self.assertFalse(care.ordinary_bed_candidate({}, 1))

    def test_candidate_filters_native_owner_and_recovery_and_reopens_stale_memory(self):
        snapshot = {'game': {'tick': 2000}, 'map': {'id': 0, 'resources': {'food': 30}},
            'colonists': [{'id': 1, 'name': 'Sleeper', 'health': 1, 'current_job': 'LayDown'}],
            'combat': {'colonists': [{'id': 1, 'current_job_target_id': 10}]},
            'animals': [], 'wild_animals': [], 'development': {
                'buildings': [{'id': 10, 'def': 'SleepingSpot'},
                    {'id': 20, 'def': 'Bed', 'bed_owner_ids': [], 'bed_compatible_pawn_ids': [1]}],
                'rooms': [{'contained_beds_ids': [20], 'open_roof_count': 0, 'touches_map_edge': False,
                           'cells': [{'x': 11, 'z': 11}]}],
                'building_counts': {'Bed': 1}, 'zones': [], 'item_counts': {}, 'forbidden': [], 'plants': []}}
        state = {'anchor': {'x': 11, 'z': 11}, 'issued': {}, 'assigned_real_beds': {'1': 20}}
        s = copy.deepcopy(snapshot)
        actions, _ = director.candidate_actions(None, s, copy.deepcopy(state))
        self.assertIn('assign_real_bed', actions)  # stale local record does not defeat native unowned bed
        for change in ('other_owner', 'unknown_owner', 'recovery', 'queue'):
            s = copy.deepcopy(snapshot)
            if change == 'other_owner':
                s['development']['buildings'][1]['bed_owner_ids'] = [2]
            elif change == 'unknown_owner':
                del s['development']['buildings'][1]['bed_owner_ids']
            elif change == 'recovery':
                s['combat']['colonists'][0]['caregiver_recovery_active'] = True
            else:
                s['combat']['colonists'][0]['queued_job_count'] = 1
            actions, _ = director.candidate_actions(None, s, copy.deepcopy(state))
            self.assertNotIn('assign_real_bed', actions, change)


if __name__ == '__main__':
    unittest.main()

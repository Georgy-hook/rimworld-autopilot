"""Urgent pending care owns one free clinician, without freezing other cleanup."""
import copy
import unittest
from unittest.mock import patch

import colony_director as director
from test_combat_medical_transition import fixture


def clinical_fixture():
    snapshot = fixture()
    first, free, downed, mobile = snapshot['combat']['colonists']
    first.update(current_job='TendPatient', current_job_target_id=3,
                 is_drafted=False, has_care_job=True)
    free.update(current_job='Repair', is_drafted=False)
    mobile.update(current_job='LayDown', is_drafted=False, is_downed=False,
                  moving=.7, manipulation=.5, bleeding_rate=2.9)
    snapshot['colonists'][3].update(downed=False, capacities=dict(moving=.7, manipulation=.5))
    snapshot['colonists'][3]['skills']['Medicine']['disabled'] = True
    snapshot['colonists'][3]['work_priorities']['Doctor']['disabled'] = True
    return snapshot


class PendingClinicalCleanupTests(unittest.TestCase):
    def test_free_second_doctor_reserved_current_first_doctor_untouched(self):
        snapshot = clinical_fixture()
        original = copy.deepcopy(snapshot['combat']['colonists'][0])
        self.assertEqual({2}, director.pending_urgent_care_clinicians(snapshot, {}))
        self.assertEqual(original, snapshot['combat']['colonists'][0])

    def test_one_patient_does_not_reserve_every_independent_finisher(self):
        snapshot = clinical_fixture()
        extra = copy.deepcopy(snapshot['combat']['colonists'][1])
        extra.update(id=5, name='extra', position=dict(x=35, z=10))
        details = copy.deepcopy(snapshot['colonists'][1]); details.update(id=5, position=extra['position'])
        snapshot['combat']['colonists'].append(extra); snapshot['colonists'].append(details)
        reserved = director.pending_urgent_care_clinicians(snapshot, {})
        self.assertEqual({5}, reserved)
        self.assertTrue(director.downed_combat.eligible(snapshot['combat']['colonists'][1], {'1', *map(str, reserved)}))
        self.assertFalse(director.downed_combat.eligible(extra, {'1', *map(str, reserved)}))

    def test_failed_pair_must_expire_on_both_clocks_before_reservation_returns(self):
        snapshot = clinical_fixture()
        plan = director.post_combat_care_options(snapshot)['tend_4_2']
        with patch('time.time', return_value=1000):
            failure = director.retry_clock.failure_record(snapshot['game']['tick'])
        failure['state'] = director.medical_recovery.care_failure_state(snapshot, plan)
        state = dict(care_assignment_failures={'tend_4_2': failure})
        for wall, ticks, expected in [(1020, 3000, set()), (1040, 1000, set()), (1040, 3000, {2})]:
            with self.subTest(wall=wall, ticks=ticks):
                current = copy.deepcopy(snapshot); current['game']['tick'] += ticks
                with patch('time.time', return_value=wall):
                    self.assertEqual(expected, director.pending_urgent_care_clinicians(current, state))

    def test_ordinary_minor_wounds_or_later_queue_do_not_hold_a_clinician(self):
        snapshot = clinical_fixture(); snapshot['combat']['colonists'][3]['bleeding_rate'] = .18
        self.assertEqual(set(), director.pending_urgent_care_clinicians(snapshot, {}))
        snapshot = clinical_fixture(); snapshot['combat']['colonists'][1]['queued_job_count'] = 1
        self.assertEqual(set(), director.pending_urgent_care_clinicians(snapshot, {}))


if __name__ == '__main__':
    unittest.main()

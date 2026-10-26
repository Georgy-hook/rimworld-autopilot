import unittest
import colony_medical_recovery as care
import rimworld_laya as bridge


class Client:
    def __init__(self, job='Wait', target=None):
        self.combat = {'colonists': [{'id': 8814, 'current_job': job,
                                     'current_job_target_id': target}]}
        self.posts = []

    def get(self, endpoint, **kwargs):
        return self.combat

    def post(self, *args, **kwargs):
        self.posts.append((args, kwargs))
        raise AssertionError('A reservation refusal must not replay a POST')


class TendReservationResponse(unittest.TestCase):
    plan = {'kind': 'tend', 'patient_id': 8822, 'doctor_id': 8814}
    snapshot = {'map': {'id': 0}}

    def result(self):
        return {'response': {'applied': False, 'blocked': True,
                             'reason': 'patient_reserved_or_unreachable',
                             'patient_pawn_id': 8822, 'doctor_pawn_id': 8814}}

    def test_reservation_refusal_is_not_assignment_or_completed_treatment(self):
        client = Client()
        r = care.observe_post_combat_assignment(client, self.snapshot, self.plan, self.result())
        self.assertFalse(r['applied'])
        self.assertFalse(r['assignment_accepted'])
        self.assertFalse(r['job_observed'])
        self.assertEqual(r['reason'], 'patient_reserved_or_unreachable')
        self.assertEqual(r['completion'], 'unverified')
        self.assertNotIn('error', r)
        self.assertEqual(client.posts, [])

    def test_concurrent_exact_native_job_is_observed_without_claiming_this_post_applied(self):
        r = care.observe_post_combat_assignment(Client('TendPatient', 8822), self.snapshot, self.plan, self.result())
        self.assertTrue(r['job_observed'])
        self.assertTrue(r['in_progress'])
        self.assertFalse(r['applied'])
        self.assertFalse(r['assignment_accepted'])

    def test_real_rejection_does_not_hide_unknown_readback(self):
        client = Client()
        client.combat = {}
        r = care.observe_post_combat_assignment(client, self.snapshot, self.plan, self.result())
        self.assertTrue(r['outcome_unknown'])
        self.assertIsNone(r['job_observed'])
        self.assertFalse(r['applied'])
        self.assertEqual(r['native_refusal'], 'patient_reserved_or_unreachable')

    def test_generic_envelope_false_is_not_acknowledged_as_success(self):
        self.assertFalse(bridge.command_acceptance({'endpoint': '/api/v1/pawn/medical/tend'},
                                                   {'success': True, 'data': self.result()['response']}))


if __name__ == '__main__':
    unittest.main()

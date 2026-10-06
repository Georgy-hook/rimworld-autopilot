import copy
import unittest
import colony_director as director


class ContextClient:
    def __init__(self, row, active):
        self.context = {'options': [row], 'active_orders': active}
        self.posts = []

    def get(self, endpoint, **kwargs):
        assert endpoint == '/api/v1/resilience/context'
        return copy.deepcopy(self.context)

    def post(self, endpoint, **kwargs):
        assert endpoint == '/api/v1/resilience/order'
        self.posts.append(kwargs['body'])
        return {'applied': True, 'reason': 'normal_job_observed; completion_unobserved'}


class MedicalYieldExecutor(unittest.TestCase):
    def fixture(self, target=2):
        row = {'kind': 'feed', 'worker_id': 1, 'target_id': target, 'giver': 'DoctorFeedHumanlikes',
               'expected_current_job': 'TendPatient', 'expected_care_patient_id': 2,
               'care_yield_reason': 'stable_tend_to_feed_same_starving_patient', 'food_feasible': True}
        active = [{'kind': 'tend', 'worker_id': 1, 'target_id': 2, 'job_def': 'TendPatient'}]
        snap = {'map': {'id': 0}, 'game': {'tick': 100}, 'development': {
            'medical_action_options': {'feed_hungry_colonist': {str(target): {'helpers': {'1': row}}}}}}
        return snap, row, active

    def run_order(self, snapshot, client, target=2):
        return director.execute_action(client, snapshot, {'anchor': {}}, 'feed_hungry_colonist',
            {'medical_patient': str(target), 'care_helper': '1'})

    def test_same_patient_native_binding_is_transferred_and_allowed(self):
        snapshot, row, active = self.fixture()
        client = ContextClient(row, active)
        result = self.run_order(snapshot, client)
        self.assertTrue(result['applied'])
        self.assertEqual(result['completion'], 'unverified')
        self.assertEqual(client.posts[0]['expected_current_job'], 'TendPatient')
        self.assertEqual(client.posts[0]['expected_care_patient_id'], 2)

    def test_changed_native_binding_is_rejected_before_post(self):
        snapshot, row, active = self.fixture()
        client = ContextClient(dict(row, expected_care_patient_id=3), active)
        self.assertFalse(self.run_order(snapshot, client)['applied'])
        self.assertEqual(client.posts, [])

    def test_existing_other_feed_lease_remains_protected(self):
        snapshot, row, active = self.fixture()
        active.append({'kind': 'feed', 'worker_id': 9, 'target_id': 2, 'job_def': 'FeedPatient'})
        client = ContextClient(row, active)
        self.assertFalse(self.run_order(snapshot, client)['applied'])
        self.assertEqual(client.posts, [])

    def test_different_patient_binding_is_not_lost(self):
        snapshot, row, active = self.fixture(target=3)
        client = ContextClient(row, active)
        self.assertTrue(self.run_order(snapshot, client, target=3)['applied'])
        self.assertEqual(client.posts[0]['target_id'], 3)
        self.assertEqual(client.posts[0]['expected_care_patient_id'], 2)


if __name__ == '__main__':
    unittest.main()

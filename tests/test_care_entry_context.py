"""Clinical entry keeps native triage after a stand-down snapshot refresh."""
import copy
from contextlib import ExitStack
from pathlib import Path
import unittest
from unittest.mock import patch

import colony_director as director
import colony_medical_recovery as recovery


def fixture():
    return dict(game=dict(tick=8539, is_paused=False), map=dict(id=0),
                colonists=[dict(id=1), dict(id=2)], development={},
                combat=dict(hostiles=[], colonists=[
                    dict(id=1, name='doctor', current_job='LayDown', current_job_target_id=10,
                         bleeding_rate=1.78, tendable_now=True, is_downed=False, is_drafted=False, health=.44),
                    dict(id=2, name='patient', current_job='Wait_Downed', bleeding_rate=4.46,
                         tendable_now=True, is_downed=True, is_dead=False, health=.38)]))


class Client:
    def __init__(self, snapshot):
        self.rows = copy.deepcopy(snapshot['combat']['colonists'])
        self.calls, self.posts = [], []
        self.failed = False
        self.context = dict(available=True, patients=[
            dict(pawn_id=1, bleeding_total=1.78, bleedout_ticks=26523,
                 bleeding_evidence_complete=True, tendable_now=True),
            dict(pawn_id=2, bleeding_total=4.46, bleedout_ticks=6073,
                 bleeding_evidence_complete=True, tendable_now=True)])

    def get(self, endpoint, **kwargs):
        self.calls.append(endpoint)
        if endpoint == '/api/v1/resilience/context':
            if self.failed:
                raise director.bridge.RimApiError('Declared clinical read failure')
            return copy.deepcopy(self.context)
        if endpoint == '/api/v1/combat/state':
            return dict(available=True, colonists=copy.deepcopy(self.rows), hostiles=[])
        return []

    def post(self, endpoint, **kwargs):
        self.posts.append(dict(endpoint=endpoint, **copy.deepcopy(kwargs)))
        if endpoint == '/api/v1/pawn/medical/tend':
            self.rows[0].update(current_job='TendPatient', current_job_target_id=1)
        return dict(success=True)


def entry(snapshot, client):
    selected = dict(kind='tend', patient_id=1, doctor_id=1, self_tend=True, summary='Self-care')
    with ExitStack() as stack:
        stack.enter_context(patch.object(director, 'collect_care_environment', return_value=[]))
        stack.enter_context(patch.object(director, 'post_combat_care_options',
                                         return_value={'self_tend_1': selected}))
        # The independent menu ranking is already covered by clinical frontier
        # tests. Keep actual entry, fresh assignment validation and POST body.
        stack.enter_context(patch.object(recovery, 'clinical_order_frontier', side_effect=lambda s, plans: plans))
        stack.enter_context(patch.object(director, 'ask_laya_choice', return_value=('self_tend_1', {})))
        stack.enter_context(patch.object(director, 'publish_post_combat_care_overlay'))
        stack.enter_context(patch.object(director.colony_reasoning, 'attention_facts', return_value={}))
        stack.enter_context(patch.object(director.bridge, 'append_log'))
        return director.run_post_combat_care_cycle(client, object(), snapshot, Path('unused'))


class CareEntryContextTests(unittest.TestCase):
    def tend_body(self, client):
        return next(row['body'] for row in client.posts if row['endpoint'] == '/api/v1/pawn/medical/tend')

    def test_first_care_after_snapshot_refresh_requests_finite_native_tend(self):
        snapshot = fixture(); client = Client(snapshot)
        result = entry(snapshot, client)
        self.assertTrue(self.tend_body(client)['review_after_tend'])
        self.assertEqual(1, client.calls.count('/api/v1/resilience/context'))
        self.assertTrue(result['clinical_context_read']['available'])
        self.assertTrue(result['result']['job_observed'])

    def test_stale_empty_context_cannot_disable_first_clinical_review(self):
        snapshot = fixture(); snapshot['development']['resilience'] = dict(available=True, patients=[])
        client = Client(snapshot); entry(snapshot, client)
        self.assertTrue(self.tend_body(client)['review_after_tend'])
        self.assertEqual(2, len(snapshot['development']['resilience']['patients']))

    def test_failed_read_is_explicit_and_does_not_fabricate_finite_treatment(self):
        snapshot = fixture(); client = Client(snapshot); client.failed = True
        result = entry(snapshot, client)
        self.assertNotIn('review_after_tend', self.tend_body(client))
        self.assertFalse(result['clinical_context_read']['available'])
        self.assertIn('Declared clinical read failure', result['clinical_context_read']['error'])
        self.assertTrue(snapshot['warnings'])

    def test_empty_available_fallback_is_not_complete_patient_evidence(self):
        snapshot = fixture(); client = Client(snapshot); client.context['patients'] = []
        result = entry(snapshot, client)
        self.assertNotIn('review_after_tend', self.tend_body(client))
        self.assertFalse(result['clinical_context_read']['available'])
        self.assertEqual([1, 2], snapshot['development']['resilience']['read_errors']['patient_coverage'])

    def test_incomplete_bleeding_evidence_keeps_normal_tending(self):
        snapshot = fixture(); client = Client(snapshot)
        client.context['patients'][1]['bleeding_evidence_complete'] = False
        entry(snapshot, client)
        self.assertNotIn('review_after_tend', self.tend_body(client))

    def test_existing_exact_tend_is_readback_and_is_never_retroactively_shortened(self):
        snapshot = fixture(); snapshot['combat']['colonists'][0].update(current_job='TendPatient', current_job_target_id=1)
        client = Client(snapshot); result = entry(snapshot, client)
        self.assertFalse(result['result']['assignment_accepted'])
        self.assertTrue(result['result']['job_observed'])
        self.assertEqual([], client.posts)

    def test_one_snapshot_read_is_reused_but_new_tick_rechecks(self):
        snapshot = fixture(); client = Client(snapshot)
        recovery.refresh_competing_tend_context(client, snapshot)
        entry(snapshot, client)
        self.assertEqual(1, client.calls.count('/api/v1/resilience/context'))
        snapshot['game']['tick'] += 1
        recovery.refresh_competing_tend_context(client, snapshot)
        self.assertEqual(2, client.calls.count('/api/v1/resilience/context'))

    def test_last_routine_patient_gets_completed_tend_review(self):
        snapshot = fixture(); snapshot['combat']['colonists'].pop(); client = Client(snapshot)
        entry(snapshot, client)
        self.assertEqual(1, client.calls.count('/api/v1/resilience/context'))
        self.assertTrue(self.tend_body(client)['review_after_tend'])


if __name__ == '__main__':
    unittest.main()

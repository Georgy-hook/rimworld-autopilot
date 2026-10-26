"""Finite treatment is requested only for a fresh competing bleeding triage."""
import unittest
import colony_medical_recovery as recovery


def fixture():
    return dict(combat=dict(colonists=[dict(id=1), dict(id=2)]),
                development=dict(resilience=dict(available=True, patients=[
                    dict(pawn_id=1, bleeding_total=1.36, bleeding_evidence_complete=True, tendable_now=True),
                    dict(pawn_id=2, bleeding_total=2.84, bleeding_evidence_complete=True, tendable_now=True)])))


class CompetingTendReview(unittest.TestCase):
    def test_finish_one_tend_before_reviewing_a_bleeding_competitor(self):
        self.assertTrue(recovery.competing_tend_review(fixture(), dict(kind='tend')))

    def test_two_minor_bleeds_still_need_a_completed_tend_review(self):
        s = fixture(); s['development']['resilience']['patients'][1]['bleeding_total'] = 0
        self.assertFalse(recovery.competing_tend_review(s, dict(kind='tend')))
        s = fixture(); s['development']['resilience']['patients'][1]['bleeding_total'] = 1.4
        self.assertTrue(recovery.competing_tend_review(s, dict(kind='tend')))

    def test_selected_last_bleeding_patient_and_nonbleeding_wounds_are_finite(self):
        s = fixture()
        s['development']['resilience']['patients'][0]['bleeding_total'] = 0
        s['development']['resilience']['patients'][1]['bleeding_total'] = .7
        self.assertTrue(recovery.competing_tend_review(s, dict(kind='tend', patient_id=2)))
        self.assertTrue(recovery.competing_tend_review(s, dict(kind='tend', patient_id=1)))

    def test_independent_active_infection_is_not_shortened(self):
        s = fixture()
        s['development']['resilience']['patients'][0]['conditions'] = [
            dict(def_name='WoundInfection', tendable_now=True, immunity_can_develop=True, immunity=.4)]
        self.assertFalse(recovery.competing_tend_review(s, dict(kind='tend', patient_id=1)))

    def test_unknown_clinical_rate_does_not_invent_a_competing_patient(self):
        for value in (None, True, float('nan'), '2.84'):
            s = fixture(); s['development']['resilience']['patients'][1]['bleeding_total'] = value
            self.assertFalse(recovery.competing_tend_review(s, dict(kind='tend')), value)

    def test_failed_or_incomplete_native_read_does_not_truncate_treatment(self):
        for field in ('error', 'errors', 'read_errors'):
            s = fixture(); s['development']['resilience'][field] = {'patients': 'failed'}
            self.assertFalse(recovery.competing_tend_review(s, dict(kind='tend')))
        s = fixture(); s['development']['resilience']['patients'][1]['bleeding_evidence_complete'] = False
        self.assertFalse(recovery.competing_tend_review(s, dict(kind='tend')))

    def test_dead_or_unknown_roster_patient_does_not_create_a_review(self):
        s = fixture(); s['combat']['colonists'][1]['is_dead'] = True
        self.assertFalse(recovery.competing_tend_review(s, dict(kind='tend')))
        s = fixture(); s['development']['resilience']['patients'][1]['pawn_id'] = 99
        self.assertFalse(recovery.competing_tend_review(s, dict(kind='tend')))

    def test_feed_rescue_and_operations_are_not_shortened(self):
        for kind in ('feed', 'rescue', 'rest', 'operation'):
            self.assertFalse(recovery.competing_tend_review(fixture(), dict(kind=kind)))


if __name__ == '__main__':
    unittest.main()

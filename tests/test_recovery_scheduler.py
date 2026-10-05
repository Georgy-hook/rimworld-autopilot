"""Transitions from the 3 October failure: care progress and lost shelter facts."""
import copy
import unittest
from unittest.mock import patch
import colony_director as director
import colony_reasoning as reasoning


class RecoverySchedulerTests(unittest.TestCase):
    def test_native_combat_labels_use_detailed_patient_state_by_id(self):
        disease = {'def_name': 'LungRot', 'part': 'left lung', 'severity': .55,
                   'lethal_severity': 1, 'tendable_now': False}
        snap = {'combat': {'colonists': [
            {'id': 2, 'health_conditions': ['hypothermia (shivering)']},
            {'id': 1, 'is_downed': True, 'health_conditions': ['lung rot (left lung)']} ]},
            'colonists': [{'id': 1, 'health_conditions': [disease]},
                          {'id': 2, 'health_conditions': []}]}
        previous, _ = director.clinical_reassessment_due(snap, None)
        disease['severity'] = .85
        current, due = director.clinical_reassessment_due(snap, previous)
        self.assertTrue(due)
        self.assertNotEqual(previous, current)
        snap['colonists'].reverse()
        self.assertEqual(current, director.care_reassessment_signature(snap))

    def test_label_only_combat_snapshot_does_not_crash_or_invent_disease_severity(self):
        snap = {'combat': {'colonists': [
            {'id': 1, 'health_conditions': ['hypothermia (shivering)', None]}]}}
        signature, due = director.clinical_reassessment_due(snap, None)
        self.assertFalse(due)
        self.assertEqual(signature[0][-1], ())

    def test_overdue_empty_shelter_requires_progress_but_does_not_interrupt_existing_project(self):
        snap = {'map': {'enemies': 0}, 'colonists': [{'id': 1, 'current_job': 'GotoWander'}],
                'development': {'shelter_exposure_days': 1, 'construction_projects': []}}
        choices = ['hold_survival', 'build_starter_base', 'build_recreation_pin', 'tend_colonist']
        with patch.object(director, 'sleeping_place_counts', return_value=(1, 0)):
            focused = director.focus_overdue_shelter_choices(snap, choices)
            self.assertEqual(focused, ['build_starter_base', 'tend_colonist'])
            snap['development']['construction_projects'] = [{'thing_id': 50}]
            self.assertEqual(choices, director.focus_overdue_shelter_choices(snap, choices))
            snap['development']['construction_projects'] = []
            snap['colonists'][0]['current_job'] = 'TendPatient'
            self.assertIn('hold_survival', director.focus_overdue_shelter_choices(snap, choices))

    def test_stabilized_patient_reopens_triage_before_old_wall_clock_delay(self):
        snap = {"combat": {"colonists": [
            {"id": 1, "is_downed": True, "tendable_now": True, "bleeding_rate": 5.092},
            {"id": 2, "is_downed": True, "tendable_now": True, "bleeding_rate": 4.315},
            {"id": 3, "current_job": "TendPatient", "current_job_target_id": 1},
        ]}}
        signature, due = director.clinical_reassessment_due(snap, None)
        self.assertTrue(due)
        self.assertFalse(director.clinical_reassessment_due(snap, signature)[1])
        snap['combat']['colonists'][0]['bleeding_rate'] = 0
        changed, due = director.clinical_reassessment_due(snap, signature)
        self.assertTrue(due)
        snap['combat']['colonists'][2]['current_job'] = 'GotoWander'
        self.assertTrue(director.clinical_reassessment_due(snap, changed)[1])

    def test_expiring_treatment_and_worsening_bleedout_reopen_care(self):
        disease = {'def_name': 'LungRot', 'part': 'left lung', 'severity': .55,
                   'lethal_severity': 1, 'tendable_now': False}
        pawn = {'id': 1, 'is_downed': True, 'tendable_now': False, 'health_conditions': [disease]}
        snap = {'combat': {'colonists': [pawn]}}
        signature, _ = director.clinical_reassessment_due(snap, None)
        disease['tendable_now'] = pawn['tendable_now'] = True
        self.assertTrue(director.clinical_reassessment_due(snap, signature)[1])
        disease.update(def_name='BloodLoss', severity=.25)
        signature, _ = director.clinical_reassessment_due(snap, None)
        disease['severity'] = .65
        self.assertTrue(director.clinical_reassessment_due(snap, signature)[1])

    def test_no_clinical_replan_for_normal_job_churn_or_clock_progress(self):
        snap = {'game': {'tick': 10}, 'combat': {'colonists': [
            {'id': 1, 'current_job': 'HaulToCell', 'current_job_target_id': 25}]}}
        signature, _ = director.clinical_reassessment_due(snap, None)
        snap['game']['tick'] = 60000
        snap['combat']['colonists'][0].update(current_job='GotoWander', current_job_target_id=72)
        self.assertEqual((signature, False), director.clinical_reassessment_due(snap, signature))

    def test_disposal_focus_preserves_immediate_care_not_rituals(self):
        snap = {'development': {'sanitation_urgent': True}}
        choices = ['resilience_dispose_corpse', 'resilience_shelter', 'tend_colonist',
                   'specialists_ritual', 'build_sculpture', 'hold_survival']
        actual = director.focus_contamination_choices(snap, choices)
        self.assertIn('tend_colonist', actual)
        self.assertIn('resilience_shelter', actual)
        self.assertNotIn('specialists_ritual', actual)
        self.assertEqual(choices, director.focus_contamination_choices({}, choices))

    def test_root_shelter_fact_survives_general_summary_losses(self):
        snap = {'map': {'enemies': 0, 'resources': {'meals': 47}},
                'colonists': [{'id': i, 'hunger': .4} for i in range(3)],
                'development': {'construction_projects': [], 'weather': {'temperature': 3}}}
        facts = reasoning.attention_facts(snap, roofed_sleeping_places=0)
        self.assertEqual(facts['unroofed_sleepers'], 3)
        self.assertEqual(facts['pending_builds'], 0)
        self.assertEqual(facts['building_now'], 0)
        self.assertLess(list(facts).index('unroofed_sleepers'), list(facts).index('meals'))
        self.assertNotIn('unroofed_sleepers', reasoning.attention_facts(snap))


if __name__ == '__main__':
    unittest.main()

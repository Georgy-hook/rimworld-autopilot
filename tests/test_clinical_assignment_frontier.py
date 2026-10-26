"""New care must compare the same doctor's native patient deadlines."""
import copy
import unittest
import colony_medical_recovery as recovery


def fixture():
    patients = [dict(pawn_id=1, bleeding_evidence_complete=True, bleeding_total=4.7,
                     bleedout_ticks=5500, conditions=[]),
                dict(pawn_id=2, bleeding_evidence_complete=True, bleeding_total=2.3,
                     bleedout_ticks=16000, conditions=[]),
                dict(pawn_id=3, bleeding_evidence_complete=True, bleeding_total=0, conditions=[])]
    s = dict(development=dict(resilience=dict(patients=patients)))
    plans = dict(earlier=dict(kind='tend', patient_id=1, doctor_id=3),
                 later=dict(kind='tend', patient_id=2, doctor_id=3),
                 self_bruise=dict(kind='tend', patient_id=3, doctor_id=3),
                 carry_later=dict(kind='rescue', patient_id=2, doctor_id=3),
                 other_helper=dict(kind='rescue', patient_id=2, doctor_id=4))
    return s, plans


def caregiver_fixture():
    from test_caregiver_self_tend_yield import situation, clinical
    import colony_director as director
    snapshot, doctor = situation()
    doctor.update(name='Bleeding doctor', bleeding_rate=1.74, tendable_now=True, health=.41)
    snapshot['combat']['colonists'][0].update(bleeding_rate=0, tendable_now=True)
    snapshot['combat']['colonists'].append(dict(
        id=3, is_downed=True, bleeding_rate=3.4, tendable_now=True, health=.4,
        moving=0, manipulation=0, position=dict(x=2, z=0)))
    native = snapshot['development']['resilience']['patients']
    native[1]['bleedout_ticks'] = 15000
    native.append(dict(pawn_id=3, bleeding_total=3.4, bleedout_ticks=8000,
                       bleeding_evidence_complete=True, tendable_now=True, conditions=[clinical()]))
    snapshot['colonists'] = [dict(id=p['id'], downed=bool(p.get('is_downed')), health_conditions=[],
                                   skills=dict(Medicine=dict(disabled=False)),
                                   work_priorities=dict(Doctor=dict(disabled=False)))
                            for p in snapshot['combat']['colonists']]
    return snapshot, director.post_combat_care_options(snapshot)


class ClinicalAssignmentFrontier(unittest.TestCase):
    def test_free_critical_caregiver_keeps_self_care_after_completed_tend(self):
        import colony_director as director
        for job in ('Wait', 'LayDown', 'DoBill'):
            s, _ = caregiver_fixture()
            doctor = s['combat']['colonists'][1]
            doctor.update(current_job=job, current_job_target_id=None, queued_job_count=0,
                          has_care_job=False)
            before = copy.deepcopy(s['combat'])
            plans = director.post_combat_care_options(s)
            self.assertIn('self_tend_2', plans)
            self.assertIn('other observed mobile care-capable doctors', plans['self_tend_2']['summary'])
            result = recovery.clinical_order_frontier(s, plans)
            self.assertIn('self_tend_2', result, job)
            self.assertIn('tend_3_2', result, job)
            self.assertEqual(s['combat'], before)

    def test_free_caregiver_exception_rechecks_readiness_and_native_bleeding(self):
        for mutation in ('queue', 'unknown_queue', 'bool_queue', 'carry', 'draft', 'downed',
                         'mental', 'disabled', 'incapable', 'care', 'unknown_job', 'retreat',
                         'improved', 'incomplete', 'not_tendable', 'read_error', 'unavailable',
                         'unsafe', 'stale_binding'):
            s, _ = caregiver_fixture()
            doctor = s['combat']['colonists'][1]
            doctor.update(current_job='Wait', current_job_target_id=None, queued_job_count=0,
                          has_care_job=False)
            native = s['development']['resilience']
            own = native['patients'][1]
            row = dict(kind='tend', patient_id=2, doctor_id=2, self_tend=True)
            if mutation == 'queue': doctor['queued_job_count'] = 1
            elif mutation == 'unknown_queue': doctor.pop('queued_job_count')
            elif mutation == 'bool_queue': doctor['queued_job_count'] = False
            elif mutation == 'carry': doctor['carrying_pawn_id'] = 1
            elif mutation == 'draft': doctor['is_drafted'] = True
            elif mutation == 'downed': doctor['is_downed'] = True
            elif mutation == 'mental': doctor['is_in_mental_state'] = True
            elif mutation == 'disabled': doctor['medical_work_enabled'] = False
            elif mutation == 'incapable': doctor['manipulation'] = .1
            elif mutation == 'care': doctor.update(current_job='DoBill', has_care_job=True)
            elif mutation == 'unknown_job': doctor.pop('current_job')
            elif mutation == 'retreat':
                doctor['current_job'] = 'Goto'
                s['combat']['care_retreat_pawn_ids'] = [2]
            elif mutation == 'improved': own['bleeding_total'] = 1.4
            elif mutation == 'incomplete': own['bleeding_evidence_complete'] = False
            elif mutation == 'not_tendable': own['tendable_now'] = False
            elif mutation == 'read_error': native['read_errors'] = {'patients': 'unavailable'}
            elif mutation == 'unavailable': native['available'] = False
            elif mutation == 'unsafe':
                s['combat']['hostiles'] = [dict(id=9, position=dict(x=1, z=0))]
            else: row['reassign_from_patient_id'] = 1
            self.assertFalse(recovery.critical_caregiver_self_tend(s, row), mutation)

    def test_offered_critical_caregiver_self_tend_survives_earlier_other_patient(self):
        s, plans = caregiver_fixture()
        self.assertIn('tend_3_2', plans)
        self.assertIn('self_tend_2', plans)
        before = copy.deepcopy(s['combat'])
        result = recovery.clinical_order_frontier(s, plans)
        self.assertIn('tend_3_2', result)
        self.assertIn('self_tend_2', result)
        self.assertEqual(s['combat'], before)

    def test_critical_label_cannot_bypass_the_exact_native_binding(self):
        for key, value in [('doctor_id', True), ('patient_id', 3), ('self_tend', False),
                           ('reassign_from_patient_id', 99), ('reassign_from_patient_id', True),
                           ('care_yield_reason', 'urgent')]:
            s, plans = caregiver_fixture()
            plans['self_tend_2'][key] = value
            self.assertFalse(recovery.critical_caregiver_self_tend(s, plans['self_tend_2']), key)

    def test_stale_critical_caregiver_option_is_filtered_again(self):
        for mutation in ('queue', 'old_bleeding', 'own_improved', 'old_disease', 'read_error'):
            s, plans = caregiver_fixture()
            native = s['development']['resilience']
            if mutation == 'queue':
                s['combat']['colonists'][1]['queued_job_count'] = 1
            elif mutation == 'old_bleeding':
                native['patients'][0]['bleeding_total'] = .01
            elif mutation == 'own_improved':
                native['patients'][1]['bleeding_total'] = 1.4
            elif mutation == 'old_disease':
                native['patients'][0]['conditions'][0].update(immunity_can_develop=True, immunity=.7)
            else:
                native['read_errors'] = {'patients': 'unavailable'}
            self.assertNotIn('self_tend_2', recovery.clinical_order_frontier(s, plans), mutation)
            self.assertIn('tend_3_2', recovery.clinical_order_frontier(s, plans), mutation)

    def test_one_doctor_does_not_delay_a_shorter_native_bleedout_for_later_care(self):
        s, plans = fixture()
        self.assertEqual(set(recovery.clinical_order_frontier(s, plans)), {'earlier', 'other_helper'})
        self.assertEqual(s['development']['clinical_order_frontier']['later']['earliest_native_bleedout_ticks'], 5500)

    def test_near_deadlines_allow_a_real_patient_choice(self):
        s, plans = fixture(); s['development']['resilience']['patients'][1]['bleedout_ticks'] = 6500
        result = recovery.clinical_order_frontier(s, plans)
        self.assertIn('later', result)
        self.assertIn('earlier', result)

    def test_unknown_deadline_or_incomplete_native_read_is_not_assumed_safe(self):
        for mutation in ('bleedout_ticks', 'bleeding_evidence_complete'):
            s, plans = fixture(); del s['development']['resilience']['patients'][1][mutation]
            self.assertIn('later', recovery.clinical_order_frontier(s, plans))

    def test_independent_disease_thermal_or_starvation_crisis_stays_available(self):
        for condition in [dict(def_name='Plague', tendable_now=True, immunity=.5, immunity_can_develop=True),
                          dict(def_name='Heatstroke', life_threatening=True)]:
            s, plans = fixture(); s['development']['resilience']['patients'][1]['conditions'] = [condition]
            self.assertIn('later', recovery.clinical_order_frontier(s, plans))
        s, plans = fixture(); s['development']['resilience']['patients'][1]['starvation_ticks'] = 3000
        self.assertIn('carry_later', recovery.clinical_order_frontier(s, plans))

    def test_failed_earlier_assignment_does_not_block_all_other_care(self):
        s, plans = fixture(); del plans['earlier']
        self.assertIn('later', recovery.clinical_order_frontier(s, plans))

    def test_native_offered_thermal_rescue_is_preserved_before_life_threatening_stage(self):
        s, plans = fixture()
        plans['carry_later']['thermal_rescue'] = True
        s['development']['resilience']['patients'][1]['conditions'] = [dict(def_name='Hypothermia', severity=.2, life_threatening=False)]
        self.assertIn('carry_later', recovery.clinical_order_frontier(s, plans))

    def test_clinical_frontier_never_edits_running_care_or_its_targets(self):
        s, plans = fixture()
        s['combat'] = dict(colonists=[dict(id=3, current_job='TendPatient', current_job_target_id=2)])
        before = copy.deepcopy(s['combat'])
        recovery.clinical_order_frontier(s, plans)
        self.assertEqual(s['combat'], before)


if __name__ == '__main__':
    unittest.main()

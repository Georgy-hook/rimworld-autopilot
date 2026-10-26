"""Synthetic caregiver safety contracts; not raid outcomes."""
import unittest

from colony_combat import stable_patient_self_tend_binding as binding


def clinical(name='Gunshot', **changes):
    return dict(def_name=name, visible=True, life_threatening=False,
                immunity_can_develop=False, immunity=None, tendable_now=True,
                lethal_severity=-1, **changes)


def situation():
    doctor = dict(id=2, current_job='TendPatient', current_job_target_id=1,
                  queued_job_count=0, medical_work_enabled=True,
                  consciousness=.31, moving=.31, manipulation=.21,
                  position=dict(x=0, z=0))
    old = dict(id=1, is_downed=True, position=dict(x=1, z=0))
    return dict(combat=dict(colonists=[old, doctor], hostiles=[]), development=dict(resilience=dict(
        available=True, patients=[dict(pawn_id=1, bleeding_total=0, bleeding_evidence_complete=True,
                                      conditions=[clinical()]),
                                 dict(pawn_id=2, bleeding_total=1.74, bleeding_evidence_complete=True,
                                      tendable_now=True, conditions=[clinical()])]))), doctor


class SelfCareYield(unittest.TestCase):
    def test_explicit_stable_patient_binding(self):
        s, d = situation()
        self.assertEqual(binding(s, d)['reassign_from_patient_id'], 1)

    def test_no_queue_or_carry_override(self):
        for key, value in [('queued_job_count', 1), ('queued_job_count', None), ('queued_job_count', False),
                           ('carrying_pawn_id', 9), ('carrying_player_pawn', True)]:
            s, d = situation(); d[key] = value
            self.assertIsNone(binding(s, d), key)

    def test_never_replace_feeding_rescue_or_operation(self):
        for job in ['FeedPatient', 'Rescue', 'DoBill', 'Goto']:
            s, d = situation(); d['current_job'] = job
            self.assertIsNone(binding(s, d), job)

    def test_keep_any_old_active_bleeding(self):
        s, d = situation(); s['development']['resilience']['patients'][0]['bleeding_total'] = .01
        self.assertIsNone(binding(s, d))

    def test_keep_infection_immunity_race_and_lethal_condition(self):
        for updates in [dict(immunity_can_develop=True, immunity=.8), dict(life_threatening=True),
                        dict(def_name='Infection')]:
            s, d = situation(); s['development']['resilience']['patients'][0]['conditions'][0].update(updates)
            self.assertIsNone(binding(s, d))

    def test_nonimmunizable_zero_is_not_race(self):
        s, d = situation()
        s['development']['resilience']['patients'][0]['conditions'][0].update(
            def_name='OldChronic', immunity=0, immunity_can_develop=False, tendable_now=False)
        self.assertIsNotNone(binding(s, d))

    def test_unknown_immunity_remains_protected(self):
        for value in [None, float('nan'), '0.8']:
            s, d = situation()
            s['development']['resilience']['patients'][0]['conditions'][0].update(
                immunity_can_develop=True, immunity=value)
            self.assertIsNone(binding(s, d))

    def test_invalid_previous_bleeding_does_not_mean_zero(self):
        for value in [False, None, float('nan'), '0']:
            s, d = situation(); s['development']['resilience']['patients'][0]['bleeding_total'] = value
            self.assertIsNone(binding(s, d))

    def test_unknown_or_failed_native_read_stays_protected(self):
        for field in ['bleeding_evidence_complete', 'conditions']:
            s, d = situation(); s['development']['resilience']['patients'][0].pop(field)
            self.assertIsNone(binding(s, d), field)
        s, d = situation(); s['development']['resilience']['available'] = False
        self.assertIsNone(binding(s, d))

    def test_exact_patient_identity_required(self):
        s, d = situation(); d['current_job_target_id'] = 99
        self.assertIsNone(binding(s, d))

    def test_available_flag_does_not_hide_native_read_error(self):
        for key in ['error', 'errors', 'read_errors']:
            s, d = situation(); s['development']['resilience'][key] = {'patients': 'read failed'}
            self.assertIsNone(binding(s, d), key)

    def test_medical_disability_and_capacity_retained(self):
        for field, value in [('medical_work_enabled', False), ('manipulation', .1),
                             ('is_drafted', True), ('is_downed', True), ('is_in_mental_state', True)]:
            s, d = situation(); d[field] = value
            self.assertIsNone(binding(s, d), field)

    def test_routine_self_care_does_not_override_current_care(self):
        s, d = situation(); s['development']['resilience']['patients'][1]['bleeding_total'] = .2
        self.assertIsNone(binding(s, d))

    def test_self_care_not_started_under_nearby_enemy(self):
        s, d = situation(); s['combat']['hostiles'] = [dict(id=99, position=dict(x=5, z=0))]
        self.assertIsNone(binding(s, d))

    def test_recovery_menu_carries_exact_native_reassignment_binding(self):
        import colony_director as director
        s, doctor = situation()
        doctor.update(name='Bleeding doctor', bleeding_rate=1.74, tendable_now=True, health=.41)
        s['colonists'] = [dict(id=p['id'], health_conditions=[],
                              skills=dict(Medicine=dict(disabled=False)),
                              work_priorities=dict(Doctor=dict(disabled=False)))
                          for p in s['combat']['colonists']]
        options = director.post_combat_care_options(s)
        selected = options['self_tend_2']
        self.assertTrue(selected['self_tend'])
        self.assertEqual((selected['patient_id'], selected['doctor_id'], selected['reassign_from_patient_id']), (2, 2, 1))
        self.assertNotIn('tend_1_2', options)
        s['development']['resilience']['patients'][0]['bleeding_total'] = .1
        self.assertNotIn('self_tend_2', director.post_combat_care_options(s))


if __name__ == '__main__':
    unittest.main()

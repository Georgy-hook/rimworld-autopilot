"""A brief blocked gun ray must not become a routine field hospital."""
import copy
import unittest

import colony_combat as combat
import colony_director as director
import colony_medical_recovery as recovery


def situation():
    patient = dict(id=1, name='Patient', position=dict(x=0, z=0), tendable_now=True,
                   bleeding_rate=.3, moving=1, manipulation=1, health=.9, current_job='Wait_Combat')
    doctor = dict(id=3, name='Doctor', position=dict(x=-2, z=0), moving=1, manipulation=1,
                  medicine_skill=8, current_job='Wait', is_drafted=False)
    return dict(game=dict(tick=3000), map=dict(id=1),
                combat=dict(colonists=[patient, doctor], hostiles=[dict(id=99, position=dict(x=30, z=0),
                    has_ranged_weapon=True, weapon_range=37, shootable_opponent_ids=[])]),
                colonists=[dict(id=1, position=dict(x=0, z=0), health_conditions=[],
                    skills=dict(Medicine=dict(disabled=False)), work_priorities=dict(Doctor=dict(disabled=False))),
                    dict(id=3, skills=dict(Medicine=dict(disabled=False)), work_priorities=dict(Doctor=dict(disabled=False)))],
                development=dict(resilience=dict(patients=[dict(pawn_id=1, room_id=0, room_outdoors=True,
                    room_roof_complete=False, bleeding_total=.3, bleeding_evidence_complete=True, conditions=[])],
                    options=[dict(kind='tend', target_id=1, worker_id=3, giver='DoctorTendEmergency')])))


class TreatmentWindow(unittest.TestCase):
    def test_all_new_tend_menus_reject_temporary_outdoor_gun_safety(self):
        s = situation()
        self.assertFalse(combat.safe_new_self_tend(s, s['combat']['colonists'][0]))
        self.assertEqual(director.post_combat_care_options(s), {})
        self.assertEqual(recovery.build_options(None, s, {})['tend_colonist'], {})
        s['combat']['hostiles'][0]['position']['x'] = 50
        self.assertTrue(combat.safe_new_self_tend(s, s['combat']['colonists'][0]))
        self.assertIn('tend_1_3', director.post_combat_care_options(s))
        self.assertIn('1', recovery.build_options(None, s, {})['tend_colonist'])

    def test_only_exact_native_enclosed_room_can_supply_the_routine_window(self):
        s = situation(); patient = s['combat']['colonists'][0]
        clinical = s['development']['resilience']['patients'][0]
        clinical.update(room_id=8, room_outdoors=False, room_roof_complete=True)
        self.assertTrue(combat.safe_new_self_tend(s, patient))
        for field, value in [('pawn_id', 7), ('room_id', None), ('room_outdoors', True), ('room_roof_complete', False)]:
            other = copy.deepcopy(s); other['development']['resilience']['patients'][0][field] = value
            self.assertFalse(combat.safe_new_self_tend(other, patient), field)
        s['combat']['hostiles'][0]['shootable_opponent_ids'] = [1]
        self.assertFalse(combat.safe_new_self_tend(s, patient))

    def test_major_bleeding_keeps_field_care_but_not_unsafe_self_tending(self):
        s = situation(); patient = s['combat']['colonists'][0]
        s['development']['resilience']['patients'][0]['bleeding_total'] = 1.6
        self.assertTrue(combat.new_treatment_window(s, patient))
        self.assertIn('tend_1_3', director.post_combat_care_options(s))
        s['combat']['hostiles'][0]['shootable_opponent_ids'] = [1]
        self.assertFalse(combat.safe_new_self_tend(s, patient))
        s['combat']['hostiles'][0].update(shootable_opponent_ids=[], position=dict(x=10, z=0))
        self.assertFalse(combat.safe_new_self_tend(s, patient))

    def test_only_actual_imminent_bleedout_keeps_the_field_window(self):
        s = situation(); patient = s['combat']['colonists'][0]
        clinical = s['development']['resilience']['patients'][0]
        clinical['bleedout_ticks'] = 800
        self.assertTrue(combat.new_treatment_window(s, patient))
        clinical['bleeding_total'] = 0
        self.assertFalse(combat.new_treatment_window(s, patient))

    def test_chronic_immunity_zero_does_not_turn_a_bruise_into_critical_care(self):
        s = situation(); patient = s['combat']['colonists'][0]
        illness = dict(def_name='Chronic', tendable_now=True, immunity=0, immunity_can_develop=False)
        s['development']['resilience']['patients'][0]['conditions'] = [illness]
        self.assertFalse(combat.new_treatment_window(s, patient))
        illness.update(def_name='Plague', immunity=.5, immunity_can_develop=True)
        self.assertTrue(combat.new_treatment_window(s, patient))
        illness.update(tendable_now=False)
        self.assertFalse(combat.new_treatment_window(s, patient))
        illness.update(def_name='ToxicBuildup', tendable_now=True, life_threatening=True)
        self.assertFalse(combat.new_treatment_window(s, patient))

    def test_no_hostile_care_and_existing_doctor_protection_are_preserved(self):
        s = situation(); s['combat']['hostiles'] = []
        self.assertIn('tend_1_3', director.post_combat_care_options(s))
        doctor = s['combat']['colonists'][1]
        doctor.update(current_job='TendPatient', current_job_target_id=1, tendable_now=True)
        self.assertEqual(combat.self_tend_candidates(s), [])
        self.assertEqual(director.post_combat_care_options(s), {})


if __name__ == '__main__':
    unittest.main()

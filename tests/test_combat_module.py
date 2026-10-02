import unittest
import colony_combat as c

class CombatModuleTests(unittest.TestCase):
    def pawn(self, **extra):
        return {"id":1,"position":{"x":10,"z":10},"has_ranged_weapon":True,"weapon_def":"Gun_Autopistol","weapon_range":25,"moving":1,"distance_to_nearest_opponent":0,**extra}
    def snapshot(self, **pawn):
        return {"combat":{"colonists":[self.pawn(**pawn)],"hostiles":[{"id":2,"position":{"x":10,"z":10},"def_name":"Scyther","distance_to_nearest_opponent":0}]}}
    def test_carried_enemy_or_unknown_victim_is_not_kidnapping(self):
        base = {"id":8,"current_job":"Kidnap","carrying_pawn_id":99}
        self.assertFalse(c.is_kidnapper(base))
        self.assertFalse(c.is_kidnapper({**base,"carrying_player_pawn":False}))
        self.assertFalse(c.is_kidnapper({**base,"current_job":"Rescue","carrying_player_pawn":True}))
        self.assertTrue(c.is_kidnapper({**base,"carrying_player_pawn":True}))
        self.assertTrue(c.is_kidnapper({**base,"current_job":"Goto","lord_job_type":"LordJob_Kidnap","carrying_player_pawn":True}))

    def test_building_only_threat_and_verified_native_tactics(self):
        snap = self.snapshot(distance_to_nearest_opponent=20)
        snap["combat"]["hostiles"] = []
        snap["combat"]["hostile_buildings"] = [{"id":9,"is_turret":True,"position":{"x":20,"z":10},"kind_def":"Turret_Auto","weapon_range":30}]
        self.assertEqual([9], [r["id"] for r in c.live_hostiles(snap)])
        self.assertNotIn("stand_down", c.available_tactics(snap))
        self.assertNotIn("emp_control", c.available_tactics(snap))
        for tactic in ("emp_control","smoke_advance","mortar_counterbattery","attack_structure"):
            snap["combat"]["native_options"] = [dict(tactic=tactic,fighter_id=1,target_id=9,defense_building_id=44)]
            self.assertIn(tactic, c.available_tactics(snap))
            self.assertEqual(9, next(iter(c.native_tactical_options(snap,tactic).values()))["target_id"])
        self.assertEqual(9,c.choose_default_target(snap,"focus_fire"))

    def test_surgery_and_childcare_protection_and_patient_target_b(self):
        for job in ("DoBill","BottleFeedBaby","BreastfeedCarryToMom","BringBabyToSafetyUnforced","PlayWalking","Lessongiving","Deathrest"):
            snap=self.snapshot(current_job=job,distance_to_nearest_opponent=20)
            self.assertEqual({1},c.protected_emergency_care_ids(snap))
            snap["combat"]["native_options"]=[dict(tactic="emp_control",fighter_id=1,target_id=2)]
            self.assertFalse(c.native_tactical_options(snap,"emp_control"))
            snap["combat"]["colonists"][0]["distance_to_nearest_opponent"]=0
            self.assertFalse(c.protected_emergency_care_ids(snap))
        snap=self.snapshot(current_job="FeedPatient",current_job_target_id=999,current_job_target_id_b=8,distance_to_nearest_opponent=20)
        snap["development"]={"resilience":{"patients":[{"pawn_id":8,"downed":True}]}}
        self.assertEqual({1},c.protected_emergency_care_ids(snap))

    def test_zero_contact_offers_withdraw_and_backstep(self):
        tactics=c.available_tactics(self.snapshot())
        self.assertIn('withdraw_and_regroup',tactics)
        self.assertIn('backstep_fire',tactics)
        self.assertNotIn('hold_cover',tactics)
    def test_zero_contact_does_not_protect_tending_worker(self):
        s=self.snapshot(current_job='TendPatient',current_job_target_id=3)
        s['combat']['colonists'].append(self.pawn(id=3,tendable_now=True,is_downed=True))
        self.assertEqual(set(),c.protected_emergency_care_ids(s))
        s['combat']['colonists'][0]['distance_to_nearest_opponent']=10
        self.assertEqual({1},c.protected_emergency_care_ids(s))
    def test_unknown_distance_cannot_protect_medic(self):
        s=self.snapshot(current_job='TendPatient',current_job_target_id=3,distance_to_nearest_opponent=None)
        s['combat']['colonists'].append(self.pawn(id=3,tendable_now=True,is_downed=True))
        self.assertEqual(set(),c.protected_emergency_care_ids(s))
    def test_rescue_and_feed_downed_nonbleeding_patient_are_protected(self):
        for job in ['Rescue', 'FeedPatient']:
            s=self.snapshot(current_job=job,current_job_target_id=3,distance_to_nearest_opponent=20)
            s['combat']['colonists'].append(self.pawn(id=3,tendable_now=False,is_downed=True))
            self.assertEqual({1},c.protected_emergency_care_ids(s))

    def test_native_care_job_protected_when_patient_telemetry_is_absent(self):
        for job in ['TendPatient', 'Rescue', 'FeedPatient', 'BabyPlay', 'BabySuckle', 'PrisonerInterrogateIdentity']:
            s = self.snapshot(current_job=job, distance_to_nearest_opponent=20)
            self.assertEqual({1}, c.protected_emergency_care_ids(s), job)
            self.assertEqual({}, c.available_tactics(s), job)
    def test_animal_patient_rescue_keeps_distant_worker_protected(self):
        s=self.snapshot(current_job='Rescue',current_job_target_id=8,distance_to_nearest_opponent=20)
        s['development']={'resilience': {'patients': [{'pawn_id': 8, 'downed': True, 'tendable_now': False}]}}
        self.assertEqual({1},c.protected_emergency_care_ids(s))
    def test_bad_distance_no_nan_or_fake_contact(self):
        for value in [None,float('nan'),float('inf'),-1,'unknown']:
            self.assertEqual(9999,c.opponent_distance({'distance_to_nearest_opponent':value}))
        self.assertEqual(0,c.opponent_distance({'distance_to_nearest_opponent':0}))
    def test_unknown_position_not_ranked_as_nearest(self):
        s=self.snapshot(distance_to_nearest_opponent=15)
        s['combat']['hostiles']=[{'id':2,'combat_power':999}, {'id':3,'position':{'x':11,'z':10},'combat_power':1}]
        self.assertEqual(3,c.choose_default_target(s,'focus_fire'))
    def test_facts_report_contact_and_mechanics_uncertainty(self):
        facts=c.threat_facts(self.snapshot())
        self.assertEqual([1],facts['contact_fighters'])
        self.assertIn('EMP adaptation',facts['uncertainty'])

if __name__=='__main__':unittest.main()

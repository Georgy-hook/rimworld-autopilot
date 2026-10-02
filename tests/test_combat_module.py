import unittest
import colony_combat as c

class CombatModuleTests(unittest.TestCase):
    def pawn(self, **extra):
        return {"id":1,"position":{"x":10,"z":10},"has_ranged_weapon":True,"weapon_def":"Gun_Autopistol","weapon_range":25,"moving":1,"distance_to_nearest_opponent":0,**extra}
    def snapshot(self, **pawn):
        return {"combat":{"colonists":[self.pawn(**pawn)],"hostiles":[{"id":2,"position":{"x":10,"z":10},"def_name":"Scyther","distance_to_nearest_opponent":0}]}}
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

import copy
import unittest

import colony_combat as combat
import rimworld_laya as bridge


def situation():
    gun = dict(id=1, position=dict(x=0,z=0), current_job='Wait_Combat', is_drafted=True,
               can_fight=True, has_ranged_weapon=True, ranged_attack_available=True,
               moving=1, manipulation=1, consciousness=1, sight=1, weapon_range=32,
               shootable_opponent_ids=[99,100], incoming_ranged_exposure=0,
               distance_to_nearest_opponent=20, health=.8, bleeding_rate=.2)
    ally = dict(id=2, is_downed=True, position=dict(x=20,z=0), is_colonist=True)
    attempt = dict(id=100, is_hostile=True, current_job='Kidnap', current_job_target_id=2,
                   kidnapping_intent=True, position=dict(x=21,z=0), carrying_player_pawn=False)
    other = dict(id=99, current_job='AttackStatic', position=dict(x=15,z=3), has_ranged_weapon=True, weapon_range=20)
    return dict(map=dict(id=1,enemies=2), game=dict(tick=4000, is_paused=False), colonists=[],
                development=dict(resilience=dict(patients=[])),
                combat=dict(colonists=[gun,ally], hostiles=[other,attempt], defenses=[]))


class AbductionResponse(unittest.TestCase):
    def test_observed_pickup_attempt_is_not_yet_a_carried_or_lost_colonist(self):
        s=situation();enemy=s['combat']['hostiles'][1]
        self.assertFalse(combat.is_kidnapper(enemy))
        self.assertTrue(combat.is_abduction_threat(enemy,s))
        facts=combat.threat_facts(s)
        self.assertEqual(facts['carriers'],[])
        self.assertEqual(facts['abduction_attempts'],[dict(id=100,target_id=2)])

    def test_job_label_without_exact_native_patient_and_intent_is_insufficient(self):
        original=situation()
        changes=[('current_job','Goto'),('current_job_target_id',7),('kidnapping_intent',False),('is_hostile',False),('is_colonist',True)]
        for key,value in changes:
            s=copy.deepcopy(original);enemy=s['combat']['hostiles'][1];enemy[key]=value
            self.assertFalse(combat.is_abduction_threat(enemy,s),(key,value))
        for key in ('is_dead','is_downed'):
            s=copy.deepcopy(original);s['combat']['colonists'][1][key]=key=='is_dead'
            self.assertFalse(combat.is_abduction_threat(s['combat']['hostiles'][1],s),key)

    def test_actual_carrier_does_not_require_victim_still_in_spawned_roster(self):
        s=situation();enemy=s['combat']['hostiles'][1]
        enemy.update(carrying_player_pawn=True,carrying_pawn_id=2)
        s['combat']['colonists'].pop()
        self.assertTrue(combat.is_kidnapper(enemy))
        self.assertTrue(combat.is_abduction_threat(enemy,s))

    def test_default_fire_and_interception_prioritize_pickup_before_carrying(self):
        s=situation()
        for tactic in ('hold_cover','focus_fire','intercept_kidnapper','stationary_fire'):
            self.assertEqual(combat.choose_default_target(s,tactic),100,tactic)
        self.assertIn('intercept_kidnapper',combat.available_tactics(s))
        action=bridge.plan_action(s,dict(choice='stationary_fire'))
        self.assertEqual(action['commands'][0]['body']['target_pawn_id'],100)

    def test_available_shot_is_kept_and_missing_lane_requires_review(self):
        s=situation();gun=s['combat']['colonists'][0]
        self.assertTrue(combat.stationary_firing_candidate(gun,s))
        gun['shootable_opponent_ids']=[99]
        self.assertFalse(combat.stationary_firing_candidate(gun,s))

    def test_new_routine_gunner_care_waits_but_critical_care_stays_available(self):
        s=situation();gun=s['combat']['colonists'][0]
        for e in s['combat']['hostiles']:e['position']['x']=80
        self.assertFalse(combat.new_treatment_window(s,gun))
        gun['bleeding_rate']=1.6
        self.assertTrue(combat.new_treatment_window(s,gun))
        gun.update(bleeding_rate=.2,has_ranged_weapon=False)
        self.assertTrue(combat.new_treatment_window(s,gun))

    def test_injured_legal_shooter_can_fire_in_place_without_being_a_fast_runner(self):
        s=situation();gun=s['combat']['colonists'][0]
        gun.update(moving=.4,manipulation=.5)
        self.assertTrue(combat.intercept_capable(gun,s))
        action=bridge.plan_action(s,dict(choice='intercept_kidnapper'))
        self.assertTrue(any(c.get('body',{}).get('fighter_ids')==[1] for c in action['commands']))
        gun['shootable_opponent_ids']=[]
        self.assertFalse(combat.intercept_capable(gun,s))

    def test_existing_care_never_becomes_an_interceptor(self):
        s=situation();gun=s['combat']['colonists'][0]
        gun.update(current_job='TendPatient',current_job_target_id=2)
        self.assertIn(1,combat.protected_emergency_care_ids(s))
        self.assertFalse(combat.intercept_capable(gun,s))

    def test_missing_movement_read_without_an_actual_shot_does_not_authorize_advance(self):
        s=situation();gun=s['combat']['colonists'][0]
        gun.pop('moving');gun['shootable_opponent_ids']=[]
        self.assertFalse(combat.intercept_capable(gun,s))

    def test_only_abductor_does_not_offer_backward_defensive_assembly(self):
        s=situation();s['combat']['hostiles'].pop(0)
        choices=combat.available_tactics(s)
        self.assertIn('intercept_kidnapper',choices)
        for old_post in ('hold_cover','fallback_line','firing_line','focus_fire','stationary_fire'):
            self.assertNotIn(old_post,choices,old_post)


if __name__=='__main__':
    unittest.main()

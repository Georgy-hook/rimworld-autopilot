import unittest
import colony_combat as combat
import rimworld_laya as bridge
from test_combat_scenarios import fighter, raid


def option(kind,actor=2):
    return {'tactic':kind,'fighter_id':actor,'target_id':99,'label':'Exact native defence',
        'effects':{'benefit':'Defend named actor','risk':'Injury possible','cost':'Existing job changes',
                   'inaction':'Enemy continues','uncertainty':'Outcome unverified'}}


class PredictiveFollowupTests(unittest.TestCase):
    def snapshot(self):
        pacifist=fighter(2,ranged=False,weapon=None,distance=8);pacifist['can_fight']=False
        return raid([fighter(1),pacifist],[{'id':99,'is_hostile':True,'health':1,
            'position':{'x':24,'z':10},'current_job':'AttackMelee','current_job_target_id':2}])

    def test_pacifist_lure_is_movement_only_and_requires_exact_native_plan(self):
        s=self.snapshot();o=option('lure_enemy');s['combat']['native_options']=[o]
        self.assertIn('lure_enemy',bridge.make_questions(s)['threat_action']['criteria'])
        a=bridge.plan_action(s,{'choice':'lure_enemy','native_plan':o})
        self.assertEqual(a['commands'][0]['body']['fighter_ids'],[2])
        self.assertEqual(a['commands'][0]['body']['tactic'],'lure_enemy')
        self.assertEqual(a['commands'][0]['body']['target_pawn_id'],99)

    def test_changed_pursuit_or_cover_cannot_replay_a_bait_order(self):
        s=self.snapshot();o=option('lure_enemy');s['combat']['native_options']=[]
        self.assertNotIn('lure_enemy',combat.available_tactics(s))
        self.assertEqual(bridge.plan_action(s,{'choice':'lure_enemy','native_plan':o})['kind'],'noop')

    def test_contact_defence_survives_the_isolated_gunner_retreat_menu(self):
        p=fighter(1,distance=1);s=raid([p],[{'id':99,'health':1,'position':{'x':12,'z':10}}])
        o=option('contact_melee',1);s['combat']['native_options']=[o]
        self.assertIn('contact_melee',bridge.make_questions(s)['threat_action']['criteria'])
        a=bridge.plan_action(s,{'choice':'contact_melee','native_plan':o})
        self.assertEqual(a['commands'][0]['body']['fighter_ids'],[1])
        self.assertEqual(a['commands'][0]['body']['tactic'],'contact_melee')

    def test_contact_option_cannot_take_an_exact_active_feeder(self):
        s=self.snapshot();s['combat']['colonists'][0].update(current_job='FeedPatient',
            current_job_target_id_b=2,distance_to_nearest_opponent=1)
        s['combat']['native_options']=[option('contact_melee',1)]
        self.assertFalse(combat.native_tactical_options(s,'contact_melee'))

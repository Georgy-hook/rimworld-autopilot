import unittest
import stream_observer as observer


class EarlyCombatTests(unittest.TestCase):
    def test_live_raider_slows_before_any_injury(self):
        self.assertTrue(observer._active_combat_threat({'hostiles':[{'id':9,'is_hostile':True}]}))

    def test_dead_or_downed_enemy_is_not_an_active_speed_threat(self):
        for flag in ('is_dead','is_downed'):
            self.assertFalse(observer._active_combat_threat({'hostiles':[{'id':9,'is_hostile':True,flag:True}]}))

    def test_passive_animal_and_hunt_for_wild_prey_do_not_slow_colony(self):
        for job in ('GotoWander','PredatorHunt'):
            self.assertFalse(observer._active_combat_threat({'colonists':[{'id':1}],
                'hostiles':[{'id':9,'is_hostile':False,'current_job':job,'current_job_target_id':8}]}))

    def test_neutral_predator_hunting_an_owned_pet_is_a_threat(self):
        self.assertTrue(observer._active_combat_threat({'colony_animals':[{'id':8}],
            'hostiles':[{'id':9,'is_hostile':False,'current_job':'PredatorHunt','current_job_target_id':8}]}))

    def test_unknown_victim_is_not_a_proved_player_target(self):
        self.assertFalse(observer._active_combat_threat({'colonists':[{}],
            'hostiles':[{'id':9,'current_job':'PredatorHunt'}]}))

    def test_pacing_reopens_after_threat_but_never_without_ready_director(self):
        p=observer.ObserverPlanner();game={'is_paused':False}
        self.assertEqual(p.pacing_actions(game,0,critical_combat=True),[{'kind':'ensure_speed','speed':1}])
        self.assertEqual(p.pacing_actions(game,1,critical_combat=True),[])
        self.assertEqual(p.pacing_actions(game,2),[{'kind':'ensure_speed','speed':3}])
        self.assertEqual(p.pacing_actions(game,3,critical_combat=True,director_is_ready=False),[{'kind':'ensure_speed','speed':0}])

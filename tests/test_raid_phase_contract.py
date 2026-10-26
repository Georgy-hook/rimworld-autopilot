"""Preparation cannot be an indefinite drafted waiting state."""
import unittest
import colony_combat as combat
import rimworld_laya as bridge
import colony_director as director
from unittest.mock import Mock
from test_combat_scenarios import fighter, raid

def staged():
    gunner=fighter(1,distance=90,range_cells=37)
    gunner.update(is_drafted=True,current_job='Wait_Combat',shootable_opponent_ids=[])
    enemy={'id':99,'kind_def':'Raider','is_animal':False,'current_job':'Wait_Combat',
           'lord_job_type':'LordJob_StageThenAttack','lord_toil_name':'LordToil_Stage',
           'distance_to_nearest_opponent':90,'position':{'x':100,'z':100}}
    return raid([gunner],[enemy])

class RaidPhaseContract(unittest.TestCase):
    def test_downed_enemy_nearest_distance_does_not_offer_contact(self):
        p=fighter(1,distance=1);p['position']={'x':10,'z':10}
        fallen={'id':91,'position':{'x':11,'z':10},'is_downed':True}
        live={'id':92,'position':{'x':30,'z':10},'current_job':'AttackMelee'}
        s=raid([p],[fallen,live])
        self.assertEqual(combat.contact_opponents(s,p),[])
        self.assertNotIn('engage_melee',bridge.make_questions(s)['threat_action']['criteria'])
        live['position']={'x':11,'z':10}
        self.assertEqual([e['id'] for e in combat.contact_opponents(s,p)],[92])
        self.assertIn('engage_melee',bridge.make_questions(s)['threat_action']['criteria'])

    def test_initial_cargo_wait_cannot_hide_an_actual_assault(self):
        s=staged();s['game']['tick']=17
        self.assertTrue(director.landing_cargo_pending(s))
        s['combat']['hostiles'][0]['lord_toil_name']='LordToil_AssaultColony'
        self.assertFalse(director.landing_cargo_pending(s))
        s['combat']['hostiles'][0].update(lord_toil_name='LordToil_Stage',current_job='AttackMelee')
        self.assertFalse(director.landing_cargo_pending(s))

    def test_complete_landing_and_safe_initial_cargo_are_distinct(self):
        s=staged();s['combat']['hostiles']=[];s['game']['tick']=17
        self.assertTrue(director.landing_cargo_pending(s))
        s['game']['tick']=600
        self.assertFalse(director.landing_cargo_pending(s))

    def test_current_stage_toil_precedes_wait_combat_and_camp_movement(self):
        enemy=staged()['combat']['hostiles'][0]
        for job in ('Wait_Combat','Goto','GotoWander','Wait_Wander'):
            self.assertTrue(combat.hostile_is_preparing({**enemy,'current_job':job}),job)

    def test_assault_toil_precedes_raid_lord_job_name(self):
        enemy=staged()['combat']['hostiles'][0]
        for toil in ('LordToil_AssaultColony','LordToil_KidnapCover','LordToil_StealCover'):
            self.assertFalse(combat.hostile_is_preparing({**enemy,'lord_toil_name':toil}))

    def test_a_real_shot_or_attack_during_stage_is_not_safe_waiting(self):
        enemy=staged()['combat']['hostiles'][0]
        self.assertFalse(combat.hostile_is_preparing({**enemy,'is_warming_up':True}))
        self.assertFalse(combat.hostile_is_preparing({**enemy,'current_job':'AttackMelee'}))

    def test_drafted_wait_is_not_a_real_engagement(self):
        s=staged()
        self.assertEqual(combat.engaged_fighter_ids(s),set())
        self.assertEqual(combat.safe_work_actor_ids(s,allow_idle_drafted=True),{1})

    def test_only_work_or_explicit_preemptive_plan_during_safe_stage(self):
        options=bridge.make_questions(staged())['threat_action']['criteria']
        self.assertIn('continue_safe_colony_work',options)
        self.assertIn('preemptive_strike',options)
        for forbidden in ('hold_cover','focus_fire','engage_melee','firing_line','hold_and_observe'):
            self.assertNotIn(forbidden,options)

    def test_normal_work_releases_waiting_defender_and_returns_development(self):
        s=staged();a=bridge.plan_action(s,{'choice':'continue_safe_colony_work'})
        self.assertEqual(a['commands'][0]['body'],{'pawn_id':1,'is_drafted':False})
        s['combat']['colonists'][0].update(is_drafted=False,current_job='Ingest')
        self.assertTrue(director.staging_development_allowed(s,{'decision':{'choice':'continue_safe_colony_work'}}))

    def test_three_days_of_staging_does_not_create_a_draft_order(self):
        s=staged()
        for tick in range(0,180001,6000):
            s['game']['tick']=tick
            a=bridge.plan_action(s,{'choice':'continue_safe_colony_work'})
            self.assertFalse(any(c.get('body',{}).get('is_drafted') is True for c in a.get('commands',[])))
            s['combat']['colonists'][0].update(is_drafted=False,current_job='LayDown' if tick%12000 else 'Ingest')

    def test_assault_transition_closes_work_window_immediately(self):
        s=staged();s['combat']['hostiles'][0]['lord_toil_name']='LordToil_AssaultColony'
        self.assertEqual(combat.safe_work_actor_ids(s,allow_idle_drafted=True),set())
        self.assertNotIn('continue_safe_colony_work',bridge.make_questions(s)['threat_action']['criteria'])
        self.assertEqual(bridge.plan_action(s,{'choice':'prepare_undrafted'})['kind'],'noop')

    def test_preemptive_queued_advance_and_actual_aim_keep_their_commitment(self):
        s=staged();p=s['combat']['colonists'][0]
        p.update(current_job='Goto',combat_plan='preemptive_strike',queued_attack_target_ids=[99])
        self.assertEqual(combat.engaged_fighter_ids(s),{1})
        self.assertEqual(combat.safe_work_actor_ids(s,allow_idle_drafted=True),set())
        p.update(current_job='Wait_Combat',is_warming_up=True)
        self.assertEqual(combat.engaged_fighter_ids(s),{1})

    def test_out_of_range_attack_order_does_not_mean_a_shot(self):
        s=staged();p=s['combat']['colonists'][0]
        p.update(current_job='AttackStatic',current_job_target_id=99)
        self.assertEqual(combat.engaged_fighter_ids(s),set())
        self.assertEqual(combat.safe_work_actor_ids(s,allow_idle_drafted=True),{1})

    def test_new_self_tend_requires_escape_from_pursuit_and_incoming_fire(self):
        pawn=fighter(1,distance=30);pawn.update(tendable_now=True,position={'x':0,'z':0})
        enemy={'id':99,'position':{'x':30,'z':0},'has_ranged_weapon':True,
               'weapon_range':37,'shootable_opponent_ids':[1]}
        s=raid([pawn],[enemy])
        self.assertEqual(combat.self_tend_candidates(s),[])
        enemy.update(shootable_opponent_ids=[],current_job_target_id=1,current_job='AttackMelee')
        self.assertEqual(combat.self_tend_candidates(s),[])
        enemy.update(current_job_target_id=None,current_job='Wait_Combat',position={'x':10,'z':0})
        self.assertEqual(combat.self_tend_candidates(s),[])
        enemy.update(position={'x':30,'z':0})
        self.assertEqual(combat.self_tend_candidates(s),[])
        enemy.update(position={'x':50,'z':0})
        self.assertEqual(combat.self_tend_candidates(s),[pawn])

    def test_completed_battle_releases_idle_workers_while_finisher_and_care_continue(self):
        s=staged();s['combat']['hostiles'][0]['is_downed']=True
        s['combat']['colonists']=[dict(s['combat']['colonists'][0]),
            {'id':2,'is_drafted':True,'current_job':'AttackMelee','current_job_kill_incapped_target':True,'current_job_target_id':99},
            {'id':3,'is_drafted':True,'current_job':'TendPatient','has_care_job':True},
            {'id':4,'is_drafted':True,'current_job':'Wait_Combat'},
            {'id':6,'is_drafted':True,'current_job':'AttackStatic','current_job_target_id':99},
            {'id':7,'is_drafted':True,'current_job':'Goto','combat_plan':'focus_fire'}]
        client=Mock();client.post.return_value={'applied':True}
        director.release_idle_combat_workers(client,s,{4})
        self.assertEqual(client.post.call_args.kwargs['body']['fighter_ids'],[1,6,7])
        s['combat']['hostiles'][0]['is_downed']=False
        client.reset_mock();self.assertIsNone(director.release_idle_combat_workers(client,s))
        client.post.assert_not_called()

    def test_fresh_observation_keeps_selected_control_alive_without_reissuing_jobs(self):
        s=staged();s['combat']['colonists'][0]['combat_plan']='hold_cover'
        client=Mock();client.post.return_value={'applied':False,'notes':['lease refreshed']}
        for tick in (0,900,1800):
            s['game']['tick']=tick
            bridge.refresh_combat_control(client,s,apply=True)
        self.assertEqual(client.post.call_count,3)
        self.assertTrue(all(c.kwargs['body']['tactic']=='refresh_control' for c in client.post.call_args_list))
        client.reset_mock();bridge.refresh_combat_control(client,s,apply=False)
        client.post.assert_not_called()
        s['combat']['colonists'][0].pop('combat_plan')
        bridge.refresh_combat_control(client,s,apply=True);client.post.assert_not_called()

    def test_actual_hostile_carrier_exiting_map_is_not_an_ordinary_distant_enemy(self):
        s=staged();enemy=s['combat']['hostiles'][0]
        enemy.update(current_job='Goto',lord_job_type='LordJob_ExitMapBest',lord_toil_name='LordToil_ExitMap',
                     carrying_player_pawn=True,carrying_pawn_id=7)
        self.assertTrue(combat.is_kidnapper(enemy))
        self.assertFalse(combat.hostile_is_preparing(enemy))
        self.assertIn('intercept_kidnapper',bridge.make_questions(s)['threat_action']['criteria'])
        for passive in ('hold_cover','firing_line','hold_and_observe','prepare_undrafted'):
            self.assertNotIn(passive,bridge.make_questions(s)['threat_action']['criteria'])
        enemy['carrying_player_pawn']=False
        self.assertFalse(combat.is_kidnapper(enemy))
        enemy.update(carrying_player_pawn=True,is_colonist=True)
        self.assertFalse(combat.is_kidnapper(enemy))

    def test_healthy_gun_has_a_stationary_option_when_the_native_lane_is_open(self):
        s=staged();pawn=s['combat']['colonists'][0];enemy=s['combat']['hostiles'][0]
        pawn.update(distance_to_nearest_opponent=20,shootable_opponent_ids=[99],moving=1,manipulation=1,sight=1)
        enemy.update(lord_toil_name='LordToil_AssaultColony',distance_to_nearest_opponent=20)
        options=bridge.make_questions(s)['threat_action']['criteria']
        self.assertIn('stationary_fire',options)
        action=bridge.plan_action(s,{'choice':'stationary_fire'})
        orders=[c['body'] for c in action['commands'] if c['endpoint']=='/api/v1/combat/tactic']
        self.assertEqual(orders,[dict(map_id=s['map']['id'],tactic='stationary_fire',fighter_ids=[1],target_pawn_id=99)])

    def test_native_corridor_keeps_a_healthy_firing_group_until_new_danger(self):
        guns=[fighter(i,distance=10) for i in (1,2)]
        for p in guns:p.update(is_drafted=True,current_job='AttackStatic',health=1,moving=1,bleeding_rate=0,
            shootable_opponent_ids=[99],defended_approach_target_ids=[99])
        enemy=dict(id=99,kind_def='Raider',has_ranged_weapon=False,is_animal=False,current_job='AttackMelee',
                   distance_to_nearest_opponent=10,position=dict(x=10,z=0))
        s=raid(guns,[enemy])
        self.assertTrue(combat.held_defensive_corridor(s))
        self.assertNotIn('backstep_fire',bridge.make_questions(s)['threat_action']['criteria'])
        guns[0]['bleeding_rate']=.2
        self.assertFalse(combat.held_defensive_corridor(s))
        self.assertIn('backstep_fire',bridge.make_questions(s)['threat_action']['criteria'])
        guns[0]['bleeding_rate']=0;enemy['distance_to_nearest_opponent']=2
        self.assertFalse(combat.held_defensive_corridor(s))
        enemy['distance_to_nearest_opponent']=10
        for p in guns:p.pop('defended_approach_target_ids')
        self.assertFalse(combat.held_defensive_corridor(s))

    def test_crossfire_reopens_cover_review_for_a_mobile_gun(self):
        s=staged();pawn=s['combat']['colonists'][0];enemy=s['combat']['hostiles'][0]
        pawn.update(distance_to_nearest_opponent=20,shootable_opponent_ids=[99],incoming_ranged_exposure=1.4)
        enemy.update(has_ranged_weapon=True,lord_toil_name='LordToil_AssaultColony',distance_to_nearest_opponent=20)
        options=bridge.make_questions(s)['threat_action']['criteria']
        self.assertNotIn('stationary_fire',options)
        self.assertIn('hold_cover',options)
        self.assertEqual(bridge.plan_action(s,{'choice':'stationary_fire'})['kind'],'noop')
        pawn['incoming_ranged_exposure']=.45
        self.assertIn('stationary_fire',bridge.make_questions(s)['threat_action']['criteria'])

    def test_an_impaired_exposed_shooter_can_keep_an_actual_shot(self):
        s=staged();pawn=s['combat']['colonists'][0]
        pawn.update(distance_to_nearest_opponent=20,shootable_opponent_ids=[99],incoming_ranged_exposure=1.4,moving=.3)
        s['combat']['hostiles'][0].update(has_ranged_weapon=True,lord_toil_name='LordToil_AssaultColony',distance_to_nearest_opponent=20)
        self.assertIn('stationary_fire',bridge.make_questions(s)['threat_action']['criteria'])
        orders=bridge.plan_action(s,{'choice':'stationary_fire'})['commands']
        self.assertEqual(orders[0]['body']['fighter_ids'],[1])

    def test_mobile_gun_cannot_pin_itself_to_an_escaping_carrier(self):
        s=staged();pawn=s['combat']['colonists'][0]
        pawn.update(distance_to_nearest_opponent=20,shootable_opponent_ids=[99],incoming_ranged_exposure=0)
        s['combat']['hostiles'][0].update(current_job='Kidnap',carrying_pawn_id=21,
            carrying_player_pawn=True,distance_to_nearest_opponent=20)
        self.assertNotIn('stationary_fire',bridge.make_questions(s)['threat_action']['criteria'])
        self.assertEqual(bridge.plan_action(s,{'choice':'stationary_fire'})['kind'],'noop')

    def test_stationary_volley_uses_the_lane_shared_by_the_guns(self):
        guns=[fighter(i,distance=20) for i in (1,2,3)]
        for i,p in enumerate(guns):
            p.update(position={'x':10,'z':10+i*4},shootable_opponent_ids=[99,100] if i<2 else [100])
        enemies=[{'id':99,'position':{'x':12,'z':10},'health':1},
                 {'id':100,'position':{'x':26,'z':14},'health':1}]
        commands=bridge.plan_action(raid(guns,enemies),{'choice':'stationary_fire'})['commands']
        self.assertEqual([c['body']['target_pawn_id'] for c in commands if c['endpoint']=='/api/v1/combat/tactic'],[100,100,100])

    def test_impaired_interceptor_can_take_an_available_last_shot(self):
        s=staged();pawn=s['combat']['colonists'][0]
        pawn.update(distance_to_nearest_opponent=20,shootable_opponent_ids=[99],moving=.3)
        s['combat']['hostiles'][0].update(current_job='ExitMapBest',carrying_pawn_id=21,
            carrying_player_pawn=True,distance_to_nearest_opponent=20)
        self.assertIn('stationary_fire',bridge.make_questions(s)['threat_action']['criteria'])
        self.assertEqual(bridge.plan_action(s,{'choice':'stationary_fire'})['commands'][0]['body']['fighter_ids'],[1])

    def test_mobile_covering_gun_keeps_an_actual_shot_at_close_pursuit(self):
        s=staged();gun=s['combat']['colonists'][0]
        gun.update(distance_to_nearest_opponent=20,shootable_opponent_ids=[99])
        ally=fighter(2,distance=7);ally.update(position={'x':80,'z':100})
        s['combat']['colonists'].append(ally)
        enemy=s['combat']['hostiles'][0]
        enemy.update(position={'x':87,'z':100},current_job='AttackMelee',current_job_target_id=2,
            lord_toil_name='LordToil_AssaultColony',distance_to_nearest_opponent=7)
        self.assertTrue(combat.stationary_firing_candidate(gun,s))
        self.assertEqual(bridge.plan_action(s,{'choice':'stationary_fire'})['kind'],'commands')
        gun['shootable_opponent_ids']=[]
        self.assertFalse(combat.stationary_firing_candidate(gun,s))
        self.assertEqual(bridge.plan_action(s,{'choice':'stationary_fire'})['kind'],'noop')
        enemy['position']['x']=90
        self.assertTrue(combat.stationary_firing_candidate(gun,s))

    def test_distant_pursuers_do_not_split_the_requested_shared_volley(self):
        guns=[fighter(i,distance=15) for i in (1,2)]
        for i,p in enumerate(guns):p.update(position={'x':10,'z':10+i*4},shootable_opponent_ids=[99,100])
        enemies=[{'id':99,'position':{'x':24,'z':10},'current_job':'AttackMelee','current_job_target_id':1},
                 {'id':100,'position':{'x':24,'z':14},'current_job':'AttackMelee','current_job_target_id':2}]
        commands=bridge.plan_action(raid(guns,enemies),{'choice':'stationary_fire'})['commands']
        self.assertEqual([c['body']['target_pawn_id'] for c in commands if c['endpoint']=='/api/v1/combat/tactic'],[99,99])

    def test_shared_volley_uses_loaded_damage_resistance_not_just_displayed_health(self):
        guns=[fighter(i,distance=20) for i in (1,2)]
        for p in guns:p.update(position={'x':10,'z':10},shootable_opponent_ids=[99,100])
        enemies=[{'id':99,'position':{'x':25,'z':10},'health':1,'incoming_damage_factor':.5,'body_size':1},
                 {'id':100,'position':{'x':25,'z':10},'health':1,'incoming_damage_factor':1,'body_size':1}]
        commands=bridge.plan_action(raid(guns,enemies),{'choice':'stationary_fire'})['commands']
        self.assertEqual([c['body']['target_pawn_id'] for c in commands if c['endpoint']=='/api/v1/combat/tactic'],[100,100])

    def test_medical_skill_alone_is_not_a_ready_doctor(self):
        p=fighter(1,distance=20)
        p.update(medicine_skill=8,medical_work_enabled=True,consciousness=1,moving=1,manipulation=1)
        s=raid([p],[])
        self.assertEqual(combat.medically_capable_ids(s),{1})
        for field,value in [('medical_work_enabled',False),('is_downed',True),('is_in_mental_state',True),
                            ('consciousness',.1),('moving',0),('manipulation',None)]:
            prior=p.get(field);p[field]=value
            self.assertEqual(combat.medically_capable_ids(s),set(),field)
            p[field]=prior

    def test_observed_attack_on_remaining_medic_has_shared_cover_but_not_carrier_priority(self):
        guns=[fighter(i,distance=20) for i in (1,2)]
        for i,p in enumerate(guns):p.update(position={'x':10,'z':10+i*4},shootable_opponent_ids=[99,100])
        guns[1].update(medical_work_enabled=True,consciousness=1,moving=1,manipulation=1)
        enemies=[{'id':99,'position':{'x':23,'z':10},'current_job':'AttackMelee','current_job_target_id':1},
                 {'id':100,'position':{'x':25,'z':14},'current_job':'Wait_Combat','observed_attack_target_id':2}]
        s=raid(guns,enemies)
        def targets():
            return [c['body']['target_pawn_id'] for c in bridge.plan_action(s,{'choice':'stationary_fire'})['commands']
                    if c['endpoint']=='/api/v1/combat/tactic']
        self.assertEqual(targets(),[100,100])
        enemies[0].update(current_job='Kidnap',carrying_player_pawn=True,carrying_pawn_id=7)
        # The stationary option belongs only to immobile interceptors in a carrier emergency.
        for p in guns:p['moving']=.3
        self.assertEqual(targets(),[99,99])

    def test_distant_downed_enemy_does_not_cancel_an_ordinary_stationary_shot(self):
        s=staged();pawn=s['combat']['colonists'][0]
        pawn.update(distance_to_nearest_opponent=20,shootable_opponent_ids=[99])
        s['combat']['hostiles'][0].update(current_job='AttackStatic',distance_to_nearest_opponent=20)
        s['combat']['hostiles'].append({'id':98,'is_downed':True,'current_job':'Kidnap',
            'carrying_player_pawn':True,'carrying_pawn_id':21})
        self.assertIn('stationary_fire',bridge.make_questions(s)['threat_action']['criteria'])

if __name__=='__main__':unittest.main()

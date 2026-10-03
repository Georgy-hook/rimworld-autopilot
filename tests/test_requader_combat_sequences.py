import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import colony_combat as combat
import rimworld_laya as bridge

# Capacities/identities are from Requader resume-first; target lane is an
# explicitly varied native readback, not a claim that its engine path was run.
def injured_snapshot():
    pawn = dict(id=254,name='Alyssa',health=.5367,position={'x':165,'z':116},
                weapon_def='Gun_Revolver',has_ranged_weapon=True,weapon_range=25,
                manipulation=.4,sight=.94,moving=.3,is_drafted=True,can_fight=True,
                distance_to_nearest_opponent=16.76,shootable_opponent_ids=[5068],
                ranged_attack_available=True)
    return {'game':{'tick':220163,'is_paused':False},'map':{'id':1,'enemies':1},
            'colonists':[{'id':254,'rest':.8,'hunger':.8}],
            'combat':{'available':True,'colonists':[pawn], 'available_weapons':[],
                      'defenses':[],'hostile_buildings':[],'native_options':[],
                      'hostiles':[{'id':5068,'name':'Bambino','kind_def':'YorkshireTerrier',
                                   'is_animal':True,'is_hostile':True,'is_in_mental_state':True,
                                   'current_job':'AttackMelee','position':{'x':170,'z':100}}]}}

class StationaryAgent:
    def predict(self, state, questions):
        key, question = next(iter(questions.items()))
        criteria = question['criteria']
        choice = 'stationary_fire' if 'stationary_fire' in criteria else next(iter(criteria))
        return {'answers':{key:{'choice':choice,'confidence':1}}}

class NativeClient:
    def __init__(self): self.posts=[]
    def post(self, endpoint, **kwargs):
        self.posts.append((endpoint,kwargs))
        return {'attacking_pawn_ids':[254],'positioned_pawn_ids':[], 'psycast_queued':False}

class RequaderCombatSequenceTests(unittest.TestCase):
    def test_eight_actual_cycles_impaired_shooter_only_current_position_shot(self):
        snap=injured_snapshot(); client=NativeClient()
        with tempfile.TemporaryDirectory() as folder, patch.object(bridge,'collect_snapshot',side_effect=lambda _:copy.deepcopy(snap)), patch.object(bridge,'append_log'):
            for cycle in range(8):
                snap['game']['tick']+=1
                record=bridge.run_cycle(client,StationaryAgent(),apply=True,confidence=0,log_path=Path(folder)/'log')
                self.assertEqual('stationary_fire',record['decision']['choice'])
                self.assertNotIn('advance_to_range',combat.available_tactics(snap))
                self.assertNotIn('skirmish',combat.available_tactics(snap))
        self.assertEqual(8,len(client.posts))
        for endpoint, kwargs in client.posts:
            self.assertEqual('/api/v1/combat/tactic',endpoint)
            self.assertEqual({'map_id':1,'tactic':'stationary_fire','fighter_ids':[254],'target_pawn_id':5068},kwargs['body'])

    def test_stationary_rejection_memory_suppresses_unchanged_then_recovers(self):
        snap=injured_snapshot(); client=NativeClient(); memory={}
        original=client.post
        def reject(endpoint, **kwargs):
            original(endpoint, **kwargs)
            return {'attacking_pawn_ids':[], 'positioned_pawn_ids':[], 'psycast_queued':False}
        client.post=reject
        with tempfile.TemporaryDirectory() as folder, patch.object(bridge,'collect_snapshot',side_effect=lambda _:copy.deepcopy(snap)), patch.object(bridge,'append_log'):
            for now in range(100,108):
                with patch('time.time',return_value=now):
                    bridge.run_cycle(client,StationaryAgent(),apply=True,confidence=0,log_path=Path(folder)/'log',combat_memory=memory,combat_signature=lambda _: 'stable')
            self.assertEqual(2,len(client.posts))
            with patch('time.time',return_value=162):
                bridge.run_cycle(client,StationaryAgent(),apply=True,confidence=0,log_path=Path(folder)/'log',combat_memory=memory,combat_signature=lambda _: 'stable')
            self.assertEqual(3,len(client.posts))
            snap['combat']['hostiles'][0]['id']=5069
            snap['combat']['colonists'][0]['shootable_opponent_ids']=[5069]
            with patch('time.time',return_value=163):
                bridge.run_cycle(client,StationaryAgent(),apply=True,confidence=0,log_path=Path(folder)/'log',combat_memory=memory,combat_signature=lambda _: 'stable')
            self.assertEqual(5069,client.posts[-1][1]['body']['target_pawn_id'])

    def test_unverified_or_unavailable_lane_never_advances_injured_shooter(self):
        for readback in ([],None):
            snap=injured_snapshot(); pawn=snap['combat']['colonists'][0]
            if readback is None: pawn.pop('shootable_opponent_ids')
            else: pawn['shootable_opponent_ids']=readback
            for cycle in range(8):
                self.assertNotIn('stationary_fire',combat.available_tactics(snap))
                self.assertNotIn('advance_to_range',combat.available_tactics(snap))
                self.assertEqual('noop',bridge.plan_action(snap,{'choice':'stationary_fire'})['kind'])
        snap=injured_snapshot(); snap['combat']['colonists'][0]['ranged_attack_available']=False
        self.assertNotIn('stationary_fire',combat.available_tactics(snap))

    def test_actual_remote_patient_facts_release_exposed_traveling_doctor(self):
        snap=injured_snapshot(); doctor=snap['combat']['colonists'][0]
        doctor.update(id=22839,name='Nanda',current_job='TendPatient',current_job_target_id=257,
                      current_job_target_position={'x':216,'z':142},distance_to_nearest_opponent=16.76)
        patient={'id':257,'position':{'x':216,'z':142},'is_downed':True}
        snap['combat']['colonists'].append(patient)
        for cycle in range(8):
            self.assertFalse(combat.care_at_bedside(doctor,snap))
            self.assertNotIn(22839,combat.protected_emergency_care_ids(snap))
        doctor['position']={'x':216,'z':141}
        self.assertTrue(combat.care_at_bedside(doctor,snap))
        self.assertIn(22839,combat.protected_emergency_care_ids(snap))
        doctor['distance_to_nearest_opponent']=2
        self.assertNotIn(22839,combat.protected_emergency_care_ids(snap))

    def test_feed_target_a_food_does_not_claim_patient_bedside(self):
        snap=injured_snapshot(); doctor=snap['combat']['colonists'][0]
        doctor.update(current_job='FeedPatient',current_job_target_id=999,
                      current_job_target_id_b=257,current_job_target_position=doctor['position'])
        snap['combat']['colonists'].append({'id':257,'position':{'x':216,'z':142},'is_downed':True})
        self.assertFalse(combat.care_at_bedside(doctor,snap))
        doctor.update(care_target_id=257,care_target_position={'x':216,'z':142},care_at_bedside=False)
        self.assertNotIn(254,combat.protected_emergency_care_ids(snap))
        doctor['care_at_bedside']=True
        self.assertIn(254,combat.protected_emergency_care_ids(snap))

    def test_passive_rat_is_not_humanoid_staging(self):
        for job in ('Wait','Wander'):
            self.assertFalse(combat.hostile_is_preparing({'kind_def':'Rat','is_animal':True,'current_job':job}))
            self.assertFalse(combat.hostile_is_preparing({'kind_def':'Rat','current_job':job}))
        self.assertTrue(combat.hostile_is_preparing({'kind_def':'Human','current_job':'Wait','lord_job_type':'LordJob_StageThenAttack'}))

    def test_eight_cycles_uncontrollable_founders_report_blocked_without_orders(self):
        snap=injured_snapshot(); snap['combat']['colonists'][0]['is_downed']=True
        client=NativeClient()
        with tempfile.TemporaryDirectory() as folder, patch.object(bridge,'collect_snapshot',side_effect=lambda _:copy.deepcopy(snap)), patch.object(bridge,'append_log'):
            for cycle in range(8):
                snap['game']['tick']+=1
                record=bridge.run_cycle(client,StationaryAgent(),apply=True,confidence=0,log_path=Path(folder)/'log')
                self.assertTrue(record['result']['combat_unavailable'])
                self.assertTrue(record['result']['blocked'])
        self.assertEqual([],client.posts)

    def test_native_contract_fields_and_stationary_branch_are_additive(self):
        root=Path('vendor/RIMAPI/Source/RIMAPI/RimworldRestApi')
        dto=(root/'Models/Pawns/CombatStateDto.cs').read_text()
        service=(root/'Services/Pawns/CombatService/CombatService.cs').read_text()
        for field in ('CurrentJobTargetId','CurrentJobTargetPosition','CareAtBedside','CareTargetId','CareTargetPosition','RangedAttackAvailable'):
            self.assertIn(field,dto); self.assertIn(field+' =',service)
        helper=(root/'Helpers/CombatNativeHelper.cs').read_text()
        self.assertIn('job.def == JobDefOf.FeedPatient',helper)
        self.assertIn('return job.targetB.Thing',helper)
        tactics=(root/'Helpers/CombatTacticsHelper.cs').read_text()
        branch=tactics.split('if (tactic == "stationary_fire")',1)[1].split('if (tactic == "preemptive_strike")',1)[0]
        self.assertIn('CanShootTarget(pawn, pawn.Position, target)',branch)
        self.assertIn('JobDefOf.AttackStatic',branch)
        self.assertIn('pawn.CurJob.targetA.Thing == target',branch)
        self.assertIn('++pathAttempts > 16',tactics)
        self.assertIn('.Take(3).ToList()',tactics)
        self.assertNotIn('JobDefOf.Goto',branch)
        self.assertIn('TryFindCoveredRetreatCell',tactics)
        self.assertIn('RetreatRouteSafe',tactics)


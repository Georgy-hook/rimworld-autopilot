import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import rimworld_laya as bridge
import colony_director as director

class Agent:
    def predict(self, state, questions):
        key, question = next(iter(questions.items()))
        criteria = question['criteria']
        choice = 'smoke_advance' if 'smoke_advance' in criteria else next((k for k in criteria if k != 'defer'), next(iter(criteria)))
        return {'answers': {key: {'choice': choice, 'confidence': 1}}}

class Client:
    def __init__(self): self.posts = []
    def post(self, endpoint, **kwargs):
        self.posts.append((endpoint, kwargs))
        body = kwargs.get('body') or {}
        if endpoint.endswith('/tactic'):
            return {'applied': False} if body.get('fighter_ids') == [1] else {'attacking_pawn_ids': [n for n in body.get('fighter_ids') or [] if n != 1], 'positioned_pawn_ids': [], 'psycast_queued': False}
        return {'applied': True}

def snapshot():
    pawns = [{'id': n, 'name': str(n), 'health': 1, 'weapon_def': 'Gun_Revolver', 'has_ranged_weapon': True,
              'weapon_range': 25, 'moving': 1, 'sight': 1, 'manipulation': 1, 'is_drafted': True,
              'distance_to_nearest_opponent': 20, 'position': {'x': n, 'z': 1}} for n in (1,2)]
    options = [{'tactic': 'smoke_advance', 'fighter_id': n, 'target_id': 77, 'defense_building_id': 0,
                'label': 'Smoke turret', 'effects': {k: 'native' for k in ('benefit','risk','cost','inaction','uncertainty')}} for n in (1,2)]
    return {'game': {'tick': 100, 'is_paused': False}, 'map': {'id': 1, 'enemies': 1},
            'colonists': [{'id': n, 'rest': .8, 'hunger': .8} for n in (1,2)],
            'combat': {'available': True, 'colonists': pawns, 'hostiles': [], 'available_weapons': [], 'defenses': [],
                       'hostile_buildings': [{'id':77, 'active_threat':True, 'is_building':True, 'kind_def':'Turret'}], 'native_options': options}}

class CombatRetrySequenceTests(unittest.TestCase):
    def test_eight_actual_cycles_keep_other_native_worker_and_immediate_new_threat(self):
        snap, client, memory = snapshot(), Client(), {}
        with tempfile.TemporaryDirectory() as folder, patch.object(bridge, 'collect_snapshot', side_effect=lambda _: copy.deepcopy(snap)), patch.object(bridge, 'append_log'), patch('time.time', return_value=100):
            for cycle in range(8):
                snap['game']['tick'] += 1
                snap['combat']['colonists'][0]['position']['x'] += 1
                record = bridge.run_cycle(client, Agent(), apply=True, confidence=0, log_path=Path(folder)/'log', combat_memory=memory, combat_signature=director.combat_order_signature)
                memory = json.loads(json.dumps(memory))
                self.assertEqual(record['decision']['choice'], 'smoke_advance')
            tactical = [kwargs['body'] for endpoint, kwargs in client.posts if endpoint.endswith('/tactic')]
            self.assertEqual([row['fighter_ids'] for row in tactical], [[1],[1]] + [[2]]*6)
            # Material casualty is immediately a new semantic combat state.
            snap['combat']['colonists'][0]['health'] = .4
            bridge.run_cycle(client, Agent(), apply=True, confidence=0, log_path=Path(folder)/'log', combat_memory=memory, combat_signature=director.combat_order_signature)
            self.assertEqual(client.posts[-1][1]['body']['fighter_ids'], [1])
    def test_ambiguous_retry_recovers_after_sixty_seconds(self):
        snap, client, memory = snapshot(), Client(), {}
        with tempfile.TemporaryDirectory() as folder, patch.object(bridge, 'collect_snapshot', side_effect=lambda _: copy.deepcopy(snap)), patch.object(bridge, 'append_log'):
            for now in (100, 101, 110, 120, 130, 140, 150, 159):
                with patch('time.time', return_value=now):
                    bridge.run_cycle(client, Agent(), apply=True, confidence=0, log_path=Path(folder)/'log', combat_memory=memory, combat_signature=director.combat_order_signature)
            with patch('time.time', return_value=162):
                bridge.run_cycle(client, Agent(), apply=True, confidence=0, log_path=Path(folder)/'log', combat_memory=memory, combat_signature=director.combat_order_signature)
            tactics = [kwargs['body']['fighter_ids'] for endpoint, kwargs in client.posts if endpoint.endswith('/tactic')]
            self.assertEqual(tactics.count([1]), 3)
    def test_duplicate_responses_count_once_and_success_other_worker_does_not_clear_failure(self):
        memory = {}; command = {'endpoint':'/api/v1/combat/tactic', 'body':{'tactic':'smoke_advance','fighter_ids':[1],'target_pawn_id':77}}
        for _ in range(2): bridge._combat_retry_record(memory, 'same', {'choice':'smoke_advance'}, {'commands':[command, command]}, {'responses':[{},{}]})
        self.assertEqual(next(iter(memory.values()))['count'], 2)
        other = copy.deepcopy(command); other['body']['fighter_ids'] = [2]
        bridge._combat_retry_record(memory, 'same', {'choice':'smoke_advance'}, {'commands':[other]}, {'responses':[{'applied':True,'attacking_pawn_ids':[2]}]})
        self.assertEqual(next(iter(memory.values()))['count'], 2)

    def test_recovery_choices_survive_failed_attack_and_malformed_memory(self):
        snap = snapshot(); memory = {'bad': {'count': 2, 'until': 'bad'}}
        commands = [{'endpoint': '/api/v1/combat/tactic', 'body': {'tactic': choice, 'target_pawn_id': 77, 'fighter_ids': [1]}}
                    for choice in ('withdraw_and_regroup', 'civilian_retreat', 'emergency_self_tend')]
        for cycle in range(2):
            bridge._combat_retry_record(memory, 'same', {'choice': 'withdraw_and_regroup'}, {'commands': commands}, {'responses': [{}, {}, {}]})
        bridge._combat_retry_prepare(snap, memory, 'same')
        self.assertNotIn('bad', memory)
        self.assertNotIn('withdraw_and_regroup', snap['_combat_blocked_choices'])
        self.assertNotIn('civilian_retreat', snap['_combat_blocked_choices'])
        snap['game']['tick'] = 10
        bridge._combat_retry_prepare(snap, memory, 'same')
        self.assertEqual(list(memory), ['_timeline'])

    def test_actual_native_response_contract_and_missing_failed_response(self):
        for dto in ({'positioned_pawn_ids':[1]}, {'attacking_pawn_ids':[1]}, {'psycast_queued':True}):
            self.assertTrue(bridge.combat_tactical_acceptance(dto))
            for flag in (False, 'false', 0, None):
                self.assertFalse(bridge.combat_tactical_acceptance({**dto, 'applied':flag}))
                self.assertFalse(bridge.combat_tactical_acceptance({**dto, 'success':flag}))
        self.assertFalse(bridge.combat_tactical_acceptance({'positioned_pawn_ids':[], 'attacking_pawn_ids':[], 'psycast_queued':False}))
        command = {'endpoint':'/api/v1/combat/tactic', 'body':{'tactic':'focus_fire','fighter_ids':[1],'target_pawn_id':77}}
        memory = {}
        for _ in range(2):
            bridge._combat_retry_record(memory, 'same', {'choice':'focus_fire'}, {'commands':[command]}, {'failed_command_index':0,'responses':[]})
        self.assertEqual(next(iter(memory.values()))['count'], 2)
    def test_standard_focus_fire_partial_acceptance_preserves_other_fighter(self):
        snap, client, memory = snapshot(), Client(), {}
        snap['combat']['native_options'] = []
        snap['combat']['hostile_buildings'] = []
        snap['combat']['hostiles'] = [{'id':77, 'health':1, 'has_ranged_weapon':True, 'weapon_range':25,
            'current_job':'AttackStatic','distance_to_nearest_opponent':20,'position':{'x':20,'z':1}}]
        class Focus(Agent):
            def predict(self, state, questions):
                key, question = next(iter(questions.items()))
                criteria = question['criteria']; choice = 'focus_fire' if 'focus_fire' in criteria else next(iter(criteria))
                return {'answers': {key: {'choice':choice, 'confidence':1}}}
        with tempfile.TemporaryDirectory() as folder, patch.object(bridge, 'collect_snapshot', side_effect=lambda _: copy.deepcopy(snap)), patch.object(bridge, 'append_log'), patch('time.time', return_value=100):
            for cycle in range(8):
                record = bridge.run_cycle(client, Focus(), apply=True, confidence=0, log_path=Path(folder)/'log', combat_memory=memory, combat_signature=director.combat_order_signature)
                self.assertEqual(record['decision']['choice'], 'focus_fire')
                memory = json.loads(json.dumps(memory))
        tactics = [kwargs['body']['fighter_ids'] for endpoint, kwargs in client.posts if endpoint.endswith('/tactic') and kwargs['body'].get('tactic') == 'focus_fire']
        self.assertEqual(tactics, [[1,2],[1,2]] + [[2]]*6)

    def test_malformed_mixed_dto_fields_are_rejected_without_concatenation_error(self):
        command = {'endpoint':'/api/v1/combat/tactic', 'body':{'tactic':'focus_fire','fighter_ids':[1],'target_pawn_id':77}}
        for dto in ({'positioned_pawn_ids':[1], 'attacking_pawn_ids':'bad'}, {'positioned_pawn_ids':[True]}, {'attacking_pawn_ids':[0]}, {'psycast_queued':'false'}):
            self.assertFalse(bridge.combat_tactical_acceptance(dto))
            memory = {}
            bridge._combat_retry_record(memory, 'same', {'choice':'focus_fire'}, {'commands':[command]}, {'responses':[dto]})
            self.assertEqual(next(iter(memory.values()))['count'], 1)
    def test_eight_actual_recovery_cycles_keep_real_retreat_commands(self):
        snap, memory = snapshot(), {}
        snap['combat']['native_options'] = []
        snap['combat']['hostile_buildings'] = []
        snap['combat']['hostiles'] = [{'id':77, 'health':1, 'has_ranged_weapon':True, 'weapon_range':25,
            'current_job':'AttackStatic','distance_to_nearest_opponent':20,'position':{'x':20,'z':1}}]
        class Retreat(Agent):
            def predict(self, state, questions):
                key, question = next(iter(questions.items()))
                criteria = question['criteria']; choice = 'withdraw_and_regroup' if 'withdraw_and_regroup' in criteria else next(iter(criteria))
                return {'answers': {key: {'choice':choice, 'confidence':1}}}
        class Denied(Client):
            def post(self, endpoint, **kwargs):
                self.posts.append((endpoint, kwargs)); return {'positioned_pawn_ids': [], 'attacking_pawn_ids': [], 'psycast_queued':False}
        client = Denied()
        with tempfile.TemporaryDirectory() as folder, patch.object(bridge, 'collect_snapshot', side_effect=lambda _: copy.deepcopy(snap)), patch.object(bridge, 'append_log'), patch('time.time', return_value=100):
            for cycle in range(8):
                record = bridge.run_cycle(client, Retreat(), apply=True, confidence=0, log_path=Path(folder)/'log', combat_memory=memory, combat_signature=director.combat_order_signature)
                self.assertEqual(record['decision']['choice'], 'withdraw_and_regroup')
                commands = [command for command in record['action']['commands'] if command['endpoint'].endswith('/tactic') and command['body']['tactic'] == 'withdraw_and_regroup']
                self.assertTrue(commands)
                self.assertTrue(commands[0]['body']['fighter_ids'])
                memory = json.loads(json.dumps(memory))

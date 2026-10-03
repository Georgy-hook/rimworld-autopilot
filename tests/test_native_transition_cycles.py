import copy
import json
import unittest
from unittest.mock import patch
import colony_sessions as sessions
import colony_specialists as specialists
import colony_progression as progression

class Client:
    def __init__(self, context, result):
        self.context, self.result, self.posts = context, result, []
    def get(self, path, **kwargs):
        if path.endswith('/windows'): return []
        return copy.deepcopy(self.context)
    def post(self, path, **kwargs):
        self.posts.append((path, kwargs)); return copy.deepcopy(self.result)

class Agent:
    def predict(self, state, questions):
        key, question = next(iter(questions.items()))
        choice = next(k for k in question['criteria'] if k not in ('cancel', 'defer'))
        return {'answers': {key: {'choice': choice}}}

class CycleTests(unittest.TestCase):
    def target_cycles(self, result):
        context = {'active': True, 'session_id': 10, 'map_id': 1, 'effect_identity': 'heal',
                   'options': [{'key': 'pawn:9', 'target_id': 9, 'kind': 'pawn', 'x': 1, 'z': 1, 'clinical': {'health': .8, 'bleeding_rate': .1}}]}
        selected = {'session_id': 10, 'map_id': 1, 'target_id': 9, 'x': 1, 'z': 1, 'cancel': False}
        client, memory = Client(context, result), {}
        with patch.object(sessions, 'target_choice', wraps=sessions.target_choice) as choose, patch.object(sessions.time, 'time', return_value=100):
            for cycle in range(8):
                client.context['options'][0].update(x=cycle + 1, mood=.5 + cycle/100)
                client.context['options'][0]['clinical']['bleeding_rate'] = .1 + cycle/1000
                client.context['options'][0]['clinical']['pain'] = .1 + cycle/1000
                record = sessions.run_pending(client, Agent(), {'game': {'tick': cycle}}, memory)
                memory = json.loads(json.dumps(memory))
                if cycle: self.assertFalse(record['blocks_development'])
            self.assertEqual(len(client.posts), 1)
            self.assertEqual(choose.call_count, 1)
            client.context['options'][0]['clinical']['health'] = .4
            sessions.run_pending(client, Agent(), {}, memory)
            self.assertEqual(choose.call_count, 2)
        return client, memory
    def test_accepted_unchanged_target_and_urgency(self): self.target_cycles({'applied': True})
    def test_invalid_target_and_urgency(self): self.target_cycles({'applied': False, 'reason': 'invalid_target'})
    def test_unknown_target_recovers_occasionally(self):
        client, memory = self.target_cycles({})
        selected = {'session_id': 10, 'map_id': 1, 'target_id': 9, 'x': 8, 'z': 1, 'cancel': False}
        with patch.object(sessions.time, 'time', return_value=161), patch.object(sessions, 'target_choice', return_value=(selected, {})):
            sessions.run_pending(client, None, {}, memory)
        self.assertEqual(len(client.posts), 3)
    def test_progression_accepted_replayed_world_stage(self):
        context = {'world_targeting': {'active': True, 'session': 1, 'options': [{'operation': 'choose', 'tile_id': 8}]}}
        client, memory = Client(context, 'world_target_chosen'), {}
        with patch.object(progression, 'collect', side_effect=lambda *a: copy.deepcopy(client.context)):
            for cycle in range(8):
                snap = {'map': {'id': 1}, 'game': {'tick': cycle}, 'development': {'progression': copy.deepcopy(context)}}
                progression.prepare(snap, memory)
                rows = progression.ending_options(snap['development']['progression'])
                if cycle == 0:
                    selected, _ = progression.choose(Agent(), {}, 'progression_ending', snap)
                    progression.execute(client, snap, memory, 'progression_ending', selected)
                else: self.assertNotIn('world_0', rows)
                memory = json.loads(json.dumps(memory))
            self.assertEqual(len(client.posts), 1)
            context['world_targeting']['session'] = 2
            snap['development']['progression'] = copy.deepcopy(context)
            progression.prepare(snap, memory)
            self.assertIn('world_0', progression.ending_options(snap['development']['progression']))
    def test_specialist_accepted_configuration_unchanged(self):
        native = {'available': True, 'configuring': True, 'session_id': 3, 'map_id': 1,
                  'can_begin': True, 'configuration': {'roles': []}, 'choices': []}
        context = {'rituals': native}
        client, memory = Client(context, 'ritual_begin_requested'), {}
        with patch.object(specialists, 'collect', side_effect=lambda *a: copy.deepcopy(client.context)):
            for cycle in range(8):
                snap = {'map': {'id': 1}, 'game': {'tick': cycle}, 'development': {'specialists': copy.deepcopy(context)}}
                specialists.prepare(snap, memory)
                rows = snap['development']['specialists']['options']['specialists_ritual']
                if cycle == 0:
                    selected, _ = specialists.choose(Agent(), {}, 'specialists_ritual', snap)
                    specialists.execute(client, snap, memory, 'specialists_ritual', selected)
                else: self.assertNotIn('begin', rows)
                memory = json.loads(json.dumps(memory))
            self.assertEqual(len(client.posts), 1)
            context['rituals']['session_id'] = 4
            snap['development']['specialists'] = copy.deepcopy(context)
            specialists.prepare(snap, memory)
            self.assertIn('begin', snap['development']['specialists']['options']['specialists_ritual'])

    def test_stale_readback_waits_without_dispatch_then_new_session_bypasses(self):
        context = {'active': True, 'session_id': 10, 'map_id': 1, 'options': [{'key': 'pawn:9', 'kind': 'pawn', 'target_id': 9, 'x': 1, 'z': 1}]}
        class Stale(Client):
            def get(self, path, **kwargs):
                row = super().get(path, **kwargs)
                if path.endswith('/targeting'):
                    self.reads = getattr(self, 'reads', 0) + 1
                    if self.reads % 2 == 0: row['session_id'] += 1
                return row
        client, memory = Stale(context, {'applied': True}), {}
        with patch.object(sessions.time, 'time', return_value=100):
            for cycle in range(8):
                record = sessions.run_pending(client, Agent(), {}, memory)
                self.assertFalse(record['result']['applied'])
                memory = json.loads(json.dumps(memory))
            self.assertEqual(client.posts, [])
            client.context['session_id'] = 20
            record = sessions.run_pending(client, Agent(), {}, memory)
            self.assertEqual(record['mode'], 'native-target')
    def test_modal_replayed_begin_wait_remains_blocking(self):
        context = {'rituals': {'available': True, 'configuring': True, 'session_id': 3, 'map_id': 1,
                  'can_begin': True, 'configuration': {'roles': []}, 'choices': []}}
        class Modal(Client):
            def get(self, path, **kwargs):
                if path.endswith('/windows'): return [{'window_id': 3, 'window_type': 'Dialog_BeginRitual', 'force_pause': True}]
                return super().get(path, **kwargs)
        client, memory = Modal(context, 'ritual_begin_requested'), {}
        with patch.object(specialists, 'collect', side_effect=lambda *a: copy.deepcopy(context)):
            for cycle in range(8):
                record = sessions.run_pending(client, Agent(), {'map': {'id': 1}, 'game': {'tick': cycle}}, memory)
                self.assertTrue(record['blocks_development'])
                memory = json.loads(json.dumps(memory))
            self.assertEqual(len(client.posts), 1)

    def test_readiness_order_cell_identity_and_critical_bleed(self):
        first = {'options': [{'kind': 'pawn', 'target_id': 1, 'clinical': {'bleeding_rate': .1}}, {'kind': 'cell', 'position': {'x': 2, 'z': 3}}]}
        reordered = copy.deepcopy(first); reordered['options'].reverse()
        reordered['options'][1]['clinical']['bleeding_rate'] = .11
        self.assertEqual(sessions.transition_signature(first), sessions.transition_signature(reordered))
        reordered['options'][1]['clinical']['bleeding_rate'] = 2
        self.assertNotEqual(sessions.transition_signature(first), sessions.transition_signature(reordered))
        reordered = copy.deepcopy(first); reordered['options'][1]['position']['x'] = 4
        self.assertNotEqual(sessions.transition_signature(first), sessions.transition_signature(reordered))
        reordered = copy.deepcopy(first); reordered['options'][0]['target_id'] = 10
        self.assertNotEqual(sessions.transition_signature(first), sessions.transition_signature(reordered))
    def test_memory_validation_bounded_persistence_and_rollback(self):
        state = {'attempts': {'bad': {'until': 'bad', 'readiness': 'x', 'status': 'unknown'}}}
        memory = sessions.transition_memory(state, 'attempts', {'game': {'tick': 100}})
        self.assertEqual(memory, {})
        for number in range(200): sessions.transition_record(memory, str(number), 'state', {'applied': True})
        self.assertLessEqual(len(memory), 128)
        state = json.loads(json.dumps(state))
        self.assertTrue(sessions.transition_wait(state['attempts'], '199', 'state'))
        memory = sessions.transition_memory(state, 'attempts', {'game': {'tick': 50}})
        self.assertEqual(memory, {})

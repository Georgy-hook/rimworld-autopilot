import copy
from contextlib import ExitStack
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).parents[1]))
import colony_director as d


class MainCareDevelopmentReplayTests(unittest.TestCase):
    def replay(self, *, downed=False, critical_cycle=None, start_without_job=False):
        def pawn(i):
            return dict(id=i, name=str(i), health=1, rest=1, hunger=1,
                        skills={'Construction': {'level': 10}},
                        work_priorities={'Construction': {'priority': 2, 'disabled': False}})
        snapshot = {'game': {'tick': 184175, 'is_paused': False},
                    'map': {'id': 1, 'enemies': 0},
                    'colonists': [pawn(361), pawn(355), pawn(358), pawn(400)],
                    'combat': {'colonists': [
                        {'id': 361, 'current_job': 'TendPatient', 'current_job_target_id': 355},
                        {'id': 355, 'tendable_now': True, 'is_downed': downed, 'bleeding_rate': 0},
                        {'id': 358, 'current_job': 'FinishFrame'}, {'id': 400}], 'hostiles': []},
                    'development': {'cold_threat': {'outside_c': -8}}}
        snapshot['colonists'][3]['skills']['Construction']['level'] = 0
        clock = [100.0]
        cycle = [0]
        posts = []
        client = Mock()
        client.get.return_value = []
        def post(endpoint, **kw):
            posts.append((cycle[0], endpoint, kw))
            return {'applied': True}
        client.post.side_effect = post
        def collect(_):
            cycle[0] += 1
            if cycle[0] > 8:
                raise KeyboardInterrupt
            clock[0] = 100 + (cycle[0] - 1) * 10
            row = copy.deepcopy(snapshot)
            row['game']['tick'] += (cycle[0] - 1) * 4500
            if start_without_job and cycle[0] == 1:
                row['combat']['colonists'][0]['current_job'] = 'Wander'
            if critical_cycle and cycle[0] >= critical_cycle:
                row['combat']['colonists'][2].update(tendable_now=True, bleeding_rate=2, is_downed=True)
                row['colonists'][2].update(downed=True, bleeding_rate=2)
            current[0] = row
            return row
        current = [snapshot]
        care_calls = []
        def care(client, agent, row, log, **kw):
            care_calls.append((cycle[0], kw))
            row['combat']['colonists'][0].update(current_job='TendPatient', current_job_target_id=355)
            return {'timestamp': 'replay', 'decision': {'choice': 'tend_colonist'},
                    'result': {'applied': True}}
        def development(client, *args, **kw):
            # Execute the real priority selector and readback. A busy doctor and
            # actual patient outrank the free builder but must never be selected.
            with patch.object(d.bridge, 'normalize_colonists', return_value=[
                    {**p, 'work_priorities': {'Construction': {'priority': 1}}}
                    for p in current[0]['colonists']]):
                result = d.prioritize(client, current[0], 'Construction')
            return {'timestamp': 'replay', 'decision': {'choice': 'prioritize_construction'}, 'result': result}
        with tempfile.TemporaryDirectory() as td, ExitStack() as stack:
            args = d.parser().parse_args(['--state', str(Path(td)/'state.json'),
                '--log', str(Path(td)/'decisions.jsonl'), '--pid-file', str(Path(td)/'pid'),
                '--runtime-status', str(Path(td)/'runtime.json')])
            stack.enter_context(patch.object(d, 'parser', return_value=Mock(parse_args=Mock(return_value=args))))
            # Windows singleton is mocked; no process/game/model is launched.
            if d.os.name == 'nt':
                stack.enter_context(patch.object(d.ctypes.windll.kernel32, 'CreateMutexW', return_value=0))
                stack.enter_context(patch.object(d.ctypes.windll.kernel32, 'GetLastError', return_value=0))
            stack.enter_context(patch.object(d.bridge, 'RimApiClient', return_value=client))
            stack.enter_context(patch.object(d.bridge, 'load_agent', return_value=object()))
            stack.enter_context(patch.object(d.bridge, 'collect_snapshot', side_effect=collect))
            stack.enter_context(patch.object(d.bridge, 'safe_get', return_value={}))
            stack.enter_context(patch.object(d.time, 'monotonic', side_effect=lambda: clock[0]))
            stack.enter_context(patch.object(d.time, 'sleep'))
            stack.enter_context(patch.object(d.colony_sessions, 'bind_campaign'))
            stack.enter_context(patch.object(d.colony_sessions, 'terminal_result', return_value=None))
            stack.enter_context(patch.object(d.colony_sessions, 'run_pending', return_value=None))
            for name in ('run_caravan_trade_cycle', 'run_window_cycle', 'run_letter_cycle',
                         'run_rescue_site_cycle', 'run_event_cycle'):
                stack.enter_context(patch.object(d, name, return_value=None))
            stack.enter_context(patch.object(d, 'get_ancient_danger', return_value={}))
            stack.enter_context(patch.object(d, 'run_post_combat_care_cycle', side_effect=care))
            stack.enter_context(patch.object(d, 'run_development_cycle', side_effect=development))
            stack.enter_context(patch.object(d, 'post_combat_care_options', side_effect=lambda row, *a, **kw:
                {'critical': {'kind': 'tend', 'patient_critical': True, 'patient_id': 358}}
                if row['combat']['colonists'][2].get('is_downed') else {}))
            self.assertEqual(d.main(), 0)
        orders = [p for p in posts if p[1] == '/api/v1/colonist/work-priority']
        self.assertEqual(len(orders), 8)
        for i, _, kw in orders:
            self.assertEqual(kw['body']['id'], 400 if critical_cycle and i >= critical_cycle else 358)
        return care_calls

    def test_active_tending_allows_eight_development_cycles(self):
        self.assertEqual(self.replay(), [])

    def test_downed_patient_being_tended_allows_eight_cycles(self):
        self.assertEqual(self.replay(downed=True), [])

    def test_recent_accepted_care_does_not_hold_other_workers(self):
        self.assertEqual([i for i, _ in self.replay(start_without_job=True)], [1])

    def test_explicit_priority_never_reassigns_care_actor_or_patient(self):
        row = {'colonists': [{'id': i} for i in (1, 2, 3)],
               'combat': {'colonists': [{'id': 1, 'current_job': 'FeedPatient',
                                        'current_job_target_id': 99, 'care_target_id': 2}]}}
        client = Mock()
        for i in (1, 2):
            self.assertFalse(d.prioritize(client, row, 'Construction', i)['applied'])
        client.post.assert_not_called()
        self.assertEqual(d.active_care_pawn_ids(row), {'1', '2'})

    def test_normalized_care_job_is_reserved_without_combat_row(self):
        row = {'colonists': [{'id': 1, 'current_job': 'TendPatient',
                             'current_job_target_id': 2}, {'id': 2}], 'combat': {}}
        self.assertEqual(d.active_care_pawn_ids(row), {'1', '2'})

    def test_baby_and_deathrest_jobs_are_reserved(self):
        row = {'colonists': [{'id': i} for i in (1, 2, 3)],
               'combat': {'colonists': [{'id': 1, 'current_job': 'BottleFeedBaby',
                                        'care_target_id': 2},
                                       {'id': 3, 'current_job': 'Deathrest'}]}}
        self.assertEqual(d.active_care_pawn_ids(row), {'1', '2', '3'})

    def test_new_critical_patient_bypasses_active_care_wait(self):
        calls = self.replay(critical_cycle=4)
        self.assertIn(4, [i for i, _ in calls])
        self.assertTrue(all(kw.get('focus_downed') for _, kw in calls))


if __name__ == '__main__':
    unittest.main()

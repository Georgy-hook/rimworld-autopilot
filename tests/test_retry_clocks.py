import copy
import importlib
import json
import math
import unittest
from unittest.mock import patch
import colony_retry as retry


class RetryClockTests(unittest.TestCase):
    @patch('colony_retry.time.time', return_value=100)
    def test_both_clocks_expire_json_restart_and_exact_boundaries(self, clock):
        record = retry.failure_record(10000, seconds=15)
        restored = json.loads(json.dumps(record))
        importlib.reload(retry)  # No process-local state can establish or clear the deadline.
        self.assertTrue(retry.recent(restored, 13600, 60, now=102))
        self.assertTrue(retry.recent(restored, 10001, 60, now=120))
        self.assertTrue(retry.recent(restored, 13600, 60, now=114.999))
        self.assertFalse(retry.recent(restored, 10060, 60, now=115))
        self.assertEqual(restored, record)
    def test_malformed_and_clock_or_tick_rollback_invalidates(self):
        base = {'tick': 10000, 'retry_started_at': 100, 'retry_until': 130}
        malformed = [None, [], 'bad', {}, {'tick': True}, {'tick': '10000'},
                     {**base, 'tick': 10**1000}, {**base, 'retry_until': 10**1000},
                     {**base, 'retry_started_at': math.nan}, {**base, 'retry_until': math.inf},
                     {**base, 'retry_until': 99}, {**base, 'retry_until': 401},
                     {'tick': 10000, 'retry_until': 130}, {'tick': 10000, 'retry_started_at': 100}]
        for record in malformed:
            with self.subTest(record=repr(record)[:100]):
                self.assertFalse(retry.recent(record, 13600, 60, now=102))
        self.assertFalse(retry.recent(base, 9999, 60, now=102))
        self.assertFalse(retry.recent(base, 13600, 60, now=99.9))
        self.assertFalse(retry.recent(base, 13600, 10**1000, now=102))
        self.assertFalse(retry.recent(base, 13600, 60, now=math.nan))
    def test_success_defer_and_legacy_records_keep_game_policy(self):
        self.assertTrue(retry.recent({'tick': 10000}, 10059, 60, now=1000000))
        self.assertFalse(retry.recent({'tick': 10000}, 10060, 60, now=1))


class ModuleFailureFloorTests(unittest.TestCase):
    def assert_floor(self, clock, snapshot, state, prepare, keys, failed, alternative, seconds):
        restored = json.loads(json.dumps(state))
        snapshot = copy.deepcopy(snapshot)
        snapshot['game']['tick'] += 3600
        clock.return_value = 102
        prepare(snapshot, restored)
        self.assertNotIn(failed, keys(snapshot))
        self.assertIn(alternative, keys(snapshot))
        # A fresh snapshot/state object after restart still obeys the persisted deadline.
        restored = json.loads(json.dumps(restored)); snapshot = copy.deepcopy(snapshot)
        clock.return_value = 100 + seconds
        prepare(snapshot, restored)
        self.assertIn(failed, keys(snapshot))
        self.assertIn(alternative, keys(snapshot))
    @patch('colony_retry.time.time', return_value=100)
    def test_resilience_failure_floor_preserves_other_patient(self, clock):
        import colony_resilience as m
        import test_resilience as fixtures
        fixture = fixtures.ResilienceTests(); fixture.setUp()
        s = fixture.snapshot; r = fixture.row
        s['development']['resilience']['options'].append({**r, 'target_id': 99})
        state = {}; m.execute(fixtures.Client([]), s, state, 'resilience_rescue', r)
        self.assert_floor(clock, s, state, m.prepare,
                          lambda s: {r['target_id'] for r in s['development']['resilience']['plans']['resilience_rescue'].values()}, 2, 99, 15)
    @patch('colony_retry.time.time', return_value=100)
    def test_society_failure_floor_preserves_other_person(self, clock):
        import colony_society as m
        import test_society as fixtures
        s = fixtures.snapshot(); person = copy.deepcopy(s['development']['society']['people'][0])
        person['pawn_id'] = 99; s['development']['society']['people'].append(person)
        m.prepare(s, {}); r = next(r for r in s['development']['society']['options']['society_free_time'].values() if r['pawn_id'] == 1)
        state = {}; m.execute(fixtures.Client({'people': []}), s, state, 'society_free_time', m._payload(r))
        self.assert_floor(clock, s, state, m.prepare,
                          lambda s: {r['pawn_id'] for r in s['development']['society']['options']['society_free_time'].values()}, 1, 99, 15)
    @patch('colony_retry.time.time', return_value=100)
    def test_production_failure_floor_preserves_other_building(self, clock):
        import colony_production as m
        import test_production as fixtures
        fixture = fixtures.IndependentProductionTests(); s = fixture.snapshot(); state = {}
        m.execute(fixture.client(s, 'POST'), s, state, 'production_utilities', {'production_policy': '2:switch_off'})
        self.assert_floor(clock, s, state, m.prepare, lambda s: s['development']['production']['options'],
                          '2:switch_off', '9:switch_off', 30)
    @patch('colony_retry.time.time', return_value=100)
    def test_sustenance_failure_floor_preserves_other_animal(self, clock):
        import colony_sustenance as m
        import test_sustenance as fixtures
        fixture = fixtures.SustenanceHistoryTests(); fixture.setUp(); s = fixture.s; state = {}
        fixture.execute(state, client=fixtures.Client({'options': []}))
        self.assert_floor(clock, s, state, m.prepare,
                          lambda s: m.options(s['development']['sustenance'], 'sustenance_animal_welfare'),
                          fixture.plans[0]['key'], fixture.plans[1]['key'], 30)
    @patch('colony_retry.time.time', return_value=100)
    def test_specialists_failure_floor_preserves_other_mode(self, clock):
        import colony_specialists as m
        import test_specialists as fixtures
        s = fixtures.snapshot(); m.prepare(s, {})
        plans = s['development']['specialists']['options']['specialists_mech_mode']
        failed, alternative = list(plans)[:2]; selected = m._payload(plans[failed], 'specialists_mech_mode'); state = {}
        m.execute(fixtures.Client(s['development']['specialists'], applied=False), s, state, 'specialists_mech_mode', selected)
        self.assert_floor(clock, s, state, m.prepare,
                          lambda s: s['development']['specialists']['options']['specialists_mech_mode'], failed, alternative, 30)
    @patch('colony_retry.time.time', return_value=100)
    def test_affordances_failure_floor_preserves_other_target(self, clock):
        import colony_affordances as m
        import test_affordances as fixtures
        r = fixtures.option(); alternative = {**fixtures.option(1), 'target_id': 99}
        s = {'map': {'id': 1}, 'game': {'tick': 10000}, 'development': {'affordances': {'options': [r, alternative]}}}
        class Client(fixtures.Client):
            def post(self, *args, **kwargs): return {'applied': False}
        state = {}; client = Client({'/api/v1/affordances/context': {'options': [r, alternative]}})
        m.execute(client, s, state, 'affordances_ability', {**r, 'decision_evidence': m.evidence(r)})
        self.assert_floor(clock, s, state, m.prepare,
                          lambda s: {r['target_id'] for r in s['development']['affordances']['candidates']['affordances_ability'].values()}, 1, 99, 30)

if __name__ == '__main__': unittest.main()

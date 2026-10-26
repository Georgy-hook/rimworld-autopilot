import importlib.util
from pathlib import Path
import threading
import unittest

spec = importlib.util.spec_from_file_location('lab_finalization', Path(__file__).parent/'native_combat_lab/combat_lab_finalization.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)

def healthy():
    return dict(tick=100, enemies=[], captive=None,
                allies=[dict(id=1, spawned=True, dead=False, downed=False, drafted=False, bleeding=0, in_bed=False)])

class FinalizationTests(unittest.TestCase):
    def test_missing_originals_and_empty_export_cannot_close(self):
        guard=f.FinalizationGuard({1,2})
        self.assertIsNone(guard.try_close(healthy, {}))
        state=healthy(); state['allies']=[]
        self.assertFalse(f.recovered_outcome(state, {}))
        guard=f.FinalizationGuard({1},99)
        self.assertIsNone(guard.try_close(healthy, {}))

    def test_open_write_forwards_exact_result(self):
        guard=f.FinalizationGuard(); result=object()
        self.assertIs(guard.run_write('/real', lambda:result), result)

    def test_inflight_draft_cannot_be_closed_as_undrafted(self):
        guard=f.FinalizationGuard(); state=healthy(); entered=threading.Event(); release=threading.Event()
        def write():
            entered.set(); release.wait(2); state['allies'][0]['drafted']=True
        thread=threading.Thread(target=lambda:guard.run_write('/draft', write)); thread.start()
        self.assertTrue(entered.wait(2))
        self.assertIsNone(guard.try_close(lambda:state, {}))
        release.set(); thread.join(2); self.assertFalse(thread.is_alive())
        self.assertIsNone(guard.try_close(lambda:state, {}))
        self.assertFalse(guard.closed)

    def test_close_blocks_new_side_effect_without_fake_success(self):
        guard=f.FinalizationGuard(); state=healthy(); called=[]
        self.assertIs(guard.try_close(lambda:state, {}), state)
        with self.assertRaises(f.LogicalOutcomeClosed):
            guard.run_write('/draft', lambda:called.append(True))
        self.assertEqual(called, [])

    def test_quiet_window_requires_both_clocks_and_resets(self):
        guard=f.FinalizationGuard(); state=healthy()
        self.assertFalse(guard.observe(state, {}, now=0))
        state['tick']=300; self.assertFalse(guard.observe(state, {}, now=1))
        self.assertTrue(guard.observe(state, {}, now=2))
        state['allies'][0]['bleeding']=1
        self.assertFalse(guard.observe(state, {'require_defenders_stabilized':True}, now=3))
        self.assertIsNone(guard.window)

    def test_monitor_pause_remains_real_after_director_closed(self):
        calls=[]
        class Client:
            def post(self, endpoint): calls.append(endpoint); return endpoint
        guard=f.FinalizationGuard(); restore=guard.install(Client)
        try:
            guard.try_close(healthy, {})
            with self.assertRaises(f.LogicalOutcomeClosed):Client().post('/draft')
            thread=threading.Thread(target=lambda:Client().post('/native-pause')); thread.start();thread.join(2)
            self.assertEqual(calls, ['/native-pause'])
        finally:restore()
        self.assertEqual(Client().post('/ordinary-unwrapped'), '/ordinary-unwrapped')

    def test_terminal_stop_blocks_next_main_read_and_write_without_async_interrupt(self):
        calls=[]
        class Client:
            def get(self, endpoint): calls.append(endpoint); return endpoint
            def post(self, endpoint): calls.append(endpoint); return endpoint
        guard=f.FinalizationGuard(); restore=guard.install(Client)
        try:
            self.assertEqual(Client().get('/open-read'), '/open-read')
            self.assertEqual(Client().post('/open-write'), '/open-write')
            guard.request_director_stop()
            with self.assertRaises(f.LogicalOutcomeClosed):Client().get('/next-read')
            with self.assertRaises(f.LogicalOutcomeClosed):Client().post('/next-write')
            thread=threading.Thread(target=lambda:Client().post('/real-monitor-pause'))
            thread.start();thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(calls, ['/open-read','/open-write','/real-monitor-pause'])
        finally:restore()
        self.assertEqual(Client().get('/ordinary-unwrapped'), '/ordinary-unwrapped')

    def test_terminal_stop_does_not_interrupt_or_undo_inflight_write(self):
        guard=f.FinalizationGuard(); entered=threading.Event(); finish=threading.Event(); result=[]
        def actual_write():
            entered.set();finish.wait(2);result.append('committed');return 'native-response'
        thread=threading.Thread(target=lambda:result.append(guard.run_write('/inflight', actual_write)))
        thread.start();self.assertTrue(entered.wait(2))
        guard.request_director_stop();finish.set();thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, ['committed','native-response'])
        with self.assertRaises(f.LogicalOutcomeClosed):guard.run_write('/later', lambda:result.append('bad'))

if __name__=='__main__':unittest.main()

"""Close a laboratory outcome between actual director writes, without fabricating an ACK.

This is measurement shutdown coordination. While open it forwards every request
unchanged. A closed result blocks a later main-thread write by interrupting the
director; the monitor can still pause the verified native instance. It does not
undo a committed order or change the final native outcome gates.
"""
import threading
import time


class LogicalOutcomeClosed(KeyboardInterrupt):
    pass


def recovered_outcome(state, case):
    if not state['allies']:
        return False
    if state.get('unexpected_player_ids') or state.get('unexpected_threat_ids'):
        return False
    if any(p['spawned'] and not p['dead'] and not p['downed'] for p in state['enemies']):
        return False
    if any(p['drafted'] or p['dead'] or not p['spawned'] for p in state['allies']):
        return False
    captive = state.get('captive')
    if captive and (not captive['spawned'] or captive['dead']):
        return False
    if case.get('require_captive_tended'):
        if not captive or not captive['bleeding'] <= 0 or captive['downed'] and not captive.get('in_bed'):
            return False
    if case.get('require_defenders_stabilized'):
        if any(not p['bleeding'] <= 0 or p['downed'] and not p.get('in_bed') for p in state['allies']):
            return False
    return True


class FinalizationGuard:
    def __init__(self, expected_allied_ids=None, expected_captive_id=None):
        self.lock = threading.RLock()
        self.closed = False
        self.closed_tick = None
        self.blocked_endpoints = []
        self.busy_reviews = 0
        self.rejected_fresh_reviews = 0
        self.window = None
        self.expected_allied_ids = set(expected_allied_ids) if expected_allied_ids is not None else None
        self.expected_captive_id = expected_captive_id
        self.stop_requested = threading.Event()

    def request_director_stop(self):
        # Cooperative cancellation after an observed terminal condition. A
        # pending API call is not undone; subsequent main-thread I/O stops.
        # No asynchronous KeyboardInterrupt may arrive during result cleanup.
        self.stop_requested.set()

    def recovered(self, state, case):
        if self.expected_allied_ids is not None and {p.get('id') for p in state['allies']} != self.expected_allied_ids:
            return False
        if self.expected_captive_id is not None and (state.get('captive') or {}).get('id') != self.expected_captive_id:
            return False
        return recovered_outcome(state, case)

    def observe(self, state, case, now=None):
        now = time.monotonic() if now is None else now
        if not self.recovered(state, case):
            self.window = None
            return False
        if self.window is None:
            self.window = (now, state['tick'])
        # An additional observed quiet window tightens the old single-sample
        # closure. It neither advances ticks nor gives a treatment order.
        return now - self.window[0] >= 2.0 and state['tick'] - self.window[1] >= 120

    def run_write(self, endpoint, invoke):
        with self.lock:
            if self.closed or self.stop_requested.is_set():
                self.blocked_endpoints.append(endpoint)
                raise LogicalOutcomeClosed()
            return invoke()

    def try_close(self, read_fresh, case):
        if not self.lock.acquire(blocking=False):
            self.busy_reviews += 1
            return None
        try:
            fresh = read_fresh()
            if not self.recovered(fresh, case):
                self.rejected_fresh_reviews += 1
                self.window = None
                return None
            self.closed = True
            self.closed_tick = fresh['tick']
            return fresh
        finally:
            self.lock.release()

    def install(self, client_type):
        original = client_type.post
        original_get = getattr(client_type, 'get', None)
        main_thread = threading.current_thread()
        guard = self
        def guarded(client, endpoint, *args, **kwargs):
            if threading.current_thread() is main_thread:
                return guard.run_write(endpoint, lambda: original(client, endpoint, *args, **kwargs))
            return original(client, endpoint, *args, **kwargs)
        client_type.post = guarded
        def guarded_get(client, endpoint, *args, **kwargs):
            if threading.current_thread() is main_thread and guard.stop_requested.is_set():
                raise LogicalOutcomeClosed()
            return original_get(client, endpoint, *args, **kwargs)
        if original_get is not None:
            client_type.get = guarded_get
        def restore():
            assert client_type.post is guarded
            client_type.post = original
            if original_get is not None:
                assert client_type.get is guarded_get
                client_type.get = original_get
        return restore

    def evidence(self):
        return dict(protocol='post_outcome_write_barrier_v1', closed=self.closed,
                    closing_tick=self.closed_tick, busy_reviews=self.busy_reviews,
                    rejected_fresh_reviews=self.rejected_fresh_reviews,
                    blocked_main_thread_endpoints=list(self.blocked_endpoints),
                    quiet_real_seconds=2.0, quiet_native_ticks=120,
                    terminal_stop='cooperative_main_thread_io_v2',
                    scope='Only closing coordination; no request payload or success response is substituted, and no native order is undone.')

"""Offline scheduler tests: no HTTP connection, game or model weights."""
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import colony_director as director
import colony_modules as modules


class LoopOrchestrationTests(unittest.TestCase):
    def test_bad_domain_preparation_does_not_hide_other_domains_and_can_recover(self):
        broken = SimpleNamespace(prepare=Mock(side_effect=KeyError("target_id")), ACTIONS={"production_work"})
        good = SimpleNamespace(prepare=lambda *_: ["society_care"], ACTIONS={"society_care"})
        snapshot = {"development": {"production": {"plans": {"obsolete": 99}}}}
        with patch.object(modules, "modules", return_value=(broken, good)):
            self.assertEqual(modules.prepare(snapshot, {}), ["society_care"])
            self.assertEqual(snapshot["development"]["production"], {})
            status = snapshot["development"]["module_status"]["production"]
            self.assertFalse(status["available"])
            self.assertEqual(status["phase"], "prepare")
            # Only a fresh collection makes the domain available again.
            broken.collect = lambda *_: {"options": []}
            good.collect = lambda *_: {}
            broken.prepare = lambda *_: ["production_work"]
            modules.collect(None, snapshot)
            self.assertEqual(modules.prepare(snapshot, {}), ["production_work", "society_care"])

    def test_world_read_errors_obey_backoff_before_any_map_exists(self):
        now = [1000.0]
        attempts = []
        def pending(*_args, **_kwargs):
            attempts.append(now[0])
            if len(attempts) == 3:
                raise KeyboardInterrupt()
            raise ValueError("native continuation unavailable")
        def sleep(seconds):
            now[0] += seconds
            if now[0] > 1040:
                raise AssertionError("scheduler failed to retry within bound")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            args = SimpleNamespace(pid_file=root/"director.pid", runtime_status=root/"status.json",
                log=root/"decisions.jsonl", state=root/"state.json", api_url="http://localhost:8765",
                model="mock-only", device="cpu", interval=10)
            with patch.object(director, "parser", return_value=SimpleNamespace(parse_args=lambda: args)), \
                 patch.object(director, "os", SimpleNamespace(name="offline", getpid=os.getpid)), \
                 patch.object(director, "write_runtime_status"), \
                 patch.object(director.bridge, "RimApiClient"), \
                 patch.object(director.bridge, "load_agent", return_value=object()), \
                 patch.object(director, "load_state", return_value={}), \
                 patch.object(director.bridge, "safe_get", return_value={}) as reads, \
                 patch.object(director.bridge, "append_log"), \
                 patch.object(director.colony_sessions, "run_pending", side_effect=pending), \
                 patch.object(director.time, "monotonic", side_effect=lambda: now[0]), \
                 patch.object(director.time, "sleep", side_effect=sleep):
                self.assertEqual(director.main(), 0)
            self.assertEqual(attempts, [1000.0, 1010.0, 1030.0])
            self.assertEqual(reads.call_count, 3)
            self.assertFalse(args.pid_file.exists())


if __name__ == "__main__":
    unittest.main()

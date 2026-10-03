import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import colony_director as director
from tests.test_equipment_sequence import replay_snapshot, Chooser, Orders


class DirectorOutcomeSequences(unittest.TestCase):
    def test_unexplained_empty_result_cannot_erase_failure_or_starve_next_full_cycle(self):
        source, state, client = replay_snapshot(), {}, Orders()
        memory = director.map_state_for_snapshot(state, source)
        memory.update(anchor={"x": 120, "z": 120}, growing_anchor={"x": 110, "z": 110}, starter_site_verified=True)
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(director.bridge, "collect_snapshot", side_effect=lambda c: copy.deepcopy(source)), \
                patch.object(director, "collect_development", side_effect=lambda c, s: s), \
                patch.object(director, "publish_overlay"), \
                patch.object(director, "execute_action", return_value={"applied": False, "assignments": [], "responses": []}):
            path, log = Path(folder)/"state.json", Path(folder)/"log.jsonl"
            first = director.run_development_cycle(client, Chooser(), state, path, log)
            self.assertEqual(first["decision"]["choice"], "equip_colonists")
            self.assertEqual(first["order_outcome"], "rejected")
            restored = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(director.map_state_for_snapshot(restored, source)["action_failures"]["equip_colonists"]["count"], 1)
            second = director.run_development_cycle(client, Chooser(), restored, path, log)
            self.assertNotIn("equip_colonists", second["candidates"])
            self.assertIn("build_starter_base", second["candidates"])
            self.assertNotEqual(second["decision"]["choice"], "hold_survival")

    def test_letter_unknown_not_handled_and_retry_does_not_block_other_work(self):
        class Client:
            calls = 0
            def get(self, path, **kwargs):
                return {"letters": [{"id": 17, "arrival_tick": 1000, "label": "Joiner",
                    "text": "A refugee asks to stay.", "enabled_options": ["Accept", "Reject"]}]}
            def post(self, path, **kwargs):
                self.calls += 1
                return {"success": False}
        source = {"map": {"id": 1, "resources": {"food": 35}}, "game": {"tick": 1200}, "colonists": [{"id": 1}]}
        state, client = {}, Client()
        with tempfile.TemporaryDirectory() as folder:
            first = director.run_letter_cycle(client, Chooser(), source, state, Path(folder)/"log.jsonl")
            self.assertIs(first["result"]["applied"], False)
            for cycle in range(8):
                source["game"]["tick"] += 10
                self.assertIsNone(director.run_letter_cycle(client, Chooser(), source, state, Path(folder)/"log.jsonl"))
            self.assertNotIn("17", director.map_state_for_snapshot(state, source).get("handled_letters", {}))
            self.assertEqual(client.calls, 1)

    def test_nonmodal_failed_event_yields_to_development_but_modal_wait_does_not(self):
        for result in ({"applied": False}, {}, {"applied": True}):
            self.assertFalse(director.interrupt_blocks_development({"result": result, "blocks_development": False}))
        self.assertTrue(director.interrupt_blocks_development({"mode": "native-window-wait", "quiet": True}))
        self.assertFalse(director.interrupt_blocks_development(None))

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import colony_director as d


class RescueSiteAcknowledgmentTests(unittest.TestCase):
    def run_sequence(self, first):
        snapshot = {"map": {"id": 0, "is_temp_incident_map": True}, "game": {"tick": 1000}, "combat": {"colonists": []}}
        state = {"maps": {"home": {"rescue_mission": {"site_id": 17}}}}
        client = Mock()
        client.get.return_value = {"site_id": 17, "captive_pawn_ids": [], "can_return_home": True}
        client.post.side_effect = [first, {"applied": True, "status": "returning from rescue site"}]
        with tempfile.TemporaryDirectory() as folder, patch.object(d, "overlay_language", return_value="en"), \
                patch.object(d, "show_overlay"), patch("colony_retry.time.time", return_value=100) as clock:
            args = (client, state, Path(folder)/"state.json", Path(folder)/"log.jsonl", snapshot)
            record = d.run_rescue_site_cycle(*args)
            self.assertIn("rescue_mission", state["maps"]["home"])
            self.assertNotIn("last_rescue_mission", state["maps"]["home"])
            self.assertFalse(record["result"]["applied"])
            saved = json.loads((Path(folder)/"state.json").read_text(encoding="utf-8"))
            self.assertIn("site_retry", saved["maps"]["home"]["rescue_mission"])
            snapshot["game"]["tick"] += 3600
            clock.return_value = 102
            self.assertIsNone(d.run_rescue_site_cycle(*args))
            self.assertEqual(client.post.call_count, 1)
            clock.return_value = 115
            d.run_rescue_site_cycle(*args)
            self.assertEqual(client.post.call_count, 2)
            last = state["maps"]["home"]["last_rescue_mission"]
            self.assertNotIn("completed_tick", last)
            self.assertEqual(last["completion"], "unverified")
            self.assertEqual(last["return_requested_tick"], 4600)
            self.assertNotIn("rescue_mission", state["maps"]["home"])

    def test_rejected_return_preserves_mission_then_only_acknowledges_departure(self):
        self.run_sequence({"applied": False, "reason": "route unavailable"})

    def test_lost_return_reply_remains_unknown_with_bounded_retry(self):
        self.run_sequence(d.bridge.RimApiError("POST reply lost"))

    def test_new_captive_state_reopens_failed_secure(self):
        snapshot = {"map": {"id": 0, "is_temp_incident_map": True}, "game": {"tick": 1000}, "combat": {"colonists": []}}
        state = {"maps": {"home": {"rescue_mission": {"site_id": 17}}}}
        client = Mock()
        status = {"site_id": 17, "captive_pawn_ids": [5], "can_return_home": False}
        client.get.side_effect = lambda *a, **k: status
        client.post.return_value = {"success": False, "applied": False}
        with tempfile.TemporaryDirectory() as folder, patch.object(d, "overlay_language", return_value="en"), \
                patch.object(d, "show_overlay"), patch("colony_retry.time.time", return_value=100):
            args = (client, state, Path(folder)/"state.json", Path(folder)/"log.jsonl", snapshot)
            d.run_rescue_site_cycle(*args)
            self.assertIsNone(d.run_rescue_site_cycle(*args))
            status["captive_pawn_ids"] = [6]
            client.post.return_value = {"success": True}
            d.run_rescue_site_cycle(*args)
            self.assertEqual(client.post.call_count, 2)
            self.assertTrue(state["maps"]["home"]["rescue_mission"]["site_retry"]["awaiting_observation"])
            for cycle in range(8):
                self.assertIsNone(d.run_rescue_site_cycle(*args))
            self.assertEqual(client.post.call_count, 2)
            snapshot["combat"]["colonists"] = [{"id": 1, "current_job": "ReleasePrisoner"}]
            snapshot["game"]["tick"] += 1000
            with patch("colony_retry.time.time", return_value=200):
                self.assertIsNone(d.run_rescue_site_cycle(*args))
            self.assertEqual(client.post.call_count, 2)

if __name__ == "__main__":
    unittest.main()

"""Exercise growth modal scheduling, scoped acknowledgements and observed closure."""
import copy
import pathlib
import tempfile
import unittest
from unittest import mock

import colony_director as director


class NoChoiceAgent:
    def predict(self, *_args, **_kwargs):
        raise AssertionError("One informational OK needs no inference; awards belong to Society")


class WindowClient:
    def __init__(self, windows, after=None, error=None):
        self.windows = copy.deepcopy(windows)
        self.after = copy.deepcopy(after) if after is not None else []
        self.error = error
        self.posts = []

    def get(self, endpoint):
        if endpoint != "/api/v1/ui/windows":
            raise AssertionError(endpoint)
        return copy.deepcopy(self.windows)

    def post(self, endpoint, body):
        self.posts.append((endpoint, copy.deepcopy(body)))
        if self.error:
            raise self.error
        self.windows = copy.deepcopy(self.after)
        return {"success": True}


class GrowthDialogueTests(unittest.TestCase):
    def setUp(self):
        self.window = {"window_id": 812, "window_type": "Dialog_GrowthMomentChoices",
                       "dialog_text": "Growth completed: earned trait; no awards remain.",
                       "force_pause": True, "blocks_input": True,
                       "confirmation_only": True, "enabled_options": ["ОК"]}
        self.snapshot = {"map": {"id": 0, "resources": {"food": 14}},
                         "game": {"tick": 2571140}, "colonists": [{"id": 1}]}
        self.state = {}
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.log = pathlib.Path(self.folder.name) / "decisions.jsonl"

    def run_cycle(self, client):
        return director.run_window_cycle(client, NoChoiceAgent(), self.snapshot, self.state, self.log)

    def test_acknowledgement_uses_exact_localized_callback_then_stops_repeating(self):
        client = WindowClient([self.window])
        record = self.run_cycle(client)
        self.assertEqual(client.posts, [("/api/v1/ui/window/choose", {
            "window_type": self.window["window_type"], "window_id": 812,
            "option_label": "ОК", "dialog_text": self.window["dialog_text"]})])
        self.assertTrue(record["result"]["applied"])
        self.assertEqual(record["result"]["completion"], "window_closed")
        self.assertTrue(record["decision"]["raw"]["answers"]["live_dialogue"]["resolved_without_model"])
        self.assertNotIn("defer", record["candidates"])
        self.assertIn("traits and passions remain unchanged", record["dialogue"]["option_effects"]["option_0"]["risk"])
        self.assertIsNone(self.run_cycle(client))
        self.assertEqual(len(client.posts), 1)

    def test_success_without_closure_is_unverified_and_retry_is_bounded(self):
        client = WindowClient([self.window], after=[self.window])
        with mock.patch.object(director.time, "time", return_value=100):
            first = self.run_cycle(client)
            self.assertFalse(first["result"]["applied"])
            self.assertEqual(first["result"]["completion"], "unverified")
            self.assertIsNone(self.run_cycle(client))
        with mock.patch.object(director.time, "time", return_value=161):
            client.after = []
            self.assertTrue(self.run_cycle(client)["result"]["applied"])
        self.assertEqual(len(client.posts), 2)

    def test_changed_window_is_available_during_old_window_backoff(self):
        client = WindowClient([self.window], error=director.bridge.RimApiError("Window changed"))
        with mock.patch.object(director.time, "time", return_value=100):
            self.assertFalse(self.run_cycle(client)["result"]["applied"])
            self.assertIsNone(self.run_cycle(client))
            client.windows[0]["window_id"] = 813
            client.error = None
            self.assertTrue(self.run_cycle(client)["result"]["applied"])
        self.assertEqual([body["window_id"] for _, body in client.posts], [812, 813])

    def test_awards_requiring_choices_are_left_to_society(self):
        self.window.update(confirmation_only=False, enabled_options=["OK", "Later"])
        client = WindowClient([self.window])
        self.assertIsNone(self.run_cycle(client))
        self.assertEqual(client.posts, [])

    def test_older_api_without_confirmation_flag_cannot_be_blindly_closed(self):
        del self.window["confirmation_only"]
        client = WindowClient([self.window])
        self.assertIsNone(self.run_cycle(client))
        self.assertEqual(client.posts, [])

    def test_missing_identity_or_ambiguous_buttons_cannot_be_acknowledged(self):
        for changes in ({"window_id": None}, {"enabled_options": ["OK", "OK"]},
                        {"enabled_options": []}):
            with self.subTest(changes=changes):
                window = {**self.window, **changes}
                client = WindowClient([window])
                self.assertIsNone(self.run_cycle(client))
                self.assertEqual(client.posts, [])

    def test_newer_unhandled_modal_blocks_underlying_acknowledgement(self):
        blocker = {"window_id": 900, "window_type": "Dialog_NativeChoice",
                   "force_pause": True, "blocks_input": True, "enabled_options": []}
        client = WindowClient([self.window, blocker])
        self.assertIsNone(self.run_cycle(client))
        self.assertEqual(client.posts, [])
        client.windows = [self.window]
        self.assertTrue(self.run_cycle(client)["result"]["applied"])

    def test_unrelated_replacement_window_is_retained(self):
        other = {**self.window, "window_id": 900}
        client = WindowClient([self.window], after=[other])
        self.assertTrue(self.run_cycle(client)["result"]["applied"])
        self.assertEqual(client.windows, [other])
        self.assertEqual(len(client.posts), 1)


if __name__ == "__main__":
    unittest.main()

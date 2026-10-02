import tempfile
from pathlib import Path
import unittest
from unittest import mock
import colony_director as director
import colony_growth as growth
import colony_professions as professions


class EventGrowthContracts(unittest.TestCase):
    def test_history_forward_expiry_rollback_and_json_values(self):
        history = {"current": "1000", "old": 0, "bad": "oops", "future": 1300}
        self.assertEqual(director.prune_event_history(history, 120001), {"current": 1000, "future": 1300})
        self.assertEqual(director.prune_event_history(history, 100), {"old": 0})
        self.assertEqual(director.prune_event_history([], 100), {})

    def test_rejected_result_is_not_ack_but_deliberate_defer_is(self):
        for result in ({"applied": False}, {"success": False}, {}, None):
            self.assertFalse(director.event_result_acknowledged("accept_quest", result))
        self.assertTrue(director.event_result_acknowledged("accept_quest", {"success": True}))
        self.assertFalse(director.event_result_acknowledged("accept_quest", {"success": True, "applied": False}))
        self.assertTrue(director.event_result_acknowledged("defer_quest", {"applied": False}))
        self.assertTrue(director.event_result_acknowledged("trade_now", {"applied": False, "reason": "Laya chose no sale and no purchase"}))

    def test_event_rejected_then_retry_then_ack_and_tick_rollback(self):
        snapshot = {"map": {"id": 0, "seed": "event-qa"}, "game": {"tick": 1000},
                    "colonists": [], "development": {}}
        event = {"family": "quest", "signature": "quest:1", "urgency": 50}
        state = {"maps": {}}
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(director.bridge, "collect_snapshot", return_value=snapshot), \
                mock.patch.object(director, "collect_development", return_value=snapshot), \
                mock.patch.object(director.bridge, "safe_get", return_value={}), \
                mock.patch.object(director.events, "pending_events", side_effect=lambda ctx, handled: [] if "quest:1" in handled else [event]), \
                mock.patch.object(director.events, "response_options", return_value={"accept_quest": "accept"}), \
                mock.patch.object(director.events, "event_context_for_model", return_value={}), \
                mock.patch.object(director, "ask_laya_choice", return_value=("accept_quest", {})) as choose, \
                mock.patch.object(director, "_execute_event_response", side_effect=[{"applied": False, "reason": "stale"}, {"success": True}, {"applied": False}]) as execute, \
                mock.patch.object(director, "publish_event_overlay"), \
                mock.patch.object(director.time, "time", return_value=100) as clock:
            args = (mock.Mock(), mock.Mock(), state, Path(folder)/"state.json", Path(folder)/"log.jsonl")
            first = director.run_event_cycle(*args)
            map_state = next(iter(state["maps"].values()))
            self.assertFalse(map_state["handled_events"])
            self.assertEqual(first["result"]["retry_in_seconds"], 5)
            clock.return_value = 101
            self.assertIsNone(director.run_event_cycle(*args))
            self.assertEqual(choose.call_count, 1)
            clock.return_value = 105
            director.run_event_cycle(*args)
            self.assertEqual(map_state["handled_events"], {"quest:1": 1000})
            snapshot["game"]["tick"] = 100
            clock.return_value = 110
            director.run_event_cycle(*args)
            self.assertFalse(next(iter(state["maps"].values()))["handled_events"])
            self.assertEqual(execute.call_count, 3)

    def test_security_profession_uses_native_medicine_skill(self):
        healthy = {"name": "Medic", "skills": {"Medicine": {"level": 16}}}
        untrained = {"name": "Medic", "skills": {"Medicine": {"level": 0}}}
        good = professions.profession_context([healthy], [])["directions"]["security_hunting"]
        bad = professions.profession_context([untrained], [])["directions"]["security_hunting"]
        self.assertEqual(good["fit_score"] - bad["fit_score"], 9.6)
        self.assertIn("Medicine", [row["skill"] for row in good["people"]])

    def test_growth_reports_current_available_skills_and_mental_absence(self):
        people = [
            {"in_mental_state": True, "skills": {"Medicine": {"level": 20}}},
            {"skills": {"Medicine": {"level": 16, "disabled": True}}},
            {"skills": {"Medicine": {"level": 5}}},
            {"downed": True, "skills": {"Medicine": {"level": 19}}},
            {"capacities": {"moving": 0}, "skills": {"Medicine": {"level": 18}}},
        ]
        result = growth.trade_population_context({"colonists": people})
        self.assertEqual(result["able_workers"], 2)
        self.assertEqual(result["bedbound"], 2)
        self.assertEqual(result["unavailable_workers"], 3)
        self.assertEqual(result["best_skills"]["Medicine"], 5)


if __name__ == "__main__":
    unittest.main()

import copy
from pathlib import Path
import unittest
import rimworld_laya as bridge
import colony_director as director


class CombatContracts(unittest.TestCase):
    def command(self, endpoint="/api/v1/combat/tactic"):
        return {"endpoint": endpoint, "body": {"target_thing_id": 9}}

    def test_endpoint_contract_rejection_unknown_and_no_body_success(self):
        self.assertFalse(bridge.command_acceptance(self.command(), {"applied": False, "drafted_pawn_ids": [1]}))
        self.assertFalse(bridge.command_acceptance(self.command(), {"drafted_pawn_ids": [], "positioned_pawn_ids": [], "attacking_pawn_ids": [], "psycast_queued": False}))
        self.assertTrue(bridge.command_acceptance(self.command(), {"positioned_pawn_ids": [1]}))
        self.assertTrue(bridge.command_acceptance(self.command(), {"success": True, "data": {"psycast_queued": True}}))
        self.assertIsNone(bridge.command_acceptance(self.command("/unknown"), {"success": True}))
        for endpoint in bridge._NO_BODY_COMMANDS:
            self.assertTrue(bridge.command_acceptance(self.command(endpoint), {"success": True, "errors": [], "warnings": []}))
            self.assertFalse(bridge.command_acceptance(self.command(endpoint), {"applied": False, "success": True}))

    def test_partial_acceptance_and_failed_post_keep_rows_aligned(self):
        class Client:
            calls = 0
            def post(self, *args, **kwargs):
                self.calls += 1
                if self.calls == 2: raise bridge.RimApiError("transport failed after POST")
                return {"positioned_pawn_ids": [1]}
        commands = [self.command(), self.command(), self.command()]
        result = bridge.apply_action(Client(), {"kind": "commands", "commands": commands})
        self.assertTrue(result["applied"])
        self.assertTrue(result["outcome_unknown"])
        self.assertEqual(result["failed_command_index"], 1)
        self.assertEqual(result["command_acceptance"], [True, False])
        self.assertEqual(len(result["responses"]), 2)
        self.assertIn("error", result["responses"][1])
        result = bridge.command_result(commands, [{"applied": False}, {"success": True}, {"positioned_pawn_ids": [1]}])
        self.assertEqual(result["command_acceptance"], [False, None, True])
        self.assertTrue(result["applied"])
        self.assertTrue(result["outcome_unknown"])

    def test_rejected_stale_target_is_not_applied_when_only_prior_denial(self):
        class Client:
            calls = 0
            def post(self, *args, **kwargs):
                self.calls += 1
                if self.calls == 2:
                    raise bridge.RimApiError("HTTP 404 Target thing not found on the worker's map")
                return {"drafted_pawn_ids": [], "positioned_pawn_ids": [], "attacking_pawn_ids": []}
        commands = [self.command(), self.command("/api/v1/pawn/job")]
        result = bridge.apply_action(Client(), {"kind": "commands", "commands": commands})
        self.assertFalse(result["applied"])
        self.assertTrue(result["stale_target"])
        self.assertEqual(result["command_acceptance"], [False, False])

    def test_preemptive_failed_hop_replaces_acceptance_and_retry_is_five_seconds(self):
        snapshot = {"combat": {"colonists": [{"id": 1, "health": 1, "current_job": "Wait_Combat"}, {"id": 2, "health": 1, "current_job": "Wait_Combat"}],
                               "hostiles": [{"id": 9, "current_job": "GotoWander"}]}}
        record = {"decision": {"choice": "preemptive_strike"}, "action": {"commands": [{"endpoint": "/api/v1/combat/tactic", "body": {"tactic": "preemptive_strike", "fighter_ids": [1, 2], "target_pawn_id": 9}}]},
                  "result": {"responses": [{"positioned_pawn_ids": [1, 2]}]}}
        self.assertEqual(director.preemptive_advance_state(snapshot, record, 3)[0], "advance")
        director.record_combat_step(record, {"positioned_pawn_ids": [], "attacking_pawn_ids": [], "drafted_pawn_ids": []})
        self.assertEqual(director.preemptive_advance_state(snapshot, record, 3)[0], "replan")
        self.assertTrue(director.combat_record_rejected(record))
        self.assertEqual([director.combat_failed_retry_due((1,), (1,), t) for t in (0, 2, 4.9, 5, 10)], [False, False, False, True, True])
        self.assertTrue(director.combat_failed_retry_due((2,), (1,), .1))
        director.record_combat_step(record, {"positioned_pawn_ids": [1, 2]})
        snapshot["combat"]["colonists"][0]["current_job"] = "Goto"
        self.assertEqual(director.preemptive_advance_state(snapshot, record, 3)[0], "wait")
        self.assertFalse(director.combat_record_rejected(record))

    def test_reserve_and_support_success_do_not_hide_primary_failure_or_receive_hop_response(self):
        snapshot = {"combat": {"colonists": [{"id": 1, "health": 1, "current_job": "Wait_Combat"}, {"id": 2, "health": 1, "current_job": "Wait_Combat"}], "hostiles": [{"id": 9, "current_job": "GotoWander"}]}}
        main = {"endpoint": "/api/v1/combat/tactic", "body": {"tactic": "preemptive_strike", "fighter_ids": [1, 2], "target_pawn_id": 9}}
        reserve = {"endpoint": "/api/v1/combat/tactic", "body": {"tactic": "withdraw_and_regroup"}}
        support = {"endpoint": "/api/v1/combat/tactic", "body": {"tactic": "focus_fire"}}
        record = {"decision": {"choice": "preemptive_strike"}, "action": {"commands": [reserve, main, support]},
                  "result": {"responses": [{"positioned_pawn_ids": [3]}, {"positioned_pawn_ids": [], "attacking_pawn_ids": []}, {"attacking_pawn_ids": [4]}]}}
        self.assertTrue(director.combat_record_rejected(record))
        self.assertEqual(director.preemptive_advance_state(snapshot, record, 3)[0], "replan")
        director.record_combat_step(record, {"positioned_pawn_ids": [1, 2]})
        self.assertEqual(record["result"]["responses"][0], {"positioned_pawn_ids": [3]})
        self.assertEqual(record["result"]["responses"][2], {"attacking_pawn_ids": [4]})
        self.assertFalse(director.combat_record_rejected(record))
        self.assertEqual(director.preemptive_advance_state(snapshot, record, 3)[0], "advance")
        record["decision"]["choice"] = "kite"
        record["action"]["commands"][1]["body"]["tactic"] = "kite"
        record["result"]["responses"][1] = {"attacking_pawn_ids": []}
        self.assertTrue(director.combat_record_rejected(record))
        record = {"decision": {"choice": "stand_down"}, "action": {"commands": [self.command("/api/v1/pawn/edit/status")]},
                  "result": {"failed_command_index": 0, "error": "transport failed", "outcome_unknown": True}}
        self.assertTrue(director.combat_record_rejected(record))

    def test_native_actual_kidnapper_guard_precedes_drafting(self):
        source = Path("vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatTacticsHelper.cs").read_text()
        guard = 'tactic == "intercept_kidnapper" && !CombatNativeHelper.Kidnapper(target)'
        self.assertLess(source.index(guard), source.index('pawn.drafter.Drafted = true'))
        self.assertIn('(tactic == "focus_fire" && CombatNativeHelper.Kidnapper(target))', source)
        self.assertNotIn('(tactic == "focus_fire" && target.carryTracker?.CarriedThing is Pawn)', source)


if __name__ == "__main__": unittest.main()

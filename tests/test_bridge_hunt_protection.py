"""A hunt lease protects only its actors, only while combat is absent."""
import unittest
import rimworld_laya as bridge


class HuntStandDownTests(unittest.TestCase):
    def snapshot(self):
        return {"map": {"id": 0, "enemies": 0}, "game": {"is_paused": False},
                "colonists": [], "combat": {"colonists": [
                    {"id": 1, "is_drafted": True}, {"id": 2, "is_drafted": True}],
                    "hostiles": [], "protected_noncombat_pawn_ids": [1],
                    "colony_animals": [{"master_pawn_id": 1, "animals_released": True},
                                       {"master_pawn_id": 2, "animals_released": True}]}}

    def test_stand_down_leaves_observed_hunter_and_its_animals(self):
        action = bridge.plan_action(self.snapshot(), {"choice": "stand_down"})
        self.assertEqual([c["body"]["pawn_id"] for c in action["commands"]
                          if "pawn_id" in c.get("body", {})], [2])
        self.assertEqual([c["body"]["master_pawn_id"] for c in action["commands"]
                          if "master_pawn_id" in c.get("body", {})], [2])

    def test_fresh_hostile_invalidates_peaceful_lease_protection(self):
        snapshot = self.snapshot()
        snapshot["combat"]["hostiles"] = [{"id": 99, "is_downed": False, "is_dead": False}]
        action = bridge.plan_action(snapshot, {"choice": "stand_down"})
        self.assertEqual([c["body"]["pawn_id"] for c in action["commands"]
                          if "pawn_id" in c.get("body", {})], [1, 2])


if __name__ == "__main__":
    unittest.main()

import copy
import json
import unittest
from unittest.mock import patch
import colony_architect as a
import colony_director as d
from tests.test_capabilities import snapshot
from tests.test_construction_recovery import NativeClient


class LegacyHospitalRecoveryTests(unittest.TestCase):
    def fixture(self):
        s = snapshot(); s["map"]["id"] = 1
        s["development"].update(item_counts={"WoodLog": 1000}, building_counts={"Wall": 25, "Bed": 2, "FueledStove": 1})
        s["colonists"][0]["work_priorities"]["Construction"] = {"priority": 1, "disabled": False}
        memory = {"anchor": {"x": 10, "z": 10}, "issued": {}}
        client = NativeClient()
        client.catalog += [{"def_name": n, "available_now": True, "cost_list": []} for n in ("Bed", "TorchLamp")]
        return s, memory, client

    def execute(self, client, snap, memory, site_finder=None):
        with patch.object(d, "prioritize", return_value={}), \
             patch.object(d, "find_clear_layout_site", side_effect=site_finder or (lambda c, m, origin, layout, dev, state: origin)):
            return d.execute_action(client, snap, memory, "build_hospital", {})

    def candidates(self, snap, memory, client):
        snap["development"].update(a.read_construction(client, 1))
        with patch.object(d, "sheltered_real_bed_count", return_value=2), \
             patch.object(d, "defer_discretionary_work_until_shelter", side_effect=lambda s, m, actions: actions):
            return d.candidate_actions(None, snap, memory)[0]

    @patch("colony_retry.time.time", return_value=100)
    def test_rejected_blueprint_not_success_and_candidate_retries(self, clock):
        s, memory, client = self.fixture(); client.place = False
        result = self.execute(client, s, memory)
        self.assertFalse(result["applied"])
        self.assertEqual(result["project"]["verified_count"], 0)
        self.assertNotIn("build_hospital", self.candidates(s, memory, client))
        s["game"]["tick"] += 2500
        clock.return_value = 131
        self.assertIn("build_hospital", self.candidates(s, memory, client))

    def test_old_marker_without_layout_expires_without_invented_recovery(self):
        s, memory, client = self.fixture()
        memory["issued"]["hospital_blueprint"] = s["game"]["tick"] - 2500
        self.assertIn("build_hospital", self.candidates(s, memory, client))
        self.assertEqual(memory.get("architecture_projects", []), [])

    def test_partial_lost_response_repairs_only_missing_at_original_site(self):
        s, memory, client = self.fixture()
        original = client.post
        def partial(path, **kwargs):
            if path.endswith("/preview"):
                return original(path, **kwargs)
            original(path, **kwargs)
            client.projects = client.projects[:1]
            raise ConnectionError("lost partial reply")
        client.post = partial
        result = self.execute(client, s, memory)
        self.assertFalse(result["applied"])
        self.assertEqual(result["project"]["verified_count"], 1)
        self.assertEqual(result["project"]["origin"], {"x": 35, "z": 10})
        memory = json.loads(json.dumps(memory)); s["game"]["tick"] += 2500
        self.assertIn("repair_architecture", self.candidates(s, memory, client))
        self.assertNotIn("build_hospital", self.candidates(s, memory, client))
        client.post = original
        result = a.execute_repair(client, s, memory, "0", d.terrain_defs_at_cells)
        self.assertTrue(result["complete_plan_placed"])
        preview = [v for p, v in client.posts if p.endswith("/preview")][-1]["body"]
        self.assertEqual(preview["position"]["x"], 35)
        self.assertEqual(len(preview["blueprint"]["buildings"]), 26)

    def test_all_cancelled_retry_can_search_new_clear_site(self):
        s, memory, client = self.fixture()
        self.assertTrue(self.execute(client, s, memory)["applied"])
        self.assertNotIn("build_hospital", self.candidates(s, memory, client))
        client.projects = []; s["game"]["tick"] += 2500
        memory["anchor"] = {"x": 100, "z": 100}
        self.assertIn("build_hospital", self.candidates(s, memory, client))
        self.assertTrue(self.execute(client, s, memory)["applied"])
        body = [v for p, v in client.posts if not p.endswith("/preview")][-1]["body"]
        self.assertEqual(body["position"]["x"], 125)
        self.assertEqual(len(memory["architecture_projects"]), 1)

    def test_full_existing_clinic_prevents_duplicate(self):
        s, memory, client = self.fixture()
        self.execute(client, s, memory)
        client.buildings = copy.deepcopy(client.projects); client.projects = []
        s["game"]["tick"] += 2500
        self.assertNotIn("build_hospital", self.candidates(s, memory, client))
        before = len(client.posts)
        result = self.execute(client, s, memory)
        self.assertFalse(result["applied"])
        self.assertTrue(result["complete_plan_placed"])
        self.assertEqual(len(client.posts), before)

    def test_observation_loss_keeps_exact_intent(self):
        s, memory, client = self.fixture()
        original = client.get
        def lost(path, **kwargs):
            if client.projects and path.endswith("/projects"):
                raise ConnectionError("observation lost")
            return original(path, **kwargs)
        client.get = lost
        result = self.execute(client, s, memory)
        self.assertFalse(result["applied"])
        self.assertTrue(result["outcome_unknown"])
        self.assertTrue(memory["architecture_projects"][0]["observation_pending"])
        self.assertEqual(len(memory["architecture_projects"][0]["layout"]["buildings"]), 27)

    @patch("colony_retry.time.time", return_value=100)
    def test_empty_blocked_site_retry_selects_fresh_clear_site_after_both_clocks(self, clock):
        s, memory, client = self.fixture(); client.preview_blocked = True
        result = self.execute(client, s, memory)
        self.assertFalse(result["applied"])
        self.assertEqual(result["project"]["origin"], {"x": 35, "z": 10})
        s["game"]["tick"] += 3600; clock.return_value = 102
        self.assertNotIn("build_hospital", self.candidates(s, memory, client))
        clock.return_value = 131
        self.assertIn("build_hospital", self.candidates(s, memory, client))
        client.preview_blocked = False
        def new_clear_site(c, map_id, desired, layout, development, search_memory):
            self.assertIn((35, 10), d.architecture_occupied_cells(development, search_memory))
            return {"x": 70, "z": 25}
        result = self.execute(client, s, memory, site_finder=new_clear_site)
        self.assertTrue(result["applied"])
        self.assertEqual(result["project"]["origin"], {"x": 70, "z": 25})
        self.assertNotIn("failure_retry", result["project"])
        self.assertEqual(len(memory["architecture_projects"]), 1)

    def test_actual_medical_bed_outside_legacy_rectangle_prevents_new_clinic(self):
        s, memory, client = self.fixture()
        client.buildings = [{"id": 4, "def": "Bed", "medical": True, "position": {"x": 5, "z": 5}}]
        self.assertNotIn("build_hospital", self.candidates(s, memory, client))

    @patch("colony_retry.time.time", return_value=100)
    def test_failed_repair_floor_is_scoped_to_one_project(self, clock):
        s, memory, client = self.fixture()
        layout = {"width": 2, "height": 1, "floors": [], "buildings": [
            d.building("Wall", 0, 0, stuff="WoodLog"), d.building("Door", 1, 0, stuff="WoodLog")]}
        memory["architecture_projects"] = [{"map_id": 1, "program": "hospital", "layout": copy.deepcopy(layout),
            "origin": {"x": x, "z": 10}, "width": 2, "height": 1, "issued_tick": s["game"]["tick"] - 3000}
            for x in (10, 20)]
        client.projects = [{"def_name": "Wall", "stuff_def_name": "WoodLog", "rotation": 0,
                            "position": {"x": x, "z": 10}} for x in (10, 20)]
        client.preview_blocked = True
        result = a.execute_repair(client, s, memory, "0", d.terrain_defs_at_cells)
        self.assertFalse(result["applied"])
        s["game"]["tick"] += 3600; clock.return_value = 102
        fresh = a.read_construction(client, 1)
        options = a.reconcile_projects(fresh, memory, 1, s["game"]["tick"], d.terrain_defs_at_cells)
        self.assertNotIn("0", options)
        self.assertIn("1", options)
        clock.return_value = 131
        options = a.reconcile_projects(fresh, memory, 1, s["game"]["tick"], d.terrain_defs_at_cells)
        self.assertIn("0", options)
        client.preview_blocked = False
        self.assertTrue(a.execute_repair(client, s, memory, "0", d.terrain_defs_at_cells)["applied"])
        self.assertNotIn("failure_retry", memory["architecture_projects"][0])


if __name__ == "__main__":
    unittest.main()

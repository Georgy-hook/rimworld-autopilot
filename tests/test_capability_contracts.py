"""Sequential offline checks; no game, API server or model required."""
import copy
import json
import unittest
from unittest.mock import patch
import colony_capabilities as caps
from tests.test_capabilities import snapshot, animal, augmentation, crop, growing_site, Agent, Client


class CapabilityContractTests(unittest.TestCase):
    def training(self):
        s = snapshot()
        s["animals"] = [animal(7, learned=False), animal(8, learned=False)]
        return s

    def test_success_subject_dwell_keeps_new_animal_available(self):
        s, memory = self.training(), {}
        caps.prepare(s, memory)
        caps.execute(Client(), s, memory, "assign_animal_training", {
            "training_animal": "7", "animal_trainable": "Obedience", "animal_handler": "1"})
        memory = json.loads(json.dumps(memory))
        self.assertIn("assign_animal_training", caps.prepare(s, memory))
        self.assertEqual(set(s["development"]["capability_plans"]["assign_animal_training"]), {"8"})

    @patch("colony_retry.time.time", return_value=100)
    def test_rejection_short_and_independent_then_expires(self, clock):
        s, memory = self.training(), {}
        caps.prepare(s, memory)
        caps.execute(Client(False), s, memory, "assign_animal_training", {
            "training_animal": "7", "animal_trainable": "Obedience", "animal_handler": "1"})
        caps.prepare(s, memory)
        self.assertEqual(set(s["development"]["capability_plans"]["assign_animal_training"]), {"8"})
        s["game"]["tick"] += 250
        clock.return_value = 131
        caps.prepare(s, memory)
        self.assertEqual(set(s["development"]["capability_plans"]["assign_animal_training"]), {"7", "8"})

    def test_unknown_post_has_short_backoff(self):
        class Lost(Client):
            def post(self, *args, **kwargs):
                raise OSError("lost response")
        s, memory = self.training(), {}
        caps.prepare(s, memory)
        result = caps.execute(Lost(), s, memory, "assign_animal_training", {
            "training_animal": "7", "animal_trainable": "Obedience", "animal_handler": "1"})
        self.assertTrue(result["outcome_unknown"])
        caps.prepare(s, memory)
        self.assertNotIn("7", s["development"]["capability_plans"]["assign_animal_training"])

    @patch("colony_retry.time.time", return_value=100)
    def test_partial_surgery_retry_only_priority(self, clock):
        class Partial(Client):
            def post(self, endpoint, **kwargs):
                self.calls.append((endpoint, kwargs))
                return {"applied": endpoint != "/api/v1/colonist/work-priority" or self.applied}
        s, memory, client = snapshot(), {}, Partial(False)
        s["development"]["augmentation_context"] = {"options": [augmentation()]}
        caps.prepare(s, memory)
        result = caps.execute(client, s, memory, "plan_colonist_augmentation", {
            "augmentation_operation": "1|InstallFieldHand|5", "augmentation_doctor": "2", "augmentation_bed": "10"})
        self.assertTrue(result["applied"])
        self.assertTrue(result["partial"])
        # The actual native queued bill disappears from ordinary choices.
        s["development"]["augmentation_context"]["options"][0]["already_queued"] = True
        s["game"]["tick"] += 250
        clock.return_value = 131
        memory = json.loads(json.dumps(memory))
        self.assertIn("plan_colonist_augmentation", caps.prepare(s, memory))
        selected, _ = caps.choose(Agent(), {}, "plan_colonist_augmentation", s)
        client.applied = True
        result = caps.execute(client, s, memory, "plan_colonist_augmentation", selected)
        self.assertTrue(result["applied"])
        self.assertEqual([p for p, _ in client.calls].count("/api/v1/medical/augmentation"), 1)
        self.assertEqual(client.calls[-1][0], "/api/v1/colonist/work-priority")
        self.assertEqual(memory["capability_auxiliary"], {})

    @patch("colony_retry.time.time", return_value=100)
    def test_fast_game_failure_waits_for_real_deadline(self, clock):
        s, memory = self.training(), {}
        caps.prepare(s, memory)
        caps.execute(Client(False), s, memory, "assign_animal_training", {
            "training_animal": "7", "animal_trainable": "Obedience", "animal_handler": "1"})
        s["game"]["tick"] += 3600
        clock.return_value = 102
        caps.prepare(s, memory)
        self.assertEqual(set(s["development"]["capability_plans"]["assign_animal_training"]), {"8"})
        clock.return_value = 131
        caps.prepare(s, memory)
        self.assertEqual(set(s["development"]["capability_plans"]["assign_animal_training"]), {"7", "8"})

    @patch("colony_retry.time.time", return_value=100)
    def test_failure_expires_only_after_both_clocks(self, clock):
        s, memory = self.training(), {}
        caps.prepare(s, memory)
        caps.execute(Client(False), s, memory, "assign_animal_training", {
            "training_animal": "7", "animal_trainable": "Obedience", "animal_handler": "1"})
        clock.return_value = 131
        caps.prepare(s, memory)
        self.assertNotIn("7", s["development"]["capability_plans"]["assign_animal_training"])
        s["game"]["tick"] += 250
        caps.prepare(s, memory)
        self.assertIn("7", s["development"]["capability_plans"]["assign_animal_training"])

    @patch("colony_retry.time.time", return_value=100)
    def test_wall_rollback_and_far_future_deadline_invalidated(self, clock):
        s, memory = self.training(), {}
        caps.prepare(s, memory)
        caps.execute(Client(False), s, memory, "assign_animal_training", {
            "training_animal": "7", "animal_trainable": "Obedience", "animal_handler": "1"})
        memory = json.loads(json.dumps(memory))
        clock.return_value = 99
        caps.prepare(s, memory)
        self.assertEqual(memory["capability_history"], {})
        record = {"tick": s["game"]["tick"], "map_id": 0, "duration": 250,
                  "retry_started_at": 90, "retry_until": 10**20}
        memory["capability_history"]["assign_animal_training:failed:7"] = record
        caps.prepare(s, memory)
        self.assertEqual(memory["capability_history"], {})
        self.assertIn("7", s["development"]["capability_plans"]["assign_animal_training"])

    @patch("colony_retry.time.time", return_value=100)
    def test_repeated_aux_failure_frees_other_recipient(self, clock):
        class Partial(Client):
            def post(self, path, **kwargs):
                self.calls.append((path, kwargs))
                return {"applied": not path.endswith("work-priority")}
        s, memory, client = self.training(), {}, Partial()
        caps.prepare(s, memory)
        caps.execute(client, s, memory, "assign_animal_training", {
            "training_animal": "7", "animal_trainable": "Obedience", "animal_handler": "1"})
        s["game"]["tick"] += 3600; clock.return_value = 102
        caps.prepare(s, memory)
        self.assertEqual(set(s["development"]["capability_plans"]["assign_animal_training"]), {"8"})
        clock.return_value = 131
        caps.prepare(s, memory)
        selection, _ = caps.choose(Agent(), {}, "assign_animal_training", s)
        self.assertIn("auxiliary_retry", selection)
        caps.execute(client, s, memory, "assign_animal_training", selection)
        s["game"]["tick"] += 3600; clock.return_value = 133
        caps.prepare(s, memory)
        self.assertEqual(set(s["development"]["capability_plans"]["assign_animal_training"]), {"8"})
        self.assertEqual([p for p, _ in client.calls].count("/api/v1/map/animal/training"), 1)

    def test_defer_only_shown_patient_and_new_patient_visible(self):
        s, memory = snapshot(), {}
        s["development"]["augmentation_context"] = {"options": [augmentation()]}
        caps.prepare(s, memory)
        selected, _ = caps.choose(Agent({"augmentation_patient": "defer"}), {}, "plan_colonist_augmentation", s)
        caps.execute(Client(), s, memory, "plan_colonist_augmentation", selected)
        other = augmentation(); other["patient_pawn_id"] = 9
        s["development"]["augmentation_context"]["options"].append(other)
        caps.prepare(s, memory)
        self.assertEqual(set(s["development"]["capability_plans"]["plan_colonist_augmentation"]), {"9|InstallFieldHand|5"})

    def test_rollback_map_and_malformed_history_pruned(self):
        s = self.training()
        memory = {"capability_history": {"bad": None, "incomplete": {}, "future": {
            "tick": 70000, "duration": 15000, "map_id": 0}, "other": {"tick": 60000, "duration": 15000, "map_id": 8}},
            "capability_auxiliary": {"legacy": None}}
        caps.prepare(s, json.loads(json.dumps(memory)))
        caps.prepare(s, memory)
        self.assertEqual(memory["capability_history"], {})
        self.assertEqual(memory["capability_auxiliary"], {})

    def test_full_care_jobs_excluded(self):
        for job in ("BottleFeedBaby", "BringBabyToSafety", "Deathrest", "Ingest"):
            s = snapshot(); s["colonists"][0]["current_job"] = job
            self.assertEqual(caps.workers(s, "Growing"), [], job)

    def test_designated_blight_not_reissued(self):
        s = snapshot()
        s["development"]["plants"] = [{"thing_id": 3, "blighted": True, "is_designated_for_cut": True}]
        self.assertNotIn("clear_plant_blight", caps.prepare(s, {}))

    def test_same_def_emp_quality_remains_explicit_choice(self):
        s = snapshot(); p = s["combat"]["colonists"][0]
        p["weapon_def"] = "Gun_EMPLauncher"
        p["weapon_info"] = {"id": 3, "def_name": "Gun_EMPLauncher", "emp": True, "is_ranged": True, "quality": 2}
        s["combat"]["available_weapons"] = [{**p["weapon_info"], "id": 4, "quality": 5, "compatible_pawn_ids": [1]}]
        self.assertIn("improve_weapon_loadout", caps.prepare(s, {}))
        selected, _ = caps.choose(Agent({"weapon_pawn": "defer"}), {}, "improve_weapon_loadout", s)
        self.assertTrue(selected["weapon_defer"])

    @patch("colony_retry.time.time", return_value=100)
    def test_crop_repair_does_not_repeat_accepted_crop(self, clock):
        class Partial(Client):
            def post(self, path, **kwargs):
                self.calls.append((path, kwargs))
                return {"applied": self.applied or path.endswith("/crop")}
        s, memory, client = snapshot(), {}, Partial(False)
        rice = crop()
        site = growing_site(options=[rice], allow_sow=False)
        s["development"]["plant_catalog"] = {"plants": [rice], "growers": [site]}
        caps.prepare(s, memory)
        result = caps.execute(client, s, memory, "configure_crop", {
            "crop_site": "zone:4", "crop_type": "Plant_Rice", "crop_worker": "1"})
        self.assertTrue(result["partial"])
        self.assertTrue(result["applied"])
        site["plant_def"] = "Plant_Rice"
        s["game"]["tick"] += 3600; clock.return_value = 131
        caps.prepare(s, memory)
        selection, _ = caps.choose(Agent(), {}, "configure_crop", s)
        client.applied = True
        caps.execute(client, s, memory, "configure_crop", selection)
        self.assertEqual([path for path, _ in client.calls].count("/api/v1/map/zone/growing/crop"), 1)
        self.assertEqual(memory["capability_auxiliary"], {})

    @patch("colony_retry.time.time", return_value=100)
    def test_unknown_auxiliary_preserves_accepted_training(self, clock):
        class LostPriority(Client):
            def post(self, path, **kwargs):
                self.calls.append((path, kwargs))
                if path.endswith("work-priority") and not self.applied:
                    raise OSError("unknown permission outcome")
                return {"success": True} if path.endswith("work-priority") else {"applied": True}
        s, memory, client = self.training(), {}, LostPriority(False)
        caps.prepare(s, memory)
        result = caps.execute(client, s, memory, "assign_animal_training", {
            "training_animal": "7", "animal_trainable": "Obedience", "animal_handler": "1"})
        self.assertTrue(result["applied"])
        self.assertTrue(result["partial"])
        self.assertTrue(result["outcome_unknown"])
        s["game"]["tick"] += 3600; clock.return_value = 131
        caps.prepare(s, memory)
        selection, _ = caps.choose(Agent(), {}, "assign_animal_training", s)
        client.applied = True
        caps.execute(client, s, memory, "assign_animal_training", selection)
        self.assertEqual([p for p, _ in client.calls].count("/api/v1/map/animal/training"), 1)

    def test_equip_permission_in_guarded_request_and_success_envelope(self):
        class Equip(Client):
            def post(self, path, **kwargs):
                self.calls.append((path, kwargs))
                return {"success": True}
        s, memory, client = snapshot(), {}, Equip()
        s["combat"]["available_weapons"] = [{"id": 4, "def_name": "ModWeapon", "is_forbidden": True,
            "is_ranged": True, "compatible_pawn_ids": [1]}]
        caps.prepare(s, memory)
        result = caps.execute(client, s, memory, "improve_weapon_loadout", {"weapon_pawn": "1", "weapon_item": "4"})
        self.assertTrue(result["applied"])
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0][0], "/api/v1/pawn/job")
        self.assertEqual(client.calls[0][1]["body"]["map_id"], 0)
        self.assertTrue(client.calls[0][1]["body"]["allow_unforbid_equip"])


if __name__ == "__main__":
    unittest.main()

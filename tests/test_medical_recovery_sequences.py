"""Offline patient recovery through real candidate, choice and executor calls."""
import copy
import unittest
import colony_director as director
import colony_medical_recovery as care
from test_legacy_action_sequences import baseline, pawn, FirstChoice, World


class MedicalWorld(World):
    def __init__(self):
        snap = baseline()
        dawn = pawn(257)
        dawn.update(name="Dawn", downed=True, hunger=0, bleeding_rate=0,
                    health_conditions=[{"def_name": "BloodLoss", "severity": .099},
                                       {"def_name": "Malnutrition", "severity": 1}])
        nanda = pawn(300)
        nanda["work_priorities"]["Doctor"] = {"priority": 3, "disabled": False}
        nanda["skills"]["Medicine"] = {"level": 2}
        snap["colonists"] = [dawn, nanda]
        snap["development"]["resilience"] = {"available": True, "patients": [
            {"pawn_id": 257, "in_bed": False}], "options": [], "active_orders": []}
        super().__init__(snap)
        self.sites = [{"position": {"x": 20, "z": 20}, "rotation": 0}]
        self.stage = "bed_prerequisite"
        self.context_rejected = False
        self.order_mode = "success"
        self.update()

    def update(self):
        context = self.snapshot["development"]["resilience"]
        context["options"] = [] if self.stage == "active" else [{"kind": self.stage,
            "worker_id": 300, "target_id": 257, "worker": "Nanda", "medicine_skill": 2, "food_feasible": True,
            "giver": "SleepingSpot" if self.stage == "bed_prerequisite" else
                     "DoctorRescue" if self.stage == "rescue" else "DoctorFeedHumanlikes"}]

    def get(self, endpoint, **kwargs):
        if endpoint == "/api/v1/resilience/context":
            context = copy.deepcopy(self.snapshot["development"]["resilience"])
            if self.context_rejected:
                context["options"] = []
            return context
        return super().get(endpoint, **kwargs)

    def post(self, endpoint, **kwargs):
        if endpoint == "/api/v1/builder/blueprint":
            self.calls.append(("post", endpoint, kwargs))
            return {"success": self.mode != "denied"}
        if endpoint == "/api/v1/resilience/order":
            self.calls.append(("post", endpoint, kwargs))
            if self.order_mode != "denied":
                self.snapshot["development"]["resilience"]["active_orders"] = [kwargs["body"]]
                self.stage = "active"
                self.update()
            if self.order_mode == "lost":
                raise director.bridge.RimApiError("lost acknowledgment")
            return {"applied": self.order_mode != "denied"}
        return super().post(endpoint, **kwargs)


class MedicalRecoverySequences(unittest.TestCase):
    def setUp(self):
        self.world = MedicalWorld()
        self.state = {"anchor": {"x": 20, "z": 20}, "issued": {"starter_base": 12000}}

    def candidates(self):
        snapshot = copy.deepcopy(self.world.snapshot)
        actions, details = director.candidate_actions(self.world, snapshot, self.state)
        return snapshot, actions, details

    def cycle(self, action):
        snapshot, actions, details = self.candidates()
        self.assertIn(action, actions)
        choice = director.choose_action(FirstChoice(), snapshot, [action])
        details = director.merge_decision_details(details, choice)
        return director.execute_action(self.world, snapshot, self.state, action, details)

    def test_dawn_ground_accepted_spot_wait_then_real_spot_rescue_and_feed(self):
        placed = self.cycle("prepare_patient_bed")
        self.assertFalse(placed["applied"])
        self.assertTrue(placed["pending"])
        _, actions, _ = self.candidates()
        self.assertNotIn("prepare_patient_bed", actions)
        self.assertNotIn("equip_colonists", actions)
        self.world.snapshot["development"]["buildings"] = [{"id": 50, "def": "SleepingSpot", "position": {"x": 20, "z": 20}}]
        self.world.stage = "rescue"
        self.world.update()
        self.assertTrue(self.cycle("rescue_downed_colonist")["applied"])
        _, actions, _ = self.candidates()
        self.assertNotIn("rescue_downed_colonist", actions)
        self.assertNotIn("prepare_patient_bed", actions)
        self.world.snapshot["development"]["resilience"]["active_orders"] = []
        self.world.snapshot["development"]["resilience"]["patients"][0].update(in_bed=True, current_bed_id=50)
        self.world.stage = "feed"
        self.world.update()
        self.assertTrue(self.cycle("feed_hungry_colonist")["applied"])
        self.assertNotIn("feed_hungry_colonist", self.candidates()[1])

    def test_failed_placement_never_records_success_or_pending(self):
        self.world.mode = "denied"
        self.assertFalse(self.cycle("prepare_patient_bed")["applied"])
        self.assertFalse(self.state["patient_spot_pending"])
        self.assertIn("prepare_patient_bed", self.candidates()[1])

    def test_animal_prerequisite_uses_native_animal_spot_def(self):
        animal = self.world.snapshot["colonists"].pop(0)
        self.world.snapshot["animals"] = [animal]
        self.world.snapshot["development"]["resilience"]["options"][0]["giver"] = "AnimalSleepingSpot"
        result = self.cycle("prepare_patient_bed")
        self.assertTrue(result["pending"])
        posted = next(call for call in self.world.calls if call[1] == "/api/v1/builder/blueprint")
        self.assertEqual(posted[2]["body"]["blueprint"]["buildings"][0]["def_name"], "AnimalSleepingSpot")

    def test_mental_doctor_before_and_after_selection(self):
        self.world.stage = "tend"
        self.world.update()
        self.world.snapshot["colonists"][1]["in_mental_state"] = True
        self.assertNotIn("tend_colonist", self.candidates()[1])
        self.world.snapshot["colonists"][1]["in_mental_state"] = False
        snapshot, _, details = self.candidates()
        choice = director.choose_action(FirstChoice(), snapshot, ["tend_colonist"])
        self.world.context_rejected = True
        result = director.execute_action(self.world, snapshot, self.state, "tend_colonist",
                                        director.merge_decision_details(details, choice))
        self.assertFalse(result["applied"])
        self.assertFalse(any(call[1] == "/api/v1/resilience/order" for call in self.world.calls))

    def test_bed_subset_and_feed_actual_patient_target(self):
        snapshot = self.world.snapshot
        snapshot["development"]["resilience"]["patients"][0].update(in_bed=True, current_bed_id=50)
        self.assertFalse(director.patient_in_completed_bed(snapshot["colonists"][0], snapshot, [{"id": 51}]))
        snapshot["combat"] = {"colonists": [{"current_job": "FeedPatient", "current_job_target_id": 99,
                                              "care_target_id": 257}]}
        self.assertEqual(care.active_patients(snapshot), {"257"})

    def test_native_rejection_and_lost_response_reconcile_active_job(self):
        self.world.stage = "feed"
        self.world.update()
        self.world.order_mode = "denied"
        self.assertFalse(self.cycle("feed_hungry_colonist")["applied"])
        self.assertIn("feed_hungry_colonist", self.candidates()[1])
        self.world.order_mode = "lost"
        result = self.cycle("feed_hungry_colonist")
        self.assertTrue(result["readback_verified"])
        self.assertEqual(result["completion"], "unverified")
        self.assertNotIn("feed_hungry_colonist", self.candidates()[1])

    def test_pending_state_reload_and_malformed_records(self):
        import json
        self.cycle("prepare_patient_bed")
        self.state = json.loads(json.dumps(self.state))
        self.assertNotIn("prepare_patient_bed", self.candidates()[1])
        for malformed in (None, "bad", [], {"257": None}, {"257": {"position": []}}):
            self.state["patient_spot_pending"] = malformed
            self.assertIn("prepare_patient_bed", self.candidates()[1])

    def test_two_patients_keep_choices_and_blood_loss_urgency(self):
        snapshot = baseline()
        alyssa = pawn(254)
        dawn = pawn(257)
        alyssa.update(health_conditions=[{"def_name": "BloodLoss", "severity": .857}])
        dawn.update(health_conditions=[{"def_name": "BloodLoss", "severity": .412}])
        snapshot["colonists"] = [alyssa, dawn, pawn(300)]
        snapshot["combat"] = {"colonists": [
            {"id": 254, "name": "Alyssa", "is_downed": True, "tendable_now": True, "bleeding_rate": 2.547},
            {"id": 257, "name": "Dawn", "is_downed": True, "tendable_now": True, "bleeding_rate": 4.324},
            {"id": 300, "name": "Nanda", "medicine_skill": 2}]}
        options = director.post_combat_care_options(snapshot)
        self.assertEqual({row["patient_id"] for row in options.values()}, {254, 257})
        self.assertEqual(next(iter(options.values()))["patient_id"], 254)
        self.assertIsNone(care.triage({"bleeding_rate": 2})[1])

    def test_busy_doctor_for_other_patient_and_food_route_failure(self):
        self.world.stage = "tend"
        self.world.update()
        self.world.snapshot["colonists"][1]["current_job"] = "TendPatient"
        self.assertNotIn("tend_colonist", self.candidates()[1])
        self.world.snapshot["colonists"][1]["current_job"] = "Clean"
        self.assertIn("tend_colonist", self.candidates()[1])
        self.world.stage = "bed_prerequisite"
        self.world.update()
        snapshot = copy.deepcopy(self.world.snapshot)
        snapshot["development"]["resilience"]["options"][0]["food_feasible"] = False
        care.build_options(self.world, snapshot, self.state)
        self.assertEqual(care.focus(snapshot, ["prepare_patient_bed", "harvest_local_plants"]),
                         ["prepare_patient_bed", "harvest_local_plants"])

    def test_comparative_facts_are_independent_of_candidate_order(self):
        import itertools
        patients = [("254", {"patient": {"name": "Patient A", "bleeding_rate": 2.547,
                        "health_conditions": [{"def_name": "BloodLoss", "severity": .857}]}}),
                    ("257", {"patient": {"name": "Patient B", "bleeding_rate": 4.324,
                        "health_conditions": [{"def_name": "BloodLoss", "severity": .412}]}}),
                    ("999", {"patient": {"name": "Unknown", "bleeding_rate": 3}})]
        expected = care.patient_comparison(dict(patients))
        for permutation in itertools.permutations(patients):
            self.assertEqual(care.patient_comparison(dict(permutation)), expected)
        self.assertTrue(expected[1]["254"].startswith("Shortest estimated survival"))
        self.assertTrue(expected[1]["257"].startswith("More estimated time"))
        self.assertTrue(expected[1]["999"].startswith("Death deadline unknown"))
        plan = {"patient": {"position": {"x": 20, "z": 20}}, "helpers": {
            "300": {"worker": "Low skill", "medicine_skill": 2},
            "301": {"worker": "High skill", "medicine_skill": 10}}}
        snapshot = {"colonists": [{"id": 300, "position": {"x": 21, "z": 20}},
                                  {"id": 301, "position": {"x": 21, "z": 20}}]}
        expected = care.helper_comparison(snapshot, plan, "tend_colonist")
        plan["helpers"] = dict(reversed(list(plan["helpers"].items())))
        self.assertEqual(care.helper_comparison(snapshot, plan, "tend_colonist"), expected)
        self.assertIn("Highest available medicine skill", expected[1]["301"])
        self.assertIn("Lower medicine skill", expected[1]["300"])
        self.assertTrue(expected[1]["300"].startswith("Assign Low skill to help this patient:"))
        self.assertNotIn("quality", care.helper_comparison(snapshot, plan, "feed_hungry_colonist")[1]["301"])

    def test_engine_quality_outweighs_skill_proxy_without_hiding_speed_tradeoff(self):
        plan = {"patient": {"position": {"x": 10, "z": 10}}, "helpers": {
            "1": {"worker": "Enhanced doctor", "medicine_skill": 2,
                  "medical_tend_quality": .9, "medical_tend_speed": .6},
            "2": {"worker": "Impaired doctor", "medicine_skill": 10,
                  "medical_tend_quality": .4, "medical_tend_speed": 1.2}}}
        context, criteria = care.helper_comparison({}, plan, "tend_colonist")
        self.assertEqual(set(criteria), {"1", "2"})
        self.assertIn("highest available expected quality", criteria["1"])
        self.assertIn("slower than another doctor", criteria["1"])
        self.assertIn("poorer expected quality", criteria["2"])
        self.assertIn("fastest available", criteria["2"])
        self.assertIn("infection risk", context)
        plan["helpers"]["1"].pop("medical_tend_quality")
        plan["helpers"]["1"].pop("medical_tend_speed")
        unknown = care.helper_comparison({}, plan, "tend_colonist")[1]["1"]
        self.assertNotIn("Tend quality stat", unknown)
        self.assertNotIn("tend speed 0%", unknown)

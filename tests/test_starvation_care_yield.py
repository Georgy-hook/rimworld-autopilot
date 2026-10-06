"""Offline projection/sequence contracts; native feasibility is not simulated game proof."""
import copy
import json
import unittest
import colony_medical_recovery as care


def snapshot(job="Harvest", target=2):
    return {"game": {"tick": 100}, "map": {"id": 0}, "colonists": [
        {"id": 1, "name": "Child", "downed": True, "hunger": 0, "bleeding_rate": 0,
         "health_conditions": [{"def_name": "Malnutrition", "severity": .912, "lethal_severity": 1}]},
        {"id": 2, "name": "Wounded", "downed": True, "hunger": 0, "bleeding_rate": 0 if job == "TendPatient" else .244,
         "health_conditions": [{"def_name": "BloodLoss", "severity": .1}]},
        {"id": 3, "name": "Only caregiver", "current_job": job, "capacities": {"moving": 1, "manipulation": 1},
         "work_priorities": {"Doctor": {"priority": 0, "disabled": False}}}],
        "combat": {"colonists": [{"id": 3, "current_job": job, "current_job_target_id": target}]},
        "development": {"resilience": {"patients": [{"pawn_id": 1, "starvation_ticks": 11000,
             "malnutrition_severity": .912, "lethal_margin": .088}], "options": [], "active_orders": []}}}


def option(kind="rescue", target=1, expected=None):
    row = {"kind": kind, "target_id": target, "worker_id": 3, "giver": "DoctorRescue" if kind == "rescue" else "DoctorFeedHumanlikes",
           "food_feasible": True, "travel_distance": 4}
    if expected:
        row.update(expected_current_job=expected, expected_care_patient_id=2,
                   care_yield_reason="starvation_precedes_current_patient_known_deadline")
    return row


class StarvationCareYield(unittest.TestCase):
    def plans(self, snap, row):
        snap["development"]["resilience"]["options"] = [row]
        return care.build_options(None, snap, {})

    def test_no_wounds_child_and_doctor_zero_project_native_forced_rescue(self):
        s = snapshot()
        plans = self.plans(s, option())["rescue_downed_colonist"]
        self.assertEqual(set(plans), {"1"})
        self.assertEqual(set(plans["1"]["helpers"]), {"3"})
        self.assertEqual(care.clinical_deadline(plans["1"]["patient"]), 11000)
        self.assertEqual(care.care_order_fields(option()), {})

    def test_disabled_doctor_cannot_feed_even_with_old_native_option(self):
        s = snapshot()
        s["colonists"][2]["work_priorities"]["Doctor"]["disabled"] = True
        self.assertEqual(self.plans(s, option("feed"))["feed_hungry_colonist"], {})

    def test_traveling_rescue_binding_roundtrips_and_supersedes_only_observed_job(self):
        s = snapshot("Rescue")
        row = option(expected="Rescue")
        plans = self.plans(s, row)["rescue_downed_colonist"]
        self.assertEqual(care.care_order_fields(plans["1"]["helpers"]["3"]),
                         {"expected_current_job": "Rescue", "expected_care_patient_id": 2})
        restored = json.loads(json.dumps(s))
        self.assertIsNotNone(care.offered_care_yield(restored, row))
        restored["combat"]["colonists"][0]["current_job_target_id"] = 4
        self.assertEqual(self.plans(restored, row)["rescue_downed_colonist"], {})

    def test_feed_carry_or_changed_job_never_passes_old_binding(self):
        for job, carry in (("FeedPatient", None), ("Rescue", 2), ("SocialRelax", None)):
            with self.subTest(job=job, carry=carry):
                s = snapshot(job)
                s["combat"]["colonists"][0].update(carrying_pawn_id=carry, carrying_player_pawn=carry is not None)
                self.assertEqual(self.plans(s, option(expected="Rescue"))["rescue_downed_colonist"], {})

    def test_same_patient_feed_replaces_native_offered_stable_tend_only(self):
        s = snapshot("TendPatient")
        s["development"]["resilience"]["active_orders"] = [{"kind": "tend", "worker_id": 3, "target_id": 2}]
        row = option("feed", target=2, expected="TendPatient")
        self.assertEqual(set(self.plans(s, row)["feed_hungry_colonist"]), {"2"})
        row.pop("expected_current_job")
        self.assertEqual(self.plans(s, row)["feed_hungry_colonist"], {})

    def test_accepted_rescue_then_feed_lease_suppresses_repeats_and_other_actors(self):
        s = snapshot("Rescue", target=1)
        row = option()
        s["development"]["resilience"]["active_orders"] = [{"kind": "rescue", "worker_id": 3, "target_id": 1}]
        self.assertEqual(self.plans(s, row)["rescue_downed_colonist"], {})
        s["combat"]["colonists"][0].update(current_job="FeedPatient", current_job_target_id_b=1)
        s["development"]["resilience"]["active_orders"] = [{"kind": "feed", "worker_id": 3, "target_id": 1}]
        self.assertEqual(self.plans(s, option("feed"))["feed_hungry_colonist"], {})

    def test_new_urgent_patient_requires_new_native_binding_not_local_bypass(self):
        s = snapshot("TendPatient")
        self.assertEqual(self.plans(s, option())["rescue_downed_colonist"], {})
        self.assertEqual(set(self.plans(s, option(expected="TendPatient"))["rescue_downed_colonist"]), {"1"})

    def test_starvation_compared_with_bleedout_and_unknown_remains_unknown(self):
        s = snapshot()
        starving = {**s["colonists"][0], "starvation_ticks": 11000, "lethal_margin": .088}
        wounded = s["colonists"][1]
        _, facts = care.patient_comparison({"child": {"patient": starving}, "wounded": {"patient": wounded}})
        self.assertIn("Shortest estimated survival", facts["child"])
        self.assertIn("starvation ~11000 ticks", facts["child"])
        self.assertIn("lethal margin 0.088", facts["child"])
        self.assertIsNone(care.clinical_deadline({"bleeding_rate": .244, "health_conditions": []}))
        self.assertIsNone(care.clinical_deadline({"starvation_ticks": None}))
        self.assertEqual(care.clinical_deadline({"bleedout_ticks": 20000, "starvation_ticks": 3000}), 3000)

    def test_dangerous_unknown_bleed_and_immune_disease_keep_existing_care(self):
        for mutation in ("critical_bleed", "unknown_blood", "immune", "critical_other"):
            with self.subTest(mutation=mutation):
                s = snapshot("Rescue")
                old = s["colonists"][1]
                if mutation == "critical_bleed":
                    old["health_conditions"][0]["severity"] = .99
                elif mutation == "unknown_blood":
                    old["health_conditions"] = []
                elif mutation == "immune":
                    old["health_conditions"].append({"def_name": "Plague", "immunity": .8})
                else:
                    old["health_conditions"].append({"def_name": "LungRot", "life_threatening": True})
                self.assertEqual(self.plans(s, option(expected="Rescue"))["rescue_downed_colonist"], {})

    def test_tend_with_any_current_bleeding_cannot_yield_to_feed(self):
        s = snapshot("TendPatient")
        s["colonists"][1]["bleeding_rate"] = .01
        self.assertEqual(self.plans(s, option("feed", target=2, expected="TendPatient"))["feed_hungry_colonist"], {})

    def test_nonimmune_chronic_heart_condition_does_not_hide_urgent_feeding(self):
        s = snapshot('TendPatient')
        old = s['colonists'][1]
        chronic = {'def_name': 'HeartArteryBlockage', 'severity': .196,
                   'immunity': 0, 'immunity_can_develop': False,
                   'lethal_severity': 1, 'life_threatening': False, 'tendable_now': False}
        old['health_conditions'].append(chronic)
        self.assertEqual(set(self.plans(s, option('feed', expected='TendPatient'))['feed_hungry_colonist']), {'1'})
        chronic['life_threatening'] = True
        self.assertEqual(self.plans(s, option('feed', expected='TendPatient'))['feed_hungry_colonist'], {})
        chronic['life_threatening'] = False
        chronic['immunity_can_develop'] = True
        self.assertEqual(self.plans(s, option('feed', expected='TendPatient'))['feed_hungry_colonist'], {})

    def test_native_carried_order_protects_patient_with_stale_combat_view(self):
        s = snapshot('Rescue')
        s['development']['resilience']['active_orders'] = [
            {'kind': 'rescue', 'worker_id': 3, 'target_id': 2, 'job_def': 'Rescue', 'carried_thing_id': 2}]
        self.assertEqual(self.plans(s, option(expected='Rescue'))['rescue_downed_colonist'], {})

    def test_nonimmune_minor_asthma_is_stable_but_real_disease_is_protected(self):
        h = {'def_name': 'Asthma', 'tendable_now': True, 'immunity': 0,
             'immunity_can_develop': False, 'lethal_severity': -1, 'life_threatening': False}
        patient = {'bleeding_rate': 0, 'health_conditions': [h]}
        self.assertTrue(care.stable_tend_patient(patient))
        h['life_threatening'] = True
        self.assertFalse(care.stable_tend_patient(patient))
        h.update(life_threatening=False, immunity_can_develop=True)
        self.assertFalse(care.stable_tend_patient(patient))

    def test_native_low_rate_healing_is_not_a_fabricated_bleedout(self):
        patient = {"bleeding_rate": .09, "health_conditions": [{"def_name": "BloodLoss", "severity": .99}],
                   "bleeding_evidence_complete": True, "bleedout_ticks": None}
        self.assertIsNone(care.clinical_deadline(patient))
        self.assertIn('no finite bleedout', care.patient_summary(patient))
        patient["starvation_ticks"] = 500
        self.assertEqual(care.clinical_deadline(patient), 500)
        patient.pop("starvation_ticks")
        patient["bleeding_rate"] = .1
        self.assertAlmostEqual(care.clinical_deadline(patient), 6000)
        # Native completeness distinguishes known low-rate healing from incomplete fixture evidence.
        s = snapshot("Rescue")
        s["colonists"][1].update(bleeding_rate=.09, health_conditions=[])
        row = option(expected="Rescue")
        self.assertEqual(self.plans(s, row)["rescue_downed_colonist"], {})
        s["development"]["resilience"]["patients"].append({"pawn_id": 2, "bleeding_evidence_complete": True, "bleedout_ticks": None})
        self.assertEqual(set(self.plans(s, row)["rescue_downed_colonist"]), {"1"})

    def test_malformed_binding_never_grants_care_override(self):
        for bad in (True, "2", None):
            s = snapshot("Rescue")
            row = option(expected="Rescue")
            row["expected_care_patient_id"] = bad
            self.assertEqual(self.plans(s, row)["rescue_downed_colonist"], {})


if __name__ == "__main__":
    unittest.main()

"""Public domain sequences with fresh observations and deterministic choices."""
import copy
import unittest
from unittest.mock import patch

import colony_production as production
import colony_resilience as resilience
import colony_society as society


class Chooser:
    def __init__(self, preferred=None):
        self.preferred = preferred or {}

    def predict(self, state, questions):
        question, row = next(iter(questions.items()))
        root = question.split("_round_")[0]
        criteria = row["criteria"]
        choice = self.preferred.get(root)
        if choice not in criteria:
            choice = next(k for k in criteria if k != "defer")
        return {"answers": {question: {"choice": choice}}}


class Http:
    def __init__(self, context, response):
        self.context = context
        self.response = response
        self.posts = []

    def get(self, path, **kwargs):
        return copy.deepcopy(self.context)

    def post(self, path, **kwargs):
        self.posts.append((path, kwargs))
        return copy.deepcopy(self.response)


def observation(domain, context, tick=100):
    return {"game": {"tick": tick}, "map": {"id": 0}, "colonists": [],
            "development": {domain: copy.deepcopy(context)}}


def logistics(target):
    return {"key": f"haul:{target}:1", "kind": "haul", "target_id": target,
            "worker_id": 1, "label": f"Haul stack {target}"}


class DomainCycleContracts(unittest.TestCase):
    def test_active_native_jobs_survive_dwell_and_release_without_permanent_lock(self):
        for kind in ("haul", "feed", "rescue"):
            with self.subTest(kind=kind):
                if kind == "haul":
                    module, domain, action = production, "production", "production_material_logistics"
                    rows = [logistics(p) for p in (1, 2)]
                    wrap = lambda native: {"logistics_context": native}
                else:
                    module, domain, action = resilience, "resilience", "resilience_" + kind
                    rows = [{"kind": kind, "worker_id": 7, "target_id": p, "giver": kind} for p in (1, 2)]
                    wrap = lambda native: native
                context = {"options": [rows[0]], "active_orders": []}
                state = {}
                client = Http(context, {"applied": True})
                first = observation(domain, wrap(context))
                module.prepare(first, state)
                selected, _ = module.choose(Chooser(), {}, action, first)
                self.assertTrue(module.execute(client, first, state, action, selected)["applied"])
                context = {"options": rows, "active_orders": [{"kind": kind, "worker_id": 7,
                    "target_id": 1, "job_def": "NativeJob", "carried_thing_id": None}]}
                client.context = context
                second = observation(domain, wrap(context), 20000)
                self.assertIn(action, module.prepare(second, state))
                selected, _ = module.choose(Chooser(), {}, action, second)
                self.assertEqual(2, selected.get("target_id") or int(selected["production_policy"].split(":")[1]))
                self.assertTrue(module.execute(client, second, state, action, selected)["applied"])
                context = {"options": rows, "active_orders": []}
                client.context = context
                third = observation(domain, wrap(context), 40000)
                self.assertIn(action, module.prepare(third, state))
                selected, _ = module.choose(Chooser(), {}, action, third)
                self.assertEqual(1, selected.get("target_id") or int(selected["production_policy"].split(":")[1]))
                self.assertEqual(2, len(client.posts))

    def test_active_native_job_appearing_between_choose_and_execute_blocks_post(self):
        for kind in ("haul", "feed", "rescue"):
            with self.subTest(kind=kind):
                if kind == "haul":
                    module, domain, action = production, "production", "production_material_logistics"
                    native = {"options": [logistics(1)], "active_orders": []}
                    context = {"logistics_context": native}
                else:
                    module, domain, action = resilience, "resilience", "resilience_" + kind
                    native = {"options": [{"kind": kind, "worker_id": 7, "target_id": 1, "giver": kind}], "active_orders": []}
                    context = native
                snap = observation(domain, context)
                state = {}
                module.prepare(snap, state)
                selected, _ = module.choose(Chooser(), {}, action, snap)
                native["active_orders"] = [{"kind": kind, "worker_id": 99, "target_id": 1, "job_def": "NativeJob"}]
                client = Http(native, {"applied": True})
                self.assertFalse(module.execute(client, snap, state, action, selected)["applied"])
                self.assertEqual([], client.posts)

    def test_downstream_care_defer_preserves_another_patient(self):
        cases = [
            (resilience, "resilience", "resilience_feed", {"patients": [{"pawn_id": p, "food": .2} for p in (2, 3)],
                "options": [{"kind": "feed", "worker_id": 1, "target_id": p, "giver": "FeedPatient"} for p in (2, 3)]},
                {"resilience_feed_patient": "2", "resilience_feed": "defer"}),
            (society, "society", "society_medical_care", {"people": [{"pawn_id": p, "medical_attention": True,
                "medical_care": "NoCare", "care_options": ["NoCare", "Best"]} for p in (2, 3)]},
                {"society_medical_care_person": "2", "society_medical_care": "defer"}),
        ]
        for module, domain, action, context, preferred in cases:
            with self.subTest(domain=domain):
                state = {}
                client = Http(context, {"applied": True})
                first = observation(domain, context)
                module.prepare(first, state)
                selected, _ = module.choose(Chooser(preferred), {}, action, first)
                self.assertFalse(module.execute(client, first, state, action, selected)["applied"])
                self.assertEqual([], client.posts)
                second = observation(domain, context, 101)
                self.assertIn(action, module.prepare(second, state))
                selected, _ = module.choose(Chooser(), {}, action, second)
                self.assertEqual(3, selected.get("target_id", selected.get("pawn_id")))
                self.assertTrue(module.execute(client, second, state, action, selected)["applied"])

    def test_production_acceptance_does_not_hide_another_target(self):
        context = {"options": [logistics(1)]}
        state = {"issued": {"production:production_material_logistics": 99}}
        client = Http(context, {"applied": True})
        first = observation("production", {"logistics_context": context})
        action = "production_material_logistics"
        self.assertIn(action, production.prepare(first, state))
        selected, _ = production.choose(Chooser(), {}, action, first)
        self.assertTrue(production.execute(client, first, state, action, selected)["applied"])
        second = observation("production", {"logistics_context": {"options": [logistics(1), logistics(2)]}}, 101)
        self.assertIn(action, production.prepare(second, state))
        selected, _ = production.choose(Chooser(), {}, action, second)
        self.assertEqual("haul:2:1", selected["production_policy"])
        self.assertNotIn("production:" + action, state["issued"])

    def test_production_denial_does_not_repeat_or_hide_other_target(self):
        context = {"options": [logistics(1), logistics(2)]}
        state = {}
        client = Http(context, {"applied": False, "reason": "reserved"})
        action = "production_material_logistics"
        with patch("colony_retry.time.time", return_value=1000):
            for tick, expected in ((100, "haul:1:1"), (101, "haul:2:1")):
                snap = observation("production", {"logistics_context": context}, tick)
                self.assertIn(action, production.prepare(snap, state))
                selected, _ = production.choose(Chooser(), {}, action, snap)
                self.assertEqual(expected, selected["production_policy"])
                self.assertFalse(production.execute(client, snap, state, action, selected)["applied"])
            third = observation("production", {"logistics_context": context}, 10000)
            self.assertNotIn(action, production.prepare(third, state))
        self.assertEqual(2, len(client.posts))

    def test_production_success_dwell_survives_worker_and_observation_drift(self):
        context = {"options": [logistics(1)]}
        state = {}
        client = Http(context, {"applied": True})
        action = "production_material_logistics"
        first = observation("production", {"logistics_context": context})
        production.prepare(first, state)
        selected, _ = production.choose(Chooser(), {}, action, first)
        production.execute(client, first, state, action, selected)
        alternate = {**logistics(1), "key": "haul:1:99", "worker_id": 99,
                     "position": {"x": 99, "z": 3}, "stock": 500, "label": "Moved stack"}
        second = observation("production", {"logistics_context": {"options": [alternate]}}, 101)
        self.assertNotIn(action, production.prepare(second, state))
        self.assertEqual(1, len(client.posts))

    def test_production_selected_subject_defer_does_not_hide_other_stack(self):
        context = {"options": [logistics(1), logistics(2)]}
        state = {}
        client = Http(context, {"applied": True})
        action = "production_material_logistics"
        first = observation("production", {"logistics_context": context})
        production.prepare(first, state)
        selected, _ = production.choose(Chooser({"production_logistics_policy": "defer"}), {}, action, first)
        self.assertFalse(production.execute(client, first, state, action, selected)["applied"])
        self.assertEqual([], client.posts)
        second = observation("production", {"logistics_context": context}, 101)
        self.assertIn(action, production.prepare(second, state))
        selected, _ = production.choose(Chooser(), {}, action, second)
        self.assertEqual("haul:2:1", selected["production_policy"])

    def test_care_malformed_acknowledgments_are_unknown_and_backed_off(self):
        cases = [
            (society, "society", "society_medical_care", {"people": [{"pawn_id": 2, "medical_attention": True,
                "medical_care": "NoCare", "care_options": ["NoCare", "Best"]}]}),
            (resilience, "resilience", "resilience_feed", {"patients": [{"pawn_id": 2, "food": .2}],
                "options": [{"kind": "feed", "worker_id": 1, "target_id": 2, "giver": "FeedPatient"}]}),
        ]
        for module, domain, action, context in cases:
            for response in ({"applied": "false"}, {"success": True}, None):
                with self.subTest(domain=domain, response=response), patch("colony_retry.time.time", return_value=1000):
                    state = {}
                    client = Http(context, response)
                    snap = observation(domain, context)
                    self.assertIn(action, module.prepare(snap, state))
                    selected, _ = module.choose(Chooser(), {}, action, snap)
                    result = module.execute(client, snap, state, action, selected)
                    self.assertIs(result["applied"], False)
                    self.assertTrue(result["outcome_unknown"])
                    self.assertNotIn(action, module.prepare(observation(domain, context, 10000), state))
                    self.assertEqual(1, len(client.posts))

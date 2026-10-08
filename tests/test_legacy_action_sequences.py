"""Offline sequences through real candidates, parameter selection and execution."""
import copy
import unittest

import colony_director as director


def pawn(pawn_id=1, priority=1):
    return {"id": pawn_id, "name": f"Worker {pawn_id}", "health": 1,
            "hunger": 1, "rest": 1, "position": {"x": 20, "z": 20},
            "skills": {"Construction": {"level": 5}},
            "work_priorities": {"Construction": {"priority": priority, "disabled": False}}}


def baseline():
    return {"game": {"tick": 12000},
            "map": {"id": 1, "resources": {"food": 100, "meals": 100, "nutrition": 90}},
            "colonists": [pawn()], "animals": [], "wild_animals": [], "combat": {},
            "development": {"building_counts": {"Bed": 1, "Campfire": 1},
                "buildings": [], "rooms": [], "zones": [], "things": [], "plants": [],
                "corpses": [], "work_tables": [], "item_counts": {}, "construction_projects": [],
                "weather": {"temperature": 20}}}


class FirstChoice:
    def predict(self, state, questions):
        return {"answers": {key: {"choice": next(iter(row["criteria"])), "confidence": 1}
                            for key, row in questions.items()}}


class World:
    """A stateful fake transport; successful requests change the next observation."""
    def __init__(self, snapshot):
        self.snapshot = copy.deepcopy(snapshot)
        self.sites = []
        self.bills = {}
        self.unknown_tables = set()
        self.fail_tables = set()
        self.mode = "success"
        self.calls = []

    def get(self, endpoint, **kwargs):
        self.calls.append(("get", endpoint, kwargs))
        dev = self.snapshot["development"]
        if endpoint == "/api/v1/buildings/bills":
            key = kwargs["building_id"]
            if key in self.unknown_tables:
                raise director.bridge.RimApiError("bill read unavailable")
            return copy.deepcopy(self.bills.get(key, []))
        if endpoint == "/api/v1/builder/projects":
            return {"projects": copy.deepcopy(dev["construction_projects"])}
        if endpoint == "/api/v1/map/buildings":
            return copy.deepcopy(dev["buildings"])
        if endpoint == "/api/v1/map/work-tables":
            return copy.deepcopy(dev["work_tables"])
        if endpoint == "/api/v2/colonists/detailed":
            return [{"id": p["id"], "name": p["name"], "work_info": {"work_priorities": [
                {"work_type": name, "priority": row["priority"], "is_totally_disabled": False}
                for name, row in p["work_priorities"].items()]}}
                for p in self.snapshot["colonists"]]
        return []

    def post(self, endpoint, **kwargs):
        self.calls.append(("post", endpoint, copy.deepcopy(kwargs)))
        dev = self.snapshot["development"]
        if endpoint == "/api/v1/builder/site-options":
            return {"sites": copy.deepcopy(self.sites)}
        applied = self.mode in {"success", "lost"}
        if endpoint == "/api/v1/buildings/bills/add":
            table = kwargs["query"]["building_id"]
            applied = applied and table not in self.fail_tables
            if applied:
                self.bills.setdefault(table, []).append(copy.deepcopy(kwargs["body"]))
                for row in dev["work_tables"]:
                    if row["id"] == table:
                        row["bills_count"] = len(self.bills[table])
        elif endpoint == "/api/v1/builder/blueprint" and applied:
            body = kwargs["body"]
            for i, row in enumerate(body["blueprint"]["buildings"]):
                point = {"x": body["position"]["x"] + row["rel_x"],
                         "z": body["position"]["z"] + row["rel_z"]}
                if row["def_name"] == "ButcherSpot":
                    dev["buildings"].append({"id": 50, "def": "ButcherSpot", "position": point})
                    dev["work_tables"].append({"id": 50, "thing_def": "ButcherSpot", "position": point,
                                               "bills_count": 0})
                else:
                    dev["construction_projects"].append({"thing_id": 50 + i, "def_name": row["def_name"],
                                                        "position": point})
        elif endpoint == "/api/v1/colonist/work-priority" and applied:
            body = kwargs["body"]
            for row in self.snapshot["colonists"]:
                if row["id"] == body["id"]:
                    row["work_priorities"][body["work"]]["priority"] = body["priority"]
        if self.mode == "lost" and endpoint != "/api/v1/builder/site-options":
            raise director.bridge.RimApiError("response lost")
        if endpoint == "/api/v1/builder/prioritize" and self.mode == "unknown":
            return {"success": True}
        return {"success": self.mode != "denied", "applied": applied}


class LegacyActionSequences(unittest.TestCase):
    def setUp(self):
        self.state = {"anchor": {"x": 20, "z": 20}, "issued": {"starter_base": 12000}}

    def candidates(self, world):
        snapshot = copy.deepcopy(world.snapshot)
        actions, details = director.candidate_actions(world, snapshot, self.state)
        return snapshot, actions, details

    def cycle(self, world, action):
        snapshot, actions, details = self.candidates(world)
        self.assertIn(action, actions)
        # Selecting a known offered action keeps the real conditional parameter cascade.
        decision = director.choose_action(FirstChoice(), snapshot, [action])
        details = director.merge_decision_details(details, decision)
        return director.execute_action(world, snapshot, self.state, action, details)

    def test_butcher_no_site_then_feasibility_change_and_lost_response(self):
        snap = baseline()
        snap["development"]["corpses"] = [{"thing_id": 99, "label": "deer",
            "categories": ["CorpsesAnimal"], "position": {"x": 22, "z": 22}}]
        world = World(snap)
        for _ in range(3):
            _, actions, _ = self.candidates(world)
            self.assertNotIn("build_butcher_spot", actions)
            focused = director.focus_imminent_food_choices(world.snapshot,
                actions + ["designate_safe_hunting", "prioritize_hunting"])
            self.assertIn("designate_safe_hunting", focused)
            world.snapshot["game"]["tick"] += 100
        world.sites = [{"position": {"x": 23, "z": 22}, "rotation": 1}]
        world.mode = "lost"
        result = self.cycle(world, "build_butcher_spot")
        self.assertTrue(result["applied"])
        self.assertTrue(result["bill_configured"])
        self.assertNotIn("build_butcher_spot", self.candidates(world)[1])
        queries = [kwargs["body"] for method, path, kwargs in world.calls
                   if method == "post" and path.endswith("site-options")]
        self.assertTrue(all(row["radius"] <= 24 for row in queries))
        self.assertEqual(queries[-1]["radius"], 1)

    def test_bill_unknown_table_partial_failure_new_table_and_lost_response(self):
        snap = baseline()
        snap["development"]["work_tables"] = [{"id": i, "thing_def": "Campfire", "bills_count": 0}
                                                  for i in (1, 2, 3)]
        world = World(snap)
        world.unknown_tables = {1}
        world.fail_tables = {3}
        result = self.cycle(world, "configure_food_bills")
        self.assertEqual(result["fulfilled_table_ids"], [2])
        self.assertEqual([row["table_id"] for row in result["failures"]], [3])
        self.assertNotIn("food_bills", self.state["issued"])
        _, _, details = self.candidates(world)
        self.assertEqual([row["id"] for row in details["food_bill_targets"]], [3])
        world.snapshot["development"]["work_tables"].append(
            {"id": 4, "thing_def": "Campfire", "bills_count": 0})
        world.fail_tables.clear()
        world.mode = "lost"
        result = self.cycle(world, "configure_food_bills")
        self.assertEqual(result["fulfilled_table_ids"], [3, 4])
        self.assertNotIn("configure_food_bills", self.candidates(world)[1])
        world.unknown_tables.clear()
        self.assertIn("configure_food_bills", self.candidates(world)[1])

    def test_butcher_exact_site_drift_is_revalidated_before_mutation(self):
        snap = baseline()
        snap["development"]["corpses"] = [{"thing_id": 99, "categories": ["CorpsesAnimal"],
                                            "position": {"x": 22, "z": 22}}]
        world = World(snap)
        world.sites = [{"position": {"x": 23, "z": 22}, "rotation": 0}]
        snapshot, actions, details = self.candidates(world)
        self.assertIn("build_butcher_spot", actions)
        decision = director.choose_action(FirstChoice(), snapshot, ["build_butcher_spot"])
        world.sites = [{"position": {"x": 24, "z": 22}, "rotation": 0}]
        result = director.execute_action(world, snapshot, self.state, "build_butcher_spot",
                                        director.merge_decision_details(details, decision))
        self.assertFalse(result["applied"])
        self.assertFalse(any(endpoint.endswith("/blueprint") for _, endpoint, _ in world.calls))
        self.assertEqual(self.candidates(world)[2]["butcher_site"]["position"], {"x": 24, "z": 22})

    def test_heating_denied_accepted_no_effect_then_lost_response(self):
        snap = baseline()
        dev = snap["development"]
        dev["weather"]["temperature"] = -10
        dev["item_counts"] = {"WoodLog": 30}
        dev["building_catalog"] = [{"def_name": "Campfire", "available_now": True}]
        dev["rooms"] = [{"id": 9, "contained_beds_ids": [7], "contained_thing_defs": ["Bed"],
                         "temperature": -5, "cells_count": 16, "open_roof_count": 0,
                         "cells": [{"x": x, "z": z} for x in range(20, 24) for z in range(20, 24)],
                         "light_placement_cells": [{"x": 22, "z": 22}]}]
        world = World(snap)
        world.sites = [{"position": {"x": 22, "z": 22}, "rotation": 0}]
        for mode in ("denied", "no_effect"):
            world.mode = mode
            result = self.cycle(world, "build_room_campfire")
            self.assertFalse(result["applied"])
            self.assertNotIn("heating_room:9", self.state["issued"])
        world.mode = "lost"
        self.assertTrue(self.cycle(world, "build_room_campfire")["applied"])
        self.assertNotIn("build_room_campfire", self.candidates(world)[1])

    def test_priority_unchanged_drift_and_new_recipient_inside_old_marker(self):
        world = World(baseline())
        world.snapshot["development"]["construction_projects"] = [
            {"thing_id": 75, "def_name": "Wall", "kind": "frame",
             "position": {"x": 21, "z": 21}, "label": "wall", "percent_complete": 0.8}
        ]
        self.state["issued"]["priority:Construction"] = 12000
        for _ in range(3):
            self.assertNotIn("prioritize_construction", self.candidates(world)[1])
            world.snapshot["game"]["tick"] += 10
        world.snapshot["colonists"].append(pawn(2, priority=3))
        world.snapshot["colonists"][-1]["skills"]["Construction"]["level"] = 2
        self.assertNotIn("prioritize_construction", self.candidates(world)[1])
        world.snapshot["colonists"][-1]["skills"]["Construction"]["level"] = 10
        world.mode = "no_effect"
        self.assertFalse(self.cycle(world, "prioritize_construction")["applied"])
        world.mode = "lost"
        result = self.cycle(world, "prioritize_construction")
        self.assertTrue(result["applied"])
        self.assertEqual(result["pawn_id"], 2)
        self.assertNotIn("prioritize_construction", self.candidates(world)[1])
        targets = [kwargs["body"]["id"] for method, endpoint, kwargs in world.calls
                   if method == "post" and endpoint.endswith("work-priority")]
        self.assertEqual(targets, [2, 2])

    def test_post_combat_tending_keeps_its_actor_while_another_worker_gets_food_work(self):
        s = baseline()
        s['map']['resources'] = {'food': 0, 'meals': 0, 'nutrition': 0}
        s['colonists'][0]['work_priorities']['PlantCutting'] = {'priority': 2, 'disabled': False}
        doctor, patient = pawn(2), pawn(3)
        doctor.update(current_job='TendPatient', current_job_target_id=3)
        patient.update(downed=True, current_job='LayDown')
        s['colonists'] += [doctor, patient]
        s['combat'] = {'colonists': [dict(p, is_drafted=False, is_downed=p.get('downed', False))
                                   for p in s['colonists']],
            'hostiles': [{'id': 9, 'kind_def': 'Human', 'is_downed': True, 'bleeding_rate': .5}]}
        world = World(s)
        self.assertEqual(director.independent_development_workers(world.snapshot), {1})
        result = director.execute_action(world, world.snapshot, self.state, 'prioritize_plant_cutting', {})
        self.assertTrue(result['applied'])
        self.assertEqual(result['pawn_id'], 1)
        self.assertEqual(doctor['current_job'], 'TendPatient')
        self.assertTrue(all(kw['body']['id'] == 1 for method, path, kw in world.calls
                            if method == 'post' and path.endswith('work-priority')))
        world.snapshot['combat']['hostiles'][0]['is_downed'] = False
        self.assertEqual(director.independent_development_workers(world.snapshot), set())
        world.snapshot['combat']['hostiles'][0].update(is_downed=True, kind_def='Shambler', bleeding_rate=0)
        self.assertEqual(director.independent_development_workers(world.snapshot), set())

    def test_project_rejection_or_unknown_response_retires_only_exact_project(self):
        for mode in ("denied", "no_effect", "unknown"):
            with self.subTest(mode=mode):
                self.state = {"anchor": {"x": 20, "z": 20}, "issued": {"starter_base": 12000}}
                snap = baseline()
                project = {"thing_id": 75, "def_name": "Wall", "kind": "frame",
                           "position": {"x": 21, "z": 21}, "label": "wall", "percent_complete": 0.8}
                snap["development"]["construction_projects"] = [project]
                world = World(snap)
                world.mode = mode
                result = self.cycle(world, "prioritize_construction_project")
                self.assertFalse(result["applied"])
                self.assertNotIn("construction_project:75", self.state["issued"])
                self.assertNotIn("construction_project_priority", self.state["issued"])
                self.assertNotIn("prioritize_construction_project", self.candidates(world)[1])
                world.snapshot["game"]["tick"] += 20
                self.assertNotIn("prioritize_construction_project", self.candidates(world)[1])
                world.snapshot["development"]["construction_projects"].append({**project, "thing_id": 76})
                world.mode = "success"
                result = self.cycle(world, "prioritize_construction_project")
                self.assertTrue(result["applied"])
                self.assertEqual(result["project_id"], 76)
                self.assertIn("construction_project:76", self.state["issued"])


if __name__ == "__main__":
    unittest.main()

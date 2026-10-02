import unittest
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import colony_progression as p
from laya_decisions import _consequence_state


def project(name, **kw):
    return {"name": name, "can_start_now": True, "player_has_any_appropriate_research_bench": True, **kw}


class ProgressionTests(unittest.TestCase):
    def test_deliberate_defer_suppresses_choice_and_rollbacks_expire_it(self):
        ship = {"map_id": 1, "root_id": 2, "parts": {"engine": 3}, "required_parts": {"engine": 3}, "has_hibernating_parts": True}
        snapshot = {"game": {"tick": 20000}, "development": {"progression": {"native_milestones": [ship]}}}
        map_state = {}
        self.assertIn("progression_ship", p.prepare(snapshot, map_state))
        result = p.execute(None, snapshot, map_state, "progression_ship", {"defer": True})
        self.assertFalse(result["applied"])
        snapshot["game"]["tick"] = 20001
        self.assertNotIn("progression_ship", p.prepare(snapshot, map_state))
        snapshot["game"]["tick"] = 35000
        self.assertIn("progression_ship", p.prepare(snapshot, map_state))
        snapshot["game"]["tick"] = 10000
        self.assertIn("progression_ship", p.prepare(snapshot, map_state))
        self.assertNotIn("progression:progression_ship", map_state["progression_cooldowns"])

    def test_applied_boarding_cooldown_is_short_and_research_longer(self):
        state = {}
        snapshot = {"game": {"tick": 50000}}
        p._record_cooldown(snapshot, state, "progression_boardship")
        p._record_cooldown(snapshot, state, "progression_research")
        snapshot["game"]["tick"] = 50599
        self.assertTrue(p._cooling(snapshot, state, "progression_boardship"))
        snapshot["game"]["tick"] = 50600
        self.assertFalse(p._cooling(snapshot, state, "progression_boardship"))
        self.assertTrue(p._cooling(snapshot, state, "progression_research"))
        snapshot["game"]["tick"] = 80000
        self.assertFalse(p._cooling(snapshot, state, "progression_research"))

    def test_bounded_ship_risk_retains_native_days_and_outside_passengers(self):
        class Tokenizer:
            def __call__(self, text, **kwargs):
                return {"input_ids": list(range((len(text) + 2) // 3))}
        class Agent:
            tok = Tokenizer()
            cfg = {"max_len": 512, "head_max_len": 192}
        start = {"map_id": 1, "root_id": 2, "parts": {"engine": 3}, "required_parts": {"engine": 3}, "has_hibernating_parts": True,
                 "startup_days": 15.0, "armed_mobile_combat_colonists": 1, "downed_colonists": 2}
        launch = {"map_id": 1, "root_id": 3, "launch_blockers": [], "passengers": ["A"], "colonists_at_home": ["B", "C"]}
        candidates, choices, effects, facts = p.comparison("progression_ship", {"native_milestones": [start, launch]})
        # Artificially huge benefits must not erase separate native risks.
        for row in effects.values():
            row["benefit"] += " verbose " * 500
        for key, row in candidates.items():
            pair = {key: choices[key], "defer": choices["defer"]}
            visible = _consequence_state(Agent(), {"option_effects": effects, "decision_facts": facts}, pair)
            self.assertLessEqual(len(Agent.tok(json.dumps(visible, ensure_ascii=False))["input_ids"]), 312)
            risk = visible["effects"][key]["risk"]
            self.assertIn("15.0 days" if row["ship_action"] == "start" else "2 unboarded", risk)
            self.assertEqual(set(visible["effects"][key]), {"benefit", "risk", "cost", "inaction", "uncertainty"})

    def test_bounded_boarding_risk_starts_with_last_roles(self):
        row = {"map_id": 1, "root_id": 2, "pawn_id": 3, "worker_id": 3, "casket_id": 4,
               "remaining_armed_mobile_combat_colonists": 0, "remaining_mobile_doctors": 0, "pawn": "A"}
        _, _, effects, facts = p.comparison("progression_boardship", {"native_milestones": [{"boarding_options": [row]}]})
        key = next(k for k in effects if k != "defer")
        self.assertTrue(effects[key]["risk"].startswith("0 armed / 0 doctors remain"))
        self.assertIn("last_roles", facts)

    def test_installed_core_casket_and_reactor_source_facts(self):
        path = Path("C:/Program Files (x86)/Steam/steamapps/common/RimWorld/Data/Core/Defs/ThingDefs_Buildings/Buildings_Ship.xml")
        if not path.exists():
            self.skipTest("installed RimWorld definitions unavailable")
        defs = {node.findtext("defName"): node for node in ET.parse(path).getroot()}
        self.assertEqual(defs["Ship_CryptosleepCasket"].findtext("building/isPlayerEjectable"), "true")
        self.assertEqual(defs["Ship_Reactor"].findtext("comps/li[@Class='CompProperties_Hibernatable']/incidentTargetWhileStarting"), "Map_RaidBeacon")

    def test_native_boarding_uses_jobs_and_preserves_active_care(self):
        path = Path(__file__).resolve().parents[1] / "vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/ProgressionBoardingHelper.cs"
        source = path.read_text(encoding="utf-8-sig")
        for job in ("TendPatient", "Rescue", "FeedPatient", "DoBill"):
            self.assertIn(f'"{job}"', source)
        self.assertIn("JobMaker.MakeJob(JobDefOf.CarryToCryptosleepCasket, pawn, casket)", source)
        self.assertIn("JobMaker.MakeJob(JobDefOf.EnterCryptosleepCasket, casket)", source)
        self.assertIn("worker.jobs.TryTakeOrderedJob(job, JobTag.Misc)", source)
        self.assertNotIn("TryAcceptThing(", source)

    def test_collect_filters_selected_map(self):
        class Client:
            def get(self, endpoint, **params):
                if endpoint.endswith("progression"):
                    self.native_query = params
                return [{"map_id": 1}, {"map_id": 2}] if endpoint.endswith("progression") else {}
        client = Client()
        self.assertEqual(p.collect(client, {"map": {"id": 2}})["native_milestones"], [{"map_id": 2}])
        self.assertEqual(client.native_query, {"map_id": 2})

    def test_normal_boarding_job_success_ignores_director_metadata(self):
        row = {"map_id": 1, "root_id": 2, "pawn_id": 3, "worker_id": 3, "casket_id": 4,
               "job": "EnterCryptosleepCasket", "reactor_running": True, "pawn_downed": False}
        ship = {"map_id": 1, "boarding_options": [row]}
        selected = next(iter(p.boarding_options({"native_milestones": [ship]}).values()))
        class Client:
            def get(self, endpoint, **params):
                return [ship] if endpoint.endswith("progression") else {}
            def post(self, endpoint, **kwargs):
                self.endpoint, self.query = endpoint, kwargs["query"]
                return "boarding_job_started"
        client = Client()
        result = p.execute(client, {"map": {"id": 1}}, {}, "progression_boardship", {**selected, "director_reason": "leave", "confidence": .8})
        self.assertTrue(result["applied"])
        self.assertFalse(result["boarding_complete"])
        self.assertEqual(client.endpoint, "/api/v1/colony/progression/board")
        self.assertEqual(client.query["worker_id"], 3)
        self.assertNotIn("director_reason", client.query)

    def test_boarding_paused_for_hostiles_and_failed_job_honest(self):
        row = {"map_id": 1, "root_id": 2, "pawn_id": 3, "worker_id": 5, "casket_id": 4, "job": "CarryToCryptosleepCasket"}
        self.assertFalse(p.boarding_options({"native_milestones": [{"hostile_pawns": 1, "boarding_options": [row]}]}))
        ship = {"boarding_options": [row]}
        selected = next(iter(p.boarding_options({"native_milestones": [ship]}).values()))
        class Client:
            def get(self, endpoint, **params):
                return [ship] if endpoint.endswith("progression") else {}
            def post(self, *args, **kwargs):
                return "boarding_not_started"
        self.assertFalse(p.execute(Client(), {}, {}, "progression_boardship", selected)["applied"])

    def test_ship_changed_passengers_rejected(self):
        selected = {"map_id": 1, "root_id": 4, "ship_action": "launch", "passengers": ["A"]}
        class Client:
            def get(self, endpoint, **params):
                return [{**selected, "passengers": ["B"], "launch_blockers": []}] if endpoint.endswith("progression") else {}
            def post(self, *args, **kwargs):
                raise AssertionError("must not launch changed passenger set")
        self.assertFalse(p.execute(Client(), {}, {}, "progression_ship", selected)["applied"])

    def test_launch_is_countdown_not_verified_victory(self):
        selected = {"map_id": 1, "root_id": 4, "ship_action": "launch", "passengers": ["A"], "launch_blockers": []}
        class Client:
            def get(self, endpoint, **params):
                return [selected] if endpoint.endswith("progression") else {}
            def post(self, endpoint, **kwargs):
                self.query = kwargs["query"]
                return "launch_countdown_started"
        client = Client()
        result = p.execute(client, {}, {}, "progression_ship", selected)
        self.assertTrue(result["applied"])
        self.assertFalse(result["victory_verified"])
        self.assertTrue(client.query["confirmed"])

    def test_ship_requires_engine_readiness_and_passengers(self):
        base = {"map_id": 1, "root_id": 4, "parts": {"Ship_Engine": 3}, "required_parts": {"Ship_Engine": 3}, "launch_blockers": [], "passengers": []}
        self.assertEqual(p.ship_options({"native_milestones": [base]}), {})
        self.assertEqual(next(iter(p.ship_options({"native_milestones": [{**base, "passengers": ["A"]}]}).values()))["ship_action"], "launch")
        self.assertEqual(next(iter(p.ship_options({"native_milestones": [{**base, "has_hibernating_parts": True}]}).values()))["ship_action"], "start")

    def test_collect_reuses_shared_research(self):
        class Client:
            def get(self, endpoint, **params):
                self.endpoint = endpoint
                return []
        client = Client()
        p.collect(client, {"development": {"research_tree": [], "current_research": {}}})
        self.assertEqual(client.endpoint, "/api/v1/colony/progression")

    def test_hidden_prerequisite_frontier_and_cycle(self):
        tree = [project("ShipBasics", can_start_now=False, hidden_prerequisites=["Microelectronics"]),
                project("Microelectronics", prerequisites=["ShipBasics"])]
        result = p.research_frontier(tree, ["ShipBasics"])
        self.assertEqual(result["frontier"], ["Microelectronics"])
        self.assertFalse(result["complete"])

    def test_missing_bench_is_not_actionable(self):
        self.assertEqual(p.research_frontier([project("ShipBasics", player_has_any_appropriate_research_bench=False)], ["ShipBasics"])["frontier"], [])

    def test_no_victory_from_research(self):
        class Client:
            def get(self, endpoint, **params):
                return {"projects": [project(n, is_finished=True) for n in p.SHIP_RESEARCH]} if endpoint.endswith("tree") else {}
        result = p.collect(Client(), {})
        self.assertTrue(result["ship_research"]["complete"])
        self.assertFalse(result["victory_verified"])

    def test_stale_project_prevents_mutation(self):
        class Client:
            def get(self, endpoint, **params):
                return {"projects": [project("ShipBasics", can_start_now=False)]} if endpoint.endswith("tree") else {}
            def post(self, *args, **kwargs):
                raise AssertionError("must not mutate")
        self.assertFalse(p.execute(Client(), {}, {}, "progression_research", {"name": "ShipBasics"})["applied"])

    def test_native_target_without_force_and_confirmed(self):
        class Client:
            def get(self, endpoint, **params):
                return {"projects": [project("ShipBasics")]} if endpoint.endswith("tree") else {}
            def post(self, endpoint, **kwargs):
                self.query = kwargs["query"]
                return {"name": "ShipBasics"}
        client = Client()
        self.assertTrue(p.execute(client, {}, {}, "progression_research", {"name": "ShipBasics"})["applied"])
        self.assertIs(client.query["force"], False)


if __name__ == "__main__":
    unittest.main()

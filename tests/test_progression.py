import unittest
from unittest.mock import patch
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
            endpoints = []
            def get(self, endpoint, **params):
                self.endpoints.append(endpoint)
                return {} if "endings" in endpoint else []
        client = Client()
        p.collect(client, {"development": {"research_tree": [], "current_research": {}}})
        self.assertEqual(client.endpoints, ["/api/v1/colony/progression", "/api/v1/colony/endings", "/api/v1/colony/endings/selection", "/api/v1/colony/endings/continuation", "/api/v1/colony/endings/odyssey", "/api/v1/colony/endings/world-targeting"])

    def test_ending_options_require_native_eligibility_and_stop_on_credits(self):
        native = {"quests": [{"quest_id": 2, "can_accept": True, "requires_accepter": True, "accepter_ids": [4]},
                            {"quest_id": 3, "can_accept": False}], "site_jobs": []}
        self.assertEqual(list(p.ending_options({"endings": native})), ["quest_2_4"])
        self.assertEqual(p.ending_options({"endings": {**native, "victory_verified": True}}), {})

    def test_sale_selection_preserves_explicit_people_and_native_limits(self):
        selection = {"available": True, "can_submit": False, "rows": [{"thing_id": 7, "label": "Doctor", "selected": False, "category": "colonists"}]}
        choices = p.ending_options({"ending_selection": selection})
        self.assertEqual(choices["transfer_7"]["selected"], True)
        self.assertNotIn("submit_transfer", choices)
        choices = p.ending_options({"ending_selection": {**selection, "can_submit": True}})
        self.assertEqual(choices["submit_transfer"]["operation"], "submit")

    def test_stale_ending_job_does_not_execute(self):
        chosen = {"map_id": 1, "thing_id": 2, "pawn_id": 3, "label": "Invoke", "kind": "job", "current_job": "Wait"}
        class Client:
            def get(self, endpoint, **kwargs):
                if endpoint == "/api/v1/colony/endings":
                    return {"site_jobs": [{**chosen, "current_job": "TendPatient"}]}
                return {} if "endings" in endpoint else []
            def post(self, *args, **kwargs):
                raise AssertionError("Stale ending action must never be issued")
        result = p.execute(Client(), {"map": {"id": 1}}, {}, "progression_ending", chosen)
        self.assertFalse(result["applied"])

    def test_odyssey_doctrine_matches_native_support_route(self):
        context = {"support_research": {"odyssey_mechhive": {"frontier": []}}}
        snapshot = {"development": {"progression": context}}
        p.prepare(snapshot, {"doctrine": {"endgame": "mechhive"}})
        self.assertEqual(context["chosen_ending_route"], "odyssey_mechhive")
        self.assertEqual(context["chosen_route_support"], {"frontier": []})

    def test_ending_quest_survives_elapsed_ticks_but_requires_live_eligibility(self):
        quest_offer = {"id": 31, "quest_def": "EndGame_RoyalAscent", "name": "Royal ascent",
            "description": "Host the royal guests and defend them before departing.", "can_accept": True,
            "state": "NotYetAccepted", "requires_accepter": True, "eligible_accepters": [{"pawn_id": 7}],
            "reward_groups": [], "offer_version": "terms-v1"}
        offer = {"quest_id": 31, "route": "EndGame_RoyalAscent", "label": "Royal ascent",
                 "state": "NotYetAccepted", "can_accept": True, "requires_accepter": True,
                 "accepter_ids": [7], "expires_in_ticks": 9000, "quest_offer": quest_offer}
        chosen = next(iter(p.ending_options({"endings": {"quests": [offer]}}).values()))
        class Agent:
            def predict(self, state, questions):
                key, q = next(iter(questions.items()))
                return {"answers": {key: {"choice": next(iter(q["criteria"]))}}}
        _, _, plan = p.quests.review(Agent(), quest_offer, {})
        chosen["quest_plan"] = plan
        class Client:
            eligible = True
            calls = []
            def get(self, endpoint, **params):
                if endpoint == "/api/v1/colony/endings":
                    return {"quests": [{**offer, "expires_in_ticks": 8800, "can_accept": self.eligible}]}
                if endpoint == "/api/v1/quest/offer":
                    return {**quest_offer, "can_accept": self.eligible}
                return [] if endpoint.endswith("progression") else {}
            def post(self, endpoint, **params):
                self.calls.append((endpoint, params))
                return {"success": True}
        client = Client()
        with patch('rimworld_laya.collect_snapshot', return_value={}):
            result = p.execute(client, {}, {}, "progression_ending", {**chosen, "director_reason": "advance", "confidence": .9})
        self.assertTrue(result["applied"])
        self.assertFalse(result["victory_verified"])
        self.assertEqual(client.calls, [("/api/v1/quest/accept", {"body": {
            "quest_id": 31, "accepter_pawn_id": 7, "offer_version": "terms-v1", "reward_choices": []}})])
        client.eligible = False
        self.assertFalse(p.execute(client, {}, {}, "progression_ending", chosen)["applied"])
        self.assertEqual(len(client.calls), 1)

    def test_native_credits_stop_all_progression_and_inflight_mutations(self):
        ship = {"map_id": 1, "root_id": 4, "launch_blockers": [], "passengers": ["A"]}
        context = {"endings": {"victory_verified": True}, "native_milestones": [ship],
                   "research_tree": [project("ShipBasics")]}
        self.assertEqual(p.prepare({"development": {"progression": context}}, {}), [])
        class Client:
            def get(self, endpoint, **params):
                if endpoint == "/api/v1/colony/endings":
                    return {"victory_verified": True, "ending_route": "ship_escape", "ending_tick": 500}
                return [ship] if endpoint.endswith("progression") else {}
            def post(self, *args, **params):
                raise AssertionError("Credits must stop an already selected mutation")
        for action in p.ACTIONS:
            result = p.execute(Client(), {}, {}, action, {"name": "ShipBasics", "ship_action": "launch", **ship})
            self.assertFalse(result["applied"])
            self.assertTrue(result["victory_verified"])

    def test_existing_ship_journey_contract_then_arrival_and_launch(self):
        plan = {"map_id": 1, "object_id": 70, "team": "migration", "supply_days": 15,
                "route": "ship_journey", "pawn_ids": [3, 4], "travelers": ["A", "B"],
                "colonists_at_home": [], "food_nutrition": 48.0, "home_food_nutrition": 0,
                "medicine_count": 4, "mass": 20.0, "capacity": 70.0}
        class Client:
            arrived = False
            calls = []
            def get(self, endpoint, **params):
                if endpoint.endswith("/journey"):
                    return {"journeys": [] if self.arrived else [plan]}
                if endpoint.endswith("/progression"):
                    return [{"map_id": 2, "root_id": 90, "launch_blockers": [], "passengers": ["A", "B"], "colonists_at_home": []}] if self.arrived else []
                return {}
            def post(self, endpoint, **params):
                self.calls.append((endpoint, params["query"]))
                return "ending_caravan_forming" if endpoint.endswith("/journey") else "launch_countdown_started"
        client = Client()
        before = p.collect(client, {"map": {"id": 1}})
        selected = next(iter(p.ending_options(before).values()))
        result = p.execute(client, {"map": {"id": 1}}, {}, "progression_ending", selected)
        self.assertTrue(result["applied"])
        self.assertFalse(result["victory_verified"])
        self.assertEqual(client.calls[0], ("/api/v1/colony/endings/journey", {"map_id": 1, "object_id": 70, "team": "migration", "supply_days": 15, "pawn_ids": "3,4", "home_pawn_ids": "", "manifest": "", "confirmed": True}))
        client.arrived = True
        after = p.collect(client, {"map": {"id": 2}})
        self.assertEqual(p.ending_options(after), {})
        ship = next(iter(p.ship_options(after).values()))
        launched = p.execute(client, {"map": {"id": 2}}, {}, "progression_ship", ship)
        self.assertTrue(launched["applied"])
        self.assertFalse(launched["victory_verified"])

    def test_changed_journey_travelers_or_supplies_require_new_choice(self):
        plan = {"map_id": 1, "object_id": 70, "team": "scout", "supply_days": 5, "pawn_ids": [3, 4], "food_nutrition": 16}
        selected = {**plan, "kind": "journey"}
        class Client:
            def get(self, endpoint, **params):
                return {"journeys": [{**plan, "pawn_ids": [3, 5]}]} if endpoint.endswith("/journey") else [] if endpoint.endswith("/progression") else {}
            def post(self, *args, **params):
                raise AssertionError("Changed journey must not start")
        self.assertFalse(p.execute(Client(), {"map": {"id": 1}}, {}, "progression_ending", selected)["applied"])

    def test_ship_journey_doctrine_does_not_request_self_build_research(self):
        context = {"research_tree": [project("ShipBasics")] , "ship_research": {"frontier": ["ShipBasics"]}}
        snapshot = {"development": {"progression": context}}
        self.assertEqual(p.prepare(snapshot, {"doctrine": {"endgame": "ship_journey"}}), [])

    def test_journey_native_food_and_destination_contract(self):
        source = (Path(__file__).resolve().parents[1] / "vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Controllers/Colony/EndingJourneyController.cs").read_text(encoding="utf-8-sig")
        # Native assembly APIs are the contract for gene/food-policy dependent
        # rates and edibility. A generic fixed rate or raw nutrition total cannot
        # establish that a restrictive-diet traveler has a usable supply.
        for native in ("CaravanPawnsNeedsUtility.CanEatForNutritionEver(food.def, p)",
                       "CurrentFoodPolicy?.filter.Allows(food)", "food.IngestibleNow",
                       "t.TryGetComp<CompRottable>() == null",
                       "NutritionBetweenHungryAndFed", "TicksUntilHungryWhenFedIgnoringMalnutrition",
                       "DaysWorthOfFoodCalculator.ApproxDaysWorthOfFood", "IgnorePawnsInventoryMode.Ignore",
                       "CaravanTicksPerMoveUtility.GetTicksPerMove", "CaravanArrivalTimeEstimator.EstimatedTicksToArrive",
                       "nativeDays < estimate.Days.Value + 1f", "Math.Ceiling(estimate.Days.Value + 2f)",
                       "!q.hidden && !q.dismissed", "s.sitePartsKnown", "!s.parts.Any(p => p.hidden)",
                       "CaravanArrivalAction_VisitEscapeShip", "LookMode.Deep"):
            self.assertIn(native, source)
        self.assertNotIn("1.6f", source)

    def test_native_journey_eta_drift_preserves_order_but_changed_route_cost_rejects(self):
        plan = {"map_id": 1, "object_id": 70, "team": "migration", "supply_days": 15, "pawn_ids": [3],
                "travel_days": 8.0, "food_margin_days": 7.0, "native_approx_food_days": 15.0}
        selected = {**plan, "kind": "journey"}
        class Client:
            travel_days = 8.1
            calls = 0
            def get(self, endpoint, **params):
                if endpoint.endswith("/journey"):
                    return {"journeys": [{**plan, "travel_days": self.travel_days, "food_margin_days": 15.0 - self.travel_days}]}
                return [] if endpoint.endswith("/progression") else {}
            def post(self, *args, **params):
                self.calls += 1
                return "ending_caravan_forming"
        client = Client()
        self.assertTrue(p.execute(client, {"map": {"id": 1}}, {}, "progression_ending", selected)["applied"])
        client.travel_days = 11.0
        self.assertFalse(p.execute(client, {"map": {"id": 1}}, {}, "progression_ending", selected)["applied"])
        self.assertEqual(client.calls, 1)

    def test_unavailable_journey_exposes_ration_research_without_order(self):
        readiness = {"journeys": [], "readiness": [{"object_id": 70, "route": "ship_journey", "label": "Revealed ship",
                      "blockers": ["insufficient food edible and policy-allowed for every traveler"], "acceptable_stock_nutrition": 0}],
                     "support_research_targets": ["PackagedSurvivalMeal"], "ration_production": [{"name": "CookMealSurvival", "research": "PackagedSurvivalMeal"}]}
        class Client:
            def get(self, endpoint, **params):
                if endpoint.endswith("/journey"):
                    return readiness
                if endpoint.endswith("/tree"):
                    return {"projects": [project("PackagedSurvivalMeal")]}
                return [] if endpoint.endswith("/progression") else {}
            def post(self, *args, **params):
                raise AssertionError("No supply means no journey order")
        context = p.collect(Client(), {"map": {"id": 1}})
        self.assertEqual(p.ending_options(context), {})
        snapshot = {"development": {"progression": context}}
        self.assertEqual(p.prepare(snapshot, {"doctrine": {"endgame": "ship_journey"}}), ["progression_research"])
        self.assertEqual(context["chosen_route_support"]["frontier"], ["PackagedSurvivalMeal"])
        _, _, _, facts = p.comparison("progression_research", context)
        self.assertEqual(facts["journey_needs"]["research"], ["PackagedSurvivalMeal"])
        self.assertEqual(facts["journey_needs"]["blockers"], ["diet-allowed survival meals missing"])
        self.assertEqual(p.summary(snapshot)["journey_blockers"], 1)
        self.assertFalse(p.execute(Client(), {"map": {"id": 1}}, {}, "progression_ending", {"kind": "journey", "object_id": 70})["applied"])

    def test_journey_freshness_keeps_reserve_drift_but_binds_manifest_and_roster(self):
        plan = {"kind": "journey", "map_id": 1, "object_id": 70, "pawn_ids": [3],
                "home_pawn_ids": [4], "manifest": [{"def_name": "MealSurvivalPack", "count": 50}],
                "home_food_nutrition": 100, "food_margin_days": 2, "medicine_count": 4}
        self.assertTrue(p._ending_unchanged(plan, {**plan, "home_food_nutrition": 99.1}))
        for changed in ({"home_pawn_ids": [5]}, {"medicine_count": 3},
                        {"manifest": [{"def_name": "MealSurvivalPack", "count": 49}]}, {"food_margin_days": -1}):
            self.assertFalse(p._ending_unchanged(plan, {**plan, **changed}))

    def test_boarding_ordinary_job_progress_is_allowed_but_care_is_not(self):
        row = {"map_id": 1, "root_id": 2, "pawn_id": 3, "worker_id": 3, "casket_id": 4,
               "job": "EnterCryptosleepCasket", "current_job": "Goto"}
        selected = next(iter(p.boarding_options({"native_milestones": [{"boarding_options": [row]}]}).values()))
        class Client:
            job = "Wait"
            calls = 0
            def get(self, endpoint, **params):
                return [{"boarding_options": [{**row, "current_job": self.job}]}] if endpoint.endswith("progression") else {}
            def post(self, *args, **kwargs):
                self.calls += 1
                return "boarding_job_started"
        client = Client()
        self.assertTrue(p.execute(client, {}, {}, "progression_boardship", selected)["applied"])
        client.job = "TendPatient"
        self.assertFalse(p.execute(client, {}, {}, "progression_boardship", selected)["applied"])
        self.assertEqual(client.calls, 1)

    def test_empty_landing_waits_without_model_and_recovers(self):
        import colony_sessions as sessions
        from unittest.mock import patch
        context = {"odyssey": {"landing": True, "landings": [], "landing_blocker": "No viable native cell"}}
        snapshot = {"development": {"progression": context}}
        selected, raw = p.choose(None, {}, "progression_ending", snapshot)
        self.assertTrue(selected["blocked"])
        class Client:
            def get(self, *args, **kwargs): return []
        state = {}
        with patch.object(sessions.colony_modules, "modules", return_value=[p]), \
             patch.object(p, "peek_pending", return_value=True), patch.object(p, "collect", return_value=context), \
             patch.object(p, "prepare"), patch.object(p, "choose", side_effect=AssertionError("No model")):
            first = sessions.run_pending(Client(), None, {}, state, world_only=True)
            second = sessions.run_pending(Client(), None, {}, state, world_only=True)
        self.assertEqual(first["mode"], "native-continuation-wait")
        self.assertEqual(first["result"]["reason"], "No viable native cell")
        self.assertTrue(second["quiet"])
        context["odyssey"].update(landing_session="L1", landings=[{"operation": "view_landing_map", "map_id": 7}])
        option = next(iter(p.ending_options(context).values()))
        self.assertEqual(option["session"], "L1")
        with patch.object(sessions.colony_modules, "modules", return_value=[p]), \
             patch.object(p, "peek_pending", return_value=True), patch.object(p, "collect", return_value=context), \
             patch.object(p, "prepare"), patch.object(p, "choose", return_value=(option, {})), \
             patch.object(sessions.colony_modules, "execute", return_value={"applied": True}):
            recovered = sessions.run_pending(Client(), None, {}, state, world_only=True)
        self.assertEqual(recovered["mode"], "native-continuation")
        self.assertNotIn("blocked_native_continuation", state)

    def test_native_formation_uses_persisted_lord_callback_and_invalidates_cancellation(self):
        source = Path("vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Controllers/Colony/EndingJourneyController.cs").read_text()
        self.assertIn('Scribe_References.Look(ref FormingLord, "formingLord")', source)
        self.assertIn('map.lordManager.lords.Contains(route.FormingLord)', source)
        self.assertIn('Routes.FirstOrDefault(r => r.FormingLord == formingLord)', source)
        self.assertIn('CaravanCreated(__state, __result)', source)
        self.assertIn('job.downedPawns.Any()', source)
        self.assertIn('Saved journey has no native formation identity', source)
        self.assertNotIn('Find.WorldObjects.Caravans', source.split('public class EndingJourneyPlan')[0])
        self.assertIn('homeIds = RequestParser.GetStringParameter(context, "home_pawn_ids", required: false) ?? ""', source)

    def test_landing_recovery_posts_identity_and_fresh_session_rejects(self):
        row = {"operation": "view_landing_map", "map_id": 7, "rotation": 0}
        class Client:
            session = "L1"
            calls = []
            def get(self, endpoint, **params):
                return {"landing": True, "landing_session": self.session, "landings": [row]} if endpoint.endswith("/odyssey") else {}
            def post(self, endpoint, **kwargs):
                self.calls.append(kwargs["query"])
                return "gravship_landing_map_selected"
        client = Client()
        selected = next(iter(p.ending_options(p.collect(client, {})).values()))
        self.assertTrue(p.execute(client, {}, {}, "progression_ending", selected)["applied"])
        self.assertEqual(client.calls[0], {"operation": "view_landing_map", "map_id": 7, "rotation": 0, "session": "L1", "confirmed": True})
        client.session = "L2"
        self.assertFalse(p.execute(client, {}, {}, "progression_ending", selected)["applied"])
        self.assertEqual(len(client.calls), 1)
        source = Path("vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Controllers/Colony/EndingOdysseyController.cs").read_text()
        self.assertIn('Current.Game.CurrentMap = designator.map', source)
        self.assertIn('GetStringParameter(context, "session") != Session(marker)', source)
        self.assertIn('LandingSearchCursor + 256', source)
        self.assertIn('LandingSearchCells.RemoveAll(cell => !designator.CanDesignateCell(cell).Accepted)', source)
        self.assertIn('TotalSeconds >= 30', source)

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

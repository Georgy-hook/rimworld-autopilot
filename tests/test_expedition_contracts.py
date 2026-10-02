import copy
from pathlib import Path
import unittest
from unittest import mock
import colony_expeditions as expeditions
import colony_director as director
import colony_events as events
from laya_decisions import ask_laya_choice
from tests.test_affordances import Agent


class Client:
    def __init__(self, preview, result=None):
        self.preview, self.result, self.posts = preview, result or {"applied": True, "status": "forming", "formation_id": "f1"}, []
    def post(self, path, **kwargs):
        self.posts.append((path, copy.deepcopy(kwargs)))
        return copy.deepcopy(self.preview if path.endswith("preview") else self.result)


def plan():
    return {"plan_id": "1,2", "essentials": "exact", "mode": "trade", "destination_name": "Settlement" * 40,
            "pawn_ids": [1, 2], "home_pawn_ids": [3, 4], "manifest": [{"thing_id": 40, "def_name": "MealSurvivalPack", "count": 25}],
            "travelers": ["ExtremelyLongPawnName" * 30 for _ in range(20)], "prisoners": ["Captive"],
            "diets": [{"pawn_id": i, "daily_nutrition": 1.5, "policy": "Simple"} for i in range(20)],
            "outbound_days": 2, "return_days": 3, "food_days": 8, "food_nutrition": 18, "daily_nutrition": 2,
            "food_margin_days": 3, "margin_days": 2, "mass": 44, "capacity": 100, "carried_gear_mass": 12,
            "home_defenders": 2, "home_food_items": 30, "home_food_nutrition": 18, "minimum_home_food_items": 20,
            "minimum_home_food_nutrition": 1, "home_medicine": 8, "consequences": "Normal trade session", "estimate_reason": "Native estimator"}


class ExpeditionContracts(unittest.TestCase):
    def test_actual_512_adapter_keeps_critical_facts_and_defer(self):
        agent = Agent()
        client = Client({"plans": [plan()]})
        prepared = expeditions.prepare(client, agent, {"mode": "trade", "map_id": 0}, ask_laya_choice)
        self.assertEqual(prepared["status"], "confirmed")
        visible, questions = agent.calls[-1]
        effect = visible["effects"]["plan_1"]
        self.assertIn("Outbound 2.00d return 3.00d", effect["benefit"])
        self.assertIn("Food 8.00d margin 3.00d", effect["risk"])
        self.assertIn("Mass 44.0/100.0kg food 18.0nut", effect["cost"])
        self.assertIn("Home 2def med8 food30items/18.0nut", effect["inaction"])
        self.assertIn("ETA excludes formation/combat", effect["uncertainty"])
        self.assertIn("defer", visible["effects"])
        self.assertIn("defer", next(iter(questions.values()))["criteria"])
        self.assertEqual(len(client.posts), 1)

    def test_confirmed_roster_manifest_and_policy_sent_exactly(self):
        p = plan(); request = {"mode": "rescue", "map_id": 0, "quest_id": 4, "site_id": 9, "minimum_food_at_home": 20}
        client = Client({"plans": [p]})
        prepared = expeditions.prepare(client, None, request, lambda *args: ("plan_1", {}))
        result = expeditions.execute(client, prepared)
        self.assertTrue(result["applied"])
        sent = client.posts[-1][1]["body"]
        for key in ("pawn_ids", "home_pawn_ids", "manifest", "essentials"):
            self.assertEqual(sent[key], p[key])
        self.assertTrue(sent["confirmed"])
        self.assertEqual(sent["minimum_food_at_home"], 20)
        self.assertEqual(client.posts[-1][0], "/api/v1/world/caravan/rescue/start")

    def test_no_supplies_unknown_eta_and_defer_never_start(self):
        ask = mock.Mock(return_value=("defer", {}))
        for preview in ({"plans": [], "blockers": ["Insufficient nutrition"], "readiness": {"required_nutrition": 18}},
                        {"plans": [plan() | {"outbound_days": None}]},
                        {"plans": [plan() | {"food_margin_days": .5}]}):
            client = Client(preview)
            prepared = expeditions.prepare(client, None, {"mode": "trade"}, ask)
            self.assertFalse(expeditions.execute(client, prepared)["applied"])
            self.assertEqual(len(client.posts), 1)
        ask.assert_not_called()
        client = Client({"plans": [plan()]})
        prepared = expeditions.prepare(client, None, {"mode": "trade"}, ask)
        self.assertTrue(expeditions.execute(client, prepared)["deliberate_defer"])
        self.assertEqual(len(client.posts), 1)

    def test_rejected_start_never_marks_issued(self):
        snapshot = {"map": {"id": 0}, "game": {"tick": 100}, "development": {}}
        state = {"issued": {}, "anchor": {"x": 0, "z": 0}}
        client = Client({}, {"applied": False})
        result = director.execute_action(client, snapshot, state, "trade_to:9:funds", {"expedition": {"status": "confirmed", "body": {"mode": "trade"}, "plan": plan()}})
        self.assertFalse(result["applied"])
        self.assertNotIn("trade_caravan", state["issued"])
        self.assertNotIn("caravan_plan", state)

    def test_native_preview_bypasses_only_legacy_rescue_item_gate(self):
        event = {"family": "kidnap_rescue"}
        context = {"active_quests": [{"quest_def": "PrisonerRescue", "ever_accepted": True, "look_targets": [{"world_object_id": 5}]}],
                   "rescue_readiness": {"ready": False}}
        self.assertNotIn("prepare_rescue_mission", events.response_options(event, context))
        context["rescue_readiness"]["native_preview_required"] = True
        self.assertIn("prepare_rescue_mission", events.response_options(event, context))

    def test_native_source_contract_not_live_harmony_proof(self):
        root = Path("vendor/RIMAPI/Source/RIMAPI/RimworldRestApi")
        helper = (root/"Helpers/ExpeditionPlanHelper.cs").read_text(encoding="utf-8")
        route = (root/"Helpers/ExpeditionRouteState.cs").read_text(encoding="utf-8")
        old = (root/"Helpers/CaravanAutomationHelper.cs").read_text(encoding="utf-8")
        hook = (root/"Controllers/Colony/EndingJourneyController.cs").read_text(encoding="utf-8")
        self.assertNotIn("private static readonly List<PendingRoute>", old)
        self.assertNotIn("PawnsListForReading.Any", old)
        self.assertNotIn("StopFormingCaravan", route)
        self.assertIn('Scribe_References.Look(ref FormingLord', route)
        self.assertIn('r.FormingLord == formingLord', route)
        self.assertIn('SequenceEqual(caravan.PawnsListForReading', route)
        self.assertIn('GetComponent<ExpeditionRouteState>()?.CaravanCreated', hook)
        self.assertIn('CombatNativeHelper.HasCareJob(p)', helper)
        self.assertIn('HealthAIUtility.ShouldSeekMedicalRest(p)', helper)
        self.assertIn('CanEatForNutritionEver', helper)
        self.assertIn('CurrentFoodPolicy?.filter.Allows(t)', helper)
        self.assertIn('TicksUntilRotAtTemp(40f)', helper)
        self.assertIn('MassUtility.GearAndInventoryMass(p)', helper)
        self.assertIn('nativeDays < days', helper)
        self.assertIn('Estimate(target.Tile, map.Tile', helper)
        self.assertIn('Selected cargo is not allowed', helper)
        self.assertIn('already_forming', helper)
        self.assertNotIn('result.Pending = state?.Routes;', helper)
        # Installed nutrition is per unit, never the old identical item count per human.
        self.assertIn('needed - Nutrition(supplies)) / per', helper)
        self.assertNotIn('pawns.Count * 10', old)


if __name__ == "__main__": unittest.main()

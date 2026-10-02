import copy
import json
import unittest
from unittest.mock import patch
import colony_affordances as module
import colony_sessions as sessions
import colony_director as director
import colony_strategy as strategy


class Agent:
    cfg = {"max_len": 512, "head_max_len": 192}
    def __init__(self):
        self.calls = []
    def tok(self, text, **kwargs):
        return {"input_ids": list(range((len(text)+2)//3))}
    def predict(self, state, questions):
        self.calls.append((copy.deepcopy(state), copy.deepcopy(questions)))
        qid, q = next(iter(questions.items()))
        return {"answers": {qid: {"choice": next(iter(q["criteria"]))}}}


class Client:
    def __init__(self, data):
        self.data, self.posts = data, []
    def get(self, path, **kwargs):
        return copy.deepcopy(self.data.get(path, {}))
    def post(self, path, **kwargs):
        self.posts.append((path, kwargs))
        return {"applied": True, "completion": "unverified"}


def option(index=0, label=None):
    return {"key": "native-key-"+str(index), "kind": "ability", "pawn_id": 1,
            "target_id": 1, "ability": "Coagulate", "label": label or "Coagulate",
            "target": "Choose target next", "description": "Stop blood loss.",
            "risk": "Consumes hemogen; target may still need rescue.", "cost": "hemogen",
            "pawn": {"name": "Doctor", "health": .8}}


class AffordanceTests(unittest.TestCase):
    def test_target_refresh_follows_pawn_position_but_rejects_collateral_cost_or_stage(self):
        import copy
        target = {"key": "thing:9", "target_id": 9, "kind": "pawn", "definition": "Human", "x": 2, "z": 3,
                  "hostile": False, "downed": False, "allies_within_five": 1, "affected_allies": 1,
                  "clinical": {"pawn_id": 9, "health": 1, "bleed_rate": 0, "stages": [{"def_name": "Cut", "stage": 0}]},
                  "actual_cost": {"psyfocus": .1, "heat": 5, "charges": 3}}
        original = {"active": True, "session_id": 10, "map_id": 1, "source": "Verb_CastAbility",
                    "effect_identity": "Coagulate", "effect_cost": "charges3", "options": [target]}
        selected = {"session_id": 10, "map_id": 1, "target_id": 9, "x": 2, "z": 3, "cancel": False}
        class C:
            posts = 0
            def get(self, path, **kwargs):
                if path.endswith("/windows"): return []
                self.reads += 1
                return copy.deepcopy(original if self.reads == 1 else self.live)
            def post(self, *args, **kwargs): self.posts += 1; return {"applied": True}
        moved = copy.deepcopy(original)
        moved["options"][0].update(x=8, z=9)
        moved["options"][0]["clinical"]["health"] = .99
        for change, expected in (({}, True), ({"affected_allies": 2}, False),
                                  ({"clinical": {"pawn_id": 9, "health": .99, "bleed_rate": 0, "stages": [{"def_name": "Cut", "stage": 1}]}}, False),
                                  ({"actual_cost": {"psyfocus": .1, "heat": 5, "charges": 2}}, False)):
            client = C(); client.reads = 0; client.live = copy.deepcopy(moved)
            client.live["options"][0].update(change)
            with patch.object(sessions, "target_choice", return_value=(selected, {})):
                result = sessions.run_pending(client, None, {}, {})
            self.assertEqual(result["result"]["applied"], expected)
            self.assertEqual(client.posts, int(expected))
            self.assertEqual(client.reads, 2)

    def test_reopened_target_or_effect_changed_requires_decision_and_current_cancel_is_valid(self):
        context = {"active": True, "session_id": 10, "map_id": 1, "effect_identity": "AbilityA", "effect_cost": "charges3",
                   "caster_facts": {"pawn_id": 2, "health": 1},
                   "options": [{"target_id": 9, "x": 1, "z": 1, "kind": "pawn"}]}
        selected = {"session_id": 10, "map_id": 1, "target_id": 9, "x": 1, "z": 1, "cancel": False}
        for changed in ({"session_id": 11}, {"effect_identity": "AbilityB"}, {"effect_cost": "charges2"},
                        {"caster_facts": {"pawn_id": 3, "health": 1}}):
            class C(Client):
                reads = 0
                def get(self, path, **kwargs):
                    if path.endswith("/windows"): return []
                    self.reads += 1
                    return context if self.reads == 1 else {**context, **changed}
            client = C({})
            with patch.object(sessions, "target_choice", return_value=(selected, {})):
                result = sessions.run_pending(client, None, {}, {})
            self.assertFalse(result["result"]["applied"])
            self.assertFalse(client.posts)
        client = Client({"/api/v1/ui/windows": [], "/api/v1/affordances/targeting": context})
        with patch.object(sessions, "target_choice", return_value=({**selected, "cancel": True}, {})):
            self.assertTrue(sessions.run_pending(client, None, {}, {})["result"]["applied"])
        self.assertTrue(client.posts[0][1]["query"]["cancel"])

    def test_scanner_identity_and_remaining_charges_are_decision_evidence(self):
        row = option()
        row.update(kind="scanner", ability=None, pawn_id=0, cost="Scan ingredients",
                   scanner_facts={"state": "Occupied", "occupant_id": 9, "selected_pawn_id": 9,
                                  "ingredients": [{"def_name": "Steel", "required": 50, "remaining": 0}]})
        selected = {**row, "decision_evidence": module.evidence(row)}
        for changed in ({**row["scanner_facts"], "occupant_id": 10},
                        {**row["scanner_facts"], "state": "WaitingForOccupant"},
                        {**row["scanner_facts"], "ingredients": [{"def_name": "Steel", "required": 50, "remaining": 1}]}):
            client = Client({"/api/v1/affordances/context": {"options": [{**row, "scanner_facts": changed}]}})
            self.assertFalse(module.execute(client, {"map": {"id": 1}}, {}, "affordances_scanner", selected)["applied"])
            self.assertFalse(client.posts)
        client = Client({"/api/v1/affordances/context": {"options": [{**row, "inspect": "ordinary countdown changed"}]}})
        self.assertTrue(module.execute(client, {"map": {"id": 1}}, {}, "affordances_scanner", selected)["applied"])
        ability = {**option(), "cost": {"charges": 2}}
        client = Client({"/api/v1/affordances/context": {"options": [{**ability, "cost": {"charges": 1}}]}})
        self.assertFalse(module.execute(client, {"map": {"id": 1}}, {}, "affordances_ability",
                                        {**ability, "decision_evidence": module.evidence(ability)})["applied"])

    def test_native_generation_and_structured_scanner_contract_source(self):
        from pathlib import Path
        base = Path("vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers")
        source = (base / "AffordanceTargetingHelper.cs").read_text()
        self.assertIn('typeof(Targeter).GetMethods(BindingFlags.Instance | BindingFlags.Public)', source)
        self.assertIn('method.Name == nameof(Targeter.BeginTargeting)', source)
        self.assertIn('AffordanceTargetingHelper.AdvanceGeneration()', source)
        self.assertNotIn('RuntimeHelpers.GetHashCode', source)
        self.assertIn('t.BeginTargeting(source.DestinationSelector', source)
        source = (base / "AffordanceAutomationHelper.cs").read_text()
        self.assertIn('occupant_id=scanner.Occupant?.thingIDNumber', source)
        self.assertIn('remaining=scanner.GetRequiredCountOf(i.FixedIngredient)', source)
        self.assertIn('charges=a.UsesCharges ? a.RemainingCharges : -1', source)

    def test_actual_target_cost_and_late_collateral_reach_visible_budgeted_cards(self):
        context = {"active": True, "session_id": 1, "map_id": 1, "effect_label": "Blast", "effect_cost": "generic",
                   "options": [{"key": "thing:1", "target_id": 1, "kind": "pawn", "x": 1, "z": 1,
                                "actual_cost": {"psyfocus": .1, "heat": 5, "charges": 3}, "affected_allies": 0},
                               {"key": "thing:2", "target_id": 2, "kind": "pawn", "x": 1, "z": 1,
                                "actual_cost": {"psyfocus": .7, "heat": 12, "charges": 3}, "affected_allies": 4,
                                "clinical": {"stages": [{"def_name": "BloodLoss", "stage": 3, "life_threatening": True}]}}]}
        agent = Agent()
        sessions.target_choice(agent, context)
        first = json.dumps(agent.calls[0][0], ensure_ascii=False)
        self.assertIn("AoE allies 4", first)
        self.assertIn("BloodLoss:3!", first)
        self.assertIn("0.7", first)
        for state, _ in agent.calls:
            self.assertLessEqual(len(agent.tok(json.dumps(state, ensure_ascii=False))["input_ids"]), 312)

    def test_scanner_occupant_is_upfront_in_visible_card(self):
        agent = Agent()
        row = {**option(), "kind": "scanner", "pawn_id": 0,
               "scanner_facts": {"state": "Occupied", "occupant_id": 9, "selected_pawn_id": 9}}
        snapshot = {"development": {"affordances": {"options": [row]}}}
        module.prepare(snapshot, {})
        module.choose(agent, {}, "affordances_scanner", snapshot)
        shown = json.dumps(agent.calls[0][0], ensure_ascii=False)
        self.assertIn("Scanner Occupied; occupant 9; selected person 9", shown)

    def test_defer_is_per_offered_identity_and_accepted_dwell_survives_charge_use(self):
        row = {**option(), "cost": {"charges": 3}}
        snapshot = {"game": {"tick": 100}, "map": {"id": 1}, "development": {"affordances": {"options": [row]}}}
        memory = {}
        module.prepare(snapshot, memory)
        with patch.object(module, "ask_laya_choice", return_value=("defer", {})):
            selected, _ = module.choose(None, {}, "affordances_ability", snapshot)
        module.execute(None, snapshot, memory, "affordances_ability", selected)
        newer = {**row, "key": "new", "pawn_id": 2, "target_id": 2}
        snapshot["development"]["affordances"]["options"] = [row, newer]
        module.prepare(snapshot, memory)
        self.assertEqual(set(snapshot["development"]["affordances"]["candidates"]["affordances_ability"]), {"new"})
        memory = {}
        client = Client({"/api/v1/affordances/context": {"options": [row]}})
        self.assertTrue(module.execute(client, snapshot, memory, "affordances_ability", {**row, "decision_evidence": module.evidence(row)})["applied"])
        snapshot["development"]["affordances"]["options"] = [{**row, "cost": {"charges": 2}}]
        self.assertEqual(module.prepare(snapshot, memory), [])

    @patch('colony_retry.time.time')
    def test_failed_and_stale_option_retry_prunes_and_new_urgency_bypasses(self, clock):
        clock.return_value = 100
        row = option(); row["pawn"] = {"health": .9, "conditions": [{"stage": 0}]}
        snapshot = {"game": {"tick": 100}, "map": {"id": 1}, "development": {"affordances": {"options": [row]}}}
        for failure in ("stale", "get", "post", "rejected"):
            clock.return_value = 100
            class C(Client):
                def get(self, *args, **kwargs):
                    if failure == "get": raise RuntimeError("offline get failure")
                    return {"options": [] if failure == "stale" else [row]}
                def post(self, *args, **kwargs):
                    if failure == "post": raise RuntimeError("offline post failure")
                    return {"applied": False}
            memory = {}
            result = module.execute(C({}), snapshot, memory, "affordances_ability", {**row, "decision_evidence": module.evidence(row)})
            self.assertFalse(result["applied"])
            memory = json.loads(json.dumps(memory))
            self.assertEqual(module.prepare(snapshot, memory), [])
            snapshot["development"]["affordances"]["options"] = [{**row, "pawn": {"health": .4, "conditions": [{"stage": 1}]}}]
            self.assertEqual(module.prepare(snapshot, memory), ["affordances_ability"])
            snapshot["development"]["affordances"]["options"] = [row]
            clock.return_value = 131
            snapshot["game"]["tick"] = 250
            module.prepare(snapshot, memory)
            self.assertEqual(memory["affordance_cooldowns"], {})
            snapshot["game"]["tick"] = 100
        memory = {"affordance_cooldowns": {"legacy": 100, "bad": {"tick": "bad"}, "future": {"tick": 200, "retry_ticks": 150}}}
        module.prepare(snapshot, memory)
        self.assertEqual(memory["affordance_cooldowns"], {})

    def test_paused_target_failure_has_bounded_wall_retry_and_new_session_bypasses(self):
        context = {"active": True, "session_id": 10, "map_id": 1, "options": [{"target_id": 9, "kind": "pawn", "x": 1, "z": 1}]}
        selected = {"session_id": 10, "map_id": 1, "target_id": 9, "x": 1, "z": 1, "cancel": False}
        class C(Client):
            def post(self, *args, **kwargs): self.posts.append((args, kwargs)); return {"applied": False}
        client = C({"/api/v1/ui/windows": [], "/api/v1/affordances/targeting": context})
        memory = {}
        with patch.object(sessions, "target_choice", return_value=(selected, {})) as choose:
            for now in (100, 100.5, 101, 101.5, 103, 107, 112):
                with patch.object(sessions.time, "time", return_value=now):
                    sessions.run_pending(client, None, {"game": {"tick": 100, "is_paused": True}}, memory)
            self.assertEqual(choose.call_count, 5)
            self.assertEqual(memory["native_target_retry"]["delay"], 5)
            memory = json.loads(json.dumps(memory))
            context["session_id"] = 11
            with patch.object(sessions.time, "time", return_value=112.1):
                sessions.run_pending(client, None, {}, memory)
            self.assertEqual(choose.call_count, 6)
        context["options"] = []
        with patch.object(sessions, "target_choice", return_value=({**selected, "session_id": 11, "cancel": True}, {})), patch.object(sessions.time, "time", return_value=112.2):
            sessions.run_pending(client, None, {}, memory)
        self.assertTrue(client.posts[-1][1]["query"]["cancel"])

    def test_long_risk_keeps_collateral_and_hostility_upfront(self):
        row = {**option(), "risk": "modded verbose risk " * 500, "affected_allies": 7, "target_hostile": True}
        snapshot = {"development": {"affordances": {"options": [row]}}}
        agent = Agent(); module.prepare(snapshot, {})
        module.choose(agent, {}, "affordances_ability", snapshot)
        shown = json.dumps(agent.calls[0][0], ensure_ascii=False)
        self.assertIn("maximum allies in area 7; target hostile True", shown)
        self.assertLessEqual(len(agent.tok(shown)["input_ids"]), 312)

    def test_long_translated_labels_never_become_model_identifiers(self):
        agent = Agent()
        rows = [option(i, ("Применить способность "+str(i)+" ") * 140) for i in range(8)]
        snapshot = {"development": {"affordances": {"options": rows}}, "game": {"tick": 100}}
        module.prepare(snapshot, {})
        selected, _ = module.choose(agent, {}, "affordances_ability", snapshot)
        self.assertEqual(selected["key"], rows[0]["key"])
        for state, qs in agent.calls:
            self.assertLessEqual(len(agent.tok(json.dumps(state, ensure_ascii=False))["input_ids"]), 312)
            for q in qs.values():
                self.assertTrue(all(len(key) < 10 for key in q["criteria"]))
            for card in state.get("effects", {}).values():
                self.assertEqual(set(card), {"benefit", "risk", "cost", "inaction", "uncertainty"})

    def test_stale_or_changed_ability_is_not_submitted(self):
        selected = option()
        client = Client({"/api/v1/affordances/context": {"options": []}})
        result = module.execute(client, {"map": {"id": 1}, "game": {}}, {},
                                "affordances_ability", selected)
        self.assertFalse(result["applied"])
        self.assertEqual(client.posts, [])

    def test_unrelated_director_details_cannot_enter_native_payload(self):
        row = option()
        client = Client({"/api/v1/affordances/context": {"options": [row]}})
        result = module.execute(client, {"map": {"id": 3}, "game": {"tick": 20}}, {},
                                "affordances_ability", {**row, "command": "debug_kill", "other_plan": [1, 2]})
        self.assertTrue(result["applied"])
        self.assertEqual(set(client.posts[0][1]["body"]),
                         {"map_id", "kind", "pawn_id", "target_id", "ability", "label"})

    def test_no_cross_action_confusion(self):
        row = option()
        client = Client({"/api/v1/affordances/context": {"options": [row]}})
        self.assertFalse(module.execute(client, {"map": {"id": 1}}, {},
                                       "affordances_scanner", row)["applied"])
        self.assertFalse(client.posts)

    def test_future_cooldown_does_not_survive_loaded_save(self):
        snap = {"game": {"tick": 20}, "development": {"affordances": {"options": [option()]}}}
        state = {"affordance_cooldowns": {"native-key-0": 1000}}
        self.assertIn("affordances_ability", module.prepare(snap, state))

    def test_only_confirmed_native_ending_can_stop_run(self):
        for value in ({}, {"ship_countdown": True}, {"victory_verified": True},
                      {"victory_verified": True, "ending_tick": -1}):
            self.assertIsNone(sessions.ending_result(value))
        result = sessions.ending_result({"victory_verified": True, "ending_tick": 200, "ending_route": "anomaly_void"})
        self.assertEqual(result["mode"], "victory")

    def test_pending_target_keeps_actual_effect_and_cost(self):
        context = {"active": True, "session_id": 8, "map_id": 1, "source": "Verb_CastAbility",
                   "effect_label": "Coagulate", "effect_description": "Stop blood loss", "effect_cost": "hemogen",
                   "options": [{"key": "pawn:3", "kind": "pawn", "target_id": 3, "x": 10, "z": 10,
                                "label": "Patient", "inspect": "Bleeding", "allies_within_five": 3}]}
        agent = Agent()
        selected, _ = sessions.target_choice(agent, context)
        self.assertEqual(selected["target_id"], 3)
        for visible, _ in agent.calls:
            offered = next(card for key, card in visible["effects"].items() if key != "cancel")
            self.assertIn("Coagulate", offered["benefit"])
            self.assertIn("hemogen", offered["cost"])

    def test_unknown_paused_modal_suppresses_normal_orders(self):
        client = Client({"/api/v1/ui/windows": [{"window_type": "Dialog_Unexpected", "force_pause": True, "window_id": 6}]})
        memory = {}
        first = sessions.run_pending(client, Agent(), {}, memory)
        second = sessions.run_pending(client, Agent(), {}, memory)
        self.assertEqual(first["mode"], "native-window-wait")
        self.assertFalse(first["quiet"])
        self.assertTrue(second["quiet"])
        self.assertFalse(client.posts)

    def test_new_care_and_cooling_survive_emergency_filters(self):
        actions = ["resilience_rescue", "resilience_tend", "resilience_temperature", "production_recipe_batch"]
        self.assertIn("resilience_rescue", director.focus_active_fire_choices(actions, True))
        snap = {"development": {"heat_threat": {"patients": [{"severity": .8}]}}}
        filtered = director.focus_heatstroke_choices(snap, actions)
        self.assertIn("resilience_temperature", filtered)
        self.assertNotIn("production_recipe_batch", filtered)

    def test_empty_or_inactive_ending_cannot_be_retained(self):
        for endgame in ("", "mechhive", "enduring_colony"):
            context = {"current": {"endgame": endgame}, "active_mods": [], "victory_required": True}
            result = strategy.choose_cascaded_doctrine(Agent(), {}, context)
            self.assertFalse(result.get("retained"))
            self.assertEqual(result["selection"]["endgame"], "ship_escape")

    def test_downed_patient_late_in_target_group_is_visible(self):
        rows = [{"key": f"pawn:{i}", "label": f"Healthy{i}", "kind": "pawn", "health": 1.0} for i in range(80)]
        rows.append({"key": "pawn:999", "label": "Bleeding child", "health": .1,
                     "downed": True, "bleed_rate": .9, "conditions": ["Blood loss"]})
        facts = sessions.target_group_facts(rows)
        self.assertIn("downed 1", facts)
        self.assertIn("Bleeding child", facts)
        self.assertIn("0.1", facts)

    def test_modal_prevents_reaching_through_to_local_target(self):
        client = Client({"/api/v1/affordances/targeting": {"active": True},
                         "/api/v1/ui/windows": [{"window_type": "Dialog_MessageBox", "blocks_input": True, "window_id": 6}]})
        result = sessions.run_pending(client, Agent(), {}, {})
        self.assertEqual(result["mode"], "native-window-wait")
        self.assertFalse(client.posts)

    def test_native_game_over_does_not_depend_on_translated_text(self):
        self.assertIsNone(sessions.terminal_result({"colonists": 0, "game_over_verified": False}))
        self.assertEqual(sessions.terminal_result({"game_over_verified": True})["mode"], "game-over")

    def test_urgent_care_survives_fire_and_cold_early_branches(self):
        care = ["resilience_rescue", "resilience_tend", "resilience_feed", "society_baby_safe"]
        for first in ("prioritize_firefighting", "expand_home_area"):
            self.assertTrue(set(care).issubset(director.focus_active_fire_choices([first, *care], True)))
        snap = {"development": {"cold_threat": {"outside_c": -25, "patients": [{}]}}, "colonists": [{}]}
        for first in ("build_starter_base", "unforbid_supplies"):
            result = director.focus_cold_start_choices(snap, [first, "build_temple", *care], {})
            self.assertTrue(set(care).issubset(result))
            self.assertNotIn("build_temple", result)

    def test_ability_cost_changed_since_decision_requires_new_choice(self):
        row = option()
        selected = {**row, "decision_evidence": module.evidence(row)}
        client = Client({"/api/v1/affordances/context": {"options": [{**row, "cost": "last hemogen pack"}]}})
        result = module.execute(client, {"map": {"id": 1}, "game": {}}, {}, "affordances_ability", selected)
        self.assertFalse(result["applied"])
        self.assertFalse(client.posts)

    def test_world_pending_can_execute_without_any_map(self):
        import types
        fake = types.SimpleNamespace(__name__="colony_progression", PENDING_WINDOWS=(),
            peek_pending=lambda c: True, collect=lambda c,s: {"stage": "tile"},
            prepare=lambda s,m: [], pending_action=lambda c: "progression_ending",
            choose=lambda a,s,x,snap: ({"operation": "tile"}, {}))
        with patch.object(sessions.colony_modules, "modules", return_value=(fake,)), \
             patch.object(sessions.colony_modules, "execute", return_value={"applied": True}) as execute:
            result = sessions.run_pending(Client({}), Agent(), {"map": {}, "game": {}}, {}, world_only=True)
        self.assertEqual(result["mode"], "native-continuation")
        self.assertEqual(execute.call_args.args[1]["map"], {})


if __name__ == "__main__":
    unittest.main()

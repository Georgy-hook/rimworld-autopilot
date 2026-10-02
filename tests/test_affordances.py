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

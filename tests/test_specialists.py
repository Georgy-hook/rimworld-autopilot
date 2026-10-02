import copy
import unittest
import colony_specialists as specialists


def snapshot():
    return {"map": {"id": 7}, "game": {"tick": 50000}, "development": {"specialists": {
        "available": True, "biotech_active": True, "anomaly_active": True, "pollution_percent": .12,
        "wastepacks": [{"count": 5, "frozen": False}], "chargers": [{"id": 60, "powered": True}],
        "mech_groups": [{"mechanitor_id": 1, "group_index": 1, "mode": "Work", "mode_options": ["Work", "Recharge", "SelfShutdown"], "mechs": [{"pawn_id": 10, "name": "Lifter", "energy": .1}]}],
        "entities": [{"platform_id": 40, "name": "Entity", "activity": .6, "containment_strength": 50, "minimum_strength": 100, "worker_options": [{"pawn_id": 2, "name": "Warden", "social": 8, "suppression_rate": .2}]}],
    }}}


class Agent:
    def __init__(self, preferred=None):
        self.preferred = preferred or {}
        self.calls = []
    def predict(self, state, questions):
        self.calls.append(copy.deepcopy(state))
        qid, question = next(iter(questions.items()))
        preferred = self.preferred.get(qid.split("_round_")[0])
        value = preferred if preferred in question["criteria"] else next((k for k in question["criteria"] if k != "defer"), next(iter(question["criteria"])))
        return {"answers": {qid: {"choice": value}}}


class Client:
    def __init__(self, context, applied=True):
        self.context = context
        self.posts = []
        self.applied = applied
    def get(self, path, **kwargs):
        if path.endswith("/context"):
            return copy.deepcopy(self.context)
        key = {"rituals": "rituals", "genetics": "genetics", "mech-bosses": "mech_bosses", "permits": "permits"}.get(path.rsplit("/", 1)[-1])
        return copy.deepcopy(self.context.get(key) or {})
    def post(self, path, **kwargs):
        self.posts.append((path, kwargs))
        return {"applied": self.applied, "reason": "normal_job_assigned"}


class SpecialistTests(unittest.TestCase):
    def test_loading_older_save_restores_specialist_choices(self):
        snap = snapshot()
        issued = {'issued': {'specialists:specialists_mech_mode': 900000, 'specialists:specialists_suppress_entity': 900000}}
        self.assertEqual(set(specialists.prepare(snap, issued)), {'specialists_mech_mode', 'specialists_suppress_entity'})
        self.assertEqual(specialists.prepare(snap, {'issued': {'specialists:specialists_mech_mode': 49000, 'specialists:specialists_suppress_entity': 49000}}), [])

    def test_only_loaded_dlc_and_live_native_options_are_offered(self):
        snap = snapshot()
        self.assertEqual(set(specialists.prepare(snap, {})), {"specialists_mech_mode", "specialists_suppress_entity"})
        context = snap["development"]["specialists"]
        context["biotech_active"] = False
        self.assertEqual(specialists.prepare(snap, {}), ["specialists_suppress_entity"])
        context["anomaly_active"] = False
        self.assertEqual(specialists.prepare(snap, {}), [])

    def test_ritual_native_blockers_prevent_begin_but_allow_assignment(self):
        snap = snapshot()
        snap["development"]["specialists"]["rituals"] = {"available": True, "configuring": True, "can_begin": False,
            "blockers": ["missing invoker"], "choices": [{"operation": "assign", "role_id": "Invoker", "pawn_id": 4, "label": "Assign researcher"}]}
        self.assertIn("specialists_ritual", specialists.prepare(snap, {"issued": {"specialists:specialists_ritual": 50000}}))
        rows = snap["development"]["specialists"]["options"]["specialists_ritual"]
        self.assertNotIn("begin", rows)
        self.assertEqual(rows["0"]["role_id"], "Invoker")

    def test_gene_design_cannot_begin_without_native_limits_and_name(self):
        snap = snapshot()
        snap["development"]["specialists"]["genetics"] = {"available": True, "configuring": True, "can_begin": False,
            "packs": [{"thing_id": 4, "label": "Strong", "selected": False, "powered": True},
                      {"thing_id": 5, "label": "Unavailable", "selected": False, "powered": False}]}
        specialists.prepare(snap, {})
        rows = snap["development"]["specialists"]["options"]["specialists_genetics"]
        self.assertEqual(set(rows), {"4", "cancel"})
        self.assertTrue(rows["4"]["selected"])
        self.assertNotIn("begin", rows)

    def test_stale_ritual_quality_or_defense_rejects_operation(self):
        snap = snapshot()
        native = {"available": True, "configuring": True, "can_begin": True, "choices": [], "quality": {"minimum": .7}}
        snap["development"]["specialists"]["rituals"] = native
        specialists.prepare(snap, {})
        selected = snap["development"]["specialists"]["options"]["specialists_ritual"]["begin"]
        class LiveClient:
            def get(self, path, **kwargs):
                if path.endswith("/context"):
                    return {"available": True}
                if path.endswith("/rituals"):
                    return {**native, "quality": {"minimum": .1}}
                return {}
            def post(self, *args, **kwargs):
                raise AssertionError("No stale ritual should start")
        result = specialists.execute(LiveClient(), snap, {}, "specialists_ritual", selected)
        self.assertFalse(result["applied"])

    def test_protected_or_charging_group_has_no_exported_options(self):
        snap = snapshot()
        snap["development"]["specialists"]["mech_groups"][0]["mode_options"] = []
        self.assertNotIn("specialists_mech_mode", specialists.prepare(snap, {}))

    def test_no_native_feasible_warden_means_no_suppression_action(self):
        snap = snapshot()
        snap["development"]["specialists"]["entities"][0]["worker_options"] = []
        self.assertNotIn("specialists_suppress_entity", specialists.prepare(snap, {}))

    def test_current_mech_mode_is_not_a_change_option(self):
        snap = snapshot()
        specialists.prepare(snap, {})
        values = [row["value"] for row in snap["development"]["specialists"]["options"]["specialists_mech_mode"].values()]
        self.assertEqual(set(values), {"Recharge", "SelfShutdown"})

    def test_laya_can_choose_dormancy_instead_of_powered_recharge(self):
        snap = snapshot()
        specialists.prepare(snap, {})
        agent = Agent({"specialists_mech_mode": "1:1:SelfShutdown"})
        selected, _ = specialists.choose(agent, {}, "specialists_mech_mode", snap)
        self.assertEqual(selected["value"], "SelfShutdown")
        facts = agent.calls[-1]["facts"]
        self.assertEqual(facts["pollution"], .12)
        self.assertEqual(facts["wastepacks"]["unfrozen"], 5)
        self.assertEqual(facts["target"]["minimum_energy"], .1)

    def test_deferral_at_each_stage_never_posts_and_gets_cooldown(self):
        for preferences in ({"specialists_mech_mode_target": "defer"}, {"specialists_mech_mode": "defer"}):
            snap = snapshot()
            specialists.prepare(snap, {})
            selected, _ = specialists.choose(Agent(preferences), {}, "specialists_mech_mode", snap)
            client = Client(snap["development"]["specialists"])
            state = {}
            self.assertEqual(specialists.execute(client, snap, state, "specialists_mech_mode", selected)["reason"], "laya_deferred")
            self.assertFalse(client.posts)
            self.assertNotIn("specialists_mech_mode", specialists.prepare(snap, state))

    def test_entity_strength_risk_remains_visible_in_selected_target_context(self):
        snap = snapshot()
        specialists.prepare(snap, {})
        agent = Agent()
        selected, _ = specialists.choose(agent, {}, "specialists_suppress_entity", snap)
        self.assertEqual(selected, {"kind": "suppress", "platform_id": 40, "worker_id": 2})
        facts = agent.calls[-1]["facts"]
        self.assertEqual(facts["target"]["minimum_strength"], 100)
        self.assertIn("does not repair", agent.calls[-1]["effects"]["40:2"]["risk"])

    def test_stale_group_or_worker_refuses_before_mutation(self):
        for action in specialists.ACTIONS:
            snap = snapshot()
            specialists.prepare(snap, {})
            selected, _ = specialists.choose(Agent(), {}, action, snap)
            changed = copy.deepcopy(snap["development"]["specialists"])
            changed["mech_groups"][0]["mode_options"] = []
            changed["entities"][0]["worker_options"] = []
            client = Client(changed)
            self.assertFalse(specialists.execute(client, snap, {}, action, selected)["applied"])
            self.assertFalse(client.posts)

    def test_director_extras_do_not_change_exact_order_payload(self):
        snap = snapshot()
        specialists.prepare(snap, {})
        selected, _ = specialists.choose(Agent(), {}, "specialists_suppress_entity", snap)
        selected["architecture_context"] = {"foreign": True}
        client = Client(snap["development"]["specialists"])
        self.assertTrue(specialists.execute(client, snap, {}, "specialists_suppress_entity", selected)["applied"])
        self.assertEqual(client.posts[0][1]["body"], {"map_id": 7, "kind": "suppress", "platform_id": 40, "worker_id": 2})

    def test_failed_native_order_does_not_claim_completion_or_enter_cooldown(self):
        snap = snapshot()
        specialists.prepare(snap, {})
        selected, _ = specialists.choose(Agent(), {}, "specialists_mech_mode", snap)
        client = Client(snap["development"]["specialists"], applied=False)
        state = {}
        self.assertFalse(specialists.execute(client, snap, state, "specialists_mech_mode", selected)["applied"])
        self.assertFalse(state.get("issued"))

    def test_compact_summary_reports_hazards_without_claiming_special_actions(self):
        snap = snapshot()
        snap["development"]["specialists"]["gene_pawns"] = [{"pawn_id": 4, "resources": [{"def_name": "Hemogen", "level": .1, "target": .5}], "needs": [{"def_name": "Deathrest", "level": .1}]}]
        facts = specialists.summary(snap)
        self.assertEqual(len(facts), 5)
        self.assertEqual(facts["low_energy_mechs"]["count"], 1)
        self.assertEqual(facts["unsafe_containment"]["count"], 1)
        self.assertEqual(facts["pollution_waste"]["unfrozen_wastepacks"], 5)
        self.assertEqual(facts["low_gene_resources"]["examples"][0]["resource"], "Hemogen")
        self.assertEqual(facts["low_gene_needs"]["examples"][0]["need"], "Deathrest")


    def test_native_policy_choices_preserve_exact_pruning_cost_and_caste_pending(self):
        value = snapshot()
        context = value["development"]["specialists"]
        context["policies"] = {"configuring": True, "choices": [
            {"operation": "caste", "value": "Carrier", "label": "Carrier", "description": "Hauling dryad", "warning": "Cocoon downtime"},
            {"operation": "cancel", "label": "Cancel"}]}
        actions = specialists.prepare(value, {"issued": {"specialists:specialists_policy": 50000}})
        self.assertIn("specialists_policy", actions)
        self.assertEqual(specialists.pending_action(context), "specialists_policy")
        agent = Agent()
        selected, _ = specialists.choose(agent, {}, "specialists_policy", value)
        self.assertEqual(selected["operation"], "caste")
        self.assertNotIn("defer", str(agent.calls))

    def test_changed_native_policy_cost_refuses_order(self):
        value = snapshot()
        policy = {"operation": "pruning", "thing_id": 8, "value": "75", "label": "Prune", "pruning_hours": 4}
        value["development"]["specialists"]["policies"] = {"choices": [policy]}
        specialists.prepare(value, {})
        selected = value["development"]["specialists"]["options"]["specialists_policy"]["0"]
        client = Client({**value["development"]["specialists"], "policies": {"choices": [{**policy, "pruning_hours": 8}]}})
        result = specialists.execute(client, value, {}, "specialists_policy", selected)
        self.assertFalse(result["applied"])
        self.assertEqual(client.posts, [])

if __name__ == "__main__":
    unittest.main()

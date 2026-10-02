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
        key = {"rituals": "rituals", "genetics": "genetics", "mech-bosses": "mech_bosses", "permits": "permits", "policies": "policies"}.get(path.rsplit("/", 1)[-1])
        return copy.deepcopy(self.context.get(key) or {})
    def post(self, path, **kwargs):
        self.posts.append((path, kwargs))
        return {"applied": self.applied, "reason": "normal_job_assigned"}


class SpecialistTests(unittest.TestCase):
    def test_loading_older_save_restores_specialist_choices(self):
        snap = snapshot()
        issued = {'specialists_memory': {'issued': {'specialists_mech_mode:1:1': {'tick': 900000}, 'specialists_suppress_entity:40': {'tick': 900000}}}}
        self.assertEqual(set(specialists.prepare(snap, issued)), {'specialists_mech_mode', 'specialists_suppress_entity'})
        self.assertEqual(specialists.prepare(snap, {'specialists_memory': {'issued': {'specialists_mech_mode:1:1': {'tick': 49000}, 'specialists_suppress_entity:40': {'tick': 49000}}}}), [])

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

class NativeClient(Client):
    def __init__(self, context, result='ritual_assignment_updated'):
        super().__init__(context)
        self.result = result
    def post(self, path, **kwargs):
        self.posts.append((path, kwargs))
        return self.result


class SpecialistCycleContracts(unittest.TestCase):
    def dialog(self, board=False, sid='window1'):
        return {'available': True, 'configuring': True, 'session_id': sid, 'map_id': 7,
                'configuration': {'board': board}, 'blockers': [], 'can_begin': True,
                'quality': {'minimum': .7}, 'choices': [{'operation': 'policy', 'policy': 'boardColonyAnimals', 'value': not board, 'label': 'Board animals'}]}

    def test_benign_focus_drift_post_and_subject_policy_dwell(self):
        snap = snapshot()
        row = {'operation': 'focus', 'pawn_id': 8, 'map_id': 7, 'value': '50', 'label': 'focus50', 'current': .4, 'desired': .25}
        context = snap['development']['specialists']
        context['policies'] = {'choices': [row]}
        specialists.prepare(snap, {})
        selected = context['options']['specialists_policy']['0']
        live = copy.deepcopy(context); live['policies']['choices'][0]['current'] = .401
        state = {}; client = NativeClient(live, 'specialist_policy_requested')
        self.assertTrue(specialists.execute(client, snap, state, 'specialists_policy', selected)['applied'])
        self.assertEqual(client.posts[0][1]['query'], {'operation': 'focus', 'pawn_id': 8, 'map_id': 7, 'value': '50', 'label': 'focus50', 'confirmed': True})
        context['policies']['choices'].append(dict(row, pawn_id=99))
        specialists.prepare(snap, state)
        self.assertEqual({r['pawn_id'] for r in context['options']['specialists_policy'].values()}, {99})

    def test_session_first_undo_allowed_repeated_edge_blocked_begin_cancel_remain(self):
        snap = snapshot(); context = snap['development']['specialists']; state = {}
        context['rituals'] = self.dialog(False)
        specialists.prepare(snap, state)
        first = context['options']['specialists_ritual']['0']
        specialists.execute(NativeClient(context), snap, state, 'specialists_ritual', first)
        context['rituals'] = self.dialog(True)
        specialists.prepare(snap, state)
        undo = context['options']['specialists_ritual']['0']
        specialists.execute(NativeClient(context), snap, state, 'specialists_ritual', undo)
        context['rituals'] = self.dialog(False)
        specialists.prepare(snap, state)
        self.assertEqual(set(context['options']['specialists_ritual']), {'begin', 'cancel'})
        self.assertIn('Repeated', context['rituals']['repeat_blocker'])
        context['rituals']['blockers'] = ['Offering replenishment required']
        specialists.prepare(snap, state)
        self.assertIn('0', context['options']['specialists_ritual'])
        context['rituals'] = self.dialog(False, 'window2')
        specialists.prepare(snap, state)
        self.assertIn('0', context['options']['specialists_ritual'])
        self.assertEqual(set(state['specialists_memory']['sessions']), {'window2'})

    def test_reopened_same_dialog_rejects_old_command_and_begin_config_change(self):
        snap = snapshot(); context = snap['development']['specialists']
        context['rituals'] = self.dialog()
        specialists.prepare(snap, {})
        selected = context['options']['specialists_ritual']['begin']
        live = copy.deepcopy(context); live['rituals']['session_id'] = 'window2'
        client = NativeClient(live)
        self.assertFalse(specialists.execute(client, snap, {}, 'specialists_ritual', selected)['applied'])
        self.assertFalse(client.posts)
        live = copy.deepcopy(context); live['rituals']['configuration']['board'] = True
        self.assertFalse(specialists.execute(NativeClient(live), snap, {}, 'specialists_ritual', selected)['applied'])

    def test_pending_failed_backoff_uses_wall_time_and_cancel_persists(self):
        from unittest.mock import patch
        snap = snapshot(); context = snap['development']['specialists']; context['rituals'] = self.dialog(); state = {}
        specialists.prepare(snap, state); selected = context['options']['specialists_ritual']['0']
        with patch.object(specialists.time, 'time', return_value=100):
            specialists.execute(NativeClient(context, 'rejected'), snap, state, 'specialists_ritual', selected)
            specialists.prepare(snap, state)
            self.assertNotIn('0', context['options']['specialists_ritual'])
            self.assertIn('cancel', context['options']['specialists_ritual'])
        with patch.object(specialists.time, 'time', return_value=102.1):
            specialists.prepare(snap, state)
            self.assertIn('0', context['options']['specialists_ritual'])
        context['options']['specialists_ritual'] = {}
        self.assertIsNotNone(specialists.pending_blocker(context))

    def test_map_scope_and_both_stage_boss_facts_are_visible(self):
        snap = snapshot(); context = snap['development']['specialists']
        context['mech_bosses'] = {'options': [{'pawn_id': 8, 'map_id': 7, 'label': 'Summon', 'hostile_pawns': 6, 'mobile_defenders': 2}, {'pawn_id': 99, 'map_id': 9, 'label': 'Other map'}]}
        specialists.prepare(snap, {})
        self.assertEqual(len(context['options']['specialists_mech_boss']), 1)
        agent = Agent(); specialists.choose(agent, {}, 'specialists_mech_boss', snap)
        for state in agent.calls:
            self.assertIn('hostile_pawns=6', str(state['effects']))
            self.assertIn('mobile_defenders=2', str(state['effects']))

    def test_name_once_per_composition_and_new_composition_reopens(self):
        snap = snapshot(); context = snap['development']['specialists']; state = {}
        context['genetics'] = {'available': True, 'configuring': True, 'session_id': 'genes1', 'map_id': 7,
            'configuration': {'selected_packs': [4], 'name': 'Before'}, 'can_begin': True,
            'packs': [{'thing_id': 4, 'label': 'Pack', 'selected': True, 'powered': True}]}
        specialists.prepare(snap, state)
        selected = context['options']['specialists_genetics']['name']
        specialists.execute(NativeClient(context, 'gene_name_chosen'), snap, state, 'specialists_genetics', selected)
        context['genetics']['configuration']['name'] = 'After'
        specialists.prepare(snap, state)
        self.assertNotIn('name', context['options']['specialists_genetics'])
        self.assertIn('begin', context['options']['specialists_genetics'])
        context['genetics']['configuration']['selected_packs'] = [4, 5]
        specialists.prepare(snap, state)
        self.assertIn('name', context['options']['specialists_genetics'])

    def test_operation_query_contracts_do_not_invent_unrelated_ids(self):
        snap = snapshot(); context = snap['development']['specialists']
        cases = [
            ('rituals', 'specialists_ritual', {'operation': 'assign', 'pawn_id': 8, 'role_id': 'Invoker'}, {'pawn_id', 'role_id'}),
            ('rituals', 'specialists_ritual', {'operation': 'remove', 'pawn_id': 8}, {'pawn_id'}),
            ('rituals', 'specialists_ritual', {'operation': 'role', 'role_id': 'Leader'}, {'role_id'}),
            ('rituals', 'specialists_ritual', {'operation': 'policy', 'policy': 'boardColonyAnimals', 'value': False}, {'policy', 'value'}),
            ('policies', 'specialists_policy', {'operation': 'caste', 'value': 'Carrier'}, {'value'}),
        ]
        for name, action, offered, required in cases:
            context[name] = {'available': True, 'configuring': True, 'session_id': 'window', 'map_id': 7, 'choices': [{**offered, 'label': 'Choice'}]}
            specialists.prepare(snap, {})
            row = context['options'][action]['0']; client = NativeClient(context, 'ritual_assignment_updated' if name == 'rituals' else 'specialist_policy_requested')
            self.assertTrue(specialists.execute(client, snap, {}, action, row)['applied'])
            query = client.posts[0][1]['query']
            self.assertTrue(required <= set(query))
            self.assertEqual(query['session_id'], 'window')
            self.assertEqual(set(query) & {'thing_id', 'pawn_id', 'role_id'}, required & {'thing_id', 'pawn_id', 'role_id'})
        context['genetics'] = {'available': True, 'configuring': True, 'session_id': 'gene', 'map_id': 7, 'can_begin': True, 'packs': []}
        specialists.prepare(snap, {})
        for operation in ('begin', 'cancel'):
            row = context['options']['specialists_genetics'][operation]
            self.assertNotIn('thing_id', specialists._payload(row, 'specialists_genetics'))

    def test_json_rollback_and_expired_history_pruning(self):
        import json
        snap = snapshot(); specialists.prepare(snap, {})
        state = {}; row = snap['development']['specialists']['options']['specialists_mech_mode']['1:1:Recharge']
        specialists.execute(Client(snap['development']['specialists']), snap, state, 'specialists_mech_mode', row)
        state = json.loads(json.dumps(state)); specialists.prepare(snap, state)
        self.assertNotIn('specialists_mech_mode', snap['development']['specialists']['eligible_actions'])
        snap['game']['tick'] -= 1; specialists.prepare(snap, state)
        self.assertNotIn('specialists_memory', state)
        state = {'specialists_memory': {'issued': {str(i): {'tick': 0} for i in range(10000)}}}
        specialists.prepare(snap, state)
        self.assertNotIn('specialists_memory', state)

    def test_long_description_late_hazard_numeric_facts_survive_312_budget(self):
        import json
        class BudgetAgent(Agent):
            cfg = {'max_len': 512, 'head_max_len': 192}
            def tok(self, text, **kwargs):
                return {'input_ids': list(range((len(text) + 3) // 4))}
            def predict(self, state, questions):
                self.calls.append(copy.deepcopy(state))
                question = next(iter(questions))
                selected = next((key for key, effect in state['effects'].items() if 'hostile_pawns=6' in effect['benefit'] or 'favor=5' in effect['benefit'] or 'strength=50' in effect['benefit']), next(iter(state['effects'])))
                return {'answers': {question: {'choice': selected}}}
        for action, native_key, fact_values, required in (
            ('specialists_mech_boss', 'mech_bosses', {'hostile_pawns': 6, 'mobile_defenders': 2}, ('hostile_pawns=6', 'mobile_defenders=2')),
            ('specialists_permit', 'permits', {'favor': 5, 'on_cooldown': True, 'permit': 'Aid', 'faction_id': 4}, ('favor=5', 'on_cooldown=True')),
            ('specialists_policy', 'policies', {'strength': 50, 'minimum': 100, 'operation': 'study_mode', 'value': 'Study'}, ('strength=50', 'minimum=100')),
        ):
            snap = snapshot(); rows = []
            for i in range(20):
                row = {'pawn_id': 100+i, 'map_id': 7, 'label': 'Native choice', 'description': 'Long loaded explanation ' * 1000}
                if i == 19:
                    row.update(fact_values)
                rows.append(row)
            snap['development']['specialists'][native_key] = {'choices' if native_key == 'policies' else 'options': rows}
            specialists.prepare(snap, {})
            agent = BudgetAgent(); selected, _ = specialists.choose(agent, {}, action, snap)
            self.assertEqual(selected['pawn_id'], 119)
            for stage in agent.calls:
                self.assertLessEqual(len(agent.tok(json.dumps(stage, ensure_ascii=False, default=str))['input_ids']), 312)
            seen = [stage for stage in agent.calls if required[0] in str(stage['effects'])]
            self.assertGreaterEqual(len(seen), 2)
            for stage in seen:
                self.assertIn(required[1], str(stage['effects']))

    def test_malformed_persisted_records_are_removed(self):
        snap = snapshot()
        state = {'specialists_memory': {'issued': {'bad': 'broken', 'null': None}, 'deferred': ['broken'], 'failed': {'bad': {'tick': 'oops'}}, 'sessions': ['broken']}}
        self.assertEqual(set(specialists.prepare(snap, state)), {'specialists_mech_mode', 'specialists_suppress_entity'})
        self.assertNotIn('specialists_memory', state)
        snap['development']['specialists']['rituals'] = self.dialog()
        state = {'specialists_memory': {'sessions': {'window1': {'edges': None, 'named': 'broken', 'pending': {'from': None}}}}}
        self.assertIn('specialists_ritual', specialists.prepare(snap, state))
        self.assertEqual(state['specialists_memory']['sessions']['window1']['edges'], [])

    def test_native_identity_parse_noops_hidden_and_map_source_contracts(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi'
        ritual = (root / 'Controllers/Colony/SpecialistRitualController.cs').read_text(encoding='utf-8')
        genetics = (root / 'Controllers/Colony/SpecialistGeneticsController.cs').read_text(encoding='utf-8')
        policy = (root / 'Controllers/Colony/SpecialistPolicyController.cs').read_text(encoding='utf-8')
        helper = (root / 'Helpers/SpecialistWindowSessionHelper.cs').read_text(encoding='utf-8')
        observed = (root / 'Helpers/SpecialistAutomationHelper.cs').read_text(encoding='utf-8')
        self.assertIn('ConditionalWeakTable<Window,Identity>', helper)
        self.assertIn('nameof(WindowStack.Add)', helper)
        for source in (ritual, genetics, policy):
            self.assertIn('SpecialistWindowSessionHelper.Matches(dialog,context)', source)
            self.assertIn('RequestParser.GetMapId(context)', source)
        self.assertNotIn('Find.CurrentMap', policy)
        self.assertIn('operation == "open" || operation == "select" ? RequestParser.GetIntParameter', genetics)
        self.assertIn('new[]{"assign","remove","spectate"}.Contains(operation)', ritual)
        self.assertIn('operation=="assign" || operation=="role"', ritual)
        self.assertIn('operation=="focus" || operation=="meditation_hour" ? RequestParser.GetIntParameter', policy)
        self.assertIn('assignments.RoleForPawn(p)!=role', ritual)
        self.assertIn('!assignments.SpectatorsForReading.Contains(p)', ritual)
        self.assertIn('hediffs.Where(h => h.Visible).Select(h => h.def.defName)', observed)
        self.assertNotIn('Materials(Map map)', helper)


if __name__ == "__main__":
    unittest.main()

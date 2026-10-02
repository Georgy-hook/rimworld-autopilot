import copy
import json
import unittest
import colony_society as society


def snapshot(person=None):
    person = person or {"pawn_id": 1, "name": "Child", "needs": [{"def_name": "Learning", "level": .2}], "timetable": ["Sleep", "Work", "Anything"]}
    return {"map": {"id": 7}, "game": {"tick": 50000}, "development": {"society": {"available": True, "people": [person], "medicine": {"MedicineHerbal": 4}}}}


class Agent:
    def __init__(self, preferred):
        self.preferred = preferred
        self.calls = []
    def predict(self, state, questions):
        self.calls.append(copy.deepcopy(state))
        qid, q = next(iter(questions.items()))
        root = qid.split("_round_")[0]
        value = self.preferred.get(root)
        if value not in q["criteria"]:
            value = next((k for k in q["criteria"] if k != "defer"), next(iter(q["criteria"])))
        return {"answers": {qid: {"choice": value}}}


class Client:
    def __init__(self, context, applied=True):
        self.context = context
        self.posts = []
        self.applied = applied
    def get(self, path, **kwargs):
        return copy.deepcopy(self.context)
    def post(self, path, **kwargs):
        self.posts.append((path, kwargs))
        return {"applied": self.applied, "reason": "configured"}


class SocietyTests(unittest.TestCase):
    def test_learning_has_only_work_hours_and_changes_no_sleep(self):
        snap = snapshot()
        self.assertIn("society_free_time", society.prepare(snap, {}))
        plans = snap["development"]["society"]["options"]["society_free_time"]
        self.assertEqual([p["hour"] for p in plans.values()], [1])
        self.assertEqual(snap["development"]["society"]["people"][0]["timetable"][0], "Sleep")

    def test_active_medical_jobs_drafted_and_incapacitated_have_no_schedule_option(self):
        for change in ({"current_job": "TendPatient"}, {"current_job": "Rescue"}, {"current_job": "FeedPatient"}, {"current_job": "DoBill"}, {"downed": True}, {"drafted": True}, {"mental_state": True}):
            snap = snapshot()
            snap["development"]["society"]["people"][0].update(change)
            self.assertNotIn("society_free_time", society.prepare(snap, {}), change)

    def test_live_medical_ceiling_is_not_no_care_and_not_a_completed_tend(self):
        snap = snapshot({"pawn_id": 2, "medical_attention": True, "medical_care": "NoCare", "care_options": ["NoMeds", "HerbalOrWorse", "NormalOrWorse", "Best"]})
        society.prepare(snap, {})
        values = [p["value"] for p in snap["development"]["society"]["options"]["society_medical_care"].values()]
        self.assertIn("NoMeds", values)
        self.assertNotIn("NoCare", values)
        self.assertIn("does not guarantee", society.assess("society_medical_care", snap)["risk"])

    def test_prisoner_resistance_and_conversion_use_exported_options_only(self):
        snap = snapshot({"pawn_id": 3, "prisoner_mode": "AttemptRecruit", "prisoner_options": ["MaintainOnly", "AttemptRecruit", "ReduceResistance"]})
        society.prepare(snap, {})
        values = [p["value"] for p in snap["development"]["society"]["options"]["society_prisoner_policy"].values()]
        self.assertEqual(set(values), {"MaintainOnly", "ReduceResistance"})
        self.assertNotIn("Convert", values)

    def test_laya_can_defer_before_or_after_person_choice(self):
        for preferences in ({"society_free_time_person": "defer"}, {"society_free_time_person": "1", "society_free_time": "defer"}):
            snap = snapshot()
            society.prepare(snap, {})
            selected, _ = society.choose(Agent(preferences), {}, "society_free_time", snap)
            client = Client(snap["development"]["society"])
            self.assertEqual(society.execute(client, snap, {}, "society_free_time", selected)["reason"], "laya_deferred")
            self.assertFalse(client.posts)

    def test_stale_choice_revalidated_before_any_post(self):
        snap = snapshot()
        society.prepare(snap, {})
        selected, _ = society.choose(Agent({}), {}, "society_free_time", snap)
        changed = copy.deepcopy(snap["development"]["society"])
        changed["people"][0]["timetable"][1] = "Sleep"
        client = Client(changed)
        result = society.execute(client, snap, {}, "society_free_time", selected)
        self.assertFalse(result["applied"])
        self.assertFalse(client.posts)

    def test_policy_post_exact_and_cooldown_only_for_applied(self):
        for applied in (False, True):
            snap = snapshot()
            society.prepare(snap, {})
            selected, _ = society.choose(Agent({}), {}, "society_free_time", snap)
            client = Client(snap["development"]["society"], applied)
            state = {}
            society.execute(client, snap, state, "society_free_time", selected)
            self.assertEqual(client.posts[0][1]["body"], {"map_id": 7, "pawn_id": 1, "kind": "timetable", "hour": 1, "value": "Joy"})
            self.assertEqual(bool(state.get("issued")), applied)

    def test_unavailable_endpoint_is_honest_no_options(self):
        class Missing:
            def get(self, *args, **kwargs):
                raise RuntimeError("endpoint unavailable")
        snap = snapshot()
        snap["development"]["society"] = society.collect(Missing(), snap)
        self.assertFalse(snap["development"]["society"]["available"])
        self.assertEqual(society.prepare(snap, {}), [])

    def test_director_details_are_ignored_and_defer_has_cooldown(self):
        snap = snapshot()
        society.prepare(snap, {})
        selected, _ = society.choose(Agent({}), {}, "society_free_time", snap)
        selected.update({"architecture_context": {}, "other_options": ["foreign"], "untrusted": 9})
        client = Client(snap["development"]["society"])
        self.assertTrue(society.execute(client, snap, {}, "society_free_time", selected)["applied"])
        self.assertNotIn("untrusted", client.posts[0][1]["body"])
        state = {}
        society.execute(client, snap, state, "society_free_time", {"defer": True})
        self.assertNotIn("society_free_time", society.prepare(snap, state))

    def test_selected_patient_keeps_diagnosis_stock_beliefs_in_choice_context(self):
        snap = snapshot({"pawn_id": 2, "name": "Patient", "medical_attention": True, "medical_care": "NoMeds", "care_options": ["NoMeds", "Best"], "conditions": [{"def_name": "Infection", "immunity": .3, "severity": .5}], "beliefs": ["MedicalDrugUse_Prohibited"]})
        society.prepare(snap, {})
        agent = Agent({})
        society.choose(agent, {}, "society_medical_care", snap)
        effects = agent.calls[-1]["effects"]
        selected = next(e for k, e in effects.items() if k != "defer")
        self.assertIn("Infection s=0.5 i=0.3", selected["benefit"])
        self.assertIn("MedicineHerbal", selected["cost"])
        self.assertIn("MedicalDrugUse_Prohibited", selected["risk"])

    def native_snapshot(self, kind="baby_feed"):
        snap = snapshot()
        snap["development"]["society"]["native_options"] = [{"kind": kind, "pawn_id": 1, "worker_id": 8, "target_id": 9, "letter_id": 10, "value": "native", "label": "care", "effects": dict(benefit="starving baby food=.05", risk="caregiver exposure", cost="milk", inaction="starvation", uncertainty="completion") }]
        return snap

    def test_native_job_exact_payload_and_stale_worker(self):
        snap = self.native_snapshot()
        society.prepare(snap, {})
        selected, _ = society.choose(Agent({}), {}, "society_baby_feed", snap)
        selected["untrusted"] = "ignored"
        client = Client(snap["development"]["society"])
        self.assertTrue(society.execute(client, snap, {}, "society_baby_feed", selected)["applied"])
        self.assertEqual(client.posts[0][0], "/api/v1/society/order")
        self.assertEqual(client.posts[0][1]["body"], dict(map_id=7, kind="baby_feed", pawn_id=1, worker_id=8, target_id=9, letter_id=10, value="native"))
        client.context["native_options"][0]["worker_id"] = 12
        self.assertFalse(society.execute(client, snap, {}, "society_baby_feed", selected)["applied"])
        self.assertEqual(len(client.posts), 1)

    def test_twentieth_baby_need_survives_512_token_context(self):
        class PressureAgent:
            cfg = {"max_len": 512, "head_max_len": 192}
            def __init__(self): self.seen = []
            def tok(self, value, **kwargs): return {"input_ids": list(range((len(value)+3)//4))}
            def predict(self, visible, questions):
                self.seen.append(visible)
                qid = next(iter(questions))
                key = next((k for k, e in visible["effects"].items() if "starvation" in e["benefit"]), next(k for k in visible["effects"] if k != "defer"))
                return {"answers": {qid: {"choice": key}}}
        snap = self.native_snapshot()
        context = snap["development"]["society"]
        template = context["native_options"][0]
        context["native_options"] = [{**template, "pawn_id":i, "effects":{**template["effects"], "benefit": "starvation food=.01" if i==20 else "hungry food=.4"}} for i in range(1,21)]
        society.prepare(snap, {})
        agent = PressureAgent()
        selected, _ = society.choose(agent, {}, "society_baby_feed", snap)
        self.assertEqual(selected["pawn_id"], 20)
        for visible in agent.seen:
            self.assertLessEqual(len(agent.tok(json.dumps(visible, ensure_ascii=False, default=str))["input_ids"]), 312)
            for effect in visible["effects"].values():
                self.assertEqual(set(effect), {"benefit","risk","cost","inaction","uncertainty"})

    def test_growth_pending_defer_cooldown_and_tick_rollback(self):
        snap = self.native_snapshot("growth_prepare")
        state = {}
        society.prepare(snap, state)
        self.assertEqual(society.pending_action(snap["development"]["society"]), "society_growth_prepare")
        society.execute(Client({}), snap, state, "society_growth_prepare", {"defer": True})
        society.prepare(snap, state)
        self.assertIsNone(society.pending_action(snap["development"]["society"]))
        snap["game"]["tick"] = 10
        society.prepare(snap, state)
        self.assertEqual(society.pending_action(snap["development"]["society"]), "society_growth_prepare")

    def test_growth_exact_offered_traits_and_distinct_passions(self):
        snap = self.native_snapshot("growth")
        context = snap["development"]["society"]
        context["growth_moments"] = [dict(letter_id=10, pawn_id=1, ready=True, passion_gains=2, name="Child", traits=[dict(index=0,label="Kind",description="kindness")], no_trait=True, passions=[dict(def_name=k,label=k,current_passion="None",level=2) for k in ("Medical","Plants","Cooking")])]
        society.prepare(snap, {})
        selected, _ = society.choose(Agent({"society_growth_trait":"-2", "society_growth_passion_0":"Medical", "society_growth_passion_1":"Plants"}), {}, "society_growth", snap)
        self.assertEqual(selected["trait_index"], -2)
        self.assertEqual(selected["skill_defs"], ["Medical", "Plants"])
        for change in ({"skill_defs":["Medical","Medical"]}, {"skill_defs":["Medical","Shooting"]}, {"trait_index":4}, {"trait_index":True}):
            client = Client(context)
            self.assertFalse(society.execute(client, snap, {}, "society_growth", {**selected, **change})["applied"])
            self.assertFalse(client.posts)
        client = Client(context)
        self.assertTrue(society.execute(client, snap, {}, "society_growth", selected)["applied"])
        self.assertEqual(client.posts[0][1]["body"]["skill_defs"], ["Medical", "Plants"])
        client.context["growth_moments"][0]["ready"] = False
        self.assertFalse(society.execute(client, snap, {}, "society_growth", selected)["applied"])


if __name__ == "__main__":
    unittest.main()

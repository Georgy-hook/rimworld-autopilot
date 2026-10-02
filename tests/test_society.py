import copy
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
        facts = agent.calls[-1]["decision_facts"]
        self.assertEqual(facts["medicine"], {"MedicineHerbal": 4})
        self.assertEqual(facts["people"]["2"]["conditions"][0]["immunity"], .3)
        self.assertIn("MedicalDrugUse_Prohibited", facts["people"]["2"]["beliefs"])


if __name__ == "__main__":
    unittest.main()

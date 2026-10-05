import unittest

import rimworld_laya as bridge
import stream_observer as observer


def native(name="Hypothermia", severity=.35, stage=3, *, dead=False, job="TendPatient"):
    return [{"pawn": {"id": 355, "name": "Red", "health": 1}, "detailes": {
        "work_info": {"current_job": job},
        "medical_info": {"is_dead": dead, "hediffs": [{
            "def_name": name, "severity": severity, "cur_stage_index": stage,
            "cur_stage_label": "serious", "visible": True,
            "tendable_now": False, "immunity": None, "can_ever_kill": True}]}}}]


class ThermalObserverContract(unittest.TestCase):
    def test_native_stages_survive_projection_and_slow_both_illnesses(self):
        for name in ("Hypothermia", "Heatstroke"):
            for job in ("LayDown", "FinishFrame", "TendPatient"):
                with self.subTest(name=name, job=job):
                    rows = native(name, job=job)
                    pawns = bridge.normalize_colonists(rows)
                    h = pawns[0]["health_conditions"][0]
                    self.assertEqual((h["cur_stage_index"], h["cur_stage_label"]), (3, "serious"))
                    context = bridge.thermal_emergency_context(pawns)
                    self.assertEqual(context[0]["current_job"], job)
                    self.assertEqual(context[0]["reason"], "serious_native_stage")
                    self.assertFalse(observer._critical_disease(rows))
                    planner = observer.ObserverPlanner()
                    self.assertEqual(planner.pacing_actions({"is_paused": False}, 0,
                        critical_thermal=bool(context)), [{"kind": "ensure_speed", "speed": 1}])
                    self.assertEqual(planner.pacing_actions({"is_paused": False}, 1,
                        critical_thermal=True, director_is_ready=False),
                        [{"kind": "ensure_speed", "speed": 0}])

    def test_mild_dead_and_native_minor_do_not_trigger(self):
        for rows in (native(severity=.068, stage=1), native(dead=True),
                     native(severity=.5, stage=2)):
            self.assertEqual(bridge.thermal_emergency_context(bridge.normalize_colonists(rows)), [])

    def test_missing_stage_fallback_and_extreme_native_evidence(self):
        for stage in (None, "bad", True, -1):
            context = bridge.thermal_emergency_context(bridge.normalize_colonists(native(stage=stage)))
            self.assertEqual(context[0]["reason"], "serious_severity_fallback")
        rows = native(severity=.62, stage=4)
        rows[0]["detailes"]["medical_info"]["hediffs"][0]["is_currently_life_threatening"] = True
        self.assertEqual(bridge.thermal_emergency_context(bridge.normalize_colonists(rows))[0]["reason"], "life_threatening")

    def test_bounded_context_and_invalid_severity_are_safe(self):
        pawn = {"id": 1, "health_conditions": [{"def_name": "Heatstroke", "severity": float("nan")}]}
        self.assertEqual(bridge.thermal_emergency_context([pawn]), [])
        pawn["health_conditions"][0]["severity"] = 10 ** 1000
        self.assertEqual(bridge.thermal_emergency_context([pawn]), [])
        pawn["health_conditions"][0].update(severity=.5, cur_stage_index=3)
        self.assertEqual(len(bridge.thermal_emergency_context([pawn] * 100)), 16)


if __name__ == "__main__":
    unittest.main()

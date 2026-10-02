import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import stream_observer as observer


def pawn(pawn_id, *, health=1.0, drafted=False, distance=999, job="Wait", conditions=None):
    return {"id": pawn_id, "name": f"Colonist {pawn_id}", "position": {"x": pawn_id * 5, "z": 20},
            "health": health, "is_drafted": drafted, "distance_to_nearest_opponent": distance,
            "current_job": job, "health_conditions": conditions or []}


def state(colonists=None, hostiles=None, *, tick=1000, paused=False, map_id=1, corpses=None):
    return {"game": {"game_tick": tick, "is_paused": paused},
            "map": {"id": map_id, "seed": 10, "tile_id": 5, "size": "250x250"},
            "colonists": colonists if colonists is not None else [pawn(1), pawn(2)],
            "hostiles": hostiles or [], "corpses": corpses or []}


def kinds(actions):
    return [action["kind"] for action in actions]


class StreamObserverTests(unittest.TestCase):
    def test_research_and_quest_tabs_close_after_thirty_wall_seconds(self):
        closer = observer.TimedWindowCloser()
        windows = [{"window_type": "MainTabWindow_Research"},
                   {"window_type": "MainTabWindow_Quests"},
                   {"window_type": "Dialog_NodeTree"},
                   {"window_type": "MainTabWindow_Menu"}]
        self.assertEqual(closer.step(windows, 100), [])
        self.assertEqual(closer.step(windows, 129.9), [])
        due = closer.step(windows, 130)
        self.assertEqual({row["window_type"] for row in due},
                         {"MainTabWindow_Research", "MainTabWindow_Quests"})
        self.assertEqual(closer.step(windows, 131), [])
        self.assertEqual(len(closer.step(windows, 135)), 2)
        self.assertEqual(closer.step([], 136), [])
        self.assertEqual(closer.step([windows[0]], 137), [])
        self.assertEqual(closer.step([windows[0]], 166), [])
        self.assertEqual(closer.step([windows[0]], 167),
                         [{"kind": "close_window", "window_type": "MainTabWindow_Research"}])

    def test_window_close_targets_only_the_elapsed_tab(self):
        api = mock.Mock()
        observer._execute(api, {"kind": "close_window", "window_type": "MainTabWindow_Quests"})
        api.request.assert_called_once_with(
            "/api/v1/ui/window/close", post=True,
            body={"window_types": ["MainTabWindow_Quests"], "force_pause_only": False})

    def test_status_replace_contention_does_not_stop_observer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status = Path(temp_dir) / "observer-status.json"
            status.write_text('{"state":"running"}', encoding="utf-8")
            with mock.patch.object(Path, "replace", side_effect=PermissionError("busy")), \
                    mock.patch.object(observer.time, "sleep") as sleep:
                observer._write_json(status, {"state": "waiting"})
            self.assertEqual(json.loads(status.read_text(encoding="utf-8"))["state"], "running")
            self.assertEqual(sleep.call_count, 7)

    def test_death_is_shown_once_for_twenty_seconds_then_returns_to_living_pawn(self):
        planner = observer.ObserverPlanner()
        planner.step(state(), [], 0)
        corpse = {"def_name": "Corpse_Human", "label": "Corpse of Colonist 1", "position": {"x": 7, "z": 22}}
        event = {"id": 1, "name": "Colonist 1", "cause": "Bullet", "ticks": 1001}
        death_state = state([pawn(2)], tick=1001, corpses=[corpse])
        actions = planner.step(death_state, [event], 1)
        self.assertIn("position", kinds(actions))
        self.assertIn("caption", kinds(actions))
        self.assertIn("gunshot wounds", actions[-1]["text"])
        self.assertEqual(planner.shot.kind, "death")
        self.assertEqual(planner.shot.position, {"x": 7, "z": 22})
        self.assertEqual(planner.step(death_state, [], 20), [])
        actions = planner.step(death_state, [], 21)
        self.assertEqual(planner.shot.target_id, 2)
        self.assertNotIn("caption", kinds(actions))
        self.assertEqual(planner.step(death_state, [event], 22), [])

    def test_leaving_map_without_corpse_or_death_event_is_not_a_death(self):
        planner = observer.ObserverPlanner()
        planner.step(state(), [], 0)
        actions = planner.step(state([pawn(2)], tick=1001), [], 1)
        self.assertNotIn("caption", kinds(actions))
        self.assertEqual(planner.shown_deaths, set())

    def test_corpse_fallback_shows_unknown_cause_without_inventing_one(self):
        planner = observer.ObserverPlanner()
        planner.step(state([pawn(1, conditions=["Bite:Arm", "Malnutrition:whole body"]), pawn(2)]), [], 0)
        corpse = {"def_name": "Corpse_Human", "label": "Corpse of Colonist 1", "position": {"x": 5, "z": 20}}
        actions = planner.step(state([pawn(2)], tick=1001, corpses=[corpse]), [], 1)
        self.assertIn("last observed condition: Malnutrition", actions[-1]["text"])
        self.assertNotIn("Bite:Arm", actions[-1]["text"])

    def test_old_scar_alone_is_not_reported_as_death_cause(self):
        planner = observer.ObserverPlanner()
        planner.step(state([pawn(1, conditions=["Bite:Arm"]), pawn(2)]), [], 0)
        corpse = {"def_name": "Corpse_Human", "label": "Corpse of Colonist 1", "position": {"x": 5, "z": 20}}
        actions = planner.step(state([pawn(2)], tick=1001, corpses=[corpse]), [], 1)
        self.assertIn("Cause: not reported by the game", actions[-1]["text"])
        self.assertNotIn("Bite:Arm", actions[-1]["text"])

    def test_corpse_appearing_on_a_later_poll_still_gets_a_death_shot(self):
        planner = observer.ObserverPlanner()
        planner.step(state(), [], 0)
        planner.step(state([pawn(2)], tick=1001), [], 1)
        corpse = {"def_name": "Corpse_Human", "label": "Corpse of Colonist 1", "position": {"x": 7, "z": 22}}
        actions = planner.step(state([pawn(2)], tick=1002, corpses=[corpse]), [], 2)
        self.assertIn("caption", kinds(actions))
        self.assertEqual(planner.shot.position, {"x": 7, "z": 22})

    def test_after_death_the_camera_returns_to_a_survivor_before_hostiles(self):
        planner = observer.ObserverPlanner()
        planner.step(state(), [], 0)
        event = {"id": 1, "name": "Colonist 1", "cause": "Bullet", "ticks": 1001}
        under_threat = state([pawn(2)], hostiles=[pawn(50)], tick=1001)
        planner.step(under_threat, [event], 1)
        planner.step(under_threat, [], 21)
        self.assertEqual(planner.shot.target_id, 2)
        self.assertEqual(planner.shot.kind, "idle")

    def test_combat_rotates_two_fighters_every_thirty_seconds_and_changes_zoom_after_ten(self):
        planner = observer.ObserverPlanner()
        fighters = [pawn(1, drafted=True, distance=8), pawn(2, drafted=True, distance=10)]
        enemy = [pawn(50)]
        actions = planner.step(state(fighters, enemy), [], 0)
        self.assertEqual(planner.shot.target_id, 1)
        self.assertEqual(actions[-1], {"kind": "zoom", "zoom": observer.CLOSE_ZOOM})
        self.assertIn({"kind": "zoom", "zoom": observer.MEDIUM_ZOOM}, planner.step(state(fighters, enemy), [], 10))
        planner.step(state(fighters, enemy), [], 29)
        self.assertEqual(planner.shot.target_id, 1)
        planner.step(state(fighters, enemy), [], 30)
        self.assertEqual(planner.shot.target_id, 2)
        planner.step(state(fighters, enemy), [], 60)
        self.assertEqual(planner.shot.target_id, 1)

    def test_solo_fighter_stays_medium_after_first_closeup(self):
        planner = observer.ObserverPlanner()
        battle = state([pawn(1, drafted=True, distance=5)], [pawn(50)])
        planner.step(battle, [], 0)
        planner.step(battle, [], 10)
        actions = planner.step(battle, [], 35)
        self.assertEqual(planner.shot.target_id, 1)
        self.assertNotIn({"kind": "zoom", "zoom": observer.CLOSE_ZOOM}, actions)

    def test_attack_job_counts_as_action_even_without_reported_hostiles(self):
        planner = observer.ObserverPlanner()
        planner.step(state([pawn(1, job="AttackStatic")]), [], 0)
        self.assertEqual(planner.shot.kind, "combat")

    def test_speed_returns_to_three_after_pause_or_raid_slowdown_without_changing_shot_timing(self):
        planner = observer.ObserverPlanner()
        paused = state(paused=True)
        planner.step(paused, [], 0)
        self.assertEqual(planner.pacing_actions(paused["game"], 0),
                         [{"kind": "ensure_speed", "speed": 3}])
        self.assertEqual(planner.pacing_actions(paused["game"], 1), [])
        self.assertEqual(planner.pacing_actions(paused["game"], 5),
                         [{"kind": "ensure_speed", "speed": 3}])
        running = state()
        self.assertEqual(planner.pacing_actions(running["game"], 6), [])
        self.assertEqual(planner.pacing_actions(running["game"], 10),
                         [{"kind": "ensure_speed", "speed": 3}])
        # Shots still use monotonic wall seconds, not in-game ticks or speed.
        self.assertIn({"kind": "zoom", "zoom": observer.FAR_ZOOM},
                      planner.step(running, [], 10))
        planner.step(running, [], 45)
        self.assertEqual(planner.shot.target_id, 2)

    def test_home_fire_slows_immediately_then_returns_to_three(self):
        planner = observer.ObserverPlanner()
        game = state()["game"]
        self.assertEqual(planner.pacing_actions(game, 0),
                         [{"kind": "ensure_speed", "speed": 3}])
        self.assertEqual(planner.pacing_actions(game, 1, home_fire=True),
                         [{"kind": "ensure_speed", "speed": 1}])
        self.assertEqual(planner.pacing_actions(game, 2, home_fire=True), [])
        self.assertEqual(planner.pacing_actions(game, 3),
                         [{"kind": "ensure_speed", "speed": 3}])

    def test_critical_bleeding_slows_immediately_then_returns_to_three(self):
        planner = observer.ObserverPlanner()
        game = state()["game"]
        self.assertEqual(planner.pacing_actions(game, 0),
                         [{"kind": "ensure_speed", "speed": 3}])
        self.assertEqual(planner.pacing_actions(game, 1, critical_bleeding=True),
                         [{"kind": "ensure_speed", "speed": 1}])
        self.assertEqual(planner.pacing_actions(game, 2),
                         [{"kind": "ensure_speed", "speed": 3}])

    def test_dangerous_disease_slows_even_without_bleeding_or_low_summary_health(self):
        for name in ("WoundInfection", "Malaria", "Flu", "Plague"):
            rows = [{"health": 1, "detailes": {"medical_info": {"hediffs": [{
                "def_name": name, "severity": 0.82, "lethal_severity": 1,
                "immunity": 0.62, "can_ever_kill": True}]}}}]
            self.assertTrue(observer._critical_disease(rows))
            planner = observer.ObserverPlanner()
            game = state()["game"]
            self.assertEqual(planner.pacing_actions(game, 0, critical_disease=True),
                             [{"kind": "ensure_speed", "speed": 1}])
            rows[0]["detailes"]["medical_info"]["hediffs"][0]["immunity"] = 1
            self.assertFalse(observer._critical_disease(rows))
            self.assertEqual(planner.pacing_actions(game, 1), [{"kind": "ensure_speed", "speed": 3}])

    def test_downed_colonist_with_active_enemy_slows_then_returns_to_three(self):
        planner = observer.ObserverPlanner()
        game = state()["game"]
        self.assertEqual(planner.pacing_actions(game, 0),
                         [{"kind": "ensure_speed", "speed": 3}])
        self.assertEqual(planner.pacing_actions(game, 1, downed_under_attack=True),
                         [{"kind": "ensure_speed", "speed": 1}])
        self.assertEqual(planner.pacing_actions(game, 2),
                         [{"kind": "ensure_speed", "speed": 3}])

    def test_distant_enemy_does_not_slow_downed_colonist_recovery(self):
        colonists = [dict(pawn(1), is_downed=True), pawn(2)]
        far = [dict(pawn(50), distance_to_nearest_opponent=106)]
        near = [dict(pawn(50), distance_to_nearest_opponent=30)]
        self.assertFalse(observer._downed_under_attack(colonists, far))
        self.assertTrue(observer._downed_under_attack(colonists, near))
        self.assertFalse(observer._downed_under_attack([pawn(1), pawn(2)], near))

    def test_new_colony_rearms_three_times_speed_immediately(self):
        planner = observer.ObserverPlanner()
        first = state(map_id=1, tick=120000)
        planner.step(first, [], 100)
        self.assertEqual(planner.pacing_actions(first["game"], 100),
                         [{"kind": "ensure_speed", "speed": 3}])
        next_colony = state(map_id=2, tick=100)
        planner.step(next_colony, [], 101)
        self.assertEqual(planner.pacing_actions(next_colony["game"], 101),
                         [{"kind": "ensure_speed", "speed": 3}])

    def test_quiet_colony_rotates_and_zoom_out_is_far(self):
        planner = observer.ObserverPlanner()
        snapshot = state()
        planner.step(snapshot, [], 0)
        self.assertEqual(planner.shot.target_id, 1)
        self.assertIn({"kind": "zoom", "zoom": observer.FAR_ZOOM}, planner.step(snapshot, [], 10))
        planner.step(snapshot, [], 45)
        self.assertEqual(planner.shot.target_id, 2)
        planner.step(snapshot, [], 90)
        self.assertEqual(planner.shot.target_id, 1)

    def test_map_tour_covers_five_points_at_far_zoom_every_ten_minutes(self):
        planner = observer.ObserverPlanner()
        snapshot = state()
        planner.step(snapshot, [], 0)
        first = planner.step(snapshot, [], 600)
        self.assertEqual(planner.shot.kind, "tour")
        self.assertIn({"kind": "position", "x": 62, "z": 62}, first)
        self.assertIn({"kind": "zoom", "zoom": observer.FAR_ZOOM}, first)
        second = planner.step(snapshot, [], 605)
        self.assertIn({"kind": "position", "x": 187, "z": 62}, second)
        planner.step(snapshot, [], 625)
        self.assertEqual(planner.shot.kind, "idle")
        self.assertEqual(planner.next_tour_at, 1200)

    def test_map_tour_uses_horizontal_z_dimension_from_rimapi(self):
        snapshot = state()
        snapshot["map"]["size"] = "(250, 1, 250)"
        planner = observer.ObserverPlanner()
        planner.step(snapshot, [], 0)
        actions = planner.step(snapshot, [], 600)
        self.assertIn({"kind": "position", "x": 62, "z": 62}, actions)

    def test_thirty_raiders_get_one_second_each_and_then_colonist_returns(self):
        planner = observer.ObserverPlanner()
        enemies = [pawn(100 + index) for index in range(30)]
        snapshot = state(hostiles=enemies)
        planner.step(snapshot, [], 0)
        self.assertEqual(planner.shot.target_id, 100)
        planner.step(snapshot, [], 1)
        self.assertEqual(planner.shot.target_id, 101)
        planner.step(snapshot, [], 29)
        self.assertEqual(planner.shot.target_id, 129)
        planner.step(snapshot, [], 30)
        self.assertEqual(planner.shot.kind, "idle")
        self.assertIn(planner.shot.target_id, {1, 2})
        planner.step(snapshot, [], 31)
        self.assertEqual(planner.shot.kind, "idle")

    def test_sick_pawn_gets_priority_but_cannot_monopolize_camera(self):
        planner = observer.ObserverPlanner()
        snapshot = state([pawn(1, health=0.5, conditions=["Flu"]), pawn(2)])
        planner.step(snapshot, [], 0)
        self.assertEqual(planner.shot.kind, "medical")
        self.assertEqual(planner.shot.target_id, 1)
        planner.step(snapshot, [], 45)
        self.assertEqual(planner.shot.target_id, 2)
        planner.step(snapshot, [], 90)
        self.assertEqual(planner.shot.target_id, 1)

    def test_injured_but_stable_pawn_is_prioritized_once(self):
        planner = observer.ObserverPlanner()
        snapshot = state([pawn(1, conditions=["Gunshot:Leg"]), pawn(2)])
        planner.step(snapshot, [], 0)
        self.assertEqual(planner.shot.kind, "medical")
        planner.step(snapshot, [], 45)
        self.assertEqual(planner.shot.target_id, 2)

    def test_save_rollback_resets_old_deaths_and_shots(self):
        planner = observer.ObserverPlanner()
        planner.step(state(tick=5000), [], 0)
        planner.shown_deaths.add(1)
        planner.step(state(tick=1000), [], 1)
        self.assertEqual(planner.shown_deaths, set())

    def test_sse_parser_only_accepts_colonist_death(self):
        self.assertIsNone(observer.parse_sse_event("heartbeat", "{}"))
        self.assertIsNone(observer.parse_sse_event("pawn_killed", "bad json"))
        self.assertIsNone(observer.parse_sse_event("pawn_killed", "[]"))
        self.assertIsNone(observer.parse_sse_event("pawn_killed", json.dumps({"pawn": {"id": "bad", "isColonist": True}})))
        self.assertIsNone(observer.parse_sse_event("pawn_killed", json.dumps({"pawn": {"id": 1, "isColonist": False}})))
        self.assertEqual(observer.parse_sse_event("pawn_killed", json.dumps({
            "pawn": {"id": 3, "name": "Ada", "isColonist": True}, "cause": "Cut", "ticks": 42,
        }))["id"], 3)

    def test_commands_use_camera_and_speed_endpoints_only(self):
        api = mock.Mock()
        observer._execute(api, {"kind": "follow", "pawn_id": 7})
        observer._execute(api, {"kind": "position", "x": 10, "z": 20})
        observer._execute(api, {"kind": "zoom", "zoom": 18})
        observer._execute(api, {"kind": "ensure_speed", "speed": 3})
        self.assertEqual([call.args[0].split("?")[0] for call in api.request.call_args_list], [
            "/api/v1/camera/follow/pawn", "/api/v1/camera/change/position", "/api/v1/camera/change/zoom", "/api/v1/game/speed",
        ])
        self.assertEqual(api.request.call_args.args[0], "/api/v1/game/speed?speed=3")


if __name__ == "__main__":
    unittest.main()

"""Deterministic raid rehearsals against the decision and order layers."""

import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import colony_combat
import rimworld_laya as bridge


def fighter(pawn_id, *, ranged=True, weapon="Gun_Revolver", armor=0.0, distance=12,
            health=1.0, moving=1.0, range_cells=25):
    return {
        "id": pawn_id, "name": f"Colonist {pawn_id}", "health": health,
        "is_dead": False, "is_downed": False, "is_drafted": False,
        "has_ranged_weapon": ranged, "weapon_def": weapon, "weapon_label": weapon,
        "weapon_range": range_cells, "armor_sharp": armor, "moving": moving,
        "manipulation": 1.0, "sight": 1.0, "shooting_skill": 8,
        "melee_skill": 8, "distance_to_nearest_opponent": distance,
        "position": {"x": 10 + pawn_id, "z": 10}, "current_job": "Wait",
    }


def raid(fighters, hostiles, defenses=()):
    return {
        "game": {"is_paused": True},
        "map": {"id": 1, "enemies": len(hostiles)},
        "colonists": [{"id": pawn["id"], "rest": 0.8, "hunger": 0.8} for pawn in fighters],
        "combat": {
            "available": True, "colonists": fighters, "hostiles": hostiles,
            "available_weapons": [], "defenses": list(defenses),
        },
    }


class CombatScenarioTests(unittest.TestCase):
    def test_wall_blocked_gun_is_not_counted_as_cover_even_inside_range(self):
        shooter = fighter(1, distance=9, range_cells=25)
        shooter["shootable_opponent_ids"] = []
        hostile = {"id": 99, "kind_def": "GuineaPig", "health": 1.0,
                   "position": {"x": 20, "z": 10}}
        snapshot = raid([shooter], [hostile])
        self.assertFalse(colony_combat.has_clear_shot(shooter, [hostile]))
        context = bridge.combat_model_context(None, snapshot)
        self.assertEqual(context["covering_guns"], "0/1 have clear firing lanes")
        criteria = bridge.make_questions(snapshot)["threat_action"]["criteria"]
        self.assertIn("focus_fire", criteria)
        self.assertIn("advance_to_range", criteria)
        self.assertIn("clear firing lane", criteria["hold_cover"])

    def test_exposed_civilian_and_idle_guns_are_explicit_in_laya_context(self):
        civilian = fighter(3, ranged=False, weapon=None, distance=4, health=0.42)
        shooters = [fighter(1, distance=95, range_cells=37),
                    fighter(2, distance=101, range_cells=26)]
        snapshot = raid(shooters + [civilian], [{
            "id": 99, "kind_def": "Drifter", "health": 1.0,
            "weapon_def": "MeleeWeapon_Knife", "current_job": "AttackMelee",
            "position": {"x": 20, "z": 10},
        }])
        context = bridge.combat_model_context(None, snapshot)
        self.assertIn("0/2 guns have a clear firing lane", context["immediate_threat"])
        criteria = bridge.make_questions(snapshot)["threat_action"]["criteria"]
        self.assertIn("advance_to_range", criteria)
        self.assertIn("must move around walls", criteria["firing_line"])
        self.assertIn("unarmed", criteria["advance_to_range"])
        self.assertIn("captured", criteria["hold_cover"])

    def test_focus_fire_reissues_when_target_moves_out_of_range(self):
        shooter = fighter(1, distance=60, range_cells=37)
        shooter.update(is_drafted=True, current_job="AttackStatic", current_job_target_id=99)
        snapshot = raid([shooter], [{"id": 99, "kind_def": "Raider", "health": 1.0,
                                     "position": {"x": 70, "z": 10}}])
        action = bridge.plan_action(snapshot, {"choice": "focus_fire"})
        self.assertTrue(any(command.get("body", {}).get("tactic") == "focus_fire"
                            for command in action["commands"]))

    def test_focus_fire_reissues_when_wall_blocks_existing_attack_job(self):
        shooters = [fighter(1, distance=9), fighter(2, distance=10)]
        for shooter in shooters:
            shooter.update(is_drafted=True, current_job="AttackStatic",
                           current_job_target_id=99, shootable_opponent_ids=[])
        snapshot = raid(shooters, [{"id": 99, "kind_def": "GuineaPig", "health": 1.0,
                                    "position": {"x": 20, "z": 10}}])
        action = bridge.plan_action(snapshot, {"choice": "focus_fire"})
        tactic = next(command["body"] for command in action["commands"]
                      if command.get("body", {}).get("tactic") == "focus_fire")
        self.assertEqual(tactic["fighter_ids"], [1, 2])

    def test_compact_context_keeps_all_three_fighters_visible(self):
        class ShortWindowAgent:
            cfg = {"max_len": 512, "head_max_len": 192}

            def tok(self, text, add_special_tokens=False):
                return {"input_ids": [0] * ((len(text) + 1) // 2)}

        snapshot = raid(
            [fighter(1), fighter(2), fighter(3, ranged=False, weapon=None)],
            [{"id": 99, "kind_def": "Rhinoceros", "health": 0.7,
              "distance_to_nearest_opponent": 1}],
        )
        context = bridge.combat_model_context(ShortWindowAgent(), snapshot)
        self.assertEqual(len(context["fighters"]), 3)
        self.assertIn("unarmed", context["ally_weapons"])

    def test_pacifist_with_rifle_is_not_counted_or_commanded_as_a_shooter(self):
        gunner = fighter(1, distance=9)
        pacifist = fighter(2, distance=11, weapon="Gun_BoltActionRifle")
        combat = {"colonists": [gunner, pacifist]}
        bridge.annotate_combat_capability([
            {"id": 1, "skills": {"Shooting": {"disabled": False}, "Melee": {"disabled": False}}},
            {"id": 2, "skills": {"Shooting": {"disabled": True}, "Melee": {"disabled": True}}},
        ], combat)
        self.assertTrue(gunner["can_fight"])
        self.assertFalse(pacifist["can_fight"])
        hostile = {"id": 99, "kind_def": "Wolf_Timber", "health": 1.0,
                   "position": {"x": 20, "z": 10}}
        snapshot = raid(combat["colonists"], [hostile])
        context = bridge.combat_model_context(None, snapshot)
        self.assertIn("1 allies, 1 guns", context["forces"])
        self.assertIn("/pacifist", " ".join(context["fighters"]))
        self.assertIn("focus_fire", bridge.make_questions(snapshot)["threat_action"]["criteria"])
        action = bridge.plan_action(snapshot, {"choice": "focus_fire"})
        attacks = [row["body"] for row in action["commands"]
                   if row.get("body", {}).get("tactic") == "focus_fire"]
        self.assertEqual(attacks[0]["fighter_ids"], [1])

    def test_compact_contact_context_names_animal_and_bleeding_gunner_risk(self):
        class ShortWindowAgent:
            cfg = {"max_len": 512, "head_max_len": 192}

            def tok(self, text, add_special_tokens=False):
                return {"input_ids": [0] * ((len(text) + 1) // 2)}

        gunner = fighter(1, distance=1, health=0.85)
        gunner["bleeding_rate"] = 0.66
        snapshot = raid([gunner], [{"id": 99, "kind_def": "Wolf_Timber", "health": 1.0,
                                    "position": {"x": 12, "z": 10}}])
        context = bridge.combat_model_context(ShortWindowAgent(), snapshot)
        self.assertIn("Wolf_Timber", " ".join(context["hostiles"]))
        self.assertIn("Gun in melee", context["risk"])
        self.assertIn("bleeding 0.66", context["risk"])

    def test_revolver_vs_yorkshire_terrier_at_melee_range_offers_movement_or_melee(self):
        shooter = fighter(1, distance=1, health=0.79)
        shooter["tendable_now"] = True
        shooter["is_drafted"] = True
        shooter["current_job"] = "AttackStatic"
        shooter["current_job_target_id"] = 99
        snapshot = raid([shooter], [{
            "id": 99, "kind_def": "YorkshireTerrier", "name": "Yorkshire terrier",
            "health": 0.48, "position": {"x": 12, "z": 10}, "has_ranged_weapon": False,
            "current_job": "AttackMelee",
        }])
        criteria = bridge.make_questions(snapshot)["threat_action"]["criteria"]
        self.assertIn("backstep_fire", criteria)
        self.assertIn("engage_melee", criteria)
        self.assertNotIn("focus_fire", criteria)
        self.assertNotIn("engage_ranged", criteria)
        self.assertNotIn("emergency_self_tend", criteria)
        action = bridge.plan_action(snapshot, {"choice": "backstep_fire"})
        self.assertEqual(next(row["body"]["tactic"] for row in action["commands"]
                              if row.get("body", {}).get("tactic")), "backstep_fire")

    def test_unsupported_sword_charge_gets_a_real_model_support_choice(self):
        class SupportAgent:
            def __init__(self):
                self.questions = []

            def predict(self, state, questions):
                question = next(iter(questions))
                self.questions.append(question)
                selected = {
                    "threat_action": "melee_assault",
                    "unsupported_charge": "bring_guns_forward",
                    "melee_role_3": "guard_shooters",
                }[question]
                return {"answers": {question: {"choice": selected, "confidence": 0.9}}}

        snapshot = raid(
            [fighter(1, distance=58, range_cells=36),
             fighter(2, distance=61, range_cells=25),
             fighter(3, ranged=False, weapon="MeleeWeapon_Gladius", distance=40)],
            [{"id": 99, "kind_def": "Raider", "health": 1.0,
              "position": {"x": 70, "z": 10}}],
        )
        agent = SupportAgent()
        decision = bridge.decide(agent, snapshot, 0.0)
        self.assertEqual(decision["choice"], "advance_to_range")
        self.assertEqual(agent.questions, ["threat_action", "unsupported_charge", "melee_role_3"])
        self.assertIn("Only 0/2 guns can cover", colony_combat.available_tactics(snapshot)["melee_assault"])
        self.assertEqual(bridge.combat_model_context(agent, snapshot)["covering_guns"],
                         "0/2 have clear firing lanes")
        action = bridge.plan_action(snapshot, decision)
        tactics = [row["body"] for row in action["commands"] if row.get("body", {}).get("tactic")]
        self.assertIn(("advance_to_range", [1, 2]),
                      [(row["tactic"], row["fighter_ids"]) for row in tactics])
        self.assertIn(("guard_shooters", [3]),
                      [(row["tactic"], row["fighter_ids"]) for row in tactics])

    def test_unarmed_colonists_can_choose_trap_free_retreat_instead_of_idle_melee(self):
        snapshot = raid(
            [fighter(1, ranged=False, weapon=None, distance=8)],
            [{"id": 99, "kind_def": "Raider", "current_job": "AttackMelee", "health": 1.0,
              "position": {"x": 22, "z": 10}}],
        )
        options = bridge.make_questions(snapshot)["threat_action"]["criteria"]
        self.assertIn("civilian_retreat", options)
        self.assertNotIn("engage_melee", options)
        action = bridge.plan_action(snapshot, {"choice": "civilian_retreat"})
        tactic = next(row for row in action["commands"] if row["endpoint"] == "/api/v1/combat/tactic")
        self.assertEqual(tactic["body"]["fighter_ids"], [1])
        self.assertEqual(tactic["body"]["tactic"], "civilian_retreat")

    def test_unarmed_colonist_gets_own_role_while_shooters_hold_cover(self):
        class RoleAgent:
            def __init__(self):
                self.questions = []

            def predict(self, state, questions):
                question = next(iter(questions))
                self.questions.append(question)
                choice = {"threat_action": "hold_cover",
                          "melee_role_3": "withdraw_and_regroup"}[question]
                return {"answers": {question: {"choice": choice, "confidence": 0.7}}}

        snapshot = raid(
            [fighter(1, distance=35, range_cells=37),
             fighter(2, distance=40, range_cells=26),
             fighter(3, ranged=False, weapon=None, distance=2)],
            [{"id": 99, "kind_def": "GuineaPig", "health": 0.7,
              "position": {"x": 20, "z": 10}}],
        )
        agent = RoleAgent()
        decision = bridge.decide(agent, snapshot, 0.0)
        self.assertEqual(agent.questions, ["threat_action", "melee_role_3"])
        self.assertEqual(decision["melee_roles"], {3: "withdraw_and_regroup"})
        tactics = [row["body"] for row in bridge.plan_action(snapshot, decision)["commands"]
                   if row.get("body", {}).get("tactic")]
        self.assertIn(("hold_cover", [1, 2]),
                      [(row["tactic"], row["fighter_ids"]) for row in tactics])
        self.assertIn(("withdraw_and_regroup", [3]),
                      [(row["tactic"], row["fighter_ids"]) for row in tactics])

    def test_isolated_unarmed_role_exposes_support_gap_without_forcing_retreat(self):
        class RoleAgent:
            def __init__(self):
                self.role_question = None
                self.role_state = None

            def predict(self, state, questions):
                name = next(iter(questions))
                if name.startswith("melee_role_"):
                    self.role_question = questions[name]
                    self.role_state = state
                    selected = "withdraw_and_regroup"
                else:
                    selected = "hold_cover"
                return {"answers": {name: {"choice": selected, "confidence": 0.8}}}

        shooters = [fighter(1, distance=112, range_cells=37),
                    fighter(2, distance=116, range_cells=26)]
        shooters[0]["position"] = {"x": 130, "z": 100}
        shooters[1]["position"] = {"x": 134, "z": 100}
        isolated = fighter(3, ranged=False, weapon=None, distance=3)
        isolated["position"] = {"x": 20, "z": 100}
        enemy = {"id": 99, "kind_def": "GuineaPig", "health": 1.0,
                 "position": {"x": 23, "z": 100}}
        agent = RoleAgent()
        decision = bridge.decide(agent, raid(shooters + [isolated], [enemy]), 0.0)
        self.assertEqual(decision["melee_roles"], {3: "withdraw_and_regroup"})
        self.assertGreater(agent.role_state["role_target"]["nearest_gun_cells"], 100)
        criteria = agent.role_question["criteria"]
        self.assertIn("0/2 guns can cover", criteria["melee_assault"])
        self.assertIn("Regroup", criteria["guard_shooters"])
        self.assertIn("withdraw_and_regroup", criteria)
        self.assertNotIn("lure_enemy", criteria)

    def test_staging_raid_offers_weapon_equipping_as_a_real_choice(self):
        snapshot = raid(
            [fighter(1, ranged=False, weapon=None, distance=80)],
            [{"id": 99, "kind_def": "Raider", "current_job": "Wait_Wander", "position": {"x": 100, "z": 100}}],
        )
        snapshot["combat"]["available_weapons"] = [{"id": 71, "def_name": "Gun_BoltActionRifle", "is_ranged": True, "is_forbidden": True}]
        options = bridge.make_questions(snapshot)["threat_action"]["criteria"]
        self.assertIn("equip_ranged_weapon", options)
        action = bridge.plan_action(snapshot, {"choice": "equip_ranged_weapon"})
        self.assertEqual([row["endpoint"] for row in action["commands"][:2]],
                         ["/api/v1/things/set-forbidden", "/api/v1/pawn/job"])

    def test_equipping_ranged_weapon_replaces_a_melee_weapon_instead_of_noop(self):
        snapshot = raid(
            [fighter(1, distance=12), fighter(2, ranged=False, weapon="MeleeWeapon_Gladius", distance=25)],
            [{"id": 99, "kind_def": "Megascarab", "health": 1.0, "position": {"x": 25, "z": 10}}],
        )
        snapshot["combat"]["available_weapons"] = [
            {"id": 71, "def_name": "Gun_BoltActionRifle", "label": "bolt-action rifle",
             "is_ranged": True, "is_forbidden": False, "position": {"x": 14, "z": 10}},
        ]
        action = bridge.plan_action(snapshot, {"choice": "equip_ranged_weapon"})
        jobs = [row["body"] for row in action["commands"] if row["endpoint"] == "/api/v1/pawn/job"]
        self.assertEqual(jobs, [{"pawn_id": 2, "job_def": "Equip", "target_thing_id": 71}])

    def test_kite_keeps_a_shooter_covering_one_close_lure(self):
        snapshot = raid(
            [fighter(1, distance=8, range_cells=30), fighter(2, distance=15, range_cells=30)],
            [{"id": 99, "kind_def": "Megaspider", "health": 1.0, "has_ranged_weapon": False,
              "position": {"x": 22, "z": 10}}],
        )
        self.assertIn("kite", colony_combat.available_tactics(snapshot))
        action = bridge.plan_action(snapshot, {"choice": "kite", "selected_fighter_ids": [1, 2]})
        tactics = [row["body"] for row in action["commands"] if row["endpoint"] == "/api/v1/combat/tactic"]
        self.assertEqual([row["tactic"] for row in tactics], ["advance_to_range", "kite"])
        self.assertEqual({tuple(row["fighter_ids"]) for row in tactics}, {(1,), (2,)})
        self.assertFalse(any(row["endpoint"] == "/api/v1/pawn/edit/status" for row in action["commands"]))

    def test_kite_requires_coverage_and_does_not_turn_solo_roster_into_a_lure(self):
        snapshot = raid(
            [fighter(1, distance=55), fighter(2, distance=56)],
            [{"id": 99, "kind_def": "Megaspider", "health": 1.0, "has_ranged_weapon": False,
              "position": {"x": 100, "z": 100}}],
        )
        self.assertNotIn("kite", colony_combat.available_tactics(snapshot))
        snapshot["combat"]["colonists"][0]["distance_to_nearest_opponent"] = 8
        snapshot["combat"]["colonists"][1]["distance_to_nearest_opponent"] = 12
        action = bridge.plan_action(snapshot, {"choice": "kite", "selected_fighter_ids": [1]})
        self.assertFalse(any(row.get("body", {}).get("tactic") == "kite" for row in action.get("commands", [])))

    def test_kite_covering_shooter_can_follow_a_lure_just_beyond_gun_range(self):
        snapshot = raid(
            [fighter(1, distance=8, range_cells=25), fighter(2, distance=31, range_cells=25)],
            [{"id": 99, "kind_def": "Megaspider", "health": 1.0, "has_ranged_weapon": False,
              "position": {"x": 22, "z": 10}}],
        )
        self.assertIn("kite", colony_combat.available_tactics(snapshot))
        action = bridge.plan_action(snapshot, {"choice": "kite", "selected_fighter_ids": [1, 2]})
        tactics = [row["body"] for row in action["commands"] if row["endpoint"] == "/api/v1/combat/tactic"]
        self.assertEqual(tactics[0]["tactic"], "advance_to_range")
        self.assertEqual(tactics[0]["fighter_ids"], [2])
        self.assertEqual(tactics[1]["fighter_ids"], [1])

    def test_insects_offer_backstep_and_melee_screen_as_separate_choices(self):
        snapshot = raid(
            [fighter(1, distance=5), fighter(2, distance=9),
             fighter(3, ranged=False, weapon="MeleeWeapon_Gladius", distance=6)],
            [{"id": 99, "kind_def": "Megaspider", "health": 1.0, "has_ranged_weapon": False,
              "position": {"x": 18, "z": 10}}],
        )
        options = bridge.make_questions(snapshot)["threat_action"]["criteria"]
        self.assertIn("backstep_fire", options)
        self.assertIn("screen_melee", options)
        self.assertIn("nearby melee enemy", options["focus_fire"])
        backstep = bridge.plan_action(snapshot, {"choice": "backstep_fire", "selected_fighter_ids": [1, 2]})
        tactic = next(row["body"] for row in backstep["commands"] if row.get("body", {}).get("tactic") == "backstep_fire")
        self.assertEqual(tactic["tactic"], "backstep_fire")
        self.assertEqual(tactic["fighter_ids"], [1, 2])
        screen = bridge.plan_action(snapshot, {"choice": "screen_melee", "selected_fighter_ids": [1, 3]})
        tactics = [row["body"] for row in screen["commands"] if row.get("body", {}).get("tactic")]
        self.assertEqual([(row["tactic"], row["fighter_ids"]) for row in tactics], [
            ("screen_melee", [3]), ("focus_fire", [1, 2]),
        ])

    def test_mixed_group_chooses_melee_role_and_orders_everyone_in_one_cycle(self):
        class MixedAgent:
            def __init__(self):
                self.questions = []

            def predict(self, state, questions):
                question = next(iter(questions))
                self.questions.append(question)
                choice = "focus_fire" if question == "threat_action" else "screen_melee"
                return {"answers": {question: {"choice": choice, "confidence": 0.9}}}

        snapshot = raid(
            [fighter(1, distance=8), fighter(2, distance=9),
             fighter(3, ranged=False, weapon="MeleeWeapon_LongSword", distance=7)],
            [{"id": 99, "kind_def": "Megaspider", "health": 0.7,
              "position": {"x": 18, "z": 10}}],
        )
        agent = MixedAgent()
        decision = bridge.decide(agent, snapshot, 0.0)
        self.assertEqual(agent.questions, ["threat_action", "melee_role_3"])
        self.assertEqual(decision["melee_roles"], {3: "screen_melee"})
        action = bridge.plan_action(snapshot, decision)
        tactics = [row["body"] for row in action["commands"] if row.get("body", {}).get("tactic")]
        self.assertEqual([(row["tactic"], row["fighter_ids"]) for row in tactics], [
            ("focus_fire", [1, 2]), ("screen_melee", [3]),
        ])

        for pawn in snapshot["combat"]["colonists"][:2]:
            pawn.update(is_drafted=True, current_job="AttackStatic", current_job_target_id=99)
        again = bridge.plan_action(snapshot, decision)
        self.assertEqual([row["body"]["tactic"] for row in again["commands"]
                          if row.get("body", {}).get("tactic")], ["screen_melee"])

    def test_mixed_group_can_explicitly_withdraw_melee_without_silently_undrafting_shooters(self):
        snapshot = raid(
            [fighter(1, distance=8), fighter(2, distance=9),
             fighter(3, ranged=False, weapon="MeleeWeapon_LongSword", distance=7)],
            [{"id": 99, "kind_def": "Megaspider", "health": 0.7,
              "position": {"x": 18, "z": 10}}],
        )
        action = bridge.plan_action(snapshot, {"choice": "backstep_fire", "melee_role": "withdraw_and_regroup"})
        tactics = [row["body"] for row in action["commands"] if row.get("body", {}).get("tactic")]
        self.assertEqual([(row["tactic"], row["fighter_ids"]) for row in tactics], [
            ("backstep_fire", [1, 2]), ("withdraw_and_regroup", [3]),
        ])

    def test_two_swords_can_choose_full_assault_while_one_shooter_fires(self):
        class AssaultAgent:
            def __init__(self):
                self.melee_options = None

            def predict(self, state, questions):
                question = next(iter(questions))
                if question.startswith("melee_role_"):
                    self.melee_options = set(questions[question]["criteria"])
                chosen = "focus_fire" if question == "threat_action" else "melee_assault"
                return {"answers": {question: {"choice": chosen, "confidence": 0.9}}}

        snapshot = raid(
            [fighter(1, distance=12),
             fighter(2, ranged=False, weapon="MeleeWeapon_LongSword", distance=11),
             fighter(3, ranged=False, weapon="MeleeWeapon_Gladius", distance=10)],
            [{"id": 99, "kind_def": "Megaspider", "health": 0.8,
              "position": {"x": 24, "z": 10}}],
        )
        agent = AssaultAgent()
        decision = bridge.decide(agent, snapshot, 0.0)
        self.assertEqual(decision["melee_roles"], {2: "melee_assault", 3: "melee_assault"})
        self.assertIn("melee_assault", agent.melee_options)
        self.assertIn("guard_shooters", agent.melee_options)
        self.assertIn("withdraw_and_regroup", agent.melee_options)
        action = bridge.plan_action(snapshot, decision)
        tactics = [row["body"] for row in action["commands"] if row.get("body", {}).get("tactic")]
        self.assertEqual([(row["tactic"], row["fighter_ids"]) for row in tactics], [
            ("focus_fire", [1]), ("melee_assault", [2, 3]),
        ])

    def test_five_shooters_and_two_swords_can_split_lure_and_attack_roles(self):
        class SplitAgent:
            def __init__(self):
                self.role_targets = []

            def predict(self, state, questions):
                question = next(iter(questions))
                if question.startswith("melee_role_"):
                    self.role_targets.append(state["role_target"]["id"])
                chosen = {"threat_action": "focus_fire", "melee_role_6": "lure_enemy",
                          "melee_role_7": "melee_assault"}[question]
                return {"answers": {question: {"choice": chosen, "confidence": 0.9}}}

        team = [fighter(pawn_id, distance=12) for pawn_id in range(1, 6)]
        team += [fighter(6, ranged=False, weapon="MeleeWeapon_LongSword", distance=11),
                 fighter(7, ranged=False, weapon="MeleeWeapon_Gladius", distance=10)]
        snapshot = raid(team, [{"id": 99, "kind_def": "Megaspider", "health": 0.8,
                               "position": {"x": 24, "z": 10}}])
        state = bridge.decision_state(snapshot)
        self.assertEqual(state["force_balance"]["available_shooters"], 5)
        self.assertEqual(state["force_balance"]["available_armed_melee"], 2)
        self.assertTrue(any("#7" in row for row in state["fighters"]))
        agent = SplitAgent()
        decision = bridge.decide(agent, snapshot, 0.0)
        self.assertEqual(agent.role_targets, [6, 7])
        self.assertEqual(decision["melee_roles"], {6: "lure_enemy", 7: "melee_assault"})
        action = bridge.plan_action(snapshot, decision)
        tactics = [row["body"] for row in action["commands"] if row.get("body", {}).get("tactic")]
        self.assertEqual([(row["tactic"], row["fighter_ids"]) for row in tactics], [
            ("focus_fire", [1, 2, 3, 4, 5]), ("lure_enemy", [6]), ("melee_assault", [7]),
        ])

    def test_pure_melee_group_can_assign_different_roles_without_idle_fighters(self):
        class SplitAgent:
            def predict(self, state, questions):
                question = next(iter(questions))
                chosen = {"threat_action": "coordinate_melee_roles", "melee_role_1": "lure_enemy",
                          "melee_role_2": "melee_assault"}[question]
                return {"answers": {question: {"choice": chosen, "confidence": 0.9}}}

        snapshot = raid(
            [fighter(1, ranged=False, weapon="MeleeWeapon_LongSword", distance=10),
             fighter(2, ranged=False, weapon="MeleeWeapon_LongSword", distance=11)],
            [{"id": 99, "kind_def": "Megaspider", "health": 0.8,
              "position": {"x": 24, "z": 10}}],
        )
        self.assertIn("coordinate_melee_roles", bridge.make_questions(snapshot)["threat_action"]["criteria"])
        decision = bridge.decide(SplitAgent(), snapshot, 0.0)
        action = bridge.plan_action(snapshot, decision)
        tactics = [row["body"] for row in action["commands"] if row.get("body", {}).get("tactic")]
        self.assertEqual([(row["tactic"], row["fighter_ids"]) for row in tactics], [
            ("lure_enemy", [1]), ("melee_assault", [2]),
        ])

    def test_three_swords_can_attack_together_instead_of_becoming_civilian_retreaters(self):
        swords = [fighter(pawn_id, ranged=False, weapon="MeleeWeapon_LongSword",
                          distance=9, health=0.9, moving=0.9)
                  for pawn_id in (1, 2, 3)]
        snapshot = raid(swords, [
            {"id": 99, "kind_def": "Megaspider", "health": 0.8,
             "position": {"x": 20, "z": 10}},
        ])
        choices = colony_combat.available_tactics(snapshot)
        self.assertIn("melee_assault", choices)
        self.assertIn("melee_hold_line", choices)
        self.assertIn("withdraw_and_regroup", choices)
        self.assertNotIn("civilian_retreat", choices)
        action = bridge.plan_action(snapshot, {"choice": "melee_assault"})
        tactics = [row["body"] for row in action["commands"] if row.get("body", {}).get("tactic")]
        self.assertEqual(tactics[0]["tactic"], "melee_assault")
        self.assertEqual(tactics[0]["fighter_ids"], [1, 2, 3])
        self.assertFalse(any(row["tactic"] == "withdraw_and_regroup" for row in tactics))
        hold = bridge.plan_action(snapshot, {"choice": "melee_hold_line"})
        hold_tactics = [row["body"] for row in hold["commands"] if row.get("body", {}).get("tactic")]
        self.assertEqual([(row["tactic"], row["fighter_ids"]) for row in hold_tactics], [
            ("melee_hold_line", [1, 2, 3]),
        ])

        for pawn in swords:
            pawn["distance_to_nearest_opponent"] = 30
        choices = colony_combat.available_tactics(snapshot)
        self.assertIn("melee_assault", choices)
        self.assertIn("melee_hold_line", choices)
        self.assertNotIn("civilian_retreat", choices)
        self.assertNotIn("withdraw_and_regroup", choices)

    def test_out_of_range_shooters_can_advance_and_full_team_can_regroup(self):
        snapshot = raid(
            [fighter(1, distance=15, range_cells=25), fighter(2, distance=33, range_cells=25),
             fighter(3, ranged=False, weapon="MeleeWeapon_Gladius", distance=9)],
            [{"id": 99, "kind_def": "Mech_Militor", "health": 0.6,
              "weapon_def": "Gun_MilitorShotgun", "position": {"x": 32, "z": 10}}],
        )
        criteria = bridge.make_questions(snapshot)["threat_action"]["criteria"]
        self.assertIn("advance_to_range", criteria)
        self.assertIn("withdraw_and_regroup", criteria)
        self.assertIn("Only 1/2 armed shooters", criteria["focus_fire"])
        state = bridge.decision_state(snapshot)
        self.assertEqual(state["force_balance"]["active_enemies"], 1)
        self.assertEqual(state["force_balance"]["available_allies"], 3)
        self.assertIn("Gun_MilitorShotgun", state["force_balance"]["enemy_gear"])
        self.assertIn("withdrawing them", state["combat_tradeoff"])
        advance = bridge.plan_action(snapshot, {"choice": "advance_to_range", "selected_fighter_ids": [1, 2]})
        tactic = next(row["body"] for row in advance["commands"] if row.get("body", {}).get("tactic") == "advance_to_range")
        self.assertEqual(tactic["fighter_ids"], [1, 2])
        regroup = bridge.plan_action(snapshot, {"choice": "withdraw_and_regroup", "selected_fighter_ids": [1, 2, 3]})
        tactic = next(row["body"] for row in regroup["commands"] if row["endpoint"] == "/api/v1/combat/tactic")
        self.assertEqual(tactic["fighter_ids"], [1, 2, 3])
        self.assertEqual(tactic["tactic"], "withdraw_and_regroup")

    def test_far_assault_allows_laya_to_prepare_or_advance(self):
        shooters = [fighter(1, distance=120, range_cells=37), fighter(2, distance=122, range_cells=26)]
        snapshot = raid(shooters, [{"id": 99, "kind_def": "Raider", "current_job": "Goto",
                                    "distance_to_nearest_opponent": 120, "weapon_range": 0,
                                    "position": {"x": 120, "z": 120}}])
        criteria = bridge.make_questions(snapshot)["threat_action"]["criteria"]
        self.assertTrue({"prepare_undrafted", "hold_and_observe", "advance_to_range", "hold_cover"}.issubset(criteria))
        shooters[0]["distance_to_nearest_opponent"] = 22
        snapshot["combat"]["hostiles"][0]["distance_to_nearest_opponent"] = 22
        self.assertIn("focus_fire", bridge.make_questions(snapshot)["threat_action"]["criteria"])

    def test_repeating_retreat_outside_melee_reach_is_not_offered(self):
        survivor = fighter(1, distance=30, health=0.55)
        snapshot = raid([survivor], [{"id": 99, "kind_def": "Megaspider", "health": 0.7,
                                     "position": {"x": 45, "z": 10}}])
        self.assertNotIn("withdraw_and_regroup", colony_combat.available_tactics(snapshot))
        survivor["distance_to_nearest_opponent"] = 8
        self.assertIn("withdraw_and_regroup", colony_combat.available_tactics(snapshot))

    def test_already_drafted_defender_is_not_undrafted_during_distant_active_assault(self):
        shooter = fighter(1, distance=50, range_cells=25)
        shooter.update(is_drafted=True, current_job="Goto")
        snapshot = raid([shooter], [{"id": 99, "kind_def": "Megaspider", "health": 0.7,
                                     "current_job": "AttackMelee", "position": {"x": 65, "z": 10}}])
        criteria = bridge.make_questions(snapshot)["threat_action"]["criteria"]
        self.assertNotIn("prepare_undrafted", criteria)
        self.assertIn("advance_to_range", criteria)

    def test_focus_fire_keeps_out_of_range_shooters_in_the_squad_to_advance(self):
        shooters = [fighter(1, distance=25, range_cells=37), fighter(2, distance=25, range_cells=20)]
        snapshot = raid(shooters, [{"id": 99, "kind_def": "Raider", "health": 1.0,
                                    "current_job": "AttackMelee", "position": {"x": 36, "z": 10}}])
        action = bridge.plan_action(snapshot, {"choice": "focus_fire"})
        tactic = next(row for row in action["commands"] if row["endpoint"] == "/api/v1/combat/tactic")
        self.assertEqual(tactic["body"]["fighter_ids"], [1, 2])

    def test_outnumbered_emp_scout_risk_is_context_not_hard_veto(self):
        emp = fighter(1, weapon="Gun_EmpLauncher", distance=12, range_cells=24)
        rear = fighter(2, weapon="Gun_ChargeRifle", distance=38, range_cells=30)
        third = fighter(3, weapon="Gun_ChargeRifle", distance=40, range_cells=30)
        hostiles = [
            {"id": 90 + index, "kind_def": "Mech_Militor", "faction": "Mechanoid",
             "has_ranged_weapon": True, "health": 1.0,
             "position": {"x": 22 + index, "z": 10}}
            for index in range(4)
        ]
        snapshot = raid([emp, rear, third], hostiles)
        criteria = bridge.make_questions(snapshot)["threat_action"]["criteria"]
        self.assertIn("focus_fire", criteria)
        self.assertIn("fewer shooters", criteria["focus_fire"])
        self.assertNotIn("engage_ranged", criteria)
        self.assertIn("hold_cover", criteria)
        self.assertIn("firing_line", criteria)
        rear["distance_to_nearest_opponent"] = 25
        self.assertIn("focus_fire", bridge.make_questions(snapshot)["threat_action"]["criteria"])

    def test_normal_focus_fire_orders_every_shooter_including_the_wounded(self):
        class TeamAgent:
            def __init__(self):
                self.calls = []

            def predict(self, state, questions):
                self.calls.append(questions)
                if "threat_action" in questions:
                    return {"answers": {"threat_action": {"choice": "focus_fire", "confidence": 0.9}}}
                raise AssertionError("Normal attacks must not ask for a one-person roster")

        wounded = fighter(1, health=0.58)
        snapshot = raid(
            [wounded, fighter(2), fighter(3)],
            [{"id": 90 + index, "kind_def": "Mech_Militor", "health": 0.4,
              "position": {"x": 22 + index, "z": 10}} for index in range(3)],
        )
        agent = TeamAgent()
        decision = bridge.decide(agent, snapshot, 0.0)
        self.assertIsNone(decision["selected_fighter_ids"])
        self.assertEqual(len(agent.calls), 1)
        action = bridge.plan_action(snapshot, decision)
        tactic = next(row["body"] for row in action["commands"] if row.get("body", {}).get("tactic") == "focus_fire")
        self.assertEqual(tactic["fighter_ids"], [1, 2, 3])

    def test_mental_break_is_visible_but_not_counted_as_controllable_fighter(self):
        broken = fighter(1)
        broken.update(is_in_mental_state=True, current_job="FleeAndCower")
        snapshot = raid([broken, fighter(2)], [
            {"id": 99, "kind_def": "Megaspider", "health": 1.0,
             "position": {"x": 22, "z": 10}},
        ])
        state = bridge.decision_state(snapshot)
        self.assertEqual(state["force_balance"]["available_allies"], 1)
        self.assertEqual(state["force_balance"]["allies_in_mental_break"], 1)
        self.assertIn("mental_break", state["fighters"][0])
        action = bridge.plan_action(snapshot, {"choice": "focus_fire"})
        tactic = next(row["body"] for row in action["commands"] if row.get("body", {}).get("tactic") == "focus_fire")
        self.assertEqual(tactic["fighter_ids"], [2])

    def test_laya_can_choose_two_to_withdraw_and_one_to_cover(self):
        class WithdrawalAgent:
            def predict(self, state, questions):
                question = next(iter(questions))
                chosen = {"threat_action": "withdraw_and_regroup",
                          "combat_team": "team_2_3", "cover_tactic": "focus_fire"}[question]
                return {"answers": {question: {"choice": chosen, "confidence": 0.9}}}

        snapshot = raid(
            [fighter(1, distance=9, health=0.58), fighter(2, distance=10), fighter(3, distance=11)],
            [{"id": 99, "kind_def": "Mech_Militor", "health": 0.4,
              "weapon_def": "Gun_MilitorShotgun", "position": {"x": 22, "z": 10}}],
        )
        decision = bridge.decide(WithdrawalAgent(), snapshot, 0.0)
        self.assertEqual(decision["selected_fighter_ids"], [2, 3])
        self.assertEqual(decision["cover_tactic"], "focus_fire")
        action = bridge.plan_action(snapshot, decision)
        tactics = [row["body"] for row in action["commands"] if row.get("body", {}).get("tactic")]
        self.assertEqual([(row["tactic"], row["fighter_ids"]) for row in tactics], [
            ("withdraw_and_regroup", [2, 3]), ("focus_fire", [1]),
        ])

    def test_emergency_self_tend_is_a_safe_model_choice_far_from_enemy(self):
        patient = fighter(1, health=0.53, distance=30)
        patient.update(tendable_now=True, bleeding_rate=0.15, is_drafted=True)
        snapshot = raid([patient, fighter(2, distance=32)], [
            {"id": 99, "kind_def": "Megaspider", "health": 1.0,
             "position": {"x": 50, "z": 50}},
        ])
        criteria = bridge.make_questions(snapshot)["threat_action"]["criteria"]
        self.assertIn("emergency_self_tend", criteria)
        action = bridge.plan_action(snapshot, {"choice": "emergency_self_tend", "medical_target_id": 1})
        self.assertEqual(action["commands"][0]["body"], {"pawn_id": 1, "is_drafted": False})
        self.assertEqual(action["commands"][1]["body"], {
            "patient_pawn_id": 1, "doctor_pawn_id": 1, "self_tend": True,
        })
        patient["distance_to_nearest_opponent"] = 8
        self.assertIn("emergency_self_tend", bridge.make_questions(snapshot)["threat_action"]["criteria"])
        self.assertIn("Close enemies", bridge.make_questions(snapshot)["threat_action"]["criteria"]["emergency_self_tend"])
        close_action = bridge.plan_action(snapshot, {"choice": "emergency_self_tend", "medical_target_id": 1})
        self.assertTrue(any(row["endpoint"] == "/api/v1/pawn/medical/tend" for row in close_action["commands"]))

    def test_staging_tournament_still_exposes_preemptive_strike(self):
        class ModelLikeAgent:
            cfg = {"max_len": 512, "head_max_len": 192}
            def __init__(self):
                self.calls = []
            @staticmethod
            def tok(value, add_special_tokens=False):
                return {"input_ids": value.split()}
            def predict(self, state, questions):
                self.calls.append((state, questions))
                question_id, question = next(iter(questions.items()))
                options = question["criteria"]
                selected = "preemptive_strike" if "preemptive_strike" in options else next(iter(options))
                return {"answers": {question_id: {"choice": selected, "confidence": 0.6}}}

        snapshot = raid([fighter(1, distance=80, range_cells=37), fighter(2, distance=82, range_cells=26),
                         fighter(3, distance=83, range_cells=32)],
                        [{"id": 99, "kind_def": "Raider", "current_job": "Wait_Wander",
                          "distance_to_nearest_opponent": 80, "position": {"x": 100, "z": 100}}])
        offered = set(bridge.make_questions(snapshot)["threat_action"]["criteria"])
        self.assertGreater(len(offered), 6)
        agent = ModelLikeAgent()
        decision = bridge.decide(agent, snapshot, 0.0)
        self.assertEqual(decision["choice"], "preemptive_strike")
        considered = set().union(*(set(next(iter(questions.values()))["criteria"])
                                  for _, questions in agent.calls if "_round_" in next(iter(questions))))
        self.assertEqual(considered, offered)
        self.assertIn("forces", decision["raw"]["visible_state"])

    def test_self_tend_does_not_require_an_arbitrary_health_threshold(self):
        patient = fighter(1, health=0.9, distance=30)
        patient.update(tendable_now=True, bleeding_rate=0.01)
        snapshot = raid([patient, fighter(2, distance=30)], [
            {"id": 99, "kind_def": "Raider", "health": 1.0, "position": {"x": 50, "z": 50}},
        ])
        self.assertIn("emergency_self_tend", bridge.make_questions(snapshot)["threat_action"]["criteria"])

    def test_squirrel_raid_does_not_send_unarmed_civilian_into_melee(self):
        snapshot = raid(
            [fighter(1), fighter(2, ranged=False, weapon=None)],
            [{"id": 99, "kind_def": "Squirrel", "health": 1.0, "position": {"x": 22, "z": 10}}],
        )
        options = colony_combat.available_tactics(snapshot)
        self.assertIn("focus_fire", options)
        self.assertNotIn("melee_block", options)
        self.assertNotIn("rush_ranged", options)
        action = bridge.plan_action(snapshot, {"choice": "focus_fire"})
        bodies = [row["body"] for row in action["commands"] if row["endpoint"] == "/api/v1/combat/tactic"]
        self.assertEqual(next(body for body in bodies if body["tactic"] == "focus_fire")["fighter_ids"], [1])
        self.assertEqual(next(body for body in bodies if body["tactic"] == "focus_fire")["target_pawn_id"], 99)
        self.assertEqual(next(body for body in bodies if body["tactic"] == "withdraw_and_regroup")["fighter_ids"], [2])
        self.assertEqual(action["commands"][-1]["query"], {"speed": 1})

    def test_distant_preparing_raid_cannot_provoke_with_short_range_or_unarmed_pawns(self):
        snapshot = raid(
            [fighter(1, distance=80, range_cells=15), fighter(2, ranged=False, weapon=None, distance=80)],
            [{"id": 99, "kind_def": "Raider", "current_job": "Wait_Combat", "position": {"x": 100, "z": 100}}],
        )
        options = bridge.make_questions(snapshot)["threat_action"]["criteria"]
        self.assertIn("prepare_undrafted", options)
        self.assertIn("hold_and_observe", options)
        self.assertIn("advance_to_range", options)
        self.assertNotIn("preemptive_strike", options)

    def test_enemy_goto_is_an_assault_not_preparation(self):
        snapshot = raid(
            [fighter(1, distance=80, range_cells=37), fighter(2, distance=82, range_cells=26)],
            [{"id": 99, "kind_def": "Raider", "current_job": "Goto", "position": {"x": 100, "z": 100}}],
        )
        self.assertNotIn("preemptive_strike", bridge.make_questions(snapshot)["threat_action"]["criteria"])

    def test_stage_lord_counts_as_preparation_before_first_pawn_job(self):
        shooters = [fighter(1, distance=80, range_cells=37), fighter(2, distance=82, range_cells=26)]
        hostile = {"id": 99, "kind_def": "Raider", "current_job": None,
                   "lord_toil_name": "LordToil_Stage", "position": {"x": 100, "z": 100}}
        snapshot = raid(shooters, [hostile])
        self.assertTrue(colony_combat.hostile_is_preparing(hostile))
        self.assertIn("preemptive_strike", bridge.make_questions(snapshot)["threat_action"]["criteria"])
        hostile["current_job"] = "Goto"
        self.assertFalse(colony_combat.hostile_is_preparing(hostile))

    def test_outnumbered_insect_raid_exposes_preemptive_risk_to_laya(self):
        shooters = [fighter(1, distance=85, range_cells=37), fighter(2, distance=86, range_cells=26)]
        hostiles = [
            {"id": 90 + index, "kind_def": "Megaspider", "health": 1.0,
             "current_job": "Wait_Wander", "position": {"x": 100 + index, "z": 100}}
            for index in range(3)
        ]
        snapshot = raid(shooters, hostiles)
        options = bridge.make_questions(snapshot)["threat_action"]["criteria"]
        self.assertIn("preemptive_strike", options)
        self.assertIn("outnumbered=True", options["preemptive_strike"])
        self.assertIn("prepare_undrafted", options)

    def test_ranged_raider_does_not_hide_preemptive_strike(self):
        snapshot = raid(
            [fighter(1, distance=80, range_cells=37), fighter(2, distance=82, range_cells=26)],
            [{"id": 99, "kind_def": "Raider", "current_job": "Wait_Wander",
              "has_ranged_weapon": True, "weapon_def": "Gun_Autopistol", "position": {"x": 100, "z": 100}}],
        )
        self.assertIn("preemptive_strike", bridge.make_questions(snapshot)["threat_action"]["criteria"])

    def test_staging_does_not_undraft_active_defenders_near_the_enemy(self):
        shooters = [fighter(1, distance=48, range_cells=37), fighter(2, distance=50, range_cells=26)]
        shooters[0].update(is_drafted=True, current_job="AttackStatic", current_job_target_id=99)
        snapshot = raid(shooters, [{"id": 99, "kind_def": "Raider", "health": 1.0,
                                    "current_job": "Wait_Wander", "position": {"x": 100, "z": 100}}])
        self.assertNotIn("prepare_undrafted", bridge.make_questions(snapshot)["threat_action"]["criteria"])

    def test_wounded_or_reserved_fighter_receives_a_regroup_order(self):
        shooters = [fighter(1), fighter(2, health=0.57)]
        for pawn in shooters:
            pawn["is_drafted"] = True
        snapshot = raid(shooters, [{"id": 99, "kind_def": "Raider", "health": 1.0,
                                    "current_job": "AttackMelee", "position": {"x": 22, "z": 10}}])
        action = bridge.plan_action(snapshot, {"choice": "focus_fire", "selected_fighter_ids": [1]})
        self.assertEqual(action["commands"][0]["body"], {
            "map_id": 1, "tactic": "withdraw_and_regroup",
            "fighter_ids": [2], "target_pawn_id": 99,
        })
        self.assertEqual(action["commands"][1]["body"]["fighter_ids"], [1])

    def test_solo_holdout_explicitly_orders_other_nearby_colonists_to_regroup(self):
        snapshot = raid(
            [fighter(1, distance=9), fighter(2, distance=10), fighter(3, distance=11)],
            [{"id": 99, "kind_def": "Megaspider", "health": 1.0,
              "position": {"x": 22, "z": 10}}],
        )
        action = bridge.plan_action(snapshot, {"choice": "focus_fire", "selected_fighter_ids": [1]})
        tactics = [row["body"] for row in action["commands"] if row["endpoint"] == "/api/v1/combat/tactic"]
        self.assertEqual(tactics[0]["tactic"], "withdraw_and_regroup")
        self.assertEqual(tactics[0]["fighter_ids"], [2, 3])
        self.assertEqual(tactics[1]["tactic"], "focus_fire")
        self.assertEqual(tactics[1]["fighter_ids"], [1])

    def test_kidnapper_is_priority_target_over_more_valuable_raider(self):
        snapshot = raid(
            [fighter(1)],
            [{"id": 98, "kind_def": "Raider", "combat_power": 100, "health": 1.0, "position": {"x": 15, "z": 10}},
             {"id": 99, "kind_def": "Raider", "combat_power": 20, "health": 1.0, "carrying_pawn_id": 3,
              "current_job": "Kidnap", "position": {"x": 25, "z": 10}}],
        )
        self.assertEqual(colony_combat.choose_default_target(snapshot, "focus_fire"), 99)

    def test_infestation_choke_requires_real_door_armed_armored_melee(self):
        insect = {"id": 99, "kind_def": "Megaspider", "health": 1.0, "position": {"x": 22, "z": 10}}
        unarmored = raid([fighter(1, ranged=False, weapon="MeleeWeapon_Gladius")], [insect], [{"kind": "door"}])
        self.assertNotIn("infestation_choke", colony_combat.available_tactics(unarmored))
        armored = raid([fighter(1, ranged=False, weapon="MeleeWeapon_Gladius", armor=0.55)], [insect], [{"kind": "door"}])
        self.assertIn("infestation_choke", colony_combat.available_tactics(armored))

    def test_combat_prompt_starts_with_live_battle_instead_of_farm_data(self):
        snapshot = raid([fighter(1)], [{"id": 99, "kind_def": "Raider", "health": 1.0, "current_job": "AttackStatic"}], [{"kind": "barricade"}])
        state = bridge.decision_state(snapshot)
        self.assertIn("fighters", state)
        self.assertIn("hostiles", state)
        self.assertIn("barricade", state["defenses"])
        self.assertNotIn("farm", state)
        self.assertIn("range=25", state["fighters"][0])


if __name__ == "__main__":
    unittest.main()

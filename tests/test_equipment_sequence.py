"""Replay the real first-start mismatch through preparation, selection and orders."""
import copy
import json
from pathlib import Path
import unittest

import colony_director as director
import colony_capabilities as capabilities


class Chooser:
    def __init__(self, pawn="254", weapon="5062"):
        self.preferred = {"colony_goal_domain": "strategy", "colony_goal_action": "equip_colonists",
                          "action": "equip_colonists", "weapon_pawn": pawn, "weapon_item": weapon}

    def predict(self, state, questions):
        question, description = next(iter(questions.items()))
        options = description["criteria"]
        preferred = self.preferred.get(question.split("_round_")[0], "equip_colonists")
        choice = preferred if preferred in options else next((k for k in options if k != "defer"), next(iter(options)))
        return {"answers": {question: {"choice": choice, "confidence": 1, "probabilities": {choice: 1}}}}


class Orders:
    def __init__(self, response=None):
        self.calls = []
        self.response = response if response is not None else {"success": True}

    def post(self, path, **kwargs):
        self.calls.append((path, kwargs))
        return copy.deepcopy(self.response)


def replay_snapshot():
    return json.loads((Path(__file__).parent / "fixtures/equipment-noop-20261003.json").read_text(encoding="utf-8"))


class EquipmentSequenceTests(unittest.TestCase):
    def test_actual_start_only_offers_executable_founder_then_releases_development(self):
        snapshot, memory, client = replay_snapshot(), {"anchor": {"x": 120, "z": 120}}, Orders()
        choices, details = director.candidate_actions(None, snapshot, memory)
        self.assertIn("equip_colonists", choices)
        selection = director.choose_action(Chooser(), snapshot, choices)
        # The old selector chose armed Alyssa (254), then the executor silently
        # skipped her because the founder branch only accepted unarmed pawns.
        self.assertEqual(str(selection["weapon_pawn"]), "257")
        result = director.execute_action(client, snapshot, memory, selection["choice"],
                                         director.merge_decision_details(details, selection))
        self.assertIs(result["applied"], True)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0][1]["body"], {"pawn_id": 257, "job_def": "Equip",
            "target_thing_id": 5062, "map_id": 0, "allow_unforbid_equip": False})
        # Persisted memory + unchanged snapshots must not repeat this order.
        for cycle in range(8):
            memory = json.loads(json.dumps(memory))
            snapshot["game"]["tick"] += 10
            choices, _ = director.candidate_actions(None, snapshot, memory)
            self.assertNotIn("equip_colonists", choices, cycle)
            self.assertIn("build_starter_base", choices)

    def test_new_unarmed_subject_bypasses_existing_subject_dwell(self):
        snapshot, memory, client = replay_snapshot(), {"anchor": {"x": 120, "z": 120}}, Orders()
        choices, details = director.candidate_actions(None, snapshot, memory)
        selected = director.choose_action(Chooser(), snapshot, choices)
        director.execute_action(client, snapshot, memory, selected["choice"], director.merge_decision_details(details, selected))
        new = copy.deepcopy(next(p for p in snapshot["combat"]["colonists"] if p["id"] == 257))
        new["id"], new["name"] = 999, "New arrival"
        snapshot["combat"]["colonists"].append(new)
        for weapon in snapshot["combat"]["available_weapons"]:
            weapon.setdefault("compatible_pawn_ids", []).append(999)
        choices, _ = director.candidate_actions(None, snapshot, memory)
        self.assertIn("equip_colonists", choices)
        selected = director.choose_action(Chooser(pawn="999"), snapshot, choices)
        self.assertEqual(str(selected["weapon_pawn"]), "999")

    def test_rejected_and_malformed_acknowledgments_are_not_success(self):
        for response in ({"applied": False}, {"applied": "false"}, {}, {"ok": True}):
            with self.subTest(response=response):
                snapshot, memory, client = replay_snapshot(), {"anchor": {"x": 120, "z": 120}}, Orders(response)
                choices, details = director.candidate_actions(None, snapshot, memory)
                selected = director.choose_action(Chooser(pawn="257"), snapshot, choices)
                result = director.execute_action(client, snapshot, memory, selected["choice"], director.merge_decision_details(details, selected))
                self.assertIs(result["applied"], False)
                for cycle in range(8):
                    snapshot["game"]["tick"] += 400
                    choices, _ = director.candidate_actions(None, snapshot, memory)
                    self.assertNotIn("equip_colonists", choices)

    def test_equipment_does_not_interrupt_care_or_repeat_current_equip_job(self):
        for job in ("Equip", "TendPatient", "FeedPatient", "Rescue", "Ingest"):
            snapshot, memory = replay_snapshot(), {"anchor": {"x": 120, "z": 120}}
            for pawn in snapshot["combat"]["colonists"]:
                pawn["current_job"] = job
            choices, _ = director.candidate_actions(None, snapshot, memory)
            self.assertNotIn("equip_colonists", choices, job)
            self.assertNotIn("improve_weapon_loadout", choices, job)

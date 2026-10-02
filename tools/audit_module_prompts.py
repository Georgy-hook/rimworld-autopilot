"""Offline model-input audit. Uses tokenizer/config only; never loads weights."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "2"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from transformers import AutoTokenizer
    from laya.common import build_sequence, serialize_state
    import colony_modules
    import colony_sessions
    from tests.test_affordances import option
    from tests.test_production import ProductionTests, RecipeProductionTests, LogisticsProductionTests
    from tests.test_society import snapshot as society_snapshot
    from tests.test_specialists import snapshot as specialist_snapshot

    class Agent:
        cfg = json.loads((args.checkpoint / "rl_agent_config.json").read_text())
        tok = AutoTokenizer.from_pretrained(args.checkpoint / "tokenizer", local_files_only=True)
        calls = []

        def predict(self, state, questions):
            qid, question = next(iter(questions.items()))
            sequence, markers = build_sequence(self.tok, state,
                {"t": "choice", "ins": question["instructions"], "crit": question["criteria"]},
                self.cfg["max_len"], self.cfg["head_max_len"])
            ids = self.tok(serialize_state(state).replace(self.tok.mask_token, " "), add_special_tokens=False)["input_ids"]
            assert len(ids) <= 312, (qid, len(ids))
            assert sequence[-len(ids)-1:-1] == ids, ("encoder truncated state", qid)
            assert len(markers) == len(question["criteria"]), ("lost option", qid)
            cards = state.get("effects", {})
            assert len(cards) == len(question["criteria"]), ("missing consequence cards", qid, state)
            for card in cards.values():
                assert set(card) == {"benefit", "risk", "cost", "inaction", "uncertainty"}
                assert all(card.values()), ("empty field", qid)
            self.calls.append({"question": qid, "state_tokens": len(ids), "sequence_tokens": len(sequence),
                               "visible_state": state})
            selected = next((key for key in question["criteria"] if key not in {"defer", "cancel"}), next(iter(question["criteria"])))
            return {"answers": {qid: {"choice": selected}}}

    def snap(name, data):
        return {"map": {"id": 1}, "game": {"tick": 50000}, "development": {name: data}}

    patients = [{"pawn_id": 100+i, "name": f"Patient{i}", "conditions": [
        {"def_name": "Plague" if i == 19 else "Scratch", "severity": .9 if i == 19 else .1,
         "immunity": .4 if i == 19 else None, "life_threatening": i == 19}]} for i in range(20)]
    resilience = snap("resilience", {"patients": patients, "options": [
        {"kind": "tend", "worker_id": 1, "target_id": 100+i, "giver": "DoctorTendEmergency", "medicine_skill": 14}
        for i in range(20)]})
    sustenance = snap("sustenance", {
        "animals": [{"id": i, "food": .001 if i == 80 else .9, "rest": .5, "pregnant": False, "medical_care": "NoMeds"} for i in range(1,81)],
        "options": [{"key": f"care:{i}:2", "kind": "care", "target_id": i, "value": "2", "label": f"Cow{i} herbal",
                     "cost": "medicine", "risk": "competes with humans"} for i in range(1,81)]})
    recipes = RecipeProductionTests().snapshot()
    recipes["development"]["production"]["recipe_context"]["options"] = [RecipeProductionTests().plan(i) for i in range(50)]
    ship = snap("progression", {"native_milestones": [
        {"map_id": 1, "root_id": 2, "parts": {"engine": 3}, "required_parts": {"engine": 3},
         "has_hibernating_parts": True, "startup_days": 15, "armed_mobile_combat_colonists": 1, "downed_colonists": 2}]})
    scenarios = [
        ("sustenance", "sustenance_animal_welfare", sustenance),
        ("resilience", "resilience_tend", resilience),
        ("production", "production_recipe_batch", recipes),
        ("production", "production_material_logistics", LogisticsProductionTests().snapshot()),
        ("production", "production_utilities", ProductionTests().snapshot()),
        ("society", "society_free_time", society_snapshot()),
        ("specialists", "specialists_mech_mode", specialist_snapshot()),
        ("specialists", "specialists_suppress_entity", specialist_snapshot()),
        ("progression", "progression_ship", ship),
        ("affordances", "affordances_ability", snap("affordances", {"options": [
            option(i, (f"Способность {i} ")*50) for i in range(15)]})),
    ]
    agent = Agent()
    completed = []
    for name, action, snapshot in scenarios:
        module = colony_modules.owner(action)
        assert module is not None, action
        module.prepare(snapshot, {})
        module.choose(agent, {"endgame": "archonexus"}, action, snapshot)
        completed.append(action)
    colony_sessions.target_choice(agent, {"session_id": 1, "map_id": 1, "source": "Verb_CastAbility",
        "effect_label": "Coagulate", "effect_description": "Stop bleeding", "effect_cost": "hemogen",
        "options": [{"key": f"pawn:{i}", "kind": "pawn", "target_id": i, "x": i, "z": i,
                     "label": f"Pawn{i}", "health": .1 if i == 31 else 1,
                     "downed": i == 31, "bleed_rate": .8 if i == 31 else 0} for i in range(32)]})
    completed.append("native_target")
    result = {"checkpoint": str(args.checkpoint), "scenarios": completed, "model_weights_loaded": False,
              "max_len": agent.cfg["max_len"], "head_max_len": agent.cfg["head_max_len"],
              "full_state_retained": True, "calls": agent.calls}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"scenarios": len(completed), "comparisons": len(agent.calls),
        "max_state_tokens": max(row["state_tokens"] for row in agent.calls),
        "max_sequence_tokens": max(row["sequence_tokens"] for row in agent.calls),
        "full_state_retained": True, "model_weights_loaded": False}))


if __name__ == "__main__":
    main()

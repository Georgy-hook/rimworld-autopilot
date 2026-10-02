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
    import colony_strategy
    import colony_expeditions
    from laya_decisions import ask_laya_choice
    from tests.test_affordances import option
    from tests.test_expedition_contracts import plan as expedition_plan, Client as ExpeditionClient
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
            if "effects" in state:
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
        ("specialists", "specialists_royal_assign", snap("specialists", {"royal_assignments": [
            {"kind": "royal_bed", "pawn_id": i, "thing_id": 100+i,
             "label": f"Guest{i}: assign qualifying RoyalBed in room {i}",
             "description": "Actual room requirements met; assignment does not prove good mood or successful hospitality."}
            for i in range(12)]})),
        ("progression", "progression_ending", snap("progression", {"ending_journey": {"journeys": [
            {"map_id": 1, "object_id": 70, "team": "migration", "supply_days": days,
             "route": "ship_journey", "travel_days": 18.2, "native_approx_food_days": days,
             "food_margin_days": days-18.2, "pawn_ids": [3,4], "travelers": ["A","B"],
             "colonists_at_home": [], "food_nutrition": days*3.2, "home_food_nutrition": 0,
             "medicine_count": 4, "mass": 22, "capacity": 70} for days in (21,30)]}})),
        ("affordances", "affordances_ability", snap("affordances", {"options": [
            option(i, (f"Способность {i} ")*50) for i in range(15)]})),
    ]
    agent = Agent()
    completed = []
    for name, action, snapshot in scenarios:
        module = colony_modules.owner(action)
        assert module is not None, action
        module.prepare(snapshot, {})
        module.choose(agent, {"endgame": "archonexus", "goal_requirements": {
            "journey": {"route": "archonexus", "blockers": ["diet-allowed survival meals missing"], "ration_work": "Cooking8,ElectricStove"}}}, action, snapshot)
        completed.append(action)
    colony_sessions.target_choice(agent, {"session_id": 1, "map_id": 1, "source": "Verb_CastAbility",
        "effect_label": "Coagulate", "effect_description": "Stop bleeding", "effect_cost": "hemogen",
        "options": [{"key": f"pawn:{i}", "kind": "pawn", "target_id": i, "x": i, "z": i,
                     "label": f"Pawn{i}", "health": .1 if i == 31 else 1,
                     "downed": i == 31, "bleed_rate": .8 if i == 31 else 0} for i in range(32)]})
    completed.append("native_target")
    # Full strategy cascade: later choices used to disappear behind a large
    # progression/catalogue object despite the per-module prompt checks passing.
    doctrine = colony_strategy.choose_cascaded_doctrine(agent,
        {"people": 5, "needs": {"food": 300, "sheltered_beds": 5}},
        {"active_mods": [{"package_id": value} for value in colony_strategy.EXPANSION_PACKAGES.values()],
         "ending_progress": {"huge_catalogue": "irrelevant details " * 3000},
         "material_options": {"WoodLog": "wood", "Steel": "steel"}})
    assert doctrine["selection"]["endgame"] != "enduring_colony"
    completed.append("full_doctrine_cascade_all_dlc_fixture")
    ask_laya_choice(agent, {"decision_facts": {"endgame": "archonexus"}, "large_history": "x" * 30000},
        "legacy_large_context", "Choose the next native step", {"study": "Study the current archostructure", "wait": "Wait"})
    completed.append("legacy_oversized_context")
    colony_expeditions.prepare(ExpeditionClient({"plans": [expedition_plan()]}), agent,
        {"mode": "trade", "map_id": 0}, ask_laya_choice)
    expedition_effects = agent.calls[-1]["visible_state"]["effects"]["plan_1"]
    for field, fragment in (("benefit", "Outbound 2.00d return 3.00d"), ("risk", "Food 8.00d margin 3.00d"),
                            ("cost", "Mass 44.0/100.0kg"), ("inaction", "Home 2def med8"),
                            ("uncertainty", "ETA excludes formation/combat")):
        assert fragment in expedition_effects[field], ("lost expedition fact", field, expedition_effects)
    completed.append("expedition_roster_long_names_real_tokenizer")
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

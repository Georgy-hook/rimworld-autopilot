"""Offline model replay of the recorded startup fault; never connects to RimWorld.

The first decision revisits the offending equipment action. Later decisions use
the full candidate set. Transport acknowledges equipment only; stop before any
other action could be submitted. This verifies exit from the loop, not gameplay.
"""
from __future__ import annotations
import argparse
import copy
import json
import os
from pathlib import Path
import sys

os.environ.update(HF_HUB_OFFLINE="1", TOKENIZERS_PARALLELISM="false", LAYA_CPU_THREADS="4",
                  OMP_NUM_THREADS="4", MKL_NUM_THREADS="4")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import colony_director as director
import rimworld_laya as bridge


class EquipmentTransport:
    def __init__(self):
        self.orders = []

    def post(self, path, **kwargs):
        if path != "/api/v1/pawn/job" or kwargs.get("body", {}).get("job_def") != "Equip":
            raise AssertionError("Replay cannot submit non-equipment operations")
        self.orders.append({"path": path, **copy.deepcopy(kwargs)})
        return {"success": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=Path(__file__).resolve().parents[1] / "tests/fixtures/equipment-noop-20261003.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda", choices=("cuda", "cpu"))
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    memory = {"anchor": {"x": 120, "z": 120}}
    agent, client = bridge.load_agent(bridge.DEFAULT_MODEL, args.device), EquipmentTransport()
    records = []
    for cycle in range(8):
        candidates, details = director.candidate_actions(None, snapshot, memory)
        if cycle == 0:
            assert "equip_colonists" in candidates
            candidates = ["equip_colonists"]
        decision = director.choose_action(agent, snapshot, candidates)
        choice = decision["choice"]
        row = {"cycle": cycle, "tick": snapshot["game"]["tick"], "candidates": candidates,
               "decision": decision, "mode": "offline_model_replay"}
        if choice not in {"equip_colonists", "improve_weapon_loadout"}:
            row["result"] = {"not_executed": True, "reason": "Reached another development action"}
            records.append(row)
            break
        row["result"] = director.execute_action(client, snapshot, memory, choice,
                                                director.merge_decision_details(details, decision))
        records.append(row)
        memory = json.loads(json.dumps(memory))
        snapshot["game"]["tick"] += 10
    output = {"game_mutations": 0, "transport": "offline equipment acknowledgment double",
              "source": str(args.snapshot), "records": records, "orders": client.orders,
              "exited_equipment_loop": records[-1]["decision"]["choice"] not in {"equip_colonists", "improve_weapon_loadout"}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"choices": [r["decision"]["choice"] for r in records],
                      "orders": client.orders, "exited_equipment_loop": output["exited_equipment_loop"]}, ensure_ascii=False))
    return 0 if output["exited_equipment_loop"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

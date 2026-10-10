"""Load Laya and make a real diagnostic decision without connecting to RimWorld."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rimworld_laya as bridge


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    agent = bridge.load_agent(bridge.DEFAULT_MODEL, args.device)
    question = {"next_step": {"type": "choice", "instructions": "Compare the next ordinary colony action.",
                              "criteria": {"gather_food": "Gather available edible berries.",
                                           "research": "Work at an available research bench."}}}
    started = time.perf_counter()
    answer = agent.predict("A colony has little food and a capable, available worker. No attack is active.", question)
    result = {
        "laya_version": importlib.metadata.version("laya"),
        "runtime": agent.runtime_info(),
        "decision_ms": round((time.perf_counter() - started) * 1000, 2),
        "answer": answer["answers"]["next_step"],
        "offline_diagnostic_only": True,
    }
    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()

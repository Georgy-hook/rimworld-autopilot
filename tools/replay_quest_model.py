"""Read-only cached Laya quest diagnostics; no HTTP client, director or game."""
import argparse
import json
import os
from pathlib import Path
import sys

os.environ.update(HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false',
                  LAYA_CPU_THREADS='4', OMP_NUM_THREADS='4', MKL_NUM_THREADS='4')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import colony_quests as quests
import rimworld_laya as bridge


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding='utf-8-sig'))
    agent = bridge.load_agent(bridge.DEFAULT_MODEL, 'cuda')
    records = []
    for scenario in fixture['scenarios']:
        chosen, raw, plan = quests.review(agent, scenario['offer'], scenario['snapshot'], scenario.get('strategy'))
        records.append({"scenario": scenario['name'], "choice": chosen,
                        "plan": plan, "raw": raw})
        print(json.dumps({"scenario": scenario['name'], "choice": chosen,
                          "pages": raw.get('page_count')}, ensure_ascii=False), flush=True)
    args.output.write_text(json.dumps({"game_commands": 0, "api_contacted": False,
        "cpu_threads": 4, "device": "cuda", "not_a_survival_benchmark": True,
        "records": records}, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__': main()

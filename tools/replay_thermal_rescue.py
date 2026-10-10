"""Offline cached-model thermal rescue choice and persistence; no game sockets."""
import argparse
import copy
import json
import os
from pathlib import Path
import sys

os.environ.update(HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false', LAYA_CPU_THREADS='4', OMP_NUM_THREADS='4', MKL_NUM_THREADS='4')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
import rimworld_laya as bridge
import colony_director as director
import colony_resilience as resilience
from test_thermal_rescue_sequences import World, snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    agent = bridge.load_agent(bridge.DEFAULT_MODEL, 'cuda')
    records = []
    for reverse in (False, True):
        s = snapshot()
        second = copy.deepcopy(s['development']['resilience']['options'][0])
        second.update(worker_id=3, expected_current_job=None, expected_care_patient_id=None, care_yield_reason=None, travel_distance=60)
        s['colonists'].append({'id': 3, 'name': 'Idle helper', 'current_job': 'Wander', 'health_conditions': [], 'capacities': {'moving': 1, 'manipulation': 1}})
        s['combat']['colonists'].append({'id': 3, 'current_job': 'Wander'})
        s['development']['resilience']['options'].append(second)
        if reverse: s['development']['resilience']['options'].reverse()
        transport, memory = World(s), {}
        first = director.run_urgent_thermal_cycle(transport, agent, s, memory, args.output.with_suffix('.jsonl'))
        records.append({'reverse': reverse, 'record': first, 'orders': transport.orders})
        assert first is not None and first['decision']['choice'] != 'defer', 'Model deferred thermal rescue'
        assert first['result']['applied'] is True
        for _ in range(8):
            s['game']['tick'] += 600
            memory = json.loads(json.dumps(memory))
            assert director.run_urgent_thermal_cycle(transport, agent, s, memory, args.output.with_suffix('.jsonl')) is None
        assert len(transport.orders) == 1
    args.output.write_text(json.dumps({'offline': True, 'game_mutations': 0, 'native_offer_is_fixture': True,
        'live_survival_not_proven': True, 'records': records}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'choices': [x.get('choice', (x.get('record') or {}).get('decision', {}).get('choice')) for x in records],
                      'game_mutations': 0, 'rescue_persisted_eight_cycles': True}))


if __name__ == '__main__': main()

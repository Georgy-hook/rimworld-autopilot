"""Cached-model decisions over synthetic repair fixtures; no RimWorld client or sockets."""
import argparse
import copy
import json
import os
from pathlib import Path
import sys

os.environ.update(HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false', LAYA_CPU_THREADS='4',
                  OMP_NUM_THREADS='4', MKL_NUM_THREADS='4')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import colony_labor as labor
import colony_mining as mining
import colony_sustenance as sustenance
import rimworld_laya as bridge
from tests.test_postmortem_fault_sequences import mine_snapshot


class OfflineTransport:
    def __init__(self, context, endpoint):
        self.context, self.endpoint, self.orders = context, endpoint, []

    def get(self, path, **kwargs):
        if path != self.endpoint + '/context':
            raise AssertionError('Unexpected offline read: ' + path)
        return copy.deepcopy(self.context)

    def post(self, path, *, body):
        expected = self.endpoint + ('/order' if self.endpoint.endswith('/mining') else '/policy')
        if path != expected:
            raise AssertionError('Unexpected offline write: ' + path)
        self.orders.append({'path': path, 'body': copy.deepcopy(body)})
        return {'applied': True, 'reason': 'offline_ack_only'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    agent = bridge.load_agent(bridge.DEFAULT_MODEL, 'cuda')
    records = []
    for reverse in (False, True):
        snapshot = mine_snapshot()
        ore = snapshot['development']['mining']['options'][0]
        other = copy.deepcopy(ore)
        other.update(key='1:101', thing_ids=[101], product_def='Steel', ore_def='MineableSteel',
                     base_yield=40, nominal_market_value=76, remaining_hp=1500)
        snapshot['development']['mining']['options'] = [other, ore] if reverse else [ore, other]
        memory = {'doctrine': {'mining_product': 'mineable_jade'}}
        labor.prepare(snapshot, memory)
        assert 'mining_extract' in mining.prepare(snapshot, memory)
        selected, decision = mining.choose(agent, {}, 'mining_extract', snapshot)
        assert selected.get('mining_plan') in {'defer', ore['key'], other['key']}
        transport = OfflineTransport(snapshot['development']['mining'], '/api/v1/mining')
        result = mining.execute(transport, snapshot, memory, 'mining_extract', selected)
        mining.prepare(snapshot, memory)
        assert selected['mining_plan'] not in snapshot['development']['mining']['prepared_options']
        records.append({'scenario': 'exact_visible_mineral_choice', 'reverse': reverse,
                        'selection': selected, 'decision': decision, 'result': result, 'orders': transport.orders})

        snapshot = mine_snapshot()
        context = {'available': True, 'options': [
            {'key': 'penfeed:9:1:33:30:25', 'kind': 'penfeed', 'target_id': 9,
             'value': '1,33,30,25,16', 'label': 'Worker: haul 16 fresh rice into connected pen',
             'cost': '0.8 nutrition, 5.4 remaining human nutrition',
             'risk': 'Actual hauler and both routes rechecked; delivery and ingestion not proven'},
            {'key': 'warmspot:4:21:21', 'kind': 'warmspot', 'target_id': 4, 'value': '21,21',
             'label': 'Roofed warm animal sleeping spot: -22C to 21C',
             'cost': 'Loaded zero-work zero-material spot inside existing shelter',
             'risk': 'Patient remains outside until ordinary thermal rescue succeeds'}],
            'pens': [{'id': 9, 'enclosed': True, 'consumption_per_day': 2,
                      'pasture_nutrition_per_day': 0, 'stockpiled_nutrition': 0}],
            'animals': [{'id': 4, 'food': 0.4, 'downed': True,
                         'health': [{'def_name': 'Hypothermia', 'stage_index': 3}]}]}
        if reverse:
            context['options'].reverse()
        snapshot['development']['sustenance'] = context
        memory = {}
        assert 'sustenance_animal_welfare' in sustenance.prepare(snapshot, memory)
        selected, decision = sustenance.choose(agent, {}, 'sustenance_animal_welfare', snapshot)
        assert selected.get('sustenance_policy') in {'defer', *[p['key'] for p in context['options']]}
        transport = OfflineTransport(context, '/api/v1/sustenance')
        result = sustenance.execute(transport, snapshot, memory, 'sustenance_animal_welfare', selected)
        records.append({'scenario': 'finite_feed_or_warm_spot_choice', 'reverse': reverse,
                        'selection': selected, 'decision': decision, 'result': result, 'orders': transport.orders})
    output = {'offline': True, 'game_mutations': 0, 'survival_not_proven': True,
              'native_completion_not_proven': True, 'records': records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'scenarios': len(records), 'selections': [r['selection'] for r in records], 'game_mutations': 0}))


if __name__ == '__main__':
    main()

"""Offline model decisions on supplied native starvation snapshots; never contacts the game."""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
import time

os.environ.update(HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false', LAYA_CPU_THREADS='4', OMP_NUM_THREADS='4', MKL_NUM_THREADS='4')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import colony_capabilities as caps
import colony_director as director
import rimworld_laya as bridge


class CropTransport:
    """Actual acknowledgment shapes; only in-memory configuration, no client/socket."""
    def __init__(self, snapshot):
        self.snapshot, self.orders = snapshot, []

    def post(self, path, *, body):
        self.orders.append({'path': path, 'body': copy.deepcopy(body)})
        if path == '/api/v1/map/zone/growing/crop':
            site = next(s for s in self.snapshot['development']['plant_catalog']['growers']
                        if s.get('zone_id') == body.get('zone_id') and s.get('building_id') == body.get('building_id'))
            site['plant_def'] = body['plant_def']
            return {'success': True, 'affected_count': 0}
        if path == '/api/v1/colonist/work-priority':
            pawn = next(p for p in self.snapshot['colonists'] if p['id'] == body['id'])
            pawn['work_priorities'][body['work']]['priority'] = body['priority']
            return {'success': True}
        if path == '/api/v1/map/zone/growing/sowing':
            return {'success': True}
        raise AssertionError('Unimplemented offline operation: ' + path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    agent = bridge.load_agent(bridge.DEFAULT_MODEL, 'cuda')
    records = []
    for source in args.snapshot:
        original = json.loads(source.read_text(encoding='utf-8-sig'))
        for reverse in (False, True):
            s = copy.deepcopy(original)
            memory = {'anchor': {'x': 157, 'z': 135}, 'issued': {}}
            actions, details = director.candidate_actions(None, s, memory)
            if reverse: actions.reverse()
            assert 'configure_crop' not in actions and 'create_growing_zone' not in actions
            assert not set(actions).intersection({'sustenance_animal_welfare', 'sustenance_preservation', 'sustenance_food_batch'})
            assert any(a in actions for a in ('harvest_local_plants', 'harvest_food_crops_early', 'wildlife_hunt_plan'))
            decision = director.choose_action(agent, s, actions)
            assert decision['choice'] in {'harvest_local_plants', 'harvest_food_crops_early', 'wildlife_hunt_plan',
                                          'prioritize_plant_cutting', 'prioritize_hunting', 'harvest_nearby_trees',
                                          'harvest_at_risk_crops', 'refuel_building', 'prioritize_cooking'}
            records.append({'scenario': 'full_starvation_candidate_pipeline', 'source': str(source), 'reverse': reverse,
                            'candidates': actions, 'decision': decision, 'farm_loop_removed': True,
                            'orders': [], 'game_mutations': 0})
        # Native grower/definition options, with a genuine unsatisfied field
        # capacity. Choose and accept one food configuration, then resume at
        # faster game time with exactly the same recorded food crisis.
        s = copy.deepcopy(original)
        growers = s['development']['plant_catalog']['growers']
        for site in growers:
            if site.get('kind') != 'new_ground':
                site['plant_def'] = 'Plant_Hops'
        memory = {}
        caps.prepare(s, memory)
        plans = s['development']['capability_plans'].get('configure_crop') or {}
        assert plans
        # One existing outdoor site is enough to exercise crop purpose/type and
        # exact worker selection. Site ranking is tested by the full pipeline.
        key = next(k for k, site in plans.items() if site.get('zone_id') is not None and not site.get('roofed'))
        s['development']['capability_plans']['configure_crop'] = {key: plans[key]}
        selected, raw = caps.choose(agent, {}, 'configure_crop', s)
        assert plans[key]['crop_options'][selected['crop_type']]['human_edible_product'] is True
        transport = CropTransport(s)
        result = caps.execute(transport, s, memory, 'configure_crop', selected)
        assert result['applied']
        memory = json.loads(json.dumps(memory))
        s['game']['tick'] += 40000
        next_actions = caps.prepare(s, memory)
        assert 'configure_crop' not in next_actions and 'create_growing_zone' not in next_actions
        records.append({'scenario': 'native_crop_choice_accept_persist_fast_tick', 'source': str(source),
                        'selection': selected, 'raw': raw, 'result': result, 'next_actions': next_actions,
                        'human_food': True, 'dwell_preserved': True, 'orders': transport.orders, 'game_mutations': 0})
    output = {'offline': True, 'game_mutations': 0, 'survival_not_proven': True, 'records': records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps([{'scenario': r['scenario'], 'reverse': r.get('reverse'),
                       'choice': r.get('decision', {}).get('choice'), 'selection': r.get('selection'),
                       'dwell_preserved': r.get('dwell_preserved')} for r in records]))


if __name__ == '__main__':
    main()

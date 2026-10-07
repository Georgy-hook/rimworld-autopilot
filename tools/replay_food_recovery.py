"""Offline crop/food decisions from a recorded native snapshot. No API client."""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
os.environ.update(HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false',
                  LAYA_CPU_THREADS='4', OMP_NUM_THREADS='4', MKL_NUM_THREADS='4')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import colony_capabilities as caps
import colony_director as director
import rimworld_laya as bridge


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    original = json.loads(args.snapshot.read_text(encoding='utf-8'))
    agent = bridge.load_agent(bridge.DEFAULT_MODEL, 'cuda')
    records = []
    for reverse in (False, True):
        s = copy.deepcopy(original)
        s['map']['resources'].update(food=0, meals=0, raw_food=0, nutrition=0)
        catalog = s['development']['plant_catalog']
        if reverse:
            for site in catalog.get('growers') or []:
                site['options'] = list(reversed(site.get('options') or []))
        caps.prepare(s, {})
        action = 'create_growing_zone' if 'create_growing_zone' in s['development']['capability_plans'] else 'configure_crop'
        selection, raw = caps.choose(agent, {}, action, s)
        site = s['development']['capability_plans'][action][selection['crop_site']]
        plant = site['crop_options'][selection['crop_type']]
        records.append({'scenario': 'empty_food_viable_native_crop_catalog', 'reverse': reverse,
                        'selection': selection, 'human_food': plant.get('human_edible_product') is True, 'raw': raw})
        s['development']['capability_plans']['harvest_at_risk_crops'] = {
            'products': {'WoodLog': 160}, 'expected_human_nutrition': 0,
            'plants': [{'thing_id': -1, 'harvested_thing_def': 'WoodLog', 'harvest_yield': 160}],
            'workers': caps.workers(s, 'PlantCutting')}
        choices = ['harvest_at_risk_crops', 'create_growing_zone', 'hold_survival']
        if reverse:
            choices.reverse()
        choices = director.focus_imminent_food_choices(s, choices)
        decision = director.choose_action(agent, s, choices)
        records.append({'scenario': 'timber_does_not_feed_colony', 'reverse': reverse, 'decision': decision,
                        'food_not_falsely_counted': 'WoodLog' in director.action_description('harvest_at_risk_crops', s),
                        'expected_progress': decision['choice'] == 'create_growing_zone'})
    output = {'game_commands': 0, 'survival_not_proven': True, 'records': records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps([{k: r.get(k) for k in ('scenario', 'reverse', 'selection', 'human_food', 'expected_progress')} for r in records]))
    return 0 if all(r.get('human_food', r.get('food_not_falsely_counted')) for r in records) else 1


if __name__ == '__main__':
    raise SystemExit(main())

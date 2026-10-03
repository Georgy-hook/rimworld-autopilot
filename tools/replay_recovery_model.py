"""Read-only model diagnostics; never opens a client or issues game commands."""
import argparse
import json
import os
from pathlib import Path
import sys
os.environ.update(HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false',
                  LAYA_CPU_THREADS='4', OMP_NUM_THREADS='4', MKL_NUM_THREADS='4')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import colony_director as director
import rimworld_laya as bridge
import colony_medical_recovery as recovery
from laya_decisions import ask_laya_choice


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding='utf-8'))
    snapshot['development']['shelter_exposure_days'] = max(0, (snapshot['game']['tick'] - 1560) / 60000)
    agent = bridge.load_agent(bridge.DEFAULT_MODEL, 'cuda')
    choices = ['hold_survival', 'build_sleeping_spots', 'build_recreation_pin',
               'create_stockpile', 'build_starter_base', 'prioritize_construction', 'prioritize_hauling']
    records = []
    for order in (choices, list(reversed(choices))):
        focused = director.focus_overdue_shelter_choices(snapshot, order)
        decision = director.choose_action(agent, snapshot, focused)
        records.append({'scenario': 'recorded_exposed_start', 'candidate_order': order, 'focused_candidates': focused, 'decision': decision,
                        'expected_progress': decision['choice'] in {'build_starter_base', 'prioritize_construction'}})
    options = {'experienced': 'Doctor: expected tend quality 90%, speed 120%, medicine 14, 10 cells away. Treat the lung disease.',
               'novice': 'Doctor: expected tend quality 10%, speed 100%, medicine 0, 10 cells away. Treat the same lung disease.'}
    for ordered in (options, dict(reversed(list(options.items())))):
        patient = {'id': 1, 'position': {'x': 0, 'z': 0}}
        helper_rows = {
            'experienced': {'id': 2, 'medical_tend_quality': .9, 'medical_tend_speed': 1.2, 'medicine_skill': 14},
            'novice': {'id': 3, 'medical_tend_quality': .1, 'medical_tend_speed': 1, 'medicine_skill': 0}}
        helpers = {key: {**helper_rows[key], 'current_job': 'Wait', 'position': {'x': 10, 'z': 0}}
                   for key in ordered}
        kept, excluded = recovery.helper_frontier({'combat': {'colonists': [patient, *helpers.values()]}}, patient, helpers)
        kept_ids = {row['id'] for row in kept.values()}
        feasible = {key: value for key, value in ordered.items() if helper_rows[key]['id'] in kept_ids}
        choice, raw = ask_laya_choice(agent, {
            'choice_context': 'Same patient has LungRot severity 0.58 of lethal 1.0; no immunity race. '
                              'Both doctors available now at equal distance. Low-quality treatment may fail to reverse progression.'},
            'disease_doctor', 'Choose the doctor more likely to reverse this lethal disease with effective treatment.', feasible, detailed=True)
        records.append({'scenario': 'illustrative_equal_distance_doctor_comparison', 'choice': choice,
                        'expected_progress': choice == 'experienced', 'frontier_exclusions': excluded, 'raw': raw})
    args.output.write_text(json.dumps({'game_commands': 0, 'not_a_survival_benchmark': True,
                                     'records': records}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps([{'scenario': r['scenario'], 'choice': r.get('choice') or r['decision']['choice'],
                      'expected_progress': r['expected_progress']} for r in records]))


if __name__ == '__main__':
    main()

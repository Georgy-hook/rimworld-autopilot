"""Cached model over a cold bedside fixture. No API client, sockets or game orders."""
import argparse
import copy
import json
import os
from pathlib import Path
import sys

os.environ.update(HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false', LAYA_CPU_THREADS='4',
                  OMP_NUM_THREADS='4', MKL_NUM_THREADS='4')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import colony_director as director
import rimworld_laya as bridge
from laya_decisions import ask_laya_choice
from tests.test_patient_heat_maintenance import cold_bedside


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    agent = bridge.load_agent(bridge.DEFAULT_MODEL, 'auto')
    records = []
    for reverse in (False, True):
        s = cold_bedside()
        options = director.routine_care_refuel_options(s, 1)
        assert options and director.patient_care_is_urgent(s, 2) is False
        criteria = {'refuel_room': 'Refuel the completed campfire in this cold patient room with stocked wood. Ordinary job and exact current patient are rechecked; fuel delivery and warming are not yet proven.',
                    'continue_tending': 'Continue treating nonbleeding frostbite. This does not remove cold exposure and the empty campfire cannot warm the patient.'}
        if reverse: criteria = dict(reversed(list(criteria.items())))
        choice, raw = ask_laya_choice(agent, {
            'decision_facts': {'room_c': -3.38, 'roofed': True, 'hypothermia': .9, 'downed': True,
                'bleeding': 0, 'immunity_can_develop': False, 'routine_tend': 'Frostbite', 'fuel': 0,
                'wood': 53, 'source': 'synthetic reproduction of retained bedside conditions'},
            'option_effects': {
                'refuel_room': {'benefit': 'Restore heat in the existing patient room', 'risk': 'Interrupts routine frostbite treatment; both routes and fresh clinical state must pass native checks',
                    'cost': 'One fuel delivery with existing wood', 'inaction': 'Continued exposure can kill the patient', 'uncertainty': 'Order acceptance is not delivery or recovery'},
                'continue_tending': {'benefit': 'Treat frostbite', 'risk': 'Hypothermia can be fatal while the room remains cold',
                    'cost': 'Keeps the sole caregiver occupied', 'inaction': 'No fuel delivery', 'uncertainty': 'Tending is not temperature treatment'}}},
            'cold_patient_response', 'Choose the next care response for a bedbound hypothermic patient in a cold room.', criteria, detailed=True)
        # Also exercise the actual action filter and parameter decision. The
        # free clinical head above is a diagnostic, not the product executor.
        s['development']['resilience'] = {'available': True, 'options': []}
        actions, details = director.candidate_actions(None, s, {'anchor': {'x': 10, 'z': 10}, 'issued': {}})
        if reverse: actions.reverse()
        actual = director.choose_action(agent, s, actions)
        records.append({'reverse': reverse, 'clinical_head_choice': choice, 'raw': raw,
                        'offered_facility_count': len(options), 'product_candidates': actions,
                        'product_decision': actual})
    args.output.write_text(json.dumps({'offline': True, 'game_orders': 0, 'live_survival_unverified': True,
                                      'records': records}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'clinical_head_choices': [r['clinical_head_choice'] for r in records],
                      'product_choices': [r['product_decision']['choice'] for r in records], 'game_orders': 0}))
    return 0 if all(r['product_decision']['choice'] == 'refuel_building' and not r['product_decision'].get('selection_unavailable')
                   for r in records) else 1


if __name__ == '__main__':
    raise SystemExit(main())

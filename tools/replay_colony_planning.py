"""Offline real-model root decisions on recorded colonies; no game transport."""
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
import colony_plan
import rimworld_laya as bridge


def root_prompts(raw):
    if not isinstance(raw, dict):
        return []
    result = []
    question = raw.get('question') or {}
    if str(question.get('id') or '').startswith('colony_goal'):
        result.append({'question': question, 'visible_state': raw.get('visible_state'),
                       'prompt_budget': raw.get('prompt_budget'), 'answers': raw.get('answers')})
    for key, value in raw.items():
        if key in {'question', 'visible_state', 'answers', 'prompt_budget'}:
            continue
        if isinstance(value, dict):
            result.extend(root_prompts(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    result.extend(root_prompts(item))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', action='append', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    agent = bridge.load_agent(bridge.DEFAULT_MODEL, 'cuda')
    records = []
    for source in args.snapshot:
        original = json.loads(source.read_text(encoding='utf-8-sig'))
        for reverse in (False, True):
            s = copy.deepcopy(original)
            memory = {'anchor': director.anchor_from_snapshot(s), 'issued': {},
                      'doctrine': (s.get('development') or {}).get('doctrine') or {}}
            colony_plan.reconcile(s, memory)
            candidates, _ = director.candidate_actions(None, s, memory)
            candidates = director.focus_overdue_shelter_choices(s, candidates)
            candidates = director.focus_contamination_choices(s, candidates)
            if reverse:
                candidates.reverse()
            decision = director.choose_action(agent, s, candidates)
            prompts = root_prompts(decision.get('raw') or {})
            record = {'source': str(source.resolve()), 'reverse': reverse,
                      'tick': s.get('game', {}).get('tick'), 'people': len(s.get('colonists') or []),
                      'candidates': candidates, 'choice': decision['choice'],
                      'selection': {k: v for k, v in decision.items()
                                    if k not in {'raw', 'choice', 'confidence', 'probabilities'}},
                      'selection_unavailable': decision.get('selection_unavailable'), 'root_prompts': prompts}
            records.append(record)
            # Write after each case so a failed assertion leaves reviewable evidence.
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps({'offline': True, 'game_commands': 0,
                'survival_not_proven': True, 'records': records}, ensure_ascii=False, indent=2), encoding='utf-8')
            for prompt in prompts:
                assert isinstance((prompt['visible_state'] or {}).get('plan'), dict)
                assert prompt['prompt_budget']['state_tokens'] <= prompt['prompt_budget']['state_budget']
                assert 'ending' in prompt['visible_state']['plan']
            print(json.dumps({k: v for k, v in record.items() if k not in {'root_prompts', 'source'}}, ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

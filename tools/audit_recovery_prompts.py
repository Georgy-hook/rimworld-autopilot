"""Audit medical choice encoding using the real cached tokenizer, without weights/game."""
import argparse
import copy
import json
import os
from pathlib import Path
import sys

os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['OMP_NUM_THREADS'] = '2'
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--model', action='store_true', help='Also rank the offline choices on CUDA; never issue game commands')
    args = parser.parse_args()
    from transformers import AutoTokenizer
    from laya.common import build_sequence, serialize_state
    from test_medical_recovery_sequences import MedicalWorld
    import colony_director as director
    if args.model:
        os.environ.update(HF_HUB_OFFLINE='1', LAYA_CPU_THREADS='4', MKL_NUM_THREADS='4')
        import rimworld_laya as bridge
        delegate = bridge.load_agent(str(args.checkpoint), 'cuda')
    else:
        delegate = None

    class Agent:
        cfg = json.loads((args.checkpoint / 'rl_agent_config.json').read_text())
        tok = AutoTokenizer.from_pretrained(args.checkpoint / 'tokenizer', local_files_only=True)
        calls = []

        def predict(self, state, questions):
            qid, question = next(iter(questions.items()))
            ids = self.tok(serialize_state(state).replace(self.tok.mask_token, ' '), add_special_tokens=False)['input_ids']
            sequence, markers = build_sequence(self.tok, state,
                {'t': 'choice', 'ins': question['instructions'], 'crit': question['criteria']},
                self.cfg['max_len'], self.cfg['head_max_len'])
            assert len(ids) <= 312, (qid, len(ids))
            assert sequence[-len(ids)-1:-1] == ids, ('state truncated', qid)
            assert len(markers) == len(question['criteria']), ('option lost', qid)
            self.calls.append({'question': qid, 'state_tokens': len(ids), 'sequence_tokens': len(sequence),
                               'visible_state': state, 'criteria': question['criteria']})
            return delegate.predict(state, questions) if delegate is not None else {
                'answers': {qid: {'choice': next(iter(question['criteria']))}}}

    agent = Agent()
    world = MedicalWorld()
    snap = world.snapshot
    # Recorded Alyssa/Dawn severity and bleeding rates; remaining transport is an
    # explicit offline fixture. Include two feasible helpers for comparison.
    dawn = snap['colonists'][0]
    dawn.update(bleeding_rate=4.324, health_conditions=[{'def_name': 'BloodLoss', 'severity': .412}])
    alyssa = copy.deepcopy(dawn)
    alyssa.update(id=254, name='Alyssa', bleeding_rate=2.547,
                  health_conditions=[{'def_name': 'BloodLoss', 'severity': .857}])
    helper = copy.deepcopy(snap['colonists'][1])
    helper.update(id=301, name='Alternative doctor')
    snap['colonists'].extend([alyssa, helper])
    # Quality/speed are illustrative API values for the added helper, not
    # historical measurements (the old native DTO did not expose these stats).
    snap['development']['resilience']['options'] = [
        {'kind': 'tend', 'worker_id': wid, 'target_id': pid, 'medicine_skill': level,
         'medical_tend_quality': quality, 'medical_tend_speed': speed,
         'worker': name, 'giver': 'DoctorTendEmergency'}
        for wid, level, name, quality, speed in [(300, 2, 'Nanda', .25, 1), (301, 10, 'Alternative doctor', .7, 1.2)]
        for pid in (254, 257)]
    director.candidate_actions(world, snap, {'anchor': {'x': 20, 'z': 20}, 'issued': {}})
    decision = director.choose_action(agent, snap, ['tend_colonist'])
    patient_calls = [c for c in agent.calls if c['question'].startswith('medical_patient')]
    assert patient_calls, 'No medical comparison encoded'
    encoded = json.dumps(patient_calls)
    for fact in ('3369', '8159', 'BloodLoss', '0.857', '0.412'):
        assert fact in encoded, ('missing triage fact', fact)
    assert any(c['question'].startswith('care_helper') for c in agent.calls)
    result = {'comparisons': len(agent.calls), 'max_state_tokens': max(c['state_tokens'] for c in agent.calls),
              'full_state_retained': True, 'model_weights_loaded': args.model, 'game_contacted': False,
              'fixture': 'Recorded patient bleeding; illustrative equally distant helper stats, not native runtime measurements',
              'decision': decision, 'calls': agent.calls}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in {'calls', 'decision'}}))
    if args.model:
        print(json.dumps({'medical_patient': decision.get('medical_patient'), 'care_helper': decision.get('care_helper')}))


if __name__ == '__main__':
    main()

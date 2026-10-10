"""Cross-domain regressions: actual root prompts, persistence and combat cycles."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import colony_combat as combat
import colony_director as director
import colony_outcomes
import colony_plan
import colony_progression as progression
import colony_reasoning
import colony_resilience
import colony_sustenance
import colony_strategy
import laya_decisions
import rimworld_laya as bridge


def snapshot():
    person = {'id': 1, 'name': 'Worker', 'health': 1, 'hunger': .8, 'rest': .8,
              'current_job': 'Wait_Combat', 'skills': {'Construction': {'level': 5},
                  'Intellectual': {'level': 4}, 'Plants': {'level': 4}},
              'work_priorities': {'Research': {'priority': 0}, 'Growing': {'priority': 1}},
              'health_conditions': []}
    fighter = {**person, 'can_fight': True, 'is_drafted': True, 'has_ranged_weapon': True,
               'weapon_def': 'Gun_Revolver', 'weapon_range': 25, 'moving': 1, 'sight': 1,
               'manipulation': 1, 'position': {'x': 10, 'z': 10},
               'distance_to_nearest_opponent': 90}
    return {'game': {'tick': 100, 'is_paused': False}, 'map': {'id': 0, 'enemies': 1,
            'resources': {'nutrition': 0, 'food': 0, 'meals': 0}}, 'colonists': [person], 'animals': [],
            'combat': {'available': True, 'colonists': [fighter], 'available_weapons': [],
                'hostiles': [{'id': 9, 'kind_def': 'Shambler', 'health': 1,
                             'current_job': 'Wait_Wander', 'position': {'x': 100, 'z': 10},
                             'distance_to_nearest_opponent': 90}],
                'defenses': [{'id': 10, 'kind': 'door', 'position': {'x': 8, 'z': 8}}]},
            'development': {'current_research': {'name': 'Electricity', 'progress': 0},
                'finished_research': [], 'construction_projects': [], 'rooms': [],
                'building_counts': {'SimpleResearchBench': 1}, 'buildings': [],
                'item_counts': {}, 'zones': [], 'doctrine': {'endgame': 'ship_escape'},
                'progression': {'ship_research': {'frontier': ['Electricity']}}}}


class PlanningSequenceTests(unittest.TestCase):
    def test_wait_and_other_accepted_commands_do_not_erase_stalled_research(self):
        s, memory = snapshot(), {}
        colony_plan.reconcile(s, memory)
        for tick, action in ((40000, 'build_prison'), (90000, 'hold_survival'), (150000, 'configure_food_bills')):
            s['game']['tick'] = tick
            colony_outcomes.record(s, memory, action, {'applied': action != 'hold_survival'})
            memory = json.loads(json.dumps(memory))
            colony_plan.reconcile(s, memory)
        self.assertEqual(s['development']['plan_observation']['unchanged_ticks']['research'], 149900)
        self.assertIn('research 149900 ticks', colony_plan.brief(s, 1, {})['unchanged'])
        s['game']['tick'] = 160000
        s['development']['current_research'] = {'name': 'Batteries', 'progress': 0}
        colony_plan.reconcile(s, memory)
        self.assertEqual(s['development']['plan_observation']['unchanged_ticks']['research'], 159900)
        s['development']['current_research'] = {'name': 'Electricity', 'progress': 0}
        colony_plan.reconcile(s, memory)
        self.assertEqual(s['development']['plan_observation']['unchanged_ticks']['research'], 159900)
        s['development']['current_research']['progress'] = 10
        colony_plan.reconcile(s, memory)
        self.assertNotIn('research', s['development']['plan_observation']['unchanged_ticks'])
        s['game']['tick'] = 21
        colony_plan.reconcile(s, memory)
        self.assertEqual(s['development']['plan_observation']['unchanged_ticks'], {})

    def test_real_root_domain_and_action_calls_keep_complete_plan_with_cached_tokenizer(self):
        from tokenizers import Tokenizer
        files = list((Path.home()/'.cache/huggingface/hub/models--convaiinnovations--laya/snapshots').glob('*/tokenizer/tokenizer.json'))
        if not files:
            self.skipTest('cached Laya tokenizer unavailable')
        tokenizer = Tokenizer.from_file(str(files[0]))
        class Agent:
            cfg = {'max_len': 512, 'head_max_len': 192}
            calls = []
            def tok(self, text, **kw):
                ids = tokenizer.encode(text, add_special_tokens=False).ids
                return {'input_ids': ids[:kw.get('max_length', len(ids))]}
            def predict(self, state, questions):
                self.calls.append((copy.deepcopy(state), copy.deepcopy(questions)))
                q, question = next(iter(questions.items()))
                choices = question['criteria']
                selected = next((k for k in ('defense', 'build_fallback_defense') if k in choices), next(iter(choices)))
                return {'answers': {q: {'choice': selected, 'confidence': 1}}}
        s, agent = snapshot(), Agent()
        s['colonists'][0]['health_conditions'] = [{'def_name': 'Malnutrition', 'severity': .64}]
        decision = director.choose_action(agent, s, ['build_basic_beds', 'build_fallback_defense',
            'build_prison', 'prioritize_hunting', 'prioritize_cooking', 'prioritize_growing', 'hold_survival'])
        root_calls = [(state, q) for state, q in agent.calls if next(iter(q)).startswith('colony_goal')]
        self.assertGreaterEqual(len(root_calls), 2)
        self.assertEqual(decision['choice'], 'build_fallback_defense')
        for state, _ in root_calls:
            self.assertEqual(state['plan']['ending'], 'ship_escape')
            self.assertIn('food 0.0 days', state['plan']['needs'])
            self.assertIn('malnutrition 0.64', state['plan']['needs'])
            self.assertIn('unassigned Research', state['plan']['development'])
            self.assertIn('free labor 0/1', state['plan']['needs'])
            self.assertEqual(state['plan']['next_research'], ['Electricity'])
            self.assertLessEqual(len(agent.tok(json.dumps(state, ensure_ascii=False))['input_ids']), 312)

    def test_severe_thermal_and_blood_loss_cannot_evict_ending_from_root(self):
        from tokenizers import Tokenizer
        files = list((Path.home()/'.cache/huggingface/hub/models--convaiinnovations--laya/snapshots').glob('*/tokenizer/tokenizer.json'))
        if not files:
            self.skipTest('cached Laya tokenizer unavailable')
        tokenizer = Tokenizer.from_file(str(files[0]))
        class Agent:
            cfg = {'max_len': 512, 'head_max_len': 192}
            def tok(self, text, **kw):
                ids = tokenizer.encode(text, add_special_tokens=False).ids
                return {'input_ids': ids[:kw.get('max_length', len(ids))]}
        s = snapshot()
        s['colonists'][0].update(downed=True, bleeding_rate=2.5, health_conditions=[
            {'def_name': 'Hypothermia', 'severity': .8, 'cur_stage_index': 3, 'life_threatening': True},
            {'def_name': 'Heatstroke', 'severity': .6, 'cur_stage_index': 2, 'life_threatening': True},
            {'def_name': 'Malnutrition', 'severity': .5}])
        s['animals'] = [{'bleeding_rate': .8, 'downed': True}]
        facts = colony_reasoning.attention_facts(s, roofed_sleeping_places=1)
        plan = colony_plan.brief(s, 1, facts.get('care_risks'))
        visible = laya_decisions._planning_state(Agent(), {'planning_context': plan,
            'option_effects': {k: {f: 'Huge irrelevant description '*100 for f in
                ('benefit', 'risk', 'cost', 'inaction')} for k in ('resilience_tend', 'resilience_rescue')}},
                {'resilience_tend': 'tend', 'resilience_rescue': 'rescue'})
        self.assertEqual(visible['plan'], plan)
        self.assertIn('bleeding 2.5', plan['needs'])
        self.assertIn('Hypothermia 0.8 stage 3 lethal True', plan['needs'])
        self.assertEqual(plan['ending'], 'ship_escape')
        for row in visible['alternatives'].values():
            for field in ('benefit', 'risk', 'cost', 'inaction'):
                self.assertIn(field + ':', row)

    def test_accepted_idle_positioning_is_not_engagement_and_returns_worker_to_work(self):
        s, memory = snapshot(), {}
        class Agent:
            def predict(self, state, questions):
                q, question = next(iter(questions.items()))
                choices = question['criteria']
                chosen = next((k for k in ('fallback_line', 'hold_cover', 'continue_safe_colony_work') if k in choices), next(iter(choices)))
                return {'answers': {q: {'choice': chosen, 'confidence': 1}}}
        class Client:
            posts = []
            def post(self, endpoint, **kw):
                self.posts.append((endpoint, kw))
                if endpoint.endswith('/tactic'):
                    return {'positioned_pawn_ids': [1], 'attacking_pawn_ids': [], 'psycast_queued': False}
                if endpoint.endswith('/status'):
                    s['combat']['colonists'][0]['is_drafted'] = kw['body']['is_drafted']
                return {'success': True}
        client = Client()
        with tempfile.TemporaryDirectory() as folder, patch.object(bridge, 'collect_snapshot', side_effect=lambda _: copy.deepcopy(s)), patch.object(bridge, 'append_log'):
            for now, tick in ((100, 100), (120, 1500), (140, 2500), (141, 2501)):
                s['game']['tick'] = tick
                s['combat']['hostiles'][0]['position']['z'] += 1
                s['combat']['hostiles'][0]['current_job'] = 'GotoWander' if now == 120 else 'Wait_Wander'
                with patch('time.time', return_value=now):
                    record = bridge.run_cycle(client, Agent(), apply=True, confidence=0, log_path=Path(folder)/'log',
                        combat_memory=memory, combat_signature=director.combat_order_signature)
                memory = json.loads(json.dumps(memory))
            self.assertEqual(record['decision']['choice'], 'continue_safe_colony_work')
            self.assertFalse(s['combat']['colonists'][0]['is_drafted'])
            self.assertTrue(director.staging_development_allowed(s, record))
            self.assertIn('_combat_progress_feedback', record['snapshot'])

    def test_changed_assault_reopens_defense_and_closes_safe_work(self):
        s = snapshot()
        self.assertEqual(combat.safe_work_actor_ids(s, allow_idle_drafted=True), {1})
        s['combat']['hostiles'][0]['current_job'] = 'AttackMelee'
        self.assertEqual(combat.safe_work_actor_ids(s, allow_idle_drafted=True), set())
        s['combat']['hostiles'][0]['current_job'] = 'Wait_Wander'
        del s['combat']['colonists'][0]['distance_to_nearest_opponent']
        self.assertEqual(combat.safe_work_actor_ids(s, allow_idle_drafted=True), set())

    def test_one_patient_and_caregiver_do_not_own_unrelated_safe_workers(self):
        s = snapshot()
        s['combat']['colonists'][0]['is_drafted'] = False
        s['combat']['colonists'] += [
            {'id': 2, 'is_downed': True, 'distance_to_nearest_opponent': 90, 'bleeding_rate': 1},
            {'id': 3, 'current_job': 'TendPatient', 'current_job_target_id': 2,
             'distance_to_nearest_opponent': 90}]
        self.assertEqual(combat.safe_work_actor_ids(s), {1})
        plan = bridge.plan_action(s, {'choice': 'continue_safe_colony_work'})
        self.assertFalse(plan['commands'])
        self.assertTrue(director.staging_development_allowed(s, {'decision': {'choice': 'continue_safe_colony_work'}}))
        s['combat']['colonists'][1]['distance_to_nearest_opponent'] = 3
        self.assertFalse(director.staging_development_allowed(s, {'decision': {'choice': 'continue_safe_colony_work'}}))

    def test_saved_royal_route_cannot_launch_anomaly_or_ship_under_other_labels(self):
        royal = {'quest_id': 2, 'route': 'EndGame_RoyalAscent', 'can_accept': True}
        void = {'map_id': 0, 'thing_id': 42, 'pawn_id': 1, 'site': 'VoidMonolith', 'label': 'Investigate'}
        context = {'chosen_ending_route': 'royal_ascent', 'endings': {'quests': [royal], 'site_jobs': [void]}}
        rows = progression.ending_options(context)
        self.assertEqual(len(rows), 1)
        self.assertEqual(next(iter(rows.values()))['route'], 'EndGame_RoyalAscent')
        self.assertEqual(progression.option_route(void), 'anomaly_void')
        self.assertEqual(progression.ship_options(context), {})
        context['chosen_ending_route'] = 'anomaly_void'
        self.assertEqual(next(iter(progression.ending_options(context).values()))['site'], 'VoidMonolith')

    def test_execution_rechecks_route_and_pending_sale_remains_resolvable(self):
        s, memory = snapshot(), {'doctrine': {'endgame': 'imperial_ascension'}}
        row = {'map_id': 0, 'thing_id': 42, 'pawn_id': 1, 'site': 'VoidMonolith', 'label': 'Investigate', 'kind': 'job'}
        with patch.object(progression, 'collect', return_value={'endings': {'site_jobs': [row]}}):
            result = progression.execute(None, s, memory, 'progression_ending', row)
        self.assertFalse(result['applied'])
        self.assertNotIn('ending_commitment', memory)
        context = {'chosen_ending_route': 'royal_ascent', 'ending_selection': {'available': True, 'rows': [], 'can_submit': True}}
        self.assertIn('cancel_transfer', progression.ending_options(context))
        self.assertIn('submit_transfer', progression.ending_options(context))

    def test_mountain_geometry_and_cold_furnishing_do_not_claim_power_from_research(self):
        ores = {'map_width': 20, 'ores': {'MineableGranite': {'cells': [z*20+x for z in range(4, 11) for x in range(5, 12)]}}}
        self.assertIsNotNone(director.mining_bedroom_rect(ores, {'x': 8, 'z': 8}))
        ores['ores']['MineableGranite']['cells'].append(3*20+8)  # Only front door is buried.
        self.assertIsNone(director.mining_bedroom_rect(ores, {'x': 8, 'z': 8}))
        layout = director.mountain_bedroom_furnishing(powered=False, climate='cold')
        names = [b['def_name'] for b in layout['buildings']]
        self.assertEqual(names.count('Door'), 2)
        self.assertIn('Campfire', names)
        self.assertIn('TorchLamp', names)
        self.assertNotIn('Heater', names)

    def test_mountain_ack_and_partial_construction_remain_pending_across_reload(self):
        s, memory = snapshot(), {'anchor': {'x': 10, 'z': 10}, 'issued': {},
                                 'mountain_bedroom': {'x': 5, 'z': 4, 'furnished': True}}
        s['development']['weather'] = {'temperature': -20}
        s['development']['finished_research'] = ['Electricity']
        with patch.object(director, 'post_blueprint', return_value={'success': True}) as post:
            response = director.execute_action(None, s, memory, 'finish_mountain_bedroom', {})
        self.assertTrue(response['applied'])
        self.assertEqual(response['completion'], 'unverified')
        self.assertFalse(memory['mountain_bedroom']['furnished'])
        layout = post.call_args.args[3]
        memory = json.loads(json.dumps(memory))
        origin = memory['mountain_bedroom']
        rows = [{**item, 'def': item['def_name'],
                 'position': {'x': origin['x']+item['rel_x'], 'z': origin['z']+item['rel_z']}}
                for item in layout['buildings']]
        s['development']['construction_projects'] = rows
        observed = director.mountain_furnishing_observation(s, origin)
        self.assertEqual(observed['missing'], [])
        self.assertFalse(origin['furnished'])
        with patch.object(director, 'post_blueprint') as post:
            self.assertFalse(director.execute_action(None, s, memory, 'finish_mountain_bedroom', {})['applied'])
            post.assert_not_called()
        s['development']['buildings'] = rows[:-1]
        s['development']['construction_projects'] = []
        with patch.object(director, 'post_blueprint', return_value={'success': True}) as post:
            director.execute_action(None, s, memory, 'finish_mountain_bedroom', {})
        self.assertEqual(post.call_args.args[3]['buildings'], [layout['buildings'][-1]])
        s['development']['buildings'] = rows
        observed = director.mountain_furnishing_observation(s, origin)
        self.assertTrue(origin['furnished'])
        self.assertEqual(observed['completion'], 'furniture_built')
        self.assertIn('Campfire', [b['def_name'] for b in observed['layout']['buildings']])
        s['development']['buildings'].pop()
        self.assertFalse(director.mountain_furnishing_observation(s, origin)['completion'] == 'furniture_built')

    def test_medical_and_animal_policy_effects_do_not_claim_feeding_or_recovery(self):
        s = snapshot()
        s['development']['resilience'] = {'plans': {'resilience_rest': {'patient': {'target_id': 2}}},
            'patients': [{'pawn_id': 2, 'in_bed': True, 'food': 0, 'conditions': [{'def_name': 'Malnutrition'}]}]}
        effects = colony_resilience.assess('resilience_rest', s)
        self.assertIn('already in bed', effects['benefit'])
        self.assertIn('no feeding', effects['benefit'])
        self.assertIn('other workers remain available', effects['cost'])
        s['development']['sustenance'] = {'options': [{'key': 'care:3:4', 'kind': 'care', 'target_id': 3}]}
        effects = colony_sustenance.assess('sustenance_animal_welfare', s)
        self.assertIn('Medicine ceiling only', effects['benefit'])
        self.assertIn('cannot cure starvation', effects['benefit'])

    def test_priority_change_cannot_requeue_an_incapacitated_patients_existing_rest(self):
        s, memory = snapshot(), {}
        patient = {'pawn_id': 2, 'downed': True, 'in_bed': True, 'current_job': 'LayDown'}
        s['development']['resilience'] = {'patients': [patient], 'options': [
            {'kind': 'rest', 'worker_id': 2, 'target_id': 2},
            {'kind': 'feed', 'worker_id': 1, 'target_id': 2}]}
        self.assertEqual(colony_resilience.prepare(s, memory), ['resilience_feed'])
        patient['downed'] = False
        self.assertIn('resilience_rest', colony_resilience.prepare(s, memory))
        patient['downed'] = True
        patient['in_bed'] = False
        self.assertIn('resilience_rest', colony_resilience.prepare(s, memory))

    def test_doctrine_choices_retain_the_complete_ending_and_diplomatic_requirements(self):
        from tokenizers import Tokenizer
        files = list((Path.home()/'.cache/huggingface/hub/models--convaiinnovations--laya/snapshots').glob('*/tokenizer/tokenizer.json'))
        if not files:
            self.skipTest('cached Laya tokenizer unavailable')
        tokenizer = Tokenizer.from_file(str(files[0]))
        class Agent:
            cfg = {'max_len': 512, 'head_max_len': 192}
            calls = []
            def tok(self, text, **kw):
                ids = tokenizer.encode(text, add_special_tokens=False).ids
                return {'input_ids': ids[:kw.get('max_length', len(ids))]}
            def predict(self, state, questions):
                self.calls.append(copy.deepcopy(state))
                key, q = next(iter(questions.items()))
                return {'answers': {key: {'choice': next(iter(q['criteria']))}}}
        agent = Agent()
        colony_strategy._ask(agent, {'chosen_so_far': {'endgame': 'imperial_ascension',
            'primary_direction': 'anomaly_containment', 'diplomacy': 'neutral'},
            'population': 3, 'food': 15, 'sheltered_beds': 3}, 'doctrine_diplomacy',
            'Choose external posture supporting the ending.', dict(colony_strategy.DIPLOMACY))
        self.assertTrue(agent.calls)
        for state in agent.calls:
            plan = state['plan']
            self.assertEqual(plan['endgame'], 'imperial_ascension')
            self.assertEqual(plan['direction'], 'anomaly_containment')
            self.assertEqual(plan['diplomacy'], 'neutral')
            self.assertIn('hostile Empire raiding can block', plan['ending_requirements'])
            self.assertLessEqual(len(agent.tok(json.dumps(state, ensure_ascii=False))['input_ids']), 312)


if __name__ == '__main__':
    unittest.main()

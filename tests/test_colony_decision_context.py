"""Cross-domain decisions keep observed context without inventing an outcome."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import colony_capabilities as loadout
import colony_decision_context as facts
import colony_director as director
import colony_manufacturing as manufacturing
import colony_mining as mining
import colony_production as production
import colony_progression as progression
import colony_quests as quests
import colony_reasoning as reasoning
import colony_resilience as care
from laya_decisions import ChoiceContextOverflow


def observation():
    return {'map': {'id': 0, 'enemies': 0, 'resources': {'nutrition': .8, 'food': 4, 'meals': 0, 'medicine': 25}},
        'game': {'tick': 1000}, 'colonists': [{'id': 1, 'name': 'Worker', 'hunger': .8, 'downed': False,
            'bleeding_rate': 0, 'current_job': 'Wait'}],
        'development': {'weather': {'weather': 'SnowHard', 'temperature': -20, 'growth_season_now': False,
                                  'next_twelfth_average_temperatures': [-21, -31, -37]},
            'rooms': [{'contained_beds_ids': [8], 'open_roof_count': 0, 'temperature': -10}],
            'construction_projects': [{'thing_id': 50, 'def_name': 'Heater', 'materials_needed': []}],
            'production': {'buildings': [{'fuel': 0, 'fuel_per_day': 10, 'fuel_defs': ['WoodLog']}],
                'recipe_context': {'stocks': [{'def_name': 'WoodLog', 'count': 0},
                    {'def_name': 'ComponentIndustrial', 'count': 29}, {'def_name': 'Steel', 'count': 346}], 'options': []}}}}


def component_recipe():
    return {'recipe': 'Make_ComponentIndustrial', 'label': 'Make component', 'cost': '12 Steel',
        'products': [{'def_name': 'ComponentIndustrial', 'count': 1, 'stock': 29}],
        'fixed_ingredients': [{'def_name': 'Steel', 'count': 12}], 'variable_ingredients': [],
        'missing_research': ['Fabrication'], 'skill_requirements': [{'skill': 'Crafting', 'level': 8}],
        'table_defs': ['FabricationBench'], 'completed_table_ids': [], 'work_amount': 5000,
        'tables': [{'def_name': 'FabricationBench', 'construction_skill': 6, 'power_watts': 250,
            'fixed_cost': [{'def_name': 'Steel', 'count': 200}, {'def_name': 'ComponentIndustrial', 'count': 12},
                           {'def_name': 'ComponentSpacer', 'count': 2}], 'missing_research': ['Fabrication']}]}


class ContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tokenizers import Tokenizer
        paths = list((Path.home()/'.cache/huggingface/hub/models--convaiinnovations--laya/snapshots').glob('*/tokenizer/tokenizer.json'))
        if not paths:
            raise unittest.SkipTest('Cached actual Laya tokenizer unavailable')
        cls.tokenizer = Tokenizer.from_file(str(paths[0]))

    def agent(self, chooser=None):
        tokenizer = self.tokenizer
        class Agent:
            cfg = {'max_len': 512, 'head_max_len': 192}
            def __init__(self): self.seen = []
            def tok(self, text, **kwargs):
                return {'input_ids': tokenizer.encode(text, add_special_tokens=False).ids}
            def predict(self, state, questions):
                self.seen.append((copy.deepcopy(state), copy.deepcopy(questions)))
                qid, question = next(iter(questions.items()))
                selected = chooser(state, question) if chooser else next(k for k in question['criteria'] if k != 'defer')
                return {'answers': {qid: {'choice': selected}}}
        return Agent()

    def assert_bounded(self, agent):
        self.assertTrue(agent.seen)
        for state, _ in agent.seen:
            self.assertLessEqual(len(agent.tok(json.dumps(state, ensure_ascii=False))['input_ids']), 312)

    def test_shared_fuel_is_one_pool_not_a_per_room_reserve(self):
        s = observation()
        buildings = s['development']['production']['buildings']
        buildings[0]['fuel'] = 10
        buildings.append({'fuel': 20, 'fuel_per_day': 10, 'fuel_defs': ['WoodLog']})
        self.assertEqual(facts.environment(s)['shared_fuel_days'], 1.5)
        buildings[1].pop('fuel')
        self.assertIsNone(facts.environment(s)['shared_fuel_days'])

    def test_unobserved_stocks_do_not_become_empty(self):
        self.assertIsNone(facts.material_need({'development': {}}, 'ComponentIndustrial')['stock'])
        self.assertIsNone(facts.environment({'development': {}})['shared_fuel_days'])

    def test_funded_frame_and_alternative_catalog_recipes_are_not_double_charged(self):
        s = observation()
        s['development']['manufacturing_goal'] = {'product_def': 'Gun_Revolver',
            'fixed_ingredients': [{'def_name': 'ComponentIndustrial', 'count': 2}]}
        s['development']['production']['recipe_context']['planning_catalog'] = [component_recipe()]
        need = facts.material_need(s, 'ComponentIndustrial')
        self.assertEqual((need['stock'], need['remaining_build_need'], need['selected_recipe_need'], need['deficit']), (29, 0, 2, 0))
        s['development']['construction_projects'].append({'thing_id': 51, 'def_name': 'TableMachining',
            'materials_needed': [{'def_name': 'ComponentIndustrial', 'required_count': 5}]})
        self.assertEqual(facts.material_need(s, 'ComponentIndustrial')['remaining_build_need'], 5)

    def test_weather_duration_and_empty_fuel_follow_every_term_and_reward_page(self):
        s = observation()
        offer = {'id': 5, 'quest_def': 'ThreatReward_GameCondition_ItemPod',
            'description': 'A rainy thunderstorm will last 9.6 days. ' + 'Public terms remain complete. '*90,
            'name': 'Weather controller', 'state': 'NotYetAccepted', 'offer_version': 'observed',
            'can_accept': True, 'reward_groups': [], 'requires_accepter': False}
        agent = self.agent()
        pages = quests.review_pages(agent, offer, s, {})
        self.assertGreater(len(pages), 1)
        for page in pages:
            impact = page['supplies_and_climate']
            self.assertEqual((impact['wood'], impact['bed_room_min_c'], impact['shared_fuel_days']), (0, -10, 0))
            self.assertEqual(impact['public_durations'], ['9.6 days'])
            self.assertIn('thunderstorm', impact['public_weather_words'])
            self.assertLessEqual(len(agent.tok(json.dumps(page, ensure_ascii=False))['input_ids']), 312)
        self.assertEqual(quests.reconstruct_field(pages, 'description'), offer['description'])
        quests.select_exact(agent, quests.review_header(agent, s, {}, offer), 'reward',
            {'uranium_book': {'rewards': ['69 Uranium', 'Principles of Fire Safety Devices (excellent)']},
             'alternative': {'rewards': ['Honor'], 'cost': 'Same 9.6 days of weather'}}, quests.QUEST_RULE)
        self.assert_bounded(agent)
        self.assertTrue(all(state['supplies_and_climate']['wood'] == 0 for state, _ in agent.seen))

    def test_loss_of_heat_or_fuel_requires_fresh_quest_review(self):
        self.assertTrue(quests.impact_changed({'wood': 20, 'shared_fuel_days': 1, 'nutrition': 4, 'bed_room_min_c': 20},
                                            {'wood': 0, 'shared_fuel_days': 0, 'nutrition': 4, 'bed_room_min_c': -10}))
        self.assertFalse(quests.impact_changed({'wood': 20, 'shared_fuel_days': 1, 'nutrition': 4, 'bed_room_min_c': 20},
                                             {'wood': 19, 'shared_fuel_days': .95, 'nutrition': 3.9, 'bed_room_min_c': 19}))

    def test_oversized_quest_header_defers_locally_instead_of_runtime_failure(self):
        with self.assertRaises(ChoiceContextOverflow) as raised:
            quests.text_pages(self.agent(), {'critical': 'clinical observation '*1000}, 'public_terms', 'A reward')
        self.assertEqual(raised.exception.question_id, 'quest_terms:public_terms')
        self.assertGreater(raised.exception.minimum_tokens, 312)

    def mental_observation(self):
        s = observation()
        s['colonists'][0]['traits'] = [{'name': 'Brawler', 'suppressed': False}]
        s['development']['society'] = {'people': [{'pawn_id': 1, 'name': 'Worker', 'minor_break_threshold': .35,
            'needs': [{'def_name': 'Mood', 'level': .2}, {'def_name': 'Joy', 'level': .8}],
            'thoughts': [{'def_name': 'NeedFood', 'mood_offset': -38}, {'def_name': 'Pain', 'mood_offset': -20},
                {'def_name': 'MySisterDied', 'mood_offset': -14}, {'def_name': 'BrawlerUnhappy', 'mood_offset': -10},
                {'def_name': 'WieldingNobleOrDespisedWeapon', 'mood_offset': -5}, {'def_name': 'SleptOnGround', 'mood_offset': -4}],
            'beliefs': ['Weapons_Noble: preferred weapons change weapon mood']} ]}
        return s

    def test_high_recreation_does_not_hide_break_risk_or_lower_ranked_weapon_cause(self):
        s = self.mental_observation()
        self.assertEqual(len(facts.mood_pressure(s)), 1)
        self.assertIn('BrawlerUnhappy', facts.mood_causes(s))
        self.assertEqual(facts.mood_pressure(s)[0]['joy'], .8)
        self.assertEqual(facts.mood_pressure(s)[0]['other_negative'], 3)
        self.assertFalse(reasoning.recreation_pressure(s))

    def test_weapon_guard_reconsiders_changed_penalties_not_every_mood_tick(self):
        s = self.mental_observation()
        pawn = {'id': 1, 'weapon_info': {}, 'position': {'x': 0, 'z': 0}}
        prefs = facts.weapon_preferences(s, pawn)
        self.assertTrue(prefs['brawler'])
        self.assertEqual(len(prefs['weapon_thoughts']), 2)
        before = loadout._weapon_assignment_guard(s, pawn)
        s['development']['society']['people'][0]['needs'][0]['level'] = .19
        self.assertEqual(before, loadout._weapon_assignment_guard(s, pawn))
        s['development']['society']['people'][0]['thoughts'][3]['mood_offset'] = 0
        self.assertNotEqual(before, loadout._weapon_assignment_guard(s, pawn))

    def test_neutral_patient_bleeding_deadline_bed_and_temperature_reach_both_choice_stages(self):
        s = observation()
        patient = {'pawn_id': 99, 'name': 'Pod patient', 'neutral_arrival': True, 'downed': True,
            'food': .4, 'bleeding_total': 1.1, 'bleedout_ticks': 3500, 'temperature': -18,
            'in_bed': False, 'current_bed_id': None, 'conditions': [{'def_name': 'WoundInfection',
                'severity': .45, 'immunity': .2, 'immunity_can_develop': True, 'can_ever_kill': True,
                'treatment_ticks_left': 4000}]}
        row = {'kind': 'rescue', 'worker_id': 1, 'target_id': 99, 'giver': 'DoctorRescue', 'bed_id': 8,
               'destination_temperature': 20, 'travel_distance': 30, 'medicine_skill': 6}
        s['development']['resilience'] = {'available': True, 'patients': [patient], 'options': [row]}
        care.prepare(s, {})
        agent = self.agent()
        selected, _ = care.choose(agent, {}, 'resilience_rescue', s)
        self.assertEqual(selected['target_id'], 99)
        self.assert_bounded(agent)
        for state, _ in agent.seen:
            encoded = json.dumps(state)
            self.assertIn('3500', encoded)
            self.assertIn('neutral_arrival', encoded)
            self.assertIn('current_bed_id', encoded)
            self.assertIn('immunity_races', encoded)

    def test_unavailable_mining_is_diagnosed_without_an_invented_model_refusal(self):
        s = observation()
        s['development']['mining'] = {'available': True, 'options': [], 'diagnostics': {'workers': [{'blocker': 'protected_patient_care'}]}}
        self.assertEqual(mining.prepare(s, {}), [])
        observed = s['development']['mining']['availability_observation']
        self.assertEqual(observed['native_options'], 0)
        self.assertIn('protected_patient_care', json.dumps(observed))
        self.assertEqual(observed['python_ready'], 0)

    def test_planning_catalog_remains_available_when_no_bill_is_executable(self):
        s = observation()
        s['development']['production']['recipe_context']['planning_catalog'] = [component_recipe()]
        self.assertIn('production_plan', production.prepare(s, {}))
        s['development']['production']['recipe_context'].pop('planning_catalog')
        self.assertNotIn('production_plan', production.prepare(s, {}))

    def test_manufacturing_choice_reads_all_table_skill_power_and_recipe_costs(self):
        s = observation()
        s['development']['production']['recipe_context']['planning_catalog'] = [component_recipe()]
        agent = self.agent()
        chosen, _ = manufacturing.choose(agent, s, {'endgame': 'ship_escape'})
        self.assertEqual(chosen['production_policy'], 'Make_ComponentIndustrial')
        self.assert_bounded(agent)
        pages = [state for state, _ in agent.seen]
        decoded = quests.reconstruct_field(pages, 'manufacturing_requirements')
        self.assertIn('FabricationBench', decoded)
        self.assertIn('construction_skill', decoded)
        self.assertIn('power_watts', decoded)
        self.assertIn('Crafting', decoded)
        self.assertIn('Steel', decoded)
        self.assertTrue(all(p['ending'] == 'ship_escape' for p in pages))

    def test_manufacturing_plan_uses_get_only_and_revalidates_changed_requirements(self):
        s = observation(); row = component_recipe()
        s['development']['production']['recipe_context']['planning_catalog'] = [row]
        class Client:
            posts = []
            def get(self, path, **kwargs): return {'available': True, 'options': [], 'planning_catalog': [copy.deepcopy(row)]}
            def post(self, *args, **kwargs): raise AssertionError('A plan must not issue gameplay orders')
        memory = {}
        selected = {'production_policy': row['recipe'], 'product_def': 'ComponentIndustrial'}
        result = manufacturing.execute(Client(), s, memory, selected)
        self.assertTrue(result['plan_only']); self.assertFalse(result['completion_verified'])
        self.assertEqual(memory['manufacturing_goal']['target_stock'], 30)
        row['skill_requirements'][0]['level'] = 9
        # Snapshot must retain the earlier exact terms.
        s['development']['production']['recipe_context']['planning_catalog'] = [component_recipe()]
        self.assertEqual(manufacturing.execute(Client(), s, {}, selected)['reason'], 'manufacturing_requirements_changed')

    def test_selected_manufacturing_goal_exposes_actual_research_frontier_and_stock_provenance(self):
        s = observation(); recipe = component_recipe()
        s['development']['production']['recipe_context']['planning_catalog'] = [recipe]
        s['development']['research_tree'] = [
            {'name': 'Fabrication', 'can_start_now': False, 'prerequisites': ['MicroelectronicsBasics']},
            {'name': 'MicroelectronicsBasics', 'can_start_now': True, 'player_has_any_appropriate_research_bench': True}]
        memory = {'manufacturing_goal': {'recipe': recipe['recipe'], 'product_def': 'ComponentIndustrial', 'target_stock': 30}}
        manufacturing.prepare(s, memory)
        self.assertEqual(s['development']['progression']['manufacturing_support']['frontier'], ['MicroelectronicsBasics'])
        self.assertEqual(facts.material_need(s, 'Steel')['selected_recipe_need'], 12)
        recipe['products'][0]['stock'] = 30
        manufacturing.prepare(s, memory)
        goal = s['development']['manufacturing_goal']
        self.assertTrue(goal['stock_target_met']); self.assertIn('not attributed', goal['outcome'])
        self.assertEqual(facts.material_need(s, 'Steel')['selected_recipe_need'], 0)

    @patch('colony_retry.time.time')
    def test_manufacturing_review_respects_both_clocks(self, clock):
        s = observation(); s['development']['production']['recipe_context']['planning_catalog'] = [component_recipe()]
        clock.return_value = 100
        memory = {}
        manufacturing.execute(None, s, memory, {'production_policy': 'defer'})
        s['game']['tick'] += 30000
        clock.return_value = 219
        self.assertFalse(manufacturing.prepare(s, memory))
        s['game']['tick'] -= 1; clock.return_value = 221
        self.assertFalse(manufacturing.prepare(s, memory))
        s['game']['tick'] += 1
        self.assertTrue(manufacturing.prepare(s, memory))


if __name__ == '__main__':
    unittest.main()

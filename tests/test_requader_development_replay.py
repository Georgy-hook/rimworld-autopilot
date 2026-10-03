"""Sequences anchored in the captured lone Nanda state, with offline HTTP."""
import copy
import json
from pathlib import Path
import unittest

import colony_capabilities as capabilities
import colony_director as director
import colony_society as society
from test_domain_cycle_contracts import Chooser


def snapshot():
    return json.loads((Path(__file__).parent / 'fixtures' / 'requader-nanda-final.json').read_text())


class Http:
    def __init__(self, state, observe_blueprint=True, blueprint_limit=None):
        self.state = state
        self.posts = []
        self.observe_blueprint = observe_blueprint
        self.blueprint_limit = blueprint_limit

    def post(self, path, **kwargs):
        self.posts.append((path, copy.deepcopy(kwargs)))
        body = kwargs.get('body') or {}
        if path == '/api/v1/builder/blueprint' and self.observe_blueprint:
            for row in body['blueprint']['buildings'][:self.blueprint_limit]:
                self.state['development']['construction_projects'].append({
                    'def_name': row['def_name'], 'position': {
                        'x': body['position']['x'] + row['rel_x'],
                        'z': body['position']['z'] + row['rel_z']}})
        if path == '/api/v1/colonist/work-priority':
            pawn = next(p for p in self.state['colonists'] if p['id'] == body['id'])
            pawn['work_priorities'][body['work']]['priority'] = body['priority']
        return {'success': True, 'applied': True}

    def get(self, path, **kwargs):
        if path == '/api/v1/builder/projects':
            return {'projects': copy.deepcopy(self.state['development']['construction_projects'])}
        if path == '/api/v1/map/buildings':
            return copy.deepcopy(self.state['development']['buildings'])
        if path == '/api/v2/colonists/detailed':
            return [{'id': p['id'], 'name': p['name'], 'work_info': {'work_priorities': [
                {'work_type': k, 'priority': v['priority']} for k, v in p['work_priorities'].items()]}}
                for p in self.state['colonists']]
        if path == '/api/v1/society/context':
            return copy.deepcopy(self.state['development']['society'])
        raise AssertionError(path)


class RequaderDevelopmentReplay(unittest.TestCase):
    def test_weapon_defer_survives_saved_memory_drift_and_allows_growing(self):
        first = snapshot()
        memory = {}
        http = Http(first)
        action = 'improve_weapon_loadout'
        self.assertIn(action, capabilities.prepare(first, memory))
        selected, _ = capabilities.choose(Chooser({'weapon_pawn': '22839', 'weapon_item': 'defer'}), {}, action, first)
        self.assertFalse(capabilities.execute(http, first, memory, action, selected)['applied'])
        self.assertEqual([], http.posts)
        memory = json.loads(json.dumps(memory))
        second = snapshot()
        second['game']['tick'] += 100000
        pawn = second['combat']['colonists'][0]
        pawn['position']['x'] += 50
        pawn['weapon_info']['hit_points_percent'] = .75
        for w in second['combat']['available_weapons']:
            w['position']['x'] += 10
            w['hit_points_percent'] = .6
        actions = capabilities.prepare(second, memory)
        self.assertNotIn(action, actions)
        self.assertIn('create_growing_zone', actions)
        selected, _ = capabilities.choose(Chooser(), {}, 'create_growing_zone', second)
        self.assertTrue(capabilities.execute(http, second, memory, 'create_growing_zone', selected)['applied'])
        self.assertTrue(any(path == '/api/v1/map/zone/growing' for path, _ in http.posts))
        for change in ('new_weapon', 'new_threat', 'current_weapon'):
            with self.subTest(change=change):
                third = snapshot()
                third['game']['tick'] += 100001
                if change == 'new_weapon':
                    third['combat']['available_weapons'].append({**third['combat']['available_weapons'][1], 'id': 99999})
                elif change == 'new_threat':
                    third['combat']['hostiles'] = [{'id': 9999, 'kind_def': 'Scyther', 'is_mechanoid': True,
                        'position': {'x': 240, 'z': 240}, 'weapon_range': 1}]
                else:
                    third['combat']['colonists'][0]['weapon_def'] = 'Gun_Revolver'
                self.assertIn(action, capabilities.prepare(third, copy.deepcopy(memory)))

    def test_drug_defer_ignores_hunger_and_reopens_for_real_clinical_change(self):
        first = snapshot()
        memory = {}
        action = 'society_drug_policy'
        self.assertIn(action, society.prepare(first, memory))
        selected, _ = society.choose(Chooser({action: 'defer'}), {}, action, first)
        self.assertFalse(society.execute(Http(first), first, memory, action, selected)['applied'])
        memory = json.loads(json.dumps(memory))
        second = snapshot()
        second['game']['tick'] += 100000
        for need in second['development']['society']['people'][0]['needs']:
            need['level'] = .1
        self.assertNotIn(action, society.prepare(second, memory))
        for change in ('dependency', 'withdrawal', 'new_stock'):
            with self.subTest(change=change):
                third = copy.deepcopy(second)
                person = third['development']['society']['people'][0]
                if change == 'dependency':
                    person['genes']['dependencies'] = [{'chemical': 'Psychite', 'last_ingested_tick': third['game']['tick']}]
                elif change == 'withdrawal':
                    person['drugs']['conditions'] = [{'def_name': 'PsychiteWithdrawal', 'severity': .3}]
                else:
                    person['drugs']['entries'][0]['stock'] = 5
                self.assertIn(action, society.prepare(third, copy.deepcopy(memory)))

    def test_optional_drug_policy_is_not_a_shelter_care_blocker(self):
        state = snapshot()
        actions = ['build_starter_base', 'society_drug_policy', 'society_drug_entry']
        memory = {'anchor': {'x': 146, 'z': 115}}
        self.assertEqual(['build_starter_base'], director.defer_discretionary_work_until_shelter(state, memory, actions))
        person = state['development']['society']['people'][0]
        person['genes']['dependencies'] = [{'chemical': 'Luciferium'}]
        self.assertIn('society_drug_policy', director.defer_discretionary_work_until_shelter(state, memory, actions))
        person['genes']['dependencies'] = []
        person['beliefs'] = ['DrugUse_Prohibited: nonmedical drugs forbidden']
        self.assertIn('society_drug_policy', director.defer_discretionary_work_until_shelter(state, memory, actions))
        self.assertEqual('work_orders', society.DOMAINS['society_drug_policy'])

    def test_warm_starter_shelter_enables_lone_priority_zero_builder_after_readback(self):
        state = snapshot()
        memory = {'anchor': {'x': 146, 'z': 115}, 'issued': {}}
        self.assertEqual(0, state['colonists'][0]['work_priorities']['Construction']['priority'])
        http = Http(state)
        result = director.execute_action(http, state, memory, 'build_starter_base', {})
        self.assertTrue(result['applied'])
        self.assertTrue(state['development']['construction_projects'])
        self.assertEqual(1, state['colonists'][0]['work_priorities']['Construction']['priority'])
        self.assertTrue(any(r.get('applied') for r in result['shelter_staffing']))

    def test_partially_accepted_starter_staffs_and_retries_exact_cells_after_reload(self):
        state = snapshot()
        memory = {'anchor': {'x': 146, 'z': 115}, 'issued': {}}
        http = Http(state, blueprint_limit=8)
        result = director.execute_action(http, state, memory, 'build_starter_base', {})
        self.assertFalse(result['applied'])
        self.assertEqual(8, result['observed_starter_projects'])
        self.assertEqual(1, state['colonists'][0]['work_priorities']['Construction']['priority'])
        self.assertNotIn('starter_base', memory['issued'])
        memory = json.loads(json.dumps(memory))
        plan = director.pending_starter_plan(memory, state['map']['id'])
        self.assertIsNotNone(plan)
        expected = len(plan['layout']['buildings'])
        memory['starter_site_verified'] = False
        actions, _ = director.candidate_actions(http, state, memory)
        self.assertIn('build_starter_base', actions)
        memory['anchor'] = {'x': 180, 'z': 180}
        # Temperature/population drift must not relocate the partially accepted plan.
        state['development']['weather']['temperature'] = -20
        state['development']['item_counts']['WoodLog'] = 0
        completed = state['development']['construction_projects'].pop(0)
        state['development']['buildings'].append({'def': completed['def_name'], 'position': completed['position']})
        http.blueprint_limit = None
        result = director.execute_action(http, state, memory, 'build_starter_base', {})
        self.assertTrue(result['applied'])
        self.assertIn('starter_base', memory['issued'])
        self.assertNotIn('pending_starter_base', memory)
        blueprints = [body['body'] for path, body in http.posts if path == '/api/v1/builder/blueprint']
        self.assertEqual({'x': 146, 'y': 0, 'z': 115}, blueprints[1]['position'])
        self.assertEqual(expected - 8, len(blueprints[1]['blueprint']['buildings']))
        projects = state['development']['construction_projects']
        cells = {(p['def_name'], p['position']['x'], p['position']['z']) for p in projects}
        self.assertEqual(expected - 1, len(projects))
        self.assertEqual(len(projects), len(cells))

    def test_pending_starter_rejects_malformed_or_wrong_map_memory(self):
        state = snapshot()
        http = Http(state, blueprint_limit=1)
        memory = {'anchor': {'x': 146, 'z': 115}, 'issued': {}}
        director.execute_action(http, state, memory, 'build_starter_base', {})
        valid = memory['pending_starter_base']
        malformed = [[], 'old', {**valid, 'map_id': True}, {**valid, 'map_id': 999},
                     {**valid, 'origin': {'x': True, 'z': 2}},
                     {**valid, 'origin': {'x': -1, 'z': 2}},
                     {**valid, 'layout': {**valid['layout'], 'width': True}},
                     {**valid, 'layout': {**valid['layout'], 'buildings': [{'def_name': 'Wall', 'rel_x': 1000, 'rel_z': 0}]}}]
        for record in malformed:
            with self.subTest(record=record):
                saved = {'pending_starter_base': record}
                self.assertIsNone(director.pending_starter_plan(saved, state['map']['id']))
                self.assertNotIn('pending_starter_base', saved)

    def test_unobserved_blueprint_and_active_care_do_not_change_staffing(self):
        for active_care in (False, True):
            with self.subTest(active_care=active_care):
                state = snapshot()
                state['colonists'][0]['current_job'] = 'FeedPatient' if active_care else 'Clean'
                http = Http(state, observe_blueprint=active_care)
                memory = {'anchor': {'x': 146, 'z': 115}, 'issued': {}}
                result = director.execute_action(http, state, memory, 'build_starter_base', {})
                self.assertEqual(active_care, result['applied'])
                self.assertFalse(any(path == '/api/v1/colonist/work-priority' for path, _ in http.posts))
                self.assertEqual(0, state['colonists'][0]['work_priorities']['Construction']['priority'])

    def test_improvised_native_weapon_is_not_routine_upgrade_but_unarmed_fallback(self):
        state = snapshot()
        wood = {**next(w for w in state['combat']['available_weapons'] if w['def_name'] == 'WoodLog'),
                'is_weapon': True, 'is_improvised': True}
        state['combat']['available_weapons'] = [wood]
        self.assertNotIn('improve_weapon_loadout', capabilities.prepare(state, {}))
        state['combat']['colonists'][0]['weapon_def'] = None
        state['combat']['colonists'][0]['weapon_info'] = {}
        self.assertIn('improve_weapon_loadout', capabilities.prepare(state, {}))
        state['combat']['colonists'][0]['weapon_def'] = 'Gun_BoltActionRifle'
        state['combat']['colonists'][0]['weapon_info'] = snapshot()['combat']['colonists'][0]['weapon_info']
        state['combat']['available_weapons'] = [{**wood, 'is_weapon': False, 'is_improvised': False}]
        self.assertNotIn('improve_weapon_loadout', capabilities.prepare(state, {}))
        state = snapshot()
        state['combat']['available_weapons'] = [{**wood, 'id': 9999, 'def_name': 'ModTaggedMelee', 'is_improvised': False}]
        self.assertIn('improve_weapon_loadout', capabilities.prepare(state, {}))
        note = capabilities.weapon_tradeoff_note(snapshot()['combat']['colonists'][0]['weapon_info'], wood)
        self.assertIn('loses ranged reach', note)
        self.assertIn('range change -', note)
        # The historical payload has no additive classifier fields; valid guns remain.
        state['combat']['available_weapons'] = [snapshot()['combat']['available_weapons'][1]]
        self.assertIn('improve_weapon_loadout', capabilities.prepare(state, {}))

    def test_malformed_semantic_memory_is_pruned_by_public_prepare(self):
        for malformed in ([], 'bad', {'22839': {'tick': True, 'map_id': 0, 'guard': 'bad'},
                                      'dead': {'tick': 1, 'map_id': 0, 'guard': 'bad'}},
                          {'22839': {'tick': 99999999, 'map_id': 0, 'guard': 'future'}},
                          {'22839': {'tick': 1, 'map_id': False, 'guard': 'bad map'}}):
            with self.subTest(malformed=malformed):
                state = snapshot()
                self.assertIn('improve_weapon_loadout', capabilities.prepare(state, {'weapon_deferred': malformed}))
        for malformed in ([], 'bad', {'society_drug_policy:22839': {'tick': True, 'map_id': 0, 'state': 'bad'},
                                      'society_drug_policy:dead': {'tick': 1, 'map_id': 0, 'state': 'bad'}},
                          {'society_drug_policy:22839': {'tick': 99999999, 'map_id': 0, 'state': 'future'}},
                          {'society_drug_policy:22839': {'tick': 1, 'map_id': False, 'state': 'bad map'}}):
            with self.subTest(malformed=malformed):
                state = snapshot()
                self.assertIn('society_drug_policy', society.prepare(state, {'society_memory': {'drug_deferred': malformed}}))

    def test_native_classifier_reports_category_and_tags_without_filtering_catalog(self):
        source = (Path(__file__).parents[1] / 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/WeaponAutomationHelper.cs').read_text()
        self.assertIn('IsWeapon = def.IsWeapon', source)
        self.assertIn('!def.IsWithinCategory(ThingCategoryDefOf.Weapons)', source)
        self.assertIn('def.weaponTags.NullOrEmpty()', source)
        self.assertIn('Where(d => d.IsWeapon)', source)

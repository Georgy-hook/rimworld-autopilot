import copy
import json
import unittest
from unittest.mock import patch
import colony_architect as a
import colony_shipbuilding as ship
import colony_director as d


def row(definition, x, z, rotation=0, stuff=None):
    return {"def_name": definition, "position": {"x": x, "z": z}, "rotation": rotation,
            "stuff_def_name": stuff}


class NativeClient:
    def __init__(self, projects=None, raise_after=False, place=True):
        self.projects = projects or []
        self.buildings = []
        self.raise_after = raise_after
        self.place = place
        self.posts = []
        self.preview_blocked = False
        self.catalog = [{"def_name": n, "available_now": True, "cost_list": []}
                        for n in ("Wall", "Door", "Ship_Beam", "Ship_ComputerCore", "Ship_CryptosleepCasket")]
    def get(self, path, **query):
        if path.endswith('/projects'): return {"projects": copy.deepcopy(self.projects)}
        if path.endswith('/buildings'): return copy.deepcopy(self.buildings)
        if path.endswith('/terrain'): return {}
        if path.endswith('/catalog'): return self.catalog
        if path.endswith('/things'): return [{"def_name": "WoodLog", "stack_count": 1000}]
        raise AssertionError(path)
    def post(self, path, **request):
        self.posts.append((path, copy.deepcopy(request)))
        body = request['body']
        if path.endswith('/preview'):
            return {"all_placeable": not self.preview_blocked,
                    "elements": [{"kind": "building", "index": i, "accepted": not self.preview_blocked}
                                 for i, part in enumerate(body['blueprint'].get('buildings', []))]}
        if self.place:
            origin = body['position']
            for part in body['blueprint'].get('buildings', []):
                self.projects.append(row(part['def_name'], origin['x'] + part['rel_x'],
                                         origin['z'] + part['rel_z'], part.get('rotation', 0),
                                         part.get('stuff_def_name')))
        if self.raise_after: raise ConnectionError('reply lost')
        return {"success": True}


class ConstructionRecoveryTests(unittest.TestCase):
    def fixture(self):
        layout = {'width': 2, 'height': 1, 'buildings': [
            {'def_name': 'Wall', 'rel_x': 0, 'rel_z': 0, 'rotation': 0, 'stuff_def_name': 'WoodLog'},
            {'def_name': 'Door', 'rel_x': 1, 'rel_z': 0, 'rotation': 0, 'stuff_def_name': 'WoodLog'}], 'floors': []}
        project = {'map_id': 1, 'program': 'hospital', 'origin': {'x': 10, 'z': 10},
                   'layout': layout, 'width': 2, 'height': 1, 'issued_tick': 100}
        return {'architecture_projects': [project]}, {'map': {'id': 1}, 'game': {'tick': 3000}}
    def test_actual_architecture_executor_partial_lost_reply_then_explicit_repair(self):
        template, snap = self.fixture()
        layout = template['architecture_projects'][0]['layout']
        memory = {'anchor': {'x': 10, 'z': 10}, 'issued': {}}
        client = NativeClient()
        original = client.post
        def partial(path, **kwargs):
            result = original(path, **kwargs)
            if not path.endswith('/preview'):
                client.projects.pop()  # Native accepted wall, rejected door after preview drift.
                raise ConnectionError('partial reply lost')
            return result
        client.post = partial
        variant = {'layout': layout, 'width': 2, 'height': 1}
        with patch.object(a, 'generate_program_variants', return_value={'v': variant}), \
             patch.object(a, 'affordable_variants', side_effect=lambda v, c: v), \
             patch.object(d, 'find_terrain_rect', return_value={'x': 10, 'z': 10}), \
             patch.object(d, 'prioritize', return_value={}):
            result = d.execute_action(client, snap, memory, 'plan_architecture', {
                'architecture_program': 'hospital', 'architecture_variant': 'v',
                'architecture_material': 'WoodLog',
                'architecture_context': {'material_options': {'WoodLog': 'wood'}}})
        self.assertFalse(result['applied']); self.assertIn('partial reply lost', result['transport_error'])
        self.assertEqual(memory['architecture_projects'][0]['layout'], layout)
        memory = json.loads(json.dumps(memory)); snap['game']['tick'] = 6000
        client.post = original
        result = d.execute_action(client, snap, memory, 'repair_architecture', {'architecture_repair': '0'})
        self.assertTrue(result['applied']); self.assertTrue(result['complete_plan_placed'])
        self.assertEqual(client.posts[-1][1]['body']['blueprint']['buildings'], [layout['buildings'][1]])

    def test_native_fine_floor_cost_and_unknown_not_free(self):
        catalog = [{'def_name': 'FineTileGranite', 'cost_list': [{'thing_def': 'BlocksGranite', 'count': 20}]},
                   {'def_name': 'WoodPlankFloor', 'cost_list': [{'thing_def': 'WoodLog', 'count': 7}]}]
        self.assertEqual(a.estimated_stuff_cost({'floors': [{'def_name': 'FineTileGranite'}]}, catalog), {'BlocksGranite': 20})
        self.assertEqual(a.estimated_stuff_cost({'floors': [{'def_name': 'WoodPlankFloor'}]}, catalog), {'WoodLog': 7})
        self.assertEqual(a.estimated_stuff_cost({'floors': [{'def_name': 'WoodPlankFloor'}]}, []), {'WoodLog': 3})
        self.assertEqual(a.estimated_stuff_cost({'floors': [{'def_name': 'ModFloor'}]}, []), {'unknown_floor_cost:ModFloor': 1})
    def test_partial_door_repair_same_origin_then_observed_no_duplicate(self):
        memory, snap = self.fixture()
        client = NativeClient([row('Wall', 10, 10, stuff='WoodLog')], raise_after=True)
        memory = json.loads(json.dumps(memory))
        result = a.execute_repair(client, snap, memory, '0', lambda *_: {})
        self.assertTrue(result['applied']); self.assertTrue(result['complete_plan_placed'])
        self.assertEqual(result['completion'], 'unverified')
        posted = client.posts[-1][1]['body']
        self.assertEqual(posted['position'], {'x': 10, 'y': 0, 'z': 10})
        self.assertEqual([r['def_name'] for r in posted['blueprint']['buildings']], ['Door'])
        self.assertEqual(memory['architecture_projects'][0]['completed_building_count'], 0)
        self.assertFalse(a.execute_repair(client, snap, memory, '0', lambda *_: {})['applied'])
        self.assertEqual(len(client.posts), 2)
    def test_material_mismatch_is_visible_blocker_no_post_demolition(self):
        memory, snap = self.fixture()
        client = NativeClient([row('Wall', 10, 10, stuff='WoodLog')])
        client.buildings = [row('Door', 11, 10, stuff='BlocksGranite')]
        result = a.execute_repair(client, snap, memory, '0', lambda *_: {})
        self.assertEqual(result['reason'], 'architecture_repair_occupied_identity_blocker')
        self.assertTrue(result['blockers']); self.assertFalse(client.posts)
    def test_preview_blocked_failure_backoff_json_rollback_and_cancel(self):
        memory, snap = self.fixture()
        client = NativeClient([row('Wall', 10, 10, stuff='WoodLog')]); client.preview_blocked = True
        self.assertEqual(a.execute_repair(client, snap, memory, '0', lambda *_: {})['reason'], 'architecture_repair_native_blocked')
        memory = json.loads(json.dumps(memory))
        self.assertFalse(a.execute_repair(client, snap, memory, '0', lambda *_: {})['applied'])
        self.assertEqual(len(client.posts), 1)
        snap['game']['tick'] = 20
        a.reconcile_projects({'construction_projects': client.projects}, memory, 1, 20, lambda *_: {})
        self.assertEqual(memory['architecture_projects'][0]['repair_tick'], 20)
        client.projects = []
        a.reconcile_projects({}, memory, 1, 100, lambda *_: {})
        self.assertTrue(memory['architecture_projects'][0]['reservation_active'])
        a.reconcile_projects({}, memory, 1, 2600, lambda *_: {})
        self.assertFalse(memory['architecture_projects'][0]['reservation_active'])
        self.assertFalse(d.architecture_occupied_cells({}, memory))
    def test_repair_fresh_research_and_material_failure_never_posts(self):
        for locked in (False, True):
            memory, snap = self.fixture()
            client = NativeClient([row('Wall', 10, 10, stuff='WoodLog')])
            client.catalog[1]['available_now'] = not locked
            client.catalog[1]['cost_list'] = [{'thing_def': 'Steel', 'count': 2}]
            result = a.execute_repair(client, snap, memory, '0', lambda *_: {})
            self.assertEqual(result['reason'], 'architecture_repair_budget_or_research')
            self.assertFalse(client.posts)
            self.assertEqual(result['shortages'], {'Steel': 2})
            self.assertEqual(result['locked_definitions'], ['Door'] if locked else [])

    def test_wrong_map_and_unknown_rotation_cannot_repair_or_certify(self):
        memory, snap = self.fixture()
        physical = row('Wall', 10, 10, stuff='WoodLog'); physical.pop('rotation')
        a.reconcile_projects({'buildings': [physical]}, memory, 1, 3000, lambda *_: {})
        self.assertEqual(memory['architecture_projects'][0]['verified_count'], 0)
        self.assertFalse(a.reconcile_projects({}, memory, 2, 3000, lambda *_: {}))


class ShipRecoveryTests(unittest.TestCase):
    def fixture(self):
        layout = {'width': 2, 'height': 6, 'floors': [], 'buildings': [
            {'def_name': 'Ship_Beam', 'rel_x': 0, 'rel_z': 0, 'rotation': 0}]}
        snap = {'map': {'id': 1}, 'game': {'tick': 3000}, 'development': {
            'building_catalog': [{'def_name': 'Ship_Beam', 'available_now': True, 'cost_list': []}]}}
        return layout, snap, {'anchor': {'x': 15, 'z': 15}}
    def test_wrong_or_unknown_rotated_part_not_complete_queued_not_built(self):
        layout, snap, memory = self.fixture()
        memory['ship_project'] = {'origin': {'x': 10, 'z': 40}, 'layout': layout}
        for rotation in (2, None):
            snap['development']['buildings'] = [row('Ship_Beam', 10, 40, rotation)]
            self.assertFalse(ship.prepare(snap, memory, layout)['completed'])
        snap['development']['buildings'] = []
        snap['development']['construction_projects'] = [row('Ship_Beam', 10, 40)]
        plan = ship.prepare(snap, memory, layout)
        self.assertEqual(plan['queued'], 1); self.assertFalse(plan['completed'])
    def test_applied_post_then_exception_preserves_observed_site_reload(self):
        layout, snap, memory = self.fixture()
        client = NativeClient(raise_after=True)
        result = ship.execute(client, snap, memory, layout)
        self.assertTrue(result['applied']); self.assertIn('reply lost', result['transport_error'])
        memory = json.loads(json.dumps(memory))
        count = len(client.posts)
        self.assertFalse(ship.execute(client, snap, memory, layout)['applied'])
        self.assertEqual(len(client.posts), count)
        self.assertEqual(memory['ship_project']['map_id'], 1)
    def test_empty_failed_post_releases_site_backoff_then_reselects(self):
        layout, snap, memory = self.fixture()
        client = NativeClient(raise_after=True, place=False)
        self.assertFalse(ship.execute(client, snap, memory, layout)['applied'])
        self.assertNotIn('ship_project', memory)
        memory = json.loads(json.dumps(memory))
        count = len(client.posts)
        self.assertFalse(ship.execute(client, snap, memory, layout)['applied'])
        self.assertEqual(len(client.posts), count)
        snap['game']['tick'] = 5501; client.place = True; client.raise_after = False
        self.assertTrue(ship.execute(client, snap, memory, layout)['applied'])
        self.assertEqual(sum(p.endswith('/preview') for p, _ in client.posts), 4)

if __name__ == '__main__': unittest.main()

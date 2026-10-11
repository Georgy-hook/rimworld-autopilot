import copy
import unittest
from unittest.mock import patch
import colony_storage as storage
import colony_architect as architect
import colony_director as director
import colony_production as production


def terrain(width=20, height=20):
    return {'width': width, 'height': height, 'dry_foundation_grid': [width*height, 1],
            'mountain_roof_grid': [width*height, 0], 'stockpile_available_grid': [width*height, 1]}


def change(t, field, cells, value):
    result = storage.grid(t, field, {-1, 0, 1})
    for x, z in cells: result[z*t['width']+x] = value
    t[field] = [n for v in result for n in (1, v)]


class StorageTests(unittest.TestCase):
    def test_whole_site_rejects_swamp_unknown_mountain_and_zones(self):
        for field, value in [('dry_foundation_grid', 0), ('mountain_roof_grid', 1),
                             ('mountain_roof_grid', -1), ('stockpile_available_grid', 0)]:
            t = terrain()
            change(t, field, [(8, 8)], value)
            self.assertIsNone(storage.site(t, {'x': 7, 'z': 7}, 5, 5, radius=0))
        self.assertEqual(storage.site(terrain(), {'x': 7, 'z': 7}, 5, 5, radius=0), {'x': 7, 'z': 7})

    def test_missing_or_truncated_native_grid_does_not_guess(self):
        for field in ('dry_foundation_grid', 'mountain_roof_grid', 'stockpile_available_grid'):
            t = terrain(); t[field] = [1, 1]
            self.assertIsNone(storage.site(t, {'x': 7, 'z': 7}, 5, 5))
        t = terrain(); t['dry_foundation_grid'] = [True, 1]
        self.assertIsNone(storage.site(t, {'x': 7, 'z': 7}, 5, 5))

    def test_layout_reservation_and_access_margin_are_preserved(self):
        self.assertIsNone(storage.site(terrain(), {'x': 7, 'z': 7}, 5, 5, {(6, 8)}, radius=0))
        self.assertIsNone(storage.site(terrain(), {'x': 1, 'z': 1}, 5, 5, radius=0))

    def test_variants_bind_shelves_to_intended_purpose_before_construction(self):
        plans = storage.variants({'material': 'WoodLog', 'item_counts': {'WoodLog': 2000}})
        self.assertEqual({p['storage_role'] for p in plans.values()}, set(storage.PROFILES))
        for plan in plans.values():
            layout = plan['layout']
            self.assertTrue(layout['roof'] and layout['require_dry_ground'] and layout['avoid_mountain_roof'])
            self.assertEqual(architect.layout_anchor_conflicts(layout), [])
            self.assertTrue(all(b['storage_profile'] == plan['storage_role']
                                for b in layout['buildings'] if b['def_name'] == 'Shelf'))

    def test_optional_floor_uses_loaded_cost_and_competes_with_materials(self):
        context = {'material': 'WoodLog', 'item_counts': {'WoodLog': 2000, 'Steel': 2000},
                   'building_catalog': [{'def_name': 'Wall', 'available_now': True}, {'def_name': 'Door', 'available_now': True},
                     {'def_name': 'Shelf', 'available_now': True, 'stuff_categories': ['Woody'], 'compatible_stuffs': ['WoodLog']},
                     {'def_name': 'Concrete', 'available_now': True, 'cost_list': [{'thing_def': 'Steel', 'count': 2}]}]}
        plans = storage.variants(context)
        self.assertIn('dry_goods:bare', plans); self.assertIn('dry_goods:Concrete', plans)
        bare, paved = plans['dry_goods:bare']['layout'], plans['dry_goods:Concrete']['layout']
        self.assertEqual(architect.estimated_stuff_cost(paved, context['building_catalog'])['Steel'], len(paved['floors'])*2)
        self.assertNotIn('Steel', architect.estimated_stuff_cost(bare, context['building_catalog']))

    def test_adjacency_uses_actual_completed_facility(self):
        buildings = [{'def': 'ElectricStove', 'position': {'x': 30, 'z': 40}},
                     {'def': 'FabricationBench', 'position': {'x': 90, 'z': 90}}]
        self.assertEqual(storage.adjacent_anchor('kitchen_inputs', buildings, {'x': 10, 'z': 10}), {'x': 36, 'z': 40})
        self.assertEqual(storage.adjacent_anchor('workshop_inputs', buildings, {'x': 10, 'z': 10}), {'x': 96, 'z': 90})

    def test_freezer_never_contains_campfire_or_interior_cooler(self):
        plans = architect.generate_program_variants('freezer', {'material': 'WoodLog', 'climate': 'cold', 'powered': True})
        for p in plans.values():
            bs = p['layout']['buildings']
            self.assertFalse(any(b['def_name'] in {'Campfire', 'Heater', 'PassiveCooler'} for b in bs))
            self.assertEqual(sum(b['def_name'] == 'Cooler' for b in bs), 1)
            shelves = [b for b in bs if b['def_name'] == 'Shelf']
            self.assertEqual({b['storage_profile'] for b in shelves}, {'cold_food'} if len(shelves) == 1 else {'kitchen_inputs', 'meals'})

    def test_heat_chamber_requires_revealed_specific_roof_edge(self):
        t = terrain(30, 30)
        self.assertIsNone(storage.site(t, {'x': 7, 'z': 7}, 9, 12, heat_lure=True, radius=0))
        change(t, 'mountain_roof_grid', [(x, z) for x in range(8, 15) for z in range(15, 18)], 1)
        self.assertEqual(storage.site(t, {'x': 7, 'z': 7}, 9, 12, heat_lure=True, radius=0), {'x': 7, 'z': 7})
        change(t, 'mountain_roof_grid', [(8, 10)], 1)
        self.assertIsNone(storage.site(t, {'x': 7, 'z': 7}, 9, 12, heat_lure=True, radius=0))

    def test_heat_chamber_has_no_hot_door_stored_items_or_through_route(self):
        context = {'material': 'BlocksGranite', 'item_counts': {'BlocksGranite': 3000, 'Steel': 1000},
            'building_catalog': [{'def_name': n, 'available_now': True} for n in ('Wall', 'Door', 'Shelf', 'Cooler')],
            'actual_power_source': True, 'heat_lure_site_available': True,
            'colonists': [{'skills': {'Construction': {'level': 7}}}]}
        plans = storage.heat_lure_variants(context); self.assertTrue(plans)
        plan = next(iter(plans.values())); self.assertEqual(plan['planned_power_w'], 400)
        self.assertTrue(all(b['def_name'] == 'Wall' for b in plan['layout']['buildings'] if b['rel_z'] >= 8))
        self.assertTrue(all(b['rel_z'] == 7 and b['rotation'] == 0 for b in plan['layout']['buildings'] if b['def_name'] == 'Cooler'))
        for field in ('actual_power_source', 'heat_lure_site_available'):
            self.assertFalse(storage.heat_lure_variants({**context, field: False}))
        self.assertFalse(storage.heat_lure_variants({**context, 'material': 'Steel'}))
        self.assertFalse(storage.heat_lure_variants({**context, 'colonists': [{'skills': {'Construction': {'level': 2}}}]}))

    def test_old_main_stockpile_offset_is_replaced_by_fresh_whole_footprint(self):
        class Client:
            def __init__(self): self.posts=[]
            def get(self, *a, **kw): return terrain()
            def post(self, path, **kw): self.posts.append((path, kw)); return {'success': True}
        s = {'map': {'id': 0}, 'game': {'tick': 100}, 'development': {}}
        client=Client(); state={'anchor': {'x': 7, 'z': 7}, 'issued': {}}
        director.execute_action(client, s, state, 'create_stockpile', {})
        body=client.posts[0][1]['body']; self.assertEqual(body['storage_profile'], 'dry_goods')
        self.assertEqual(body['point_a']['x'], 7)
        self.assertNotIn('allowed_item_categories', body)

    def test_new_profile_and_cooling_policies_are_freshly_revalidated(self):
        for kind in ('profile', 'cooling'):
            option={'key': kind+':1', 'kind': kind, 'target_id': 1, 'value': 'medicine' if kind == 'profile' else '-10'}
            snapshot={'map': {'id': 0}, 'game': {'tick': 100}, 'development': {'production': {'logistics_context': {'available': True, 'options': [option]}}}}
            class Client:
                def get(self, *args, **kwargs): return {'available': True, 'options': [{**option, 'value': 'changed'}]}
                def post(self, *args, **kwargs): raise AssertionError('Stale storage configuration was issued')
            result=production.execute(Client(), snapshot, {}, 'production_material_logistics', {'production_policy': option['key']})
            self.assertEqual(result['reason'], 'logistics_no_longer_available')


if __name__ == '__main__': unittest.main()

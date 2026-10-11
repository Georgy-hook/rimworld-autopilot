"""Purpose-specific storage and observed sites; native checks remain authoritative."""

PROFILES = {
    'dry_goods': ('dry warehouse', 9, 8, 'Reviewed dry supplies, books and valuables; Normal overflow; no bulk resources, fuel, shells, corpses or special biological/anomaly items'),
    'workshop_inputs': ('workshop input annex', 7, 6, 'Small components/textiles/process inputs beside production; Preferred buffer; wood, metals and stone stay in free ground zones'),
    'kitchen_inputs': ('kitchen pantry', 6, 6, 'Raw food beside cooking; roof is not refrigeration; fresh only'),
    'meals': ('meal store', 6, 6, 'Meals beside dining/cooking; Preferred; spoilage still depends on actual temperature'),
    'medicine': ('medical supply store', 5, 5, 'Medicine beside care beds; separate from corpses and bulk material'),
    'armory': ('armory', 6, 6, 'Weapons/apparel; keep away from prison exit routes'),
}


def grid(terrain, name, values):
    width, height = int(terrain.get('width') or 0), int(terrain.get('height') or 0)
    runs = terrain.get(name)
    if width <= 0 or height <= 0 or not isinstance(runs, list) or not runs or len(runs) % 2:
        return None
    cells = []
    for count, value in zip(runs[::2], runs[1::2]):
        if type(count) is not int or count <= 0 or value not in values or len(cells) + count > width * height:
            return None
        cells.extend([value] * count)
    return cells if len(cells) == width * height else None


def site(terrain, near, width, height, blocked=(), *, stockpile=False, heat_lure=False, radius=30):
    """No guessed swamp foundation, fog, mountain storage, or zoned footprint."""
    dry = grid(terrain, 'dry_foundation_grid', {0, 1})
    roofs = grid(terrain, 'mountain_roof_grid', {-1, 0, 1})
    free = grid(terrain, 'stockpile_available_grid', {0, 1})
    if dry is None or roofs is None or free is None:
        return None
    mw, mh = int(terrain['width']), int(terrain['height'])
    occupied = set(blocked)
    def suitable(x, z):
        if not (2 <= x and 2 <= z and x+width+2 <= mw and z+height+2 <= mh): return False
        for dz in range(-1, height+1):
            for dx in range(-1, width+1):
                c = (x+dx, z+dz); i = c[1]*mw+c[0]
                if c in occupied or not dry[i] or roofs[i] == -1: return False
                inside = 0 <= dx < width and 0 <= dz < height
                if inside and not free[i]: return False
                if heat_lure:
                    # Only an already revealed, empty mountain edge is considered;
                    # there is no excavation or hidden-roof inference here.
                    hot = inside and 1 <= dx <= width-2 and 8 <= dz <= height-2
                    if hot and roofs[i] != 1: return False
                    if inside and dz <= 6 and roofs[i] != 0: return False
                elif roofs[i] != 0: return False
        return True
    sites = [(x, z) for z in range(max(2, int(near['z'])-radius), min(mh-height-2, int(near['z'])+radius)+1)
             for x in range(max(2, int(near['x'])-radius), min(mw-width-2, int(near['x'])+radius)+1)
             if suitable(x, z)]
    best = min(sites, key=lambda c: (c[0]-near['x'])**2+(c[1]-near['z'])**2) if sites else None
    return {'x': best[0], 'z': best[1]} if best else None


def adjacent_anchor(role, buildings, fallback):
    def useful(name):
        if role in {'kitchen_inputs', 'meals'}: return 'Stove' in name or name in {'Campfire', 'Table1x2c', 'Table2x2c'}
        if role == 'medicine': return name in {'Bed', 'HospitalBed'}
        if role == 'workshop_inputs': return name.startswith(('TableMachining', 'Fabrication', 'ElectricSmithy', 'FueledSmithy', 'TableStonecutter', 'HandTailoring', 'ElectricTailoring'))
        return False
    candidates = [b.get('position') for b in buildings if useful(str(b.get('def') or b.get('def_name') or ''))
                  and (b.get('position') or {}).get('x') is not None and (b.get('position') or {}).get('z') is not None]
    if not candidates: return fallback
    center = min(candidates, key=lambda p: (p['x']-fallback['x'])**2+(p['z']-fallback['z'])**2)
    return {'x': int(center['x'])+6, 'z': int(center['z'])}


def variants(context):
    import colony_architect as a
    index = a.catalog_index(context.get('building_catalog') or [])
    material = str(context.get('material') or 'WoodLog')
    floors = [None]
    # Storage needs no decorative floor by default. Offer actual nonflammable
    # floor defs/costs; stone or paving competes with buildings and components.
    for name in ('Concrete', 'PavedTile', 'Tile' + material.removeprefix('Blocks')):
        if name in index and index[name].get('available_now') is True:
            floors.append(name)
    result = {}
    for role, (label, width, height, purpose) in PROFILES.items():
        for floor_def in floors[:3]:
            items = a._shell(width, height, material, str(context.get('entry_side') or 'south'), width//2)
            for x in range(2, width-2, 3):
                for z in range(2, height-2, 3):
                    items.append({**a.building('Shelf', x, z, stuff=material), 'storage_profile': role})
            layout = {**a.blueprint(items, width, height, a._interior_floor(width, height, floor_def)),
                      'roof': True, 'require_dry_ground': True, 'avoid_mountain_roof': True}
            layout = a.resolve_layout_materials(layout, index, context.get('item_counts') or {})
            if layout is None: continue
            key = role + ':' + (floor_def or 'bare')
            result[key] = {'id': key, 'program': 'storage', 'storage_role': role, 'width': width, 'height': height,
                           'name': label, 'layout': layout, 'style': floor_def or 'bare',
                           'summary': f'{label} {width}x{height}; {purpose}; floor {floor_def or "bare, no flooring cost"}; clear aisles, dry visible ground, no overhead mountain'}
    return result


def heat_lure_variants(context):
    """Conditional construction proposal, never a guaranteed insect kill."""
    import colony_architect as a
    index = a.catalog_index(context.get('building_catalog') or [])
    material = str(context.get('material') or '')
    # This plan has no door into the hot cell block, valuable storage or ordinary
    # through-route there. Breaching insects remain a threat, not a solved raid.
    if not material.startswith('Blocks') or not (index.get('Cooler') or {}).get('available_now'):
        return {}
    if not context.get('actual_power_source') or not context.get('heat_lure_site_available'): return {}
    builders = [p for p in context.get('colonists') or [] if not any(p.get(k) for k in ('dead', 'downed', 'in_mental_state'))
                and not (p.get('skills', {}).get('Construction') or {}).get('disabled')
                and int((p.get('skills', {}).get('Construction') or {}).get('level') or 0) >= 5]
    if not builders: return {}
    width, height = 9, 12
    items = a._shell(width, height, material, 'south', width//2)
    items += [a.building('Wall', x, 7, stuff=material) for x in range(1, width-1) if x not in {3, 5}]
    items += [a.building('Cooler', x, 7, rotation=0) for x in (3, 5)] # cold South, exhaust North
    items += [{**a.building('Shelf', x, 2, stuff=material), 'storage_profile': 'kitchen_inputs'} for x in (2, 5)]
    layout = {**a.blueprint(items, width, height), 'roof': True, 'require_dry_ground': True,
              'heat_lure': True}
    layout = a.resolve_layout_materials(layout, index, context.get('item_counts') or {})
    if layout is None: return {}
    return {'isolated_exhaust': {'id': 'isolated_exhaust', 'program': 'insect_heat_lure', 'width': width,
        'height': height, 'layout': layout, 'planned_power_w': 400, 'name': 'isolated cooler-exhaust chamber',
        'summary': 'Cold store below a sealed empty mountain-roof chamber; two coolers exhaust North. Stone walls, no hot-room door/stock/through-route. Active cooling/power and heatstroke take time; lure and kills unproved; bugs can breach. No excavation.'}}
def fresh_carcass(row):
    stage = row.get('rot_stage')
    if row.get('can_butcher') is False or stage is not None and stage != 'Fresh':
        return False
    return row.get('can_butcher') is True or stage == 'Fresh'


def carcass_site(snapshot, anchor, width=4, height=3):
    dev = snapshot.get('development') or {}
    # With no observed zones/pen geometry, do not guess a fixed offset.
    if 'zones' not in dev or any(not isinstance(z.get('cells'), list) for z in dev['zones']):
        return None
    pens = (dev.get('sustenance') or {}).get('pens') or []
    if any(p.get('enclosed') and not isinstance(p.get('cells'), list) for p in pens):
        return None
    blocked = {(int(c['x']), int(c['z'])) for row in dev['zones'] + pens for c in row.get('cells') or []}
    for b in (dev.get('buildings') or []) + (dev.get('construction_projects') or []):
        pos, size = b.get('position') or {}, b.get('size') or {}
        if 'x' not in pos or 'z' not in pos:
            continue
        x, z = int(pos['x']), int(pos['z'])
        blocked.update((x+dx, z+dz) for dx in range(max(1, int(size.get('x') or 1)))
                       for dz in range(max(1, int(size.get('z') or 1))))
    for room in dev.get('rooms') or []:
        if room.get('contained_beds_ids') or any('Stove' in str(d) for d in room.get('contained_thing_defs') or []):
            blocked.update((int(c['x']), int(c['z'])) for c in room.get('cells') or [])
    bounds = snapshot.get('map') or {}
    mx, mz = int(bounds.get('width') or bounds.get('size', {}).get('x') or 250), int(bounds.get('height') or bounds.get('size', {}).get('z') or 250)
    sites = [(x,z) for x in range(max(1, int(anchor['x'])-30), min(mx-width, int(anchor['x'])+31))
             for z in range(max(1, int(anchor['z'])-30), min(mz-height, int(anchor['z'])+31))
             if 12**2 <= (x-anchor['x'])**2+(z-anchor['z'])**2 <= 30**2
             and not any((x+dx,z+dz) in blocked for dx in range(width) for dz in range(height))]
    return min(sites, key=lambda c:(c[0]-anchor['x'])**2+(c[1]-anchor['z'])**2) if sites else None

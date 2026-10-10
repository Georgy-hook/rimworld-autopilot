"""Footprints for fresh carcass storage, checked again by the native zone API."""
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

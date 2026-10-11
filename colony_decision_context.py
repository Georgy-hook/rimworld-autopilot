"""Measured cross-domain facts. Unknown observations never become readiness.

These records explain constraints to Laya; none of the helpers issues orders,
chooses a reward, predicts a death or turns a stock into income.
"""
from __future__ import annotations

import math
import re


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def stocks(snapshot):
    dev = snapshot.get('development') or {}
    rows = ((dev.get('production') or {}).get('recipe_context') or {}).get('stocks')
    if isinstance(rows, list):
        return {r['def_name']: r.get('count') for r in rows if isinstance(r, dict) and r.get('def_name')}
    return dev.get('item_counts') if isinstance(dev.get('item_counts'), dict) else None


def environment(snapshot):
    dev = snapshot.get('development') or {}
    weather = dev.get('weather') or {}
    rooms = dev.get('rooms')
    temperatures = [number(r.get('temperature')) for r in rooms or []
                    if r.get('contained_beds_ids') and r.get('open_roof_count') == 0
                    and not r.get('touches_map_edge') and not r.get('is_prison_cell')]
    temperatures = [t for t in temperatures if t is not None]
    stock = stocks(snapshot)
    utilities = (dev.get('production') or {}).get('buildings')
    burners = [b for b in utilities or [] if number(b.get('fuel_per_day')) is not None and b['fuel_per_day'] > 0]
    # All burners sharing a fuel consume one pool. Do not grant the same wood
    # reserve separately to every room or count delivered frame materials.
    known_burners = isinstance(utilities, list) and bool(burners)
    fuel_known = known_burners and all(number(b.get('fuel')) is not None for b in burners)
    wood_only = known_burners and all(b.get('fuel_defs') == ['WoodLog'] for b in burners)
    runway = None
    if fuel_known and wood_only and stock is not None:
        wood = number(stock.get('WoodLog', 0))
        if wood is not None:
            runway = round((wood + sum(b['fuel'] for b in burners)) / sum(b['fuel_per_day'] for b in burners), 2)
    return dict(outside_c=number(weather.get('temperature')),
        weather=weather.get('weather'),
        bed_room_min_c=round(min(temperatures), 1) if temperatures else None,
        bed_room_max_c=round(max(temperatures), 1) if temperatures else None,
        wood=stock.get('WoodLog', 0) if stock is not None else None,
        shared_fuel_days=runway,
        empty_burners=sum(b.get('fuel') == 0 for b in burners) if known_burners else None,
        growing=weather.get('growth_season_now'),
        next_c=[round(t, 1) for t in weather.get('next_twelfth_average_temperatures') or [] if number(t) is not None])


def quest_impact(snapshot, offer=None):
    env = environment(snapshot)
    # This is a quotation of public durations, not a guessed effect or access
    # to quest parts/hidden signals. Full original terms are paginated too.
    public = re.sub(r'<[^>]*>', '', str((offer or {}).get('description') or ''))
    durations = re.findall(r'\b\d+(?:\.\d+)?\s+(?:days?|hours?)\b', public, re.I)
    # Exact words in the public offer, never a reconstructed hidden quest part.
    # Full terms still receive lossless review; this keeps their weather cues
    # beside the reward comparison even when the terms occupy other pages.
    weather_words = re.findall(r'\b(?:weather|thunderstorm|rainy|rain|cold|heat|fallout|eclipse)\w*\b', public, re.I)
    nutrition = ((snapshot.get('map') or {}).get('resources') or {}).get('nutrition')
    result = {k: env[k] for k in ('outside_c', 'bed_room_min_c', 'wood', 'shared_fuel_days', 'empty_burners')}
    result['nutrition'] = number(nutrition)
    result['weather'] = env['weather']
    result['next_c'] = env['next_c']
    if durations:
        result['public_durations'] = list(dict.fromkeys(durations))
    if weather_words:
        result['public_weather_words'] = list(dict.fromkeys(weather_words))
    return result


def mood_person(person):
    needs = {n.get('def_name'): number(n.get('level')) for n in person.get('needs') or []}
    negative = [t for t in person.get('thoughts') or [] if number(t.get('mood_offset')) is not None and t['mood_offset'] < 0]
    negative.sort(key=lambda t: (t['mood_offset'], str(t.get('def_name'))))
    return dict(mood=needs.get('Mood', number(person.get('mood'))),
        joy=needs.get('Joy', number(person.get('joy'))),
        break_below=number(person.get('minor_break_threshold')),
        causes=[dict(thought=t.get('def_name'), offset=t['mood_offset']) for t in negative[:3]],
        other_negative=len(negative)-min(3,len(negative)))


def mood_pressure(snapshot):
    context = (snapshot.get('development') or {}).get('society') or {}
    result = []
    for p in context.get('people') or []:
        if p.get('dead') or p.get('downed') or p.get('mental_state'):
            continue
        row = mood_person(p)
        threshold = row['break_below']
        if row['mood'] is not None and row['mood'] < (threshold if threshold is not None else .4):
            result.append(dict(pawn_id=p.get('pawn_id'), **row))
    return result


def mood_causes(snapshot):
    pressured = {str(p['pawn_id']) for p in mood_pressure(snapshot)}
    return {t.get('def_name') for p in (snapshot.get('development', {}).get('society') or {}).get('people') or []
            if str(p.get('pawn_id')) in pressured for t in p.get('thoughts') or []
            if number(t.get('mood_offset')) is not None and t['mood_offset'] < 0}


def weapon_preferences(snapshot, pawn):
    detail = next((p for p in snapshot.get('colonists') or [] if str(p.get('id')) == str(pawn.get('id'))), {})
    person = next((p for p in (snapshot.get('development', {}).get('society') or {}).get('people') or []
                   if str(p.get('pawn_id')) == str(pawn.get('id'))), {})
    traits = detail.get('traits', pawn.get('traits'))
    names = [str(t.get('name') or t.get('def_name') or t.get('label')) if isinstance(t, dict) else str(t)
             for t in traits or [] if not isinstance(t, dict) or not t.get('suppressed')]
    thoughts = [dict(thought=t.get('def_name'), offset=t.get('mood_offset')) for t in person.get('thoughts') or []
                if any(word in str(t.get('def_name') or '').lower() for word in ('brawler', 'weapon'))]
    beliefs = [b for b in person.get('beliefs') or [] if 'weapon' in str(b).lower()]
    return dict(brawler=any(t.lower() == 'brawler' for t in names) if traits is not None else None,
        weapon_thoughts=thoughts, weapon_beliefs=beliefs,
        mood=mood_person(person)['mood'], break_below=number(person.get('minor_break_threshold')))


def material_need(snapshot, product):
    dev = snapshot.get('development') or {}
    stock = stocks(snapshot)
    projects = dev.get('construction_projects')
    remaining = 0
    consumers = []
    seen = set()
    for p in projects or []:
        identity = p.get('thing_id')
        if identity is not None and identity in seen: continue
        seen.add(identity)
        amount = sum(number(m.get('required_count')) or 0 for m in p.get('materials_needed') or [] if m.get('def_name') == product)
        if amount:
            remaining += amount
            consumers.append(p.get('def_name'))
    goal = dev.get('manufacturing_goal') or {}
    # Only a selected finite recipe, not every possible recipe in the catalog.
    recipe_required = sum(number(r.get('count')) or 0 for r in goal.get('fixed_ingredients') or [] if r.get('def_name') == product)
    amount = stock.get(product, 0) if stock is not None else None
    known = isinstance(projects, list) and all(isinstance(p.get('materials_needed'), list) for p in projects)
    required = remaining + recipe_required if known else None
    return dict(stock=amount, remaining_build_need=remaining if known else None,
        selected_recipe_need=recipe_required, deficit=max(0,required-amount) if required is not None and number(amount) is not None else None,
        consumers=sorted(set(str(c) for c in consumers)), selected_product=goal.get('product_def'))


def neutral_patients(snapshot):
    return [p for p in (snapshot.get('development', {}).get('resilience') or {}).get('patients') or []
            if p.get('neutral_arrival') is True]


def neutral_urgency(snapshot):
    people = neutral_patients(snapshot)
    bleeding = [number(p.get('bleedout_ticks')) for p in people]
    return dict(downed=len(people), bleeding_max=max((number(p.get('bleeding_total')) or 0 for p in people),default=0),
        bleedout_min=min((t for t in bleeding if t is not None),default=None),
        in_bed=sum(p.get('in_bed') is True for p in people)) if people else None

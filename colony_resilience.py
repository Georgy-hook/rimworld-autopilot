"""Native patient care and environmental survival, with live feasibility checks."""
from __future__ import annotations
import ast
import json
import math
from typing import Any
from laya_decisions import ask_laya_choice
from colony_retry import failure_record, recent as retry_recent

DESCRIPTIONS = {
    'resilience_shelter': 'Move a mobile colonist currently breathing rot stink to a verified clear completed bed away from corpse sources and rest there. The native bed rest job must reach the bed before exposure ends.',
    'resilience_dispose_corpse': 'Carry one corpse away from occupied living areas with a verified native hauling or burial job and completed safe destination. Short corpse pickup exposure risks the hauler; removing the source reduces rot stink exposure. Watch the corpse move before considering disposal complete.',
    'resilience_tend': 'Schedule normal treatment with a feasible doctor and medicine selected by the game. Compare patient immunity/severity, treatment expiry and scarce medicine.',
    'resilience_rescue': 'Carry a downed patient to an available appropriate bed. Compare short rescuer exposure to fallout, gas, heat or cold against leaving the victim there; hostile routes remain excluded. Rescue is not treatment.',
    'resilience_feed': 'Feed a dependent patient using a normal doctor job; food and caregiver time are consumed.',
    'resilience_clean': 'Clean hospital or kitchen filth with a normal cleaning job to reduce infection or food poisoning risk.',
    'resilience_rest': 'Prioritize patient bed rest through normal work priorities, allowing autonomous rest and treatment.',
    'resilience_prevent': 'Take one available penoxycyline dose to prevent new malaria, plague and sleeping sickness; it cannot cure existing disease.',
    'resilience_temperature': 'Set an occupied room heater or cooler to a safe target temperature. Consider cold/heat injury, power, ventilation and insulation; a thermostat cannot guarantee that target is reached.',
    'resilience_roof_guard': 'Cancel one mine or deconstruct designation threatening roof support. Compare collapse prevention against delayed resources/construction; build verified replacement support before removing it.',
    'resilience_inspect': 'Queue normal surgical inspection after observable anomaly evidence. Costs two medicines, cuts and one day anesthesia; an infected doctor can lie or infect others, and detection may trigger hostile emergence.',
    'resilience_interrogate': 'Perform a normal enabled prisoner identity interrogation. This takes warden labor and may reveal hidden threats; a negative result does not guarantee safety.',
    'resilience_interrogation_policy': 'Enable normal identity interrogation for an existing adult prisoner. Compare uncertain diagnostic value against warden labor and emergence risk; no automatic arrest is included.',
}
ACTIONS = set(DESCRIPTIONS)
LABELS = {a: a.removeprefix('resilience_') for a in ACTIONS}
DOMAINS = {a: 'care' for a in ACTIONS}

def collect(client: Any, snapshot: dict) -> dict:
    value = client.get('/api/v1/resilience/context', map_id=snapshot['map']['id'])
    if not isinstance(value, dict):
        return {'available': False, 'reason': 'invalid_context'}
    for patient in value.get('patients') or []:
        patient['conditions'] = [h for h in patient.get('conditions') or [] if h.get('visible', True)]
    return value

def _immunity_race(condition: dict) -> bool | None:
    """Only observed immunity plus native lethal evidence establishes a race."""
    if condition.get('immunity_can_develop') is False or condition.get('def_name') == 'HeartArteryBlockage':
        return False
    def number(value):
        return isinstance(value, (int,float)) and not isinstance(value,bool) and math.isfinite(value)
    lethal = condition.get('lethal_severity')
    can_kill = condition.get('can_ever_kill')
    if (number(lethal) and lethal > 0) or can_kill is True:
        dangerous = True
    elif can_kill is False or (number(lethal) and lethal <= 0):
        return False
    else:
        dangerous = None
    immunity = condition.get('immunity')
    if not number(immunity):
        return None
    if immunity >= 1:
        return False
    return dangerous


def summary(snapshot: dict) -> dict:
    context = snapshot.get('development', {}).get('resilience', {})
    patients = [{**p, 'conditions': [h for h in p.get('conditions') or [] if h.get('visible', True)]} for p in context.get('patients') or []]
    environmental = []
    for patient in patients:
        temp, low, high = (patient.get(k) for k in ('temperature', 'comfortable_min', 'comfortable_max'))
        thermal = isinstance(temp, (int, float)) and ((isinstance(low, (int, float)) and temp < low) or (isinstance(high, (int, float)) and temp > high))
        if thermal or any(float(v or 0) > 0 for v in (patient.get('gases') or {}).values()):
            environmental.append(patient)
    return {'resilience_patients': {'count': sum(bool(p.get('tendable_now') or p.get('downed') or p.get('life_threatening')) for p in patients), 'examples': patients[:4]},
            'immunity_races': {'count': sum(any(h.get('visible', True) and _immunity_race(h) is True for h in p.get('conditions') or []) for p in patients),
                               'unknown_count': sum(any(h.get('immunity') is not None and _immunity_race(h) is None for h in p.get('conditions') or []) for p in patients)},
            'environmental_exposure': {'count': len(environmental), 'examples': environmental[:4]},
            'unsafe_roof_removals': {'count': sum(row.get('kind') == 'roof_guard' for row in context.get('options') or [])},
            'environment': context.get('environment') or {}}

def _delay(action: str) -> int:
    return 60000 if action == 'resilience_inspect' else 600 if action in ('resilience_tend', 'resilience_rescue', 'resilience_feed') else 2500


def _subject(row: dict) -> str:
    return str(row['worker_id'] if row['kind'] == 'prevent' else row['target_id'])


def _option(row: dict) -> str:
    return ':'.join(str(row.get(k, '')) for k in ('kind', 'worker_id', 'target_id', 'giver'))


def _state(row: dict, context: dict) -> tuple:
    patient = next((p for p in context.get('patients') or [] if str(p.get('pawn_id')) == _subject(row)), {})
    food = patient.get('food')
    conditions = patient.get('conditions') or []
    temp, low, high = (patient.get(k) for k in ('temperature', 'comfortable_min', 'comfortable_max'))
    thermal = isinstance(temp, (int, float)) and ((isinstance(low, (int, float)) and temp < low - 10) or (isinstance(high, (int, float)) and temp > high + 10))
    return (bool(patient.get('downed')), bool(patient.get('life_threatening')),
            float(patient.get('bleeding_total') or 0) > 0, thermal,
            any(float(v or 0) > 0 for v in (patient.get('gases') or {}).values()),
            2 if isinstance(food, (int, float)) and food < .1 else 1 if isinstance(food, (int, float)) and food < .3 else 0,
            list(sorted((str(h.get('def_name')), bool(h.get('life_threatening')), bool(h.get('tendable_now')),
                          h.get('immunity') is not None and float(h.get('severity') or 0) - float(h['immunity']) >= .2,
                          2 if float(h.get('severity') or 0) >= .75 else 1 if float(h.get('severity') or 0) >= .5 else 0)
                         for h in conditions if h.get('visible', True))))


DEFER_WALL_SECONDS = 120
MAX_DEFERRED_SUBJECTS = 128


def _rest_defer_state(rows: list[dict], context: dict) -> dict:
    """Rest readiness and deterioration, independent of normal eating/sleeping."""
    patient = next((p for p in context.get('patients') or []
                    if str(p.get('pawn_id')) == _subject(rows[0])), {})
    risks = {'downed': int(bool(patient.get('downed'))),
             'life_threatening': int(bool(patient.get('life_threatening'))),
             'bleeding': 2 if float(patient.get('bleeding_total') or 0) >= 1.5
                         else int(float(patient.get('bleeding_total') or 0) > 0),
             'tendable': int(bool(patient.get('tendable_now')))}
    for h in patient.get('conditions') or []:
        if not h.get('visible', True):
            continue
        name = str(h.get('def_name') or '')
        severity = float(h.get('severity') or 0)
        stage = h.get('cur_stage_index')
        thresholds = (.04, .2, .35, .62) if name in {'Hypothermia', 'Heatstroke'} else (.5, .75)
        band = stage if isinstance(stage, int) and not isinstance(stage, bool) and stage >= 0 else sum(severity >= x for x in thresholds)
        key = name + ':' + str(h.get('part') or '')
        risks[key + ':stage'] = band
        risks[key + ':tend'] = int(bool(h.get('tendable_now')))
        risks[key + ':danger'] = int(bool(h.get('life_threatening')))
        # Chronic nonlethal asthma reports immunity=0; that is not an infection
        # racing immunity. Only an actual lethal immunizable disease uses this.
        if _immunity_race(h) is True:
            risks[key + ':immunity_behind'] = int(severity - float(h['immunity']) >= .2)
    readiness = sorted([list(option.get(k) for k in ('kind','worker_id','target_id','giver'))
                        for option in rows], key=repr)
    return {'rest_version': 2, 'readiness': readiness, 'risks': risks}


def _rest_record_state(value: str, current: dict) -> dict | None:
    try:
        old = json.loads(value)
        if isinstance(old, dict) and old.get('rest_version') == 2:
            return old
    except (ValueError, TypeError):
        pass
    # Upgrade persisted v1/bare clinical tuples without restarting the floor
    # just because the patient has eaten or gone to sleep since the defer.
    try:
        legacy = ast.literal_eval(value)
        core = legacy[0] if len(legacy) == 8 else legacy
        if not isinstance(core, tuple) or len(core) != 7:
            return None
        conditions = core[6]
        risks = {'downed': int(bool(core[0])), 'life_threatening': int(bool(core[1])),
                 'bleeding': 2 if len(legacy) == 8 and legacy[2] else int(bool(core[2])),
                 'tendable': int(bool(legacy[3])) if len(legacy) == 8 else current['risks']['tendable']}
        for key in current['risks']:
            if ':' not in key:
                continue
            name = key.split(':', 1)[0]
            matching = [h for h in conditions if h[0] == name]
            if not matching:
                risks[key] = 0
            elif key.endswith(':stage'):
                old_bands = [h[1] for h in legacy[1] if h[0] == name] if len(legacy) == 8 else [h[4] for h in matching]
                risks[key] = max(old_bands, default=0)
            elif key.endswith(':tend'): risks[key] = int(any(h[2] for h in matching))
            elif key.endswith(':danger'): risks[key] = int(any(h[1] for h in matching))
            elif key.endswith(':immunity_behind'): risks[key] = int(any(h[3] for h in matching))
        readiness = [list(row[:4]) for row in legacy[-1]] if len(legacy) == 8 else current['readiness']
        return {'rest_version':2, 'readiness': readiness, 'risks': risks}
    except (ValueError, TypeError, SyntaxError, IndexError, KeyError):
        return None


def _defer_changed(record: dict, rows: list[dict], context: dict) -> bool:
    if rows[0].get('kind') != 'rest':
        return record.get('state') != _defer_state(rows, context)
    current = _rest_defer_state(rows, context)
    old = _rest_record_state(record.get('state'), current)
    if not old or not isinstance(old.get('risks'), dict) or not isinstance(old.get('readiness'), list):
        return True
    if any(row not in old['readiness'] for row in current['readiness']):
        return True
    for key, rank in current['risks'].items():
        prior = old['risks'].get(key, 0)
        if not isinstance(prior, (int,float)) or isinstance(prior, bool) or rank > prior:
            return True
    # Retain the deferred risk high-water mark: improvement followed by a
    # return to the same risk is not a new emergency during this finite floor.
    record['state'] = json.dumps(old, sort_keys=True)
    return False


def _defer_state(rows: list[dict], context: dict) -> str:
    """Clinical bands and exposed options; autonomous wandering is irrelevant."""
    row = rows[0]
    if row.get('kind') == 'rest':
        return json.dumps(_rest_defer_state(rows, context), sort_keys=True)
    patient = next((p for p in context.get('patients') or [] if str(p.get('pawn_id')) == _subject(row)), {})
    conditions = []
    for condition in patient.get('conditions') or []:
        if not condition.get('visible', True): continue
        name = str(condition.get('def_name') or '')
        severity = float(condition.get('severity') or 0)
        # Hypothermia stages change ability to work before severe .5/.75 bands.
        thresholds = (.04, .2, .35, .62) if name == 'Hypothermia' else (.5, .75)
        conditions.append((name, sum(severity >= boundary for boundary in thresholds)))
    readiness = sorted((tuple(option.get(field) for field in
        ('kind', 'worker_id', 'target_id', 'giver', 'food_feasible')) for option in rows), key=repr)
    return repr((_state(row, context), tuple(sorted(conditions)),
                 float(patient.get('bleeding_total') or 0) >= 1.5,
                 bool(patient.get('tendable_now')), bool(patient.get('in_bed')),
                 patient.get('bed_rest_priority'), patient.get('medical_care'), readiness))


def _defer_recent(record: dict, tick: int, delay: int) -> bool:
    return isinstance(record, dict) and isinstance(record.get('state'), str) and _recent(record, tick, delay)


def _recent(record: dict, tick: int, delay: int) -> bool:
    return retry_recent(record, tick, delay)


def _active_targets(context):
    return {(row.get('kind'), row.get('target_id')) for row in context.get('active_orders') or []
            if isinstance(row, dict) and row.get('kind') in {'feed', 'rescue', 'tend'}}


def prepare(snapshot: dict, map_state: dict) -> list[str]:
    context = snapshot.setdefault('development', {}).setdefault('resilience', {})
    memory = map_state.get('resilience_memory') or {}
    if not isinstance(memory, dict): memory = {}
    tick = int(snapshot.get('game', {}).get('tick') or 0)
    prior = map_state.get('resilience_defer_timeline') or {}
    if isinstance(prior, dict) and (prior.get('map_id') not in (None, snapshot.get('map', {}).get('id'))
            or (isinstance(prior.get('tick'), int) and tick < prior['tick'])):
        memory.pop('deferred', None)
    map_state['resilience_defer_timeline'] = {'map_id': snapshot.get('map', {}).get('id'), 'tick': tick}
    for bucket in ('issued', 'deferred', 'failed'):
        rows = memory.get(bucket) or {}
        if not isinstance(rows, dict):
            memory.pop(bucket, None)
            continue
        for key, record in list(rows.items()):
            horizon = 60 if bucket == 'failed' else _delay(str(key).split(':', 1)[0])
            if bucket == 'deferred':
                if (not isinstance(key, str) or not isinstance(record, dict)
                        or not isinstance(record.get('state'), str)
                        or isinstance(record.get('tick'), bool) or not isinstance(record.get('tick'), int)
                        or record['tick'] > tick):
                    del rows[key]
                    continue
                if 'retry_started_at' not in record and 'retry_until' not in record:
                    if not _recent(record, tick, horizon):
                        del rows[key]
                        continue
                    # Legacy defer records get one real-time floor on load.
                    record.update(failure_record(record['tick'], seconds=DEFER_WALL_SECONDS))
            if not _recent(record, tick, horizon):
                del rows[key]
        if bucket == 'deferred':
            while len(rows) > MAX_DEFERRED_SUBJECTS:
                rows.pop(next(iter(rows)))
        if not rows:
            memory.pop(bucket, None)
    if not memory:
        map_state.pop('resilience_memory', None)
    options = {a: {} for a in ACTIONS}
    active = _active_targets(context)
    active_hauls = {row.get('target_id') for row in context.get('active_orders') or [] if row.get('kind') == 'haul'}
    subject_rows = {}
    for row in context.get('options') or []:
        if 'resilience_' + str(row.get('kind')) in options:
            subject_rows.setdefault('resilience_' + str(row['kind']) + ':' + _subject(row), []).append(row)
    for row in context.get('options') or []:
        action = 'resilience_' + str(row.get('kind'))
        if action not in options:
            continue
        if (row.get('kind'), row.get('target_id')) in active or (row.get('kind') == 'dispose_corpse' and row.get('target_id') in active_hauls):
            continue
        subject = action + ':' + _subject(row)
        deferred = (memory.get('deferred') or {}).get(subject, {})
        signature = _defer_state(subject_rows[subject], context)
        if deferred.get('state') == repr(_state(row, context)):
            deferred['state'] = signature  # Migrate a still-matching legacy clinical projection.
        if (_recent((memory.get('issued') or {}).get(subject, {}), tick, _delay(action))
                or (_defer_recent(deferred, tick, _delay(action)) and not _defer_changed(deferred, subject_rows[subject], context))
                or _recent((memory.get('failed') or {}).get(_option(row), {}), tick, 60)):
            continue
        key = ':'.join(str(row.get(k, '')) for k in ('worker_id', 'target_id', 'giver'))
        options[action][key] = row
    context['plans'] = options
    snapshot['development']['sanitation_urgent'] = bool(options['resilience_dispose_corpse'] or options['resilience_shelter'])
    return [a for a, rows in options.items() if rows]

def assess(action: str, snapshot: dict) -> dict:
    return {'benefit': DESCRIPTIONS[action], 'cost': 'Worker time, medicine or food; other work waits.',
            'risk': 'Conditions and reservations may change. A scheduled job does not prove recovery. Prevention does not treat existing infections.',
            'inaction': 'Autonomous work continues; illness, hunger or contamination may persist.',
            'uncertainty': 'Immunity and severity are observed values, not a guaranteed survival forecast.'}

def choose(agent: Any, state: dict, action: str, snapshot: dict) -> tuple[dict, dict]:
    context = snapshot.get('development', {}).get('resilience', {})
    plans = context.get('plans', {}).get(action) or {}
    if not plans:
        return {'defer': True}, {'reason': 'no_live_resilience_options'}
    def defer_selection(rows):
        return {'defer': True, 'deferred_subjects': list(dict.fromkeys(_subject(row) for row in rows.values()))}
    people = {str(p['pawn_id']): p for p in context.get('patients') or [] if p.get('pawn_id') is not None}
    def subject(row: dict) -> str:
        return str(row['worker_id'] if row['kind'] == 'prevent' else row['target_id'])
    def effects(row: dict) -> dict:
        patient = people.get(subject(row), {})
        conditions = sorted((h for h in patient.get('conditions') or [] if h.get('visible', True)), key=lambda h: (bool(h.get('life_threatening')), _immunity_race(h) is True, bool(h.get('tendable_now'))), reverse=True)
        h = conditions[0] if conditions else {}
        race = _immunity_race(h)
        clinical = f"{h.get('def_name', row.get('target', row['target_id']))} s={h.get('severity')} i={h.get('immunity')} immunity_race={'yes' if race is True else 'no' if race is False else 'unknown'}"
        if row['kind'] == 'feed':
            clinical = f"{patient.get('name', row['target_id'])} food={patient.get('food')} in_bed={patient.get('in_bed')} down={patient.get('downed')}; dependent feeding"
        exposure = f"T={patient.get('temperature')} roof={patient.get('roof')} gas={patient.get('gases')}"
        if row['kind'] == 'roof_guard':
            clinical = f"Roof support {row['target_id']} removal={row.get('giver')}"
            exposure = 'Collapse risk after planned support removals'
        elif row['kind'] == 'temperature':
            clinical = f"Device {row['target_id']} target={row.get('giver')}C"
            exposure = f"Room={row.get('current_temperature')}C existing_target={row.get('current_target_temperature')}C power={row.get('power_on')}; insulation required"
        elif row['kind'] == 'shelter':
            clinical = f"{patient.get('name',row['target_id'])} currently in rot stink; rest in verified clear bed {row.get('giver')}"
            exposure = 'Gas exposure persists during travel; clear bed and no nearby corpses checked; movement not yet completed'
        elif row['kind'] == 'dispose_corpse':
            clinical = f"Corpse {row.get('target', row['target_id'])} near living area; native completed destination verified"
            exposure = 'Short pickup exposure; source removal reduces rot stink and lung rot risk; delivery remains pending'
        elif row['kind'] == 'clean':
            clinical = f"Filth {row['target_id']} cleanliness={row.get('room_cleanliness')}"
            exposure = 'Dirty room infection/food poison; not incident disease'
        elif row['kind'] == 'prevent':
            clinical = f"{patient.get('name', row['worker_id'])} prevent new malaria/plague/sleeping sickness"
            exposure = 'No cure; uses dose; future disease not certain'
        elif row['kind'] in ('inspect', 'interrogate', 'interrogation_policy'):
            clinical = f"{patient.get('name', row['target_id'])} anomaly diagnosis; gray flesh evidence"
            exposure = 'Infected doctor can lie/infect; discovery can cause emergence'
        return {'benefit': clinical + f"; {row['kind']} worker={row.get('worker_id')} med={row.get('medicine_skill')}",
                'risk': exposure + '; rescue exposure allowed' if row['kind'] == 'rescue' else exposure,
                'cost': '2 medicine, cut4, anesthesia60000ticks' if row['kind'] == 'inspect' else f"next={h.get('next_tend_ticks')} expiry={h.get('treatment_ticks_left')} quality={h.get('tend_quality')}; labor/dose/food",
                'inaction': f"down={patient.get('downed')} threat={patient.get('life_threatening')} bleeding={patient.get('bleeding_total')}; hazard persists",
                'uncertainty': 'Negative not clear; matching sample analysis needed; infected doctor can lie' if row['kind'] in ('inspect', 'interrogate', 'interrogation_policy') else f"immunity/day={h.get('immunity_per_day')} severity/day={h.get('severity_modifiers_per_day')}; job not recovery"}
    defer = {'benefit': 'Preserve current jobs/resources', 'risk': 'Illness/exposure/collapse can persist', 'cost': 'No new dose/food/labor', 'inaction': 'Autonomous work continues', 'uncertainty': 'No recovery guarantee'}
    targets = {}
    target_effects = {}
    for row in plans.values():
        target = subject(row)
        target_effects.setdefault(target, effects(row))
        targets.setdefault(target, f"{people.get(target, {}).get('name', row.get('target', target))}; {target_effects[target]['benefit']}")
    targets['defer'] = 'Preserve current jobs/resources; hazards may persist.'
    target_effects['defer'] = defer
    target, first = ask_laya_choice(agent, {'decision_facts': {'action': action, 'live_targets': len(targets)-1}, 'option_effects': target_effects}, action + '_patient', 'Choose a live patient/device/support, or defer. Compare exact illness and exposure.', targets, detailed=True)
    if target == 'defer':
        return defer_selection(plans), first
    plans = {k: row for k, row in plans.items() if subject(row) == target}
    choices = {k: f"{row.get('worker', row['worker_id'])}; {row.get('giver', row['kind'])}; Medicine {row.get('medicine_skill')}" for k, row in plans.items()}
    option_effects = {k: effects(row) for k, row in plans.items()}
    for key, row in plans.items():
        option_effects[key]['benefit'] = f"worker={row['worker_id']} med={row.get('medicine_skill')} {row.get('giver', row['kind'])}; " + option_effects[key]['benefit']
        if row['kind'] == 'inspect':
            option_effects[key]['benefit'] = f"Doctor{row['worker_id']} M{row.get('medicine_skill')} surgery={row.get('surgery_success')} bed={row.get('giver')}"
            option_effects[key]['risk'] = f"doctor can lie; bed cleanliness={row.get('room_cleanliness')} T={row.get('current_temperature')}; emergence possible"
    choices['defer'], option_effects['defer'] = targets['defer'], defer
    key, raw = ask_laya_choice(agent, {'decision_facts': {'target': target, 'evidence': target_effects[target]['benefit'], 'exposure': target_effects[target]['risk']}, 'option_effects': option_effects}, action, DESCRIPTIONS[action], choices, detailed=True)
    raw['patient_choice'] = first
    return (defer_selection(plans) if key == 'defer' else {k: plans[key][k] for k in ('kind', 'worker_id', 'target_id', 'giver') if k in plans[key]}), raw

def execute(client: Any, snapshot: dict, map_state: dict, action: str, selected: dict) -> dict:
    tick = int(snapshot.get('game', {}).get('tick') or 0)
    memory = map_state.setdefault('resilience_memory', {})
    if selected.get('defer'):
        context = snapshot.get('development', {}).get('resilience', {})
        for row in (context.get('plans', {}).get(action) or {}).values():
            if 'deferred_subjects' in selected and _subject(row) not in selected['deferred_subjects']:
                continue
            same_subject = [option for option in context.get('options') or []
                            if 'resilience_' + str(option.get('kind')) == action
                            and _subject(option) == _subject(row)]
            memory.setdefault('deferred', {})[action + ':' + _subject(row)] = {
                **failure_record(tick, seconds=DEFER_WALL_SECONDS), 'state': _defer_state(same_subject, context)}
        while len(memory.get('deferred') or {}) > MAX_DEFERRED_SUBJECTS:
            memory['deferred'].pop(next(iter(memory['deferred'])))
        return {'applied': False, 'reason': 'laya_deferred'}
    payload = {k: selected[k] for k in ('kind', 'worker_id', 'target_id', 'giver') if k in selected}
    def failed() -> None:
        memory.setdefault('failed', {})[_option(payload)] = failure_record(tick, seconds=15)
    try:
        fresh = collect(client, snapshot)
        if ((payload.get('kind'), payload.get('target_id')) in _active_targets(fresh)
                or (payload.get('kind') == 'dispose_corpse' and any(row.get('kind') == 'haul' and row.get('target_id') == payload.get('target_id') for row in fresh.get('active_orders') or []))
                or 'resilience_' + str(payload.get('kind')) != action or not any({k: row[k] for k in ('kind', 'worker_id', 'target_id', 'giver') if k in row} == payload for row in fresh.get('options') or [])):
            failed()
            return {'applied': False, 'reason': 'selection_no_longer_feasible'}
        result = client.post('/api/v1/resilience/order', body={'map_id': snapshot['map']['id'], **payload})
    except Exception:
        failed()
        raise
    if isinstance(result, dict) and result.get('applied') is True:
        memory.setdefault('issued', {})[action + ':' + _subject(payload)] = {'tick': tick}
    else:
        failed()
    if not isinstance(result, dict) or not isinstance(result.get("applied"), bool):
        return {"applied": False, "reason": "invalid_response", "outcome_unknown": True, "response": result}
    return result

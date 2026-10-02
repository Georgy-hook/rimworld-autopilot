"""Native patient care and environmental survival, with live feasibility checks."""
from __future__ import annotations
from typing import Any
from laya_decisions import ask_laya_choice
from colony_retry import failure_record, recent as retry_recent

DESCRIPTIONS = {
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
            'immunity_races': {'count': sum(any(h.get('visible', True) and h.get('immunity') is not None and h['immunity'] < 1 for h in p.get('conditions') or []) for p in patients)},
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


def _recent(record: dict, tick: int, delay: int) -> bool:
    return retry_recent(record, tick, delay)


def prepare(snapshot: dict, map_state: dict) -> list[str]:
    context = snapshot.setdefault('development', {}).setdefault('resilience', {})
    memory = map_state.get('resilience_memory') or {}
    tick = int(snapshot.get('game', {}).get('tick') or 0)
    for bucket in ('issued', 'deferred', 'failed'):
        rows = memory.get(bucket) or {}
        for key, record in list(rows.items()):
            horizon = 60 if bucket == 'failed' else _delay(key.split(':', 1)[0])
            if not _recent(record, tick, horizon):
                del rows[key]
        if not rows:
            memory.pop(bucket, None)
    if not memory:
        map_state.pop('resilience_memory', None)
    options = {a: {} for a in ACTIONS}
    for row in context.get('options') or []:
        action = 'resilience_' + str(row.get('kind'))
        if action not in options:
            continue
        subject = action + ':' + _subject(row)
        deferred = (memory.get('deferred') or {}).get(subject, {})
        if (_recent((memory.get('issued') or {}).get(subject, {}), tick, _delay(action))
                or (_recent(deferred, tick, _delay(action)) and deferred.get('state') == repr(_state(row, context)))
                or _recent((memory.get('failed') or {}).get(_option(row), {}), tick, 60)):
            continue
        key = ':'.join(str(row.get(k, '')) for k in ('worker_id', 'target_id', 'giver'))
        options[action][key] = row
    context['plans'] = options
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
    people = {str(p['pawn_id']): p for p in context.get('patients') or [] if p.get('pawn_id') is not None}
    def subject(row: dict) -> str:
        return str(row['worker_id'] if row['kind'] == 'prevent' else row['target_id'])
    def effects(row: dict) -> dict:
        patient = people.get(subject(row), {})
        conditions = sorted((h for h in patient.get('conditions') or [] if h.get('visible', True)), key=lambda h: (bool(h.get('life_threatening')), h.get('immunity') is not None and h['immunity'] < 1, bool(h.get('tendable_now'))), reverse=True)
        h = conditions[0] if conditions else {}
        clinical = f"{h.get('def_name', row.get('target', row['target_id']))} s={h.get('severity')} i={h.get('immunity')}"
        if row['kind'] == 'feed':
            clinical = f"{patient.get('name', row['target_id'])} food={patient.get('food')} in_bed={patient.get('in_bed')} down={patient.get('downed')}; dependent feeding"
        exposure = f"T={patient.get('temperature')} roof={patient.get('roof')} gas={patient.get('gases')}"
        if row['kind'] == 'roof_guard':
            clinical = f"Roof support {row['target_id']} removal={row.get('giver')}"
            exposure = 'Collapse risk after planned support removals'
        elif row['kind'] == 'temperature':
            clinical = f"Device {row['target_id']} target={row.get('giver')}C"
            exposure = f"Room={row.get('current_temperature')}C existing_target={row.get('current_target_temperature')}C power={row.get('power_on')}; insulation required"
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
        return {'defer': True}, first
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
    return ({'defer': True} if key == 'defer' else {k: plans[key][k] for k in ('kind', 'worker_id', 'target_id', 'giver') if k in plans[key]}), raw

def execute(client: Any, snapshot: dict, map_state: dict, action: str, selected: dict) -> dict:
    tick = int(snapshot.get('game', {}).get('tick') or 0)
    memory = map_state.setdefault('resilience_memory', {})
    if selected.get('defer'):
        context = snapshot.get('development', {}).get('resilience', {})
        for row in (context.get('plans', {}).get(action) or {}).values():
            memory.setdefault('deferred', {})[action + ':' + _subject(row)] = {'tick': tick, 'state': repr(_state(row, context))}
        return {'applied': False, 'reason': 'laya_deferred'}
    payload = {k: selected[k] for k in ('kind', 'worker_id', 'target_id', 'giver') if k in selected}
    def failed() -> None:
        memory.setdefault('failed', {})[_option(payload)] = failure_record(tick, seconds=15)
    try:
        fresh = collect(client, snapshot)
        if 'resilience_' + str(payload.get('kind')) != action or not any({k: row[k] for k in ('kind', 'worker_id', 'target_id', 'giver') if k in row} == payload for row in fresh.get('options') or []):
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
    return result if isinstance(result, dict) else {'applied': False, 'reason': 'invalid_response'}

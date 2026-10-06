"""Verified ordinary melee orders for a selected downed hostile.

The model chooses whether to finish a target. This module checks the actor,
observes the actual job, and remembers failed actor/target pairs.
"""
from __future__ import annotations

from colony_retry import failure_record, recent
import rimworld_laya as bridge


def finishable_target(pawn):
    # Mental hostility cannot turn our own resident or an allied visitor into a finisher target.
    return (pawn.get('is_downed') and not pawn.get('is_dead') and not pawn.get('is_colonist')
            and not pawn.get('is_prisoner') and str(pawn.get('faction') or '').casefold() != 'playercolony'
            and pawn.get('faction_relation_kind') != 'Ally'
            and float(pawn.get('faction_goodwill') or 0) < 75)


def eligible(pawn, protected=()):
    return (pawn.get('id') is not None and not pawn.get('is_dead')
            and not pawn.get('is_downed') and not pawn.get('is_in_mental_state')
            and pawn.get('can_fight', True)
            and bridge.first_number(pawn.get('health')) >= .75
            and bridge.first_number(pawn.get('moving'), 1) > 0
            and bridge.first_number(pawn.get('manipulation'), 1) > 0
            and str(pawn['id']) not in protected)


def attacking(pawn, target_id):
    return (str(pawn.get('current_job') or '').casefold() == 'attackmelee'
            and pawn.get('current_job_target_id') == target_id
            and pawn.get('current_job_kill_incapped_target') is True)


def _key(actor_id, target_id):
    return f'{actor_id}:{target_id}'


def _failed(memory, actor_id, target_id, tick, reason):
    memory.setdefault('failed', {})[_key(actor_id, target_id)] = {
        **failure_record(tick, 120), 'reason': reason}
    while len(memory['failed']) > 64:
        memory['failed'].pop(next(iter(memory['failed'])))
    memory.pop('active', None)


def _rows(combat, actor_id, target_id):
    if not isinstance(combat, dict) or not isinstance(combat.get('colonists'), list) or not isinstance(combat.get('hostiles'), list):
        raise bridge.RimApiError('Incomplete combat readback')
    return (next((p for p in combat.get('colonists') or [] if p.get('id') == actor_id), {}),
            next((p for p in combat.get('hostiles') or [] if p.get('id') == target_id), {}))


def _distance(actor, target):
    a, b = actor.get('position') or {}, target.get('position') or {}
    if all(k in a and k in b for k in ('x', 'z')):
        return (a['x']-b['x'])**2 + (a['z']-b['z'])**2
    return None


def _adopt(memory, actor, target, tick):
    memory['active'] = {'actor_id': actor['id'], 'target_id': target['id'],
        'best_distance': _distance(actor, target), 'best_health': bridge.first_number(target.get('health'), 1),
        'progress': failure_record(tick, 120)}


def _pending(active, reason):
    return {'applied': False, 'in_progress': True, 'actor_id': active['actor_id'],
            'target_id': active['target_id'], 'completion': 'unverified', 'reason': reason}


def prepare(snapshot, map_state, protected=()):
    """Observe an existing lease; only reconcile may cancel its actual job."""
    tick = int(snapshot['game'].get('tick') or 0)
    memory = map_state.setdefault('downed_combat', {})
    for key, row in list((memory.get('failed') or {}).items()):
        if not isinstance(row, dict) or not recent(row, tick, 6000):
            memory['failed'].pop(key)
    active = memory.get('active') or {}
    if not active:
        return None
    combat = snapshot.get('combat') or {}
    if not isinstance(combat.get('colonists'), list) or not isinstance(combat.get('hostiles'), list):
        return _pending(active, 'finishing_order_readback_unknown')
    actor, target = _rows(combat, active['actor_id'], active['target_id'])
    if not target or target.get('is_dead') or not target.get('is_downed'):
        memory.pop('active', None)
        return None
    if attacking(actor, target['id']):
        if active.pop('outcome_unknown', False):
            _adopt(memory, actor, target, tick)
            active = memory['active']
        distance, health = _distance(actor, target), bridge.first_number(target.get('health'), 1)
        best = active.get('best_distance')
        if ((distance is not None and (best is None or distance < best))
                or health < active.get('best_health', 1)):
            active.update(progress=failure_record(tick, 120), best_distance=distance if best is None else min(best, distance) if distance is not None else best,
                          best_health=min(health, active.get('best_health', 1)))
        stalled = not recent(active.get('progress') or {}, tick, 6000)
        active['stalled'] = stalled
        return _pending(active, 'finishing_job_has_no_observed_progress' if stalled else 'verified_finishing_job_in_progress')
    _failed(memory, active['actor_id'], active['target_id'], tick, 'finishing_job_ended_without_observed_completion')
    return None


def reconcile(client, snapshot, map_state, protected=()):
    result = prepare(snapshot, map_state, protected)
    memory = map_state.get('downed_combat') or {}
    active = memory.get('active') or {}
    if not result or not active.get('stalled'):
        return result
    tick = int(snapshot['game'].get('tick') or 0)
    if recent(active.get('cancel_retry') or {}, tick, 60):
        return _pending(active, 'finishing_cancel_readback_pending')
    active['cancel_retry'] = failure_record(tick, 10)
    try:
        client.post('/api/v1/pawn/job', body={'pawn_id': active['actor_id'],
            'map_id': snapshot['map']['id'], 'cancel_finishing_target_id': active['target_id']})
    except bridge.RimApiError:
        pass
    try:
        combat = client.get('/api/v1/combat/state', map_id=snapshot['map']['id'])
        actor, target = _rows(combat, active['actor_id'], active['target_id'])
        if not attacking(actor, active['target_id']):
            _failed(memory, active['actor_id'], active['target_id'], tick, 'stalled_finishing_job_cancelled_or_ended')
            return None
    except bridge.RimApiError:
        pass
    return _pending(active, 'finishing_cancel_readback_pending')


def available_fighters(snapshot, map_state, target_id, protected=()):
    memory = map_state.get('downed_combat') or {}
    target = next((p for p in (snapshot.get('combat') or {}).get('hostiles') or [] if p.get('id') == target_id), None)
    if target is not None and not finishable_target(target):
        return []
    if memory.get('active'):
        return []
    tick = int(snapshot['game'].get('tick') or 0)
    return [p for p in (snapshot.get('combat') or {}).get('colonists') or []
            if eligible(p, protected)
            and not recent((memory.get('failed') or {}).get(_key(p['id'], target_id), {}), tick, 6000)]


def issue(client, snapshot, map_state, actor, target):
    """Native validates and drafts atomically; fresh readback governs the lease."""
    tick = int(snapshot['game'].get('tick') or 0)
    memory = map_state.setdefault('downed_combat', {})
    actor_id, target_id = int(actor['id']), int(target['id'])
    result = {'applied': False, 'actor': actor.get('name'), 'actor_id': actor_id,
              'target_id': target_id, 'completion': 'unverified'}
    if not finishable_target(target):
        return {**result, 'reason': 'finishing_target_is_not_enemy'}
    if memory.get('active'):
        return {**result, 'reason': 'finishing_order_already_pending', 'in_progress': True}
    if attacking(actor, target_id):
        _adopt(memory, actor, target, tick)
        return {**result, 'in_progress': True, 'reason': 'verified_finishing_job_in_progress'}
    rejected = False
    try:
        response = client.post('/api/v1/pawn/job', body={'pawn_id': actor_id,
            'job_def': 'AttackMelee', 'target_thing_id': target_id, 'map_id': snapshot['map']['id'],
            'kill_incapped_target': True, 'request_draft_for_finishing': True})
        result['responses'] = [response]
        rejected = isinstance(response, dict) and (response.get('success') is False or response.get('applied') is False)
    except bridge.RimApiError as error:
        result.update(reason=str(error), outcome_unknown=True)
    try:
        combat = client.get('/api/v1/combat/state', map_id=snapshot['map']['id'])
        fresh, victim = _rows(combat, actor_id, target_id)
        if attacking(fresh, target_id):
            _adopt(memory, fresh, victim or target, tick)
            return {**result, 'applied': True, 'readback_verified': True, 'reason': 'finishing_job_observed'}
        result['reason'] = 'native_finishing_order_rejected' if rejected else 'finishing_job_not_observed'
        _failed(memory, actor_id, target_id, tick, result['reason'])
    except bridge.RimApiError:
        if rejected:
            result['reason'] = 'native_finishing_order_rejected'
            _failed(memory, actor_id, target_id, tick, result['reason'])
        else:
            memory['active'] = {'actor_id': actor_id, 'target_id': target_id, 'outcome_unknown': True,
                                'progress': failure_record(tick, 120)}
            result.update(outcome_unknown=True, in_progress=True, reason='finishing_order_readback_unknown')
    return result

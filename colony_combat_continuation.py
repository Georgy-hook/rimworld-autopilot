"""Finish only explicitly deferred, still idle actors of a selected tactic."""
from copy import deepcopy

FIELDS = ('positioned_pawn_ids', 'attacking_pawn_ids', 'preserved_pawn_ids')


def _accepted(response):
    for field in FIELDS:
        if field in response and (not isinstance(response[field], list) or any(
                type(pid) is not int or pid<=0 for pid in response[field])):
            raise ValueError('Invalid native tactical actor readback')
    return set().union(*(set(response.get(k) or []) for k in FIELDS))


def continue_deferred(client, action, result, planner):
    if (action.get('kind') != 'commands' or result.get('failed_command_index') is not None
            or result.get('outcome_unknown')):
        return result
    responses = result.get('responses') or []
    history = []
    for index, command in enumerate(action.get('commands') or []):
        if command.get('endpoint') != '/api/v1/combat/tactic' or index >= len(responses):
            continue
        current = responses[index]
        body = command.get('body') or {}
        if (not isinstance(current, dict) or current.get('deferred') is not True
                or current.get('review_complete') is not False or current.get('psycast_queued')
                or body.get('ability_def_name') or not body.get('fighter_ids')):
            continue
        original = set(body['fighter_ids'])
        consumed = _accepted(current)
        merged = deepcopy(current)
        for attempt in range(2):
            remaining = original - consumed
            if not remaining or current.get('deferred') is not True:
                break
            fresh = client.get('/api/v1/combat/state', map_id=body['map_id'])
            if (not isinstance(fresh, dict) or fresh.get('map_id') != body['map_id']
                    or not isinstance(fresh.get('colonists'), list)
                    or not isinstance(fresh.get('hostiles'), list)
                    or fresh.get('error') or fresh.get('errors') or fresh.get('available') is False):
                raise ValueError('Deferred combat continuation requires complete fresh native combat state')
            active = [h for h in fresh['hostiles'] if not h.get('is_dead') and not h.get('is_downed')
                      and not planner.hostile_is_preparing(h)]
            if not active or body.get('target_pawn_id') not in {h.get('id') for h in active}:
                break
            known_idle = {r.get('pawn_id') for r in current.get('current_jobs') or []
                          if r.get('drafted') is True and r.get('owned') is False
                          and r.get('job_id') is None and not r.get('job_def')
                          and r.get('queued_job_ids') == []}
            known_idle &= set(current.get('drafted_pawn_ids') or [])
            eligible = []
            for pawn in fresh['colonists']:
                if (pawn.get('id') not in remaining or pawn.get('is_drafted') is not True
                        or not (pawn.get('current_job') == 'Wait_Combat' or pawn.get('current_job') is None and pawn.get('id') in known_idle) or pawn.get('combat_plan')
                        or pawn.get('queued_job_count') != 0 or pawn.get('has_care_job')
                        or pawn.get('caregiver_recovery_protected') or pawn.get('carrying_player_pawn')
                        or pawn.get('carrying_pawn_id') or pawn.get('has_ranged_weapon') is not True
                        or any(pawn.get(k) for k in ('is_dead', 'is_downed', 'is_in_mental_state'))):
                    continue
                eligible.append(pawn['id'])
            if not eligible:
                break
            request = {**body, 'fighter_ids': sorted(eligible)}
            response = client.post('/api/v1/combat/tactic', body=request)
            if not isinstance(response, dict) or response.get('success') is False:
                raise ValueError('Deferred continuation returned an invalid native action result')
            if not _accepted(response).issubset(set(eligible)):
                raise ValueError('Deferred continuation returned actors outside the explicit remaining request')
            history.append({'command_index': index, 'attempt': attempt + 1,
                            'native_tick': fresh.get('game_tick'), 'request': request,
                            'previous_native_response': deepcopy(current), 'response': deepcopy(response)})
            consumed |= _accepted(response)
            for field in FIELDS + ('drafted_pawn_ids', 'changed_pawn_ids'):
                merged[field] = sorted(set(merged.get(field) or []) | set(response.get(field) or []))
            merged.update({k: response[k] for k in ('deferred', 'review_complete', 'partial_applied',
                'deferred_reason', 'deferred_phase', 'deferred_pawn_ids', 'current_jobs') if k in response})
            merged['applied'] = bool(consumed) or merged.get('applied') is True or response.get('applied') is True
            merged['notes'] = list(merged.get('notes') or []) + list(response.get('notes') or [])
            current = response
            responses[index] = merged
            result['native_deferred_continuations'] = history
        responses[index] = merged
    if history:
        result['native_deferred_continuations'] = history
    return result

"""Interpret observed native holders without treating rescue as disappearance."""


def observed_carriers(state):
    pawns = list(state.get('allies', [])) + list(state.get('enemies', []))
    if state.get('captive'):
        pawns.append(state['captive'])
    return {
        pawn['carried_id']: pawn['id']
        for pawn in pawns
        if pawn.get('spawned') and not pawn.get('dead') and pawn.get('carried_id') is not None
    }


def clear_window_start(active, previous_start, now):
    """A recovered enemy ends the old continuous post-combat care window."""
    if active:
        return None
    return now if previous_start is None else previous_start


def require_native_instance(state, process_id, instance_id):
    """A reused fixture campaign UUID does not identify a native process."""
    if (not isinstance(process_id, int) or process_id <= 0 or not instance_id
            or state.get('native_process_id') != process_id
            or state.get('native_instance_id') != instance_id):
        raise ValueError('Native instance changed despite a reusable fixture UUID; discard this read')
    return state

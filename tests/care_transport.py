"""Offline transport for native care assignment and exact combat-state readback."""
import copy
from unittest.mock import Mock


def bind_care_readback(client, snapshot):
    snapshot['map'].setdefault('id', 0)
    original_get = getattr(client, 'get', None)
    original_post = client.post
    mock_post = isinstance(original_post, Mock)
    previous_effect = original_post.side_effect if mock_post else None
    previous_value = original_post.return_value if mock_post else None

    def get(endpoint, **query):
        if endpoint == '/api/v1/combat/state':
            assert query.get('map_id') == snapshot['map']['id']
            return copy.deepcopy(snapshot['combat'])
        return original_get(endpoint, **query) if original_get is not None else []

    def post(endpoint, body=None, query=None):
        kwargs = {}
        if body is not None: kwargs['body'] = body
        if query is not None: kwargs['query'] = query
        result = previous_effect(endpoint, **kwargs) if mock_post and callable(previous_effect) else (
            previous_value if mock_post else original_post(endpoint, **kwargs))
        if not isinstance(result, dict) or not (result.get('success') is True or result.get('applied') is True):
            return result
        body = body or {}
        rows = snapshot['combat']['colonists']
        def actor(pid): return next(p for p in rows if p['id'] == pid)
        if endpoint == '/api/v1/pawn/medical/tend':
            actor(body['doctor_pawn_id']).update(current_job='TendPatient', current_job_target_id=body['patient_pawn_id'])
        elif endpoint == '/api/v1/pawn/medical/bed-rest':
            actor(body['patient_pawn_id']).update(current_job='LayDown', current_job_target_id=body['bed_building_id'])
        elif endpoint == '/api/v1/pawn/job':
            actor(body['pawn_id']).update(current_job=body['job_def'], current_job_target_id=body.get('target_thing_id'),
                                         current_job_target_id_b=body.get('target_thing_id_b'))
        return result

    client.get = get
    if mock_post: original_post.side_effect = post
    else: client.post = post
    return client

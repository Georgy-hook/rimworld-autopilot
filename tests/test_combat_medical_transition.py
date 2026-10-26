"""Initial postcombat care keeps a native selected-job binding until assignment."""
import copy
from contextlib import ExitStack
from pathlib import Path
import unittest
from unittest.mock import patch

import colony_director as director
import colony_medical_recovery as recovery


def fixture():
    people = [dict(id=i, name=f'p{i}', current_job='Wait_Combat' if i < 3 else 'Wait_Downed',
        is_drafted=i < 3, is_downed=i >= 3, is_dead=False, is_in_mental_state=False,
        has_care_job=False, queued_job_count=0, medical_work_enabled=True,
        consciousness=1 if i < 3 else .1, moving=1 if i < 3 else 0,
        manipulation=1 if i < 3 else 0, bleeding_rate=0 if i < 3 else 1.68 if i == 3 else .18,
        tendable_now=i >= 3, health=1 if i < 3 else .7, medicine_skill=8,
        medical_tend_speed=1, medical_tend_quality=.8, position=dict(x=10*i, z=10))
        for i in range(1, 5)]
    details = [dict(id=p['id'], name=p['name'], downed=p['is_downed'], dead=False,
        health_conditions=[], position=p['position'], capacities=dict(moving=p['moving'], manipulation=p['manipulation']),
        skills=dict(Medicine=dict(level=8, disabled=False)), work_priorities=dict(Doctor=dict(priority=1, disabled=False)))
        for p in people]
    return dict(game=dict(tick=10000), map=dict(id=0), colonists=details,
        combat=dict(available=True, colonists=people, hostiles=[], hostile_buildings=[]), development={})


class Client:
    def __init__(self, snapshot):
        self.combat = copy.deepcopy(snapshot['combat'])
        self.calls, self.posts = [], []
        self.context = dict(available=True, combat_release_tends_available=True,
            patients=[dict(pawn_id=i, bleeding_total=0 if i < 3 else 1.68 if i == 3 else .18,
                bleedout_ticks=5000 if i == 3 else 20000, bleeding_evidence_complete=True, tendable_now=i >= 3)
                for i in range(1, 5)], combat_release_tends=[
                    dict(doctor_id=i, patient_id=3, release_combat_job_id=70+i, expected_current_job='Wait_Combat',
                        travel_ticks=100 if i == 1 else 1400, locked_ticks=0,
                        medical_tend_speed=1, medical_tend_quality=.8, bleedout_ticks=5000)
                    for i in (1, 2)])

    def get(self, endpoint, **kwargs):
        self.calls.append(endpoint)
        if endpoint == '/api/v1/resilience/context':
            return copy.deepcopy(self.context)
        if endpoint == '/api/v1/combat/state':
            return copy.deepcopy(self.combat)
        return []

    def post(self, endpoint, **kwargs):
        self.posts.append(dict(endpoint=endpoint, **copy.deepcopy(kwargs)))
        if endpoint == '/api/v1/pawn/medical/tend':
            body = kwargs['body']
            actor = next(p for p in self.combat['colonists'] if p['id'] == body['doctor_pawn_id'])
            actor.update(is_drafted=False, current_job='TendPatient', current_job_target_id=body['patient_pawn_id'])
        return dict(success=True)


def entry(snapshot, client):
    with ExitStack() as stack:
        stack.enter_context(patch.object(director, 'collect_care_environment', return_value=[]))
        stack.enter_context(patch.object(director, 'ask_laya_choice', return_value=('tend_3_1', {})))
        stack.enter_context(patch.object(director, 'publish_post_combat_care_overlay'))
        stack.enter_context(patch.object(director.colony_reasoning, 'attention_facts', return_value={}))
        stack.enter_context(patch.object(director.bridge, 'append_log'))
        return director.run_initial_post_combat_care_cycle(client, object(), snapshot, Path('unused'), {})


class CombatMedicalTransitionTests(unittest.TestCase):
    def test_actual_recovering_doctor_is_kept_out_of_optional_patient_menu(self):
        snapshot = fixture()
        for pawn in snapshot['combat']['colonists'][:2]:
            pawn.update(is_drafted=False, current_job='LayDown')
        snapshot['combat']['colonists'][0]['caregiver_recovery_protected'] = True
        options = director.post_combat_care_options(snapshot)
        self.assertTrue(any(p.get('doctor_id') == 2 for p in options.values()))
        self.assertFalse(any(p.get('doctor_id') == 1 for p in options.values()))
        snapshot['combat']['colonists'][0]['caregiver_recovery_protected'] = False
        options = director.post_combat_care_options(snapshot)
        self.assertTrue(any(p.get('doctor_id') == 1 for p in options.values()))

    def test_actual_entry_sends_bound_native_tend_without_separate_undraft(self):
        snapshot = fixture(); client = Client(snapshot)
        result = entry(snapshot, client)
        self.assertTrue(result['result']['job_observed'])
        tend = next(p for p in client.posts if p['endpoint'] == '/api/v1/pawn/medical/tend')
        self.assertEqual(71, tend['body']['release_combat_job_id'])
        self.assertTrue(tend['body']['review_after_tend'])
        self.assertFalse(any(p['endpoint'] == '/api/v1/pawn/edit/status' for p in client.posts))
        self.assertEqual(1, client.calls.count('/api/v1/resilience/context'))
        self.assertTrue(client.combat['colonists'][1]['is_drafted'])

    def test_single_critical_patient_still_loads_native_initial_care_options(self):
        snapshot = fixture(); snapshot['combat']['colonists'][3].update(bleeding_rate=0, tendable_now=False)
        client = Client(snapshot); client.context['patients'][3].update(bleeding_total=0, tendable_now=False)
        result = entry(snapshot, client)
        self.assertTrue(result['result']['job_observed'])
        body = next(p['body'] for p in client.posts if p['endpoint'] == '/api/v1/pawn/medical/tend')
        self.assertTrue(body['review_after_tend'])

    def test_available_empty_patient_fallback_cannot_offer_a_release(self):
        snapshot = fixture(); client = Client(snapshot); client.context['patients'] = []
        self.assertIsNone(entry(snapshot, client))
        self.assertFalse(client.posts)
        self.assertIn('patient_coverage', snapshot['development']['resilience']['read_errors'])

    def test_older_native_without_release_capability_preserves_draft(self):
        snapshot = fixture(); client = Client(snapshot); client.context.pop('combat_release_tends_available')
        self.assertIsNone(entry(snapshot, client)); self.assertFalse(client.posts)

    def test_new_hostile_on_fresh_read_blocks_old_release_offer(self):
        snapshot = fixture(); client = Client(snapshot)
        client.combat['hostiles'] = [dict(id=90, is_hostile=True, is_dead=False, is_downed=False,
                                       current_job='AttackMelee', position=dict(x=33, z=10))]
        result = entry(snapshot, client)
        self.assertFalse(result['result']['applied']); self.assertFalse(client.posts)

    def test_foreign_queue_on_fresh_read_is_preserved(self):
        snapshot = fixture(); client = Client(snapshot); client.combat['colonists'][0]['queued_job_count'] = 1
        result = entry(snapshot, client)
        self.assertFalse(result['result']['applied']); self.assertFalse(client.posts)

    def test_current_other_patient_care_is_not_reassigned(self):
        snapshot = fixture(); client = Client(snapshot)
        client.combat['colonists'][0].update(current_job='TendPatient', current_job_target_id=4,
                                            is_drafted=False, has_care_job=True)
        result = entry(snapshot, client)
        self.assertEqual('care_actor_is_providing_other_care', result['result']['reason'])
        self.assertFalse(client.posts)

    def test_incomplete_or_changed_native_binding_is_not_a_command(self):
        snapshot = fixture(); snapshot['development']['resilience'] = Client(snapshot).context
        for change in ({'release_combat_job_id': True}, {'travel_ticks': float('nan')},
                       {'expected_current_job': 'TendPatient'}, {'medical_tend_speed': 0}):
            with self.subTest(change=change):
                modified = copy.deepcopy(snapshot)
                modified['development']['resilience']['combat_release_tends'][0].update(change)
                self.assertNotIn('tend_3_1', recovery.combat_release_tend_options(modified))


if __name__ == '__main__':
    unittest.main()

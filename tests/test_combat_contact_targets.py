import unittest
from unittest.mock import patch
import rimworld_laya as bridge
import colony_combat


class ContactTargetTests(unittest.TestCase):
    def snapshot(self):
        return {'game': {}, 'map': {'id': 0, 'enemies': 2}, 'combat': {
            'colonists': [dict(id=i, name=str(i), position={'x': x, 'z': 10},
                               distance_to_nearest_opponent=1, moving=1, health=1,
                               is_drafted=True, melee_skill=skill)
                          for i, x, skill in [(1, 10, 10), (2, 30, 3)]],
            'hostiles': [dict(id=i, position={'x': x, 'z': 10}) for i,x in [(9,11),(10,31)]]}}

    def jobs(self, snapshot):
        action = bridge.plan_action(snapshot, {'choice': 'engage_melee'})
        return [command['body'] for command in action.get('commands', [])
                if command['endpoint'] == '/api/v1/pawn/job']

    def test_each_contact_fights_its_own_attacker(self):
        self.assertEqual([(j['pawn_id'],j['target_thing_id']) for j in self.jobs(self.snapshot())],
                         [(1,9),(2,10)])

    def test_distance_summary_cannot_order_a_charge(self):
        snapshot = self.snapshot()
        snapshot['combat']['hostiles'][1]['position']['x'] = 50
        self.assertEqual([(j['pawn_id'],j['target_thing_id']) for j in self.jobs(snapshot)], [(1,9)])

    def test_repeated_contact_preserves_native_melee_job(self):
        snapshot = self.snapshot()
        for pawn,target in zip(snapshot['combat']['colonists'], (9,10)):
            pawn.update(current_job='AttackMelee', current_job_target_id=target)
        self.assertEqual(self.jobs(snapshot), [])

    def test_safe_work_choice_reaches_its_existing_noop_plan(self):
        snapshot = self.snapshot()
        snapshot['combat']['available'] = True
        answer = {'answers': {'threat_action': {'choice': 'continue_safe_colony_work', 'confidence': 1}}}
        with patch.object(bridge, 'make_questions', return_value={
                'threat_action': {'criteria': {'continue_safe_colony_work': 'Work outside exposure'}}}), \
             patch.object(bridge, 'combat_model_context', return_value={}), \
             patch.object(bridge, 'ask_combat_choice', return_value=('continue_safe_colony_work', answer)):
            decision = bridge.decide(object(), snapshot, 0)
        self.assertEqual(bridge.plan_action(snapshot, decision)['kind'], 'noop')

    def test_wounded_walker_keeps_escape_option_and_receives_route_order(self):
        snapshot = self.snapshot()
        snapshot['combat']['colonists'] = [snapshot['combat']['colonists'][0]]
        pawn = snapshot['combat']['colonists'][0]
        pawn.update(moving=.58, has_ranged_weapon=True, weapon_def='Gun_BoltActionRifle',
                    manipulation=.5, sight=1, shootable_opponent_ids=[9])
        choices = colony_combat.available_tactics(snapshot)
        self.assertIn('withdraw_and_regroup', choices)
        self.assertIn('walk slowly', choices['withdraw_and_regroup'])
        action = bridge.plan_action(snapshot, {'choice': 'withdraw_and_regroup'})
        retreat = [command['body'] for command in action['commands']
                   if command['endpoint'] == '/api/v1/combat/tactic']
        self.assertEqual(retreat[0]['tactic'], 'withdraw_and_regroup')
        self.assertEqual(retreat[0]['fighter_ids'], [1])
        pawn['moving'] = 0
        self.assertNotIn('withdraw_and_regroup', colony_combat.available_tactics(snapshot))

if __name__ == '__main__':
    unittest.main()

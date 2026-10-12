import copy
import unittest

import colony_combat as combat
import colony_events as events
import rimworld_laya as bridge


class LargeAnimalChargeTests(unittest.TestCase):
    def snapshot(self):
        return {'game': {}, 'map': {'id': 0, 'enemies': 1}, 'combat': {
            'colonists': [{'id': 1, 'name': 'Novice', 'combat_power': 30, 'health': 1,
                          'moving': 1, 'manipulation': 1, 'consciousness': 1,
                          'melee_skill': 1, 'weapon_def': 'MeleeWeapon_Knife',
                          'armor_sharp': 0, 'distance_to_nearest_opponent': 8,
                          'position': {'x': 10, 'z': 10}}],
            'hostiles': [{'id': 9, 'is_animal': True, 'kind_def': 'Bear_Grizzly',
                         'combat_power': 200, 'health': 1, 'current_job': 'AttackMelee',
                         'position': {'x': 18, 'z': 10}}]}}

    def test_novice_has_escape_but_no_charge_against_known_large_animal(self):
        choices = combat.available_tactics(self.snapshot())
        self.assertNotIn('melee_assault', choices)
        self.assertIn('withdraw_and_regroup', choices)

    def test_stale_group_and_individual_charges_emit_no_attack_orders(self):
        snapshot = self.snapshot()
        plan = bridge.plan_action(snapshot, {'choice': 'melee_assault'})
        self.assertEqual(plan['kind'], 'noop')
        commands, actors = bridge.melee_support_commands(snapshot,
            {'melee_roles': {1: 'melee_assault'}}, set(), 9)
        self.assertEqual((commands, actors), ([], set()))

    def test_distant_guns_and_caregiver_do_not_count_as_support(self):
        snapshot = self.snapshot()
        snapshot['combat']['colonists'][0].update(melee_skill=8, armor_sharp=.5)
        gun = {'id': 2, 'combat_power': 30, 'health': 1, 'moving': 1,
               'has_ranged_weapon': True, 'ranged_attack_available': True,
               'shootable_opponent_ids': []}
        snapshot['combat']['colonists'].append(gun)
        self.assertTrue(combat.unsupported_animal_charge(snapshot))
        gun.update(shootable_opponent_ids=[9], current_job='TendPatient', has_care_job=True)
        self.assertTrue(combat.unsupported_animal_charge(snapshot))

    def test_prepared_guard_with_actual_gun_cover_retains_choice(self):
        snapshot = self.snapshot()
        snapshot['combat']['colonists'][0].update(melee_skill=8, armor_sharp=.5)
        snapshot['combat']['colonists'].append({'id': 2, 'health': 1,
            'has_ranged_weapon': True, 'ranged_attack_available': True,
            'shootable_opponent_ids': [9]})
        self.assertFalse(combat.unsupported_animal_charge(snapshot))
        self.assertIn('melee_assault', combat.available_tactics(snapshot))

    def test_two_prepared_guards_retain_a_risky_choice_not_a_win(self):
        snapshot = self.snapshot()
        first = snapshot['combat']['colonists'][0]
        first.update(melee_skill=8, armor_sharp=.5)
        second = copy.deepcopy(first); second['id'] = 2
        snapshot['combat']['colonists'].append(second)
        self.assertFalse(combat.unsupported_animal_charge(snapshot))

    def test_small_or_badly_wounded_animal_is_not_the_large_animal_flag(self):
        snapshot = self.snapshot()
        enemy = snapshot['combat']['hostiles'][0]
        enemy['combat_power'] = 10
        self.assertFalse(combat.unsupported_animal_charge(snapshot))
        enemy.update(combat_power=200, health=.3)
        self.assertFalse(combat.unsupported_animal_charge(snapshot))

    def test_zero_or_unknown_clinical_capacity_does_not_make_a_prepared_guard(self):
        for value in (0, None, float('nan')):
            snapshot = self.snapshot()
            snapshot['combat']['colonists'][0].update(melee_skill=8, armor_sharp=.5, consciousness=value)
            snapshot['combat']['colonists'].append({'id': 2, 'health': 1,
                'has_ranged_weapon': True, 'ranged_attack_available': True,
                'shootable_opponent_ids': [9]})
            self.assertTrue(combat.unsupported_animal_charge(snapshot))

    def test_melee_contact_self_defense_is_preserved(self):
        snapshot = self.snapshot()
        snapshot['combat']['colonists'][0]['distance_to_nearest_opponent'] = 1
        snapshot['combat']['hostiles'][0]['position']['x'] = 11
        plan = bridge.plan_action(snapshot, {'choice': 'engage_melee'})
        self.assertTrue(any(c.get('body', {}).get('job_def') == 'AttackMelee'
                            for c in plan['commands']))

    def test_unimplemented_event_remedy_is_not_repeated_as_work(self):
        for family, name in [('power_crisis', 'power_emergency'), ('weather', 'weather_emergency'),
                             ('psychic', 'psychic_schedule_response'), ('anomaly', 'contain_anomaly'),
                             ('positive', 'use_opportunity')]:
            options = events.response_options({'family': family}, {})
            self.assertNotIn(name, options)
            self.assertIn('observe_event', options)


if __name__ == '__main__':
    unittest.main()

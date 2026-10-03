import copy
import unittest
import colony_capabilities as caps
from test_capabilities import snapshot, Client


def weapon(item, name, **kwargs):
    return dict(id=item, def_name=name, is_weapon=True, equippable=True, is_ranged=True,
                quality=2, range=25, damage=10, cooldown=1, warmup=1,
                hit_points_percent=1, position={'x': 52, 'z': 50}, **kwargs)


class LoadoutStabilityTests(unittest.TestCase):
    def setup_loadout(self):
        s = snapshot()
        a,b,c = weapon(10,'Gun_A'),weapon(11,'Gun_B'),weapon(12,'Gun_C')
        pawn = s['combat']['colonists'][0]
        pawn.update(weapon_info=a, weapon_def=a['def_name'], current_job='Wait')
        s['combat']['available_weapons'] = [b,c]
        memory = {}
        caps.prepare(s,memory)
        return s,memory,a,b,c

    def test_equipped_selection_is_noop_even_without_ground_plan(self):
        s,memory,a,b,c = self.setup_loadout()
        s['development']['capability_plans'] = {}
        client = Client()
        result = caps.execute(client,s,memory,'improve_weapon_loadout',{'weapon_pawn':'1','weapon_item':'10'})
        self.assertEqual(result['reason'],'weapon_already_equipped')
        self.assertEqual(client.calls,[])

    def test_pending_equip_cannot_be_replaced_by_another_choice(self):
        s,memory,a,b,c = self.setup_loadout()
        s['combat']['colonists'][0].update(current_job='Equip',current_job_target_id=11)
        client=Client()
        result=caps.execute(client,s,memory,'improve_weapon_loadout',{'weapon_pawn':'1','weapon_item':'12'})
        self.assertEqual(result['reason'],'weapon_equip_in_progress')
        self.assertEqual(client.calls,[])

    def test_same_snapshot_cannot_repeat_an_accepted_assignment(self):
        s,memory,a,b,c=self.setup_loadout()
        client=Client()
        self.assertTrue(caps.execute(client,s,memory,'improve_weapon_loadout',{'weapon_pawn':'1','weapon_item':'11'})['applied'])
        for item in ('11','12'):
            result=caps.execute(client,s,memory,'improve_weapon_loadout',{'weapon_pawn':'1','weapon_item':item})
            self.assertEqual(result['reason'],'weapon_assignment_pending')
        self.assertEqual(len(client.calls),1)

    def test_confirmed_assignment_survives_inventory_hand_swap_and_time(self):
        s,memory,a,b,c=self.setup_loadout()
        self.assertTrue(caps.execute(Client(),s,memory,'improve_weapon_loadout',{'weapon_pawn':'1','weapon_item':'11'})['applied'])
        pawn=s['combat']['colonists'][0]
        pawn.update(weapon_info=b,weapon_def=b['def_name'])
        s['combat']['available_weapons']=[a,c]
        s['game']['tick']+=16000
        self.assertNotIn('improve_weapon_loadout',caps.prepare(s,memory))
        s['game']['tick']+=60000
        self.assertNotIn('improve_weapon_loadout',caps.prepare(s,memory))
        s['combat']['available_weapons'].append(weapon(13,'Gun_D'))
        self.assertIn('improve_weapon_loadout',caps.prepare(s,memory))

    def test_failed_progress_retries_exact_assignment_then_missing_item_unlocks_choice(self):
        s,memory,a,b,c=self.setup_loadout()
        caps.execute(Client(),s,memory,'improve_weapon_loadout',{'weapon_pawn':'1','weapon_item':'11'})
        s['game']['tick']+=1000
        self.assertNotIn('improve_weapon_loadout',caps.prepare(s,memory))
        s['game']['tick']+=15000
        self.assertIn('improve_weapon_loadout',caps.prepare(s,memory))
        self.assertEqual(set(s['development']['capability_plans']['improve_weapon_loadout']['1']['weapons']),{'11'})
        s['combat']['available_weapons']=[c]
        self.assertIn('improve_weapon_loadout',caps.prepare(s,memory))
        self.assertEqual(set(s['development']['capability_plans']['improve_weapon_loadout']['1']['weapons']),{'12'})

    def test_lost_confirmed_weapon_can_be_recovered_and_new_threat_reopens_comparison(self):
        s,memory,a,b,c=self.setup_loadout()
        caps.execute(Client(),s,memory,'improve_weapon_loadout',{'weapon_pawn':'1','weapon_item':'11'})
        pawn=s['combat']['colonists'][0]
        pawn.update(weapon_info=b,weapon_def=b['def_name'])
        s['combat']['available_weapons']=[a,c]
        s['game']['tick']+=16000
        caps.prepare(s,memory)
        s['combat']['hostiles']=[dict(id=9,kind_def='Mech',is_mechanoid=True,position={'x':150,'z':150})]
        self.assertIn('improve_weapon_loadout',caps.prepare(s,memory))
        pawn.update(weapon_info={},weapon_def=None,has_ranged_weapon=False)
        s['combat']['available_weapons']=[a,b,c]
        self.assertIn('improve_weapon_loadout',caps.prepare(s,memory))
        self.assertTrue(caps.founder_weapon_snapshot(s)['development']['capability_plans']['improve_weapon_loadout'])

    def test_founder_arming_preserves_real_melee_weapon_but_replaces_improvised_item(self):
        s,memory,a,b,c=self.setup_loadout()
        pawn=s['combat']['colonists'][0]
        pawn.update(weapon_def='Sword',has_ranged_weapon=False,weapon_info=dict(id=14,def_name='Sword',is_ranged=False,is_weapon=True))
        caps.prepare(s,memory)
        self.assertEqual(caps.founder_weapon_snapshot(s)['development']['capability_plans']['improve_weapon_loadout'],{})
        pawn['weapon_info'].update(is_weapon=False,is_improvised=True)
        caps.prepare(s,memory)
        self.assertTrue(caps.founder_weapon_snapshot(s)['development']['capability_plans']['improve_weapon_loadout'])

    def test_another_colonist_dropping_weapon_reopens_inventory_choice(self):
        s,memory,a,b,c=self.setup_loadout()
        d=weapon(13,'Gun_D')
        s['combat']['colonists'].append(dict(id=2,weapon_info=d,is_downed=True))
        caps.prepare(s,memory)
        caps.execute(Client(),s,memory,'improve_weapon_loadout',{'weapon_pawn':'1','weapon_item':'11'})
        s['combat']['colonists'][0].update(weapon_info=b,weapon_def=b['def_name'])
        s['combat']['available_weapons']=[a,c]
        s['game']['tick']+=16000
        self.assertNotIn('improve_weapon_loadout',caps.prepare(s,memory))
        s['combat']['colonists'][1].update(is_dead=True,weapon_info={})
        s['combat']['available_weapons'].append(d)
        self.assertIn('improve_weapon_loadout',caps.prepare(s,memory))
        self.assertIn('13',s['development']['capability_plans']['improve_weapon_loadout']['1']['weapons'])

if __name__ == '__main__': unittest.main()


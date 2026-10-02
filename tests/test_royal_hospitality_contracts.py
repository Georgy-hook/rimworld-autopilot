"""Offline royalty context/order transport; source guards do not run native rooms."""
from pathlib import Path
import copy
import unittest
from unittest.mock import patch
import colony_specialists as specialists

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/RoyalHospitalityHelper.cs'


class Client:
    def __init__(self, rows):
        self.rows = rows; self.posts = []
    def get(self, endpoint, **kwargs):
        return {'royal_assignments': copy.deepcopy(self.rows)} if endpoint.endswith('/context') else {}
    def post(self, endpoint, **kwargs):
        self.posts.append((endpoint, kwargs))
        return {'applied': True, 'reason': 'native_royal_room_ownership_assigned; hospitality_outcome_unobserved'}


class RoyalHospitalityContracts(unittest.TestCase):
    def test_existing_owned_ordinary_bed_does_not_hide_royal_upgrade_option(self):
        row = {'kind': 'royal_bed', 'pawn_id': 4, 'thing_id': 55, 'room_id': 9,
               'label': 'Guest: royal bed in room 9', 'description': 'Native requirements met'}
        snap = {'map': {'id': 1}, 'game': {'tick': 50000}, 'development': {'specialists': {'royal_assignments': [row]}}}
        self.assertEqual(specialists.prepare(snap, {}), ['specialists_royal_assign'])
        with patch.object(specialists, 'ask_laya_choice', return_value=('royal_bed:4:55', {})) as choice:
            selected, _ = specialists.choose(None, {}, 'specialists_royal_assign', snap)
        self.assertEqual(selected, {'kind': 'royal_bed', 'pawn_id': 4, 'thing_id': 55})
        self.assertIn('defer', choice.call_args.args[4])
        client = Client([row])
        self.assertTrue(specialists.execute(client, snap, {}, 'specialists_royal_assign', selected)['applied'])
        self.assertEqual(client.posts[0][1]['body'], {'map_id': 1, 'kind': 'royal_bed', 'pawn_id': 4, 'thing_id': 55})
        changed = Client([])
        self.assertFalse(specialists.execute(changed, snap, {}, 'specialists_royal_assign', selected)['applied'])
        self.assertFalse(changed.posts)

    def test_native_context_includes_pending_guest_rooms_before_quest_acceptance(self):
        source = SOURCE.read_text(encoding='utf-8')
        self.assertIn('QuestPart_RequirementsToAcceptBedroom', source)
        self.assertIn('part.targetPawns', source)
        self.assertIn('part.CanAccept()', source)
        self.assertIn('RoyalTitleUtility.BedroomSatisfiesRequirements', source)
        self.assertIn('AssignedPawnsForReading.Count==0', source)
        for field in ('minimum_bedroom_area', 'minimum_bedroom_impressiveness', 'bedroom_required_things',
                      'bedroom_compatible_floor_defs', 'assigned_bed_id', 'bedroom_id', 'throne_room_id', 'qualifying_unassigned_bed_ids'):
            self.assertIn(field, source)
        self.assertIn('GetFavor(f)', source)
        self.assertIn('favor_cost=d.favorCost', source)
        self.assertIn('bedroom_required_bed_defs=BuildingDefs(bedroom,typeof(Building_Bed))', source)
        self.assertIn('p.royalty.CanRequireBedroom() && bedroom.Count>0', source)
        self.assertIn('p.royalty.CanRequireThroneroom() && throne.Count>0', source)
        self.assertNotIn('|| p.royalty.MostSeniorTitle!=null', source)

    def test_native_assignment_rechecks_room_and_uses_normal_ownership_component(self):
        source = SOURCE.read_text(encoding='utf-8')
        self.assertIn('Options(map).FirstOrDefault', source)
        self.assertIn('assign.CanAssignTo(pawn).Accepted', source)
        self.assertIn('assign.AssignedPawnsForReading.Any(p=>p!=pawn)', source)
        self.assertIn('Bedroom(pawn).All(r=>r.MetOrDisabled(room,pawn))', source)
        self.assertIn('RoomRoleWorker_ThroneRoom.Validate(room)', source)
        self.assertIn('TryAssignPawn(pawn)', source)
        self.assertNotIn('ClaimThrone(', source)
        self.assertNotIn('SetFaction(', source)


if __name__ == '__main__':
    unittest.main()

"""Offline source guards; these do not execute RimWorld jobs or simulate survival."""
from pathlib import Path
import re
import unittest

HELPERS = Path(__file__).resolve().parents[1] / 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers'


class CareCombatSourceContracts(unittest.TestCase):
    def test_routine_orders_share_childcare_and_deathrest_protection(self):
        combat = (HELPERS / 'CombatNativeHelper.cs').read_text(encoding='utf-8')
        for job in ('Deathrest', 'BottleFeedBaby', 'BringBabyToSafetyUnforced', 'PrisonerInterrogateIdentity'):
            self.assertIn('"' + job + '"', combat)
        for helper in ('ResilienceAutomationHelper.cs', 'ResilienceDiagnosisHelper.cs', 'SocietyAutomationHelper.cs', 'SpecialistAutomationHelper.cs'):
            self.assertIn('!CombatNativeHelper.HasCareJob(p)' if helper in ('ResilienceAutomationHelper.cs', 'ResilienceDiagnosisHelper.cs') else 'CombatNativeHelper.HasCareJob(p)',
                          (HELPERS / helper).read_text(encoding='utf-8'), helper)

    def test_cleaning_and_prevention_do_not_truncate_before_feasibility(self):
        source = (HELPERS / 'ResilienceAutomationHelper.cs').read_text(encoding='utf-8')
        candidates = source[source.index('foreach (Pawn worker in patients.Where(p => Idle(p)'):source.index('foreach (Pawn patient in patients.Where(p => p.IsColonistPlayerControlled')]
        self.assertNotRegex(candidates, r'\.Take\(')
        self.assertIn('NativeScanner(worker, target', candidates)
        self.assertIn('Preventible(worker, drug)', candidates)

    def test_explicit_combat_target_checked_before_drafting(self):
        source = (HELPERS / 'CombatTacticsHelper.cs').read_text(encoding='utf-8')
        target_lookup = source[source.index('Pawn target = request.TargetPawnId'):source.index('var result = new CombatTacticResponseDto')]
        self.assertRegex(target_lookup, r'FirstOrDefault\([^;]+!p\.Dead && !p\.Downed && p\.HostileTo\(Faction\.OfPlayer\)')
        self.assertIn('no fighters drafted', target_lookup)

    def test_stand_down_rechecks_pawns_and_active_structures(self):
        source = (HELPERS / 'CombatTacticsHelper.cs').read_text(encoding='utf-8')
        guard = source[source.index('if (tactic == "stand_down")'):source.index('List<Pawn> fighters')]
        self.assertLess(guard.index('Hostiles remain'), guard.index('pawn.drafter.Drafted = false'))
        self.assertIn('!p.Dead && !p.Downed && p.HostileTo(Faction.OfPlayer)', guard)
        self.assertIn('Any(CombatNativeHelper.ActiveStructure)', guard)

    def test_exact_tending_is_idempotent_before_other_care_rejection(self):
        source = (HELPERS.parent / 'Services/Pawns/PawnJobService/PawnJobService.cs').read_text(encoding='utf-8')
        tend = source[source.index('public ApiResult AssignTendJob'):source.index('public ApiResult AssignBedRest')]
        exact = tend[tend.index('if (!reassign && doctor.CurJobDef'):tend.index('if (reassign)')]
        self.assertIn('doctor.CurJob.targetA.Thing == patient', exact)
        self.assertIn('return ApiResult.Ok()', exact)
        self.assertNotIn('AssignTendJob(doctor, patient)', exact)
        self.assertLess(tend.index('if (!reassign && doctor.CurJobDef'), tend.index('already providing patient care'))

    def test_care_escape_checks_binding_and_route_before_replacing_care(self):
        source = (HELPERS / 'CombatTacticsHelper.cs').read_text(encoding='utf-8')
        escape = source[source.index('private static ApiResult<CombatTacticResponseDto> ApplyCareRetreat'):source.index('private static bool IsRanged')]
        for evidence in ('request.FighterIds.Count != 1', 'request.ExpectedCurrentJob', 'request.ExpectedCarePatientId',
                         'actor.carryTracker?.CarriedThing is Pawn', 'ImmediateCareThreat', 'TryFindCoveredRetreatCell', 'TryFindTrapFreeCell'):
            self.assertLess(escape.index(evidence), escape.index('TryTakeOrderedJob'), evidence)
        self.assertNotIn('Drafted = true', escape)
        self.assertNotIn('StopAll', escape)

    def test_care_routes_include_active_turret_reach(self):
        source = (HELPERS / 'ResilienceAutomationHelper.cs').read_text(encoding='utf-8')
        guard = source[source.index('private static bool Safe('):source.index('private static WorkGiver_Scanner NativeScanner')]
        self.assertIn('Where(CombatNativeHelper.ActiveStructure)', guard)
        self.assertIn('AttackVerb?.EffectiveRange', guard)
        self.assertIn('ex*ex+ez*ez <= radius*radius', guard)

    def test_native_care_escape_ownership_checks_the_exact_job_instance(self):
        source = (HELPERS / 'CombatNativeHelper.cs').read_text(encoding='utf-8')
        owner = source[source.index('public static bool HasCareRetreat'):source.index('public static List<int> CareRetreatPawnIds')]
        self.assertIn('record.Key == pawn', owner)
        self.assertIn('record.Value == pawn.CurJob', owner)
        self.assertIn('Find.Maps.Contains(pawn.Map)', owner)
        self.assertIn('!pawn.Dead && !pawn.Downed', owner)
        service = (HELPERS.parent / 'Services/Pawns/CombatService/CombatService.cs').read_text(encoding='utf-8')
        self.assertIn('CareRetreatPawnIds = CombatNativeHelper.CareRetreatPawnIds(map)', service)

    def test_unknown_tactic_cannot_fall_through_to_an_attack(self):
        source = (HELPERS / 'CombatTacticsHelper.cs').read_text(encoding='utf-8')
        self.assertLess(source.index('Unknown combat tactic'), source.index('List<Pawn> fighters'))
        self.assertIn('!PositioningTactics.Contains(tactic)', source)

    def test_suppression_and_utility_interactions_share_checked_route(self):
        for helper in ('SpecialistAutomationHelper.cs', 'AffordanceAutomationHelper.cs'):
            self.assertIn('ResilienceAutomationHelper.RoutineRouteSafe(p,', (HELPERS / helper).read_text(encoding='utf-8'))
        specialist = (HELPERS / 'SpecialistAutomationHelper.cs').read_text(encoding='utf-8')
        protected = specialist[specialist.index('private static bool Protected'):specialist.index('private static List<string> Modes')]
        self.assertIn('h.Visible', protected)
        self.assertIn('h.TendableNow()', protected)


if __name__ == '__main__':
    unittest.main()

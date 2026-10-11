using System.Collections.Generic;

namespace RIMAPI.Models
{
    public class CombatNativeOptionDto
    {
        public string Tactic { get; set; }
        public int FighterId { get; set; }
        public int TargetId { get; set; }
        public int DefenseBuildingId { get; set; }
        public string ExpectedCurrentJob { get; set; }
        public int? ExpectedCarePatientId { get; set; }
        public string Label { get; set; }
        public Dictionary<string,string> Effects { get; set; }
    }
    public class PsycastDto
    {
        public string DefName { get; set; }
        public string Label { get; set; }
        public string Description { get; set; }
        public int Level { get; set; }
        public bool IsPsycast { get; set; }
        public bool Hostile { get; set; }
        public bool TargetRequired { get; set; }
        public bool CanCast { get; set; }
        public string DisabledReason { get; set; }
        public float Range { get; set; }
        public float EffectRadius { get; set; }
        public float PsyfocusCost { get; set; }
        public float EntropyGain { get; set; }
        public int CooldownTicksRemaining { get; set; }
        public int RemainingCharges { get; set; }
        public string Mod { get; set; }
    }

    public class CombatDefenseDto
    {
        public int Id { get; set; }
        public string DefName { get; set; }
        public string Label { get; set; }
        public string Kind { get; set; }
        public PositionDto Position { get; set; }
        public bool Powered { get; set; }
        public float HitPointsPercent { get; set; }
    }

    public class CombatTacticRequestDto
    {
        public int MapId { get; set; }
        public string Tactic { get; set; }
        public List<int> FighterIds { get; set; } = new List<int>();
        public int? TargetPawnId { get; set; }
        public int? DefenseBuildingId { get; set; }
        public int? PsycasterPawnId { get; set; }
        public string AbilityDefName { get; set; }
        public int? AbilityTargetPawnId { get; set; }
        public PositionDto AbilityTargetPosition { get; set; }
        public string ExpectedCurrentJob { get; set; }
        public int? ExpectedCarePatientId { get; set; }
    }

    public class CombatTacticResponseDto
    {
        public string Tactic { get; set; }
        public List<int> DraftedPawnIds { get; set; } = new List<int>();
        public List<int> PositionedPawnIds { get; set; } = new List<int>();
        public List<int> AttackingPawnIds { get; set; } = new List<int>();
        public bool PsycastQueued { get; set; }
        public string Psycast { get; set; }
        public int? TargetPawnId { get; set; }
        public List<string> Notes { get; set; } = new List<string>();
    }
}

using System.Collections.Generic;

namespace RIMAPI.Models
{
    public class CombatStateDto
    {
        public int MapId { get; set; }
        public List<object> HostileBuildings { get; set; } = new List<object>();
        public List<CombatNativeOptionDto> NativeOptions { get; set; } = new List<CombatNativeOptionDto>();
        public int GameTick { get; set; }
        public List<CombatPawnDto> Colonists { get; set; } = new List<CombatPawnDto>();
        public List<CombatPawnDto> Hostiles { get; set; } = new List<CombatPawnDto>();
        public List<CombatPawnDto> Prisoners { get; set; } = new List<CombatPawnDto>();
        public List<CombatPawnDto> NeutralDowned { get; set; } = new List<CombatPawnDto>();
        public List<CombatWeaponDto> AvailableWeapons { get; set; } = new List<CombatWeaponDto>();
        public List<CombatDefenseDto> Defenses { get; set; } = new List<CombatDefenseDto>();
        public List<AnimalDto> ColonyAnimals { get; set; } = new List<AnimalDto>();
    }

    public class CombatPawnDto
    {
        public int Id { get; set; }
        public string Name { get; set; }
        public string KindDef { get; set; }
        public string Faction { get; set; }
        public bool IsColonist { get; set; }
        public bool IsHostile { get; set; }
        public bool IsDrafted { get; set; }
        public bool IsDowned { get; set; }
        public bool IsInMentalState { get; set; }
        public bool IsDead { get; set; }
        public float Health { get; set; }
        public PositionDto Position { get; set; }
        public int ShootingSkill { get; set; }
        public int MeleeSkill { get; set; }
        public string WeaponDef { get; set; }
        public string WeaponLabel { get; set; }
        public CombatWeaponDto WeaponInfo { get; set; }
        public bool HasShieldBelt { get; set; }
        public bool HasRangedWeapon { get; set; }
        public string CurrentJob { get; set; }
        public int? CurrentJobTargetId { get; set; }
        public int? CurrentJobTargetIdB { get; set; }
        public PositionDto CurrentJobTargetPosition { get; set; }
        public bool CareAtBedside { get; set; }
        public int? CareTargetId { get; set; }
        public PositionDto CareTargetPosition { get; set; }
        public bool RangedAttackAvailable { get; set; }
        public bool IsAnimal { get; set; }
        public string LordJobType { get; set; }
        public string LordToilName { get; set; }
        public float DistanceToNearestOpponent { get; set; }
        public string Gender { get; set; }
        public int BiologicalAge { get; set; }
        public float BleedingRate { get; set; }
        public bool TendableNow { get; set; }
        public bool SelfTendAllowed { get; set; }
        public float Consciousness { get; set; }
        public float Moving { get; set; }
        public float Manipulation { get; set; }
        public float Sight { get; set; }
        public float Pain { get; set; }
        public float MarketValue { get; set; }
        public float CombatPower { get; set; }
        public float WeaponRange { get; set; }
        public List<int> ShootableOpponentIds { get; set; } = new List<int>();
        public float ArmorSharp { get; set; }
        public bool CarryingPlayerPawn { get; set; }
        public string CarriedPawnFaction { get; set; }
        public bool KidnappingIntent { get; set; }
        public int? CarryingPawnId { get; set; }
        public float Psyfocus { get; set; }
        public float TargetPsyfocus { get; set; }
        public float NeuralHeat { get; set; }
        public float NeuralHeatLimit { get; set; }
        public float PsychicSensitivity { get; set; }
        public int PsylinkLevel { get; set; }
        public List<PsycastDto> Psycasts { get; set; } = new List<PsycastDto>();
        public int SocialSkill { get; set; }
        public int MedicineSkill { get; set; }
        public int ConstructionSkill { get; set; }
        public int AnimalsSkill { get; set; }
        public int IntellectualSkill { get; set; }
        public int CookingSkill { get; set; }
        public bool Recruitable { get; set; }
        public bool FactionPermanentEnemy { get; set; }
        public bool FactionCanGiveGoodwill { get; set; }
        public int FactionGoodwill { get; set; }
        public List<string> Traits { get; set; } = new List<string>();
        public List<string> TopSkills { get; set; } = new List<string>();
        public List<string> HealthConditions { get; set; } = new List<string>();
    }

    public class CombatWeaponDto
    {
        public int Id { get; set; }
        public string DefName { get; set; }
        public string Label { get; set; }
        public bool IsRanged { get; set; }
        public bool? IsWeapon { get; set; }
        public bool? IsImprovised { get; set; }
        public bool IsForbidden { get; set; }
        public float MarketValue { get; set; }
        public PositionDto Position { get; set; }
        public float Range { get; set; }
        public float MinRange { get; set; }
        public float Damage { get; set; }
        public string DamageDef { get; set; }
        public float ArmorPenetration { get; set; }
        public int BurstShots { get; set; }
        public float Warmup { get; set; }
        public float Cooldown { get; set; }
        public float AccuracyTouch { get; set; }
        public float AccuracyShort { get; set; }
        public float AccuracyMedium { get; set; }
        public float AccuracyLong { get; set; }
        public float MeleeDps { get; set; }
        public int? Quality { get; set; }
        public int? BiocodedPawnId { get; set; }
        public bool Equippable { get; set; }
        public List<int> CompatiblePawnIds { get; set; }
        public bool Explosive { get; set; }
        public bool Incendiary { get; set; }
        public bool Emp { get; set; }
        public bool SingleUse { get; set; }
        public string Description { get; set; }
        public float HitPointsPercent { get; set; }
    }
}

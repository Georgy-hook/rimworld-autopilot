using System;
using System.Collections.Generic;
using System.Linq;
using RIMAPI.Core;
using RIMAPI.Helpers;
using RIMAPI.Models;
using RimWorld;
using Verse;
using Verse.AI;
using Verse.AI.Group;

namespace RIMAPI.Services
{
    public class CombatService : ICombatService
    {
        public ApiResult<CombatStateDto> GetCombatState(int mapId)
        {
            try
            {
                var map = MapHelper.GetMapByID(mapId);
                if (map == null)
                {
                    return ApiResult<CombatStateDto>.Fail($"Map not found: {mapId}");
                }

                var colonists = map.mapPawns.FreeColonistsSpawned
                    .Where(p => p != null && !p.Dead)
                    .ToList();
                var hostiles = map.mapPawns.AllPawnsSpawned
                    .Where(p => p != null && !p.Dead && p.HostileTo(Faction.OfPlayer)
                        && IsActionableHostile(p, colonists, map))
                    .ToList();
                var prisoners = map.mapPawns.PrisonersOfColony
                    .Where(p => p != null && !p.Dead)
                    .ToList();
                var neutralDowned = map.mapPawns.AllPawnsSpawned
                    .Where(p => p != null && !p.Dead && p.Downed && p.RaceProps?.Humanlike == true
                        && !p.IsColonist && !p.IsPrisonerOfColony
                        && !p.HostileTo(Faction.OfPlayer))
                    .ToList();
                var weapons = map.listerThings.AllThings
                    .Where(t => t != null && t.Spawned && !t.Destroyed && t.def != null
                        && t.def.IsWeapon)
                    .Select(t => WeaponAutomationHelper.Describe(t.def, t))
                    .OrderByDescending(w => w.MarketValue)
                    .ToList();
                foreach (var weapon in weapons)
                {
                    Thing item = MapHelper.GetThingOnMapById(mapId, weapon.Id);
                    weapon.CompatiblePawnIds = colonists.Where(p => EquipmentUtility.CanEquip(item, p, out string reason))
                        .Select(p => p.thingIDNumber).ToList();
                }

                var defenses = map.listerBuildings.allBuildingsColonist
                    .Where(b => b != null && !b.Destroyed && b.def != null && IsDefensiveBuilding(b))
                    .Select(b => new CombatDefenseDto
                    {
                        Id = b.thingIDNumber,
                        DefName = b.def.defName,
                        Label = b.LabelCap,
                        Kind = DefenseKind(b),
                        Position = new PositionDto { X = b.Position.x, Y = b.Position.y, Z = b.Position.z },
                        Powered = b.TryGetComp<CompPowerTrader>()?.PowerOn ?? true,
                        HitPointsPercent = b.MaxHitPoints > 0 ? (float)b.HitPoints / b.MaxHitPoints : 1f,
                    })
                    .ToList();

                var result = new CombatStateDto
                {
                    MapId = map.uniqueID,
                    NativeOptions = CombatNativeHelper.Options(map),
                    HostileBuildings = map.listerBuildings.allBuildingsNonColonist.Where(b=>!b.Destroyed && b.HostileTo(Faction.OfPlayer) && !b.Position.Fogged(map)).Select(b=>(object)new{id=b.thingIDNumber,name=b.LabelShort,kind_def=b.def.defName,is_building=true,is_turret=b is Building_Turret,active_threat=CombatNativeHelper.ActiveStructure(b),dormant=!(b.TryGetComp<CompCanBeDormant>()?.Awake ?? true),position=new PositionDto{X=b.Position.x,Y=b.Position.y,Z=b.Position.z},powered=b.TryGetComp<CompPowerTrader>()?.PowerOn ?? true,weapon_range=(b as Building_Turret)?.AttackVerb?.EffectiveRange ?? 0f,hit_points_percent=(float)b.HitPoints/b.MaxHitPoints}).ToList(),
                    GameTick = Find.TickManager?.TicksGame ?? 0,
                    Colonists = colonists.Select(p => ToCombatPawn(p, false, hostiles)).ToList(),
                    Hostiles = hostiles.Select(p => ToCombatPawn(p, true, colonists)).ToList(),
                    Prisoners = prisoners.Select(p => ToCombatPawn(p, false, colonists)).ToList(),
                    NeutralDowned = neutralDowned.Select(p => ToCombatPawn(p, false, colonists)).ToList(),
                    AvailableWeapons = weapons,
                    Defenses = defenses,
                    ColonyAnimals = MapHelper.GetMapAnimals(mapId).Where(a => a.IsColonyAnimal && !a.Dead).ToList(),
                };
                return ApiResult<CombatStateDto>.Ok(result);
            }
            catch (Exception ex)
            {
                LogApi.Error($"Combat state error: {ex}");
                return ApiResult<CombatStateDto>.Fail(ex.Message);
            }
        }

        private static bool IsActionableHostile(Pawn pawn, List<Pawn> colonists, Map map)
        {
            string job = pawn.CurJobDef?.defName?.ToLowerInvariant() ?? "";
            bool attacking = job.Contains("attack") || job.Contains("breach") || job.Contains("sap")
                || job.Contains("kidnap") || job.Contains("steal") || job == "goto";
            if (attacking || CombatNativeHelper.Kidnapper(pawn))
                return true;

            string lordJob = pawn.GetLord()?.LordJob?.GetType().Name ?? "";
            bool passiveHive = lordJob.Contains("DefendAndExpandHive");
            if (passiveHive && (!colonists.Any()
                || colonists.Min(c => c.Position.DistanceToSquared(pawn.Position)) > 45 * 45))
                return false;
            if (pawn.Position.Fogged(map))
                return false;
            return colonists.Any(c => c.CanReach(pawn, PathEndMode.Touch, Danger.Deadly));
        }

        private static CombatPawnDto ToCombatPawn(Pawn pawn, bool hostile, List<Pawn> opponents)
        {
            var primary = pawn.equipment?.Primary;
            var shooting = pawn.skills?.GetSkill(SkillDefOf.Shooting);
            var melee = pawn.skills?.GetSkill(SkillDefOf.Melee);
            var faction = pawn.Faction;
            var entropy = pawn.psychicEntropy;
            var distance = 0f;
            if (opponents != null && opponents.Count > 0)
            {
                distance = opponents.Min(other => (float)Math.Sqrt(
                    pawn.Position.DistanceToSquared(other.Position)));
            }

            return new CombatPawnDto
            {
                Id = pawn.thingIDNumber,
                Name = pawn.Name?.ToStringShort ?? pawn.LabelShortCap,
                KindDef = pawn.kindDef?.defName,
                Faction = pawn.Faction?.def?.defName,
                IsColonist = pawn.IsColonist,
                IsHostile = hostile,
                IsDrafted = pawn.drafter?.Drafted ?? false,
                IsDowned = pawn.Downed,
                IsInMentalState = pawn.InMentalState,
                IsDead = pawn.Dead,
                Health = pawn.health?.summaryHealth?.SummaryHealthPercent ?? 0f,
                Position = new PositionDto
                {
                    X = pawn.Position.x,
                    Y = pawn.Position.y,
                    Z = pawn.Position.z,
                },
                ShootingSkill = shooting?.Level ?? 0,
                MeleeSkill = melee?.Level ?? 0,
                WeaponDef = primary?.def?.defName,
                WeaponInfo = primary == null ? null : WeaponAutomationHelper.Describe(primary.def, primary),
                HasShieldBelt = pawn.apparel?.WornApparel.Any(a => a.TryGetComp<CompShield>() != null) ?? false,
                WeaponLabel = primary?.LabelShortCap,
                HasRangedWeapon = primary?.def?.IsRangedWeapon ?? false,
                CurrentJob = pawn.CurJobDef?.defName,
                CurrentJobTargetId = pawn.CurJob?.targetA.Thing?.thingIDNumber,
                CurrentJobTargetIdB = pawn.CurJob?.targetB.Thing?.thingIDNumber,
                CurrentJobTargetPosition = pawn.CurJob?.targetA.Thing is Thing jobTarget && jobTarget.Spawned
                    ? new PositionDto { X = jobTarget.Position.x, Y = jobTarget.Position.y, Z = jobTarget.Position.z } : null,
                CareAtBedside = CombatNativeHelper.CareAtBedside(pawn),
                CareTargetId = CombatNativeHelper.CareTarget(pawn)?.thingIDNumber,
                CareTargetPosition = CombatNativeHelper.CareTarget(pawn) is Thing careTarget && careTarget.Spawned
                    ? new PositionDto { X = careTarget.Position.x, Y = careTarget.Position.y, Z = careTarget.Position.z } : null,
                RangedAttackAvailable = primary?.def?.IsRangedWeapon == true
                    && primary.TryGetComp<CompEquippable>()?.PrimaryVerb?.Available() == true
                    && !pawn.WorkTagIsDisabled(WorkTags.Violent),
                IsAnimal = pawn.RaceProps.Animal,
                LordJobType = pawn.GetLord()?.LordJob?.GetType().Name,
                LordToilName = pawn.GetLord()?.CurLordToil?.GetType().Name,
                DistanceToNearestOpponent = distance,
                Gender = pawn.gender.ToString(),
                BiologicalAge = pawn.ageTracker?.AgeBiologicalYears ?? 0,
                BleedingRate = pawn.health?.hediffSet?.BleedRateTotal ?? 0f,
                TendableNow = pawn.health?.hediffSet?.hediffs?.Any(h => h.TendableNow()) ?? false,
                SelfTendAllowed = pawn.playerSettings?.selfTend ?? false,
                Consciousness = pawn.health?.capacities?.GetLevel(PawnCapacityDefOf.Consciousness) ?? 0f,
                Moving = pawn.health?.capacities?.GetLevel(PawnCapacityDefOf.Moving) ?? 0f,
                Manipulation = pawn.health?.capacities?.GetLevel(PawnCapacityDefOf.Manipulation) ?? 0f,
                Sight = pawn.health?.capacities?.GetLevel(PawnCapacityDefOf.Sight) ?? 0f,
                Pain = pawn.health?.hediffSet?.PainTotal ?? 0f,
                MarketValue = pawn.MarketValue,
                CombatPower = pawn.kindDef?.combatPower ?? 0f,
                WeaponRange = primary?.def?.Verbs?.FirstOrDefault()?.range ?? 0f,
                ShootableOpponentIds = primary?.def?.IsRangedWeapon == true
                    ? (opponents ?? new List<Pawn>())
                        .Where(other => !other.Dead && !other.Downed
                            && primary.TryGetComp<CompEquippable>()?.PrimaryVerb?.CanHitTargetFrom(pawn.Position, other) == true)
                        .Select(other => other.thingIDNumber).ToList()
                    : new List<int>(),
                ArmorSharp = pawn.GetStatValue(StatDefOf.ArmorRating_Sharp),
                CarryingPlayerPawn = pawn.carryTracker?.CarriedThing is Pawn victim && victim.Faction==Faction.OfPlayer,
                CarriedPawnFaction = (pawn.carryTracker?.CarriedThing as Pawn)?.Faction?.def?.defName,
                KidnappingIntent = CombatNativeHelper.Kidnapper(pawn),
                CarryingPawnId = pawn.carryTracker?.CarriedThing is Pawn carried ? (int?)carried.thingIDNumber : null,
                Psyfocus = entropy?.CurrentPsyfocus ?? 0f,
                TargetPsyfocus = entropy?.TargetPsyfocus ?? 0f,
                NeuralHeat = entropy?.EntropyValue ?? 0f,
                NeuralHeatLimit = entropy?.MaxEntropy ?? 0f,
                PsychicSensitivity = entropy?.PsychicSensitivity ?? 0f,
                PsylinkLevel = entropy?.Psylink?.level ?? 0,
                Psycasts = PsychicAutomationHelper.GetPsycasts(pawn),
                SocialSkill = pawn.skills?.GetSkill(SkillDefOf.Social)?.Level ?? 0,
                MedicineSkill = pawn.skills?.GetSkill(SkillDefOf.Medicine)?.Level ?? 0,
                ConstructionSkill = pawn.skills?.GetSkill(SkillDefOf.Construction)?.Level ?? 0,
                AnimalsSkill = pawn.skills?.GetSkill(SkillDefOf.Animals)?.Level ?? 0,
                IntellectualSkill = pawn.skills?.GetSkill(SkillDefOf.Intellectual)?.Level ?? 0,
                CookingSkill = pawn.skills?.GetSkill(SkillDefOf.Cooking)?.Level ?? 0,
                Recruitable = !pawn.IsPrisoner || (pawn.guest?.Recruitable ?? true),
                FactionPermanentEnemy = faction?.def?.permanentEnemy ?? false,
                FactionCanGiveGoodwill = faction != null && faction != Faction.OfPlayer && faction.CanEverGiveGoodwillRewards,
                FactionGoodwill = faction != null && faction != Faction.OfPlayer ? faction.PlayerGoodwill : 0,
                Traits = pawn.story?.traits?.allTraits?.Select(t => t.LabelCap).Take(8).ToList() ?? new List<string>(),
                TopSkills = pawn.skills?.skills?.OrderByDescending(s => s.Level)
                    .Take(5).Select(s => $"{s.def.label}:{s.Level}").ToList() ?? new List<string>(),
                HealthConditions = pawn.health?.hediffSet?.hediffs?
                    .Where(h => h.Visible)
                    .Select(h => $"{h.def.defName}:{h.Part?.def?.defName ?? "whole body"}")
                    .Take(12).ToList() ?? new List<string>(),
            };
        }

        private static bool IsDefensiveBuilding(Building building)
        {
            string text = (building.def.defName + " " + building.Label).ToLowerInvariant();
            return building is Building_Trap || building is Building_Turret || building is Building_Door
                || text.Contains("wall") || text.Contains("barricade") || text.Contains("sandbag")
                || text.Contains("mortar") || text.Contains("firefoam") || text.Contains("shield")
                || text.Contains("shelf");
        }

        private static string DefenseKind(Building building)
        {
            string text = (building.def.defName + " " + building.Label).ToLowerInvariant();
            if (building is Building_Trap) return "trap";
            if (text.Contains("mortar")) return "mortar";
            if (building is Building_Turret) return "turret";
            if (building is Building_Door) return "door";
            if (text.Contains("firefoam")) return "firefoam";
            if (text.Contains("shield")) return "shield";
            if (text.Contains("barricade") || text.Contains("sandbag")) return "barricade";
            if (text.Contains("wall")) return "wall";
            if (text.Contains("shelf")) return "cover";
            return "defense";
        }
    }
}

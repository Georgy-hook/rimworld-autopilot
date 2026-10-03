using System;
using System.Collections.Generic;
using System.Linq;
using RIMAPI.Core;
using RIMAPI.Models;
using RimWorld;
using Verse;

namespace RIMAPI.Helpers
{
    public static class WeaponAutomationHelper
    {
        private static float Stat(ThingDef def, Thing thing, string name, float fallback = 0)
        {
            var stat = DefDatabase<StatDef>.GetNamedSilentFail(name);
            return stat == null ? fallback : thing == null ? def.GetStatValueAbstract(stat) : thing.GetStatValue(stat);
        }
        public static CombatWeaponDto Describe(ThingDef def, Thing thing = null)
        {
            var verb = def.Verbs?.FirstOrDefault(v => v.isPrimary) ?? def.Verbs?.FirstOrDefault();
            var projectile = verb?.defaultProjectile?.projectile;
            string damageDef = projectile?.damageDef?.defName;
            return new CombatWeaponDto {
                Id = thing?.thingIDNumber ?? 0, DefName = def.defName, Label = thing?.LabelShortCap ?? def.label,
                Description = def.description, IsRanged = def.IsRangedWeapon,
                IsWeapon = def.IsWeapon,
                // Native IsWeapon also includes resources with melee tools.
                // Category/tags distinguish improvised items without changing
                // the general catalog or excluding modded tagged weapons.
                IsImprovised = def.IsWeapon && !def.IsRangedWeapon
                    && !def.IsWithinCategory(ThingCategoryDefOf.Weapons) && def.weaponTags.NullOrEmpty(),
                Equippable = def.equipmentType == EquipmentType.Primary,
                IsForbidden = thing?.IsForbidden(Faction.OfPlayer) ?? false,
                MarketValue = thing?.MarketValue ?? def.BaseMarketValue,
                Position = thing == null ? null : new PositionDto { X = thing.Position.x, Y = 0, Z = thing.Position.z },
                Range = verb?.range ?? 0, MinRange = verb?.minRange ?? 0,
                Damage = projectile == null ? 0 : thing == null ? projectile.GetDamageAmount(def, null) : projectile.GetDamageAmount(thing),
                DamageDef = damageDef, ArmorPenetration = projectile?.GetArmorPenetration(thing) ?? 0,
                BurstShots = verb?.burstShotCount ?? 1, Warmup = verb?.warmupTime ?? 0,
                Cooldown = Stat(def, thing, "RangedWeapon_Cooldown", 1),
                AccuracyTouch = Stat(def, thing, "AccuracyTouch"), AccuracyShort = Stat(def, thing, "AccuracyShort"),
                AccuracyMedium = Stat(def, thing, "AccuracyMedium"), AccuracyLong = Stat(def, thing, "AccuracyLong"),
                MeleeDps = Stat(def, thing, "MeleeWeapon_AverageDPS"),
                Quality = thing?.TryGetComp<CompQuality>() is CompQuality quality ? (int?)quality.Quality : null,
                BiocodedPawnId = thing?.TryGetComp<CompBiocodable>()?.CodedPawn?.thingIDNumber,
                Explosive = projectile?.explosionRadius > 0,
                Incendiary = damageDef == "Flame" || damageDef == "Burn",
                Emp = damageDef == "EMP", SingleUse = def.Verbs?.Any(v => v.verbClass?.Name.Contains("OneUse") == true) == true,
                HitPointsPercent = thing == null || thing.MaxHitPoints <= 0 ? 1 : (float)thing.HitPoints / thing.MaxHitPoints
            };
        }
        public static ApiResult<List<CombatWeaponDto>> Catalog()
        {
            try { return ApiResult<List<CombatWeaponDto>>.Ok(DefDatabase<ThingDef>.AllDefsListForReading.Where(d => d.IsWeapon).Select(d => Describe(d)).ToList()); }
            catch (Exception ex) { return ApiResult<List<CombatWeaponDto>>.Fail(ex.ToString()); }
        }
        public static string Summary(Thing weapon)
        {
            if (weapon?.def == null) return "";
            var d = Describe(weapon.def, weapon);
            return $"{d.Label}; quality {d.Quality}; range {d.MinRange}..{d.Range}; damage {d.Damage} {d.DamageDef}; burst {d.BurstShots}; AP {d.ArmorPenetration}; accuracy short/medium/long {d.AccuracyShort}/{d.AccuracyMedium}/{d.AccuracyLong}; warmup/cooldown {d.Warmup}/{d.Cooldown}; melee DPS {d.MeleeDps}; EMP {d.Emp}, explosive {d.Explosive}, fire {d.Incendiary}, single use {d.SingleUse}; biocoded pawn {d.BiocodedPawnId}";
        }
    }
}

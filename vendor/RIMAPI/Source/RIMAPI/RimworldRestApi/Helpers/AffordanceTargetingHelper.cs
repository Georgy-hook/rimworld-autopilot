using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.CompilerServices;
using HarmonyLib;
using RimWorld;
using Verse;
using RIMAPI.Core;

namespace RIMAPI.Helpers
{
    public static class AffordanceTargetingHelper
    {
        private static object SessionObject(Targeter t) => (object)t?.targetingSource
            ?? (t == null ? null : Traverse.Create(t).Field("action").GetValue<Action<LocalTargetInfo>>());
        private static int SessionId(Targeter t) => SessionObject(t) is object source ? RuntimeHelpers.GetHashCode(source) : 0;
        private static bool Valid(Targeter t, Map map, LocalTargetInfo target)
        {
            if (t == null || !t.IsTargeting || !target.IsValid || !target.Cell.InBounds(map) || target.Cell.Fogged(map)) return false;
            var source=t.targetingSource;
            var parameters=source?.targetParams ?? Traverse.Create(t).Field("targetParams").GetValue<TargetingParameters>();
            if (parameters == null || !parameters.CanTarget(target.ToTargetInfo(map),source)) return false;
            if (source != null)
            {
                if (source.Caster?.MapHeld != map || source.Caster.Destroyed || !source.ValidateTarget(target,false)) return false;
                if (source.Caster is Pawn actor && !AffordanceAutomationHelper.Eligible(actor)) return false;
                if (source is CompAbilityEffect_WithDest dest && (dest.SelectedTargetInvalidated() || !dest.CanPlaceSelectedTargetAt(target))) return false;
                if (source is Verb_CastAbility cast && !AffordanceAutomationHelper.CanUse(cast.ability,target)) return false;
                return source.CanHitTarget(target);
            }
            var validator=Traverse.Create(t).Field("targetValidator").GetValue<Func<LocalTargetInfo,bool>>();
            return validator == null || validator(target);
        }
        private static IEnumerable<LocalTargetInfo> Candidates(Map map)
        {
            foreach (Thing thing in map.listerThings.AllThings.Where(t => t.Spawned && t.def.category != ThingCategory.Mote
                && (t is Pawn || t is Building || t is Fire || t.def.category == ThingCategory.Item)))
                yield return thing;
            var cells=new HashSet<IntVec3>();
            var anchors=map.mapPawns.AllPawnsSpawned.Select(p => p.Position)
                .Concat(map.listerBuildings.allBuildingsColonist.Select(b => b.Position)).Append(map.Center);
            foreach (var anchor in anchors)
            {
                cells.Add(anchor);
                foreach (var radius in new[] { 2, 5, 10, 20 })
                    foreach (var direction in GenAdj.AdjacentCells)
                        cells.Add(anchor+direction*radius);
            }
            foreach (var cell in cells.Where(c => c.InBounds(map))) yield return cell;
        }
        public static ApiResult<object> Context()
        {
            Targeter t=Find.Targeter; Map map=Find.CurrentMap;
            if (t == null || !t.IsTargeting || map == null) return ApiResult<object>.Ok(new { active=false });
            var source=t.targetingSource;
            Ability ability=(source as Verb_CastAbility)?.ability ?? (source as CompAbilityEffect_WithDest)?.parent;
            RoyalTitlePermitDef permit=(source as RoyalTitlePermitWorker)?.def;
            var pawns=map.mapPawns.AllPawnsSpawned.Where(p => !p.Dead).ToList();
            var allies=pawns.Where(p => p.Faction == Faction.OfPlayer).Select(p => p.Position).ToList();
            var hostiles=pawns.Where(p => p.HostileTo(Faction.OfPlayer) && !p.Downed).Select(p => p.Position).ToList();
            var nearby=new Dictionary<IntVec3, Tuple<int,int>>();
            Func<IntVec3,Tuple<int,int>> counts=cell => {
                if (!nearby.TryGetValue(cell,out var result)) {
                    result=Tuple.Create(allies.Count(p => p.DistanceToSquared(cell)<=25),hostiles.Count(p => p.DistanceToSquared(cell)<=400));
                    nearby[cell]=result;
                }
                return result;
            };
            var options=Candidates(map).Where(target => Valid(t,map,target)).Select(target => new {
                key=target.HasThing ? "thing:"+target.Thing.thingIDNumber : $"cell:{target.Cell.x}:{target.Cell.z}",
                target_id=target.HasThing ? target.Thing.thingIDNumber : 0, x=target.Cell.x, z=target.Cell.z,
                kind=target.Thing is Pawn ? "pawn" : target.HasThing ? "object" : "cell",
                label=target.Thing?.LabelCap.ToString() ?? target.Cell.ToString(),
                definition=target.Thing?.def.defName, inspect=target.Thing?.GetInspectString(),
                hostile=target.Thing?.HostileTo(Faction.OfPlayer) ?? false,
                downed=(target.Thing as Pawn)?.Downed ?? false,
                health=(target.Thing as Pawn)?.health?.summaryHealth?.SummaryHealthPercent,
                bleed_rate=(target.Thing as Pawn)?.health?.hediffSet?.BleedRateTotal,
                conditions=(target.Thing as Pawn)?.health?.hediffSet?.hediffs.Where(h => h.Visible)
                    .Select(h => h.def.LabelCap.ToString()).ToList(),
                roof=map.roofGrid.RoofAt(target.Cell)?.defName, temperature=target.Cell.GetTemperature(map),
                fire=target.Cell.ContainsStaticFire(map),
                allies_within_five=counts(target.Cell).Item1,
                hostiles_within_twenty=counts(target.Cell).Item2
            }).ToList();
            return ApiResult<object>.Ok(new { active=true, session_id=SessionId(t), source=source?.GetType().Name,
                effect_label=ability?.def.LabelCap.ToString() ?? permit?.LabelCap.ToString(),
                effect_description=ability?.def.description ?? permit?.description,
                effect_cost=ability != null ? $"focus {ability.def.PsyfocusCost}; heat {ability.def.EntropyGain}; charges {ability.RemainingCharges}" :
                    permit != null ? $"favor {permit.royalAid.favorCost} when cooldown not ready; cooldown {permit.CooldownTicks}" : "Original native command cost",
                caster=source?.Caster?.LabelCap.ToString(), map_id=map.uniqueID, options,
                limits="Actual native validator. Listed cells are observed anchors and offsets, not every map cell. Legal targeting does not prove safety or benefit." });
        }
        public static ApiResult<object> Order(int sessionId,int mapId,int targetId,int x,int z,bool cancel)
        {
            var t=Find.Targeter; var map=Find.CurrentMap;
            if (t == null || map == null || map.uniqueID != mapId || !t.IsTargeting || SessionId(t) != sessionId)
                return ApiResult<object>.Ok(new { applied=false,reason="targeting_session_changed" });
            if (cancel) { t.StopTargeting(); return ApiResult<object>.Ok(new { applied=true,reason="targeting_cancelled" }); }
            Thing thing=targetId == 0 ? null : map.listerThings.AllThings.FirstOrDefault(item => item.thingIDNumber == targetId);
            if (targetId != 0 && thing == null) return ApiResult<object>.Ok(new { applied=false,reason="target_disappeared" });
            LocalTargetInfo target=thing == null ? new LocalTargetInfo(new IntVec3(x,0,z)) : new LocalTargetInfo(thing);
            if (!Valid(t,map,target)) return ApiResult<object>.Ok(new { applied=false,reason="target_no_longer_valid" });
            var source=t.targetingSource;
            if (source != null)
            {
                source.OrderForceTarget(target);
                if (source.DestinationSelector != null)
                    t.BeginTargeting(source.DestinationSelector,source,allowNonSelectedTargetingSource:true);
                else if (t.targetingSource == source) t.StopTargeting();
            }
            else
            {
                var action=Traverse.Create(t).Field("action").GetValue<Action<LocalTargetInfo>>();
                if (action == null) return ApiResult<object>.Ok(new { applied=false,reason="targeting_action_missing" });
                action(target);
                if (SessionId(t) == sessionId) t.StopTargeting();
            }
            return ApiResult<object>.Ok(new { applied=true,reason="native_target_selected",completion="unverified" });
        }
    }
}

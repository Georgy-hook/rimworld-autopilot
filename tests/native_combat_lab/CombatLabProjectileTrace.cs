#if LAYA_COMBAT_LAB
// Read-only native evidence. No projectile, pawn, damage or random-state edits.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using HarmonyLib;
using RimWorld;
using UnityEngine;
using Verse;

namespace RIMAPI.Controllers
{
    public static class CombatLabProjectileTrace
    {
        public const int Limit=4000;
        public static readonly Dictionary<int,object> Launches=new Dictionary<int,object>();
        public static readonly List<object> Impacts=new List<object>(),Deaths=new List<object>();
        public static readonly Dictionary<int,object> Downs=new Dictionary<int,object>();
        public static readonly List<object> Tends=new List<object>();
        private static readonly HashSet<string> SeenImpacts=new HashSet<string>();
        private static readonly HashSet<int> SeenDeaths=new HashSet<int>();
        private static readonly FieldInfo Destination=typeof(Projectile).GetField("destination",BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic);
        public static int Dropped;
        [ThreadStatic] public static object NativeWildMiss;
        public static void Reset(){Launches.Clear();Impacts.Clear();Deaths.Clear();Downs.Clear();Tends.Clear();SeenImpacts.Clear();SeenDeaths.Clear();Dropped=0;CombatLabFutureGeometry.Reset();}
        public static bool HooksPatched()
        {
            var required=new[]{typeof(CombatLabProjectileLaunchHook),typeof(CombatLabProjectileImpactHook),typeof(CombatLabDeathHook),typeof(CombatLabDownedHook),typeof(CombatLabTendHook),typeof(CombatLabTacticHook),typeof(CombatLabCastBranchHook),typeof(CombatLabWildMissBranchHook)};
            var installed=Harmony.GetAllPatchedMethods().SelectMany(method=>{
                var info=Harmony.GetPatchInfo(method);
                return info.Prefixes.Concat(info.Postfixes).Select(patch=>patch.PatchMethod.DeclaringType);
            }).Distinct().ToArray();
            return required.All(installed.Contains);
        }
        public static bool Tracked(Thing thing)=>thing is Pawn p && p.MapHeld==CombatLabState.Map
            && (CombatLabState.Allies.Contains(p) || CombatLabState.Enemies.Contains(p) || p==CombatLabState.Captive);
        private static object Target(object value)=>value is LocalTargetInfo target
            ?(object)new{thing_id=target.HasThing?(int?)target.Thing.thingIDNumber:null,
                x=target.IsValid?(int?)target.Cell.x:null,z=target.IsValid?(int?)target.Cell.z:null}:null;
        public static void Launch(Projectile projectile,MethodBase method,object[] args)
        {
            var parameters=method.GetParameters();
            Func<string,object> argument=name=>{int index=Array.FindIndex(parameters,p=>p.Name==name);return index>=0?args[index]:null;};
            if(!(argument("launcher") is Pawn shooter) || !Tracked(shooter))return;
            if(!Launches.ContainsKey(projectile.thingIDNumber) && Launches.Count>=Limit){Dropped++;return;}
            var origin=args.OfType<Vector3>().First();
            Vector3? destination=Destination?.GetValue(projectile) is Vector3 point?(Vector3?)point:null;
            var intended=argument("intendedTarget") is LocalTargetInfo info?info.Thing as Pawn:null;
            var carried=intended?.carryTracker?.CarriedThing as Pawn;
            var verb=shooter.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            bool inspectLane=shooter.Faction!=Faction.OfPlayer && intended?.Spawned==true
                && intended.Faction==Faction.OfPlayer && intended.Map==CombatLabState.Map && verb!=null;
            // Compare the two native target forms at the actual launch, not
            // at a later sampled position. These are read-only predicates;
            // they do not change the shot, collision, stats or random stream.
            bool? hitPawn=inspectLane?(bool?)verb.CanHitTargetFrom(shooter.Position,intended):null;
            bool? hitCell=inspectLane?(bool?)verb.CanHitTargetFrom(shooter.Position,new LocalTargetInfo(intended.Position)):null;
            bool? candidateHit=inspectLane?RIMAPI.Helpers.CombatExposureHelper.CanHitCandidate(
                verb,shooter.Position,intended.Position,intended.Map):null;
            float? exposure=inspectLane?(float?)RIMAPI.Helpers.CombatControlHelper.IncomingRangedExposure(intended,intended.Position):null;
            object scatterCheck=null;
            if(shooter.Faction==Faction.OfPlayer && intended?.Spawned==true && verb!=null
                && verb.TryFindShootLineFromTo(shooter.Position,intended,out var friendlyLine))
            {
                var rngBefore=CombatLabState.RandomProperty?.GetValue(null,null)?.ToString();
                var report=ShotReport.HitReportFor(shooter,verb,intended);
                float? candidate=RIMAPI.Helpers.CombatFriendlyFireHelper.CandidateAim(shooter,verb,intended,shooter.Position,friendlyLine);
                float? radius=RIMAPI.Helpers.CombatFriendlyFireHelper.MissRadius(shooter,verb,intended,shooter.Position,friendlyLine);
                scatterCheck=new{native_aim=report.AimOnTargetChance_StandardTarget,candidate_aim=candidate,
                    maximum_endpoint_radius=radius,lane_clear=RIMAPI.Helpers.CombatInterceptHelper.FriendlyLaneClear(shooter,intended,shooter.Position),
                    control_uses_scatter_envelope=true,
                    rng_unchanged=rngBefore==CombatLabState.RandomProperty?.GetValue(null,null)?.ToString(),
                    meaning="Loaded native miss surface at quantile 1; read-only candidate lower accuracy bound. No future ally-motion guarantee."};
            }
            Launches[projectile.thingIDNumber]=new{tick=Find.TickManager.TicksGame,projectile_id=projectile.thingIDNumber,
                shooter=shooter.thingIDNumber,weapon=shooter.equipment?.Primary?.def.defName,
                origin_x=origin.x,origin_y=origin.y,origin_z=origin.z,
                destination_available=destination.HasValue,destination_x=destination?.x,destination_y=destination?.y,destination_z=destination?.z,
                native_projectile_speed=projectile.def.projectile?.speed,
                used_target=Target(argument("usedTarget")),intended_target=Target(argument("intendedTarget")),
                intended_target_carrying_pawn_id=carried?.thingIDNumber,
                carried_pawn_is_player=carried==null?(bool?)null:carried.Faction==Faction.OfPlayer,
                target_pawn_can_be_hit=hitPawn,target_cell_can_be_hit=hitCell,target_candidate_can_be_hit=candidateHit,
                target_current_ranged_exposure=exposure,
                friendly_scatter_check=scatterCheck,native_wild_miss=NativeWildMiss,
                shooter_job=shooter?.CurJobDef?.defName,control_selected_target=shooter==null?(int?)null:RIMAPI.Helpers.CombatControlHelper.TestTarget(shooter),
                owned_current_job=shooter!=null && RIMAPI.Helpers.CombatOrderHelper.Owned(shooter,shooter.CurJob),
                hit_flags=argument("hitFlags")?.ToString(),prevent_friendly_fire=argument("preventFriendlyFire"),
                allies=CombatLabState.Allies.Where(p=>p.Spawned && !p.Dead).Select(p=>new{id=p.thingIDNumber,
                    x=p.Position.x,z=p.Position.z,downed=p.Downed,moving=p.pather?.Moving,
                    job=p.CurJobDef?.defName,goal_x=p.CurJob?.targetA.Cell.x,goal_z=p.CurJob?.targetA.Cell.z}).ToArray()};
        }
        public static void Impact(Projectile projectile,MethodBase method,object[] args)
        {
            if(!Launches.ContainsKey(projectile.thingIDNumber))return;
            if(Impacts.Count>=Limit){Dropped++;return;}
            int tick=Find.TickManager.TicksGame;
            if(!SeenImpacts.Add(projectile.thingIDNumber+":"+tick))return;
            Thing hit=args.Length>0?args[0] as Thing:null;
            Impacts.Add(new{tick,projectile_id=projectile.thingIDNumber,hit_id=hit?.thingIDNumber,hit_def=hit?.def.defName,
                projectile_x=projectile.Position.x,projectile_z=projectile.Position.z,
                x=hit?.Position.x,z=hit?.Position.z,was_dead=(hit as Pawn)?.Dead,was_downed=(hit as Pawn)?.Downed,
                blocked_by_shield=args.Length>1 && args[1] is bool blocked?(bool?)blocked:null,
                native_method=method.DeclaringType.FullName+"."+method.Name});
        }
        public static object BeforeDeath(Pawn pawn,object[] args)
        {
            if(pawn.Dead || !Tracked(pawn))return null;
            Hediff culprit=args.OfType<Hediff>().FirstOrDefault();
            DamageInfo? damage=args.OfType<DamageInfo>().Select(d=>(DamageInfo?)d).FirstOrDefault();
            return new{tick=Find.TickManager.TicksGame,pawn_id=pawn.thingIDNumber,
                exact_culprit=culprit?.def.defName,culprit_severity=culprit?.Severity,
                native_damage_kind=damage?.Def?.defName,native_instigator=damage?.Instigator?.thingIDNumber,
                health_before=pawn.health.summaryHealth.SummaryHealthPercent,bleeding_before=pawn.health.hediffSet.BleedRateTotal};
        }
        public static void AfterDeath(Pawn pawn,object before)
        {if(before!=null && pawn.Dead && SeenDeaths.Add(pawn.thingIDNumber))Deaths.Add(before);}
        public static void AfterDown(Pawn pawn,object before)
        {if(before!=null && pawn.Downed && !Downs.ContainsKey(pawn.thingIDNumber))Downs[pawn.thingIDNumber]=before;}
    }
    [HarmonyPatch(typeof(Verb_LaunchProjectile),"TryCastShot")]
    public static class CombatLabCastBranchHook
    {
        public static void Prefix(){CombatLabProjectileTrace.NativeWildMiss=null;}
        public static void Postfix(){CombatLabProjectileTrace.NativeWildMiss=null;}
    }
    [HarmonyPatch(typeof(ShootLine),nameof(ShootLine.ChangeDestToMissWild))]
    public static class CombatLabWildMissBranchHook
    {
        public static void Prefix(ShootLine __instance,out ShootLine __state){__state=__instance;}
        public static void Postfix(ShootLine __instance,ShootLine __state)
        {
            CombatLabProjectileTrace.NativeWildMiss=new{source_x=__state.Source.x,source_z=__state.Source.z,
                original_x=__state.Dest.x,original_z=__state.Dest.z,miss_x=__instance.Dest.x,miss_z=__instance.Dest.z,
                source="actual_native_ChangeDestToMissWild_postfix_read_only"};
        }
    }
    [HarmonyPatch]
    public static class CombatLabProjectileLaunchHook
    {
        public static MethodBase TargetMethod()=>typeof(Projectile).GetMethods(BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic)
            .Single(m=>m.Name=="Launch" && m.GetParameters().Any(p=>p.ParameterType==typeof(Vector3)));
        public static void Postfix(Projectile __instance,MethodBase __originalMethod,object[] __args)
            =>CombatLabProjectileTrace.Launch(__instance,__originalMethod,__args);
    }
    [HarmonyPatch]
    public static class CombatLabProjectileImpactHook
    {
        public static IEnumerable<MethodBase> TargetMethods()=>typeof(Projectile).Assembly.GetTypes()
            .Where(t=>typeof(Projectile).IsAssignableFrom(t)).SelectMany(t=>t.GetMethods(BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.DeclaredOnly))
            .Where(m=>m.Name=="Impact" && !m.IsAbstract && m.GetParameters().Length>0 && m.GetParameters()[0].ParameterType==typeof(Thing))
            .Cast<MethodBase>();
        public static void Prefix(Projectile __instance,MethodBase __originalMethod,object[] __args)
            =>CombatLabProjectileTrace.Impact(__instance,__originalMethod,__args);
    }
    [HarmonyPatch]
    public static class CombatLabDeathHook
    {
        public static IEnumerable<MethodBase> TargetMethods()=>typeof(Pawn).GetMethods(BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.DeclaredOnly)
            .Where(m=>m.Name=="Kill" && !m.IsAbstract).Cast<MethodBase>();
        public static void Prefix(Pawn __instance,object[] __args,out object __state)
            =>__state=CombatLabProjectileTrace.BeforeDeath(__instance,__args);
        public static void Postfix(Pawn __instance,object __state)=>CombatLabProjectileTrace.AfterDeath(__instance,__state);
    }
    [HarmonyPatch(typeof(Pawn_HealthTracker),"MakeDowned")]
    public static class CombatLabDownedHook
    {
        public static void Prefix(Pawn ___pawn,object[] __args,out object __state)
            =>__state=___pawn.Downed?null:CombatLabProjectileTrace.BeforeDeath(___pawn,__args);
        public static void Postfix(Pawn ___pawn,object __state)=>CombatLabProjectileTrace.AfterDown(___pawn,__state);
    }
    [HarmonyPatch(typeof(TendUtility),nameof(TendUtility.DoTend),new[]{typeof(Pawn),typeof(Pawn),typeof(Medicine)})]
    public static class CombatLabTendHook
    {
        public static void Prefix(Pawn __1,out float __state)=>__state=CombatLabProjectileTrace.Tracked(__1)?__1.health.hediffSet.BleedRateTotal:-1f;
        public static void Postfix(Pawn __0,Pawn __1,float __state)
        {
            if(__state<0 || !CombatLabProjectileTrace.Tracked(__1))return;
            if(CombatLabProjectileTrace.Tends.Count>=CombatLabProjectileTrace.Limit){CombatLabProjectileTrace.Dropped++;return;}
            CombatLabProjectileTrace.Tends.Add(new{tick=Find.TickManager.TicksGame,doctor=__0?.thingIDNumber,
                patient=__1.thingIDNumber,bleeding_before=__state,bleeding_after=__1.health.hediffSet.BleedRateTotal});
        }
    }
}
#endif

#if LAYA_COMBAT_LAB
// Controlled native-engine fixtures. Never compiled into a normal package.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Reflection;
using System.Threading.Tasks;
using HarmonyLib;
using RIMAPI.Core;
using RIMAPI.Http;
using RIMAPI.Helpers;
using RIMAPI.Models;
using RimWorld;
using Verse;
using Verse.AI;
using Verse.AI.Group;

namespace RIMAPI.Controllers
{
    public class CombatLabRequest
    {
        public string CampaignId {get;set;}
        public string Scenario {get;set;}="melee_rush";
        public int Seed {get;set;}=101;
        public int Ticks {get;set;}=60;
        public int Attackers {get;set;}=6;
        public int Defenders {get;set;}=4;
        public bool Cover {get;set;}=true;
        public bool Micro {get;set;}=true;
        public string EnemyXenotype {get;set;}="Baseliner";
        public bool Fortified {get;set;}=false;
        public string DefenseLayout {get;set;}="firing_ports";
        public bool IncludeTrace {get;set;}=true;
        public List<int> AlliedIds {get;set;}
        public List<int> EnemyIds {get;set;}
        public string InitialRandomState {get;set;}
        public int ExpectedTick {get;set;}
        public bool Pause {get;set;}
        public string ExpectedNativeInstanceId {get;set;}
    }
    public static class CombatLabState
    {
        public static readonly int ProcessId=System.Diagnostics.Process.GetCurrentProcess().Id;
        public static readonly string InstanceId=Guid.NewGuid().ToString("N");
        public static List<Pawn> Allies=new List<Pawn>(),Enemies=new List<Pawn>();
        public static List<object> Damage=new List<object>(),Samples=new List<object>();
        public static Dictionary<int,int> Shots=new Dictionary<int,int>(),GunMeleeTicks=new Dictionary<int,int>(),IdleDraftTicks=new Dictionary<int,int>();
        public static int StartTick,StepTicks;
        public static string Scenario;
        public static object InitialRandomState;
        public static bool LoadedBaseline,HoldInitial;
        public static readonly PropertyInfo RandomProperty=typeof(Rand).GetProperty("StateCompressed",BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic);
        public static Map Map;
        public static Pawn Captive, PassiveProbe;
        public static bool Stepping;
        public static System.Diagnostics.Stopwatch SetupClock;
        public static List<object> SetupTimings=new List<object>();
        public static void SetupMark(string phase)=>SetupTimings.Add(new{phase=phase,seconds=SetupClock.Elapsed.TotalSeconds});
        public static void Guard(string campaign=null,string expectedNativeInstance=null)
        {
            if(Environment.GetEnvironmentVariable("LAYA_COMBAT_LAB")!="authorized-20261014")throw new InvalidOperationException("Laboratory process flag absent");
            if(expectedNativeInstance!=null && expectedNativeInstance!=InstanceId)
                throw new InvalidOperationException("Not the expected native laboratory instance");
            if(campaign!=null && (Current.Game?.GetComponent<EndingEvidence>()?.CampaignId!=campaign
                || Find.World?.info?.seedString?.StartsWith("laya-combat-lab-")!=true))
                throw new InvalidOperationException("Not the named disposable laboratory campaign");
        }
        public static object State(bool includeTrace=true)
        {
            Func<Pawn,object> row=p=>new {id=p.thingIDNumber,name=p.LabelShort,dead=p.Dead,downed=p.Downed,
                spawned=p.Spawned,health=p.health.summaryHealth.SummaryHealthPercent,
                bleeding=p.health.hediffSet.BleedRateTotal,job=p.CurJobDef?.defName,target=p.CurJob?.targetA.Thing?.thingIDNumber,
                job_id=p.CurJob?.loadID,job_player_forced=p.CurJob?.playerForced,job_can_use_ranged=p.CurJob?.canUseRangedWeapon,job_owned=CombatOrderHelper.Owned(p,p.CurJob),
                job_exit_map_on_arrival=p.CurJob?.exitMapOnArrival,native_kidnapper=CombatNativeHelper.Kidnapper(p),tend_one_pass=p.CurJobDef==JobDefOf.TendPatient?(bool?)p.CurJob.endAfterTendedOnce:null,
                queued_jobs=p.jobs?.jobQueue.Select(q=>new{job_id=q.job.loadID,def=q.job.def.defName,
                    target_id=q.job.targetA.Thing?.thingIDNumber,x=q.job.targetA.Cell.x,z=q.job.targetA.Cell.z,
                    player_forced=q.job.playerForced}).ToArray(),
                observed_firing_victim=CombatControlHelper.ObservedVictim(p)?.thingIDNumber,control_mode=CombatControlHelper.TestMode(p),
                plan_target=CombatControlHelper.TestTarget(p),
                drafted=p.Drafted,x=p.Position.x,z=p.Position.z,
                in_mental_state=p.InMentalState,food=p.needs?.food?.CurLevelPercentage,rest=p.needs?.rest?.CurLevelPercentage,mood=p.needs?.mood?.CurLevelPercentage,
                weapon=p.equipment?.Primary?.def.defName,shooting=p.skills?.GetSkill(SkillDefOf.Shooting)?.Level,
                native_shootable_ids=(p.Faction==Faction.OfPlayer?Enemies:Allies).Where(q=>q.Spawned && !q.Dead && !q.Downed
                    && p.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb?.CanHitTargetFrom(p.Position,q)==true)
                    .Select(q=>q.thingIDNumber).ToList(),
                xenotype=p.genes?.Xenotype?.defName,traits=p.story?.traits?.allTraits.Select(t=>t.def.defName+":"+t.Degree).ToList(),
                genes=p.genes?.GenesListForReading.Select(g=>g.def.defName).ToList(),body_size=p.BodySize,
                aim_delay=p.GetStatValue(StatDefOf.AimingDelayFactor),
                disabled_work=DefDatabase<WorkTypeDef>.AllDefsListForReading.Where(p.WorkTypeIsDisabled).Select(w=>w.defName).ToList(),
                faction=p.Faction?.def.defName,
                doctor_enabled=!p.WorkTypeIsDisabled(WorkTypeDefOf.Doctor),carried_id=p.carryTracker?.CarriedThing?.thingIDNumber,
                in_bed=p.InBed(),bed_id=p.CurrentBed()?.thingIDNumber,
                speed=p.Spawned?p.GetStatValue(StatDefOf.MoveSpeed):0f,move_ticks=p.Spawned?p.TicksPerMoveCardinal:0,
                cover=p.Spawned?Enemies.Where(e=>e.Spawned && !e.Dead).Select(e=>CoverUtility.CalculateOverallBlockChance(p,e.Position,p.Map)).DefaultIfEmpty().Average():0f,
                shots=Shots.TryGetValue(p.thingIDNumber,out int n)?n:0,
                gun_melee_ticks=GunMeleeTicks.TryGetValue(p.thingIDNumber,out int m)?m:0,
                idle_draft_ticks=IdleDraftTicks.TryGetValue(p.thingIDNumber,out int i)?i:0,
                warmup=(p.stances?.curStance as Stance_Warmup)?.ticksLeft,
                urgency=p.CurJob?.locomotionUrgency.ToString(),next_cell_cost=p.pather?.nextCellCostLeft,
                stance=p.stances?.curStance?.GetType().Name,moving=p.pather?.Moving,queued=p.jobs?.jobQueue?.Select(q=>q.job.def.defName).ToList(),
                lord_toil=p.GetLord()?.CurLordToil?.GetType().Name};
            return new {native_process_id=ProcessId,native_instance_id=InstanceId,
                scenario=Scenario,tick=Find.TickManager.TicksGame,start_tick=StartTick,stepped_ticks=StepTicks,
                setup_timings=SetupTimings.ToList(),
                carrier_volley_guard=CombatCarrierVolleyHelper.Diagnostics(),
                pursuit_approach=CombatPursuitApproachHelper.Diagnostics(Allies),
                initial_random_state=InitialRandomState?.ToString(),current_random_state=RandomProperty?.GetValue(null,null)?.ToString(),
                loaded_baseline=LoadedBaseline,holding_initial_clock=HoldInitial,
                random_stream="Seeded once at setup or restored initial fixture; ordinary native draws thereafter, including stepped staging ticks",
                allies=Allies.Select(row).ToList(),enemies=Enemies.Select(row).ToList(),
                ever_downed_ids=Allies.Where(p=>CombatLabProjectileTrace.Downs.ContainsKey(p.thingIDNumber)).Select(p=>p.thingIDNumber).ToArray(),
                down_events=includeTrace?CombatLabProjectileTrace.Downs.Values.ToList():new List<object>(),
                damage_events=includeTrace?Damage.ToList():new List<object>(),samples=includeTrace?Samples.ToList():new List<object>(),
                projectile_traces=includeTrace?CombatLabProjectileTrace.Launches.Values.ToList():new List<object>(),
                impact_traces=includeTrace?CombatLabProjectileTrace.Impacts.ToList():new List<object>(),
                death_events=includeTrace?CombatLabProjectileTrace.Deaths.ToList():new List<object>(),
                tend_events=includeTrace?CombatLabProjectileTrace.Tends.ToList():new List<object>(),
                projectile_trace_dropped=CombatLabProjectileTrace.Dropped,
                control=CombatControlHelper.Diagnostics(),execution_timing=CombatLabExecutionTiming.State(),
                tactic_calls=CombatLabTacticTrace.Rows.ToArray(),
                group_focus_reviews=CombatControlHelper.GroupFocusReviews.ToArray(),
                support_window_reviews=CombatControlHelper.SupportWindowReviews.ToArray(),
                medical_review_component=Current.Game.GetComponent<MedicalTendReviewComponent>()!=null,
                exposure=CombatExposureHelper.Diagnostics(),
                future_geometry=CombatLabFutureGeometry.State(includeTrace),
                future_friendly_guard_shadow=CombatLabFutureFriendlyShadow.State(includeTrace),
                long_carrier_control=CombatCarrierInterceptHelper.Diagnostics(),
                unexpected_player_ids=Map==null?new List<int>():Map.mapPawns.FreeColonistsSpawned
                    .Where(p=>!Allies.Contains(p) && p!=Captive).Select(p=>p.thingIDNumber).ToList(),
                unexpected_threat_ids=Map==null?new List<int>():Map.mapPawns.AllPawnsSpawned
                    .Where(p=>p.Spawned && !Enemies.Contains(p) && !Allies.Contains(p) && !p.Dead && !p.Downed
                        && CombatNativeHelper.IsPlayerThreat(p)).Select(p=>p.thingIDNumber).ToList(),
                unexpected_actors=Map==null?new List<object>():Map.mapPawns.AllPawnsSpawned
                    .Where(p=>p.Spawned && !Enemies.Contains(p) && !Allies.Contains(p) && p!=Captive
                        && !p.Dead && (p.Faction==Faction.OfPlayer || CombatNativeHelper.IsPlayerThreat(p)))
                    .Select(p=>(object)new{id=p.thingIDNumber,name=p.LabelShort,kind=p.kindDef.defName,
                        faction=p.Faction?.def.defName,x=p.Position.x,z=p.Position.z,job=p.CurJobDef?.defName,
                        lord=p.GetLord()?.LordJob?.GetType().Name,toil=p.GetLord()?.CurLordToil?.GetType().Name}).ToList(),
                captive=Captive==null?null:row(Captive),
                passive_probe=PassiveProbe==null?null:row(PassiveProbe),
                climate="Controlled 20C cells, clear weather at setup; no damage/health/AI/outcome overrides",
                ecology="No new wildlife influx while this declared laboratory fixture is active; initial pawns and native AI unchanged",
                engine="Actual TickManager.DoSingleTick, native jobs, verbs, projectiles and damage; no combat outcome stub"};
        }
        public static void Sample()
        {
            foreach(Pawn p in Allies.Where(p=>p.Spawned && !p.Dead))
            {
                int id=p.thingIDNumber;
                if(p.CurJobDef==JobDefOf.AttackMelee && p.equipment?.Primary?.def.IsRangedWeapon==true)
                    GunMeleeTicks[id]=(GunMeleeTicks.TryGetValue(id,out int n)?n:0)+1;
                if(p.Drafted && p.CurJobDef?.defName=="Wait_Combat" && !(p.stances.curStance is Stance_Warmup))
                    IdleDraftTicks[id]=(IdleDraftTicks.TryGetValue(id,out int n)?n:0)+1;
            }
            if(Find.TickManager.TicksGame%60==0)
                Samples.Add(new {tick=Find.TickManager.TicksGame,allies=Allies.Select(p=>new{id=p.thingIDNumber,x=p.Position.x,z=p.Position.z,job=p.CurJobDef?.defName,dead=p.Dead,downed=p.Downed,drafted=p.Drafted,
                    job_id=p.CurJob?.loadID,tend_one_pass=p.CurJobDef==JobDefOf.TendPatient?(bool?)p.CurJob.endAfterTendedOnce:null,
                    consciousness=p.health.capacities.GetLevel(PawnCapacityDefOf.Consciousness),
                    moving_capacity=p.health.capacities.GetLevel(PawnCapacityDefOf.Moving),
                    manipulation=p.health.capacities.GetLevel(PawnCapacityDefOf.Manipulation),sight=p.health.capacities.GetLevel(PawnCapacityDefOf.Sight),
                    control_mode=CombatControlHelper.TestMode(p),
                    plan_target=CombatControlHelper.TestTarget(p),
                    aim_target=CombatControlHelper.AimTarget(p)?.thingIDNumber,
                    target=p.CurJob?.targetA.Thing?.thingIDNumber,goal_x=p.CurJob?.targetA.Cell.x,goal_z=p.CurJob?.targetA.Cell.z,
                    warmup=(p.stances?.curStance as Stance_Warmup)?.ticksLeft,locked=(p.stances?.curStance as Stance_Busy)?.ticksLeft,
                    stance=p.stances?.curStance?.GetType().Name,moving=p.pather?.Moving,queued=p.jobs?.jobQueue?.Select(q=>q.job.def.defName).ToList(),
                    urgency=p.CurJob?.locomotionUrgency.ToString(),next_cell_cost=p.pather?.nextCellCostLeft,
                    health=p.health.summaryHealth.SummaryHealthPercent,bleeding=p.health.hediffSet.BleedRateTotal,
                    care_target_id=p.Spawned && CombatNativeHelper.HasClinicalCareJob(p)?CombatNativeHelper.CareTarget(p)?.thingIDNumber:null,
                    care_immediate_threat_ids=p.Spawned && CombatNativeHelper.HasClinicalCareJob(p)
                        ?Enemies.Where(e=>CombatNativeHelper.ImmediateCareThreat(p,e)).Select(e=>e.thingIDNumber).ToArray():new int[0],
                    ranged_exposure=p.Spawned?CombatControlHelper.IncomingRangedExposure(p,p.Position):0f,
                    native_shootable_ids=Enemies.Where(e=>e.Spawned && !e.Dead && !e.Downed && p.Spawned
                        && CombatInterceptHelper.CanShootNow(p,e)).Select(e=>e.thingIDNumber).ToArray(),
                    shots=Shots.TryGetValue(p.thingIDNumber,out int n)?n:0,
                    in_mental_state=p.InMentalState,food=p.needs?.food?.CurLevelPercentage,rest=p.needs?.rest?.CurLevelPercentage,mood=p.needs?.mood?.CurLevelPercentage}).ToList(),
                    enemies=Enemies.Select(p=>new{id=p.thingIDNumber,x=p.Position.x,z=p.Position.z,job=p.CurJobDef?.defName,
                        observed_firing_victim=CombatControlHelper.ObservedVictim(p)?.thingIDNumber,
                        target=p.CurJob?.targetA.Thing?.thingIDNumber,goal_x=p.CurJob?.targetA.Cell.x,goal_z=p.CurJob?.targetA.Cell.z,
                        health=p.health.summaryHealth.SummaryHealthPercent,bleeding=p.health.hediffSet.BleedRateTotal,
                        speed=p.Spawned?p.GetStatValue(StatDefOf.MoveSpeed):0f,
                        urgency=p.CurJob?.locomotionUrgency.ToString(),
                        locked=(p.stances?.curStance as Stance_Busy)?.ticksLeft,carried=p.carryTracker?.CarriedThing?.thingIDNumber,
                        lord=p.GetLord()?.LordJob?.GetType().Name,toil=p.GetLord()?.CurLordToil?.GetType().Name}).ToList()});
        }
    }
    [HarmonyPatch(typeof(Verb_LaunchProjectile),"TryCastShot")]
    public static class CombatLabShotHook
    {
        public static void Postfix(Verb_LaunchProjectile __instance,bool __result)
        {
            Pawn p=__instance.CasterPawn;
            if(!__result || p==null || (!CombatLabState.Allies.Contains(p) && !CombatLabState.Enemies.Contains(p)))return;
            int id=p.thingIDNumber;CombatLabState.Shots[id]=(CombatLabState.Shots.TryGetValue(id,out int n)?n:0)+1;
        }
    }
    [HarmonyPatch(typeof(Thing),nameof(Thing.TakeDamage))]
    public static class CombatLabDamageHook
    {
        public static void Postfix(Thing __instance,DamageInfo dinfo,DamageWorker.DamageResult __result)
        {
            if(!(__instance is Pawn p) || (!CombatLabState.Allies.Contains(p) && !CombatLabState.Enemies.Contains(p) && p!=CombatLabState.Captive))return;
            CombatLabState.Damage.Add(new {tick=Find.TickManager.TicksGame,victim=p.thingIDNumber,
                actor=dinfo.Instigator?.thingIDNumber,kind=dinfo.Def.defName,amount=__result.totalDamageDealt,weapon=dinfo.Weapon?.defName});
        }
    }
    public class CombatLabController
    {
        [Get("/api/v1/combat-lab/info")]
        public async Task Info(HttpListenerContext context)
        {
            CombatLabState.Guard();
            LogApi.IsLogging=true;LogApi.LoggingLevel=LoggingLevels.ERROR;
            var types=typeof(LordJob_AssaultColony).Assembly.GetTypes().Where(t=>t.Name.Contains("StageThenAttack") || t.Name=="LordToil_Stage");
            await context.SendJsonResponse(ApiResult<object>.Ok(new {test_build=true,
                native_process_id=CombatLabState.ProcessId,native_instance_id=CombatLabState.InstanceId,
                prior_fixture_on_current_map=CombatLabState.Map!=null && CombatLabState.Map==Find.CurrentMap,
                loaded_initial_baseline=CombatLabState.LoadedBaseline,
                projectile_trace_hooks=CombatLabProjectileTrace.HooksPatched(),
                native_down_transition_hook=CombatLabProjectileTrace.HooksPatched(),
                types=types.Select(t=>new {type=t.FullName,constructors=t.GetConstructors().Select(c=>c.GetParameters().Select(p=>p.ParameterType.FullName+" "+p.Name).ToArray()).ToArray()}).ToList(),
                random_state_available=CombatLabState.RandomProperty?.CanWrite,
                single_tick=typeof(TickManager).GetMethod("DoSingleTick",BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance)?.ToString()}));
        }
        [Get("/api/v1/combat-lab/intercept-long-route-probe")]
        public async Task LongInterceptProbe(HttpListenerContext context)
        {
            CombatLabState.Guard(context.Request.QueryString["campaign_id"],context.Request.QueryString["expected_native_instance_id"]);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabLongInterceptProbe.Read()));
        }
        [Get("/api/v1/combat-lab/intercept-probe")]
        public async Task InterceptProbe(HttpListenerContext context)
        {
            CombatLabState.Guard(context.Request.QueryString["campaign_id"],context.Request.QueryString["expected_native_instance_id"]);
            if(CombatLabState.Scenario!="intercept_perpendicular_contract" || !CombatLabState.HoldInitial || CombatLabState.StepTicks!=0)
                throw new InvalidOperationException("Read-only probe requires the held declared perpendicular initial fixture");
            var actor=CombatLabState.Allies.Single();var target=CombatLabState.Enemies.Single();
            var verb=actor.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
            string rngBefore=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            var clock=System.Diagnostics.Stopwatch.StartNew();
            var route=(List<Tuple<IntVec3,float>>)typeof(CombatInterceptHelper).GetMethod("TargetRoute",BindingFlags.Static|BindingFlags.NonPublic).Invoke(null,new object[]{target});
            float observedUntil=route?.LastOrDefault()?.Item2 ?? 0f;
            float aim=verb.verbProps.warmupTime*60f*actor.GetStatValue(StatDefOf.AimingDelayFactor);
            float engagement=CombatInterceptMath.EngagementTicks(true,false,aim,
                Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots,
                actor.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f);
            float flight=CombatInterceptMath.NativeFlightTicks(verb.verbProps.range,verb.verbProps.defaultProjectile.projectile.SpeedTilesPerTick);
            var rows=new List<object>();int pathQueries=0;
            foreach(int x in new[]{81,85,89,93,97})foreach(int z in new[]{90,94,98,102})
            {
                var cell=new IntVec3(x,0,z);pathQueries++;
                using(var path=actor.Map.pathFinder.FindPathNow(actor.Position,cell,actor,null,PathEndMode.OnCell))
                {
                    bool safe=CombatInterceptHelper.MovementSafe(actor,path);
                    float travel=path.Found?path.TotalCost:float.PositiveInfinity;
                    float horizon=CombatInterceptMath.ShotHorizon(travel+CombatInterceptHelper.MovementLockTicks(actor),aim+engagement,flight);
                    bool observed=CombatInterceptHelper.TryObservedFuturePosition(target,horizon,out var future) && horizon<=observedUntil;
                    bool window=CombatInterceptMath.CarrierWindow(verb.verbProps.range,verb.verbProps.minRange,cell.DistanceTo(future));
                    bool futureHit=CombatExposureHelper.CanHitPawnAt(verb,target,cell,future)==true;
                    bool futureLane=CombatInterceptHelper.FriendlyLaneClear(actor,new LocalTargetInfo(future),cell);
                    bool currentLane=CombatInterceptHelper.FriendlyLaneClear(actor,target,cell);
                    bool reserve=actor.CanReserve(cell) && !CombatControlHelper.CellClaimed(actor,cell);
                    rows.Add(new{x,z,path_found=path.Found,path_safe=safe,reservable=reserve,travel,horizon,observed_until=observedUntil,
                        observed_future=observed,future_x=future.x,future_z=future.z,future_window=window,
                        future_pawn_hit=futureHit,future_lane_clear=futureLane,current_lane_clear=currentLane,
                        future_legal_but_current_filter_rejects=safe && reserve && observed && window && futureHit && futureLane && !currentLane});
                }
            }
            bool oldSelected=CombatInterceptHelper.TryPosition(actor,target,out var oldCell);
            string prediction=CombatInterceptHelper.LastPrediction;
            string rngAfter=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            await context.SendJsonResponse(ApiResult<object>.Ok(new{native_process_id=CombatLabState.ProcessId,
                native_instance_id=CombatLabState.InstanceId,tick=Find.TickManager.TicksGame,
                scenario=CombatLabState.Scenario,actor_id=actor.thingIDNumber,target_id=target.thingIDNumber,
                actual_carried_id=target.carryTracker?.CarriedThing?.thingIDNumber,target_moving=target.pather.Moving,
                target_goal_x=target.pather.Destination.Cell.x,target_goal_z=target.pather.Destination.Cell.z,
                weapon=actor.equipment.Primary.def.defName,range=verb.verbProps.range,aim,engagement,flight,
                route=route?.Select(r=>new{x=r.Item1.x,z=r.Item1.z,tick=r.Item2}).ToArray(),
                old_selected=oldSelected,old_x=oldCell.x,old_z=oldCell.z,old_prediction=prediction,
                path_queries_in_probe=pathQueries,probe_ms=clock.Elapsed.TotalMilliseconds,
                rng_before=rngBefore,rng_after=rngAfter,rng_unchanged=rngBefore==rngAfter,rows,
                limits="Read-only initial route/window contract, no actor movement/stat/health/AI/RNG/physics edit and no raid credit"}));
        }
        [Post("/api/v1/combat-lab/setup")]
        public async Task Setup(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            Map map=Find.CurrentMap;Find.TickManager.Pause();
            CombatLabState.SetupTimings.Clear();CombatLabState.SetupClock=System.Diagnostics.Stopwatch.StartNew();CombatLabState.SetupMark("begin");
            // Destroying a carrier can drop a pawn that was not in the original
            // spawned-pawn snapshot. Clear those too before creating a cohort.
            for(int pass=0;pass<4 && map.mapPawns.AllPawnsSpawned.Any();pass++)
                foreach(Pawn p in map.mapPawns.AllPawnsSpawned.ToList())p.Destroy(DestroyMode.Vanish);
            if(map.mapPawns.AllPawnsSpawned.Any())throw new InvalidOperationException("Fixture pawn cleanup incomplete; no cohort generated");
            CombatLabState.SetupMark("spawned_pawns_removed");
            foreach(Corpse corpse in map.listerThings.AllThings.OfType<Corpse>().ToList())corpse.Destroy(DestroyMode.Vanish);
            // Whole-map isolation is required: generated hives outside the old
            // arena rectangle spawned extra insects on the first live ticks.
            // Remove their sources before the cohort exists, never during a fight.
            foreach(Thing t in map.listerThings.AllThings.ToList())
                {if(t.def.destroyable)t.Destroy(DestroyMode.Vanish);else if(t.Spawned)t.DeSpawn();}
            CombatLabState.SetupMark("generated_things_removed");
            for(int x=0;x<map.Size.x;x++)for(int z=0;z<map.Size.z;z++)
            {var c=new IntVec3(x,0,z);map.terrainGrid.SetTerrain(c,TerrainDefOf.Soil);map.roofGrid.SetRoof(c,null);}
            CombatLabState.SetupMark("terrain_roof_prepared");
            map.fogGrid.ClearAllFog();
            // Removing a casket/container or revealing the map can release its
            // previously unspawned occupants after the first cleanup pass.
            for(int pass=0;pass<4 && map.mapPawns.AllPawnsSpawned.Any();pass++)
                foreach(Pawn p in map.mapPawns.AllPawnsSpawned.ToList())
                {if(p.Spawned)p.DeSpawn();p.Destroy(DestroyMode.Vanish);}
            if(map.mapPawns.AllPawnsSpawned.Any())throw new InvalidOperationException("Container occupants survived fixture cleanup; no cohort generated");
            CombatLabState.Allies.Clear();CombatLabState.Enemies.Clear();CombatLabState.Damage.Clear();CombatLabState.Samples.Clear();
            CombatLabProjectileTrace.Reset();
            CombatLabTacticTrace.Rows.Clear();
            CombatLabState.Captive=null;CombatLabState.PassiveProbe=null;
            CombatLabState.Shots.Clear();CombatLabState.GunMeleeTicks.Clear();CombatLabState.IdleDraftTicks.Clear();
            CombatLabState.Scenario=r.Scenario;CombatLabState.Map=map;CombatLabState.StartTick=Find.TickManager.TicksGame;CombatLabState.StepTicks=0;
            CombatLabState.LoadedBaseline=false;CombatLabState.HoldInitial=true;
            map.weatherManager.TransitionTo(WeatherDefOf.Clear);
            CombatControlHelper.TestReset(!r.Micro);
            Rand.PushState(r.Seed);
            object prepared;
            try
            {
                Faction enemyFaction=Find.FactionManager.AllFactionsListForReading.First(f=>f.HostileTo(Faction.OfPlayer) && f.def.humanlikeFaction);
                for(int n=0;n<r.Defenders;n++)
                {
                    string weapon=n%2==0?"Gun_AssaultRifle":"Gun_HeavySMG";
                    if(r.Scenario=="rookie_knife")weapon=n==0?"Gun_BoltActionRifle":"Gun_Revolver";
                    if(r.Scenario=="staging")weapon="Gun_HeavySMG";
                    Pawn p=Spawn(map,Faction.OfPlayer,"D"+n,weapon,new IntVec3(r.Scenario=="staging"?110:119,0,111+n*3),r.Scenario=="rookie_knife"?2:8,true);
                    CombatLabState.Allies.Add(p);
                }
                CombatLabState.SetupMark("defenders_generated");
                for(int n=0;n<r.Attackers;n++)
                {
                    string weapon=r.Scenario.Contains("ranged")?"Gun_HeavySMG":"MeleeWeapon_Knife";
                    if(r.Scenario=="retreat_intent_furniture_contract" || r.Scenario=="retreat_intent_pursuer_contract")weapon="Gun_PumpShotgun";
                    if(r.Scenario=="mixed")weapon=n%3==0?"Gun_AssaultRifle":n%3==1?"MeleeWeapon_LongSword":"Gun_PumpShotgun";
                    int x=r.Scenario=="staging"?205:r.Scenario=="contact"?122:151+n%2*2;
                    Pawn p=Spawn(map,enemyFaction,"E"+n,weapon,new IntVec3(x,0,109+n*3),6,r.Scenario.Contains("ranged")||r.Scenario=="mixed",r.EnemyXenotype);
                    CombatLabState.Enemies.Add(p);
                }
                CombatLabState.SetupMark("attackers_generated");
                if(r.Cover)for(int z=106;z<=129;z++)if(z%3!=0)Building(map,"Sandbags",new IntVec3(120,0,z));
                if(r.Fortified)
                {
                    foreach(var t in map.listerThings.AllThings.Where(t=>t.Position.x==120 && t.Position.z>=100 && t.Position.z<=134).ToList())
                        if(t.def.destroyable)t.Destroy(DestroyMode.Vanish);
                    for(int z=100;z<=134;z++)Building(map,z%3==0?"Sandbags":"Wall",new IntVec3(120,0,z),z%3==0?null:"BlocksGranite");
                    for(int z=108;z<=126;z+=3)Building(map,"TrapSpike",new IntVec3(123,0,z),"Steel");
                }
                if(r.Fortified && r.DefenseLayout=="choke")
                {
                    foreach(var t in map.listerThings.AllThings.OfType<Building>().Where(t=>t.Position.x>=120 && t.Position.x<=145
                        && t.Position.z>=100 && t.Position.z<=134).ToList())t.Destroy(DestroyMode.Vanish);
                    var walls=new HashSet<IntVec3>();
                    for(int x=98;x<=120;x++)for(int z=100;z<=134;z++)
                        if((x==98 || x==120 || z==100 || z==134) && !(x==120 && z==114))walls.Add(new IntVec3(x,0,z));
                    for(int x=121;x<=145;x++){walls.Add(new IntVec3(x,0,113));walls.Add(new IntVec3(x,0,115));}
                    foreach(var cell in walls)Building(map,"Wall",cell,"BlocksGranite");
                    var exit=new IntVec3(108,0,100);exit.GetEdifice(map).Destroy(DestroyMode.Vanish);Building(map,"Door",exit,"BlocksGranite");
                    for(int x=124;x<=144;x+=4)Building(map,"TrapSpike",new IntVec3(x,0,114),"Steel");
                    for(int n=0;n<CombatLabState.Allies.Count;n++)
                    {var p=CombatLabState.Allies[n];p.DeSpawn();GenSpawn.Spawn(p,new IntVec3(114+n,0,114),map);}
                }
                if(r.Scenario=="kidnap_escape")
                {
                    var interceptor=CombatLabState.Allies[0];interceptor.DeSpawn();GenSpawn.Spawn(interceptor,new IntVec3(183,0,134),map);
                    Pawn captive=Spawn(map,Faction.OfPlayer,"Captive","Gun_Revolver",new IntVec3(151,0,109),3,false);
                    HealthUtility.DamageUntilDowned(captive);
                    CombatLabState.Captive=captive;
                    Pawn carrier=CombatLabState.Enemies[0];
                    captive.DeSpawn();
                    if(!captive.Downed || !carrier.carryTracker.TryStartCarry(captive))throw new InvalidOperationException("Native captive fixture not carried/downed");
                    LordMaker.MakeNewLord(enemyFaction,new LordJob_ExitMapBest(LocomotionUrgency.Jog,false,false),map,new[]{carrier});
                    if(CombatLabState.Enemies.Count>1)
                        LordMaker.MakeNewLord(enemyFaction,new LordJob_AssaultColony(enemyFaction,canKidnap:true,canTimeoutOrFlee:false),map,CombatLabState.Enemies.Skip(1));
                }
                if(r.Scenario=="kidnap_approach")
                {
                    Pawn captive=Spawn(map,Faction.OfPlayer,"Captive","Gun_Revolver",new IntVec3(131,0,109),3,false);
                    HealthUtility.DamageUntilDowned(captive);CombatLabState.Captive=captive;
                    if(captive.Dead || !captive.Downed)throw new InvalidOperationException("Native pre-pickup fixture requires a live downed captive");
                }
                if(r.Scenario=="idle_unreachable")
                {
                    var center=new IntVec3(204,0,156);
                    for(int dx=-2;dx<=2;dx++)for(int dz=-2;dz<=2;dz++)
                        if(Math.Abs(dx)==2 || Math.Abs(dz)==2)Building(map,"Wall",center+new IntVec3(dx,0,dz),"BlocksGranite");
                    Pawn probe=Spawn(map,enemyFaction,"Unreachable","MeleeWeapon_Knife",center,6,false);
                    CombatLabState.PassiveProbe=probe;
                    probe.jobs.StartJob(JobMaker.MakeJob(JobDefOf.Wait,1000000),JobCondition.InterruptForced);
                    foreach(Pawn p in CombatLabState.Allies)
                    {p.drafter.Drafted=true;p.jobs.StartJob(JobMaker.MakeJob(JobDefOf.Wait_Combat),JobCondition.InterruptForced);}
                }
                // Real ordinary food/sleep services for the long-stage test.
                for(int n=0;n<r.Defenders;n++)Building(map,"Bed",new IntVec3(108+n*2,0,116),"WoodLog");
                for(int n=0;n<20;n++){var food=ThingMaker.MakeThing(ThingDefOf.MealSurvivalPack);food.stackCount=10;GenSpawn.Spawn(food,new IntVec3(102+n%5,0,106+n/5),map);}
                if(r.Scenario=="staging")
                {
                    for(int x=98;x<=124;x++)for(int z=100;z<=132;z++)
                    {
                        var cell=new IntVec3(x,0,z);
                        if(x==98 || x==124 || z==100 || z==132)Building(map,x==124 && z==115?"Door":"Wall",cell,"WoodLog");
                        else {map.roofGrid.SetRoof(cell,RoofDefOf.RoofConstructed);map.terrainGrid.SetTerrain(cell,DefDatabase<TerrainDef>.GetNamed("WoodPlankFloor"));}
                    }
                    Building(map,"HorseshoesPin",new IntVec3(115,0,122),"Steel");
                    Building(map,"Table1x2c",new IntVec3(107,0,113),"WoodLog");
                    Building(map,"DiningChair",new IntVec3(106,0,113),"WoodLog");
                    for(int x=104;x<=116;x+=6)for(int z=104;z<=128;z+=6)Building(map,"Wall",new IntVec3(x,0,z),"WoodLog");
                }
                LordJob lord=r.Scenario=="staging" ? (LordJob)new LordJob_StageThenAttack(enemyFaction,new IntVec3(205,0,118),r.Seed,false,true,false,new IntRange(180000,180000))
                    : new LordJob_AssaultColony(enemyFaction,canKidnap:true,canTimeoutOrFlee:false);
                if(r.Scenario!="kidnap_escape" && !r.Scenario.StartsWith("contact_release_contract",StringComparison.Ordinal)
                    && r.Scenario!="care_threat_transition_contract" && !r.Scenario.StartsWith("intercept_perpendicular",StringComparison.Ordinal)
                    && r.Scenario!="ranged_priority_contract" && r.Scenario!="cover_handoff_contract" && !r.Scenario.StartsWith("cover_window_",StringComparison.Ordinal)
                    && !r.Scenario.StartsWith("friendly_fan_",StringComparison.Ordinal)
                    && !r.Scenario.StartsWith("execution_contract_",StringComparison.Ordinal)
                    && CombatLabState.Enemies.Any())LordMaker.MakeNewLord(enemyFaction,lord,map,CombatLabState.Enemies);
                if(r.Scenario=="kidnap_approach")
                    CombatLabState.Enemies[0].jobs.StartJob(JobMaker.MakeJob(JobDefOf.Kidnap,CombatLabState.Captive,new IntVec3(249,0,109)),JobCondition.InterruptForced);
                if(r.Fortified)foreach(Pawn p in CombatLabState.Allies)
                {p.drafter.Drafted=true;p.jobs.StartJob(JobMaker.MakeJob(JobDefOf.Wait_Combat),JobCondition.InterruptForced);}
                bool careRetreatContract=r.Scenario.StartsWith("care_retreat_contract",StringComparison.Ordinal);
                if(r.Scenario.StartsWith("care_triage_contract",StringComparison.Ordinal) || careRetreatContract)
                {
                    // A declared clinical fixture, never a raid qualification:
                    // ordinary generated work disabilities are retained. Injuries
                    // are constructed once before its held clock is released.
                    if(r.Attackers!=(careRetreatContract?1:0) || r.Defenders!=3 || r.Fortified)
                        throw new InvalidOperationException("Clinical contract cohort does not match its declared scenario");
                    var doctor=CombatLabState.Allies.FirstOrDefault(p=>!p.WorkTypeIsDisabled(WorkTypeDefOf.Doctor)
                        && !(p.skills?.GetSkill(SkillDefOf.Medicine)?.TotallyDisabled ?? true));
                    if(doctor==null)throw new InvalidOperationException("Declared cohort has no legal doctor; do not reroll");
                    var stable=CombatLabState.Allies.First(p=>p!=doctor);
                    var parts=doctor.health.hediffSet.GetNotMissingParts().Where(p=>p.def.defName=="Arm" || p.def.defName=="Leg").ToArray();
                    if(parts.Length!=4)throw new InvalidOperationException("Declared clinical fixture has unexpected native anatomy");
                    foreach(var part in parts)doctor.health.AddHediff(DefDatabase<HediffDef>.GetNamed("Cut"),part).Severity=7f;
                    var torso=stable.health.hediffSet.GetNotMissingParts().First(p=>p.def.defName=="Torso");
                    stable.health.AddHediff(DefDatabase<HediffDef>.GetNamed("Bruise"),torso).Severity=3f;
                    bool freshCareEntry=r.Scenario=="care_triage_contract_entry";
                    if(r.Scenario=="care_triage_contract_bleeding" || freshCareEntry)
                        stable.health.AddHediff(DefDatabase<HediffDef>.GetNamed("Cut"),torso).Severity=3f;
                    if(r.Scenario=="care_triage_contract_infection")
                        stable.health.AddHediff(DefDatabase<HediffDef>.GetNamed("Flu")).Severity=.2f;
                    if(doctor.Downed || doctor.Dead || doctor.health.hediffSet.BleedRateTotal<1.5f
                        || stable.Downed || !freshCareEntry && r.Scenario!="care_triage_contract_bleeding" && stable.health.hediffSet.BleedRateTotal!=0f)
                        throw new InvalidOperationException("Declared injuries did not produce the required live clinical state");
                    if(freshCareEntry)
                    {
                        foreach(var ally in CombatLabState.Allies)
                        {
                            ally.drafter.Drafted=false;
                            var waiting=JobMaker.MakeJob(JobDefOf.Wait,1200);waiting.playerForced=true;
                            ally.jobs.StartJob(waiting,JobCondition.InterruptForced);
                        }
                        CombatLabState.SetupMark("declared_free_competing_care_entry_before_held_baseline");
                    }
                    else if(!PawnHelper.AssignTendJob(doctor,stable))throw new InvalidOperationException("Native initial tend job rejected");
                    if(careRetreatContract)
                    {
                        // Initial API-boundary fixture only, not a raid result.
                        // The hostile is placed once before the held baseline.
                        var threat=CombatLabState.Enemies.Single();
                        threat.DeSpawn();GenSpawn.Spawn(threat,doctor.Position+IntVec3.East*6,map);
                    }
                    if(r.Scenario=="care_triage_contract_queued" || careRetreatContract && r.Scenario.EndsWith("_queue",StringComparison.Ordinal))
                    {
                        var later=JobMaker.MakeJob(JobDefOf.Wait,120);later.playerForced=true;
                        doctor.jobs.jobQueue.EnqueueLast(later);
                        if(r.Scenario=="care_retreat_contract_medical_queue")
                        {
                            var laterCare=JobMaker.MakeJob(JobDefOf.TendPatient,stable);
                            laterCare.playerForced=true;
                            doctor.jobs.jobQueue.EnqueueLast(laterCare);
                        }
                    }
                }
                if(r.Scenario=="intercept_perpendicular_contract" || r.Scenario=="intercept_perpendicular_exit_contract")
                {
                    // Declared initial geometry only. A carried native pawn and
                    // one native Goto-to-exit; never a forced combat outcome.
                    if(r.Defenders!=1 || r.Attackers!=1 || r.Cover || r.Fortified)
                        throw new InvalidOperationException("Perpendicular interception contract mismatch");
                    var actor=CombatLabState.Allies.Single();var carrier=CombatLabState.Enemies.Single();
                    actor.DeSpawn();GenSpawn.Spawn(actor,new IntVec3(120,0,50),map);
                    carrier.DeSpawn();GenSpawn.Spawn(carrier,new IntVec3(120,0,110),map);
                    var captive=Spawn(map,Faction.OfPlayer,"Captive","Gun_Revolver",new IntVec3(120,0,110),3,false);
                    HealthUtility.DamageUntilDowned(captive);CombatLabState.Captive=captive;
                    if(captive.Dead || !captive.Downed)throw new InvalidOperationException("Native live captive unavailable; no reroll");
                    captive.DeSpawn();
                    if(!carrier.carryTracker.TryStartCarry(captive))throw new InvalidOperationException("Native captive carry failed");
                    var exit=JobMaker.MakeJob(JobDefOf.Goto,new IntVec3(0,0,110));
                    exit.playerForced=true;exit.locomotionUrgency=LocomotionUrgency.Jog;
                    exit.exitMapOnArrival=r.Scenario=="intercept_perpendicular_exit_contract";
                    carrier.jobs.StartJob(exit,JobCondition.InterruptForced);
                    // A single declared initial tick starts the native path,
                    // before the held baseline and its RNG are recorded.
                    CombatLabState.Stepping=true;
                    try{typeof(TickManager).GetMethod("DoSingleTick",BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance).Invoke(Find.TickManager,null);}
                    finally{CombatLabState.Stepping=false;}
                    CombatLabState.StartTick=Find.TickManager.TicksGame;
                    CombatLabState.SetupMark("one_declared_native_path_initialization_tick_before_baseline");
                }
                if(r.Scenario.StartsWith("friendly_fan_",StringComparison.Ordinal))
                {
                    if(r.Defenders!=2 || r.Attackers!=2 || r.Cover || r.Fortified)
                        throw new InvalidOperationException("Friendly fan exact cohort required");
                    bool cap=r.Scenario=="friendly_fan_cap_contract";
                    bool support=r.Scenario=="friendly_fan_support_contract";
                    for(int n=0;n<2;n++)
                    {
                        var pawn=CombatLabState.Allies[n];pawn.jobs.StopAll();
                        foreach(var item in pawn.equipment.AllEquipmentListForReading.ToList())item.Destroy();
                        var cell=support?(n==0?new IntVec3(105,0,100):new IntVec3(110,0,101))
                            :n==0?new IntVec3(cap?115:109,0,114):cap?new IntVec3(119,0,120):r.Scenario=="friendly_fan_near_contract"?new IntVec3(113,0,114)
                            :r.Scenario=="friendly_fan_clear_contract"?new IntVec3(119,0,108):new IntVec3(119,0,113);
                        pawn.DeSpawn();GenSpawn.Spawn(pawn,cell,map);pawn.drafter.Drafted=true;
                        var wait=JobMaker.MakeJob(JobDefOf.Wait,1000000);wait.canUseRangedWeapon=false;
                        pawn.jobs.StartJob(wait,JobCondition.InterruptForced);
                        pawn.equipment.AddEquipment((ThingWithComps)ThingMaker.MakeThing(DefDatabase<ThingDef>.GetNamed(n==0?"Gun_HeavySMG":"Gun_AssaultRifle")));
                    }
                    for(int n=0;n<2;n++)
                    {
                        var pawn=CombatLabState.Enemies[n];pawn.jobs.StopAll();
                        pawn.DeSpawn();GenSpawn.Spawn(pawn,support?(n==0?new IntVec3(118,0,100):new IntVec3(120,0,112))
                            :n==0?(cap?new IntVec3(121,0,117):new IntVec3(126,0,114)):new IntVec3(145,0,140),map);
                        var wait=JobMaker.MakeJob(JobDefOf.Wait,1000000);wait.canUseRangedWeapon=false;
                        pawn.jobs.StartJob(wait,JobCondition.InterruptForced);
                        if(support)
                        {
                            foreach(var item in pawn.equipment.AllEquipmentListForReading.ToList())item.Destroy();
                            pawn.equipment.AddEquipment((ThingWithComps)ThingMaker.MakeThing(DefDatabase<ThingDef>.GetNamed("Gun_AssaultRifle")));
                        }
                    }
                    for(int z=105;z<=123;z++)if(!cap && !support && z!=114)
                    {
                        var wall=ThingMaker.MakeThing(ThingDefOf.Wall,ThingDefOf.BlocksGranite);
                        wall.SetFaction(Faction.OfPlayer);GenSpawn.Spawn(wall,new IntVec3(120,0,z),map);
                    }
                    if(support)
                    {
                        var actor=CombatLabState.Allies[0];var target=CombatLabState.Enemies[0];
                        var shot=JobMaker.MakeJob(JobDefOf.AttackStatic,target);shot.playerForced=true;
                        if(!CombatOrderHelper.Take(actor,ref shot))throw new InvalidOperationException("Declared selected support job rejected");
                        var assault=JobMaker.MakeJob(JobDefOf.AttackStatic,CombatLabState.Allies[1]);assault.playerForced=true;
                        target.jobs.StartJob(assault,JobCondition.InterruptForced);
                        var ids=new System.Collections.Generic.List<int>{actor.thingIDNumber};
                        CombatControlHelper.Remember(new CombatTacticRequestDto{Tactic="hold_cover",FighterIds=ids,TargetPawnId=target.thingIDNumber},
                            new CombatTacticResponseDto{Applied=true,Tactic="hold_cover",AttackingPawnIds=ids,TargetPawnId=target.thingIDNumber},map);
                    }
                    CombatLabState.StartTick=Find.TickManager.TicksGame;
                    CombatLabState.SetupMark("declared_stationary_friendly_fan_cohort_before_baseline");
                }
                if(r.Scenario=="ranged_priority_contract" || r.Scenario=="cover_handoff_contract" || r.Scenario.StartsWith("cover_window_",StringComparison.Ordinal))
                {
                    // Declared initial native jobs/geometry; read-only target
                    // selection contract, never a whole-raid qualification.
                    if(r.Defenders!=2 || r.Attackers!=2 || r.Cover || r.Fortified)
                        throw new InvalidOperationException("Ranged priority contract mismatch");
                    for(int n=0;n<2;n++)
                    {
                        var ally=CombatLabState.Allies[n];
                        foreach(var item in ally.equipment.AllEquipmentListForReading.ToList())item.Destroy();
                        ally.drafter.Drafted=false;
                        ally.DeSpawn();GenSpawn.Spawn(ally,new IntVec3(100,0,110+n*4),map);
                        ally.jobs.StartJob(JobMaker.MakeJob(JobDefOf.Wait,1000000),JobCondition.InterruptForced);
                    }
                    for(int n=0;n<2;n++)
                    {
                        var enemy=CombatLabState.Enemies[n];
                        foreach(var item in enemy.equipment.AllEquipmentListForReading.ToList())item.Destroy();
                        bool crossfire=r.Scenario=="cover_window_crossfire_contract";
                        enemy.equipment.AddEquipment((ThingWithComps)ThingMaker.MakeThing(DefDatabase<ThingDef>.GetNamed(n==0?"Gun_AssaultRifle":crossfire?"MeleeWeapon_Knife":"Gun_PumpShotgun")));
                        var initialCell=n==0?(crossfire?new IntVec3(123,0,121):new IntVec3(127,0,108)):(r.Scenario=="cover_window_occluded_contract" || crossfire)?new IntVec3(110,0,118)
                            :r.Scenario=="cover_window_flight_occluded_contract"?new IntVec3(111,0,122):new IntVec3(115,0,128);
                        enemy.DeSpawn();GenSpawn.Spawn(enemy,initialCell,map);
                        var move=JobMaker.MakeJob(JobDefOf.Goto,n==0?(crossfire?new IntVec3(123,0,122):new IntVec3(127,0,109)):new IntVec3(105,0,112));
                        move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                        enemy.jobs.StartJob(move,JobCondition.InterruptForced);
                    }
                    if(r.Scenario=="cover_handoff_contract" || r.Scenario.StartsWith("cover_window_",StringComparison.Ordinal))
                    {
                        for(int z=108;z<=110;z++)
                        {
                            var wall=ThingMaker.MakeThing(ThingDefOf.Wall,ThingDefOf.BlocksGranite);
                            wall.SetFaction(Faction.OfPlayer);GenSpawn.Spawn(wall,new IntVec3(102,0,z),map);
                        }
                    }
                    CombatLabState.Stepping=true;
                    try{typeof(TickManager).GetMethod("DoSingleTick",BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance).Invoke(Find.TickManager,null);}
                    finally{CombatLabState.Stepping=false;}
                    foreach(var ally in CombatLabState.Allies)
                    {
                        ally.drafter.Drafted=true;
                        var wait=r.Scenario.StartsWith("cover_window_",StringComparison.Ordinal)?JobMaker.MakeJob(JobDefOf.Wait,1000000):JobMaker.MakeJob(JobDefOf.Wait_Combat);
                        if(r.Scenario.StartsWith("cover_window_",StringComparison.Ordinal))wait.canUseRangedWeapon=false;
                        ally.jobs.StartJob(wait,JobCondition.InterruptForced);
                        // Equip only after initial waiting is established, so
                        // the path-initialization tick cannot start an aim.
                        // This is still before the held baseline/RNG capture.
                        ally.equipment.AddEquipment((ThingWithComps)ThingMaker.MakeThing(DefDatabase<ThingDef>.GetNamed("Gun_AssaultRifle")));
                        if(ally.stances.curStance is Stance_Busy || ally.WorkTagIsDisabled(WorkTags.Violent))
                            throw new InvalidOperationException($"Native initial gun {ally.thingIDNumber} stance={ally.stances.curStance.GetType().Name}, violenceDisabled={ally.WorkTagIsDisabled(WorkTags.Violent)}; no reroll");
                    }
                    if(r.Scenario=="cover_window_crossfire_contract")
                    {
                        // Declared synthetic native cooldown represents a gun
                        // still committed to its ordinary previous cycle. It
                        // is established before the held baseline, never used
                        // as evidence of actual earlier projectiles.
                        var actor=CombatLabState.Allies[0];var verb=actor.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
                        actor.stances.SetStance(new Stance_Cooldown(120,CombatLabState.Enemies[1],verb));
                    }
                    var ids=CombatLabState.Allies.Select(p=>p.thingIDNumber).ToList();
                    CombatControlHelper.Remember(new CombatTacticRequestDto{Tactic="hold_cover",FighterIds=ids,
                        TargetPawnId=CombatLabState.Enemies[0].thingIDNumber},
                        new CombatTacticResponseDto{Applied=true,Tactic="hold_cover",PositionedPawnIds=ids,
                            TargetPawnId=CombatLabState.Enemies[0].thingIDNumber},map);
                    CombatLabState.StartTick=Find.TickManager.TicksGame;
                    CombatLabState.SetupMark("one_declared_native_path_tick_and_initial_owned_waits_before_baseline");
                }
                if(r.Scenario.StartsWith("retreat_intent_",StringComparison.Ordinal))
                {
                    bool window=r.Scenario=="retreat_intent_uncovered_contract" || r.Scenario=="retreat_intent_covered_contract";
                    bool formation=r.Scenario.StartsWith("retreat_intent_formation",StringComparison.Ordinal);
                    bool clearFormation=r.Scenario=="retreat_intent_formation_clear_contract";
                    int count=r.Scenario=="retreat_intent_uncovered_contract"?1:3;
                    if(r.Defenders!=count || r.Attackers!=1 || r.Cover || r.Fortified)
                        throw new InvalidOperationException("Retreat intent requires its exact declared held fixture");
                    var actor=CombatLabState.Allies[0];var enemy=CombatLabState.Enemies[0];
                    var cells=formation?new[]{new IntVec3(117,0,114),new IntVec3(115,0,clearFormation?111:114),new IntVec3(113,0,clearFormation?111:114)}
                        :window?new[]{new IntVec3(120,0,100),new IntVec3(118,0,97),new IntVec3(118,0,103)}
                        :new[]{new IntVec3(120,0,100),new IntVec3(110,0,100),new IntVec3(110,0,103)};
                    for(int n=0;n<CombatLabState.Allies.Count;n++)
                    {
                        var ally=CombatLabState.Allies[n];ally.jobs.StopAll();
                        ally.DeSpawn();GenSpawn.Spawn(ally,cells[n],map);ally.drafter.Drafted=true;
                        if(window || formation){foreach(var item in ally.equipment.AllEquipmentListForReading.ToList())item.Destroy();
                            ally.equipment.AddEquipment((ThingWithComps)ThingMaker.MakeThing(DefDatabase<ThingDef>.GetNamed("Gun_AssaultRifle")));}
                    }
                    enemy.jobs.StopAll();enemy.DeSpawn();GenSpawn.Spawn(enemy,formation?new IntVec3(129,0,114):window?new IntVec3(145,0,100):new IntVec3(120,0,104),map);
                    var bed=ThingMaker.MakeThing(ThingDefOf.Bed,ThingDefOf.WoodLog);
                    bed.SetFaction(Faction.OfPlayer);GenSpawn.Spawn(bed,new IntVec3(120,0,105),map);
                    Thing target=r.Scenario=="retreat_intent_furniture_contract"?bed:(Thing)actor;
                    var assault=JobMaker.MakeJob(JobDefOf.AttackMelee,target);assault.playerForced=true;
                    enemy.jobs.StartJob(assault,JobCondition.InterruptForced);
                    foreach(var ally in CombatLabState.Allies)
                    {
                        var shot=JobMaker.MakeJob(JobDefOf.AttackStatic,enemy);shot.playerForced=true;
                        if(!CombatOrderHelper.Take(ally,ref shot))
                            throw new InvalidOperationException("Initial native selected gun job rejected; preserve partial");
                    }
                    var ids=CombatLabState.Allies.Select(p=>p.thingIDNumber).ToList();
                    CombatControlHelper.Remember(new CombatTacticRequestDto{Tactic="hold_cover",FighterIds=ids,
                        TargetPawnId=enemy.thingIDNumber},new CombatTacticResponseDto{Applied=true,Tactic="hold_cover",
                        AttackingPawnIds=ids,TargetPawnId=enemy.thingIDNumber},map);
                    CombatLabState.StartTick=Find.TickManager.TicksGame;
                    CombatLabState.SetupMark("declared_native_building_attack_or_real_pursuer_before_held_baseline");
                }
                if(r.Scenario.StartsWith("support_window_",StringComparison.Ordinal))
                {
                    if(r.Defenders!=2 || r.Attackers!=1 || r.Cover || r.Fortified)
                        throw new InvalidOperationException("Support window contract cohort mismatch");
                    bool unsafeLane=r.Scenario.EndsWith("_unsafe_contract",StringComparison.Ordinal);
                    var actor=CombatLabState.Allies[0];var buddy=CombatLabState.Allies[1];var enemy=CombatLabState.Enemies[0];
                    actor.DeSpawn();buddy.DeSpawn();enemy.DeSpawn();
                    // The buddy blocks the present firing lane. The only
                    // difference is four native map cells of enemy approach;
                    // no obstacle/weapon/stat/AI change after the baseline.
                    GenSpawn.Spawn(actor,new IntVec3(118,0,108),map);
                    GenSpawn.Spawn(buddy,new IntVec3(124,0,108),map);
                    GenSpawn.Spawn(enemy,new IntVec3(unsafeLane?128:132,0,108),map);
                    foreach(var item in actor.equipment.AllEquipmentListForReading.ToList())item.Destroy();
                    actor.equipment.AddEquipment((ThingWithComps)ThingMaker.MakeThing(DefDatabase<ThingDef>.GetNamed("Gun_AssaultRifle")));
                    actor.drafter.Drafted=true;
                    var hold=JobMaker.MakeJob(JobDefOf.Wait_Combat);hold.playerForced=true;hold.canUseRangedWeapon=false;
                    if(!CombatOrderHelper.Take(actor,ref hold))throw new InvalidOperationException("Initial held gun job rejected");
                    var pursuit=JobMaker.MakeJob(JobDefOf.AttackMelee,buddy);pursuit.playerForced=true;
                    enemy.jobs.StartJob(pursuit,JobCondition.InterruptForced);
                    enemy.pather.StartPath(buddy,PathEndMode.Touch);
                    var ids=new List<int>{actor.thingIDNumber};
                    CombatControlHelper.Remember(new CombatTacticRequestDto{Tactic="hold_cover",FighterIds=ids,TargetPawnId=enemy.thingIDNumber},
                        new CombatTacticResponseDto{Applied=true,Tactic="hold_cover",PreservedPawnIds=ids,TargetPawnId=enemy.thingIDNumber},map);
                    if(r.Scenario.Contains("_continue_") || r.Scenario.Contains("_foreign_"))
                        CombatControlHelper.TestDeclareSupport(actor,enemy,new IntVec3(119,0,108),r.Scenario.Contains("_foreign_"));
                    CombatLabState.SetupMark("declared_native_support_window_geometry_before_held_baseline");
                }
                if(r.Scenario.StartsWith("postcombat_entry_",StringComparison.Ordinal))
                {
                    bool cleanup=r.Scenario.StartsWith("postcombat_entry_cleanup_",StringComparison.Ordinal);
                    bool extra=cleanup && r.Scenario=="postcombat_entry_cleanup_worker_contract";
                    bool live=r.Scenario=="postcombat_entry_hostile_contract";
                    if(r.Defenders!=(extra?5:4) || r.Attackers!=((live || cleanup)?1:0) || r.Cover || r.Fortified)
                        throw new InvalidOperationException("Postcombat entry cohort mismatch");
                    var doctors=CombatLabState.Allies.Take(4).Where(p=>!p.WorkTypeIsDisabled(WorkTypeDefOf.Doctor)
                        && !(p.skills?.GetSkill(SkillDefOf.Medicine)?.TotallyDisabled ?? true)).Take(2).ToArray();
                    if(doctors.Length!=2)throw new InvalidOperationException("Two legal native doctors unavailable; no reroll");
                    var patients=CombatLabState.Allies.Take(4).Except(doctors).ToArray();
                    foreach(var ally in CombatLabState.Allies){ally.jobs.StopAll();ally.DeSpawn();}
                    GenSpawn.Spawn(doctors[0],new IntVec3(110,0,40),map);
                    GenSpawn.Spawn(doctors[1],new IntVec3(96,0,126),map);
                    GenSpawn.Spawn(patients[0],new IntVec3(122,0,28),map);
                    GenSpawn.Spawn(patients[1],new IntVec3(110,0,116),map);
                    foreach(var part in patients[0].health.hediffSet.GetNotMissingParts()
                        .Where(p=>p.def.defName=="Arm" || p.def.defName=="Leg").ToArray())
                        patients[0].health.AddHediff(DefDatabase<HediffDef>.GetNamed("Cut"),part).Severity=7f;
                    var minorTorso=patients[1].health.hediffSet.GetNotMissingParts().First(p=>p.def.defName=="Torso");
                    patients[1].health.AddHediff(DefDatabase<HediffDef>.GetNamed("Cut"),minorTorso).Severity=3f;
                    foreach(var patient in patients)
                    {
                        patient.drafter.Drafted=false;
                        patient.health.AddHediff(HediffDefOf.BloodLoss).Severity=.81f;
                    }
                    if(patients.Any(p=>p.Dead || !p.Downed) || patients[0].health.hediffSet.BleedRateTotal<1.5f)
                        throw new InvalidOperationException("Declared blood-loss injuries not native downed; preserve partial");
                    foreach(var doctor in doctors)
                    {
                        doctor.drafter.Drafted=true;
                        var hold=JobMaker.MakeJob(JobDefOf.Wait_Combat);hold.playerForced=true;hold.canUseRangedWeapon=false;
                        if(!CombatOrderHelper.Take(doctor,ref hold))throw new InvalidOperationException("Declared selected doctor hold rejected");
                    }
                    var ids=doctors.Select(p=>p.thingIDNumber).ToList();
                    CombatControlHelper.Remember(new CombatTacticRequestDto{Tactic="hold_cover",FighterIds=ids},
                        new CombatTacticResponseDto{Applied=true,Tactic="hold_cover",PreservedPawnIds=ids},map);
                    if(r.Scenario=="postcombat_entry_foreign_contract")
                    {
                        var later=JobMaker.MakeJob(JobDefOf.Wait,120);later.playerForced=true;
                        doctors[0].jobs.jobQueue.EnqueueLast(later);
                    }
                    if(r.Scenario=="postcombat_entry_care_contract")
                    {
                        doctors[0].drafter.Drafted=false;
                        if(!PawnHelper.AssignTendJob(doctors[0],patients[1]))
                            throw new InvalidOperationException("Declared protected current care unavailable");
                    }
                    if(cleanup)
                    {
                        // Declared initial clinical/cleanup boundary only.
                        // All work disabilities, genes, medicine and attack stats remain native.
                        var second=patients[1];
                        foreach(var h in second.health.hediffSet.hediffs.Where(h=>h.def==HediffDefOf.BloodLoss).ToArray())
                            second.health.RemoveHediff(h);
                        if(r.Scenario!="postcombat_entry_cleanup_nonurgent_contract")
                            foreach(var part in second.health.hediffSet.GetNotMissingParts()
                                .Where(p=>p.def.defName=="Arm" || p.def.defName=="Leg").ToArray())
                                second.health.AddHediff(DefDatabase<HediffDef>.GetNamed("Cut"),part).Severity=7f;
                        if(second.Dead || second.Downed)
                            throw new InvalidOperationException("Declared second mobile patient unavailable; no reroll");
                        var bed=second.Position.GetThingList(map).OfType<Building_Bed>().FirstOrDefault();
                        if(bed==null)
                        {
                            Building(map,"Bed",second.Position,"WoodLog");
                            bed=second.Position.GetThingList(map).OfType<Building_Bed>().FirstOrDefault();
                        }
                        if(bed==null || !PawnHelper.AssignBedRest(second,bed))
                            throw new InvalidOperationException("Declared ordinary bed-rest job unavailable");
                        doctors[0].drafter.Drafted=false;
                        if(!PawnHelper.AssignTendJob(doctors[0],patients[0]))
                            throw new InvalidOperationException("Declared existing first patient care unavailable");
                        doctors[1].drafter.Drafted=false;
                        var wait=JobMaker.MakeJob(JobDefOf.Wait,12000);wait.playerForced=true;
                        doctors[1].jobs.StartJob(wait,JobCondition.InterruptForced);
                        if(r.Scenario=="postcombat_entry_cleanup_queued_contract")
                            doctors[1].jobs.jobQueue.EnqueueLast(JobMaker.MakeJob(JobDefOf.Wait,120));
                        if(extra)
                        {
                            var independent=CombatLabState.Allies[4];GenSpawn.Spawn(independent,new IntVec3(78,0,126),map);
                            independent.drafter.Drafted=false;
                            var idle=JobMaker.MakeJob(JobDefOf.Wait,12000);idle.playerForced=true;
                            independent.jobs.StartJob(idle,JobCondition.InterruptForced);
                            if(independent.WorkTagIsDisabled(WorkTags.Violent))
                                throw new InvalidOperationException("Declared independent native fighter unavailable; no reroll");
                        }
                        var hostile=CombatLabState.Enemies.Single();hostile.jobs.StopAll();hostile.DeSpawn();
                        GenSpawn.Spawn(hostile,new IntVec3(100,0,126),map);
                        hostile.health.AddHediff(HediffDefOf.BloodLoss).Severity=.81f;
                        if(hostile.Dead || !hostile.Downed)
                            throw new InvalidOperationException("Declared native downed cleanup target unavailable");
                        CombatLabState.SetupMark("declared_existing_care_free_second_clinician_mobile_patient_and_downed_raider_before_baseline");
                    }
                    CombatLabState.SetupMark("declared_two_selected_doctors_and_two_downed_patients_before_initial_care");
                }

                if(r.Scenario.StartsWith("ranged_rotation_",StringComparison.Ordinal))
                {
                    if(r.Defenders!=3 || r.Attackers!=2 || r.Cover || r.Fortified)
                        throw new InvalidOperationException("Targeted rotation cohort mismatch");
                    bool warming=r.Scenario=="ranged_rotation_warmup_contract";
                    bool moving=r.Scenario=="ranged_rotation_moving_contract";
                    var cells=new[]{new IntVec3(118,0,100),new IntVec3(118,0,104),new IntVec3(118,0,108)};
                    foreach(var ally in CombatLabState.Allies)ally.DeSpawn();
                    foreach(var enemy in CombatLabState.Enemies)enemy.DeSpawn();
                    for(int n=0;n<3;n++)
                    {
                        var ally=CombatLabState.Allies[n];GenSpawn.Spawn(ally,cells[n],map);
                        foreach(var item in ally.equipment.AllEquipmentListForReading.ToList())item.Destroy();
                        ally.equipment.AddEquipment((ThingWithComps)ThingMaker.MakeThing(DefDatabase<ThingDef>.GetNamed(
                            n==1 && warming?"Gun_BoltActionRifle":"Gun_AssaultRifle")));
                        ally.drafter.Drafted=true;
                    }
                    // A normal completed short wall offers a safer rear firing cell
                    // toward the second observed hostile, rather than a forced safe shot.
                    for(int z=102;z<=106;z++)Building(map,"Wall",new IntVec3(116,0,z),"BlocksGranite");
                    var primary=CombatLabState.Enemies[0];var secondary=CombatLabState.Enemies[1];
                    GenSpawn.Spawn(primary,new IntVec3(135,0,104),map);
                    GenSpawn.Spawn(secondary,new IntVec3(115,0,80),map);
                    foreach(var item in secondary.equipment.AllEquipmentListForReading.ToList())item.Destroy();
                    secondary.equipment.AddEquipment((ThingWithComps)ThingMaker.MakeThing(DefDatabase<ThingDef>.GetNamed("MeleeWeapon_Knife")));

                    foreach(var item in primary.equipment.AllEquipmentListForReading.ToList())item.Destroy();
                    primary.equipment.AddEquipment((ThingWithComps)ThingMaker.MakeThing(DefDatabase<ThingDef>.GetNamed("Gun_SniperRifle")));
                    var aimed=JobMaker.MakeJob(JobDefOf.AttackStatic,CombatLabState.Allies[r.Scenario=="ranged_rotation_other_contract"?0:1]);
                    aimed.playerForced=true;primary.jobs.StartJob(aimed,JobCondition.InterruptForced);
                    var wait=JobMaker.MakeJob(JobDefOf.Wait,12000);wait.playerForced=true;
                    secondary.jobs.StartJob(wait,JobCondition.InterruptForced);
                    for(int n=0;n<3;n++)
                    {
                        var ally=CombatLabState.Allies[n];bool fire=n!=1 || warming;
                        var job=fire?JobMaker.MakeJob(JobDefOf.AttackStatic,primary):JobMaker.MakeJob(JobDefOf.Wait_Combat,12000);
                        job.playerForced=true;job.canUseRangedWeapon=fire;
                        if(moving && n==0){job=JobMaker.MakeJob(JobDefOf.Goto,new IntVec3(118,0,90));job.playerForced=true;job.locomotionUrgency=LocomotionUrgency.Jog;}
                        if(!CombatOrderHelper.Take(ally,ref job))throw new InvalidOperationException("Rotation initial native job rejected");
                        if(moving && n==0)CombatControlHelper.RememberMove(ally,job,CombatOrderHelper.QueueShot(ally,primary));
                        if(n==1 && r.Scenario=="ranged_rotation_queued_contract")
                            ally.jobs.jobQueue.EnqueueLast(JobMaker.MakeJob(JobDefOf.Wait,120));
                    }
                    var ids=CombatLabState.Allies.Select(p=>p.thingIDNumber).ToList();
                    CombatControlHelper.Remember(new CombatTacticRequestDto{Tactic="hold_cover",FighterIds=ids,TargetPawnId=primary.thingIDNumber},
                        new CombatTacticResponseDto{Applied=true,Tactic="hold_cover",AttackingPawnIds=ids,TargetPawnId=primary.thingIDNumber},map);
                    CombatLabState.SetupMark("declared_one_targeted_ranged_lane_rear_wall_and_second_firing_target_before_held_baseline");
                }

                if(r.Scenario.StartsWith("focus_recovery_ranged_",StringComparison.Ordinal))
                {
                    if(r.Defenders!=3 || r.Attackers!=2 || r.Cover || r.Fortified)
                        throw new InvalidOperationException("Focus recovery cohort mismatch");
                    bool warming=r.Scenario.EndsWith("_warmup_contract",StringComparison.Ordinal);
                    var cells=new[]{new IntVec3(100,0,110),new IntVec3(100,0,114),new IntVec3(100,0,118)};
                    foreach(var ally in CombatLabState.Allies)ally.DeSpawn();
                    foreach(var enemy in CombatLabState.Enemies)enemy.DeSpawn();
                    for(int n=0;n<3;n++)
                    {
                        var ally=CombatLabState.Allies[n];GenSpawn.Spawn(ally,cells[n],map);
                        foreach(var item in ally.equipment.AllEquipmentListForReading.ToList())item.Destroy();
                        ally.equipment.AddEquipment((ThingWithComps)ThingMaker.MakeThing(DefDatabase<ThingDef>.GetNamed("Gun_AssaultRifle")));
                        ally.drafter.Drafted=true;
                    }
                    var buddy=CombatLabState.Allies[1];var committed=CombatLabState.Enemies[1];
                    for(int n=0;n<2;n++)
                    {
                        var enemy=CombatLabState.Enemies[n];GenSpawn.Spawn(enemy,new IntVec3(n==0?116:128,0,114),map);
                        foreach(var item in enemy.equipment.AllEquipmentListForReading.ToList())item.Destroy();
                        enemy.equipment.AddEquipment((ThingWithComps)ThingMaker.MakeThing(DefDatabase<ThingDef>.GetNamed("Gun_AssaultRifle")));
                        var fire=JobMaker.MakeJob(JobDefOf.AttackStatic,buddy);fire.playerForced=true;
                        enemy.jobs.StartJob(fire,JobCondition.InterruptForced);
                    }
                    foreach(var ally in CombatLabState.Allies)
                    {
                        var shot=JobMaker.MakeJob(JobDefOf.AttackStatic,committed);shot.playerForced=true;
                        if(!CombatOrderHelper.Take(ally,ref shot))throw new InvalidOperationException("Initial focus recovery shot rejected");
                        var verb=ally.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
                        ally.stances.SetStance(warming?(Stance)new Stance_Warmup(60,committed,verb):new Stance_Cooldown(40,committed,verb));
                    }
                    var ids=CombatLabState.Allies.Select(p=>p.thingIDNumber).ToList();
                    CombatControlHelper.Remember(new CombatTacticRequestDto{Tactic="hold_cover",FighterIds=ids,TargetPawnId=committed.thingIDNumber},
                        new CombatTacticResponseDto{Applied=true,Tactic="hold_cover",AttackingPawnIds=ids,TargetPawnId=committed.thingIDNumber},map);
                    CombatLabState.SetupMark("declared_three_native_gun_cooldowns_or_warmups_two_stationary_ranged_targets_before_held_baseline");
                }

                if(r.Scenario.StartsWith("focus_deadline_",StringComparison.Ordinal))
                {
                    if(r.Defenders!=3 || r.Attackers!=2 || r.Cover || r.Fortified)
                        throw new InvalidOperationException("Focus deadline cohort mismatch");
                    bool self=r.Scenario.StartsWith("focus_deadline_self_",StringComparison.Ordinal);
                    bool far=r.Scenario.EndsWith("_far_contract",StringComparison.Ordinal);
                    bool warming=r.Scenario.EndsWith("_warmup_contract",StringComparison.Ordinal);
                    bool covered=r.Scenario=="focus_deadline_self_covered_contract";
                    var cells=new[]{new IntVec3(118,0,100),new IntVec3(far && !self?110:118,0,104),new IntVec3(118,0,108)};
                    foreach(var ally in CombatLabState.Allies)ally.DeSpawn();
                    foreach(var enemy in CombatLabState.Enemies)enemy.DeSpawn();
                    for(int n=0;n<3;n++)
                    {
                        var ally=CombatLabState.Allies[n];GenSpawn.Spawn(ally,cells[n],map);
                        foreach(var item in ally.equipment.AllEquipmentListForReading.ToList())item.Destroy();
                        ally.equipment.AddEquipment((ThingWithComps)ThingMaker.MakeThing(DefDatabase<ThingDef>.GetNamed("Gun_AssaultRifle")));
                        ally.drafter.Drafted=true;
                    }
                    var buddy=CombatLabState.Allies[1];var committed=CombatLabState.Enemies[1];
                    for(int n=0;n<2;n++)
                    {
                        var enemy=CombatLabState.Enemies[n];
                        GenSpawn.Spawn(enemy,self?new IntVec3(n==0?(far?148:135):131,0,n==0?(far?106:100):104):
                            new IntVec3(far?(n==0?141:144):(n==0?135:139),0,104),map);
                        var pursue=JobMaker.MakeJob(JobDefOf.AttackMelee,self && n==0?CombatLabState.Allies[0]:buddy);pursue.playerForced=true;
                        enemy.jobs.StartJob(pursue,JobCondition.InterruptForced);enemy.pather.StartPath(self && n==0?CombatLabState.Allies[0]:buddy,PathEndMode.Touch);
                    }
                    for(int n=0;n<3;n++)
                    {
                        var ally=CombatLabState.Allies[n];var initialTarget=covered && n>0?CombatLabState.Enemies[0]:committed;
                        var shot=JobMaker.MakeJob(JobDefOf.AttackStatic,initialTarget);shot.playerForced=true;
                        if(!CombatOrderHelper.Take(ally,ref shot))throw new InvalidOperationException("Declared initial focus job rejected");
                        var verb=ally.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
                        ally.stances.SetStance(n==0 && !warming || covered && n>0?
                            (Stance)new Stance_Cooldown(40,initialTarget,verb):new Stance_Warmup(60,initialTarget,verb));
                    }
                    var ids=CombatLabState.Allies.Select(p=>p.thingIDNumber).ToList();
                    CombatControlHelper.Remember(new CombatTacticRequestDto{Tactic="hold_cover",FighterIds=ids,TargetPawnId=committed.thingIDNumber},
                        new CombatTacticResponseDto{Applied=true,Tactic="hold_cover",AttackingPawnIds=ids,TargetPawnId=committed.thingIDNumber},map);
                    CombatLabState.SetupMark("declared_native_group_focus_and_gun_stances_before_held_baseline");
                }

                if(r.Scenario=="care_threat_transition_contract")
                {
                    // One declared initial clinical/LOS transition, never raid credit.
                    // All anatomy, work restrictions and combat stats are native.
                    if(r.Defenders!=3 || r.Attackers!=1 || r.Fortified || r.Cover)
                        throw new InvalidOperationException("Care transition contract scope mismatch");
                    var doctor=CombatLabState.Allies.FirstOrDefault(p=>!p.WorkTypeIsDisabled(WorkTypeDefOf.Doctor)
                        && !(p.skills?.GetSkill(SkillDefOf.Medicine)?.TotallyDisabled ?? true));
                    if(doctor==null)throw new InvalidOperationException("No legal native doctor; do not reroll");
                    var patient=CombatLabState.Allies.First(p=>p!=doctor);
                    foreach(var ally in CombatLabState.Allies)
                        foreach(var item in ally.equipment.AllEquipmentListForReading.ToList())item.Destroy();
                    var parts=patient.health.hediffSet.GetNotMissingParts().Where(p=>p.def.defName=="Arm" || p.def.defName=="Leg").ToArray();
                    if(parts.Length!=4)throw new InvalidOperationException("Unexpected clinical anatomy");
                    foreach(var part in parts)patient.health.AddHediff(DefDatabase<HediffDef>.GetNamed("Cut"),part).Severity=7f;
                    if(doctor.Dead || doctor.Downed || patient.Dead || patient.Downed)
                        throw new InvalidOperationException("Declared cohort not legally mobile; no retry");
                    patient.jobs.StartJob(JobMaker.MakeJob(JobDefOf.Wait,1200),JobCondition.InterruptForced);
                    if(!PawnHelper.AssignTendJob(doctor,patient))throw new InvalidOperationException("Initial native tending rejected");
                    var enemy=CombatLabState.Enemies.Single();
                    foreach(var item in enemy.equipment.AllEquipmentListForReading.ToList())item.Destroy();
                    var weapon=ThingMaker.MakeThing(DefDatabase<ThingDef>.GetNamed("Gun_HeavySMG")) as ThingWithComps;
                    enemy.equipment.AddEquipment(weapon);
                    enemy.DeSpawn();GenSpawn.Spawn(enemy,doctor.Position+IntVec3.East*20+IntVec3.South*2,map);
                    for(int z=-6;z<=1;z++)Building(map,"Wall",doctor.Position+IntVec3.East*10+IntVec3.North*z,"BlocksGranite");
                    var move=JobMaker.MakeJob(JobDefOf.Goto,doctor.Position+IntVec3.East*20+IntVec3.North*4);
                    move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                    enemy.jobs.StartJob(move,JobCondition.InterruptForced);
                    var attack=JobMaker.MakeJob(JobDefOf.AttackStatic,doctor);attack.playerForced=true;
                    attack.maxNumStaticAttacks=999;
                    enemy.jobs.jobQueue.EnqueueLast(attack);
                }
                if(r.Scenario.StartsWith("contact_release_contract",StringComparison.Ordinal))
                {
                    // Declared order-continuation contract, never raid credit:
                    // native sprinting creates real separation without stat,
                    // health, accuracy or collision changes after setup.
                    if(r.Defenders!=3 || r.Attackers!=1 || r.Fortified)
                        throw new InvalidOperationException("Contact contract requires three civilians and one scripted moving enemy");
                    var actor=CombatLabState.Allies[0];var enemy=CombatLabState.Enemies[0];
                    foreach(var item in actor.equipment.AllEquipmentListForReading.ToList())item.Destroy();
                    enemy.DeSpawn();GenSpawn.Spawn(enemy,actor.Position+IntVec3.East*(r.Scenario.EndsWith("_distant",StringComparison.Ordinal)?5:1),map);
                    var leave=JobMaker.MakeJob(JobDefOf.Goto,actor.Position+IntVec3.East*12);
                    leave.playerForced=true;leave.locomotionUrgency=LocomotionUrgency.Sprint;
                    enemy.jobs.StartJob(leave,JobCondition.InterruptForced);
                    if(r.Scenario.EndsWith("_busy",StringComparison.Ordinal))
                        actor.stances.SetStance(new Stance_Cooldown(90,enemy,actor.meleeVerbs.TryGetMeleeVerb(enemy)));
                }
                if(r.Scenario=="burning_patient_free_contract" || r.Scenario=="burning_patient_queued_contract")
                {
                    if(r.Defenders!=4 || r.Attackers!=0 || r.Cover || r.Fortified)
                        throw new InvalidOperationException("Burning patient contract requires its declared four-pawn initial setup");
                    foreach(var ally in CombatLabState.Allies){ally.jobs.StopAll();ally.drafter.Drafted=false;}
                    var patient=CombatLabState.Allies[3];
                    patient.health.AddHediff(HediffDefOf.Anesthetic).Severity=1f;
                    FireUtility.TryAttachFire(patient,.45f,null);
                    if(!patient.Downed || BurningPawnSafetyHelper.AttachedFire(patient)==null)
                        throw new InvalidOperationException("Declared patient did not become downed and burning; no reroll");
                    var work=DefDatabase<WorkTypeDef>.GetNamed("Firefighter");
                    var worker=CombatLabState.Allies.FirstOrDefault(p=>p!=patient && !p.WorkTypeIsDisabled(work));
                    if(worker==null)throw new InvalidOperationException("No native capable initial firefighter; no capability override");
                    var ground=(Fire)GenSpawn.Spawn(ThingDefOf.Fire,new IntVec3(132,0,114),map);ground.fireSize=.2f;
                    worker.jobs.StartJob(JobMaker.MakeJob(JobDefOf.BeatFire,ground),JobCondition.InterruptForced);
                    if(r.Scenario=="burning_patient_queued_contract")
                        worker.jobs.jobQueue.EnqueueFirst(JobMaker.MakeJob(JobDefOf.TendPatient,patient));
                    CombatLabState.SetupMark("declared_burning_downed_patient_and_normal_ground_fire_job_before_baseline");
                }
                CombatLabState.InitialRandomState=CombatLabState.RandomProperty?.GetValue(null,null);
                CombatLabState.SetupMark("native_fixture_ready");
                CombatLabExecutionProbe.Initialize(r.Scenario,map);
                prepared=CombatLabState.State();
            }
            finally{Rand.PopState();}
            if(CombatLabState.InitialRandomState==null || CombatLabState.RandomProperty?.CanWrite!=true)
                throw new InvalidOperationException("Native initial random state unavailable; fixture not qualified");
            CombatLabState.RandomProperty.SetValue(null,CombatLabState.InitialRandomState,null);
            await context.SendJsonResponse(ApiResult<object>.Ok(prepared));
        }
        [Post("/api/v1/combat-lab/step")]
        public async Task Step(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            if(r.Pause)Find.TickManager.Pause();
            if(CombatLabState.HoldInitial && r.Ticks>0)throw new InvalidOperationException("Initial laboratory clock is still held; no ticks stepped");
            var method=typeof(TickManager).GetMethod("DoSingleTick",BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance);
            if(method==null)throw new InvalidOperationException("Native single tick unavailable; do not replace with a simulated result");
            CombatLabState.Stepping=true;
            try
            {
                for(int n=0;n<Math.Min(1200,Math.Max(0,r.Ticks));n++)
                {method.Invoke(Find.TickManager,null);CombatLabState.StepTicks++;CombatLabState.Sample();}
            }
            catch(Exception ex)
            {throw new InvalidOperationException("Laboratory tick error at "+Find.TickManager.TicksGame+": "+(ex.InnerException ?? ex).ToString());}
            finally{CombatLabState.Stepping=false;}
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabState.State(r.IncludeTrace)));
        }
        [Get("/api/v1/combat-lab/state")]
        public async Task State(HttpListenerContext context)
        {CombatLabState.Guard(context.Request.QueryString["campaign_id"]);await context.SendJsonResponse(ApiResult<object>.Ok(
            CombatLabState.State(!string.Equals(context.Request.QueryString["include_trace"],"false",StringComparison.OrdinalIgnoreCase))));}
        [Post("/api/v1/combat-lab/cover-handoff-probe")]
        public async Task CoverHandoffProbe(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabCoverHandoffProbe.Run()));
        }
        [Post("/api/v1/combat-lab/execution-probe")]
        public async Task ExecutionProbe(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabExecutionProbe.Run(r.Scenario)));
        }
        [Post("/api/v1/combat-lab/fire-care-probe")]
        public async Task FireCareProbe(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabFireCareProbe.Run(r.Scenario)));
        }
        [Post("/api/v1/combat-lab/care-exposure-probe")]
        public async Task CareExposureProbe(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabCareExposureProbe.Run(r.Scenario)));
        }
        [Post("/api/v1/combat-lab/http-budget-probe")]
        public async Task HttpBudgetProbe(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabHttpBudgetProbe.Arm(r.Scenario)));
        }
        [Post("/api/v1/combat-lab/team-care-probe")]
        public async Task TeamCareProbe(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabTeamCareProbe.Run(r.Scenario)));
        }
        [Post("/api/v1/combat-lab/prepared-post-probe")]
        public async Task PreparedPostProbe(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabPreparedPostProbe.Run()));
        }
        [Post("/api/v1/combat-lab/friendly-fan-probe")]
        public async Task FriendlyFanProbe(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabFriendlyFanProbe.Run()));
        }
        [Post("/api/v1/combat-lab/cover-shot-probe")]
        public async Task CoverShotProbe(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabCoverShotProbe.Run()));
        }
        [Post("/api/v1/combat-lab/retreat-intent-probe")]
        public async Task RetreatIntentProbe(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabRetreatIntentProbe.Run()));
        }
        [Post("/api/v1/combat-lab/support-caller-probe")]
        public async Task SupportCallerProbe(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabSupportCallerProbe.Run()));
        }
        [Post("/api/v1/combat-lab/support-window-probe")]
        public async Task SupportWindowProbe(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabSupportWindowProbe.Run()));
        }
        [Post("/api/v1/combat-lab/focus-recovery-probe")]
        public async Task FocusRecoveryProbe(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabFocusRecoveryProbe.Run()));
        }
        [Post("/api/v1/combat-lab/focus-deadline-probe")]
        public async Task FocusDeadlineProbe(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabFocusDeadlineProbe.Run()));
        }
        [Post("/api/v1/combat-lab/observed-route-probe")]
        public async Task ObservedRouteProbe(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabObservedRouteProbe.Run()));
        }
        [Get("/api/v1/combat-lab/carrier-selection-budget-probe")]
        public async Task CarrierSelectionBudgetProbe(HttpListenerContext context)
        {
            CombatLabState.Guard(context.Request.QueryString["campaign_id"],context.Request.QueryString["expected_native_instance_id"]);
            int actorId=int.Parse(context.Request.QueryString["actor_id"]),targetId=int.Parse(context.Request.QueryString["target_id"]);
            var actor=CombatLabState.Allies.Single(p=>p.thingIDNumber==actorId);
            var target=CombatLabState.Enemies.Single(p=>p.thingIDNumber==targetId);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatCarrierInterceptHelper.TestSelectionBudget(actor,target)));
        }
        [Get("/api/v1/combat-lab/carrier-cell-probe")]
        public async Task CarrierCellProbe(HttpListenerContext context)
        {
            CombatLabState.Guard(context.Request.QueryString["campaign_id"],context.Request.QueryString["expected_native_instance_id"]);
            if(!int.TryParse(context.Request.QueryString["actor_id"],out var actorId)
                || !int.TryParse(context.Request.QueryString["target_id"],out var targetId)
                || !int.TryParse(context.Request.QueryString["center_x"],out var x)
                || !int.TryParse(context.Request.QueryString["center_z"],out var z))throw new ArgumentException("Explicit candidate scope required");
            var actor=CombatLabState.Allies.Single(p=>p.thingIDNumber==actorId);
            var target=CombatLabState.Enemies.Single(p=>p.thingIDNumber==targetId);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatCarrierInterceptHelper.TestCandidateGrid(actor,target,new IntVec3(x,0,z))));
        }
        [Get("/api/v1/combat-lab/priority-probe")]
        public async Task PriorityProbe(HttpListenerContext context)
        {CombatLabState.Guard(context.Request.QueryString["campaign_id"],context.Request.QueryString["expected_native_instance_id"]);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabPriorityProbe.Read()));}
        [Post("/api/v1/combat-lab/begin")]
        public async Task Begin(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            if(CombatLabState.Map!=Find.CurrentMap || !CombatLabState.HoldInitial || CombatLabState.StepTicks!=0)
                throw new InvalidOperationException("Only the held initial laboratory fixture can be started once");
            CombatControlHelper.TestDisabled=!r.Micro;
            CombatLabState.RandomProperty.SetValue(null,CombatLabState.InitialRandomState,null);
            string applied=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            CombatLabState.HoldInitial=false;
            await context.SendJsonResponse(ApiResult<object>.Ok(new{released_initial_hold=true,tick=Find.TickManager.TicksGame,initial_rng_applied=applied,micro_enabled=r.Micro}));
        }
        [Post("/api/v1/combat-lab/ranged-rotation-probe")]
        public async Task RangedRotationProbe(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabRangedRotationProbe.Run()));
        }
        [Post("/api/v1/combat-lab/release-current")]
        public async Task ReleaseCurrent(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            if(CombatLabState.Map!=Find.CurrentMap || !CombatLabState.HoldInitial || CombatLabState.StepTicks!=0
                || !(CombatLabState.Scenario.StartsWith("postcombat_entry_",StringComparison.Ordinal) || CombatLabState.Scenario.StartsWith("ranged_rotation_",StringComparison.Ordinal)
                    || CombatLabState.Scenario=="cover_handoff_contract" || CombatLabState.Scenario.StartsWith("cover_window_",StringComparison.Ordinal)
                    || CombatLabState.Scenario.StartsWith("friendly_fan_",StringComparison.Ordinal) || CombatLabState.LoadedBaseline))
                throw new InvalidOperationException("Current-state release is only for the declared held clinical entry fixture");
            string before=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            CombatControlHelper.TestDisabled=!r.Micro;
            CombatLabState.HoldInitial=false;
            string after=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            await context.SendJsonResponse(ApiResult<object>.Ok(new{released_initial_hold=true,tick=Find.TickManager.TicksGame,
                current_rng_before=before,current_rng_after=after,current_rng_preserved=before==after,
                micro_enabled=r.Micro,meaning="Continue after ordinary native clinical actions without resetting their RNG consumption"}));
        }

        [Post("/api/v1/combat-lab/bind-initial-save")]
        public async Task BindInitialSave(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            if(CombatLabState.Allies.Any() || CombatLabState.Enemies.Any() || Find.TickManager.TicksGame!=r.ExpectedTick || r.ExpectedTick>600
                || r.AlliedIds==null || r.EnemyIds==null || string.IsNullOrEmpty(r.InitialRandomState))
                throw new InvalidOperationException("Only the named existing early saved fixture can be bound; no generation permitted");
            Find.TickManager.Pause();var map=Find.CurrentMap;var pawns=map.mapPawns.AllPawnsSpawned;
            var allies=r.AlliedIds.Select(id=>pawns.Single(p=>p.thingIDNumber==id && p.Faction==Faction.OfPlayer)).ToList();
            var enemies=r.EnemyIds.Select(id=>pawns.Single(p=>p.thingIDNumber==id && p.HostileTo(Faction.OfPlayer))).ToList();
            if(allies.Any(p=>p.Dead || p.Downed) || enemies.Any(p=>p.Dead || p.Downed))
                throw new InvalidOperationException("Existing early fixture is not intact; no health/needs reset or regeneration");
            CombatLabState.Map=map;CombatLabState.Allies=allies;CombatLabState.Enemies=enemies;
            CombatLabState.Captive=null;CombatLabState.PassiveProbe=null;CombatLabState.Scenario=r.Scenario;
            CombatLabState.StartTick=Find.TickManager.TicksGame;CombatLabState.StepTicks=0;
            CombatLabState.HoldInitial=true;CombatLabState.LoadedBaseline=true;
            CombatControlHelper.TestReset(!r.Micro);
            CombatLabState.InitialRandomState=Convert.ChangeType(r.InitialRandomState,CombatLabState.RandomProperty.PropertyType,
                System.Globalization.CultureInfo.InvariantCulture);
            CombatLabState.RandomProperty.SetValue(null,CombatLabState.InitialRandomState,null);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabState.State()));
        }
        private static Pawn Spawn(Map map,Faction faction,string name,string weapon,IntVec3 pos,int skill,bool armor,string xenotype="Baseliner")
        {
            var req=new PawnGenerationRequest(PawnKindDefOf.Colonist,faction,forceGenerateNewPawn:true,mustBeCapableOfViolence:true,
                allowPregnant:false,allowAddictions:false,allowFood:false,fixedBiologicalAge:28,forcedXenotype:DefDatabase<XenotypeDef>.GetNamed(xenotype));
            Pawn pawn=PawnGenerator.GeneratePawn(req);pawn.Name=new NameTriple(name,name,"Lab");
            foreach(var h in pawn.health.hediffSet.hediffs.ToList())pawn.health.RemoveHediff(h);
            foreach(var s in pawn.skills.skills)s.Level=skill;
            foreach(var eq in pawn.equipment.AllEquipmentListForReading.ToList())eq.Destroy();
            foreach(var ap in pawn.apparel.WornApparel.ToList())ap.Destroy();
            foreach(string clothing in new[]{"Apparel_BasicShirt","Apparel_Pants"})pawn.apparel.Wear((Apparel)Make(clothing,"Cloth"));
            pawn.equipment.AddEquipment((ThingWithComps)Make(weapon));
            if(armor)foreach(string def in new[]{"Apparel_FlakVest","Apparel_SimpleHelmet"})
                pawn.apparel.Wear((Apparel)Make(def));
            GenSpawn.Spawn(pawn,pos,map);pawn.workSettings.EnableAndInitialize();
            pawn.needs.food.CurLevelPercentage=.9f;pawn.needs.rest.CurLevelPercentage=.9f;
            if(faction!=Faction.OfPlayer){var food=ThingMaker.MakeThing(ThingDefOf.MealSurvivalPack);food.stackCount=10;pawn.inventory.innerContainer.TryAdd(food);}
            return pawn;
        }
        private static void Building(Map map,string def,IntVec3 pos,string stuff=null)
        {var t=Make(def,stuff);t.SetFaction(Faction.OfPlayer);GenSpawn.Spawn(t,pos,map);}
        private static Thing Make(string name,string stuff=null)
        {var def=DefDatabase<ThingDef>.GetNamed(name);return ThingMaker.MakeThing(def,def.MadeFromStuff?(stuff==null?GenStuff.DefaultStuffFor(def):DefDatabase<ThingDef>.GetNamed(stuff)):null);}
    }
    [HarmonyPatch(typeof(Storyteller),nameof(Storyteller.StorytellerTick))]
    public static class CombatLabIncidentsHook
    { public static bool Prefix()=>CombatLabState.Map==null || !Find.Maps.Contains(CombatLabState.Map); }
    // Random map wildlife influx otherwise adds undeclared predators during a
    // long staging fixture. Preserve the original saved cohort and its AI.
    [HarmonyPatch(typeof(WildAnimalSpawner),nameof(WildAnimalSpawner.WildAnimalSpawnerTick))]
    public static class CombatLabNoWildlifeInflux
    { public static bool Prefix()=>CombatLabState.Map==null || !Find.Maps.Contains(CombatLabState.Map); }
    [HarmonyPatch(typeof(GenTemperature),nameof(GenTemperature.GetTemperatureForCell),new[]{typeof(IntVec3),typeof(Map)})]
    public static class CombatLabClimateHook
    {public static void Postfix(Map map,ref float __result){if(map==CombatLabState.Map)__result=20f;}}
    [HarmonyPatch(typeof(Room),nameof(Room.Temperature),MethodType.Getter)]
    public static class CombatLabRoomClimateHook
    {public static void Postfix(Room __instance,ref float __result){if(__instance.Map==CombatLabState.Map)__result=20f;}}
    public class CombatLabSamplingComponent : GameComponent
    {
        private bool initialFixture,micro;
        private string scenario,randomState;
        private int startTick;
        private List<Pawn> allies,enemies;
        private Pawn captive,passive;
        private Map map;
        public CombatLabSamplingComponent(Game game){}
        public override void ExposeData()
        {
            if(Scribe.mode==LoadSaveMode.Saving)
            {
                initialFixture=CombatLabState.Map==Find.CurrentMap && CombatLabState.HoldInitial && CombatLabState.StepTicks==0
                    && CombatLabState.Shots.Count==0 && CombatLabState.Damage.Count==0;
                micro=!CombatControlHelper.TestDisabled;
                scenario=initialFixture?CombatLabState.Scenario:null;
                randomState=initialFixture?CombatLabState.InitialRandomState?.ToString():null;
                startTick=CombatLabState.StartTick;
                allies=initialFixture?CombatLabState.Allies:new List<Pawn>();
                enemies=initialFixture?CombatLabState.Enemies:new List<Pawn>();
                captive=initialFixture?CombatLabState.Captive:null;
                passive=initialFixture?CombatLabState.PassiveProbe:null;
                map=initialFixture?CombatLabState.Map:null;
            }
            Scribe_Values.Look(ref initialFixture,"labInitialFixture");
            Scribe_Values.Look(ref micro,"labMicro");
            Scribe_Values.Look(ref scenario,"labScenario");
            Scribe_Values.Look(ref randomState,"labInitialRandomState");
            Scribe_Values.Look(ref startTick,"labStartTick");
            Scribe_Collections.Look(ref allies,"labAllies",LookMode.Reference);
            Scribe_Collections.Look(ref enemies,"labEnemies",LookMode.Reference);
            Scribe_References.Look(ref captive,"labCaptive");
            Scribe_References.Look(ref passive,"labPassiveProbe");
            Scribe_References.Look(ref map,"labMap");
        }
        public override void LoadedGame()
        {
            if(!initialFixture)return;
            CombatLabState.Guard(Current.Game.GetComponent<EndingEvidence>().CampaignId);
            if(map==null || allies==null || enemies==null || allies.Any(p=>p==null) || enemies.Any(p=>p==null)
                || Find.TickManager.TicksGame!=startTick || string.IsNullOrEmpty(randomState))
                throw new InvalidOperationException("Saved laboratory baseline is incomplete; do not regenerate it");
            CombatLabState.Map=map;CombatLabState.Allies=allies;CombatLabState.Enemies=enemies;
            CombatLabState.Captive=captive;CombatLabState.PassiveProbe=passive;
            CombatLabState.Scenario=scenario;CombatLabState.StartTick=startTick;CombatLabState.StepTicks=0;
            CombatLabState.Damage.Clear();CombatLabState.Samples.Clear();CombatLabState.Shots.Clear();
            CombatLabProjectileTrace.Reset();
            CombatLabState.GunMeleeTicks.Clear();CombatLabState.IdleDraftTicks.Clear();CombatLabState.SetupTimings.Clear();
            CombatControlHelper.TestReset(!micro);
            CombatLabState.InitialRandomState=Convert.ChangeType(randomState,CombatLabState.RandomProperty.PropertyType,
                System.Globalization.CultureInfo.InvariantCulture);
            CombatLabState.RandomProperty.SetValue(null,CombatLabState.InitialRandomState,null);
            CombatLabState.LoadedBaseline=true;CombatLabState.HoldInitial=true;
            Find.TickManager.CurTimeSpeed=TimeSpeed.Paused;
        }
        public override void GameComponentTick()
        {
            if(CombatLabState.Map==null || CombatLabState.Stepping || !Find.Maps.Contains(CombatLabState.Map))return;
            CombatLabState.StepTicks++;CombatLabState.Sample();
        }
    }
    [HarmonyPatch(typeof(Game),nameof(Game.LoadGame))]
    public static class CombatLabInitialLoadPause
    {
        public static void Postfix()
        {
            if(Environment.GetEnvironmentVariable("LAYA_COMBAT_LAB")!="authorized-20261014"
                || Find.World?.info?.seedString?.StartsWith("laya-combat-lab-")!=true)return;
            Find.TickManager.CurTimeSpeed=TimeSpeed.Paused;
            CombatLabState.HoldInitial=true;
            if(CombatLabState.LoadedBaseline && CombatLabState.StepTicks==0)
                CombatLabState.RandomProperty.SetValue(null,CombatLabState.InitialRandomState,null);
            else CombatLabState.Map=Find.CurrentMap;
        }
    }
    [HarmonyPatch(typeof(TickManager),"DoSingleTick")]
    public static class CombatLabInitialClockHold
    {
        public static bool Prefix()=>!CombatLabState.HoldInitial || CombatLabState.Map==null
            || !Find.Maps.Contains(CombatLabState.Map);
    }
}
#endif

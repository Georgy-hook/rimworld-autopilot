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
    }
    public static class CombatLabState
    {
        public static List<Pawn> Allies=new List<Pawn>(),Enemies=new List<Pawn>();
        public static List<object> Damage=new List<object>(),Samples=new List<object>();
        public static Dictionary<int,int> Shots=new Dictionary<int,int>(),GunMeleeTicks=new Dictionary<int,int>(),IdleDraftTicks=new Dictionary<int,int>();
        public static int StartTick,StepTicks;
        public static string Scenario;
        public static object RandomState;
        public static readonly PropertyInfo RandomProperty=typeof(Rand).GetProperty("StateCompressed",BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic);
        public static Map Map;
        public static Pawn Captive, PassiveProbe;
        public static bool Stepping;
        public static void Guard(string campaign=null)
        {
            if(Environment.GetEnvironmentVariable("LAYA_COMBAT_LAB")!="authorized-20261014")throw new InvalidOperationException("Laboratory process flag absent");
            if(campaign!=null && (Current.Game?.GetComponent<EndingEvidence>()?.CampaignId!=campaign
                || Find.World?.info?.seedString?.StartsWith("laya-combat-lab-")!=true))
                throw new InvalidOperationException("Not the named disposable laboratory campaign");
        }
        public static object State(bool includeTrace=true)
        {
            Func<Pawn,object> row=p=>new {id=p.thingIDNumber,name=p.LabelShort,dead=p.Dead,downed=p.Downed,
                spawned=p.Spawned,health=p.health.summaryHealth.SummaryHealthPercent,
                bleeding=p.health.hediffSet.BleedRateTotal,job=p.CurJobDef?.defName,target=p.CurJob?.targetA.Thing?.thingIDNumber,
                drafted=p.Drafted,x=p.Position.x,z=p.Position.z,
                food=p.needs?.food?.CurLevelPercentage,rest=p.needs?.rest?.CurLevelPercentage,mood=p.needs?.mood?.CurLevelPercentage,
                weapon=p.equipment?.Primary?.def.defName,shooting=p.skills?.GetSkill(SkillDefOf.Shooting)?.Level,
                native_shootable_ids=(p.Faction==Faction.OfPlayer?Enemies:Allies).Where(q=>q.Spawned && !q.Dead && !q.Downed
                    && p.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb?.CanHitTargetFrom(p.Position,q)==true)
                    .Select(q=>q.thingIDNumber).ToList(),
                xenotype=p.genes?.Xenotype?.defName,traits=p.story?.traits?.allTraits.Select(t=>t.def.defName+":"+t.Degree).ToList(),
                faction=p.Faction?.def.defName,
                doctor_enabled=!p.WorkTypeIsDisabled(WorkTypeDefOf.Doctor),carried_id=p.carryTracker?.CarriedThing?.thingIDNumber,
                in_bed=p.InBed(),bed_id=p.CurrentBed()?.thingIDNumber,
                speed=p.Spawned?p.GetStatValue(StatDefOf.MoveSpeed):0f,move_ticks=p.Spawned?p.TicksPerMoveCardinal:0,
                cover=p.Spawned?Enemies.Where(e=>e.Spawned && !e.Dead).Select(e=>CoverUtility.CalculateOverallBlockChance(p,e.Position,p.Map)).DefaultIfEmpty().Average():0f,
                shots=Shots.TryGetValue(p.thingIDNumber,out int n)?n:0,
                gun_melee_ticks=GunMeleeTicks.TryGetValue(p.thingIDNumber,out int m)?m:0,
                idle_draft_ticks=IdleDraftTicks.TryGetValue(p.thingIDNumber,out int i)?i:0,
                warmup=(p.stances?.curStance as Stance_Warmup)?.ticksLeft,
                stance=p.stances?.curStance?.GetType().Name,moving=p.pather?.Moving,queued=p.jobs?.jobQueue?.Select(q=>q.job.def.defName).ToList(),
                lord_toil=p.GetLord()?.CurLordToil?.GetType().Name};
            return new {scenario=Scenario,tick=Find.TickManager.TicksGame,start_tick=StartTick,stepped_ticks=StepTicks,
                allies=Allies.Select(row).ToList(),enemies=Enemies.Select(row).ToList(),
                damage_events=includeTrace?Damage.ToList():new List<object>(),samples=includeTrace?Samples.ToList():new List<object>(),
                control=CombatControlHelper.Diagnostics(),
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
                    target=p.CurJob?.targetA.Thing?.thingIDNumber,goal_x=p.CurJob?.targetA.Cell.x,goal_z=p.CurJob?.targetA.Cell.z,
                    warmup=(p.stances?.curStance as Stance_Warmup)?.ticksLeft,locked=(p.stances?.curStance as Stance_Busy)?.ticksLeft,
                    stance=p.stances?.curStance?.GetType().Name,moving=p.pather?.Moving,queued=p.jobs?.jobQueue?.Select(q=>q.job.def.defName).ToList(),
                    food=p.needs?.food?.CurLevelPercentage,rest=p.needs?.rest?.CurLevelPercentage,mood=p.needs?.mood?.CurLevelPercentage}).ToList(),
                    enemies=Enemies.Select(p=>new{id=p.thingIDNumber,x=p.Position.x,z=p.Position.z,job=p.CurJobDef?.defName,
                        goal_x=p.CurJob?.targetA.Cell.x,goal_z=p.CurJob?.targetA.Cell.z,carried=p.carryTracker?.CarriedThing?.thingIDNumber,
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
            if(!(__instance is Pawn p) || (!CombatLabState.Allies.Contains(p) && !CombatLabState.Enemies.Contains(p)))return;
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
                prior_fixture_on_current_map=CombatLabState.Map!=null && CombatLabState.Map==Find.CurrentMap,
                types=types.Select(t=>new {type=t.FullName,constructors=t.GetConstructors().Select(c=>c.GetParameters().Select(p=>p.ParameterType.FullName+" "+p.Name).ToArray()).ToArray()}).ToList(),
                random_state_available=CombatLabState.RandomProperty?.CanWrite,
                single_tick=typeof(TickManager).GetMethod("DoSingleTick",BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance)?.ToString()}));
        }
        [Post("/api/v1/combat-lab/setup")]
        public async Task Setup(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId);
            Map map=Find.CurrentMap;Find.TickManager.Pause();
            // Destroying a carrier can drop a pawn that was not in the original
            // spawned-pawn snapshot. Clear those too before creating a cohort.
            for(int pass=0;pass<4 && map.mapPawns.AllPawnsSpawned.Any();pass++)
                foreach(Pawn p in map.mapPawns.AllPawnsSpawned.ToList())p.Destroy(DestroyMode.Vanish);
            if(map.mapPawns.AllPawnsSpawned.Any())throw new InvalidOperationException("Fixture pawn cleanup incomplete; no cohort generated");
            foreach(Corpse corpse in map.listerThings.AllThings.OfType<Corpse>().ToList())corpse.Destroy(DestroyMode.Vanish);
            // Whole-map isolation is required: generated hives outside the old
            // arena rectangle spawned extra insects on the first live ticks.
            // Remove their sources before the cohort exists, never during a fight.
            foreach(Thing t in map.listerThings.AllThings.ToList())
                {if(t.def.destroyable)t.Destroy(DestroyMode.Vanish);else if(t.Spawned)t.DeSpawn();}
            for(int x=0;x<map.Size.x;x++)for(int z=0;z<map.Size.z;z++)
            {var c=new IntVec3(x,0,z);map.terrainGrid.SetTerrain(c,TerrainDefOf.Soil);map.roofGrid.SetRoof(c,null);}
            map.fogGrid.ClearAllFog();
            // Removing a casket/container or revealing the map can release its
            // previously unspawned occupants after the first cleanup pass.
            for(int pass=0;pass<4 && map.mapPawns.AllPawnsSpawned.Any();pass++)
                foreach(Pawn p in map.mapPawns.AllPawnsSpawned.ToList())
                {if(p.Spawned)p.DeSpawn();p.Destroy(DestroyMode.Vanish);}
            if(map.mapPawns.AllPawnsSpawned.Any())throw new InvalidOperationException("Container occupants survived fixture cleanup; no cohort generated");
            CombatLabState.Allies.Clear();CombatLabState.Enemies.Clear();CombatLabState.Damage.Clear();CombatLabState.Samples.Clear();
            CombatLabState.Captive=null;CombatLabState.PassiveProbe=null;
            CombatLabState.Shots.Clear();CombatLabState.GunMeleeTicks.Clear();CombatLabState.IdleDraftTicks.Clear();
            CombatLabState.Scenario=r.Scenario;CombatLabState.Map=map;CombatLabState.StartTick=Find.TickManager.TicksGame;CombatLabState.StepTicks=0;
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
                for(int n=0;n<r.Attackers;n++)
                {
                    string weapon=r.Scenario.Contains("ranged")?"Gun_HeavySMG":"MeleeWeapon_Knife";
                    if(r.Scenario=="mixed")weapon=n%3==0?"Gun_AssaultRifle":n%3==1?"MeleeWeapon_LongSword":"Gun_PumpShotgun";
                    int x=r.Scenario=="staging"?205:r.Scenario=="contact"?122:151+n%2*2;
                    Pawn p=Spawn(map,enemyFaction,"E"+n,weapon,new IntVec3(x,0,109+n*3),6,r.Scenario.Contains("ranged")||r.Scenario=="mixed",r.EnemyXenotype);
                    CombatLabState.Enemies.Add(p);
                }
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
                if(r.Scenario!="kidnap_escape" && CombatLabState.Enemies.Any())LordMaker.MakeNewLord(enemyFaction,lord,map,CombatLabState.Enemies);
                if(r.Fortified)foreach(Pawn p in CombatLabState.Allies)
                {p.drafter.Drafted=true;p.jobs.StartJob(JobMaker.MakeJob(JobDefOf.Wait_Combat),JobCondition.InterruptForced);}
                CombatLabState.RandomState=CombatLabState.RandomProperty?.GetValue(null,null);
                prepared=CombatLabState.State();
            }
            finally{Rand.PopState();}
            await context.SendJsonResponse(ApiResult<object>.Ok(prepared));
        }
        [Post("/api/v1/combat-lab/step")]
        public async Task Step(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();CombatLabState.Guard(r.CampaignId);
            var method=typeof(TickManager).GetMethod("DoSingleTick",BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance);
            if(method==null)throw new InvalidOperationException("Native single tick unavailable; do not replace with a simulated result");
            object prior=CombatLabState.RandomProperty?.GetValue(null,null);
            CombatLabState.Stepping=true;
            try
            {
                if(CombatLabState.RandomState!=null)CombatLabState.RandomProperty.SetValue(null,CombatLabState.RandomState,null);
                for(int n=0;n<Math.Min(1200,Math.Max(0,r.Ticks));n++)
                {method.Invoke(Find.TickManager,null);CombatLabState.StepTicks++;CombatLabState.Sample();}
                CombatLabState.RandomState=CombatLabState.RandomProperty?.GetValue(null,null);
            }
            catch(Exception ex)
            {throw new InvalidOperationException("Laboratory tick error at "+Find.TickManager.TicksGame+": "+(ex.InnerException ?? ex).ToString());}
            finally{CombatLabState.Stepping=false;if(prior!=null)CombatLabState.RandomProperty.SetValue(null,prior,null);}
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabState.State(r.IncludeTrace)));
        }
        [Get("/api/v1/combat-lab/state")]
        public async Task State(HttpListenerContext context)
        {CombatLabState.Guard(context.Request.QueryString["campaign_id"]);await context.SendJsonResponse(ApiResult<object>.Ok(
            CombatLabState.State(!string.Equals(context.Request.QueryString["include_trace"],"false",StringComparison.OrdinalIgnoreCase))));}
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
    [HarmonyPatch(typeof(GenTemperature),nameof(GenTemperature.GetTemperatureForCell),new[]{typeof(IntVec3),typeof(Map)})]
    public static class CombatLabClimateHook
    {public static void Postfix(Map map,ref float __result){if(map==CombatLabState.Map)__result=20f;}}
    [HarmonyPatch(typeof(Room),nameof(Room.Temperature),MethodType.Getter)]
    public static class CombatLabRoomClimateHook
    {public static void Postfix(Room __instance,ref float __result){if(__instance.Map==CombatLabState.Map)__result=20f;}}
    public class CombatLabSamplingComponent : GameComponent
    {
        public CombatLabSamplingComponent(Game game){}
        public override void GameComponentTick()
        {
            if(CombatLabState.Map==null || CombatLabState.Stepping || !Find.Maps.Contains(CombatLabState.Map))return;
            CombatLabState.StepTicks++;CombatLabState.Sample();
        }
    }
}
#endif

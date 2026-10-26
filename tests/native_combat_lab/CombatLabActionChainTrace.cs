#if LAYA_COMBAT_LAB
// Passive factual transitions only. No order, damage, AI, stat, or Rand overrides.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Threading.Tasks;
using HarmonyLib;
using RIMAPI.Core;
using RIMAPI.Http;
using RIMAPI.Models;
using RimWorld;
using Verse;

namespace RIMAPI.Controllers
{
    public static class CombatLabActionChainTrace
    {
        private static readonly List<object> Rows=new List<object>();
        private static readonly Dictionary<int,string> Last=new Dictionary<int,string>();
        public static bool Armed;
        public static int Dropped,RngChanges,Samples;
        public static void Sample()
        {
            if(!Armed || !CombatLabState.Stepping || CombatLabState.Scenario!="execution_contract_care")return;
            string before=CombatLabState.RandomProperty.GetValue(null,null).ToString();Samples++;
            int tick=Find.TickManager.TicksGame;
            foreach(var p in CombatLabState.Allies)
            {
                var job=p.CurJob;var goal=job?.targetA.Cell;
                string signature=p.Spawned+":"+p.Dead+":"+p.Downed+":"+p.Drafted+":"+p.Position+":"+job?.loadID+":"+job?.def.defName+":"+goal;
                if(tick%15!=0 && Last.TryGetValue(p.thingIDNumber,out var old) && old==signature)continue;
                Last[p.thingIDNumber]=signature;
                if(Rows.Count>=8192){Dropped++;continue;}
                Rows.Add(new{tick,pawn=p.thingIDNumber,x=p.Position.x,z=p.Position.z,spawned=p.Spawned,dead=p.Dead,downed=p.Downed,
                    drafted=p.Drafted,in_mental_state=p.InMentalState,job=job?.def.defName,job_id=job?.loadID,
                    target_id=job?.targetA.Thing?.thingIDNumber,goal_x=goal?.x,goal_z=goal?.z,moving=p.pather?.Moving,
                    queued=p.jobs?.jobQueue.Select(q=>new{job=q.job.def.defName,job_id=q.job.loadID,target=q.job.targetA.Thing?.thingIDNumber}).ToArray(),
                    bleeding=p.health.hediffSet.BleedRateTotal,health=p.health.summaryHealth.SummaryHealthPercent,
                    consciousness=p.health.capacities.GetLevel(PawnCapacityDefOf.Consciousness),
                    moving_capacity=p.health.capacities.GetLevel(PawnCapacityDefOf.Moving),
                    manipulation=p.health.capacities.GetLevel(PawnCapacityDefOf.Manipulation)});
            }
            if(before!=CombatLabState.RandomProperty.GetValue(null,null).ToString())RngChanges++;
        }
        public static object State()=>new{native_process_id=CombatLabState.ProcessId,native_instance_id=CombatLabState.InstanceId,
            armed=Armed,tick=Find.TickManager.TicksGame,samples=Samples,events=Rows.ToArray(),dropped=Dropped,
            recorder_rng_changes=RngChanges,limits="Passive native per-tick transitions, periodic15tick clinical reads. No gameplay/RNG writes; not a raid result."};
    }
    [HarmonyPatch(typeof(TickManager),"DoSingleTick")]
    public static class CombatLabActionChainTick
    {public static void Postfix(){CombatLabActionChainTrace.Sample();}}
    public class CombatLabActionChainController
    {
        [Post("/api/v1/combat-lab/measurement/action-chain/arm")]
        public async Task Arm(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();
            if(string.IsNullOrEmpty(r.CampaignId) || string.IsNullOrEmpty(r.ExpectedNativeInstanceId))throw new InvalidOperationException("Explicit lab scope required");
            CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            if(!CombatLabState.HoldInitial || CombatLabState.StepTicks!=0 || CombatLabState.Scenario!="execution_contract_care"
                || CombatLabState.Allies.Count!=3 || CombatLabState.Enemies.Count!=1 || CombatLabActionChainTrace.Armed)
                throw new InvalidOperationException("Only the exact unused held care contract can be recorded");
            CombatLabActionChainTrace.Armed=true;
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabActionChainTrace.State()));
        }
        [Get("/api/v1/combat-lab/measurement/action-chain")]
        public async Task Read(HttpListenerContext context)
        {
            var q=context.Request.QueryString;
            if(string.IsNullOrEmpty(q["campaign_id"]) || string.IsNullOrEmpty(q["expected_native_instance_id"]))throw new InvalidOperationException("Explicit lab scope required");
            CombatLabState.Guard(q["campaign_id"],q["expected_native_instance_id"]);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabActionChainTrace.State()));
        }
    }
}
#endif

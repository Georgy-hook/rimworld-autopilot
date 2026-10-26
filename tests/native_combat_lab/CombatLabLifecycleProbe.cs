#if LAYA_COMBAT_LAB
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Reflection;
using System.Threading.Tasks;
using HarmonyLib;
using RIMAPI.Core;
using RIMAPI.Helpers;
using RIMAPI.Http;
using RIMAPI.Models;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Controllers
{
    public static class CombatLabLifecycleProbe
    {
        public static bool DeferOptionalAfterClear;
        public static int OptionalDeferrals;
        public static object Read()
        {
            var plans=(IDictionary)typeof(CombatControlHelper).GetField("Plans",BindingFlags.NonPublic|BindingFlags.Static).GetValue(null);
            return new{native_process_id=CombatLabState.ProcessId,native_instance_id=CombatLabState.InstanceId,tick=Find.TickManager.TicksGame,
                optional_deferrals=OptionalDeferrals,defer_optional_after_clear=DeferOptionalAfterClear,
                actors=CombatLabState.Allies.Select(p=>
                {
                    var plan=plans[p.thingIDNumber];
                    return new{pawn=p.thingIDNumber,live_plan=CombatControlHelper.CurrentPlan(p),
                        until_tick=plan==null?(int?)null:(int)plan.GetType().GetField("UntilTick").GetValue(plan),
                        job=p.CurJobDef?.defName,job_id=p.CurJob?.loadID,drafted=p.Drafted,
                        owned=CombatOrderHelper.Owned(p,p.CurJob),queued=p.jobs.jobQueue.Select(q=>new{id=q.job.loadID,job=q.job.def.defName}).ToArray()};
                }).ToArray(),limits="Declared executor fixture only; renewal/ownership readback is not combat success"};
        }
        public static object Run(string phase)
        {
            if(CombatLabState.Scenario!="execution_contract_care")throw new InvalidOperationException("Exact care fixture required");
            var doctor=CombatLabState.Allies[0];var cover=CombatLabState.Allies[2];var enemy=CombatLabState.Enemies[0];
            void SelectHold(Pawn p)
            {
                p.drafter.Drafted=true;
                var hold=JobMaker.MakeJob(JobDefOf.Wait_Combat);hold.playerForced=true;hold.canUseRangedWeapon=false;
                if(!CombatOrderHelper.Take(p,ref hold))throw new InvalidOperationException("Declared controlled hold refused");
                CombatControlHelper.Remember(new CombatTacticRequestDto{MapId=p.Map.uniqueID,Tactic="hold_cover",TargetPawnId=enemy.thingIDNumber,FighterIds=new List<int>{p.thingIDNumber}},
                    new CombatTacticResponseDto{Applied=true,Tactic="hold_cover",TargetPawnId=enemy.thingIDNumber,AttackingPawnIds=new List<int>{p.thingIDNumber}},p.Map);
            }
            if(phase=="declare_api")
            {
                if(!CombatLabState.HoldInitial || CombatLabState.StepTicks!=0)throw new InvalidOperationException("Held API fixture required");
                SelectHold(doctor);SelectHold(cover);
            }
            else if(phase=="defer_optional_after_clear")
            {
                if(!CombatLabState.HoldInitial || CombatLabState.StepTicks!=0)throw new InvalidOperationException("Declare fault before first tick only");
                DeferOptionalAfterClear=true;
            }
            else if(phase=="manual_doctor")
            {
                if(CombatLabState.HoldInitial)throw new InvalidOperationException("Later override requires active contract");
                var manual=JobMaker.MakeJob(JobDefOf.Wait_Combat);manual.playerForced=true;manual.canUseRangedWeapon=false;
                doctor.jobs.StartJob(manual,JobCondition.InterruptForced);
            }
            else if(phase=="select_cover_then_queue_clinical")
            {
                if(CombatLabState.HoldInitial)throw new InvalidOperationException("Later queue contract requires released clock");
                SelectHold(cover);
                var clinical=JobMaker.MakeJob(JobDefOf.TendPatient,CombatLabState.Allies[1]);clinical.playerForced=true;
                cover.jobs.jobQueue.EnqueueLast(clinical);
            }
            else if(phase=="manual_readiness_after_declared_clear")
            {
                // Terminal isolation phase of a non-fighting API contract,
                // not a raid outcome. No new damage or actual treatment.
                if(CombatLabState.HoldInitial || doctor.CurJobDef!=JobDefOf.Wait_Combat
                    || !doctor.CurJob.playerForced || CombatOrderHelper.Owned(doctor,doctor.CurJob))
                    throw new InvalidOperationException("Exact later manual hold required");
                if(enemy.Spawned)enemy.DeSpawn();
                bool ready=CombatMedicalTransitionHelper.Ready(doctor,CombatLabState.Allies[1],doctor.CurJob.loadID,out var travel);
                return new{native_process_id=CombatLabState.ProcessId,native_instance_id=CombatLabState.InstanceId,
                    tick=Find.TickManager.TicksGame,manual_release_ready=ready,travel,
                    statement="Declared noncombat API readiness isolation only; waiting foe despawned terminally, no raid win or actual treatment",state=Read()};
            }
            else if(phase!="read")throw new InvalidOperationException("Unknown lifecycle fixture phase");
            return Read();
        }
    }
    [HarmonyPatch(typeof(CombatControlHelper),"ReviewPhysicianFireReturn")]
    public static class CombatLabLifecycleOptionalFault
    {
        public static void Prefix()
        {
            if(!CombatLabLifecycleProbe.DeferOptionalAfterClear || CombatLabState.HoldInitial
                || CombatLabState.Scenario!="execution_contract_care" || !CombatMedicalTransitionHelper.ThreatsClear(CombatLabState.Map))return;
            CombatLabLifecycleProbe.OptionalDeferrals++;
            throw new CombatReviewDeferredException("BudgetDeferred:declared_optional_after_clear");
        }
    }
    public class CombatLabLifecycleController
    {
        [Post("/api/v1/combat-lab/lifecycle-probe")]
        public async Task Probe(HttpListenerContext context)
        {
            var r=await context.Request.ReadBodyAsync<CombatLabRequest>();
            if(string.IsNullOrEmpty(r.CampaignId) || string.IsNullOrEmpty(r.ExpectedNativeInstanceId))throw new InvalidOperationException("Explicit native scope required");
            CombatLabState.Guard(r.CampaignId,r.ExpectedNativeInstanceId);
            await context.SendJsonResponse(ApiResult<object>.Ok(CombatLabLifecycleProbe.Run(r.Scenario)));
        }
    }
}
#endif

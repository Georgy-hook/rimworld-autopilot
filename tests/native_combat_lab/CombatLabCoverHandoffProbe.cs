#if LAYA_COMBAT_LAB
using System;
using System.Collections;
using System.Linq;
using System.Reflection;
using RIMAPI.Helpers;
using RIMAPI.Models;
using RimWorld;
using Verse;
using Verse.AI;
namespace RIMAPI.Controllers
{
    public static class CombatLabCoverHandoffProbe
    {
        private static bool used;
        public static object Run()
        {
            if(used || CombatLabState.Scenario!="cover_handoff_contract" || !CombatLabState.HoldInitial
                || CombatLabState.StepTicks!=0 || CombatLabState.Allies.Count!=2 || CombatLabState.Enemies.Count!=2)
                throw new InvalidOperationException("Cover handoff requires its unused exact held native contract");
            used=true;
            const BindingFlags flags=BindingFlags.NonPublic|BindingFlags.Static;
            var type=typeof(CombatControlHelper);
            var plans=(IDictionary)type.GetField("Plans",flags).GetValue(null);
            var actor=CombatLabState.Allies[0];var target=CombatLabState.Enemies[1];
            var plan=plans[actor.thingIDNumber];
            var commit=type.GetMethod("TryTakeCoveredShot",flags);
            var finish=type.GetMethod("TryFinishFiringApproach",flags);
            var exposure=type.GetMethod("IncomingRangedExposure",flags|BindingFlags.Public);
            if(plan==null || commit==null || finish==null || exposure==null)
                throw new MissingMethodException($"Cover methods: plan={plan!=null},commit={commit!=null},finish={finish!=null},exposure={exposure!=null}");
            int tick=Find.TickManager.TicksGame;
            string rngBefore=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            bool interiorShot=CombatInterceptHelper.InteriorShotWindow(actor,target);
            if(!interiorShot)throw new InvalidOperationException("Declared current firing window unavailable; preserve partial, no retry");
            bool accepted=(bool)commit.Invoke(null,new object[]{plan,target});
            if(!accepted || actor.CurJobDef!=JobDefOf.Goto)
                throw new InvalidOperationException("Native cover search did not accept a move in declared geometry; preserve partial, no retry");
            var move=actor.CurJob;var stamp=new CombatJobStamp(move);int moveId=move.loadID;var goal=move.targetA.Cell;
            string role=(string)plan.GetType().GetField("Mode").GetValue(plan);
            float current=(float)exposure.Invoke(null,new object[]{actor,actor.Position,0f});
            float goalNow=(float)exposure.Invoke(null,new object[]{actor,goal,0f});
            float currentFuture=(float)exposure.Invoke(null,new object[]{actor,actor.Position,360f});
            float goalFuture=(float)exposure.Invoke(null,new object[]{actor,goal,360f});
            bool earlyStop=(bool)finish.Invoke(null,new object[]{plan,CombatLabState.Enemies});
            bool sameAfterEarlyStop=stamp.Value==actor.CurJob && actor.CurJobDef==JobDefOf.Goto;
            var response=CombatTacticsHelper.Apply(new CombatTacticRequestDto{MapId=CombatLabState.Map.uniqueID,
                Tactic="hold_cover",FighterIds=CombatLabState.Allies.Select(p=>p.thingIDNumber).ToList(),
                TargetPawnId=target.thingIDNumber});
            if(!response.Success || response.Data==null)throw new InvalidOperationException("Repeated native defensive assignment failed");
            bool sameAfterRepeatedAssignment=stamp.Value==actor.CurJob && actor.CurJobDef==JobDefOf.Goto;
            string rngAfter=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            return new{native_process_id=CombatLabState.ProcessId,native_instance_id=CombatLabState.InstanceId,
                tick,scenario=CombatLabState.Scenario,actor=actor.thingIDNumber,target=target.thingIDNumber,
                interior_shot_available=interiorShot,accepted_native_cover_move=accepted,role,
                move_job_id=moveId,goal_x=goal.x,goal_z=goal.z,
                current_exposure=current,goal_current_exposure=goalNow,current_future_exposure=currentFuture,goal_future_exposure=goalFuture,
                actual_production_early_stop=earlyStop,same_owned_job_after_early_stop=sameAfterEarlyStop,
                same_owned_job_after_repeated_assignment=sameAfterRepeatedAssignment,
                preserved_pawn_ids=response.Data.PreservedPawnIds.ToArray(),
                final_job=actor.CurJobDef?.defName,final_job_id=actor.CurJob?.loadID,
                rng_before=rngBefore,rng_after=rngAfter,rng_unchanged=rngBefore==rngAfter,
                tick_unchanged=Find.TickManager.TicksGame==tick,
                limits="Actual production cover selection/order, ordinary approach early-stop and repeated native group assignment in a declared held fixture. No elapsed native ticks, movement/arrival, projectile, damage or raid-win credit."};
        }
    }
}
#endif

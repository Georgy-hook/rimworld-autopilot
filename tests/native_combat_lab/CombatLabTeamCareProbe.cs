#if LAYA_COMBAT_LAB
using System;
using System.Collections.Generic;
using System.Linq;
using RIMAPI.Helpers;
using RIMAPI.Models;
using RimWorld;
using Verse;
using Verse.AI;
namespace RIMAPI.Controllers
{
    public static class CombatLabTeamCareProbe
    {
        public static object Run(string phase)
        {
            if(CombatLabState.Scenario!="execution_contract_care")throw new InvalidOperationException("Exact retained care fixture required");
            var doctor=CombatLabState.Allies[0];var enemy=CombatLabState.Enemies[0];
            var before=CombatLabState.State(false);var checks=new Dictionary<string,bool>();
            void Register(Pawn pawn,Job job,string tactic,Pawn target,bool moved)
            {
                if(!CombatOrderHelper.Take(pawn,ref job))throw new InvalidOperationException("Declared native action rejected");
                CombatControlHelper.Remember(new CombatTacticRequestDto{MapId=pawn.Map.uniqueID,Tactic=tactic,FighterIds=new List<int>{pawn.thingIDNumber},TargetPawnId=target.thingIDNumber},
                    new CombatTacticResponseDto{Tactic=tactic,Applied=true,TargetPawnId=target.thingIDNumber,
                        AttackingPawnIds=moved?new List<int>():new List<int>{pawn.thingIDNumber},
                        PositionedPawnIds=moved?new List<int>{pawn.thingIDNumber}:new List<int>()},pawn.Map);
            }
            if(phase=="commitment_declare")
            {
                if(!CombatLabState.HoldInitial)throw new InvalidOperationException("Held native declaration required");
                doctor.stances.SetStance(new Stance_Cooldown(120,enemy,doctor.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb));
                var move=JobMaker.MakeJob(JobDefOf.Goto,CombatLabExecutionProbe.Goal);move.playerForced=true;move.locomotionUrgency=LocomotionUrgency.Jog;
                Register(doctor,move,"hold_cover",enemy,true);
                move=doctor.CurJobDef==JobDefOf.Goto?doctor.CurJob:doctor.jobs.jobQueue.Select(q=>q.job).First(j=>j.def==JobDefOf.Goto);
                var shot=CombatOrderHelper.QueueShot(doctor,enemy);CombatControlHelper.RememberSupportApproach(doctor,move,shot,enemy);
                checks["real_support_role_bound_to_accepted_move"]=CombatControlHelper.TestMode(doctor)=="support";
            }
            else if(phase=="optional_replan")
            {
                var job=doctor.CurJob;var queue=doctor.jobs.jobQueue.Select(q=>q.job).ToArray();
                var response=CombatTacticsHelper.Apply(new CombatTacticRequestDto{MapId=doctor.Map.uniqueID,Tactic="firing_line",
                    FighterIds=new List<int>{doctor.thingIDNumber},TargetPawnId=enemy.thingIDNumber});
                checks["optional_tactic_keeps_current_move"]=ReferenceEquals(job,doctor.CurJob);
                checks["optional_tactic_keeps_selected_followup"]=queue.SequenceEqual(doctor.jobs.jobQueue.Select(q=>q.job));
                checks["tactic_returns_explicit_readback"]=response.Success && response.Data.PreservedPawnIds.Contains(doctor.thingIDNumber);
            }
            else if(phase=="medical_declare")
            {
                if(!CombatLabState.HoldInitial)throw new InvalidOperationException("Held medical declaration required");
                checks["one_native_capable_doctor"]=CombatLabState.Allies.Count(p=>!p.WorkTypeIsDisabled(WorkTypeDefOf.Doctor)
                    && !(p.skills?.GetSkill(SkillDefOf.Medicine)?.TotallyDisabled ?? true))==1;
                // Separate declared contract geometry: keep the patient out of
                // the firing corridor. Wounds/skills/weapons are unchanged.
                var patient=CombatLabState.Allies[1];var cover=CombatLabState.Allies[2];
                var map=doctor.Map;
                foreach(var placement in new[]{Tuple.Create(patient,new IntVec3(110,0,100)),Tuple.Create(cover,new IntVec3(110,0,118))})
                {
                    if(!placement.Item2.Standable(map) || placement.Item2.GetThingList(map).Any(t=>t is Pawn))
                        throw new InvalidOperationException("Declared care/cover cell unavailable; no alternative geometry search");
                    placement.Item1.DeSpawn();GenSpawn.Spawn(placement.Item1,placement.Item2,map);
                }
                foreach(var pawn in new[]{doctor,CombatLabState.Allies[2]})
                {
                    pawn.drafter.Drafted=true;
                    if(!CombatInterceptHelper.CanShootNow(pawn,enemy))throw new InvalidOperationException("Declared gun has no native friendly-safe shot");
                    var shot=JobMaker.MakeJob(JobDefOf.AttackStatic,enemy);shot.playerForced=true;Register(pawn,shot,"stationary_fire",enemy,false);
                }
                // Declared only before the first tick: native pursuit of the
                // sole doctor. No later enemy retarget, wound or damage change.
                var pursuit=JobMaker.MakeJob(JobDefOf.AttackMelee,doctor);pursuit.playerForced=true;
                enemy.jobs.StartJob(pursuit,JobCondition.InterruptForced);
                checks["native_doctor_pursuit_declared"]=enemy.CurJob.targetA.Thing==doctor;
            }
            else throw new InvalidOperationException("Unknown team-care contract phase");
            return new{phase,tick=Find.TickManager.TicksGame,checks,pass=checks.Values.All(x=>x),before,after=CombatLabState.State(false),
                statement="Declared native contract, no raid score. Original care cohort, unchanged wounds/skills/weapons; medical geometry patient110,100/cover110,118 and native orders declared only before begin; commitment cooldown120."};
        }
    }
}
#endif

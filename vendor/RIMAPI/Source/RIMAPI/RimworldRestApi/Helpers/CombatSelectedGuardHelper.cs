using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;
using Verse.AI.Group;
using RIMAPI.Models;

namespace RIMAPI.Helpers
{
    public static class CombatSelectedGuardHelper
    {
        public static bool Admits(bool drafted,bool ranged,bool hasPlan,bool idle,bool foreignForced,
            bool clinical,bool queued,bool warming,bool bursting)
            =>drafted && ranged && !hasPlan && idle && !foreignForced && !clinical && !queued && !warming && !bursting;

        // This admits only an already drafted, explicitly selected idle gun.
        // The exact owned native hold is a real order, not proof of cover,
        // arrival or a shot. Optional placement remains the controller's work.
        public static bool TryAdmit(string tactic,List<Pawn> fighters,Pawn enemy,CombatTacticResponseDto result)
        {
            bool carrierPending=tactic=="intercept_kidnapper" && CombatInterceptHelper.CarrierRoutePending(enemy);
            if((!new[]{"hold_cover","firing_line","focus_fire","fallback_line"}.Contains(tactic) && !carrierPending)
                || enemy==null || !fighters.Any())return false;
            string toil=enemy.GetLord()?.CurLordToil?.GetType().Name ?? "";
            if(toil.IndexOf("Stage",StringComparison.OrdinalIgnoreCase)>=0
                || toil.IndexOf("Siege",StringComparison.OrdinalIgnoreCase)>=0)return false;
            foreach(var p in fighters)
            {
                var v=p.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
                if(!Admits(p.Drafted,p.equipment?.Primary?.def.IsRangedWeapon==true,
                    CombatControlHelper.CurrentPlan(p)!=null,p.CurJob==null || p.CurJobDef==JobDefOf.Wait_Combat,
                    p.CurJob?.playerForced==true,CombatNativeHelper.Protected(p) || p.carryTracker?.CarriedThing is Pawn,
                    p.jobs.jobQueue.Any(),p.stances.curStance is Stance_Warmup,v?.state==VerbState.Bursting))return false;
            }
            foreach(var p in fighters)
            {
                CombatPathBudgetHelper.Checkpoint("selected_idle_guard");
                var hold=JobMaker.MakeJob(JobDefOf.Wait_Combat);hold.playerForced=true;hold.canUseRangedWeapon=false;
                if(!CombatOrderHelper.Take(p,ref hold))continue;
                result.PositionedPawnIds.Add(p.thingIDNumber);
            }
            result.Applied=result.PositionedPawnIds.Any();
            result.Notes.Add("Selected idle guns received owned current-position native guard holds; no movement, protected cover, arrival, projectile or defense outcome asserted.");
            return result.Applied;
        }
    }
}

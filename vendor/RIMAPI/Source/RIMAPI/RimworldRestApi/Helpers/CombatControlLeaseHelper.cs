using System;
using System.Collections.Generic;
using System.Linq;
using RIMAPI.Models;
using RimWorld;
using Verse;

namespace RIMAPI.Helpers
{
    public static class CombatControlLeaseMath
    {
        public static bool Retain(bool live,bool mapMatches,bool requestMatches,bool eligible,
            bool foreignQueue,bool ownedCurrent,bool nativeIdle)
            =>live && mapMatches && requestMatches && eligible && !foreignQueue && (ownedCurrent || nativeIdle);
    }
    public static partial class CombatControlHelper
    {
        // No path/geometry checkpoint or pawn order: a fresh scoped request
        // may retain only its existing live role. A later expensive review
        // can still defer, and renewal is not route/order completion.
        public static List<int> RetainControlLeases(Map map,List<int> ids,CombatTacticRequestDto request=null)
        {
            var retained=new List<int>();
            if(map==null || ids==null)return retained;
            foreach(int id in ids.Distinct())
            {
                if(!Plans.TryGetValue(id,out var plan))continue;
                var pawn=plan.Pawn;
                if(pawn?.CurJob==null)continue;
                bool matches=request==null || RangedPlans.Contains(request.Tactic) && request.Tactic==plan.Tactic
                    && request.TargetPawnId==plan.Target?.thingIDNumber && plan.Target!=null && Threat(plan.Target);
                bool owned=CombatOrderHelper.Owned(pawn,pawn.CurJob)
                    && (pawn.CurJob==plan.OwnedJob || pawn.CurJob==plan.QueuedShot
                        || pawn.CurJobDef==JobDefOf.AttackStatic && pawn.CurJob.targetA.Thing==plan.Target
                        || SelectedMoves.TryGetValue(pawn,out var move) && pawn.CurJob==move.Key);
                bool nativeIdle=!pawn.CurJob.playerForced && pawn.jobs.jobQueue.Count==0 && pawn.Position==plan.ProgressCell
                    && (pawn.CurJobDef==JobDefOf.Wait_Combat || pawn.CurJobDef==JobDefOf.Wait_MaintainPosture);
                if(!CombatControlLeaseMath.Retain(Valid(plan),pawn.Map==map,matches,Eligible(pawn),
                    pawn.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(pawn,q.job)),owned,nativeIdle))continue;
                plan.UntilTick=Find.TickManager.TicksGame+1200;
                plan.UntilUtc=DateTime.UtcNow.AddSeconds(30);
                retained.Add(id);
            }
            return retained;
        }
    }
}

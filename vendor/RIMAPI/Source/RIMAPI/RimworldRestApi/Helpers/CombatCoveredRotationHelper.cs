using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class CombatCoveredRotationMath
    {
        public static bool Review(float current,float projected,int actualOtherGuns,bool healthy,bool otherMoving)
            =>healthy && !otherMoving && actualOtherGuns>=2 && current>=1.4f && projected>=1.4f
                && !float.IsNaN(current) && !float.IsNaN(projected)
                && !float.IsInfinity(current) && !float.IsInfinity(projected);
    }
    public static partial class CombatControlHelper
    {
        // A healthy front gun need not wait for a bullet wound to start a
        // checked refuge. TWO other selected stationary guns must have actually
        // fired at this exact observed aimed enemy. This is a review trigger,
        // never a waiver of the unchanged full native route/endpoint proof.
        private static Pawn ProactiveCoveredEnemy(Pawn p,List<Pawn> threats)
        {
            if(!Eligible(p) || !Plans.TryGetValue(p.thingIDNumber,out var plan) || !OwnStationaryGun(plan)
                || IsReservedDoctor(p) || CriticalRangedInjury(p) || MedicalFunctionWarning(p)
                || p.jobs.jobQueue.Any() || p.carryTracker?.CarriedThing is Pawn
                || OtherSelectedGunMoving(p))return null;
            var focused=threats.Where(e=>FocusedRangedThreat(e,p)).OrderBy(NextRangedBurst).ToArray();
            if(focused.Length==0)return null;
            float current=IncomingRangedExposure(p,p.Position);
            if(current<1.4f)return null;
            int tick=Find.TickManager.TicksGame;
            foreach(var enemy in focused)
            {
                int guns=CombatInterceptHelper.ReadyCover(p,enemy).Count(g=>Plans.TryGetValue(g.thingIDNumber,out var selected)
                    && OwnStationaryGun(selected) && !CriticalRangedInjury(g) && !MedicalFunctionWarning(g)
                    && CombatShotEvidenceHelper.LastTick(g,enemy.thingIDNumber)>=0
                    && tick-CombatShotEvidenceHelper.LastTick(g,enemy.thingIDNumber)<=TeamCycle(g)+60);
                if(CombatCoveredRotationMath.Review(current,IncomingRangedExposure(p,p.Position,180),guns,true,false))return enemy;
            }
            return null;
        }
    }
}

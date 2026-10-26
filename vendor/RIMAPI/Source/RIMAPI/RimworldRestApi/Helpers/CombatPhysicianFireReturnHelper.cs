using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static partial class CombatControlHelper
    {
        // Review a stale escape before optional formation/path work can use
        // the pulse budget. No forward move and no adoption of a manual job:
        // only an exactly owned melee escape with its original cause ended.
        private static void ReviewPhysicianFireReturn()
        {
            foreach(var group in Plans.Values.Where(Valid).GroupBy(x=>x.Pawn.Map).ToArray())
            {
                var p=ReservedDoctor(group.Key);
                if(p==null || !Plans.TryGetValue(p.thingIDNumber,out var plan)
                    || plan.Mode!="retreat" || p.CurJobDef!=JobDefOf.Goto || p.CurJob!=plan.OwnedJob
                    || !CombatOrderHelper.Owned(p,p.CurJob) || CareTriageHelper.QueuedCare(p)
                    || CombatNativeHelper.Protected(p) || p.carryTracker?.CarriedThing is Pawn
                    || p.jobs.jobQueue.Any(q=>!CombatOrderHelper.Owned(p,q.job)))continue;
                var threats=group.Key.mapPawns.AllPawnsSpawned.Where(Threat).ToList();
                if(!threats.Any() || !threats.All(MeleeThreat))continue;
                urgentTeamTransition=true;
                try
                {
                    if(TryReleaseCompletedEscape(plan,threats))
                    {TeamEvent("physician_expired_escape_rejoined_selected_fire",p,plan.Target);return;}
                }
                finally{urgentTeamTransition=false;}
            }
        }
    }
}

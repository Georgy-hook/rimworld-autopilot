using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    // A selected contact defense is not permission to chase a departing enemy.
    // Only the exact accepted job is owned; later manual/care jobs and queues
    // keep their native semantics, including explicit offensive melee orders.
    public static class CombatContactHelper
    {
        private static readonly Dictionary<Pawn,CombatJobStamp> Orders=new Dictionary<Pawn,CombatJobStamp>();
#if LAYA_COMBAT_LAB
        private static readonly List<object> Stops=new List<object>();
        public static object Diagnostics()=>new{owned=Orders.Count,stops=Stops.ToArray()};
#endif
        public static void Remember(Pawn pawn,Job job)
        {
            if(job?.def==JobDefOf.AttackMelee && !job.killIncappedTarget && job.targetA.Thing is Pawn
                && CombatOrderHelper.Owned(pawn,job))Orders[pawn]=new CombatJobStamp(job);
        }
        public static void Tick()
        {
            foreach(var pair in Orders.ToArray())
            {
                var pawn=pair.Key;var job=pair.Value.Value;
                if(job==null || job.def!=JobDefOf.AttackMelee || job.killIncappedTarget
                    || !pawn.Spawned || pawn.Dead || !CombatOrderHelper.Owned(pawn,job)
                    || pawn.CurJob!=job && !pawn.jobs.jobQueue.Any(q=>q.job==job))
                {Orders.Remove(pawn);continue;}
                var target=job.targetA.Thing as Pawn;
                bool active=target!=null && target.Spawned && !target.Dead && !target.Downed
                    && target.Map==pawn.Map && CombatNativeHelper.IsPlayerThreat(target);
                float distance=active?pawn.Position.DistanceTo(target.Position):float.PositiveInfinity;
                if(pawn.Drafted && !pawn.Downed && !pawn.InMentalState && active && distance<=1.5f)continue;
                string reason=!pawn.Drafted?"actor_undrafted":pawn.Downed || pawn.InMentalState?"actor_unavailable"
                    :!active?"target_inactive":"contact_lost";
                int jobId=job.loadID;int? targetId=target?.thingIDNumber;bool current=pawn.CurJob==job;
                // Remove only this accepted defense. EndCurrentJob starts the
                // next native queued instruction; it does not erase that queue.
                Orders.Remove(pawn);
                if(current)pawn.jobs.EndCurrentJob(JobCondition.InterruptForced,true);
                else pawn.jobs.jobQueue.RemoveAll(pawn,j=>j==job && j.loadID==jobId && CombatOrderHelper.Owned(pawn,j));
#if LAYA_COMBAT_LAB
                if(Stops.Count<128)Stops.Add(new{tick=Find.TickManager.TicksGame,pawn=pawn.thingIDNumber,
                    target=targetId,job_id=jobId,reason,current,distance=active?(float?)distance:null});
#endif
            }
        }
    }
}

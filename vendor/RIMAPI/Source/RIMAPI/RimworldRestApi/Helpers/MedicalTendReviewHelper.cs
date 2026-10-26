using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    // Explicit finite treatment leaves a short decision window after the
    // completed native tend, rather than starting another patient's wound
    // blindly. Current treatment is never interrupted by this helper.
    public static class MedicalTendReviewHelper
    {
        private sealed class Entry {public CombatJobStamp Care,Wait;public int CareId;}
        private static readonly Dictionary<Pawn,Entry> Entries=new Dictionary<Pawn,Entry>();
#if LAYA_COMBAT_LAB
        private static readonly List<object> Events=new List<object>();
        private static readonly Dictionary<Pawn,string> Last=new Dictionary<Pawn,string>();
        public static object Diagnostics()=>new{entries=Entries.Count,component=Current.Game.GetComponent<MedicalTendReviewComponent>()!=null,events=Events.ToArray()};
        private static void Trace(Pawn p,string reason,Entry entry)
        {
            string state=reason+":"+p.CurJob?.loadID+":"+entry.Care.Value?.loadID+":"+entry.Wait.Value?.loadID+":"+string.Join(",",p.jobs.jobQueue.Select(q=>q.job.loadID));
            if(Last.TryGetValue(p,out var previous) && previous==state)return;Last[p]=state;
            if(Events.Count<128)Events.Add(new{tick=Find.TickManager.TicksGame,pawn=p.thingIDNumber,reason,current=p.CurJob?.def?.defName,current_id=p.CurJob?.loadID,care_id=entry.CareId,care_stamp=entry.Care.Value?.loadID,wait_stamp=entry.Wait.Value?.loadID,queued=p.jobs.jobQueue.Select(q=>new{id=q.job.loadID,def=q.job.def.defName}).ToArray()});
        }
#else
        private static void Trace(Pawn p,string reason,Entry entry){}
#endif

        public static bool Schedule(Pawn doctor,Job care)
        {
            if(doctor?.jobs==null || care==null || doctor.CurJob!=care
                || care.def!=JobDefOf.TendPatient || !care.endAfterTendedOnce)return false;
            if(Entries.TryGetValue(doctor,out var old) && old.Care.Value==care && old.Wait.Value!=null
                && doctor.jobs.jobQueue.Any(q=>q.job==old.Wait.Value))return true;
            if(doctor.jobs.jobQueue.Any())return false;
            var wait=JobMaker.MakeJob(JobDefOf.Wait);wait.playerForced=true;
            wait.expiryInterval=180;wait.checkOverrideOnExpire=true;
            doctor.jobs.jobQueue.EnqueueLast(wait);
            Entries[doctor]=new Entry{Care=new CombatJobStamp(care),Wait=new CombatJobStamp(wait),CareId=care.loadID};
            Trace(doctor,"scheduled",Entries[doctor]);return true;
        }
        public static void Tick()
        {
            foreach(var pair in Entries.ToArray())
            {
                var doctor=pair.Key;var care=pair.Value.Care.Value;var wait=pair.Value.Wait.Value;
                Trace(doctor,"tick",pair.Value);
                if(wait==null){Trace(doctor,"wait_stamp_invalid",pair.Value);Entries.Remove(doctor);continue;}
                bool foreign=doctor.jobs.jobQueue.Any(q=>q.job!=care && q.job!=wait);
                // Native EndCurrentJob can briefly maintain posture before
                // starting the exact queued review. This is not a new order.
                if(!foreign && care==null && doctor.Spawned && !doctor.Dead && !doctor.Downed
                    && doctor.CurJobDef==JobDefOf.Wait_MaintainPosture && !doctor.CurJob.playerForced
                    && doctor.jobs.jobQueue.Any(q=>q.job==wait)
                    && CaregiverRecoveryHelper.CompletedCare(doctor,pair.Value.CareId))
                {Trace(doctor,"completed_tend_native_posture_bridge_kept",pair.Value);continue;}
                if(!foreign && doctor.CurJob==wait && CaregiverRecoveryHelper.TryStart(doctor,wait,pair.Value.CareId))
                {Entries.Remove(doctor);continue;}
                if(!doctor.Spawned || doctor.Dead || doctor.Downed || foreign
                    || doctor.CurJob!=care && doctor.CurJob!=wait)
                {
                    Trace(doctor,foreign?"foreign_queue":"current_changed",pair.Value);
                    // Preserve later manual/clinical instructions. Remove
                    // only our exact wait, including its native load ID.
                    if(doctor.CurJob==wait)doctor.jobs.EndCurrentJob(JobCondition.Succeeded);
                    else doctor.jobs.jobQueue.RemoveAll(doctor,j=>j==wait);
                    Entries.Remove(doctor);
                }
            }
        }
    }
    public sealed class MedicalTendReviewComponent:GameComponent
    {
        public MedicalTendReviewComponent(Game game){}
        public override void GameComponentTick()
        {
            if(Find.TickManager!=null && Find.TickManager.TicksGame%15==0)MedicalTendReviewHelper.Tick();
        }
    }
}

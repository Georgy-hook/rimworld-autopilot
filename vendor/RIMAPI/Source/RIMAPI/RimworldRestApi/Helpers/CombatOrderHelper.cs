using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    internal sealed class CombatJobStamp
    {
        private readonly Job job;private readonly int id;
        public CombatJobStamp(Job value){job=value;id=value?.loadID ?? -1;}
        public Job Value=>job!=null && job.loadID==id?job:null;
    }
    // Job objects are pooled. A reference alone stops proving ownership once
    // the engine returns that job and assigns the object a different loadID.
    public static class CombatOrderHelper
    {
        private static readonly Dictionary<Pawn,Dictionary<int,Job>> Orders=new Dictionary<Pawn,Dictionary<int,Job>>();
#if LAYA_COMBAT_LAB
        private static int maxQueuedShots,foreignQueueRefusals,missingAcceptedJob;
        private static readonly List<object> WarmupInterruptions=new List<object>();
        private static readonly List<object> CommitmentEvents=new List<object>();
        private static void Commitment(Pawn p,Job request,string reason)
        {
            if(CommitmentEvents.Count<256)CommitmentEvents.Add(new{tick=Find.TickManager.TicksGame,pawn=p.thingIDNumber,
                reason,current=p.CurJobDef?.defName,current_id=p.CurJob?.loadID,requested=request.def.defName,
                requested_target=request.targetA.Thing?.thingIDNumber,x=p.Position.x,z=p.Position.z,
                moving=p.pather.Moving,stance=p.stances.curStance?.GetType().Name,
                queue=p.jobs.jobQueue.Select(q=>new{id=q.job.loadID,def=q.job.def.defName,owned=Owned(p,q.job)}).ToArray()});
        }
        public static object Diagnostics()=>new{max_queued_selected_shots=maxQueuedShots,foreign_queue_refusals=foreignQueueRefusals,missing_accepted_job=missingAcceptedJob,warmup_interruptions=WarmupInterruptions.ToArray(),commitment_events=CommitmentEvents.ToArray()};
#endif
        public static bool Owned(Pawn pawn,Job job)=>job!=null && Orders.TryGetValue(pawn,out var jobs)
            && jobs.TryGetValue(job.loadID,out var owned) && ReferenceEquals(owned,job);
        private static bool Present(Pawn pawn,Job job)=>job!=null
            && (pawn.CurJob==job || pawn.jobs.jobQueue.Any(q=>q.job==job));
        private static void Register(Pawn pawn,Job job)
        {
            if(!Orders.TryGetValue(pawn,out var jobs))Orders[pawn]=jobs=new Dictionary<int,Job>();
            jobs[job.loadID]=job;
        }
        public static void Prune()
        {
            foreach(var pair in Orders.ToArray())
            {
                foreach(var entry in pair.Value.ToArray())
                    if(entry.Value.loadID!=entry.Key || !Present(pair.Key,entry.Value))pair.Value.Remove(entry.Key);
                if(pair.Value.Count==0 || !pair.Key.Spawned || pair.Key.Dead)Orders.Remove(pair.Key);
            }
        }
        public static void DropQueued(Pawn pawn)
            =>pawn.jobs.jobQueue.RemoveAll(pawn,j=>Owned(pawn,j));

        public static bool Take(Pawn pawn,ref Job requested)
        {
            if(CareTriageHelper.QueuedCare(pawn))return false;
            // Native TryTakeOrderedJob can clear the whole queue. Do not use
            // it to erase a later manual or clinical instruction.
            if(pawn.jobs.jobQueue.Any(q=>!Owned(pawn,q.job)))
            {
#if LAYA_COMBAT_LAB
                foreignQueueRefusals++;
#endif
                return false;
            }
            // Reissuing an equivalent owned job used to call the native
            // ordered-job tracker again, clearing its selected follow-up and
            // potentially restarting the same firing cycle. Preserve both the
            // actual accepted object and its owned queue. Foreign queues were
            // checked above; a native/manual job is never adopted here.
            var candidate=requested;
            bool Equivalent(Job job)=>Owned(pawn,job) && (job.def==JobDefOf.Goto || job.def==JobDefOf.AttackStatic)
                && job.def==candidate.def && job.expiryInterval==candidate.expiryInterval
                && job.checkOverrideOnExpire==candidate.checkOverrideOnExpire && job.targetA==candidate.targetA
                && job.targetB==candidate.targetB && job.targetC==candidate.targetC
                && (job.def!=JobDefOf.Goto || job.locomotionUrgency==candidate.locomotionUrgency);
            var current=pawn.CurJob;
            var retained=Equivalent(current)?current:pawn.jobs.jobQueue.Select(q=>q.job).FirstOrDefault(Equivalent);
            if(retained!=null)
            {
#if LAYA_COMBAT_LAB
                Commitment(pawn,requested,"equivalent_owned_action_retained");
#endif
                requested=retained;return true;
            }
            // A fire recommendation cannot erase the exact selected move to
            // that same target while it is pending or making safe progress.
            // Contact emergencies, unsafe/stalled moves and foreign intent
            // still go through the normal production checks.
            if(CombatControlHelper.PreserveTeamMove(pawn,requested) || CombatControlHelper.PreserveMoveBeforeShot(pawn,requested))
            {
#if LAYA_COMBAT_LAB
                Commitment(pawn,requested,"selected_move_precedes_same_target_shot");
#endif
                return false;
            }
            // A newly ordered autonomous hold must not start a vanilla
            // random-target warmup before the selected controller checks its
            // target and friendly lane. This changes only our requested job;
            // an existing foreign/native hold and its stance remain untouched.
            bool controlledHold=requested.def==JobDefOf.Wait_Combat && pawn.equipment?.Primary?.def.IsRangedWeapon==true;
            if(controlledHold)requested.canUseRangedWeapon=false;
            var def=requested.def;var a=requested.targetA;var b=requested.targetB;var c=requested.targetC;
            var urgency=requested.locomotionUrgency;int id=requested.loadID;
#if LAYA_COMBAT_LAB
            var oldWarmup=pawn.stances.curStance as Stance_Warmup;
            var oldFocus=oldWarmup?.focusTarg.Thing?.thingIDNumber;
            int oldRemaining=oldWarmup?.ticksLeft ?? 0;
            var oldTarget=oldWarmup?.focusTarg.Thing as Pawn;
            var primary=pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            bool oldAlive=oldTarget!=null && !oldTarget.Dead && !oldTarget.Downed && oldTarget.Spawned;
            bool oldLegal=oldWarmup!=null && oldWarmup.verb==primary && oldAlive
                && primary.CanHitTargetFrom(pawn.Position,oldTarget);
            bool oldFriendly=oldLegal && CombatInterceptHelper.FriendlyLaneClear(pawn,oldTarget,pawn.Position);
#endif
            if(!MentalSafetyHelper.TakeDefenceOrder(pawn,requested))return false;
#if LAYA_COMBAT_LAB
            if(oldWarmup!=null && pawn.stances.curStance!=oldWarmup && WarmupInterruptions.Count<128)
                WarmupInterruptions.Add(new{tick=Find.TickManager.TicksGame,pawn=pawn.thingIDNumber,
                    previous_target=oldFocus,remaining=oldRemaining,requested=def.defName,
                    previous_alive=oldAlive,previous_legal_shot=oldLegal,previous_friendly_clear=oldFriendly,
                    health=pawn.health.summaryHealth.SummaryHealthPercent,bleeding=pawn.health.hediffSet.BleedRateTotal,
                    requested_target=a.Thing?.thingIDNumber,current=pawn.CurJobDef?.defName,
                    current_target=pawn.CurJob?.targetA.Thing?.thingIDNumber});
#endif
            Job accepted=Present(pawn,requested) && requested.loadID==id?requested:null;
            if(accepted==null)
            {
                bool Matches(Job j)=>j!=null && j.playerForced && j.def==def && j.targetA==a && j.targetB==b && j.targetC==c
                    && (def!=JobDefOf.Goto || j.locomotionUrgency==urgency);
                accepted=Matches(pawn.CurJob)?pawn.CurJob:pawn.jobs.jobQueue.Select(q=>q.job).LastOrDefault(Matches);
            }
            if(accepted==null)
            {
#if LAYA_COMBAT_LAB
                missingAcceptedJob++;
#endif
                return false; // An ACK alone is not an accepted job.
            }
            pawn.jobs.jobQueue.RemoveAll(pawn,j=>j!=accepted && Owned(pawn,j));
            if(controlledHold)accepted.canUseRangedWeapon=false;
            Register(pawn,accepted);requested=accepted;
            return true;
        }
        public static Job QueueShot(Pawn pawn,Pawn target,bool finiteApproach=false)
        {
            // Only our exact pending shots may be replaced. An unrelated queue
            // is left alone, including instructions entered after our move.
            if(CareTriageHelper.QueuedCare(pawn) || pawn.jobs.jobQueue.Any(q=>!Owned(pawn,q.job)))return null;
            Job shot=pawn.jobs.jobQueue.Select(q=>q.job).FirstOrDefault(j=>Owned(pawn,j)
                && j.def==JobDefOf.AttackStatic && j.targetA.Thing==target);
            pawn.jobs.jobQueue.RemoveAll(pawn,j=>j!=shot && Owned(pawn,j) && j.def==JobDefOf.AttackStatic);
            if(shot!=null)return shot;
            shot=JobMaker.MakeJob(JobDefOf.AttackStatic,target);shot.playerForced=true;
            if(finiteApproach){shot.expiryInterval=300;shot.checkOverrideOnExpire=true;}
            pawn.jobs.jobQueue.EnqueueLast(shot);Register(pawn,shot);
#if LAYA_COMBAT_LAB
            maxQueuedShots=System.Math.Max(maxQueuedShots,pawn.jobs.jobQueue.Count(q=>Owned(pawn,q.job) && q.job.def==JobDefOf.AttackStatic));
#endif
            return shot;
        }
    }
}

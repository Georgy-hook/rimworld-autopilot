$ErrorActionPreference='Stop'
$taskRepo=Split-Path -Parent $PSScriptRoot
$taskSource=Get-Content -Raw -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/MedicalTendReviewHelper.cs')
$taskOrder=Get-Content -Raw -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatOrderHelper.cs')
$taskStamp=$taskOrder.Substring($taskOrder.IndexOf('    internal sealed class CombatJobStamp'),$taskOrder.IndexOf('    public static class CombatOrderHelper')-$taskOrder.IndexOf('    internal sealed class CombatJobStamp'))
$taskCode=@'
namespace Verse {
 public class Game{}public class GameComponent {public virtual void GameComponentTick(){}}
 public class TickManager {public int TicksGame;}public static class Find {public static TickManager TickManager;}
 public class Pawn {
  public bool Spawned=true,Dead,Downed;public Verse.AI.Tracker jobs;
  public Pawn(){jobs=new Verse.AI.Tracker(this);}public Verse.AI.Job CurJob=>jobs.current;public object CurJobDef=>CurJob?.def;
 }
}
namespace RimWorld {public static class JobDefOf {
 public static object TendPatient=new object(),Wait=new object(),Manual=new object(),Wait_MaintainPosture=new object();
}}
namespace Verse.AI {
 public enum JobCondition {Succeeded}
 public class Job {public object def;public bool endAfterTendedOnce,playerForced,checkOverrideOnExpire;public int loadID,expiryInterval;}
 public class QueuedJob {public Job job;}
 public class Queue:System.Collections.Generic.List<QueuedJob> {
  public void EnqueueLast(Job j){Add(new QueuedJob{job=j});}
  public void RemoveAll(Verse.Pawn p,System.Predicate<Job> test){foreach(var q in this.Where(q=>test(q.job)).ToArray()){Remove(q);q.job.loadID=0;q.job.def=null;}}
 }
 public class Tracker {
  public Job current;public Queue jobQueue=new Queue();
  public Tracker(Verse.Pawn p){}
  public void EndCurrentJob(JobCondition c){current.loadID=0;current=null;if(jobQueue.Any()){current=jobQueue[0].job;jobQueue.RemoveAt(0);}}
 }
 public static class JobMaker {static int next;public static Job MakeJob(object def)=>new Job{def=def,loadID=++next};}
}
namespace RIMAPI.Helpers {STAMP public static class CaregiverRecoveryHelper {public static bool TryStart(Verse.Pawn p,Verse.AI.Job wait,int id)=>false;public static bool completed=true;public static bool CompletedCare(Verse.Pawn p,int id)=>completed;}}
public static class MedicalReviewBoundary {
 static int n;static void Check(bool value,string text){n++;if(!value)throw new System.Exception(text);}
 static Verse.Pawn Doctor(out Verse.AI.Job care){var p=new Verse.Pawn();care=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.TendPatient);care.endAfterTendedOnce=true;p.jobs.current=care;return p;}
 public static int Run(){
  Verse.AI.Job care;var p=Doctor(out care);
  Check(RIMAPI.Helpers.MedicalTendReviewHelper.Schedule(p,care),"Finite accepted care did not get a review window");
  var wait=p.jobs.jobQueue[0].job;
  Check(wait.def==RimWorld.JobDefOf.Wait && wait.expiryInterval==180,"Review wait lacks a finite native deadline");
  Check(p.CurJob==care,"Scheduling a review interrupted current treatment");
  Check(RIMAPI.Helpers.MedicalTendReviewHelper.Schedule(p,care) && p.jobs.jobQueue.Count==1,"Repeated scheduling appended duplicate waits");
  var manual=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.Manual);p.jobs.jobQueue.EnqueueLast(manual);
  RIMAPI.Helpers.MedicalTendReviewHelper.Tick();
  Check(p.CurJob==care && p.jobs.jobQueue.Count==1 && p.jobs.jobQueue[0].job==manual,"Later manual queue was erased or current care interrupted");
  p=Doctor(out care);RIMAPI.Helpers.MedicalTendReviewHelper.Schedule(p,care);wait=p.jobs.jobQueue[0].job;
  p.jobs.EndCurrentJob(Verse.AI.JobCondition.Succeeded);manual=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.Manual);p.jobs.jobQueue.EnqueueLast(manual);
  RIMAPI.Helpers.MedicalTendReviewHelper.Tick();Check(p.CurJob==manual,"Own review wait blocked a later manual queue");
  p=Doctor(out care);RIMAPI.Helpers.MedicalTendReviewHelper.Schedule(p,care);wait=p.jobs.jobQueue[0].job;
  wait.loadID++;wait.def=RimWorld.JobDefOf.Manual;RIMAPI.Helpers.MedicalTendReviewHelper.Tick();
  Check(p.jobs.jobQueue.Count==1 && p.jobs.jobQueue[0].job==wait,"Pooled wait reference erased another instruction");
  p=Doctor(out care);care.endAfterTendedOnce=false;
  Check(!RIMAPI.Helpers.MedicalTendReviewHelper.Schedule(p,care) && !p.jobs.jobQueue.Any(),"Ordinary ongoing treatment was truncated");
  p=Doctor(out care);RIMAPI.Helpers.MedicalTendReviewHelper.Schedule(p,care);p.Downed=true;
  RIMAPI.Helpers.MedicalTendReviewHelper.Tick();Check(!p.jobs.jobQueue.Any() && p.CurJob==care,"Downed actor retained review queue or had care overwritten");
  p=Doctor(out care);manual=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.Manual);p.jobs.jobQueue.EnqueueLast(manual);
  Check(!RIMAPI.Helpers.MedicalTendReviewHelper.Schedule(p,care) && p.jobs.jobQueue[0].job==manual,"Arming review erased a preexisting instruction");
  p=Doctor(out care);RIMAPI.Helpers.MedicalTendReviewHelper.Schedule(p,care);wait=p.jobs.jobQueue[0].job;
  care.loadID=0;p.jobs.current=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.Wait_MaintainPosture);
  var posture=p.CurJob;RIMAPI.Helpers.MedicalTendReviewHelper.Tick();
  Check(p.CurJob==posture && p.jobs.jobQueue.Any(q=>q.job==wait),"Native completed-tend posture bridge lost exact review");
  manual=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.Manual);p.jobs.jobQueue.EnqueueLast(manual);
  RIMAPI.Helpers.MedicalTendReviewHelper.Tick();Check(p.CurJob==posture && p.jobs.jobQueue.Count==1 && p.jobs.jobQueue[0].job==manual,"Posture bridge erased late manual queue");
  p=Doctor(out care);RIMAPI.Helpers.MedicalTendReviewHelper.Schedule(p,care);care.loadID=0;p.jobs.current=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.Wait_MaintainPosture);
  RIMAPI.Helpers.CaregiverRecoveryHelper.completed=false;RIMAPI.Helpers.MedicalTendReviewHelper.Tick();
  Check(!p.jobs.jobQueue.Any(),"Unproven completed care claimed a posture bridge");
  return n;
 }
}
'@
Add-Type -TypeDefinition ("using System.Collections.Generic;using System.Linq;using RimWorld;using Verse;using Verse.AI;`n"+$taskCode.Replace('STAMP',$taskStamp)+$taskSource.Replace('using System.Collections.Generic;','').Replace('using System.Linq;','').Replace('using RimWorld;','').Replace('using Verse;','').Replace('using Verse.AI;','')) -Language CSharp
[MedicalReviewBoundary]::Run()

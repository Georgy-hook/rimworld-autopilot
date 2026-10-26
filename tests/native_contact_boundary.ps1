$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskHelper=Get-Content -Raw -LiteralPath (Join-Path $taskRoot 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatContactHelper.cs')
$taskOrder=Get-Content -Raw -LiteralPath (Join-Path $taskRoot 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatOrderHelper.cs')
$taskStamp=[regex]::Match($taskOrder,'(?s)internal sealed class CombatJobStamp\s*\{.*?\r?\n    \}').Value
if(-not $taskStamp){throw 'Actual pooled-job stamp unavailable'}
$taskCode=@'
namespace Verse {
 public class JobDef {}
 public struct Position {public int x;public float DistanceTo(Position other)=>System.Math.Abs(x-other.x);}
 public class Target {public Pawn Thing;}
 public class Pawn {
  public int thingIDNumber,Map=1;public bool Spawned=true,Dead,Downed,InMentalState,Drafted=true,Threat=true;
  public Position Position;public Verse.AI.Tracker jobs=new Verse.AI.Tracker();public Verse.AI.Job CurJob=>jobs.current;
 }
}
namespace RimWorld {public static class JobDefOf {public static Verse.JobDef AttackMelee=new Verse.JobDef(),Wait=new Verse.JobDef();}}
namespace Verse.AI {
 public enum JobCondition {InterruptForced}
 public class Job {public int loadID=1;public Verse.JobDef def;public bool killIncappedTarget;public Verse.Target targetA=new Verse.Target();}
 public class QueuedJob {public Job job;}
 public class Queue:System.Collections.Generic.List<QueuedJob> {
  public void RemoveAll(Verse.Pawn p,System.Predicate<Job> predicate) {base.RemoveAll(q=>predicate(q.job));}
 }
 public class Tracker {
  public Job current;public Queue jobQueue=new Queue();public int ended;
  public void EndCurrentJob(JobCondition reason,bool startNext) {ended++;current=null;if(startNext && jobQueue.Count>0){current=jobQueue[0].job;jobQueue.RemoveAt(0);}}
 }
}
namespace RIMAPI.Helpers {
 STAMP
 public static class CombatNativeHelper {public static bool IsPlayerThreat(Verse.Pawn p)=>p.Threat;}
 public static class CombatOrderHelper {
  public static readonly System.Collections.Generic.HashSet<Verse.AI.Job> Selected=new System.Collections.Generic.HashSet<Verse.AI.Job>();
  public static bool Owned(Verse.Pawn p,Verse.AI.Job j)=>Selected.Contains(j);
 }
}
'@
$taskTests=@'
public static class ContactBoundary {
 static int n;static void Check(bool ok,string message){n++;if(!ok)throw new System.Exception(message);}
 static Verse.AI.Job Job(Verse.Pawn target,bool owned=true){var j=new Verse.AI.Job{def=RimWorld.JobDefOf.AttackMelee,targetA=new Verse.Target{Thing=target}};if(owned)RIMAPI.Helpers.CombatOrderHelper.Selected.Add(j);return j;}
 static Verse.Pawn Pawn(int x)=>new Verse.Pawn{Position=new Verse.Position{x=x}};
 public static int Run(){
  var enemy=Pawn(1);var actor=Pawn(0);var job=Job(enemy);actor.jobs.current=job;
  RIMAPI.Helpers.CombatContactHelper.Remember(actor,job);RIMAPI.Helpers.CombatContactHelper.Tick();
  Check(actor.CurJob==job && actor.jobs.ended==0,"Actual adjacent defense was cancelled");
  var later=new Verse.AI.Job{def=RimWorld.JobDefOf.Wait};actor.jobs.jobQueue.Add(new Verse.AI.QueuedJob{job=later});
  enemy.Position=new Verse.Position{x=4};RIMAPI.Helpers.CombatContactHelper.Tick();
  Check(actor.jobs.ended==1 && actor.CurJob==later,"Contact loss did not end only its own job and start later queued work");
  actor=Pawn(0);enemy=Pawn(1);job=Job(enemy);actor.jobs.current=job;RIMAPI.Helpers.CombatContactHelper.Remember(actor,job);
  var manual=new Verse.AI.Job{def=RimWorld.JobDefOf.Wait};actor.jobs.current=manual;enemy.Position=new Verse.Position{x=5};
  RIMAPI.Helpers.CombatContactHelper.Tick();Check(actor.CurJob==manual && actor.jobs.ended==0,"A later manual/care job was replaced");
  actor=Pawn(0);enemy=Pawn(5);job=Job(enemy);actor.jobs.current=manual;actor.jobs.jobQueue.Add(new Verse.AI.QueuedJob{job=job});actor.jobs.jobQueue.Add(new Verse.AI.QueuedJob{job=later});
  RIMAPI.Helpers.CombatContactHelper.Remember(actor,job);RIMAPI.Helpers.CombatContactHelper.Tick();
  Check(actor.CurJob==manual && actor.jobs.jobQueue.Count==1 && actor.jobs.jobQueue[0].job==later,"Removing a stale queued contact erased another instruction");
  actor=Pawn(0);enemy=Pawn(1);job=Job(enemy);actor.jobs.current=job;RIMAPI.Helpers.CombatContactHelper.Remember(actor,job);actor.Drafted=false;
  RIMAPI.Helpers.CombatContactHelper.Tick();Check(actor.CurJob==null,"An undrafted actor continued the selected melee chase");
  actor=Pawn(0);enemy=Pawn(1);job=Job(enemy);actor.jobs.current=job;RIMAPI.Helpers.CombatContactHelper.Remember(actor,job);enemy.Downed=true;
  RIMAPI.Helpers.CombatContactHelper.Tick();Check(actor.CurJob==null,"Contact defense became an execution of a downed enemy");
  actor=Pawn(0);enemy=Pawn(5);job=Job(enemy,false);actor.jobs.current=job;RIMAPI.Helpers.CombatContactHelper.Remember(actor,job);
  RIMAPI.Helpers.CombatContactHelper.Tick();Check(actor.CurJob==job,"An unrelated explicit offensive melee order was adopted as self-defense");
  actor=Pawn(0);enemy=Pawn(1);job=Job(enemy);actor.jobs.current=job;RIMAPI.Helpers.CombatContactHelper.Remember(actor,job);job.loadID++;enemy.Position=new Verse.Position{x=5};
  RIMAPI.Helpers.CombatContactHelper.Tick();Check(actor.CurJob==job,"A pooled job reference retained ownership after its native ID changed");
  actor=Pawn(0);enemy=Pawn(1);job=Job(enemy);actor.jobs.current=job;RIMAPI.Helpers.CombatContactHelper.Remember(actor,job);job.killIncappedTarget=true;enemy.Downed=true;
  RIMAPI.Helpers.CombatContactHelper.Tick();Check(actor.CurJob==job,"A later explicit finishing upgrade in the same job was overwritten by old self-defense ownership");
  return n;
 }
}
'@
Add-Type -TypeDefinition ("using System.Collections.Generic; using System.Linq; using RimWorld; using Verse; using Verse.AI;`n" + ($taskCode.Replace('STAMP',$taskStamp)) + $taskHelper.Replace('using System.Collections.Generic;','').Replace('using System.Linq;','').Replace('using RimWorld;','').Replace('using Verse;','').Replace('using Verse.AI;','') + $taskTests) -Language CSharp
[ContactBoundary]::Run()

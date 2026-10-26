$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatOrderHelper.cs')
$taskStubs=@'
namespace Verse {
 public class JobDef { public string name; }
 public class ThingDef {public bool IsRangedWeapon;}
 public class ThingWithComps {public ThingDef def=new ThingDef();}
 public class EquipmentTracker {public ThingWithComps Primary;}
 public struct LocalTargetInfo {
  public Pawn Thing; public int Cell;
  public static bool operator ==(LocalTargetInfo a,LocalTargetInfo b)=>a.Thing==b.Thing && a.Cell==b.Cell;
  public static bool operator !=(LocalTargetInfo a,LocalTargetInfo b)=>!(a==b);
  public override bool Equals(object o)=>o is LocalTargetInfo && this==(LocalTargetInfo)o;
  public override int GetHashCode()=>Cell;
 }
 public class Pawn {
  public bool Spawned=true,Dead,Care; public Verse.AI.Tracker jobs;public EquipmentTracker equipment;
  public Pawn(){jobs=new Verse.AI.Tracker(this);} public Verse.AI.Job CurJob=>jobs.current;
 }
}
namespace RimWorld {
 public static class JobDefOf {
  public static Verse.JobDef Goto=new Verse.JobDef{name="Goto"},AttackStatic=new Verse.JobDef{name="AttackStatic"},Wait_Combat=new Verse.JobDef{name="Wait_Combat"};
 }
}
namespace Verse.AI {
 public class Job {
  public Verse.JobDef def; public Verse.LocalTargetInfo targetA,targetB,targetC; public bool playerForced,checkOverrideOnExpire;
  public int loadID,locomotionUrgency,expiryInterval;public bool canUseRangedWeapon=true;
 }
 public class QueuedJob {public Job job;}
 public class Queue:System.Collections.Generic.List<QueuedJob> {
  public void EnqueueLast(Job j){Add(new QueuedJob{job=j});}
  public void RemoveAll(Verse.Pawn p,System.Predicate<Job> predicate){
   foreach(var q in this.Where(q=>predicate(q.job)).ToArray()){Remove(q);q.job.def=null;q.job.loadID=0;}
  }
 }
 public static class JobMaker {
  static int next;public static Job MakeJob(Verse.JobDef def,Verse.Pawn target=null)=>new Job{def=def,loadID=++next,targetA=new Verse.LocalTargetInfo{Thing=target}};
 }
 public class Tracker {
  Verse.Pawn pawn;public Job current;public bool Defer,Copy,AckOnly; public Queue jobQueue=new Queue();
  public Tracker(Verse.Pawn p){pawn=p;}
  public bool Take(Job j){
   if(AckOnly)return true;
   if(current!=null && current.def==j.def && current.targetA==j.targetA && current.targetB==j.targetB && current.targetC==j.targetC)return true;
   jobQueue.RemoveAll(pawn,x=>true);
   if(Copy){var copy=JobMaker.MakeJob(j.def,j.targetA.Thing);copy.targetA=j.targetA;copy.targetB=j.targetB;copy.targetC=j.targetC;copy.locomotionUrgency=j.locomotionUrgency;copy.playerForced=true;j=copy;}
   if(Defer)jobQueue.EnqueueLast(j);else current=j;
   return true;
  }
 }
}
namespace RIMAPI.Helpers {
 public static class CareTriageHelper {public static bool QueuedCare(Verse.Pawn p)=>p.Care;}
 public static class CombatControlHelper {public static bool PreserveTeamMove(Verse.Pawn p,Verse.AI.Job j){return false;}
 public static bool PreserveMoveBeforeShot(Verse.Pawn p,Verse.AI.Job j)=>false;}
 public static class MentalSafetyHelper {public static bool TakeDefenceOrder(Verse.Pawn p,Verse.AI.Job j){j.playerForced=true;return p.jobs.Take(j);}}
}
public static class CombatOrderRegression {
 static int count;static void Check(bool ok,string message){count++;if(!ok)throw new System.Exception(message);}
 public static int Run(){
  var pawn=new Verse.Pawn();var enemy=new Verse.Pawn();var other=new Verse.Pawn();
  var move=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.Goto);move.targetA=new Verse.LocalTargetInfo{Cell=4};
  Check(RIMAPI.Helpers.CombatOrderHelper.Take(pawn,ref move) && move==pawn.CurJob,"Initial native accepted move missing");
  var shot=RIMAPI.Helpers.CombatOrderHelper.QueueShot(pawn,enemy);
  for(int i=0;i<4;i++)Check(RIMAPI.Helpers.CombatOrderHelper.QueueShot(pawn,enemy)==shot,"Repeated aim appended duplicate shots");
  Check(pawn.jobs.jobQueue.Count==1,"One move accumulated multiple selected shots");
  var repeat=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.Goto);repeat.targetA=move.targetA;
  Check(RIMAPI.Helpers.CombatOrderHelper.Take(pawn,ref repeat) && repeat==move,"Equivalent native Goto retained an unused request reference");
  Check(pawn.jobs.jobQueue.Count==1 && pawn.jobs.jobQueue[0].job==shot,"Equivalent owned move erased its selected follow-up");
  var next=RIMAPI.Helpers.CombatOrderHelper.QueueShot(pawn,other);
  Check(next!=null && pawn.jobs.jobQueue.Count==1 && next.targetA.Thing==other,"Retarget did not leave one exact pending shot");
  var manual=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.AttackStatic,enemy);pawn.jobs.jobQueue.EnqueueLast(manual);
  var refused=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.Goto);
  Check(!RIMAPI.Helpers.CombatOrderHelper.Take(pawn,ref refused) && pawn.jobs.jobQueue.Any(q=>q.job==manual),"Manual queue erased by a tactical replacement");
  Check(RIMAPI.Helpers.CombatOrderHelper.QueueShot(pawn,enemy)==null,"New selected shot appended across unrelated queued intent");
  RIMAPI.Helpers.CombatOrderHelper.DropQueued(pawn);
  Check(pawn.jobs.jobQueue.Count==1 && pawn.jobs.jobQueue[0].job==manual,"Owned queue cleanup erased unrelated instruction");
  var stamped=new RIMAPI.Helpers.CombatJobStamp(next);
  pawn.jobs.current=next;next.loadID+=100000;
  Check(stamped.Value==null,"Completed plan retained a pooled reference after its native ID changed");
  Check(!RIMAPI.Helpers.CombatOrderHelper.Owned(pawn,next),"Recycled job reference retained ownership under a different native ID");
  var deferred=new Verse.Pawn();deferred.jobs.Defer=true;deferred.jobs.current=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.AttackStatic,enemy);
  var queued=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.Goto);queued.targetA=new Verse.LocalTargetInfo{Cell=8};
  Check(RIMAPI.Helpers.CombatOrderHelper.Take(deferred,ref queued) && deferred.CurJob!=queued && deferred.jobs.jobQueue[0].job==queued,"Deferred ACK was confused with current movement");
  var pendingShot=RIMAPI.Helpers.CombatOrderHelper.QueueShot(deferred,enemy);
  var repeatedPending=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.Goto);repeatedPending.targetA=queued.targetA;
  Check(RIMAPI.Helpers.CombatOrderHelper.Take(deferred,ref repeatedPending) && repeatedPending==queued,"Equivalent pending move replaced its exact native job");
  Check(deferred.jobs.jobQueue.Count==2 && deferred.jobs.jobQueue[0].job==queued && deferred.jobs.jobQueue[1].job==pendingShot,"Equivalent pending move cleared its follow-up");
  var copied=new Verse.Pawn();copied.jobs.Copy=true;var request=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.Goto);
  Check(RIMAPI.Helpers.CombatOrderHelper.Take(copied,ref request) && request==copied.CurJob,"Copied native accepted move lost ownership");
  var ack=new Verse.Pawn();ack.jobs.AckOnly=true;var absent=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.AttackStatic,enemy);
  Check(!RIMAPI.Helpers.CombatOrderHelper.Take(ack,ref absent),"ACK with no observed job was treated as execution");
  var patient=new Verse.Pawn();patient.Care=true;var attack=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.AttackStatic,enemy);
  Check(!RIMAPI.Helpers.CombatOrderHelper.Take(patient,ref attack) && patient.CurJob==null,"Combat queue displaced protected care");
  var held=new Verse.Pawn{equipment=new Verse.EquipmentTracker{Primary=new Verse.ThingWithComps{def=new Verse.ThingDef{IsRangedWeapon=true}}}};
  var hold=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.Wait_Combat);
  Check(RIMAPI.Helpers.CombatOrderHelper.Take(held,ref hold) && !held.CurJob.canUseRangedWeapon,"Owned hold still lets native idle choose an unchecked shooting target");
  var clone=new Verse.Pawn{equipment=held.equipment};clone.jobs.Copy=true;
  var cloneHold=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.Wait_Combat);
  Check(RIMAPI.Helpers.CombatOrderHelper.Take(clone,ref cloneHold) && !clone.CurJob.canUseRangedWeapon,"Native copied hold lost the selected-only firing flag");
  var foreign=new Verse.Pawn{equipment=held.equipment};var oldHold=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.Wait_Combat);foreign.jobs.current=oldHold;
  var later=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.Goto);foreign.jobs.jobQueue.EnqueueLast(later);
  var refusedHold=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.Wait_Combat);
  Check(!RIMAPI.Helpers.CombatOrderHelper.Take(foreign,ref refusedHold) && oldHold.canUseRangedWeapon && refusedHold.canUseRangedWeapon && foreign.jobs.jobQueue[0].job==later,"A refused hold altered a foreign current/queued instruction");
  var melee=new Verse.Pawn();var meleeHold=Verse.AI.JobMaker.MakeJob(RimWorld.JobDefOf.Wait_Combat);
  Check(RIMAPI.Helpers.CombatOrderHelper.Take(melee,ref meleeHold) && meleeHold.canUseRangedWeapon,"Nonranged native hold was changed unnecessarily");
  RIMAPI.Helpers.CombatOrderHelper.Prune();
  return count;
 }
}
'@
Add-Type -TypeDefinition ($taskSource+"`n"+$taskStubs) -Language CSharp
[CombatOrderRegression]::Run()

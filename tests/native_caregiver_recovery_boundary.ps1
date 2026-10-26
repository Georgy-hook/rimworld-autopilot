$ErrorActionPreference='Stop'
$taskRepo=Split-Path -Parent $PSScriptRoot
$taskSource=Get-Content -Raw -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CaregiverRecoveryHelper.cs')
function Get-TaskMethod([string]$signature) {
 $start=$taskSource.IndexOf($signature)
 if($start -lt 0){throw "Missing actual method $signature"}
 $brace=$taskSource.IndexOf('{',$start);$depth=1;$end=$brace+1
 while($depth -gt 0){if($taskSource[$end] -eq '{'){$depth++};if($taskSource[$end] -eq '}'){$depth--};$end++}
 return $taskSource.Substring($start,$end-$start)
}
$taskMethods=@('private static bool NativePostMealBridge(','private static bool Take(','public static void Ordered(','public static bool Protected(','private static void ReturnToCare(','public static void Tick(') | ForEach-Object {Get-TaskMethod $_}
$taskCode=@'
using System;using System.Linq;using System.Collections.Generic;
public static class JobDefOf {public static object Wait=new object(),Ingest=new object(),LayDown=new object(),Manual=new object(),TendPatient=new object(),Wait_MaintainPosture=new object();}
public enum JobCondition {Succeeded}
public class Job {public int loadID,expiryInterval;public bool playerForced,checkOverrideOnExpire;public object def,targetA;}
public static class JobMaker {static int next;public static Job MakeJob(object d)=>new Job{def=d,loadID=++next};}
public class Q {public Job job;}
public class Queue:List<Q>{public void EnqueueLast(Job j)=>Add(new Q{job=j});}
public class Tracker {Pawn p;public Job current;public Queue jobQueue=new Queue();public Tracker(Pawn owner){p=owner;}
 public bool TryTakeOrderedJob(Job j){CaregiverRecoveryHelper.Ordered(p);current=j;return true;}
 public void EndCurrentJob(JobCondition c){current.loadID=0;current=null;if(jobQueue.Any()){current=jobQueue[0].job;jobQueue.RemoveAt(0);}}
}
public class Need {public float CurLevelPercentage;}
public class Needs {public Need food=new Need(),rest=new Need();}
public class Carry {public object CarriedThing;}
public class Pawn {public bool Spawned=true,Dead,Downed,Drafted,InMentalState,nativeRest;public object Map=Find.Map;public Tracker jobs;public Needs needs=new Needs();public Carry carryTracker=new Carry();public Pawn(){jobs=new Tracker(this);}public Job CurJob=>jobs.current;public object CurJobDef=>CurJob?.def;}
public static class Find {public static object Map=new object();public static List<object> Maps=new List<object>{Map};public static Clock TickManager=new Clock();}
public class Clock {public int TicksGame;}
public class CombatJobStamp {Job job;int id;public CombatJobStamp(Job j){job=j;id=j.loadID;}public Job Value=>job.loadID==id?job:null;}
public static class CaregiverRecoveryHelper {
 private const int RestTicks=3600;
 private sealed class Completed {public int JobId=0,Tick=0;}
 private sealed class Window {public int Until,TotalUntil,TransitionUntil;public string Stage;public CombatJobStamp Job;public float Food,Rest;}
 private static Dictionary<Pawn,Completed> Tends=new Dictionary<Pawn,Completed>();private static Dictionary<Pawn,Window> Windows=new Dictionary<Pawn,Window>();private static HashSet<Pawn> Issuing=new HashSet<Pawn>();
 private static bool clinical=true;private static void Record(Pawn p,string s){}
 private static bool Controllable(Pawn p)=>p!=null && p.Spawned && !p.Dead && !p.Downed && !p.Drafted && !p.InMentalState && Find.Maps.Contains(p.Map) && !p.jobs.jobQueue.Any() && !(p.carryTracker?.CarriedThing is Pawn);
 private static bool ClinicalWindow(Pawn p)=>clinical;
 private static bool NativeRestAfterMeal(Pawn p,Window w)=>p.nativeRest;
 METHODS
 static int count;static void Check(bool ok,string message){count++;if(!ok)throw new Exception(message);}
 static Pawn Setup(object def,string stage){Windows.Clear();Issuing.Clear();Find.TickManager.TicksGame=0;clinical=true;var p=new Pawn();p.jobs.current=JobMaker.MakeJob(def);p.needs.food.CurLevelPercentage=.9f;p.needs.rest.CurLevelPercentage=.1f;Windows[p]=new Window{Stage=stage,Until=1200,TotalUntil=4800,Job=new CombatJobStamp(p.CurJob),Food=.2f,Rest=.1f};return p;}
 public static int Run(){
  var p=Setup(JobDefOf.Ingest,"Ingest");Check(Protected(p),"Actual food interrupted");
  p.jobs.current=JobMaker.MakeJob(JobDefOf.LayDown);p.nativeRest=true;Tick();Check(Windows[p].Stage=="LayDown" && Protected(p),"Native safe post-meal sleep dropped");
  int sleep=p.CurJob.loadID;Find.TickManager.TicksGame=3601;Check(!Protected(p) && Windows.ContainsKey(p),"Read-only expiry erased return state");Tick();
  Check(p.CurJobDef==JobDefOf.Wait && p.CurJob.expiryInterval==180 && !Windows.ContainsKey(p),"Finite sleep failed to return clinical window");
  Check(p.needs.rest.CurLevelPercentage==.1f && p.needs.food.CurLevelPercentage==.9f,"Needs fabricated");
  p=Setup(JobDefOf.LayDown,"LayDown");var queued=JobMaker.MakeJob(JobDefOf.TendPatient);p.jobs.jobQueue.EnqueueLast(queued);Tick();Check(p.CurJob==queued,"Later medical queue lost or blocked behind own sleep");
  p=Setup(JobDefOf.LayDown,"LayDown");var manual=JobMaker.MakeJob(JobDefOf.Manual);p.jobs.TryTakeOrderedJob(manual);Tick();Check(p.CurJob==manual && !Windows.ContainsKey(p),"Later explicit order overwritten");
  p=Setup(JobDefOf.Ingest,"Ingest");var explicitSleep=JobMaker.MakeJob(JobDefOf.LayDown);p.jobs.TryTakeOrderedJob(explicitSleep);p.nativeRest=true;Tick();Check(!Windows.ContainsKey(p) && p.CurJob==explicitSleep,"Unmarked explicit bed instruction adopted");
  p=Setup(JobDefOf.LayDown,"LayDown");p.CurJob.loadID++;Tick();Check(p.CurJobDef==JobDefOf.LayDown && !Windows.ContainsKey(p),"Pooled/reused Job was ended");
  p=Setup(JobDefOf.LayDown,"LayDown");p.Drafted=true;Tick();Check(p.CurJobDef==JobDefOf.LayDown,"Unavailable actor was ordered");
  p=Setup(JobDefOf.LayDown,"LayDown");clinical=false;Tick();Check(p.CurJobDef==JobDefOf.Wait,"New clinical urgency retained optional rest");
  p=Setup(JobDefOf.LayDown,"LayDown");var own=JobMaker.MakeJob(JobDefOf.Ingest);Check(Take(p,own) && Windows.ContainsKey(p),"Own native need dispatch mistaken for external order");
  p=Setup(JobDefOf.Ingest,"Ingest");p.jobs.current=JobMaker.MakeJob(JobDefOf.Wait_MaintainPosture);
  Check(Protected(p),"Native post-meal posture was unprotected");Tick();Check(Windows.ContainsKey(p) && Windows[p].TransitionUntil==180,"Post-meal bridge was discarded or has no fixed deadline");
  p.jobs.current=JobMaker.MakeJob(JobDefOf.LayDown);p.nativeRest=true;Tick();Check(Windows[p].Stage=="LayDown","Native bridge did not reach bounded sleep");
  p=Setup(JobDefOf.Ingest,"Ingest");p.jobs.current=JobMaker.MakeJob(JobDefOf.Wait_MaintainPosture);Tick();Find.TickManager.TicksGame=181;Tick();Check(!Windows.ContainsKey(p),"Posture bridge renewed without progress");
  return count;
 }
}
'@
Add-Type -TypeDefinition $taskCode.Replace('METHODS',($taskMethods -join "`n")) -Language CSharp
$taskPassed=[CaregiverRecoveryHelper]::Run()
Write-Output "native caregiver recovery boundary: $taskPassed cases passed"

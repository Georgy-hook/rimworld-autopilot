$ErrorActionPreference='Stop'
$taskBase=Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatTeamCareHelper.cs')
$taskStart=$taskSource.IndexOf('        private static void StopUnsafeOwnedShot(')
$taskEnd=$taskSource.IndexOf('        private static bool TryTeamFirstCare(', $taskStart)
if($taskStart -lt 0 -or $taskEnd -lt $taskStart){throw 'Missing actual controlled stop method'}
$taskMethod=$taskSource.Substring($taskStart,$taskEnd-$taskStart)
$taskCode=@'
using System;using System.Collections.Generic;
public sealed class Job {public string def;public bool playerForced,canUseRangedWeapon=true;public int id;}
public static class JobDefOf {public const string Wait_Combat="Wait_Combat";}
public enum JobCondition {InterruptForced}
public static class JobMaker {static int next;public static Job MakeJob(string def)=>new Job{def=def,id=++next};}
public sealed class Jobs {public Job current=new Job{def="AttackStatic"};public Job later;public int Ends;public void EndCurrentJob(JobCondition c,bool start){Ends++;current=null;}}
public sealed class Pawn {public Jobs jobs=new Jobs();}
public sealed class Plan {public Pawn Pawn=new Pawn();public Job OwnedJob,QueuedShot;public string Mode;}
public static class CombatOrderHelper {
 public static bool Accept=true;public static HashSet<Job> Owned=new HashSet<Job>();
 public static bool Take(Pawn p,ref Job j){if(!Accept || p.jobs.later!=null)return false;j.canUseRangedWeapon=false;p.jobs.current=j;Owned.Add(j);return true;}
 public static void DropQueued(Pawn p){}
}
public static class ActualUnsafeHoldRegression {
 static int n;static void Check(bool ok,string why){n++;if(!ok)throw new Exception(why);}
 static void TeamEvent(string s,Pawn p){}
METHOD
 public static int Run(){
  var p=new Plan();var before=p.Pawn.jobs.current;StopUnsafeOwnedShot(p);
  Check(p.OwnedJob==p.Pawn.jobs.current && CombatOrderHelper.Owned.Contains(p.OwnedJob),"Stopped shot lost its selected cohort ownership");
  Check(p.OwnedJob.def==JobDefOf.Wait_Combat && p.OwnedJob.playerForced && !p.OwnedJob.canUseRangedWeapon,"Stopped shot restarted arbitrary vanilla automatic fire");
  Check(p.Pawn.jobs.Ends==0,"Ended job before controlled replacement acceptance");
  Check(!CombatOrderHelper.Owned.Contains(before),"Adopted native job rather than exact accepted hold");
  Check(p.QueuedShot==null && p.Mode=="shoot","Old selected shot survived controlled stop");
  p=new Plan();var foreign=new Job{def="ManualCare"};p.Pawn.jobs.later=foreign;StopUnsafeOwnedShot(p);
  Check(p.Pawn.jobs.later==foreign,"Later foreign instruction was erased");
  Check(p.Pawn.jobs.Ends==1 && p.OwnedJob==null,"Rejected controlled hold falsely reported ownership or left unsafe shot running");
  return n;
 }
}
'@
Add-Type -TypeDefinition $taskCode.Replace('METHOD',$taskMethod) -Language CSharp
[ActualUnsafeHoldRegression]::Run()
if($taskSource -notmatch 'StopUnsafeOwnedShot\(plan\);'){throw 'Controlled stop not called by real urgent safety'}
$taskCohort=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatFallbackCohortHelper.cs')
if($taskCohort -notmatch 'physicianRejoin\?GenRadial.RadialCellsAround\(pawn.Position,10,false\)' -or
   $taskCohort -notmatch 'physicianRejoin\?CoveredPhysicianRejoin\(pawn,path\):SaferRangedRoute' -or
   $taskCohort -notmatch 'CohortAccess\(cohort,pawn,cell,travel' -or
   $taskCohort -notmatch 'CohortArrivalShot\(pawn,cell,path.TotalCost,physicianRejoin\?new List<Pawn>\{enemy\}:threats\)'){
 throw 'Local edge search lost the measured route, same-enemy shot or clinical acceptance checks'
}

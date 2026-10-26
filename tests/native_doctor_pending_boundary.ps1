$ErrorActionPreference='Stop'
$taskBase=Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatDoctorDetourHelper.cs')
$taskStart=$taskSource.IndexOf('        private static bool DoctorDetourPending(')
$taskEnd=$taskSource.IndexOf('        private static bool KeepDoctorDetour(', $taskStart)
$taskMethod=$taskSource.Substring($taskStart,$taskEnd-$taskStart)
$taskPending=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatPendingMoveHelper.cs')
$taskMath=$taskPending.Substring($taskPending.IndexOf('    public static class CombatPendingMoveMath'),$taskPending.IndexOf('    public static partial class CombatControlHelper')-$taskPending.IndexOf('    public static class CombatPendingMoveMath'))
$taskOrders=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatOrderHelper.cs')
$taskStamp=$taskOrders.Substring($taskOrders.IndexOf('    internal sealed class CombatJobStamp'),$taskOrders.IndexOf('    // Job objects are pooled')-$taskOrders.IndexOf('    internal sealed class CombatJobStamp'))
$taskCode=@'
using System;
using System.Linq;
using System.Collections.Generic;
MATH
STAMP
public sealed class Job {public int loadID;public bool Owned,playerForced;}
public sealed class QueueEntry {public Job job;}
public sealed class Jobs {public List<QueueEntry> jobQueue=new List<QueueEntry>();}
public static class JobDefOf {public static readonly object Wait_Combat=new object(),Wait_MaintainPosture=new object(),AttackStatic=new object(),Goto=new object();}
public sealed class Pawn {public Jobs jobs=new Jobs();public Job CurJob;public object CurJobDef;public float TicksPerMoveCardinal=20;}
public static class CombatOrderHelper {public static bool Owned(Pawn p,Job j)=>j!=null && j.Owned;}
public static class Find {public static Clock TickManager=new Clock();}
public sealed class Clock {public int TicksGame;}
public static class RealQueuedDoctorRegression {
 sealed class DoctorDetour {public CombatJobStamp First;public int Started;}
 sealed class SelectedMove {public int InitialLock;}
 static readonly Dictionary<Pawn,SelectedMove> SelectedMoves=new Dictionary<Pawn,SelectedMove>();
 static int n;
 static void Check(bool b,string why){n++;if(!b)throw new Exception(why);}
METHOD
 public static int Run(){
  var first=new Job{loadID=1,Owned=true,playerForced=true};var current=new Job{loadID=2,Owned=true};
  var p=new Pawn{CurJob=current,CurJobDef=JobDefOf.AttackStatic};p.jobs.jobQueue.Add(new QueueEntry{job=first});
  var d=new DoctorDetour{First=new CombatJobStamp(first),Started=100};SelectedMoves[p]=new SelectedMove{InitialLock=90};Find.TickManager.TicksGame=120;
  Check(DoctorDetourPending(p,d),"Exact accepted queued Goto was discarded while owned native cooldown still held the previous job");
  Find.TickManager.TicksGame=281;Check(!DoctorDetourPending(p,d),"A queued exit became an unlimited busy wait");Find.TickManager.TicksGame=120;
  var foreign=new Job{loadID=3,Owned=false};p.jobs.jobQueue.Add(new QueueEntry{job=foreign});
  Check(!DoctorDetourPending(p,d),"A later foreign/clinical queue was ignored");p.jobs.jobQueue.RemoveAt(1);
  current.Owned=false;current.playerForced=true;p.CurJobDef=JobDefOf.Goto;
  Check(!DoctorDetourPending(p,d),"A manual current move was adopted merely because an old accepted Goto remained queued");
  current.playerForced=false;p.CurJobDef=JobDefOf.Wait_Combat;
  Check(DoctorDetourPending(p,d),"Ordinary native idle before the exact queued exit was rejected");
  first.loadID=99;Check(!DoctorDetourPending(p,d),"A pooled job object with a different loadID retained the old corridor");
  return n;
 }
}
'@
$taskCode=$taskCode.Replace('MATH',$taskMath).Replace('STAMP',$taskStamp).Replace('METHOD',$taskMethod)
Add-Type -TypeDefinition $taskCode -Language CSharp
[RealQueuedDoctorRegression]::Run()

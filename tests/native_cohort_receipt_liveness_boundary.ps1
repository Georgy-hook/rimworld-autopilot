$ErrorActionPreference='Stop'
$taskHelpers=Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers'
$taskFallback=Get-Content -Raw -LiteralPath (Join-Path $taskHelpers 'CombatFallbackCohortHelper.cs')
$taskGroup=Get-Content -Raw -LiteralPath (Join-Path $taskHelpers 'CombatGroupCoordinationHelper.cs')
function Extract-Block([string]$source,[string]$signature) {
 $start=$source.IndexOf($signature);if($start -lt 0){throw "Missing $signature"}
 $open=$source.IndexOf('{',$start);$depth=0
 for($i=$open;$i -lt $source.Length;$i++){
  if($source[$i] -eq '{'){$depth++};if($source[$i] -eq '}'){$depth--;if($depth -eq 0){return $source.Substring($start,$i-$start+1)}}
 };throw "Unclosed $signature"
}
$taskCohort=Extract-Block $taskFallback 'private sealed class FallbackCohort'
$taskReopen=Extract-Block $taskFallback 'private static void ReopenCompletedCohortBound'
$taskStart=$taskGroup.IndexOf('private static bool OwnStationaryGun');$taskEnd=$taskGroup.IndexOf(';',$taskStart)
$taskStationary=$taskGroup.Substring($taskStart,$taskEnd-$taskStart+1)
$taskStart=$taskFallback.IndexOf('private static int CohortMovingCount');$taskEnd=$taskFallback.IndexOf(';',$taskStart)
$taskMoving=$taskFallback.Substring($taskStart,$taskEnd-$taskStart+1)
$taskStart=$taskFallback.IndexOf('private static IntVec3 CohortFormationPost');$taskEnd=$taskFallback.IndexOf(';',$taskStart)
$taskFormation=$taskFallback.Substring($taskStart,$taskEnd-$taskStart+1)
$taskStart=$taskFallback.IndexOf('    public static class CombatFallbackMath');$taskEnd=$taskFallback.IndexOf('    public static partial class CombatControlHelper')
$taskMath=$taskFallback.Substring($taskStart,$taskEnd-$taskStart)
$taskCode=@'
using System;using System.Linq;using System.Collections.Generic;
MATH
public struct IntVec3 {public int x,z;public IntVec3(int n,int b=0){x=n;z=b;}public static IntVec3 Zero=>new IntVec3(0,0);public static IntVec3 operator +(IntVec3 a,IntVec3 b)=>new IntVec3(a.x+b.x,a.z+b.z);}
public class Job {public bool playerForced;}
public class QueueEntry {public Job job;}
public class Jobs {public List<QueueEntry> jobQueue=new List<QueueEntry>();}
public class Pather {public bool Moving;}
public class Carry {public object CarriedThing;}
public class Pawn {public bool Safe=true,Owned;public object CurJobDef;public Job CurJob;public Jobs jobs=new Jobs();public Pather pather=new Pather();public Carry carryTracker=new Carry();}
public static class JobDefOf {public static object Goto=new object(),AttackMelee=new object(),Wait_Combat=new object();}
public static class CombatOrderHelper {public static bool Owned(Pawn p,Job j)=>p.Owned;}
public class Plan {public Pawn Pawn;}
public class FallbackMove {}
public static class CohortReceiptRegression {
 static bool Valid(Plan p)=>p.Pawn.Safe;
 static bool CohortInTransit(Plan p)=>false;static bool DoctorBoundInTransit(Plan p)=>false;
 static Dictionary<Pawn,FallbackMove> FallbackMoves=new Dictionary<Pawn,FallbackMove>();
 COHORT
 REOPEN
 STATIONARY
 MOVING
 FORMATION
 static int n;static void Check(bool ok,string why){n++;if(!ok)throw new Exception(why);}
 public static int Run(){
  var medic=new Pawn();var gun=new Pawn();var c=new FallbackCohort();
  c.Staged.Add(medic);c.Staged.Add(gun);c.Posts[medic]=new IntVec3(117);c.Posts[gun]=new IntVec3(119);
  c.LastMemberReview[medic]=300;FallbackMoves[medic]=new FallbackMove();FallbackMoves[gun]=new FallbackMove();
  ReopenCompletedCohortBound(c,medic);
  Check(!c.Staged.Contains(medic),"Completed medic bound remained closed");
  Check(!c.Posts.ContainsKey(medic),"tick330 would restage the OLD tick210 arrival without any new move");
  Check(!FallbackMoves.ContainsKey(medic),"Old move receipt could license the reopened bound");
  Check(!c.LastMemberReview.ContainsKey(medic),"A reopened deadline retained stale scheduling debt");
  Check(c.Staged.Contains(gun)&&c.Posts.ContainsKey(gun)&&FallbackMoves.ContainsKey(gun),"Another gun lost its covering receipt");
  ReopenCompletedCohortBound(c,medic);Check(c.Posts.ContainsKey(gun),"Repeated review damaged peer state");
  var p=new Pawn{CurJobDef=JobDefOf.Wait_Combat,CurJob=new Job()};var plan=new Plan{Pawn=p};
  Check(OwnStationaryGun(plan),"A fresh selected native idle gun was excluded from coordinated fire");
  p.CurJob.playerForced=true;Check(!OwnStationaryGun(plan),"A foreign forced idle was commandeered");p.CurJob.playerForced=false;
  p.pather.Moving=true;Check(!OwnStationaryGun(plan),"A moving native actor was counted as stationary cover");p.pather.Moving=false;
  p.jobs.jobQueue.Add(new QueueEntry{job=new Job()});Check(!OwnStationaryGun(plan),"A later queued order was stolen");p.jobs.jobQueue.Clear();
  p.Safe=false;Check(!OwnStationaryGun(plan),"Expired/clinical/manual-ineligible actor was admitted");p.Safe=true;
  p.carryTracker.CarriedThing=new Pawn();Check(!OwnStationaryGun(plan),"A carrier was counted as an available gun");
  p.carryTracker.CarriedThing=null;p.CurJobDef=JobDefOf.Goto;p.Owned=true;
  Check(CohortMovingCount(new[]{plan})==1,"A real deadline-guard withdrawal was absent from the shared movement slot");
  p.Owned=false;Check(CohortMovingCount(new[]{plan})==0,"A foreign move acquired a cohort receipt");
  p.CurJobDef=JobDefOf.Wait_Combat;Check(CohortMovingCount(new[]{plan})==0,"A completed move continued occupying a native movement slot");
  c.Anchor=new IntVec3(115,115);c.Offsets[medic]=new IntVec3(0,-1);c.Offsets[gun]=new IntVec3(0,5);
  var m=CohortFormationPost(c,medic);var g=CohortFormationPost(c,gun);
  Check(m.x==115&&m.z==114&&g.x==115&&g.z==120,"A rear translation collapsed separate firing lanes into the common rally disc");
  Check(g.z-m.z==6,"The real initial separation was not preserved by the translated formation");
  Check(!CombatFallbackMath.FormationAuthority(false,0),"An inert ranged proposal vetoed an independent checked position");
  Check(CombatFallbackMath.FormationAuthority(false,1),"A committed cohort bound lost its finite transaction protection");
  Check(CombatFallbackMath.FormationAuthority(true,0),"Initial melee line preparation was lost");
  return n;
 }
}
'@
$taskCode=$taskCode.Replace('COHORT',$taskCohort).Replace('REOPEN',$taskReopen).Replace('STATIONARY',$taskStationary).Replace('MOVING',$taskMoving).Replace('FORMATION',$taskFormation).Replace('MATH',$taskMath)
Add-Type -TypeDefinition $taskCode -Language CSharp -IgnoreWarnings
[CohortReceiptRegression]::Run()

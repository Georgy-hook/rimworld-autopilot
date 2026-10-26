$ErrorActionPreference='Stop'
$taskBase=Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers'
$taskCohort=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatFallbackCohortHelper.cs')
$taskFrom=$taskCohort.IndexOf('    public static class CombatFallbackMath')
$taskMath=$taskCohort.Substring($taskFrom,$taskCohort.IndexOf('    public static partial class CombatControlHelper')-$taskFrom)
$taskSource=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatPhysicianLineHelper.cs')
$taskFrom=$taskSource.IndexOf('        private static bool TryPhysicianCoverPair(')
$taskMethod=$taskSource.Substring($taskFrom,$taskSource.IndexOf('        private static bool CohortCoverWindow(')-$taskFrom)
$taskCode=@'
using System;using System.Linq;using System.Collections.Generic;
MATH
public sealed class Pawn {public int thingIDNumber,Shot=-1;public Pawn Aim;public bool Stationary=true,Free=true,Window=true,Held;}
public sealed class Plan {public Pawn Pawn;}
public sealed class FallbackCohort {public int Created=30;}
public static class Find {public static TickManager TickManager=new TickManager();}public sealed class TickManager {public int TicksGame=100;}
public static class CombatPathBudgetHelper {public static void Checkpoint(string s){}}
public static class CombatShotEvidenceHelper {public static int LastTick(Pawn p,int id)=>p.Aim!=null&&p.Aim.thingIDNumber==id?p.Shot:-1;}
public static class ActualRenewCoverRegression {
 static int n;static void Check(bool ok,string why){n++;if(!ok)throw new Exception(why);}
 static bool CohortStationary(Plan p,List<Pawn> t)=>p.Pawn.Stationary;
 static Pawn AimTarget(Pawn p)=>p.Aim;static float TeamCycle(Pawn p)=>180;
 static bool CohortGunFreeFor(Pawn p,Pawn m,Pawn t)=>p.Free;
 static bool CohortCoverWindow(Pawn p,Pawn t,List<Pawn> e)=>p.Window;
 static bool KeepCoverTurn(Pawn p,Pawn e)=>p.Held;
METHOD
 public static int Run(){
  Check(CombatFallbackMath.RenewCompleted(true,false,true,true,45,300,180,100),"An arrived gun that fired cannot reopen while another original member never stages");
  Check(!CombatFallbackMath.RenewCompleted(false,false,true,true,45,300,180,100),"Melee bound renewal rewrote ranged behavior");
  Check(!CombatFallbackMath.RenewCompleted(true,true,true,true,45,300,180,100),"In-flight native move stolen by new group anchor");
  Check(!CombatFallbackMath.RenewCompleted(true,false,false,true,45,300,180,100),"Assignment counted as arrival");
  Check(!CombatFallbackMath.RenewCompleted(true,false,true,false,45,300,180,100),"Arrival order counted as real covering fire");
  Check(!CombatFallbackMath.RenewCompleted(true,false,true,true,0,300,180,100),"Fresh native arrival's first volley stolen");
  Check(!CombatFallbackMath.RenewCompleted(true,false,true,true,45,1000,180,100),"Safe distant gun peeled without pressure");
  foreach(float bad in new[]{float.NaN,float.PositiveInfinity,-1f})Check(!CombatFallbackMath.RenewCompleted(true,false,true,true,45,bad,180,100),"Unknown contact licensed another bound");
  var mover=new Plan{Pawn=new Pawn{thingIDNumber=1}};var target=new Pawn{thingIDNumber=3};var other=new Pawn{thingIDNumber=4};var p=new Pawn{thingIDNumber=2,Aim=other,Shot=80};var gun=new Plan{Pawn=p};var plans=new[]{mover,gun};var threats=new List<Pawn>{target,other};var cohort=new FallbackCohort();
  Check(TryPhysicianCoverPair(mover,cohort,plans,threats,out var chosen,out var enemy)&&chosen==gun&&enemy==other,"AE: cover for arbitrary unshootable target hides real fire on another observed enemy");
  p.Shot=-1;Check(!TryPhysicianCoverPair(mover,cohort,plans,threats,out chosen,out enemy),"Pending intent became actual cover");p.Shot=20;
  Check(!TryPhysicianCoverPair(mover,cohort,plans,threats,out chosen,out enemy),"Pre-epoch projectile became new cover");p.Shot=80;
  p.Free=false;Check(!TryPhysicianCoverPair(mover,cohort,plans,threats,out chosen,out enemy),"Another mover's real cover lease stolen");p.Free=true;
  p.Window=false;Check(!TryPhysicianCoverPair(mover,cohort,plans,threats,out chosen,out enemy),"Native clinical/contact/exposure/FF window omitted");p.Window=true;
  p.Stationary=false;Check(!TryPhysicianCoverPair(mover,cohort,plans,threats,out chosen,out enemy),"Moving gun counted as cover");p.Stationary=true;
  p.Held=true;Check(!TryPhysicianCoverPair(mover,cohort,plans,threats,out chosen,out enemy),"Active cover-turn ownership bypassed");p.Held=false;
  threats.Remove(other);Check(!TryPhysicianCoverPair(mover,cohort,plans,threats,out chosen,out enemy),"Missing target counted as cover");
  return n;
 }
}
'@
Add-Type -TypeDefinition ($taskCode.Replace('MATH',$taskMath).Replace('METHOD',$taskMethod)) -Language CSharp
[ActualRenewCoverRegression]::Run()
if($taskCohort -notmatch 'completed_bound_reopened_after_actual_fire' -or $taskCohort -notmatch 'physicianRejoin && !actual && TryPhysicianCoverPair' -or $taskCohort -notmatch 'physicianRejoin\?new List<Pawn>\{enemy\}:threats') {throw 'Renewal or exact observed cover target is not wired into actual acceptance'}

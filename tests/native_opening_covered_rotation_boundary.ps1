$ErrorActionPreference='Stop'
$taskBase=Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatCoveredRotationHelper.cs')
$taskStart=$taskSource.IndexOf('    public static class CombatCoveredRotationMath')
$taskMath=$taskSource.Substring($taskStart,$taskSource.IndexOf('    public static partial class CombatControlHelper')-$taskStart)
$taskCohort=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatFallbackCohortHelper.cs')
$taskStart=$taskCohort.IndexOf('private static bool CohortReadyMeleeMover');$taskEnd=$taskCohort.IndexOf(';',$taskStart)
$taskReady=$taskCohort.Substring($taskStart,$taskEnd-$taskStart+1)
$taskCode=@'
using System;using System.Collections.Generic;using System.Linq;
MATH
public class Pawn {public bool Shot,Critical,Warning,Melee=true;}
public class Plan {public Pawn Pawn=new Pawn();}
public static class CombatInterceptHelper {public static bool CanShootNow(Pawn p,Pawn t)=>p.Shot;}
public static class OpeningCoveredRegression {
 static bool MeleeThreat(Pawn p)=>p.Melee;static bool CriticalRangedInjury(Pawn p)=>p.Critical;static bool MedicalFunctionWarning(Pawn p)=>p.Warning;
 READY
 static int n;static void Check(bool b,string s){n++;if(!b)throw new Exception(s);}
 public static int Run(){
  var p=new Plan();var threats=new List<Pawn>{new Pawn()};
  Check(!CohortReadyMeleeMover(p,threats),"An out-of-range healthy short gun consumed the opening withdrawal instead of the firing rifle");
  p.Pawn.Shot=true;Check(CohortReadyMeleeMover(p,threats),"The already useful rifle was excluded from opening cover preparation");
  p.Pawn.Shot=false;p.Pawn.Warning=true;Check(CohortReadyMeleeMover(p,threats),"Medical warning was forced to wait for a shot");p.Pawn.Warning=false;
  p.Pawn.Critical=true;Check(CohortReadyMeleeMover(p,threats),"Critical escape was blocked by opening fire preference");p.Pawn.Critical=false;
  threats[0].Melee=false;Check(CohortReadyMeleeMover(p,threats),"Ranged formation admission changed through the melee opening rule");
  Check(CombatCoveredRotationMath.Review(2,2,2,true,false),"Two real same-enemy guns could not license an early refuge review");
  Check(!CombatCoveredRotationMath.Review(2,2,1,true,false),"A single covering gun was allowed to replace the two-gun bound");
  Check(!CombatCoveredRotationMath.Review(2,2,2,true,true),"A second optional exposed mover abandoned stationary fire");
  Check(!CombatCoveredRotationMath.Review(2,2,2,false,false),"A medical/critical actor was diverted from the existing urgent handler");
  Check(!CombatCoveredRotationMath.Review(0,2,2,true,false),"A future forecast alone caused an exposed optional exit");
  Check(!CombatCoveredRotationMath.Review(2,0,2,true,false),"The stationary future improvement was ignored");
  foreach(float x in new[]{float.NaN,float.PositiveInfinity,-1f}){
   Check(!CombatCoveredRotationMath.Review(x,2,2,true,false),"Unknown current exposure authorized a refuge");
   Check(!CombatCoveredRotationMath.Review(2,x,2,true,false),"Unknown future exposure authorized a refuge");
  }
  return n;
 }
}
'@
Add-Type -TypeDefinition ($taskCode.Replace('MATH',$taskMath).Replace('READY',$taskReady)) -Language CSharp
[OpeningCoveredRegression]::Run()
$taskControl=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatControlHelper.cs')
if($taskControl.IndexOf('PrepareOpeningCohortCover();') -gt $taskControl.IndexOf('ReviewCoordinatedFire();')){throw 'Opening cover selection is still behind the first generic warmup'}
$taskOpening=$taskCohort.Substring($taskCohort.IndexOf('private static void PrepareOpeningCohortCover()'),$taskCohort.IndexOf('private static void ReviewFallbackCohorts()')-$taskCohort.IndexOf('private static void PrepareOpeningCohortCover()'))
if($taskOpening -match 'FindPathNow|CombatPathBudgetHelper.Query|JobDefOf.Goto|Rand\.') {throw 'Opening preparation became an optional path/movement or RNG operation'}
if($taskSource -notmatch 'LastTick\(g,enemy.thingIDNumber\)' -or $taskSource -notmatch 'OwnStationaryGun\(selected\)'){throw 'Actual same-enemy stationary projectile proof was removed'}

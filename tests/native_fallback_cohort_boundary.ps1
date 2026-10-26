$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatFallbackCohortHelper.cs')
$taskStart=$taskSource.IndexOf('    public static class CombatFallbackMath')
$taskEnd=$taskSource.IndexOf('    public static partial class CombatControlHelper')
$taskCode=@'
using System;
MATH
public static class CohortRegression {
 static int n;static void Check(bool ok,string why){n++;if(!ok)throw new Exception(why);}
 public static int Run(){
  Check(!CombatFallbackMath.CoverObserved(30,-1,45,182),"No-shot sentinel licensed a group handoff");
  Check(!CombatFallbackMath.CoverObserved(30,20,45,182),"A shot before this handoff licensed new cover");
  Check(!CombatFallbackMath.CoverObserved(30,60,45,182),"A future timestamp was a real covering shot");
  Check(!CombatFallbackMath.CoverObserved(30,45,400,182),"Expired fire retained a covering role");
  Check(CombatFallbackMath.CoverObserved(30,45,60,182),"Observed same-enemy shot was lost");
  Check(!CombatFallbackMath.CoverObserved(30,45,60,float.NaN),"Unknown cycle licensed fire");
  Check(!CombatFallbackMath.ArrivalMargin(90,60,20,true),"A nearby pursuer caught the mover before its first complete burst");
  Check(!CombatFallbackMath.ArrivalMargin(160,60,20,false),"Uncovered arrival borrowed a covering gun's margin");
  Check(CombatFallbackMath.ArrivalMargin(180,60,20,true),"Real cover and finite complete arrival window rejected");
  Check(!CombatFallbackMath.ArrivalMargin(float.PositiveInfinity,60,20,true),"Unknown contact became a usable window");
  Check(!CombatFallbackMath.Access(200,10000,true),"Doctor was left beyond the finite clinical corridor");
  Check(!CombatFallbackMath.Access(80,650,true),"Walking and first treatment miss the patient's known deadline");
  Check(!CombatFallbackMath.Access(80,10000,false),"A short exposed corridor was called safe access");
  Check(!CombatFallbackMath.Access(float.NaN,10000,true),"Unknown native path became clinical access");
  Check(CombatFallbackMath.Access(120,10000,true),"Checked short protected approach was lost");
  Check(!CombatFallbackMath.LeaveFormation(false,false,14,21),"C: healthy D3 advanced away from the active shared fallback while doctor moved");
  Check(CombatFallbackMath.LeaveFormation(true,false,14,21),"Critical independent exit was blocked by formation");
  Check(CombatFallbackMath.LeaveFormation(false,true,14,21),"Immediate contact escape was blocked by formation");
  Check(CombatFallbackMath.LeaveFormation(false,false,14,8),"Movement toward the shared line was blocked");
  Check(!CombatFallbackMath.Protected(float.NaN),"Unknown endpoint exposure held a formation post");
  Check(!CombatFallbackMath.Protected(float.PositiveInfinity),"Unavailable endpoint exposure became protected");
  Check(Math.Abs(CombatFallbackMath.FutureShotHorizon(233,0,66,28,15)-372)<.01f,"Loaded path/aim/burst/flight horizon changed");
  Check(float.IsPositiveInfinity(CombatFallbackMath.FutureShotHorizon(480,180,66,28,15)),"A projection beyond the finite observed horizon was truncated into certainty");
  Check(float.IsPositiveInfinity(CombatFallbackMath.FutureShotHorizon(float.NaN,0,66,28,15)),"Unknown path became an arrival shot");
  Check(float.IsPositiveInfinity(CombatFallbackMath.FutureShotHorizon(233,-1,66,28,15)),"Unknown native lock became zero delay");
  Check(float.IsPositiveInfinity(CombatFallbackMath.FutureShotHorizon(233,0,66,28,float.PositiveInfinity)),"Unknown projectile speed became instant impact");
  Check(CombatFallbackMath.FutureClinicalOrigin(true,true,false),"Checked physician destination not used for its own access proof");
  Check(!CombatFallbackMath.FutureClinicalOrigin(false,true,false),"A member's route substituted stale physician destination for actual position");
  Check(!CombatFallbackMath.FutureClinicalOrigin(true,false,false),"Unchecked physician arrival became a clinical origin");
  Check(CombatFallbackMath.MoveSlot(0,3,false),"Initial checked handoff lost");
  Check(!CombatFallbackMath.MoveSlot(1,2,false),"Ranged regression: two members displaced at once");
  Check(CombatFallbackMath.MoveSlot(1,2,true),"Two real stationary guns cannot support a second staggered melee exit");
  Check(!CombatFallbackMath.MoveSlot(1,1,true),"Last useful gun was spent on a second exit");
  Check(!CombatFallbackMath.MoveSlot(2,2,true),"Third concurrent mover was admitted");
  Check(CombatFallbackMath.PendingCover(true,true,true,60,180),"Finite safe autonomous covering intent was discarded");
  Check(!CombatFallbackMath.PendingCover(false,true,true,60,180),"Foreign or clinical job became covering intent");
  Check(!CombatFallbackMath.PendingCover(true,false,true,60,180),"Unsafe covering gun was held in place");
  Check(!CombatFallbackMath.PendingCover(true,true,false,60,180),"Missing threat held a covering gun");
  Check(!CombatFallbackMath.PendingCover(true,true,true,180,180),"Expired covering preparation retained a role");
  return n;
 }
}
'@
$taskCode=$taskCode.Replace('MATH',$taskSource.Substring($taskStart,$taskEnd-$taskStart))
Add-Type -TypeDefinition $taskCode -Language CSharp
[CohortRegression]::Run()

$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatRangedScreenHelper.cs')
$taskStart=$taskSource.IndexOf('    public static class CombatRangedScreenMath')
$taskEnd=$taskSource.IndexOf('    public static partial class CombatControlHelper')
$taskCode=@'
using System;
MATH
public static class RangedScreenRegression {
 static int n;
 static void Check(bool ok,string why){n++;if(!ok)throw new Exception(why);}
 public static int Run(){
  Check(CombatRangedScreenMath.AllowsMedicalRotation(false,false,0),"No mover needed fictitious support");
  Check(CombatRangedScreenMath.AllowsMedicalRotation(true,true,2),"Two actual covering guns could not cover a short turn during physician transit");
  Check(!CombatRangedScreenMath.AllowsMedicalRotation(true,true,1),"One covering gun was counted as two");
  Check(!CombatRangedScreenMath.AllowsMedicalRotation(true,true,0),"Planned or absent cover enabled simultaneous rotation");
  Check(!CombatRangedScreenMath.AllowsMedicalRotation(true,false,3),"A different moving healthy gun was treated as the physician");
  Check(CombatRangedScreenMath.BeforeNextBurst(0,26,75,0,true),"Checked two-cell shelter before measured warmup was rejected");
  Check(!CombatRangedScreenMath.BeforeNextBurst(108,26,75,0,true),"Native cooldown was assumed cancellable");
  Check(!CombatRangedScreenMath.BeforeNextBurst(0,60,75,0,true),"Equality removed the ordinary transition reserve");
  Check(!CombatRangedScreenMath.BeforeNextBurst(54,300,125,0,true),"Late long Q2 withdrawal was promoted as timely short shelter");
  Check(!CombatRangedScreenMath.BeforeNextBurst(0,26,0,0,true),"An already firing burst was treated as a future deadline");
  Check(!CombatRangedScreenMath.BeforeNextBurst(0,26,75,.2f,true),"Exposed endpoint was treated as shelter");
  Check(!CombatRangedScreenMath.BeforeNextBurst(0,26,75,0,false),"Riskier path was authorized by endpoint alone");
  Check(!CombatRangedScreenMath.BeforeNextBurst(0,0,75,0,true),"Standing still was called an executed escape");
  Check(CombatRangedScreenMath.BreakFocusedLane(2.2f,.6f,0),"L failed retreat: breaking the aimed gun and reducing crossfire required impossible zero exposure to all enemies");
  Check(!CombatRangedScreenMath.BreakFocusedLane(2.2f,2.1f,0),"Trivial exposure change became shelter");
  Check(!CombatRangedScreenMath.BreakFocusedLane(2.2f,2.5f,0),"Breaking one gun hid worse crossfire");
  Check(!CombatRangedScreenMath.BreakFocusedLane(2.2f,.5f,.6f),"Still aimed-at endpoint became lane interruption");
  Check(!CombatRangedScreenMath.BreakFocusedLane(float.NaN,.5f,0),"Unknown baseline became safe");
  foreach(float unknown in new[]{float.NaN,float.PositiveInfinity,-1f}){
   Check(!CombatRangedScreenMath.BeforeNextBurst(unknown,26,75,0,true),"Unknown own movement lock became safe");
   Check(!CombatRangedScreenMath.BeforeNextBurst(0,unknown,75,0,true),"Unknown native path cost became safe");
   Check(!CombatRangedScreenMath.BeforeNextBurst(0,26,unknown,0,true),"Unknown enemy burst deadline became safe");
   Check(!CombatRangedScreenMath.BeforeNextBurst(0,26,75,unknown,true),"Unknown endpoint protection became safe");
  }
  return n;
 }
}
'@
$taskCode=$taskCode.Replace('MATH',$taskSource.Substring($taskStart,$taskEnd-$taskStart))
Add-Type -TypeDefinition $taskCode -Language CSharp
[RangedScreenRegression]::Run()
$taskController=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatControlHelper.cs')
$taskTick=$taskController.Substring($taskController.IndexOf('private static void TickBudgeted()'))
if($taskTick.IndexOf('ReviewShortRangedScreen();') -lt 0 -or $taskTick.IndexOf('ReviewShortRangedScreen();') -gt $taskTick.IndexOf('ReviewFireDoctorGuard();')){throw 'Short shelter review is disconnected or starved by long fallback'}
if($taskSource -notmatch 'ReviewEscapeCells\(p,candidate.Enemy,"short_ranged_screen",cells,2\)'){throw 'Short shelter candidate cursor cannot finish its finite page'}

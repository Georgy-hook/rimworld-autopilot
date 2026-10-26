$ErrorActionPreference='Stop'
$taskBase=Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatDoctorReserveHelper.cs')
$taskMath=$taskSource.Substring($taskSource.IndexOf('    public static class CombatDoctorReserveMath'),$taskSource.IndexOf('    public static partial class CombatControlHelper')-$taskSource.IndexOf('    public static class CombatDoctorReserveMath'))
$taskStart=$taskSource.IndexOf('        private static bool DoctorReserveGun(')
$taskEnd=$taskSource.IndexOf(';', $taskStart)
$taskMethod=$taskSource.Substring($taskStart,$taskEnd-$taskStart+1)
$taskCode=@'
using System;
MATH
public sealed class Def {public bool IsRangedWeapon=true;}
public sealed class Weapon {public Def def=new Def();}
public sealed class Equipment {public Weapon Primary=new Weapon();}
public sealed class Pawn {public Equipment equipment=new Equipment();public bool Critical,Medical,QueuedCare,Protected,Stationary=true,EnemyInRange;}
public sealed class Plan {public Pawn Pawn;}
public static class CareTriageHelper {public static bool QueuedCare(Pawn p)=>p.QueuedCare;}
public static class CombatNativeHelper {public static bool Protected(Pawn p)=>p.Protected;}
public static class ActualEarlyAdmissionRegression {
 static int n;static void Check(bool ok,string message){n++;if(!ok)throw new Exception(message);}
 static bool OwnStationaryGun(Plan p)=>p.Pawn.Stationary;
 static bool DoctorReserveStationary(Plan p)=>OwnStationaryGun(p);
 static bool CriticalRangedInjury(Pawn p)=>p.Critical;
 static bool MedicalFunctionWarning(Pawn p)=>p.Medical;
METHOD
 public static int Run(){
  var doctor=new Pawn();var gun=new Pawn{EnemyInRange=false};var g=new Plan{Pawn=gun};
  Check(DoctorReserveGun(g,doctor),"At tick15 a healthy stationary gun outside current firing range prevented a checked unexposed medical exit");
  gun.EnemyInRange=true;Check(DoctorReserveGun(g,doctor),"A potential firing lane changed armed stationary capability");
  gun.Stationary=false;Check(!DoctorReserveGun(g,doctor),"A moving ally was counted as retaining firepower");gun.Stationary=true;
  gun.Critical=true;Check(!DoctorReserveGun(g,doctor),"A critically injured ally was counted ready");gun.Critical=false;
  gun.Medical=true;Check(!DoctorReserveGun(g,doctor),"An impaired ally was counted ready");gun.Medical=false;
  gun.QueuedCare=true;Check(!DoctorReserveGun(g,doctor),"Queued care was counted as available gun");gun.QueuedCare=false;
  gun.Protected=true;Check(!DoctorReserveGun(g,doctor),"Protected medical/manual work was counted as cover");gun.Protected=false;
  gun.equipment.Primary.def.IsRangedWeapon=false;Check(!DoctorReserveGun(g,doctor),"Unarmed or melee work was counted as a gun");
  Check(!DoctorReserveGun(new Plan{Pawn=doctor},doctor),"Physician counted itself as retained firepower");
  Check(CombatDoctorReserveMath.UnexposedRoute(0,0),"Actually unexposed sampled transit was rejected without already shooting allies");
  Check(!CombatDoctorReserveMath.UnexposedRoute(2,0),"Safe endpoint excused a firing lane during transit");
  Check(!CombatDoctorReserveMath.UnexposedRoute(0,2),"Safe prefix excused a future exposed endpoint");
  Check(!CombatDoctorReserveMath.UnexposedRoute(.2f,0),"Movement lock exposure passed an optional medical exit");
  foreach(float unknown in new[]{float.NaN,float.PositiveInfinity,-1f}){
   Check(!CombatDoctorReserveMath.UnexposedRoute(unknown,0),"Unknown prefix was treated as safe");
   Check(!CombatDoctorReserveMath.UnexposedRoute(0,unknown),"Unknown terminal was treated as safe");
  }
  return n;
 }
}
'@
$taskCode=$taskCode.Replace('MATH',$taskMath).Replace('METHOD',$taskMethod)
Add-Type -TypeDefinition $taskCode -Language CSharp
[ActualEarlyAdmissionRegression]::Run()
$taskControl=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatControlHelper.cs')
if($taskMethod -match 'CanShootNow'){throw 'Medical early capability still requires enemies inside current firing range'}
if($taskSource -notmatch 'SaferRangedRoute\(p,route,false,out _,null,600f,true\)'){throw 'Uncovered early exit bypasses the full timed-route gate'}
if($taskControl -notmatch 'if\(requireUnexposed\)improves &= CombatDoctorReserveMath.UnexposedRoute\(peak,terminal\)'){throw 'Unexposed route rule is not connected'}
if($taskControl -notmatch 'float ticks=pawn.stances.curStance is Stance_Warmup\?0f:CombatInterceptHelper.MovementLockTicks\(pawn\)'){throw 'Native movement lock omitted from timed prefix'}

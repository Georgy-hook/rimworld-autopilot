$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskSource=Get-Content -Raw -LiteralPath (Join-Path $taskRoot 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatDoctorTransitHelper.cs')
$taskStart=$taskSource.IndexOf('    public static class CombatDoctorTransitMath')
$taskEnd=$taskSource.IndexOf('    public static partial class CombatControlHelper')
$taskCode=@'
using System;
MATH
public static class DoctorTransitRegression {
 static int n;
 static void Check(bool ok,string why){n++;if(!ok)throw new Exception(why);}
 public static int Run(){
  Check(!CombatDoctorTransitMath.Prefix(3,2,581.658752f,787.742737f,393.871368f),"S physician fatal prefix was licensed by lower integrated exposure and protected destination");
  Check(CombatDoctorTransitMath.Prefix(1,2,60,100,60),"A short genuinely lower-exposure step was blocked");
  Check(!CombatDoctorTransitMath.Prefix(1,2,180,100,60),"Early worse exposure was hidden by a safer late cell");
  Check(CombatDoctorTransitMath.StagedEndpoint(2,1,2),"Useful intermediate cover required impossible zero exposure to every gun");
  Check(!CombatDoctorTransitMath.StagedEndpoint(2,2.5f,2),"Worse crossfire became a short shelter");
  Check(!CombatDoctorTransitMath.StagedEndpoint(2,1,14),"Long exposed march became a staged step");
  Check(!CombatDoctorTransitMath.StagedEndpoint(2,1,0),"Standing still became an escape");
  Check(CombatDoctorTransitMath.TimelyReduction(2,75,49),"Cooldown plus checked short reduction was rejected");
  Check(!CombatDoctorTransitMath.TimelyReduction(2,300,49),"Physician was sent through another full firing cycle before exposure improved");
  Check(!CombatDoctorTransitMath.TimelyReduction(2,float.PositiveInfinity,49),"Unknown first improvement became timely");
  Check(CombatDoctorTransitMath.TimelyReduction(0,float.PositiveInfinity,0),"Already sheltered remaining route was forced to improve below zero");
  Check(CombatDoctorTransitMath.Accept(true,false,true),"A prefix-dominant checked refuge was rejected solely because no very near shelter exists");
  Check(!CombatDoctorTransitMath.Accept(false,true,true),"S higher crossfire prefix was allowed by a quick reduction and protected end");
  Check(!CombatDoctorTransitMath.Accept(true,false,false),"An unprotected long nonimproving move was authorized");
  foreach(float x in new[]{float.NaN,float.PositiveInfinity,-1f}){
   Check(!CombatDoctorTransitMath.Prefix(x,2,60,100,60),"Unknown route exposure became safe");
   Check(!CombatDoctorTransitMath.Prefix(1,x,60,100,60),"Unknown holding exposure became safe");
   Check(!CombatDoctorTransitMath.StagedEndpoint(2,x,2),"Unknown endpoint became shelter");
   Check(!CombatDoctorTransitMath.TimelyReduction(2,75,x),"Unknown movement lock became safe");
  }
  return n;
 }
}
'@
$taskCode=$taskCode.Replace('MATH',$taskSource.Substring($taskStart,$taskEnd-$taskStart))
Add-Type -TypeDefinition $taskCode -Language CSharp
[DoctorTransitRegression]::Run()
$taskControl=Get-Content -Raw -LiteralPath (Join-Path $taskRoot 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatControlHelper.cs')
if($taskControl -notmatch 'if\(clinicalTransit\)improves &= CombatDoctorTransitMath.Accept\(prefixSafe,timelyReduction,protectedArrival\)'){throw 'Protected-arrival OR bypasses physician prefix gate'}
if($taskSource -notmatch 'CohortGunFreeFor\(gun,doctor,e\)' -or $taskSource -notmatch 'TeamCoverReady\(gun,enemy,threats\)'){throw 'Cover ignores the actual projectile or an existing mover lease'}
if($taskSource -match 'verb\.Reset|Rand\.|EndCurrentJob|StopAll|JobMaker|ReleaseToPool'){throw 'Doctor route math changes native cooldown, randomness, jobs or path ownership'}

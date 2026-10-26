$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatFallbackCohortHelper.cs')
$taskStart=$taskSource.IndexOf('    public static class CombatFallbackMath')
$taskEnd=$taskSource.IndexOf('    public static partial class CombatControlHelper')
$taskCode=@'
using System;
MATH
public static class CohortArbitrationRegression {
 static int n;static void Check(bool ok,string why){n++;if(!ok)throw new Exception(why);}
 public static int Run(){
  Check(CombatFallbackMath.OptionalOwner(true,true,true,true,false),"I: active melee cohort failed to exclude the CoverTurn replacing an arrival shot");
  Check(!CombatFallbackMath.OptionalOwner(false,true,true,true,false),"Expired cohort blocked independent cover");
  Check(!CombatFallbackMath.OptionalOwner(true,false,true,true,false),"Incapacitated physician retained a shared owner");
  Check(!CombatFallbackMath.OptionalOwner(true,true,false,true,false),"Clinical/manual physician job was commandeered");
  Check(!CombatFallbackMath.OptionalOwner(true,true,true,false,false),"Ranged control ordering changed");
  Check(!CombatFallbackMath.OptionalOwner(true,true,true,true,true),"Kidnap interception blocked by an old formation");
  Check(CombatFallbackMath.GroupFirst(true,240),"Healthy precontact group lost its finite review opportunity");
  Check(!CombatFallbackMath.GroupFirst(false,240),"Urgent clinic/contact guard was deprioritized");
  Check(!CombatFallbackMath.GroupFirst(true,120),"Near contact delayed mandatory guard");
  Check(!CombatFallbackMath.GroupFirst(true,float.NaN),"Unknown contact treated as a safe group window");
  Check(CombatFallbackMath.BoundDistance(180,4.5f)==4,"A short step was replaced by the old six-cell rally");
  Check(CombatFallbackMath.BoundDistance(90,4.5f)==2.25f,"Loaded short weapon cycle was ignored");
  Check(CombatFallbackMath.BoundDistance(float.NaN,4.5f)==0,"Unknown weapon cycle invented a valid group bound");
  Check(CombatFallbackMath.WaitForMovingPeers(true,true,true,400,180),"M: another healthy gun abandoned fire while peers were still moving");
  Check(!CombatFallbackMath.WaitForMovingPeers(true,true,true,270,180),"Waiting consumed the finite contact reserve");
  Check(!CombatFallbackMath.WaitForMovingPeers(false,true,true,400,180),"Critical wounded physician was forced to wait");
  Check(!CombatFallbackMath.WaitForMovingPeers(true,false,true,400,180),"Completed bound trapped the next mover");
  Check(!CombatFallbackMath.WaitForMovingPeers(true,true,false,400,180),"A blocked idle gun was counted as useful cover");
  return n;
 }
}
'@
$taskCode=$taskCode.Replace('MATH',$taskSource.Substring($taskStart,$taskEnd-$taskStart))
Add-Type -TypeDefinition $taskCode -Language CSharp
[CohortArbitrationRegression]::Run()

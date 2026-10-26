$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatPendingMoveHelper.cs')
$taskStart=$taskSource.IndexOf('    public static class CombatPendingMoveMath')
$taskEnd=$taskSource.IndexOf('    public static partial class CombatControlHelper')
$taskCode=@'
using System;
MATH
public static class PendingMoveRegression {
 static int n;static void Check(bool ok,string why){n++;if(!ok)throw new Exception(why);}
 public static int Run(){
  Check(!CombatPendingMoveMath.Started(false,true),"A found path left from the previous native job became proof that a newly accepted withdrawal had started");
  Check(CombatPendingMoveMath.Started(true,true),"Actual moving native path was not sent to the fresh route-safety review");
  Check(!CombatPendingMoveMath.Started(true,false),"Missing native path was called an observed route");
  Check(CombatPendingMoveMath.Pending(true,false,false,15,55,13),"R2 accepted job80 was cancelled before native cooldown ended");
  Check(CombatPendingMoveMath.Pending(true,false,false,100,55,13),"Finite ordinary native start transition was erased");
  Check(!CombatPendingMoveMath.Pending(true,false,false,146,55,13),"Unstarted move persisted beyond its finite captured lock+allowance");
  Check(!CombatPendingMoveMath.Pending(false,false,false,15,55,13),"Foreign replacement adopted as our move");
  Check(!CombatPendingMoveMath.Pending(true,true,false,15,55,13),"Later foreign/clinical queue ignored");
  Check(!CombatPendingMoveMath.Pending(true,false,true,15,55,13),"Started native route bypassed fresh safety review");
  Check(!CombatPendingMoveMath.Pending(true,false,false,-1,55,13),"Future accepted timestamp became current proof");
  Check(!CombatPendingMoveMath.Pending(true,false,false,15,-1,13),"Unknown initial lock became a pending lease");
  Check(!CombatPendingMoveMath.Pending(true,false,false,15,55,float.NaN),"Unknown native movement step became a pending lease");
  Check(!CombatPendingMoveMath.Pending(true,false,false,15,55,float.PositiveInfinity),"Infinite native movement step became a pending lease");
  return n;
 }
}
'@
$taskCode=$taskCode.Replace('MATH',$taskSource.Substring($taskStart,$taskEnd-$taskStart))
Add-Type -TypeDefinition $taskCode -Language CSharp
[PendingMoveRegression]::Run()
if($taskSource -notmatch 'Started\(p.pather.Moving,p.pather.curPath\?\.Found==true\)'){throw 'Native path Found is still used without actual movement'}
$taskControl=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatControlHelper.cs')
if($taskControl -notmatch 'selectedPlan.RangedWithdrawal=new CombatJobStamp\(move\);'){throw 'Accepted ordinary retreat does not bind the receipt used by pending native-start review'}

$ErrorActionPreference='Stop'
$taskBase=Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatCoverCommitmentHelper.cs')
$taskStart=$taskSource.IndexOf('    public static class CombatCoverCommitmentMath')
$taskMath=$taskSource.Substring($taskStart,$taskSource.IndexOf('    public static partial class CombatControlHelper')-$taskStart)
$taskCode=@'
using System;
MATH
public static class InflightCoverRegression {
 static int n;static void Check(bool b,string s){n++;if(!b)throw new Exception(s);}
 public static int Run(){
  Check(CombatCoverCommitmentMath.Keep(180,750,true,true,false,false,true,false,350,100),"Tick180 cooldown released the gun while the exact tick150 withdrawal was still underway");
  Check(!CombatCoverCommitmentMath.Keep(278,750,true,true,true,false,true,false,250,0),"Native arrival did not release the move's finite cover commitment");
  Check(!CombatCoverCommitmentMath.Keep(751,750,true,true,false,false,true,false,350,0),"Cover commitment failed to expire");
  Check(!CombatCoverCommitmentMath.Keep(180,750,false,true,false,false,true,false,350,0),"Downed/absent mover retained cover");
  Check(!CombatCoverCommitmentMath.Keep(180,750,true,false,false,false,true,false,350,0),"A later unrelated native/manual move inherited cover");
  Check(!CombatCoverCommitmentMath.Keep(180,750,true,true,false,true,true,false,350,0),"A foreign/clinical queue was commandeered");
  Check(!CombatCoverCommitmentMath.Keep(180,750,true,true,false,false,false,false,350,0),"Impaired cover gun was forced to remain");
  Check(!CombatCoverCommitmentMath.Keep(180,750,true,true,false,false,true,true,350,0),"Immediate contact/fire/gas did not release the gun");
  Check(!CombatCoverCommitmentMath.Keep(180,750,true,true,false,false,true,false,190,100),"The gun's finite escape deadline was ignored");
  foreach(float x in new[]{float.NaN,float.PositiveInfinity,-1f}){
   Check(!CombatCoverCommitmentMath.Keep(180,750,true,true,false,false,true,false,x,0),"Unknown contact retained a covering gun");
   Check(!CombatCoverCommitmentMath.Keep(180,750,true,true,false,false,true,false,350,x),"Unknown lock retained a covering gun");
  }
  return n;
 }
}
'@
Add-Type -TypeDefinition ($taskCode.Replace('MATH',$taskMath)) -Language CSharp
[InflightCoverRegression]::Run()
if($taskSource -match 'FindPathNow|CombatPathBudgetHelper.Query|JobMaker|Rand\.') {throw 'Cover bookkeeping started a route, shot or random operation'}
$taskTeam=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatTeamCareHelper.cs')
if($taskTeam -notmatch 'HasClinicalCareJob\(cover.Mover\)' -or $taskTeam -notmatch 'TeamCoverReady\(pawn,cover.Enemy,threats\)'){throw 'Existing clinical cover proof was removed'}

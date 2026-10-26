$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatRangePostHelper.cs')
$taskStart=$taskSource.IndexOf('    public static class CombatRangePostMath')
$taskEnd=$taskSource.IndexOf('    public static partial class CombatControlHelper')
$taskCode=@'
using System;
MATH
public static class RangePostRegression {
 static int n;static void Check(bool ok,string why){n++;if(!ok)throw new Exception(why);}
 public static int Run(){
  Check(!CombatRangePostMath.RemainingSupport(1,2),"A long optional range move left one real gun against an observed flank while short guns were still out of range");
  Check(CombatRangePostMath.RemainingSupport(2,2),"Two actual remaining guns could not license the unchanged checked route");
  Check(CombatRangePostMath.RemainingSupport(0,0),"A genuinely quiet observed horizon blocked all optional repositioning");
  Check(!CombatRangePostMath.RemainingSupport(2,float.PositiveInfinity),"Unknown group exposure licensed an optional long move");
  Check(CombatRangePostMath.Band(31.9f,22.9f,26),"Loaded rifle range advantage was lost");
  Check(!CombatRangePostMath.Band(22.9f,22.9f,26),"Equal-range gun was sent to a nonexistent firing band");
  Check(!CombatRangePostMath.Band(31.9f,22.9f,23),"Enemy firing range was called protected range");
  Check(!CombatRangePostMath.Band(31.9f,22.9f,31.5f),"Outside own retained firing range became a firing post");
  Check(!CombatRangePostMath.Advantage(26,23),"Insufficient range reserve licensed a distant move");
  foreach(float unknown in new[]{float.NaN,float.PositiveInfinity,-1f,0f}){
   Check(!CombatRangePostMath.Band(unknown,22.9f,26),"Unknown own range authorized a firing post");
   Check(!CombatRangePostMath.Band(31.9f,unknown,26),"Unknown hostile range authorized a firing post");
  }
  Check(!CombatRangePostMath.RecentShot(-1,30,180),"No-shot sentinel was counted as early covering fire");
  Check(!CombatRangePostMath.RecentShot(200,100,180),"Future shot timestamp became current cover");
  Check(CombatRangePostMath.RecentShot(10,20,180),"Actual recent shot was lost");
  Check(!CombatRangePostMath.RecentShot(10,400,180),"Expired historical shot was counted as current cover");
  Check(CombatRangePostMath.ContinuingNotWorse(0,0,0,0,0,0,36.77f),"R3 equally protected final two cells were cancelled as unsafe");
  Check(!CombatRangePostMath.ContinuingNotWorse(5,0,.5f,0,0,0,36.77f),"Worse remaining crossing became a retained safe route");
  Check(!CombatRangePostMath.ContinuingNotWorse(0,0,0,0,.2f,0,36.77f),"Newly exposed endpoint was retained");
  Check(!CombatRangePostMath.ContinuingNotWorse(float.NaN,0,0,0,0,0,36.77f),"Unknown remaining exposure became safe continuation");
  Check(!CombatRangePostMath.ContinuingNotWorse(0,0,0,0,0,0,0),"Zero-duration absence became a real route");
  return n;
 }
}
'@
$taskCode=$taskCode.Replace('MATH',$taskSource.Substring($taskStart,$taskEnd-$taskStart))
Add-Type -TypeDefinition $taskCode -Language CSharp
[RangePostRegression]::Run()
$taskController=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatControlHelper.cs')
if($taskController -match 'if\(FallbackCohorts.Count==0\)ReviewObservedRangePosts'){throw 'An inert rally vetoes every ranged actor on every map'}
if($taskController -notmatch 'ReviewObservedRangePosts\(\);'){throw 'Ranged review is disconnected'}
if($taskController -notmatch 'if\(FallbackCohorts.Count==0 \|\| Plans.Values.Where\(Valid\)'){throw 'An irrelevant ranged phase changed active melee arbitration'}
if($taskSource -notmatch '"observed_range_post",cells,2\)'){throw 'Rejected range candidates cannot finish and advance their finite page'}

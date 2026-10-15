$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatInterceptHelper.cs')
$taskStart=$taskSource.IndexOf('public static class CombatInterceptMath')
$taskEnd=$taskSource.IndexOf('    /// <summary>', $taskStart)
$taskMath=$taskSource.Substring($taskStart,$taskEnd-$taskStart)
$taskCode=@'
using System;
MATH
public static class InterceptRegression {
static int n;static void Check(bool ok,string why){n++;if(!ok)throw new Exception(why);}
public static int Run(){
float time=CombatInterceptMath.ShotHorizon(180,120,30);
Check(time==447,"Travel, aim, projectile and safety buffer not all included");
Check(CombatInterceptMath.ShotHorizon(0,0,0)==90,"No response buffer");
Check(CombatInterceptMath.ShotHorizon(-2,-2,-2)==90,"Negative time fabricated an early shot");
Check(!CombatInterceptMath.FiringWindow(25,0,24),"Edge of range treated as safe firing window");
Check(CombatInterceptMath.FiringWindow(25,0,18),"Interior firing envelope rejected");
Check(!CombatInterceptMath.FiringWindow(25,0,28),"Fleeing target outside future range still shootable");
Check(!CombatInterceptMath.FiringWindow(25,8,8),"Minimum weapon range ignored");
Check(CombatInterceptMath.ContactDefence(true,1.4f),"Ranged carrier could not use adjacent melee self defence");
Check(!CombatInterceptMath.ContactDefence(false,1),"Pacifist received violent self defence");
Check(!CombatInterceptMath.ContactDefence(true,3),"Contact guard authorized distant charge");
Check(!CombatInterceptMath.SupportedLure(false,1,true),"Unfollowed lure accepted");
Check(!CombatInterceptMath.SupportedLure(true,0,true),"Other-target or unready gun treated as cover");
Check(!CombatInterceptMath.SupportedLure(true,1,false),"Unsafe bait route accepted");
Check(CombatInterceptMath.SupportedLure(true,1,true),"Followed covered escape rejected");
Check(CombatInterceptMath.StraightTravelTicks(3,4,12,17)==63,"Diagonal loaded movement timing ignored");
Check(CombatInterceptMath.StraightTravelTicks(-3,-4,12,17)==63,"Direction changed loaded movement timing");
Check(CombatInterceptMath.ImmediateWindow(true,false,false),"Short path cancelled an available shot");
Check(!CombatInterceptMath.ImmediateWindow(false,false,true),"Forecast fabricated a present shot");
Check(!CombatInterceptMath.ImmediateWindow(true,true,false),"Observed escape ignored");
Check(CombatInterceptMath.ImmediateWindow(true,true,true),"Valid immediate shot rejected");
Check(!CombatInterceptMath.DefensiveAdvance(35,60,25,false),"Hold cover became a long advance");
Check(!CombatInterceptMath.DefensiveAdvance(7,20,13,false),"Uncovered approach treated as defence");
Check(CombatInterceptMath.DefensiveAdvance(7,20,13,true),"Short covered reposition rejected");
Check(!CombatInterceptMath.DefensiveAdvance(3,7,4,true),"Cover justified moving into contact");
Check(CombatInterceptMath.ShotCommitment(60,20,100,90,0)==270,"Burst/cooldown lock omitted from escape horizon");
Check(CombatInterceptMath.ShotCommitment(0,0,0,30,80)==110,"Existing immobile stance treated as immediate escape");
Check(CombatInterceptMath.InterveningAlly(0,0,20,0,10,0,1.5f),"Ally directly between shooter and target ignored");
Check(!CombatInterceptMath.InterveningAlly(0,0,20,0,10,2,1.5f),"Safe side lane rejected");
Check(!CombatInterceptMath.InterveningAlly(0,0,20,0,-2,0,1.5f),"Ally behind shooter blocks firing");
Check(CombatInterceptMath.InterveningAlly(0,0,20,0,21,0,1.5f),"Ally near the target's miss envelope ignored");
Check(!CombatInterceptMath.InterveningAlly(0,0,20,0,23,0,1.5f),"Far beyond target treated as an intervening ally");
Check(CombatInterceptMath.InterveningAlly(0,0,20,20,10,10,1.5f),"Diagonal friendly lane ignored");
return n;}}
'@
Add-Type -TypeDefinition ($taskCode.Replace('MATH',$taskMath)) -Language CSharp
[InterceptRegression]::Run()

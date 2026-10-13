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
return n;}}
'@
Add-Type -TypeDefinition ($taskCode.Replace('MATH',$taskMath)) -Language CSharp
[InterceptRegression]::Run()

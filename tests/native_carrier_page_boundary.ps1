$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatCarrierInterceptHelper.cs')
$taskStart=$taskSource.IndexOf('    public static class CombatCarrierSearchMath')
$taskEnd=$taskSource.IndexOf('    public static class CombatCarrierInterceptHelper')
$taskCode=@'
using System;
MATH
public static class CarrierPageRegression {
static int n;static void Check(bool x,string why){n++;if(!x)throw new Exception(why);}
public static int Run(){
Check(CombatCarrierSearchMath.PageEnd(0,48)==4,"One pulse consumed the whole48candidate search");
Check(CombatCarrierSearchMath.PageEnd(46,48)==48,"Finite final page overran its pool");
int cursor=0,pages=0;while(cursor<48){cursor=CombatCarrierSearchMath.PageEnd(cursor,48);pages++;}
Check(cursor==48 && pages==12,"Completed pages lost progress or skipped candidates");
Check(CombatCarrierSearchMath.Reuse(true,true,true,60,4),"A moving target reset a still scoped finite search");
Check(!CombatCarrierSearchMath.Reuse(false,true,true,60,4),"A different carrier inherited the old page");
Check(!CombatCarrierSearchMath.Reuse(true,false,true,60,4),"A changed native target job inherited the old page");
Check(!CombatCarrierSearchMath.Reuse(true,true,false,60,4),"A different map inherited the old page");
Check(!CombatCarrierSearchMath.Reuse(true,true,true,-1,4),"A rewound clock inherited future candidates");
Check(!CombatCarrierSearchMath.Reuse(true,true,true,601,4),"An expired candidate page never rebuilt");
Check(!CombatCarrierSearchMath.Reuse(true,true,true,60,0),"An exhausted page never rebuilt");
return n;}}
'@
$taskCode=$taskCode.Replace('MATH',$taskSource.Substring($taskStart,$taskEnd-$taskStart));Add-Type -TypeDefinition $taskCode -Language CSharp
[CarrierPageRegression]::Run()

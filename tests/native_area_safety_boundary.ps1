$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/FalloutShelterHelper.cs')
$taskMethods=([regex]::Matches($taskSource,'public static bool (ColdRestrictionNeeded|HeatRestrictionNeeded|ExposureRouteAllowed)[^;]+;') | ForEach-Object {$_.Value}) -join "`n"
if (-not $taskMethods) {throw 'Native area boundary absent'}
$taskCode=@'
using System;
public static class NativeAreaSafetyBoundary {
METHODS
static int n; static void Check(bool ok,string why){n++;if(!ok)throw new Exception(why);}
public static int Run(){
Check(ColdRestrictionNeeded(.04f,21f,10f),"Cold injury ignored in warm room before recovery");
Check(!ColdRestrictionNeeded(.02f,21f,10f),"Recovered person kept confined");
Check(ColdRestrictionNeeded(0f,-5f,10f),"Dangerous ambient cold ignored");
Check(!ColdRestrictionNeeded(0f,4f,-40f),"Species comfort ignored");
Check(HeatRestrictionNeeded(.04f,21f,30f),"Heat injury ignored");
Check(!HeatRestrictionNeeded(.02f,21f,30f),"Recovered heat patient stuck");
Check(HeatRestrictionNeeded(0f,45f,30f),"Dangerous heat ignored");
Check(!HeatRestrictionNeeded(0f,45f,55f),"Hot-tolerant species wrongly confined");
Check(ExposureRouteAllowed(0,.9f,false),"Safe covered route blocked");
Check(!ExposureRouteAllowed(1,0f,false),"Ordinary fallout errand escaped shelter");
Check(ExposureRouteAllowed(40,.1f,true),"Bounded shelter transition blocked");
Check(!ExposureRouteAllowed(41,.1f,true),"Long exposed shelter route accepted");
Check(ExposureRouteAllowed(12,.6f,true),"Short serious-toxin escape blocked");
Check(!ExposureRouteAllowed(13,.6f,true),"Serious-toxin long escape accepted");
return n;}}
'@
Add-Type -TypeDefinition ($taskCode.Replace('METHODS',$taskMethods)) -Language CSharp
[NativeAreaSafetyBoundary]::Run()

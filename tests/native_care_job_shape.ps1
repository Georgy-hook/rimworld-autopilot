$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatNativeHelper.cs')
$taskStart=$taskSource.IndexOf('private static readonly HashSet<string> Care=')
$taskEnd=$taskSource.IndexOf('private static readonly Dictionary', $taskStart)
$taskCare=$taskSource.Substring($taskStart,$taskEnd-$taskStart)
$taskStart=$taskSource.IndexOf('public static bool CareJobShape')
$taskEnd=$taskSource.IndexOf('public static bool HasCareJob', $taskStart)
$taskMethod=$taskSource.Substring($taskStart,$taskEnd-$taskStart)
$taskCode=@'
using System;using System.Collections.Generic;
public static class NativeCareShapeBoundary {
CARE
METHOD
static int n;
static void Check(bool p,string why){n++;if(!p)throw new Exception(why);}
public static int Run(){
Check(!CareJobShape("DoBill",false),"Production locked as patient care");
Check(CareJobShape("DoBill",true),"Operation unprotected");
Check(CareJobShape("TendPatient",true),"Tend unprotected");
Check(CareJobShape("Rescue",true),"Rescue unprotected");
Check(CareJobShape("FeedPatient",true),"Feeding unprotected");
Check(!CareJobShape("Research",false),"Research is not care");
Check(!CareJobShape(null,false),"Unknown missing job fabricated care");
Check(CareJobShape("BottleFeedBaby",true),"Baby care unprotected");
return n;}
}
'@
Add-Type -TypeDefinition ($taskCode.Replace('CARE',$taskCare).Replace('METHOD',$taskMethod)) -Language CSharp
[NativeCareShapeBoundary]::Run()

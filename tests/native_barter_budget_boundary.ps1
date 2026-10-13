$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/LiveTradeAutomationHelper.cs')
$taskMethod=[regex]::Match($taskSource,'public static float SaleCreditCeiling[^;]+;').Value
if (-not $taskMethod) {throw 'Native barter boundary absent'}
$taskCode=@'
using System;
public static class NativeBarterBudgetBoundary {
METHOD
static int n;static void Check(bool ok,string why){n++;if(!ok)throw new Exception(why);}
public static int Run(){
Check(SaleCreditCeiling(0,200,true)==200,"No-cash merchant could not barter");
Check(SaleCreditCeiling(0,200,false)==0,"Cash-only sale given phantom purchase credit");
Check(SaleCreditCeiling(100,200,true)==300,"Real cash plus barter credit missing");
Check(SaleCreditCeiling(100,200,false)==100,"Cash ceiling changed");
Check(SaleCreditCeiling(-100,200,true)==200,"Negative merchant balance used");
Check(SaleCreditCeiling(100,-200,true)==100,"Negative purchase budget used");
return n;}}
'@
Add-Type -TypeDefinition ($taskCode.Replace('METHOD',$taskMethod)) -Language CSharp
[NativeBarterBudgetBoundary]::Run()

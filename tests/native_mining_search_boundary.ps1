$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/MiningAutomationHelper.cs')
$taskStart=$taskSource.IndexOf('public static T ClosestFeasible')
$taskEnd=$taskSource.IndexOf('public static List<int> ConnectedBatch',$taskStart)
$taskMethod=$taskSource.Substring($taskStart,$taskEnd-$taskStart)
if(-not $taskMethod){throw 'Actual closest feasible boundary missing'}
$taskSafetySource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/OrdinaryWorkSafety.cs')
$taskTemperatureMethod=[regex]::Match($taskSafetySource,'public static bool WorkingTemperatureSafe[\s\S]*?;').Value
if(-not $taskTemperatureMethod){throw 'Actual working-temperature boundary missing'}
$taskCode=@'
using System;using System.Linq;using System.Collections.Generic;
public static class NativeMiningSearchBoundary {
METHOD
TEMPERATURE
public class Item {public int id;public float distance;public bool feasible;}
static int n;static void Check(bool ok,string why){n++;if(!ok)throw new Exception(why);}
public static int Run(){
var rows=Enumerable.Range(1,1000).Select(i=>new Item{id=i,distance=i,feasible=true}).Reverse().ToArray();
int calls=0;var chosen=ClosestFeasible(rows,r=>r.distance,r=>{calls++;return r.feasible;});
Check(chosen.id==1,"Nearest feasible result changed");Check(calls==1,"Paths scanned for every block before choosing");
rows.First(r=>r.id==1).feasible=false;calls=0;chosen=ClosestFeasible(rows,r=>r.distance,r=>{calls++;return r.feasible;});
Check(chosen.id==2,"Blocked nearest did not fall through");Check(calls==2,"Blocked nearest scanned all candidates");
var tie=new[]{new Item{id=8,distance=1,feasible=true},new Item{id=7,distance=1,feasible=true}};
Check(ClosestFeasible(tie,r=>r.distance,r=>r.feasible).id==8,"Stable native tie order changed");
Check(ClosestFeasible(rows,r=>r.distance,r=>false)==null,"Unavailable routes fabricated a candidate");
Check(!WorkingTemperatureSafe(-5.1f,6.76f,40f),"Unsafe cold origin offered ordinary work");
Check(WorkingTemperatureSafe(6.76f-10f,6.76f,40f),"Cold boundary changed");
Check(!WorkingTemperatureSafe(51f,-10f,40f),"Unsafe hot origin offered ordinary work");
Check(WorkingTemperatureSafe(20f,-10f,40f),"Comfortable work origin rejected");
return n;}}
'@
Add-Type -TypeDefinition ($taskCode.Replace('METHOD',$taskMethod).Replace('TEMPERATURE',$taskTemperatureMethod)) -Language CSharp
[NativeMiningSearchBoundary]::Run()

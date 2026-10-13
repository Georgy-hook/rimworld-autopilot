$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/MiningAutomationHelper.cs')
$taskMethod=[regex]::Match($taskSource,'public static T ClosestFeasible[^;]+;').Value
if(-not $taskMethod){throw 'Actual closest feasible boundary missing'}
$taskCode=@'
using System;using System.Linq;using System.Collections.Generic;
public static class NativeMiningSearchBoundary {
METHOD
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
return n;}}
'@
Add-Type -TypeDefinition ($taskCode.Replace('METHOD',$taskMethod)) -Language CSharp
[NativeMiningSearchBoundary]::Run()

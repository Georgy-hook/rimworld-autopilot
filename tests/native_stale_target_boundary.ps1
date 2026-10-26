$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatTacticReadinessHelper.cs')
$taskCode=@'
using System;
using System.Collections.Generic;
namespace RIMAPI.Models {
 public sealed class CombatTacticResponseDto {
  public string Tactic; public int? TargetPawnId;public bool Applied,Deferred,ReviewComplete;
  public List<string> Notes=new List<string>();
 }
}
SOURCE
public static class StaleTargetRegression {
 public static int Run(){
  int n=0;
  foreach(int? id in new int?[]{null,21851}){
   var r=RIMAPI.Helpers.CombatTacticReadinessHelper.NoActiveTarget("stationary_fire",id);
   if(r.Applied || r.Deferred || !r.ReviewComplete)throw new Exception("Stale observation was called executed or retryable");n++;
   if(r.TargetPawnId!=id || r.Tactic!="stationary_fire")throw new Exception("Silent target replacement");n++;
   if(r.Notes.Count!=1 || !r.Notes[0].StartsWith("target_unavailable_current_state:"))throw new Exception("Stale refusal reason missing");n++;
  }
  foreach(int? id in new int?[]{null,8797}){
   var r=RIMAPI.Helpers.CombatTacticReadinessHelper.NoSelectedFighters("contact_melee",id);
   if(r.Applied || r.Deferred || !r.ReviewComplete || r.TargetPawnId!=id)throw new Exception("Unavailable selected actor was executed/retried/replaced");n++;
   if(!r.Notes[0].StartsWith("selected_fighters_unavailable_current_state:"))throw new Exception("Unavailable actor refusal reason missing");n++;
  }
  foreach(int? id in new int?[]{null,8797}){
   var r=RIMAPI.Helpers.CombatTacticReadinessHelper.StandDownBlocked("stand_down",id);
   if(r.Applied || r.Deferred || !r.ReviewComplete || r.TargetPawnId!=id || r.Tactic!="stand_down")throw new Exception("Changed hostile state became accepted stand-down/retry/retarget");n++;
   if(!r.Notes[0].StartsWith("hostiles_remain_current_state:"))throw new Exception("Changed hostile state reason missing");n++;
  }
  return n;
 }
}
'@
# A using directive cannot follow the DTO namespace; retain the actual helper
# body with its models reference supplied at the beginning of this compilation.
$taskCode="using RIMAPI.Models;`n"+$taskCode.Replace('SOURCE',$taskSource.Replace('using RIMAPI.Models;',''))
Add-Type -TypeDefinition $taskCode -Language CSharp
[StaleTargetRegression]::Run()

$ErrorActionPreference='Stop'
$taskRepo=Split-Path -Parent $PSScriptRoot
$taskBoundary=Get-Content -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/QuestPublicReadBoundary.cs') -Raw
$taskSource=@'
using System;
using RIMAPI.Helpers;
public static class QuestHistoryHarness {
 static int calls;
 static bool BrokenPopulation() { calls++; throw new NullReferenceException("discarded pawn.RaceProps"); }
 public static void Run() {
  if (QuestPublicReadBoundary.Live(true, BrokenPopulation, false) || calls!=0)
   throw new Exception("Historical parts were evaluated");
  try { QuestPublicReadBoundary.Live(false, BrokenPopulation, false); throw new Exception("Live error hidden"); }
  catch(NullReferenceException) { if(calls!=1) throw new Exception("Live callback omitted"); }
  if(!QuestPublicReadBoundary.Live(false, ()=>true, false)) throw new Exception("Healthy live opportunity lost");
 }
}
'@
Add-Type -TypeDefinition ($taskSource + "`n" + $taskBoundary.Replace('using System;', ''))
[QuestHistoryHarness]::Run()
Write-Output 'PASS: historical callbacks skipped, active failures remain explicit, healthy active population retained (3 cases)'

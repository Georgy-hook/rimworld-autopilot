$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
$taskHelpers = Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers'
$taskObservation = Get-Content -LiteralPath (Join-Path $taskHelpers 'ObservationBoundary.cs') -Raw
$taskObservation = $taskObservation -replace '(?m)^using [^;]+;\r?\n', ''
$taskAnimal = Get-Content -LiteralPath (Join-Path $taskHelpers 'AnimalProvisioningHelper.cs') -Raw
$taskReserve = [regex]::Match($taskAnimal, 'public static bool FeedReserve\([^;]+;').Value
$taskFeedCount = [regex]::Match($taskAnimal, 'public static int FeedCount\([^;]+;').Value
$taskSurgery = [regex]::Match($taskAnimal, 'public static bool ElectiveSurgeryReady\([^;]+;').Value
$taskMining = Get-Content -LiteralPath (Join-Path $taskHelpers 'MiningAutomationHelper.cs') -Raw
$taskBatch = [regex]::Match($taskMining, 'public static List<int> ConnectedBatch\(.*?\r?\n  \}', [Text.RegularExpressions.RegexOptions]::Singleline).Value
if (-not $taskReserve -or -not $taskFeedCount -or -not $taskSurgery -or -not $taskBatch) { throw 'Production boundary method missing' }
$taskFixture = @'
using System;
using System.Collections.Generic;
using System.Linq;
using RIMAPI.Helpers;
public static class PostmortemBoundaryFixture {
 RESERVE
 FEEDCOUNT
 SURGERY
 BATCH
 public static int ObservationCases() {
  var errors=new Dictionary<string,string>(); var observed=new List<int>();
  bool failed=ObservationBoundary.Read<int>("historical:1",()=>{throw new NullReferenceException();},observed.Add,errors,
   error=>{throw new Exception("diagnostic failure");});
  if(failed || errors["historical:1"]!="NullReferenceException") throw new Exception("Failed record must remain explicit");
  if(!ObservationBoundary.Read<int>("offered:2",()=>42,observed.Add,errors) || observed.Single()!=42)
   throw new Exception("Healthy record lost after historical failure");
  if(ObservationBoundary.Read<int>("receiver:3",()=>4,value=>{throw new InvalidOperationException();},errors)
   || errors["receiver:3"]!="InvalidOperationException" || observed.Single()!=42)
   throw new Exception("Receive failure erased unrelated data");
  return 3;
 }
 public static int ConnectedCases() {
  var graph=new Dictionary<int,int[]> {{1,new[]{2}}, {2,new[]{1,3}}, {3,new[]{2}}, {90,new[]{91}}, {91,new[]{90}}};
  if(!ConnectedBatch(graph,1,2).SequenceEqual(new[]{1,2})) throw new Exception("Batch exceeded finite limit");
  if(!ConnectedBatch(graph,1,12).SequenceEqual(new[]{1,2,3})) throw new Exception("Unconnected vein mixed into batch");
  if(!ConnectedBatch(graph,90,12).SequenceEqual(new[]{90,91})) throw new Exception("New vein reused old subject");
  if(ConnectedBatch(graph,1,0).Count!=0) throw new Exception("Zero batch still designated a cell");
  return 4;
 }
}
'@
Add-Type -TypeDefinition ($taskFixture.Replace('RESERVE',$taskReserve).Replace('FEEDCOUNT',$taskFeedCount).Replace('SURGERY',$taskSurgery).Replace('BATCH',$taskBatch) + $taskObservation)
$taskCount = [PostmortemBoundaryFixture]::ObservationCases() + [PostmortemBoundaryFixture]::ConnectedCases()
$taskReserves = @(
 @([float]5,[float]1,$true,2,$true),
 @([float]4,[float]1,$true,2,$false),
 @([float]0,[float]1,$false,2,$true),
 @([float]1,[float]1,$true,1,$false),
 @([float]10,[float]2,$true,4,$true)
)
foreach ($taskCase in $taskReserves) {
 if ([PostmortemBoundaryFixture]::FeedReserve($taskCase[0],$taskCase[1],$taskCase[2],$taskCase[3]) -ne $taskCase[4]) {
  throw ('Human feed reserve failed: ' + ($taskCase -join ','))
 }
}
$taskSurgeries = @(
 @([float]0.8,$false,$false,8,[float]0.95,$true),
 @([float]0.8,$false,$false,3,[float]0.95,$false),
 @([float]0.4,$false,$false,12,[float]0.95,$false),
 @([float]0.8,$true,$false,12,[float]0.95,$false),
 @([float]0.8,$false,$true,12,[float]0.95,$false),
 @([float]0.8,$false,$false,12,[float]0.8,$false)
)
foreach ($taskCase in $taskSurgeries) {
 if ([PostmortemBoundaryFixture]::ElectiveSurgeryReady($taskCase[0],$taskCase[1],$taskCase[2],$taskCase[3],$taskCase[4]) -ne $taskCase[5]) {
  throw ('Elective surgery failed: ' + ($taskCase -join ','))
 }
}
$taskCount += $taskReserves.Count + $taskSurgeries.Count
$taskFeedCases = @(
 @([float]0.05,100,2,32),
 @([float]0.05,7,2,7),
 @([float]2.0,10,2,0),
 @([float]0.0,10,2,0),
 @([float]0.05,100,0,0)
)
foreach ($taskCase in $taskFeedCases) {
 if ([PostmortemBoundaryFixture]::FeedCount($taskCase[0],$taskCase[1],$taskCase[2]) -ne $taskCase[3]) {
  throw ('Finite feed count failed: ' + ($taskCase -join ','))
 }
}
$taskCount += $taskFeedCases.Count
Write-Output ('PASS: ' + $taskCount + ' production observation, connected-vein, feed-reserve and elective-surgery cases; no game started')

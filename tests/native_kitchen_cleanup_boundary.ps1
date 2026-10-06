$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
$taskSource = Get-Content -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/SustenanceHelper.cs') -Raw
# Execute the actual dependency-free predicate used by the native option filter.
$taskMatch = [regex]::Match($taskSource, 'public static bool KitchenCleanupInFootprint\([^\r\n]+;')
if (-not $taskMatch.Success) { throw 'Native kitchen footprint predicate missing' }
Add-Type -TypeDefinition ('public static class KitchenBoundaryFixture {' + $taskMatch.Value + '}')
$taskCases = @(
    @{Enclosed=$false; SameRoom=$true; Distance=10000; Expected=$false; Name='distant outdoor room 0 filth'},
    @{Enclosed=$false; SameRoom=$true; Distance=9; Expected=$true; Name='local outdoor boundary'},
    @{Enclosed=$false; SameRoom=$true; Distance=10; Expected=$false; Name='outside local boundary'},
    @{Enclosed=$false; SameRoom=$false; Distance=1; Expected=$false; Name='nearby different room'},
    @{Enclosed=$true; SameRoom=$false; Distance=10000; Expected=$true; Name='actual enclosed kitchen room'}
)
foreach ($taskCase in $taskCases) {
    $taskActual = [KitchenBoundaryFixture]::KitchenCleanupInFootprint($taskCase.Enclosed, $taskCase.SameRoom, $taskCase.Distance)
    if ($taskActual -ne $taskCase.Expected) { throw ('Failed: ' + $taskCase.Name) }
}
Write-Output ('PASS: ' + $taskCases.Count + ' actual native footprint boundary cases; ordinary work completion untested')

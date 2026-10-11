$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
$taskSource = Get-Content -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/WildlifeHuntHelper.cs') -Raw
$taskMethod = [regex]::Match($taskSource, 'public static bool RecoveryBlocksHunt\([^;]+;').Value
if (-not $taskMethod) { throw 'Production recovery predicate missing' }
Add-Type -TypeDefinition ('public static class HuntRecoveryBoundary { ' + $taskMethod + ' }')
$taskCases = @(
    @(1,0,.7,.7,.6,0,$true,$false,$false),
    @(1,0,.7,.7,.6,0,$false,$false,$true),
    @(1,.01,.7,.7,.6,0,$true,$false,$true),
    @(1,0,.7,.7,.6,0,$true,$true,$true),
    @(1,0,.49,.7,.6,0,$true,$false,$true),
    @(1,0,.7,.39,.6,0,$true,$false,$true),
    @(1,0,.7,.7,.1,0,$true,$false,$true),
    @(.4,0,.7,.7,.6,0,$true,$false,$true),
    @(1,0,1,1,.6,.8,$false,$false,$false)
)
foreach ($taskCase in $taskCases) {
    $taskActual = [HuntRecoveryBoundary]::RecoveryBlocksHunt($taskCase[0],$taskCase[1],$taskCase[2],$taskCase[3],$taskCase[4],$taskCase[5],$taskCase[6],$taskCase[7])
    if ($taskActual -ne $taskCase[8]) { throw ('Recovery boundary failed: ' + ($taskCase -join ',')) }
}
Write-Output ('PASS: ' + $taskCases.Count + ' actual native hunting recovery cases; no game orders')

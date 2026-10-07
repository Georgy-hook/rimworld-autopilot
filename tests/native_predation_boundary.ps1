$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
$taskSource = Get-Content -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatNativeHelper.cs') -Raw
$taskMatch = [regex]::Match($taskSource, 'public static bool PredationIntent\([^\r\n]+;')
if (-not $taskMatch.Success) { throw 'Actual native predation predicate missing' }
Add-Type -TypeDefinition ('public static class PredationBoundaryFixture {' + $taskMatch.Value + '}')
$taskCases = @(
    @($false,$false,'PredatorHunt',$true,$true),
    @($false,$false,'PredatorHunt',$false,$false),
    @($false,$false,'Wander',$true,$false),
    @($false,$false,$null,$true,$false),
    @($true,$false,'PredatorHunt',$true,$false),
    @($false,$true,'PredatorHunt',$true,$false)
)
foreach ($taskCase in $taskCases) {
    $taskActual = [PredationBoundaryFixture]::PredationIntent($taskCase[0],$taskCase[1],$taskCase[2],$taskCase[3])
    if ($taskActual -ne $taskCase[4]) { throw ('Predation boundary failed: ' + ($taskCase -join ',')) }
}
Write-Output ('PASS: ' + $taskCases.Count + ' actual native intent cases; live protection outcome unverified')

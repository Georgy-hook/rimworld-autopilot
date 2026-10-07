$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
$taskSource = Get-Content -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CareTriageHelper.cs') -Raw
$taskMatch = [regex]::Match($taskSource, 'public static bool ThermalTransferBeneficial\([^;]+;')
if (-not $taskMatch.Success) { throw 'Actual native thermal transfer predicate missing' }
Add-Type -TypeDefinition ('public static class ThermalTransferBoundaryFixture {' + $taskMatch.Value + '}')
$taskCases = @(
    @($true,$false,-25,22,16,26,$true),
    @($true,$false,-25,-20,16,26,$false),
    @($true,$false,18,22,16,26,$false),
    @($true,$false,-25,40,16,26,$false),
    @($false,$true,45,22,16,26,$true),
    @($false,$true,45,42,16,26,$false),
    @($false,$false,-25,22,16,26,$false),
    @($true,$false,12,16,16,26,$false)
)
foreach ($taskCase in $taskCases) {
    $taskActual = [ThermalTransferBoundaryFixture]::ThermalTransferBeneficial($taskCase[0],$taskCase[1],$taskCase[2],$taskCase[3],$taskCase[4],$taskCase[5])
    if ($taskActual -ne $taskCase[6]) { throw ('Thermal boundary failed: ' + ($taskCase -join ',')) }
}
Write-Output ('PASS: ' + $taskCases.Count + ' actual native thermal transfer cases; live rescue remains unverified')

$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
$taskSource = Get-Content -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/AnimalProvisioningHelper.cs') -Raw
$taskMethod = [regex]::Match($taskSource, 'public static bool ComfortableSpot\([^;]+;').Value
if (-not $taskMethod) { throw 'Production shelter boundary missing' }
Add-Type -TypeDefinition ('public static class HusbandryBoundary { ' + $taskMethod + ' }')
$taskCases = @(
    @{Temperature=[float]21; Minimum=[float]-6; Maximum=[float]34; Roof=$true; Expected=$true},
    @{Temperature=[float]21; Minimum=[float]-6; Maximum=[float]34; Roof=$false; Expected=$false},
    @{Temperature=[float]-22; Minimum=[float]-6; Maximum=[float]34; Roof=$true; Expected=$false},
    @{Temperature=[float]40; Minimum=[float]-6; Maximum=[float]34; Roof=$true; Expected=$false},
    @{Temperature=[float]0; Minimum=[float]0; Maximum=[float]30; Roof=$true; Expected=$true},
    @{Temperature=[float]-1; Minimum=[float]0; Maximum=[float]30; Roof=$true; Expected=$false},
    @{Temperature=[float]30; Minimum=[float]0; Maximum=[float]30; Roof=$true; Expected=$true},
    @{Temperature=[float]21; Minimum=[float]25; Maximum=[float]20; Roof=$true; Expected=$false}
)
foreach($taskCase in $taskCases) {
    $taskActual=[HusbandryBoundary]::ComfortableSpot($taskCase.Temperature,$taskCase.Minimum,$taskCase.Maximum,$taskCase.Roof)
    if ($taskActual -ne $taskCase.Expected) { throw 'Roofed species comfort boundary violated' }
}
@{cases=$taskCases.Count; native_execution=$false; game_orders=0} | ConvertTo-Json -Compress

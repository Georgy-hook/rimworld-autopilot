param(
    [switch]$StartNow
)

$ErrorActionPreference = 'Stop'
$primaryConfigPath = Join-Path $PSScriptRoot 'rimworld-autopilot.json'
$legacyConfigPath = Join-Path $PSScriptRoot 'laya-control.json'
$configPath = if (Test-Path -LiteralPath $primaryConfigPath) { $primaryConfigPath } else { $legacyConfigPath }
$config = if (Test-Path -LiteralPath $configPath) { Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json } else { $null }
$python = if ($config -and $config.python_exe) {
    $configuredPython = [string]$config.python_exe
    if ([System.IO.Path]::IsPathRooted($configuredPython)) {
        [System.IO.Path]::GetFullPath($configuredPython)
    } else {
        [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $configuredPython))
    }
} else { Join-Path $PSScriptRoot '.venv\Scripts\python.exe' }
$director = Join-Path $PSScriptRoot 'colony_director.py'
$dataDir = Join-Path $env:LOCALAPPDATA 'RimWorld Autopilot'
$env:RIMWORLD_AUTOPILOT_PREFERENCES = Join-Path $dataDir 'autopilot-preferences.json'
$env:PYTHONIOENCODING = 'utf-8'
$logDir = Join-Path $dataDir 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir 'decisions.jsonl'
$state = Join-Path $logDir 'colony-state.json'
$pidFile = Join-Path $logDir 'director.pid'
$runtimeStatus = Join-Path $logDir 'runtime-status.json'
$device = if ($config -and $config.device) { [string]$config.device } else { 'auto' }
$apiUrl = if ($config -and $config.api_url) { [string]$config.api_url } else { 'http://localhost:8765' }
$interval = if ($config -and $config.interval) { [int]$config.interval } else { 10 }

if (-not (Test-Path -LiteralPath $python)) {
    throw "Laya virtual environment not found: $python"
}

if (-not $StartNow) {
    Write-Host 'Load or create a RimWorld colony first.' -ForegroundColor Cyan
    Read-Host 'When the colony map is visible, press Enter to start Laya'
    Start-Sleep -Seconds 5
}
& $python -u $director --device $device --interval $interval --api-url $apiUrl --log $log --state $state --pid-file $pidFile --runtime-status $runtimeStatus

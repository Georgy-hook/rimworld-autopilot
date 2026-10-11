[CmdletBinding()]
param(
    [string]$RimWorldPath = "",
    [ValidateSet("cuda", "cpu", "auto")]
    [string]$Device = "auto"
)

$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$version = (Get-Content -LiteralPath (Join-Path $projectDir "VERSION") -Raw).Trim()
$venvPython = Join-Path $projectDir ".venv\Scripts\python.exe"
$configPath = Join-Path $projectDir "rimworld-autopilot.json"
$config = if (Test-Path -LiteralPath $configPath) { Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json } else { [pscustomobject]@{} }
if (-not $RimWorldPath -and $config.rimworld_path) { $RimWorldPath = [string]$config.rimworld_path }
if (-not $PSBoundParameters.ContainsKey('Device') -and $config.device -in @('cuda', 'cpu', 'auto')) { $Device = [string]$config.device }

if (-not (Test-Path $venvPython)) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        & $launcher.Source -3.12 -m venv (Join-Path $projectDir ".venv")
    } else {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (-not $python) { throw "Python 3.10+ was not found. Install Python and rerun this script." }
        & $python.Source -m venv (Join-Path $projectDir ".venv")
    }
    if ($LASTEXITCODE -ne 0) { throw "Creating the Python environment failed." }
}

$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$pathHelper = Join-Path $projectDir "rimworld_installation.py"
$pathArguments = @($pathHelper)
if ($RimWorldPath) { $pathArguments += @("--validate", $RimWorldPath) }
$resolvedRimWorld = & $venvPython @pathArguments
if ($LASTEXITCODE -ne 0) { throw "Choose a valid RimWorld folder with -RimWorldPath." }
$RimWorldPath = ([string]$resolvedRimWorld).Trim()

$env:USE_TF = "0"
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Updating pip failed." }
if ($Device -eq 'cpu') {
    & $venvPython -m pip install torch --index-url https://download.pytorch.org/whl/cpu
    if ($LASTEXITCODE -ne 0) { throw "Installing CPU PyTorch failed." }
}
& $venvPython -m pip install -r (Join-Path $projectDir "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Installing Python dependencies failed." }
& $venvPython (Join-Path $projectDir "laya_runtime.py") --device $Device --output (Join-Path $projectDir "model-device.json")
if ($LASTEXITCODE -ne 0) { throw "Checking the local model runtime failed." }

& $venvPython $pathHelper --install-mod (Join-Path $projectDir "vendor\RIMAPI") --game $RimWorldPath --backup-root (Join-Path $projectDir "mod-backups")
if ($LASTEXITCODE -ne 0) { throw "Installing the RimWorld mod failed." }

$installedValues = [ordered]@{
    python_exe = $venvPython
    director_script = (Join-Path $projectDir "colony_director.py")
    api_url = $(if ($config.api_url) { [string]$config.api_url } else { "http://localhost:8765" })
    device = $Device
    interval = $(if ($config.interval) { [int]$config.interval } else { 10 })
    rimworld_path = $RimWorldPath
}
foreach ($entry in $installedValues.GetEnumerator()) { $config | Add-Member -NotePropertyName $entry.Key -NotePropertyValue $entry.Value -Force }
$config | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $configPath -Encoding UTF8

Write-Host "Installed RimWorld Autopilot $version."
Write-Host "Enable Harmony and RIMAPI - RimWorld Autopilot in RimWorld, restart the game, load a copied save, then run Start-Autonomous.ps1."

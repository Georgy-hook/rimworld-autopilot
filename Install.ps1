[CmdletBinding()]
param(
    [string]$RimWorldPath = "C:\Program Files\Steam\steamapps\common\RimWorld",
    [ValidateSet("cuda", "cpu", "auto")]
    [string]$Device = "cuda"
)

$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $projectDir ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        & $launcher.Source -3.12 -m venv (Join-Path $projectDir ".venv")
    } else {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (-not $python) { throw "Python 3.10+ was not found. Install Python and rerun this script." }
        & $python.Source -m venv (Join-Path $projectDir ".venv")
    }
}

$env:USE_TF = "0"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $projectDir "requirements.txt")

$modsDir = Join-Path $RimWorldPath "Mods"
if (-not (Test-Path $modsDir)) { throw "RimWorld Mods directory was not found: $modsDir" }
$modTarget = Join-Path $modsDir "RIMAPI"
if (Test-Path $modTarget) {
    $backup = "$modTarget.backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Move-Item -LiteralPath $modTarget -Destination $backup
    Write-Host "Existing RIMAPI moved to $backup"
}
Copy-Item -Path (Join-Path $projectDir "vendor\RIMAPI") -Destination $modTarget -Recurse

$config = [ordered]@{
    python_exe = $venvPython
    director_script = (Join-Path $projectDir "colony_director.py")
    api_url = "http://localhost:8765"
    device = $Device
    interval = 10
}
$config | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $projectDir "rimworld-autopilot.json") -Encoding UTF8

Write-Host "Installed RimWorld Autopilot 0.0.6."
Write-Host "Enable Harmony and RIMAPI - RimWorld Autopilot in RimWorld, restart the game, load a copied save, then run Start-Autonomous.ps1."

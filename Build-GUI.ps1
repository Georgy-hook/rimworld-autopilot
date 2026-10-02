param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$versionFile = Join-Path $projectRoot "VERSION"
$version = (Get-Content -LiteralPath $versionFile -Raw).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid release version: $version" }
$buildEnvironment = Join-Path $projectRoot ".build-venv"
$builder = Join-Path $buildEnvironment "Scripts\python.exe"
$assetRoot = Join-Path $projectRoot "assets\gui"
$icon = Join-Path $assetRoot "autopilot-emblem.png"
$installerIcon = Join-Path $assetRoot "autopilot.ico"
$distribution = Join-Path $projectRoot "dist"
$installerScript = Join-Path $projectRoot "installer\RimWorld-Autopilot.iss"
$assetValidator = Join-Path $projectRoot "tools\validate_gui_assets.py"
$innoCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)

Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath $builder)) {
        & $PythonExe -m venv $buildEnvironment
    }
    & $builder -m pip install -r (Join-Path $projectRoot "requirements-build.txt")
    & $builder $assetValidator $assetRoot
    if ($LASTEXITCODE -ne 0) { throw "GUI asset compatibility validation failed." }
    & $builder -c "from PIL import Image; import sys; Image.open(sys.argv[1]).convert('RGBA').save(sys.argv[2], sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])" $icon $installerIcon
    if ($LASTEXITCODE -ne 0) { throw "Windows icon conversion failed." }

    $shared = @(
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--distpath", $distribution,
        "--add-data", "$assetRoot;assets\gui",
        "--add-data", "$versionFile;.",
        "--icon", $icon
    )

    & $builder -m PyInstaller @shared --name "RimWorld-Autopilot" (Join-Path $projectRoot "autopilot_control.py")
    if ($LASTEXITCODE -ne 0) { throw "RimWorld Autopilot build failed." }

    & $builder -m PyInstaller @shared --uac-admin --name "RimWorld-Autopilot-Setup" (Join-Path $projectRoot "autopilot_setup.py")
    if ($LASTEXITCODE -ne 0) { throw "RimWorld Autopilot Setup build failed." }

    $releaseName = "RimWorld-Autopilot-$version"
    $releaseDirectory = Join-Path $distribution $releaseName
    $resolvedDistribution = [IO.Path]::GetFullPath($distribution)
    $resolvedRelease = [IO.Path]::GetFullPath($releaseDirectory)
    if (-not $resolvedRelease.StartsWith($resolvedDistribution.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Release directory escaped the dist folder."
    }
    if (Test-Path -LiteralPath $releaseDirectory) {
        Remove-Item -LiteralPath $releaseDirectory -Recurse -Force
    }
    New-Item -ItemType Directory -Path $releaseDirectory -Force | Out-Null
    Get-ChildItem -LiteralPath $projectRoot -File |
        Where-Object { ($_.Extension -in @(".py", ".ps1", ".cmd", ".md", ".txt")) -or ($_.Name -in @("LICENSE", "RIMAPI_UPSTREAM_COMMIT", "VERSION")) } |
        Where-Object { $_.Name -notin @("laya-control.json", "laya-preferences.json", "rimworld-autopilot.json", "autopilot-preferences.json") } |
        Copy-Item -Destination $releaseDirectory -Force
    foreach ($folder in @("assets", "docs", "laya_gui", "tools", "vendor")) {
        Copy-Item -LiteralPath (Join-Path $projectRoot $folder) -Destination $releaseDirectory -Recurse -Force
    }
    Get-ChildItem -LiteralPath $releaseDirectory -Directory -Filter "__pycache__" -Recurse |
        Remove-Item -Recurse -Force
    Get-ChildItem -LiteralPath $releaseDirectory -Directory -Recurse |
        Where-Object { $_.Name -in @("bin", "obj") } |
        Sort-Object FullName -Descending |
        Remove-Item -Recurse -Force
    Get-ChildItem -LiteralPath $releaseDirectory -File -Filter "*.pyc" -Recurse |
        Remove-Item -Force
    Get-ChildItem -LiteralPath $releaseDirectory -File -Filter "*.pdb" -Recurse |
        Remove-Item -Force
    Copy-Item -LiteralPath (Join-Path $distribution "RimWorld-Autopilot.exe") -Destination $releaseDirectory -Force
    Copy-Item -LiteralPath (Join-Path $distribution "RimWorld-Autopilot-Setup.exe") -Destination $releaseDirectory -Force
    $archive = Join-Path $distribution "rimworld-autopilot-$version.zip"
    Compress-Archive -Path (Join-Path $releaseDirectory "*") -DestinationPath $archive -CompressionLevel Optimal -Force

    # The source ZIP stays complete; Program Files gets only the playable runtime.
    $installDirectory = Join-Path $distribution "$releaseName-install"
    $resolvedInstall = [IO.Path]::GetFullPath($installDirectory)
    if (-not $resolvedInstall.StartsWith($resolvedDistribution.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Install payload directory escaped the dist folder."
    }
    if (Test-Path -LiteralPath $installDirectory) {
        Remove-Item -LiteralPath $installDirectory -Recurse -Force
    }
    & $builder (Join-Path $projectRoot "install_payload.py") $projectRoot $installDirectory
    if ($LASTEXITCODE -ne 0) { throw "Install payload build failed." }
    foreach ($unwanted in @("README.md", "RELEASE_NOTES.md", "PLAYTEST_REPORT.md", "docs", "tools", "assets", "laya_gui", "Source")) {
        if (Test-Path -LiteralPath (Join-Path $installDirectory $unwanted)) {
            throw "Source-only item entered the install payload: $unwanted"
        }
    }

    $innoCompiler = $innoCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $innoCompiler) {
        throw "Inno Setup 6.7+ is required. Install JRSoftware.InnoSetup with winget."
    }
    & $innoCompiler "/DAppVersion=$version" $installerScript
    if ($LASTEXITCODE -ne 0) { throw "Windows installer build failed." }

    # Keep a fixed asset name for GitHub's /releases/latest/download/ URL.
    # This is a copy of the full Inno installer, not the post-install assistant.
    $versionedInstaller = Join-Path $distribution "$releaseName-Setup.exe"
    $latestInstaller = Join-Path $distribution "RimWorld-Autopilot-Installer.exe"
    if (-not (Test-Path -LiteralPath $versionedInstaller)) {
        throw "Versioned Windows installer was not produced."
    }
    Copy-Item -LiteralPath $versionedInstaller -Destination $latestInstaller -Force
    if ((Get-FileHash -LiteralPath $versionedInstaller -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $latestInstaller -Algorithm SHA256).Hash) {
        throw "Fixed-name installer does not match the versioned installer."
    }

    Write-Host "GUI executables, release archive, versioned installer and fixed-name installer are ready in $distribution"
}
finally {
    Pop-Location
}

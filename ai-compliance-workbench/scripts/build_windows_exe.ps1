param(
    [switch]$SkipFrontendBuild,
    [string]$PackageName = "AI_Compliance_Workbench_Windows"
)

$ErrorActionPreference = "Stop"
if ($PackageName -notmatch '^[A-Za-z0-9_.-]+$') {
    throw "PackageName may contain only letters, digits, dots, underscores, and hyphens."
}
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $ProjectRoot "frontend"
$PythonExe = Join-Path $ProjectRoot "backend\.venv\Scripts\python.exe"
$SpecFile = Join-Path $ProjectRoot "packaging\windows_onefile.spec"
$ReleaseDir = Join-Path $ProjectRoot "release"
$DistDir = Join-Path $ProjectRoot "dist"
$GuideFile = Get-ChildItem -LiteralPath (Join-Path $ProjectRoot "packaging") -Filter "*.txt" | Select-Object -First 1

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Backend virtual environment was not found. Run scripts\start_dev.ps1 once first."
}

if (-not $SkipFrontendBuild) {
    Push-Location $FrontendDir
    try {
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend production build failed."
        }
    } finally {
        Pop-Location
    }
}

$PyInstallerPackage = Join-Path $ProjectRoot "backend\.venv\Lib\site-packages\PyInstaller"
if (-not (Test-Path -LiteralPath $PyInstallerPackage)) {
    & $PythonExe -m pip install --disable-pip-version-check --timeout 120 --retries 5 "pyinstaller>=6.10,<7"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller installation failed."
    }
}

& $PythonExe -m PyInstaller --noconfirm --clean --distpath $DistDir --workpath (Join-Path $ProjectRoot "build\pyinstaller") $SpecFile
if ($LASTEXITCODE -ne 0) {
    throw "Windows EXE build failed."
}

New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
$PackageDir = Join-Path $ReleaseDir $PackageName
New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $DistDir "AI_Compliance_Workbench.exe") -Destination $PackageDir -Force
Copy-Item -LiteralPath $GuideFile.FullName -Destination (Join-Path $PackageDir "README.txt") -Force

$Hash = (Get-FileHash -LiteralPath (Join-Path $PackageDir "AI_Compliance_Workbench.exe") -Algorithm SHA256).Hash
Set-Content -LiteralPath (Join-Path $PackageDir "SHA256.txt") -Value "$Hash  AI_Compliance_Workbench.exe" -Encoding ASCII

$ZipPath = Join-Path $ReleaseDir ($PackageName + ".zip")
Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $ZipPath -CompressionLevel Optimal -Force

Write-Host "EXE: $PackageDir\AI_Compliance_Workbench.exe" -ForegroundColor Green
Write-Host "ZIP: $ZipPath" -ForegroundColor Green
Write-Host "SHA256: $Hash" -ForegroundColor Cyan

param(
    [switch]$SkipInstall,
    [switch]$NoLaunch
)

# Keep this file ASCII-only so Windows PowerShell 5.1 can parse it without a BOM.
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$VenvDir = Join-Path $BackendDir ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"

function Get-RequiredCommand([string[]]$Names) {
    foreach ($Name in $Names) {
        $Command = Get-Command $Name -ErrorAction SilentlyContinue
        if ($Command) {
            return $Command
        }
    }
    throw "Required command was not found: $($Names -join ' or ')"
}

function Assert-MinimumVersion(
    [string]$Label,
    [string]$VersionText,
    [int]$MinimumMajor,
    [int]$MinimumMinor = 0
) {
    if ($VersionText -notmatch '(\d+)\.(\d+)') {
        throw "Could not determine $Label version from: $VersionText"
    }
    $Major = [int]$Matches[1]
    $Minor = [int]$Matches[2]
    if ($Major -lt $MinimumMajor -or ($Major -eq $MinimumMajor -and $Minor -lt $MinimumMinor)) {
        throw "$Label $MinimumMajor.$MinimumMinor or newer is required. Found: $VersionText"
    }
}

function Test-PortInUse([int]$Port) {
    $Client = New-Object System.Net.Sockets.TcpClient
    try {
        $Client.Connect("127.0.0.1", $Port)
        return $true
    } catch {
        return $false
    } finally {
        $Client.Dispose()
    }
}

function Stop-ProcessTree([System.Diagnostics.Process]$Process) {
    if ($Process -and -not $Process.HasExited) {
        & taskkill.exe /PID $Process.Id /T /F | Out-Null
    }
}

$PythonCommand = Get-RequiredCommand @("python.exe", "python", "py.exe", "py")
$PythonPrefix = @()
if ($PythonCommand.Name -in @("py.exe", "py")) {
    $PythonPrefix = @("-3")
}
$NodeCommand = Get-RequiredCommand @("node.exe", "node")
$NpmCommand = Get-RequiredCommand @("npm.cmd", "npm")

$PythonVersion = (& $PythonCommand.Source @PythonPrefix --version 2>&1 | Out-String).Trim()
$NodeVersion = (& $NodeCommand.Source --version 2>&1 | Out-String).Trim()
Assert-MinimumVersion "Python" $PythonVersion 3 11
Assert-MinimumVersion "Node.js" $NodeVersion.TrimStart("v") 18 0

Write-Host "[1/5] $PythonVersion" -ForegroundColor Cyan
Write-Host "[2/5] Node.js $NodeVersion" -ForegroundColor Cyan

$EnvPath = Join-Path $ProjectRoot ".env"
$EnvExamplePath = Join-Path $ProjectRoot ".env.example"
if (-not (Test-Path -LiteralPath $EnvPath) -and (Test-Path -LiteralPath $EnvExamplePath)) {
    Copy-Item -LiteralPath $EnvExamplePath -Destination $EnvPath
    Write-Host "[INFO] Created .env from .env.example" -ForegroundColor Cyan
}

if (-not (Test-Path -LiteralPath $PythonExe)) {
    Write-Host "[3/5] Creating Python virtual environment..." -ForegroundColor Cyan
    & $PythonCommand.Source @PythonPrefix -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the Python virtual environment."
    }
} else {
    Write-Host "[3/5] Reusing Python virtual environment." -ForegroundColor Cyan
}

$PipExe = Join-Path $VenvDir "Scripts\pip.exe"
if (-not (Test-Path -LiteralPath $PipExe)) {
    Write-Host "[INFO] Repairing pip in the virtual environment..." -ForegroundColor Cyan
    & $PythonExe -m ensurepip --upgrade --default-pip
    if ($LASTEXITCODE -ne 0) {
        throw "The virtual environment exists but pip could not be repaired."
    }
}

if (-not $SkipInstall) {
    Write-Host "[4/5] Installing backend dependencies..." -ForegroundColor Cyan
    & $PythonExe -m pip install --disable-pip-version-check -r (Join-Path $BackendDir "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Backend dependency installation failed."
    }

    Write-Host "[5/5] Installing frontend dependencies..." -ForegroundColor Cyan
    Push-Location $FrontendDir
    try {
        if (Test-Path -LiteralPath (Join-Path $FrontendDir "package-lock.json")) {
            & $NpmCommand.Source ci
        } else {
            & $NpmCommand.Source install
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend dependency installation failed."
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Host "[4/5] Backend install skipped." -ForegroundColor DarkYellow
    Write-Host "[5/5] Frontend install skipped." -ForegroundColor DarkYellow
}

if ($NoLaunch) {
    Write-Host "Environment validation completed. Services were not started." -ForegroundColor Green
    return
}

foreach ($Port in @(8000, 5173)) {
    if (Test-PortInUse $Port) {
        throw "Port $Port is already in use. Stop the existing service and run this script again."
    }
}

$PowerShellExe = Join-Path $PSHOME "powershell.exe"
$EscapedBackend = $BackendDir.Replace("'", "''")
$EscapedFrontend = $FrontendDir.Replace("'", "''")
$EscapedPython = $PythonExe.Replace("'", "''")
$EscapedNpm = $NpmCommand.Source.Replace("'", "''")
$BackendCommand = "Set-Location -LiteralPath '$EscapedBackend'; & '$EscapedPython' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
$FrontendCommand = "Set-Location -LiteralPath '$EscapedFrontend'; & '$EscapedNpm' run dev -- --host 127.0.0.1 --port 5173"

$BackendProcess = Start-Process -FilePath $PowerShellExe -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-Command", $BackendCommand
) -PassThru
$FrontendProcess = Start-Process -FilePath $PowerShellExe -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-Command", $FrontendCommand
) -PassThru

Write-Host ""
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host "API docs: http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""

try {
    Read-Host "Press Enter to stop the services"
} finally {
    Stop-ProcessTree $BackendProcess
    Stop-ProcessTree $FrontendProcess
}

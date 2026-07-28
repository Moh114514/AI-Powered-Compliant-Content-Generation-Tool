$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$VenvDir = Join-Path $BackendDir ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"

function Require-Command($Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "未找到 $Name，请先安装后重新运行。"
    }
}

Require-Command "python"
Require-Command "node"
Require-Command "npm"

if (-not (Test-Path (Join-Path $ProjectRoot ".env")) -and (Test-Path (Join-Path $ProjectRoot ".env.example"))) {
    Copy-Item (Join-Path $ProjectRoot ".env.example") (Join-Path $ProjectRoot ".env")
    Write-Host "[INFO] 已从 .env.example 创建 .env" -ForegroundColor Cyan
}

if (-not (Test-Path $PythonExe)) {
    Write-Host "[1/4] 创建 Python 虚拟环境..." -ForegroundColor Cyan
    python -m venv $VenvDir
}

Write-Host "[2/4] 安装/更新后端依赖..." -ForegroundColor Cyan
& $PythonExe -m pip install --disable-pip-version-check -r (Join-Path $BackendDir "requirements.txt")

Write-Host "[3/4] 安装/更新前端依赖..." -ForegroundColor Cyan
Push-Location $FrontendDir
try {
    npm install
} finally {
    Pop-Location
}

Write-Host "[4/4] 启动前后端..." -ForegroundColor Green
$BackendCommand = "Set-Location '$BackendDir'; & '$PythonExe' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
$FrontendCommand = "Set-Location '$FrontendDir'; npm run dev"

Start-Process powershell -ArgumentList "-NoExit", "-Command", $BackendCommand
Start-Process powershell -ArgumentList "-NoExit", "-Command", $FrontendCommand

Write-Host "前端: http://localhost:5173" -ForegroundColor Green
Write-Host "后端: http://localhost:8000" -ForegroundColor Green
Write-Host "API 文档: http://localhost:8000/docs" -ForegroundColor Green

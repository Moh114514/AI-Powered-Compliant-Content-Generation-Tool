# 一键启动脚本（Windows / PowerShell）
# 用法：在 ai-compliance-workbench 目录下右键「使用 PowerShell 运行」或直接执行
#   powershell -ExecutionPolicy Bypass -File scripts/start_dev.ps1
$ErrorActionPreference = "Stop"

$root = Split-Path $MyInvocation.MyCommand.Path | Split-Path
$backend  = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$venv     = Join-Path $backend "venv"
$envFile  = Join-Path $root ".env"

# 1. 检查 Python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) { Write-Error "未找到 Python，请先安装 Python 3.11+ 并加入 PATH。"; exit 1 }
Write-Host "[1/6] Python: $($py.Source)"

# 2. 检查 Node.js
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) { Write-Error "未找到 Node.js，请先安装 Node.js 18+。"; exit 1 }
Write-Host "[2/6] Node.js: $($node.Source)"

# 3. 创建 Python 虚拟环境
if (-not (Test-Path $venv)) {
    Write-Host "[3/6] 创建虚拟环境..."
    & $py.Source -m venv $venv
}
$venvPy  = Join-Path $venv "Scripts\python.exe"
$venvPip = Join-Path $venv "Scripts\pip.exe"

# 4. 安装后端依赖
Write-Host "[4/6] 安装后端依赖..."
& $venvPip install -r (Join-Path $backend "requirements.txt")

# 5. 安装前端依赖
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "[5/6] 安装前端依赖..."
    & npm --prefix $frontend install
}

# 6. 复制 .env 示例（若不存在）
if (-not (Test-Path $envFile)) {
    if (Test-Path (Join-Path $root ".env.example")) {
        Copy-Item (Join-Path $root ".env.example") $envFile
        Write-Host "已根据 .env.example 生成 .env"
    }
}

# 启动服务
Write-Host "[6/6] 启动服务..."
Write-Host "------------------------------------------------------------"
Write-Host " 前端地址: http://localhost:5173"
Write-Host " 后端地址: http://localhost:8000"
Write-Host " API 文档: http://localhost:8000/docs"
Write-Host "------------------------------------------------------------"
Write-Host "（未配置 LLM_API_KEY 时自动使用演示模式；Ctrl+C 退出）"

Start-Process -NoNewWindow -FilePath $venvPy -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000","--reload" -WorkingDirectory $backend
Start-Process -NoNewWindow -FilePath "npm" -ArgumentList "run","dev" -WorkingDirectory $frontend

Read-Host "按回车键停止所有服务"
# 退出时尝试关闭子进程
Get-Process -Name "uvicorn" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like "*vite*" } | Stop-Process -Force

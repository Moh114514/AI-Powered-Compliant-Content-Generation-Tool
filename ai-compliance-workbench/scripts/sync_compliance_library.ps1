param(
    [Parameter(Mandatory = $true)]
    [string]$Source,

    [switch]$Apply,
    [switch]$AllowPreV12,
    [switch]$NoBackup
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptRoot "sync_compliance_library.py"

if (-not (Test-Path $PythonScript)) {
    throw "未找到同步脚本：$PythonScript"
}

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    $Python = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $Python) {
    throw "未找到 Python。请先安装 Python 3.11 或更高版本。"
}

$Arguments = @($PythonScript, "--source", $Source)
if ($Apply) {
    $Arguments += "--apply"
}
if ($AllowPreV12) {
    $Arguments += "--allow-pre-v1.2"
}
if ($NoBackup) {
    $Arguments += "--no-backup"
}

Write-Host "正在校验规则库：$Source" -ForegroundColor Cyan
& $Python.Source @Arguments
exit $LASTEXITCODE

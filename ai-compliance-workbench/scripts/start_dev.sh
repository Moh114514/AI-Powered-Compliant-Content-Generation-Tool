#!/usr/bin/env bash
# 一键启动脚本（Linux / macOS）
# 用法：bash scripts/start_dev.sh
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV="$BACKEND/venv"
ENVFILE="$ROOT/.env"
PY="${PYTHON:-python3}"

# 1. 检查 Python
command -v "$PY" >/dev/null 2>&1 || { echo "未找到 Python，请先安装 Python 3.11+"; exit 1; }
echo "[1/6] Python: $($PY --version 2>&1)"

# 2. 检查 Node.js
command -v node >/dev/null 2>&1 || { echo "未找到 Node.js，请先安装 Node.js 18+"; exit 1; }
echo "[2/6] Node.js: $(node --version)"

# 3. 虚拟环境
if [ ! -d "$VENV" ]; then
  echo "[3/6] 创建虚拟环境..."
  "$PY" -m venv "$VENV"
fi

# 4. 安装后端依赖
echo "[4/6] 安装后端依赖..."
"$VENV/bin/pip" install -r "$BACKEND/requirements.txt"

# 5. 安装前端依赖
if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "[5/6] 安装前端依赖..."
  (cd "$FRONTEND" && npm install)
fi

# 复制 .env 示例
if [ ! -f "$ENVFILE" ] && [ -f "$ROOT/.env.example" ]; then
  cp "$ROOT/.env.example" "$ENVFILE"
  echo "已根据 .env.example 生成 .env"
fi

# 6. 启动服务
echo "[6/6] 启动服务..."
echo "------------------------------------------------------------"
echo " 前端地址: http://localhost:5173"
echo " 后端地址: http://localhost:8000"
echo " API 文档: http://localhost:8000/docs"
echo "------------------------------------------------------------"
echo "（未配置 LLM_API_KEY 时自动使用演示模式；Ctrl+C 退出）"

"$VENV/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8000 --reload &
UVPID=$!
(cd "$FRONTEND" && npm run dev) &
VITEPID=$!

cleanup() {
  echo ""
  echo "正在停止服务..."
  kill "$UVPID" "$VITEPID" 2>/dev/null || true
}
trap cleanup EXIT
wait

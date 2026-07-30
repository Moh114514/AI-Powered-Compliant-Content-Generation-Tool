# AI 医美内容合规工作台

面向内部运营人员的医美内容生成与风险筛查工具。系统可以生成多平台文案、匹配确定性规则、执行语义风险分析、提供保守改写，并导出人工复核报告。

> 检测结果仅用于内容风险筛查，不构成法律或医疗意见；正式发布前必须由具备资质的人员复核。

## 当前版本

- 应用版本：1.3 prompt catalog
- 规则库：v1.2-dev
- 规则规模：153 条核心规则、682 个表达变体、31 个来源、30 条语义规则
- 测试语料：320 条自动测试案例、15 条视觉人工检查
- 规则状态：97 条 active、56 条 pending_review

`pending_review` 规则命中时会强制进入人工复核，不会被系统视为已经获得正式法务确认。

## 功能

- 朋友圈、微信社群、小红书、微信公众号和客服话术文案生成
- 精确、包含、正则、模糊和语义风险检测
- 风险等级、审核等级、法规来源及处理建议展示
- 自动改写并对改写稿重新执行合规检测
- Markdown、JSON 和纯文本报告导出
- 本地历史记录、设置、规则查询、数据校验和规则回归测试
- 无 API Key 的离线 Mock 演示模式
- 内置 5 个平台、26 个内容场景的 v1.0 全场景生成提示词
- 可新增、停用和重新启用自定义平台及场景，并配置分层提示词
- 真实 LLM 可根据运营约束起草或优化提示词，草稿经人工确认后保存

## 环境要求

- Python 3.11+
- Node.js 18+
- Windows PowerShell 5.1+、PowerShell 7，或 Bash

## 启动

Windows：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_dev.ps1
```

脚本源码保持纯 ASCII，兼容 Windows PowerShell 5.1 的默认编码行为。它会创建 `backend/.venv`、安装依赖、首次生成 `.env`，并启动前后端。默认前端端口为 5174；如果无法绑定，脚本会自动尝试 5175–5199，并在控制台输出实际前端地址。只检查环境而不启动服务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_dev.ps1 -SkipInstall -NoLaunch
```

macOS / Linux：

```bash
bash scripts/start_dev.sh
```

启动地址：

- 前端：http://localhost:5174（端口冲突时以启动脚本输出为准）
- 后端：http://localhost:8000
- API 文档：http://localhost:8000/docs

## Windows 便携版

生成无需 Python、Node.js 的单文件 Windows EXE：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows_exe.ps1
```

构建产物：

- `release/AI_Compliance_Workbench_Windows/AI_Compliance_Workbench.exe`
- `release/AI_Compliance_Workbench_Windows.zip`

EXE 启动后会自动选择 `8765–8799` 范围内的可用端口并打开浏览器。设置、历史记录和提示词覆盖保存在 `%LOCALAPPDATA%\AIComplianceWorkbench`；替换 EXE 升级时不会清除这些本地数据。内部构建会把项目当前 `.env` 作为首次运行默认配置打入 EXE，但不会覆盖用户目录中已经存在的 `.env`。分发包同时包含使用说明和 EXE 的 SHA-256。

## 模型配置

Provider、模型、Base URL、温度和 Token 由 `.env` 强制托管：每次程序启动都重新读取，SQLite 中曾经保存的模型设置不会覆盖它。配置了 `LLM_API_KEY` 时启用 OpenAI 兼容接口；未配置 Key 时使用 MockProvider。需要调整服务时，在 `.env` 中配置：

```ini
LLM_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096
CORS_ORIGINS=http://localhost:5174,http://127.0.0.1:5174
```

当前内部 EXE 已内置构建时的 `.env`，首次运行会写入 `%LOCALAPPDATA%\AIComplianceWorkbench\.env`。设置页的模型字段仅展示当前环境配置，不允许网页覆盖；API Key 不会回显或保存到网页设置。真实模型未就绪时会明确报错，不会静默改用 Mock。
设置页中的“AI 生成/优化提示词”也使用这里配置的真实模型；Mock 模式不会伪造提示词草稿。

模型调用失败时，检测结果会标记 `semantic_analysis_failed=true` 并要求人工复核，不会静默降级为低风险。DeepSeek 调用默认关闭思考模式；语义检测启用 JSON Output，并对空内容或非法 JSON 进行一次有限重试。

内容生成与合规检测结果会在开启“保存最近记录”后自动写入本地历史。内容生成、合规检测和规则筛选的页面状态保存在当前浏览器标签页中，切换导航不会清空。

## 规则库同步

权威核心规则源为仓库根目录下 `医美内容合规规则库_v1.1/02_系统调用数据`。小红书专项词库源为 `医美内容合规规则库_v1.1/07_小红书违禁词库/xhs_banned_words.json`。目录名保留历史版本命名，核心规则实际版本以 `metadata.json` 的 `v1.2-dev` 为准，专项词库版本为 `v1.0`。

只校验：

```powershell
python scripts/sync_compliance_library.py --source "../医美内容合规规则库_v1.1/02_系统调用数据"
```

校验通过后同步：

```powershell
python scripts/sync_compliance_library.py --source "../医美内容合规规则库_v1.1/02_系统调用数据" --apply
```

同步脚本默认从 `02_系统调用数据` 的同级 `07_小红书违禁词库` 自动读取专项词库；也可通过 `--xhs-banned-words` 显式指定。同步会先备份运行时数据，使用明确的文件白名单复制，并生成包含数量与 SHA-256 的 `sync_manifest.json`。

小红书专项词命中会在检测报告中独立展示词库原因、来源和替换建议。明确营销、引流、功效承诺语境按词库风险处置；科普、否定、风险告知和资质说明进入人工复核，避免把“最近”“不含治疗”等中性表达直接判为高风险。

## 验证

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm ci
npm run build
```

启动服务后还可执行：

- `POST /api/compliance/validate`：校验运行时规则结构与引用
- `POST /api/compliance/test-suite`：运行规则回归样本

更完整的检查步骤见 `docs/ACCEPTANCE_CHECKLIST.md`。

## 数据边界

- `data/compliance/*.json`：只读运行时规则数据
- `data/brand_profiles`、`data/prompts`：内置只读配置
- `data/workbench.db`：本地历史、平台场景目录和提示词覆盖，不进入版本控制
- `.env`：本地密钥和配置，不进入版本控制

维护用规则库是权威来源，`data/compliance` 仅作为 Web 运行时副本。更新时必须依次执行来源校验、同步、运行时校验、规则回归和人工抽检，并保持已有规则及来源 ID 稳定。

当前版本不包含登录、多租户、审批流和操作审计，只适合内网单机或小团队使用。

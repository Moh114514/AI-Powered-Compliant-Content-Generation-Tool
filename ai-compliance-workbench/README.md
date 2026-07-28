# AI 医美内容合规工作台

面向非技术运营人员的轻量内部工具，提供：

- 朋友圈、微信社群、小红书、公众号和客服话术生成；
- 关键词、正则与语义风险检测；
- 原文风险高亮、规则解释和来源查看；
- 一键合规改写及改写后复检；
- 人工复核摘要、检测报告导出；
- 最近记录、规则查询、数据校验与规则回归测试。

该工具不包含登录、组织权限、审批流或自动发布功能。需要人工判断时，请复制复核摘要并通过微信、钉钉等现有渠道对接。

## 目录

```text
ai-compliance-workbench/
├── backend/                  FastAPI 后端
├── frontend/                 React + TypeScript + Vite 前端
├── data/
│   ├── compliance/           Web 运行时规则 JSON（只读）
│   ├── prompts/              平台 Prompt 模板
│   ├── brand_profiles/       品牌配置
│   └── workbench.db          本地运行后生成，不提交 Git
├── scripts/                  启动、规则同步与校验脚本
└── .env.example
```

## 环境要求

- Python 3.11 或更高版本；
- Node.js 20 或更高版本；
- Windows PowerShell 7 建议使用；
- 首次安装依赖需要访问 Python 与 npm 软件源。

## 准备规则库

后端固定从以下目录读取运行数据：

```text
data/compliance/
```

至少需要：

```text
metadata.json
rules.json
rule_variants.json
sources.json
rule_sources.json
rule_platforms.json
semantic_rules.json
```

推荐同时放入：

```text
rule_examples.json
semantic_rule_sources.json
semantic_rule_examples.json
ad_classification_rules.json
test_cases.json
visual_manual_checks.json
manual_review_issues.json
risk_scoring.json
```

原始研究报告、法规 PDF、网页快照和处罚决定不需要放进模型上下文，可留在规则库归档目录；运行时只加载结构化 JSON。

## 同步本地 v1.2 规则库

维护用规则库与 Web 运行时数据应保持单向同步：

```text
医美内容合规规则库/02_系统调用数据
                 ↓ 校验与复制
ai-compliance-workbench/data/compliance
```

不要手工复制零散文件，也不要直接使用 `supplements` 或 `_backup_before_*` 目录作为运行数据。

### 第一步：只校验，不修改文件

在 `ai-compliance-workbench` 目录运行：

```powershell
.\scripts\sync_compliance_library.ps1 `
  -Source "C:\Users\TFKJ\Desktop\AI工具\医美内容合规规则库_v1.1\02_系统调用数据"
```

脚本默认按 v1.2 最低覆盖要求检查：

- 核心规则不少于 150 条；
- 表达变体不少于 500 条；
- 语义规则不少于 25 条；
- 规则示例不少于 200 条；
- 平台关系不少于 60 条；
- 测试样本不少于 300 条；
- 所有主要 ID 和引用关系完整；
- 所有正则表达式可以编译。

### 第二步：校验通过后同步

```powershell
.\scripts\sync_compliance_library.ps1 `
  -Source "C:\Users\TFKJ\Desktop\AI工具\医美内容合规规则库_v1.1\02_系统调用数据" `
  -Apply
```

同步时会：

1. 备份当前 `data/compliance` 文件；
2. 只复制明确允许的结构化 JSON；
3. 删除目标目录中已经不属于新版数据的受管文件；
4. 再次执行结构和引用校验；
5. 生成 `data/compliance/sync_manifest.json`，记录版本、数量、文件大小和 SHA-256。

生成的本地备份目录与 `supplements` 已被 `.gitignore` 排除，不应提交到仓库。

需要临时校验旧版本时可加 `-AllowPreV12`，但正式同步 v1.2 时不要使用该参数。

## Windows 启动

在项目目录执行：

```powershell
Copy-Item .env.example .env -ErrorAction SilentlyContinue
.\scripts\start_dev.ps1
```

启动后访问：

- 前端：http://localhost:5173
- 后端：http://localhost:8000
- API 文档：http://localhost:8000/docs

## 手动启动

### 后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### 前端

```powershell
cd frontend
npm install
npm run dev
```

## 配置真实模型

复制 `.env.example` 为 `.env`，填写：

```dotenv
LLM_API_KEY=你的密钥
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=你的模型名称
```

然后在网页“工具设置”中把 Provider 改为 `OpenAI 兼容接口`。

未配置密钥时自动使用 MockProvider。Mock 模式适合演示界面与确定性检测，不代表真实模型生成质量。

## 测试与验收

后端单元测试：

```powershell
cd backend
python -m pytest -q
```

前端构建检查：

```powershell
cd frontend
npm run build
```

网页“工具设置”中还可以执行：

1. 规则库结构校验；
2. `test_cases.json` 回归测试；
3. 查看失败样本和漏命中规则。

回归测试结果用于比较规则版本，不等同于法务准确率认证。

## 当前安全边界

- “未发现明显风险”不等于内容完全合法；
- 系统不验证机构、医生、项目、药械、荣誉和统计数据的真实性；
- 系统主要检测文本，不自动审核图片、视频画面、证件和素材授权；
- 语义模型失败时，系统会明确标记检测降级并要求人工复核；
- 规则状态为 `pending_review` 时，不应直接作为最终法律结论使用；
- 正式投入业务前，应由法务、合规或医疗专业人员审核核心规则和平台范围。

## 维护原则

- 维护用规则库是研究与版本管理的权威来源；
- `data/compliance` 是 Web 工具运行时唯一读取目录，由同步脚本生成；
- 不在网页中直接修改原始规则；
- 更新规则后依次执行：来源校验 → 同步 → 数据校验 → 回归测试 → 人工抽检；
- 保留 `rule_id`、`source_id` 和变更记录，避免重新编号；
- 法律法规、平台规则和处罚案例全文用于证据归档，不应每次全部发送给模型。

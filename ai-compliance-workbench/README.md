# AI 医美内容合规工作台

> 供公司**非技术运营人员**使用的轻量级内部 Web 工具，基于「医美内容合规规则库」自动生成与审核推广文案，并给出合规修改建议。
> 本工具**不是**面向消费者的产品，也不含用户体系、审批流、权限等企业管理功能。

---

## 一、项目用途

面向运营同学在日常投放（朋友圈 / 微信社群 / 小红书 / 微信公众号 / 客服话术）中：

1. **按场景生成** 推广文案（示例 / 草稿，需人工复核后使用）。
2. **一键检测** 文案风险：高亮命中词、解释违规原因、按法规归类、给出删除 / 补充证据 / 改写 / 送审等处理建议。
3. **自动改写**：对允许自动改写的违规表达生成安全降级稿，不允许自动改写的明确标记「需人工复核」。
4. **导出**：复制 / 下载文案与风险报告（Markdown / JSON / 纯文本）。
5. **规则查询 & 数据重载**：供规则维护人员检索规则、来源，并在更新规则库后热重载。

工具内置 **演示模式（Demo）**：未配置大模型 API Key 时自动启用，使用启发式语义检测与安全改写兜底，无需任何外部服务即可完整体验流程。

> ⚠️ **免责声明（始终展示，永不消失）**：本工具仅作内容合规辅助参考，检测结果不构成法律意见，也不能等同于「完全合规 / 完全合法」。最终发布前须经具备资质的人员人工复核。

---

## 二、环境要求

| 依赖 | 版本 | 说明 |
| --- | --- | --- |
| Python | 3.11+ | 后端运行环境（脚本会自动创建虚拟环境） |
| Node.js | 18+ | 前端运行环境（含 npm） |
| 操作系统 | Windows / macOS / Linux | 提供对应一键启动脚本 |

无需数据库服务（SQLite 仅用于本地记录与设置）；无需联网（演示模式下完全离线）。

---

## 三、安装步骤

无需手动安装，直接运行对应启动脚本即可（脚本会自动创建 Python 虚拟环境、安装依赖、生成 `.env`）。

如需手动分步安装：

```bash
# 后端：创建虚拟环境并安装依赖
cd backend
python -m venv venv
venv/Scripts/pip install -r requirements.txt   # Windows
# 或 venv/bin/pip install -r requirements.txt   # macOS / Linux

# 前端：安装依赖
cd ../frontend
npm install
```

---

## 四、规则库位置

规则库为**只读**数据，以 JSON 文件形式随项目分发，初始来自 `医美内容合规规则库_v1.1 / 02_系统调用数据/`：

```
ai-compliance-workbench/
└── data/
    └── compliance/        # 18 个 JSON（规则、变体、来源、语义规则、元数据等）
```

- 当前版本：**v1.1-dev**
- 规模：**97 条核心规则 / 234 个表达变体 / 28 个来源 / 5 条语义规则**
- 后端启动时自动加载到内存并建立索引；规则 ID 不可修改、不可重新生成。
- 更新规则库：替换 `data/compliance/` 下对应 JSON 后，调用接口 `POST /api/compliance/reload` 或重启服务即可热重载。

数据校验（检查 JSON 解析与 ID 引用完整性）：

```bash
python scripts/validate_compliance_data.py
```

---

## 五、启动方式

### Windows（PowerShell）

在项目根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_dev.ps1
```

### macOS / Linux（Bash）

```bash
bash scripts/start_dev.sh
```

脚本会依次完成：检查 Python / Node → 创建虚拟环境 → 安装后端依赖 → 安装前端依赖 → 复制 `.env` → 同时启动前后端。

启动后访问：

| 服务 | 地址 |
| --- | --- |
| 前端界面 | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| API 文档（Swagger） | http://localhost:8000/docs |

> 未配置 `LLM_API_KEY` 时自动进入**演示模式**（页面顶部有 Demo 标识），所有功能可正常使用。

---

## 六、模型配置

编辑项目根目录的 `.env`（首次启动会自动从 `.env.example` 复制生成）：

```ini
# 留空则自动启用演示模式
LLM_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=1200
```

- 兼容 **OpenAI / DeepSeek / 通义** 等 OpenAI 风格接口，只需修改 `LLM_BASE_URL` 与 `LLM_MODEL`。
- 配置有效 Key 后，生成、语义检测、改写将调用真实模型；调用失败时**自动回退演示模式**，不会中断服务。
- 也可在界面「设置」页切换模型提供方（mock / 自定义），无需重启。

---

## 七、数据存储

仅本地文件，无外部数据库：

| 数据 | 位置 | 说明 |
| --- | --- | --- |
| 合规规则库 | `data/compliance/*.json` | 只读，维护人员更新 |
| 品牌画像 / Prompt 模板 | `data/brand_profiles/`、`data/prompts/` | 只读配置 |
| 历史记录 & 设置 | `backend/data/app.db`（SQLite） | 自动创建，本地留存 |

SQLite 使用 `check_same_thread=False` + 进程锁，适配 uvicorn 多线程；记录 ID 基于 UUID，避免主键冲突。

---

## 八、测试方式

### 后端单元测试（pytest）

```bash
cd backend
venv/Scripts/python -m pytest tests/ -q
# 或（已激活虚拟环境）python -m pytest tests/ -q
```

覆盖：规则库加载与完整性、精确 / 包含 / 正则 / 模糊匹配、多规则命中、平台过滤、来源关联、风险分级聚合、无命中、中文标点、去重、接口健康与错误处理、MockProvider 生成 / 改写、历史增删、报告生成、热重载、数据校验。当前 **20 项全部通过**。

### 规则数据校验

```bash
python scripts/validate_compliance_data.py
```

### 接口冒烟（示例）

```bash
curl -X POST http://127.0.0.1:8000/api/compliance/check \
  -H "Content-Type: application/json" \
  -d '{"platform":"朋友圈","content_type":"promotion","text":"全城效果最好，零风险，7天年轻十岁，限时免费体验"}'
```

### 前端构建校验

```bash
cd frontend
npm run build
```

---

## 九、已知限制

1. **演示模式为启发式兜底**：MockProvider 的语义检测基于正则与关键词，覆盖常见风险类型，但无法替代真实大模型对上下文、隐喻、谐音拆字的深度理解。
2. **规则覆盖的平台范围有限**：当前规则库的 `rule_platforms` 仅标注 微信 / 小红书 / 抖音，而本工具面向 5 个平台。对未单独标注平台专属规则的平台，引擎按通用规则检测，并在结果中标记 `platform_rules_incomplete`（平台规则可能不全），提示人工注意。
3. **自动改写偏保守**：命中「不允许自动改写」的规则（如安全性承诺、免费体验诱导）时，工具只追加风险提示语并标记「需人工复核」，不会擅自删除或替换，以避免遗漏实质性违规。
4. **无鉴权与多租户**：按需求刻意省略，仅作内网单机 / 小团队使用；如需对外或多人协作，须补充鉴权与审计。
5. **检测结果 ≠ 法律结论**：工具不宣称「未检测到风险 = 完全合法」，界面与报告始终附带免责声明。
6. **FastAPI 启动钩子告警**：`app.main` 仍使用 `@app.on_event("startup")`（已弃用，仅告警、不影响功能），后续可迁移至 `lifespan` 事件处理器。

---

## 十、后续升级方向

1. **接入真实模型做语义检测**：在「设置」中配置 Provider 后，语义风险识别准确率将显著提升，尤其对隐喻、谐音拆字、软广话术。
2. **补全平台专属规则**：与合规团队共建抖音、朋友圈、公众号等平台的专属规则，消除 `platform_rules_incomplete` 警告。
3. **规则库热更新 UI**：在界面内提供上传 / 校验 / 重载规则文件的入口，降低维护门槛。
4. **历史记录增强**：增加按平台 / 风险等级筛选、批量导出、趋势统计。
5. **可解释性增强**：为每条命中规则展示法规原文摘录与适用 / 豁免场景，提升运营同学的合规认知。
6. **按需补鉴权**：若推广至多团队使用，增加轻量登录与操作审计（当前不在范围内）。

---

## 目录结构概览

```
ai-compliance-workbench/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/routers/     # 各业务接口
│   │   ├── core/            # 配置 / 文本归一化 / 数据加载 / 匹配
│   │   ├── services/        # 生成 / 合规引擎 / 导出 / LLM 适配
│   │   ├── repositories/    # SQLite 存储
│   │   └── schemas/         # Pydantic 请求模型
│   ├── tests/               # pytest 用例
│   └── requirements.txt
├── frontend/                # React + TS + Vite + Tailwind
│   └── src/
│       ├── pages/           # 生成 / 检测 / 历史 / 规则库 / 设置
│       ├── components/      # 风险徽标 / 高亮 / 规则卡 / 报告
│       └── api/             # 接口封装
├── data/                    # 规则库 / 品牌画像 / Prompt 模板（只读）
├── scripts/                 # 一键启动 + 数据校验
├── .env.example
└── README.md
```

---

*本工具为内部效率工具，请结合专业合规判断使用。*

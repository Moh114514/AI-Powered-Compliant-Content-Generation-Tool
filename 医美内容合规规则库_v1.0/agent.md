# 医美内容合规规则库 — Agent 规范手册

> 本文件为 AI 代理（Agent）操作本项目时的强制规范。任何修改数据、新增规则、生成文件的行为必须遵守以下约定。

---

## 1 项目概述

- **名称**: 医美内容合规规则库
- **版本**: v1.0（样例阶段 → 批量建库）
- **适用范围**: 中国大陆医疗美容行业内容合规筛查
- **定位**: 不是简单禁词表，而是结构化的合规判定系统——每条规则可追溯到可验证的官方法律来源
- **免责声明**: 本规则库为内容风险筛查工具，不替代律师、法务或监管部门正式意见

---

## 2 目录结构

```
医美内容合规规则库_v1.0/
├── 01_合规规则库主表/     ← Excel 主库（人工维护入口）
│   └── 医美内容合规规则库_v1.0.xlsx   (18 sheets)
├── 02_系统调用数据/       ← JSON + CSV（程序调用入口）
│   ├── rules.json
│   ├── rule_variants.json
│   ├── rule_sources.json
│   ├── rule_platforms.json
│   ├── rule_channels.json
│   ├── rule_examples.json
│   ├── semantic_rules.json
│   ├── semantic_rule_sources.json
│   ├── semantic_rule_examples.json
│   ├── ad_classification_rules.json
│   ├── enforcement_cases.json
│   ├── case_leads.json
│   ├── test_cases.json
│   ├── manual_review_issues.json
│   ├── sources.json
│   ├── changelog.json
│   ├── metadata.json
│   ├── medical_beauty_compliance_library_v1.0.json  ← 汇总
│   ├── compliance_rules.schema.json                 ← JSON Schema
│   └── *.csv (UTF-8 BOM, 同名对应)
├── 03_研究与使用文档/     ← 研究报告、使用说明等
├── 04_来源证据/           ← 法规原文 PDF 截图等
│   ├── 01_法律法规/
│   ├── 02_行政规章/
│   ├── 03_监管指南/
│   ├── 04_平台规则/
│   ├── 05_处罚案例/
│   ├── 06_司法案例/
│   └── 07_案例线索/
├── 05_测试与质量报告/
│   └── validation_report.json
├── 06_版本管理/
│   └── 历史版本/
├── _build.py              ← 全量构建脚本（openpyxl → Excel + JSON + CSV）
├── _batch2_rules.py       ← 增量规则数据（importlib 加载）
├── _batch2_variants.py    ← 增量变体数据
└── agent.md               ← 本文件
```

**双主输出原则**: Excel 是人工维护入口，JSON 是程序调用入口。二者数据必须一致。

---

## 3 ID 体系（强制格式）

| 实体 | ID 格式 | 示例 | 递增规则 |
|---|---|---|---|
| 来源 | `S` + 4位数字 | S0001, S0014 | 全局递增 |
| 核心规则 | `R-A` + 2位类别号 + `-` + 3位序号 + 可选子规则字母 | R-A01-001, R-A05-002a | 类别内递增 |
| 表达变体 | `V` + 6位数字 | V000001 | 全局递增 |
| 规则示例 | `E` + 6位数字 | E000001 | 全局递增 |
| 语义规则 | `SR` + 4位数字 | SR0001 | 全局递增 |
| 广告认定规则 | `AC` + 4位数字 | AC0001 | 全局递增 |
| 官方处罚案例 | `C` + 4位数字 | C0001 | 全局递增 |
| 案例线索 | `CL` + 4位数字 | CL0001 | 全局递增 |
| 测试样本 | `T` + 4位数字 | T0001 | 全局递增 |
| 待核验问题 | `I` + 4位数字 | I0001 | 全局递增 |
| 规则来源关联 | `RS` + 4位数字 | RS0001 | 全局递增 |

**子规则拆分**: A05/A09/A12 等按条件拆分时用小写字母后缀（如 R-A05-002a / R-A05-002b），不得另占序号。

---

## 4 规则分类体系

| 类别代码 | 类别名称 | 已建规则数 |
|---|---|---|
| A01 | 绝对化及最高级表达 | 10 |
| A02 | 医疗功效承诺 | 12 |
| A03 | 安全性和无风险承诺 | 7 |
| A04 | 效果时间和持续时间承诺 | 8 |
| A05 | 患者证明和用户见证 | 拆分为 a/b |
| A06 | 医生和机构资质背书 | 待建 |
| A07 | 荣誉排名和数据宣传 | 9 |
| A08 | 诱导消费和焦虑制造 | 待建 |
| A09 | 容貌焦虑和心理施压 | 拆分为 a/b |
| A10 | 伪科学和虚构诊断 | 待建 |
| A11 | 药品和医疗器械违规宣传 | 待建 |
| A12 | 名人背书和代言 | 拆分为 a/b |
| A13 | 概念混淆和伪科学术语 | 待建 |
| A14 | 平台规则限制 | 待建 |
| A15 | 未经审批项目宣传 | 待建 |
| A16 | 广告识别与商业属性披露 | 1 |

---

## 5 枚举值规范（不可自创新值）

### 5.1 legal_conclusion（法律结论）

| 值 | 含义 |
|---|---|
| `explicitly_prohibited` | 明确禁止（无排除情形） |
| `conditionally_prohibited` | 有条件禁止（存在排除情形/证据可豁免） |
| `evidence_required` | 需提供证据（主张内容需证明） |
| `qualification_required` | 需资质证明 |
| `platform_prohibited` | 平台规则禁止（非法律禁止但平台禁止） |
| `internal_prohibited` | 内部策略禁止 |
| `not_applicable` | 不适用（合规内容） |
| `uncertain` | 不确定（需人工判定） |

### 5.2 risk_level（风险等级）

| 值 | 含义 | 对应典型场景 |
|---|---|---|
| `critical` | 严重风险 | 明确违反法律禁止性条款 |
| `high` | 高风险 | 有条件禁止/需证据 |
| `medium` | 中风险 | 灰地带/需审核 |
| `low` | 低风险 | 合规或近似合规 |

### 5.3 review_level（审核级别）— 与 risk_level 分离

| 值 | 含义 |
|---|---|
| `L1` | 自动拦截（系统直接 block） |
| `L2` | 自动标记+人工确认 |
| `L3` | 请求证据/资质 |
| `L4` | 仅记录/观察 |

**risk_level ≠ review_level**: critical 可能对应 L1 或 L2；high 可能对应 L2 或 L3。二者独立赋值。

### 5.4 system_action（系统动作）

| 值 | 含义 |
|---|---|
| `block` | 直接拦截 |
| `mandatory_human_review` | 强制人工审核 |
| `request_evidence` | 请求证据材料 |
| `request_qualification` | 请求资质证明 |
| `warning` | 警告标记 |
| `pass` | 放行 |

### 5.5 rule_dimension（规则维度）

| 值 | 含义 |
|---|---|
| `content_nature` | 内容性质维度（是否构成广告等） |
| `expression_risk` | 表达方式风险维度 |
| `medical_efficacy_risk` | 医疗功效风险维度 |
| `platform_risk` | 平台规则风险维度 |
| `legal_risk` | 法律合规风险维度 |

### 5.6 其他枚举

| 字段 | 枚举值 |
|---|---|
| `effective_status` | active / pending_review / suspended / superseded / abolished |
| `verification_status` | verified / partially_verified / pending_verification / unavailable |
| `confidence` | 高 / 中 / 低 |
| `review_status` | 已审核 / 待审核 |
| `content_legal_nature` | medical_advertisement / service_information / health_education / user_generated_content / diagnosis_communication / commercial_recommendation / uncertain |
| `example_type` | prohibited / compliant / high_risk / boundary |

---

## 6 核心规则字段清单

每条规则（rules.json）必须包含以下字段，缺一不可：

```
rule_id, rule_name, category_code, category_name,
rule_description, semantic_rule,
legal_conclusion, risk_level, basis_type,
applicable_business_domain, applicable_content_legal_nature,
prohibited_context, allowed_context,
evidence_requirement, qualification_requirement,
system_action, auto_rewrite_allowed, replacement_strategy,
manual_review_required, confidence, review_status,
effective_status, version, created_at, updated_at,
update_reason, updated_source_id,
rule_dimension, review_level, notes
```

**重要约束**:
- `basis_type` 必须使用分号分隔的类型标识：`law` / `regulatory_guideline` / `department_rule` / `platform_rule` / `judicial_case` / `administrative_case`
- `prohibited_context` 和 `allowed_context` 必须给出具体场景描述，不能只写"任何场景"/"无"
- `allowed_context` 写"无"时，表示确实没有任何允许情形
- `update_reason` 和 `updated_source_id` 记录修订历史，新规则可为 null

---

## 7 关联表规范（多对多不得压缩为单字段）

| 关联表 | JSON 文件 | 关系 |
|---|---|---|
| 规则↔来源 | `rule_sources.json` | 一条规则可关联多个来源 |
| 规则↔平台 | `rule_platforms.json` | 一条规则可适用多个平台产品线 |
| 规则↔渠道 | `rule_channels.json` | 一条规则可适用多个渠道 |
| 语义规则↔来源 | `semantic_rule_sources.json` | 一条语义规则可关联多个来源 |
| 语义规则↔示例 | `semantic_rule_examples.json` | 一条语义规则可有多个示例 |

**禁止**: 在 rule 或 semantic_rule 中用单个 `source_id` 或把多个值堆在一个字段里（如 `source_ids: "S0001,S0002"`）。必须拆到独立关联表。

---

## 8 来源证据规范

当前已收录 14 条正式来源（S0001-S0014），全部 `verification_status: verified`：

| ID | 名称 | 类型 | 效力级别 |
|---|---|---|---|
| S0001 | 广告法(2021修正) | 法律 | 法律 |
| S0002 | 互联网广告管理办法 | 部门规章 | 部门规章 |
| S0003 | 医美广告执法指南 | 部门文件 | 监管指南 |
| S0004 | 医疗广告管理办法 | 部门规章 | 部门规章 |
| S0005 | 医美服务管理办法(2016修正) | 部门规章 | 部门规章 |
| S0006 | 三品一械广告审查办法 | 部门规章 | 部门规章 |
| S0007 | 广告绝对化用语执法指南 | 部门文件 | 监管指南 |
| S0008 | 答记者问 | 政策解读 | 官方解释 |
| S0009 | 反不正当竞争法(2025修订) | 法律 | 法律 |
| S0010 | 消费者权益保护法实施条例 | 行政法规 | 行政法规 |
| S0011 | 医疗广告认定指南(2025) | 部门文件 | 监管指南 |
| S0012 | 医疗广告监管工作指南(2025) | 部门文件 | 监管指南 |
| S0013 | 广告引证内容执法指南(2026) | 部门文件 | 监管指南 |
| S0014 | 加强医美行业监管指导意见(2023) | 部门文件 | 监管指南 |

**新增来源规则**:
- 只收录官方发布的法律法规、部门规章、监管指南、行政处罚决定书、法院判决书
- 禁止将媒体报道、自媒体文章作为正式依据来源
- 每条来源必须包含 `official_url`、`access_date`、`verification_status`
- 来源效力级别：法律 > 行政法规 > 部门规章 > 部门文件/监管指南 > 政策解读 > 平台规则

---

## 9 平台产品线（15 条）

| 平台 | 产品线代码 |
|---|---|
| 微信 | wx_moments_personal / wx_moments_paid_ad / wx_group / wx_video / wx_private_cs |
| 小红书 | xhs_natural_note / xhs_brand_cooperation / xhs_juguang_ad / xhs_ecommerce_live |
| 抖音 | douyin_general / douyin_ecommerce / douyin_live |
| 巨量引擎 | juliang_engine_ad |
| 其他 | other |

规则对不同产品线可能有不同 system_action（如自然内容 vs 付费广告），在 `rule_platforms.json` 中体现。

---

## 10 构建与发布流程

### 10.1 全量构建

```bash
cd 医美内容合规规则库_v1.0/
python _build.py
```

- 输出: Excel（01_合规规则库主表/）+ 全部 JSON + 全部 CSV（02_系统调用数据/）
- `_build.py` 内含全部数据作为 Python dict，运行后全量重生成

### 10.2 增量构建（推荐方式）

1. 新规则数据写入 `_batch{n}_rules.py` / `_batch{n}_variants.py`
2. 通过 `importlib.util` 加载到构建脚本
3. 与现有 JSON 合并 → 验证 U+FFFD → json.dump 输出
4. 同步 CSV + Excel

### 10.3 数据流方向

```
Python dict 数据 → JSON (权威源) → CSV → Excel
```

**JSON 是权威数据源**。手动修改 Excel 后需反向同步到 JSON（目前未实现自动化）。

---

## 11 质量检查规范

### 11.1 U+FFFD 乱码检测（强制，每次写入后必检）

模型在 Write/Bash 工具输出含大量中文的长文件时，常见汉字会被替换为 U+FFFD。

**已确认受害字符**: 美/食/超/审/监/院/场/广/三/底/全/删/内/涉/国/验/合/服/传/个/从/虑/中/布/综 等

**检测方法**:
```python
import re
count = len(re.findall(r'\ufffd', open('file', encoding='utf-8').read()))
print(f"U+FFFD count: {count}")
# 必须为 0 才可交付
```

**修复策略**: 写 Python 脚本按"上下文字符串"批量 replace，不要用 Edit 一行行改（易遗漏）。

### 11.2 规则 ID 唯一性检查

```python
ids = [r['rule_id'] for r in rules]
assert len(ids) == len(set(ids)), "Duplicate rule_id found!"
```

### 11.3 关联完整性检查

- 每条 rule 的 `rule_id` 必须在 `rules.json` 中存在
- `rule_sources.json` 中引用的 `source_id` 必须在 `sources.json` 中存在
- `rule_platforms.json` 中引用的 `platform_product_line` 必须在 `rule_channels.json` 定义中存在
- `test_cases.json` 中 `expected_rule_ids` 必须全部指向真实存在的规则

### 11.4 测试样本完整性

- 每条测试样本的 `input_text` **不得为空**
- `expected_rule_ids` 必须是 JSON 数组（不是字符串）
- 必须覆盖：违规 / 合规 / 边界 / 谐音对抗 / 平台差异 五类场景

---

## 12 内容创作红线（禁止事项）

| 禁止行为 | 原因 |
|---|---|
| 同义词拆条凑数 | "最好/最佳/最优"不应拆成3条规则，应合并为1条+变体 |
| 绝对化一禁了之 | 必须区分排除情形（S0007 第五六条），用 `conditionally_prohibited` |
| 媒体案例作正式依据 | 媒体报道不是法律来源，只能作案例线索 |
| 多值压缩为单字段 | 来源/平台/渠道等多对多关系必须拆到关联表 |
| 自创枚举值 | 只能用第 5 节定义的枚举值，不得新增 |
| 规则无来源关联 | 每条规则必须至少关联 1 条 sources.json 中的来源 |
| 测试样本留空壳 | input_text / content_context / platform_product_line 等不得为空 |

---

## 13 当前进度与待办

| 项目 | 数量 | 状态 |
|---|---|---|
| 正式来源 | 14 | 全部 verified |
| 核心规则 | 65 | A01/A02/A03/A04/A07 已建；其余待建 |
| 表达变体 | 159 | 部分完成 |
| 规则来源关联 | 128 | 部分完成 |
| 语义规则 | 5 | SR0001-SR0005 |
| 广告认定规则 | 3 | AC0001-AC0003 |
| 测试样本 | 26 | 全部有真实内容（T0021-T0026 已修复） |
| 案例线索 | 3 | CL0001-CL0003 |
| 待核验问题 | 5 | I0001-I0005 |

**待建类别**: A05(b), A06, A08, A09(b), A10, A11, A12(b), A13, A14, A15, A16扩充 → 约 135 条规则待建，目标 200+。

---

## 14 Excel Sheet 名称映射

| 序号 | Sheet名 | 对应 JSON |
|---|---|---|
| 00 | 00_使用说明 | — |
| 01 | 01_数据字典 | — |
| 02 | 02_来源表 | sources.json |
| 03 | 03_核心规则 | rules.json |
| 04 | 04_表达变体 | rule_variants.json |
| 05 | 05_规则来源关联 | rule_sources.json |
| 06 | 06_平台适用关系 | rule_platforms.json |
| 07 | 07_渠道适用关系 | rule_channels.json |
| 08 | 08_规则示例 | rule_examples.json |
| 09 | 09_语义检测规则 | semantic_rules.json |
| 10 | 10_语义规则来源关联 | semantic_rule_sources.json |
| 11 | 11_语义规则示例 | semantic_rule_examples.json |
| 12 | 12_广告认定规则 | ad_classification_rules.json |
| 13 | 13_官方处罚案例 | enforcement_cases.json |
| 14 | 14_案例线索 | case_leads.json |
| 15 | 15_测试样本 | test_cases.json |
| 16 | 16_待人工核验 | manual_review_issues.json |
| 17 | 17_版本变更记录 | changelog.json |

---

## 15 Excel 文件操作注意事项

- **文件被占用时**: 不要 rm/mv（Permission denied），用不同文件名生成新文件，让用户手动关闭旧文件后替换
- **CSV 编码**: UTF-8 BOM（`utf-8-sig`），确保 Excel 正确打开
- **Excel 格式**: 每个 Sheet 需设置自动筛选 + 冻结首行 + 枚举列下拉验证
- **openpyxl 版本**: 使用已安装在 venv 的版本，不要 global install

---

## 16 修订记录格式

每条修订写入 `changelog.json`，格式：

```json
{
  "change_id": "CH001",
  "change_type": "add_rule | modify_rule | add_source | fix_data | ...",
  "affected_ids": ["R-A01-003"],
  "description": "新增极限程度副词修饰医美效果规则",
  "changed_at": "2026-07-27",
  "changed_by": "agent"
}
```

规则本身的 `update_reason` 和 `updated_source_id` 也需同步填写。

"""规则库加载与索引服务。从 data/compliance 读取权威 JSON（只读），
构建内存索引，供检测引擎与 API 使用。支持重新加载与数据校验。
"""
import json
import os
from dataclasses import dataclass, field
from typing import Any

from app.core import config


def _read_json(path: str) -> Any:
    if not os.path.exists(path):
        raise FileNotFoundError(f"未找到数据文件：{os.path.basename(path)}")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as e:
        fname = os.path.basename(path)
        raise ValueError(f"数据文件 {fname} 解析失败（第 {e.lineno} 行）：{e.msg}。请检查 JSON 格式后重试。") from e


def _as_list(d: Any) -> list:
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        for k in ("rules", "items", "data", "records"):
            if isinstance(d.get(k), list):
                return d[k]
    return []


@dataclass
class DataStore:
    metadata: dict = field(default_factory=dict)
    rules: list = field(default_factory=list)
    variants: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    rule_sources: list = field(default_factory=list)
    rule_platforms: list = field(default_factory=list)
    rule_channels: list = field(default_factory=list)
    rule_examples: list = field(default_factory=list)
    semantic_rules: list = field(default_factory=list)
    semantic_rule_sources: list = field(default_factory=list)
    semantic_rule_examples: list = field(default_factory=list)
    manual_review_issues: list = field(default_factory=list)
    ad_classification_rules: list = field(default_factory=list)
    enforcement_cases: list = field(default_factory=list)
    test_cases: list = field(default_factory=list)

    # 索引
    rules_by_id: dict = field(default_factory=dict)
    sources_by_id: dict = field(default_factory=dict)
    variants_by_rule: dict = field(default_factory=dict)
    sources_by_rule: dict = field(default_factory=dict)
    platforms_by_rule: dict = field(default_factory=dict)
    semantic_by_id: dict = field(default_factory=dict)

    loaded_at: str = ""
    validation: dict = field(default_factory=dict)


_STORE: DataStore | None = None


def load_data() -> DataStore:
    global _STORE
    store = DataStore()
    d = config.COMPLIANCE_DIR

    store.metadata = _read_json(os.path.join(d, "metadata.json")) if os.path.exists(os.path.join(d, "metadata.json")) else {}
    store.rules = _as_list(_read_json(os.path.join(d, "rules.json")))
    store.variants = _as_list(_read_json(os.path.join(d, "rule_variants.json")))
    store.sources = _as_list(_read_json(os.path.join(d, "sources.json")))
    store.rule_sources = _as_list(_read_json(os.path.join(d, "rule_sources.json")))
    store.rule_platforms = _as_list(_read_json(os.path.join(d, "rule_platforms.json")))
    store.rule_channels = _as_list(_read_json(os.path.join(d, "rule_channels.json")))
    store.rule_examples = _as_list(_read_json(os.path.join(d, "rule_examples.json")))
    store.semantic_rules = _as_list(_read_json(os.path.join(d, "semantic_rules.json")))
    store.semantic_rule_sources = _as_list(_read_json(os.path.join(d, "semantic_rule_sources.json")))
    store.semantic_rule_examples = _as_list(_read_json(os.path.join(d, "semantic_rule_examples.json")))
    store.manual_review_issues = _as_list(_read_json(os.path.join(d, "manual_review_issues.json")))
    store.ad_classification_rules = _as_list(_read_json(os.path.join(d, "ad_classification_rules.json")))
    store.enforcement_cases = _as_list(_read_json(os.path.join(d, "enforcement_cases.json")))
    store.test_cases = _as_list(_read_json(os.path.join(d, "test_cases.json")))

    # 构建索引
    store.rules_by_id = {r["rule_id"]: r for r in store.rules if "rule_id" in r}
    store.sources_by_id = {s["source_id"]: s for s in store.sources if "source_id" in s}
    store.variants_by_rule = {}
    for v in store.variants:
        store.variants_by_rule.setdefault(v.get("rule_id"), []).append(v)
    store.sources_by_rule = {}
    for rs in store.rule_sources:
        store.sources_by_rule.setdefault(rs.get("rule_id"), []).append(rs.get("source_id"))
    store.platforms_by_rule = {}
    for p in store.rule_platforms:
        store.platforms_by_rule.setdefault(p.get("rule_id"), []).append(p)
    store.semantic_by_id = {s.get("semantic_rule_id"): s for s in store.semantic_rules}

    store.validation = validate_store(store)
    import datetime
    store.loaded_at = datetime.datetime.now().isoformat(timespec="seconds")

    _STORE = store
    return store


def get_store() -> DataStore:
    global _STORE
    if _STORE is None:
        _STORE = load_data()
    return _STORE


def reload() -> DataStore:
    return load_data()


def validate_store(store: DataStore) -> dict:
    """ID 引用完整性、必填字段、重复 ID 校验。返回结构化结果。"""
    errors = []
    warnings = []

    rule_ids = [r.get("rule_id") for r in store.rules]
    dup_rules = {rid for rid in rule_ids if rule_ids.count(rid) > 1}
    if dup_rules:
        errors.append(f"存在重复 rule_id：{sorted(dup_rules)}")

    src_ids = {s.get("source_id") for s in store.sources}
    for v in store.variants:
        rid = v.get("rule_id")
        if rid and rid not in store.rules_by_id:
            errors.append(f"variant {v.get('variant_id')} 引用了不存在的 rule_id：{rid}")
    for rs in store.rule_sources:
        rid = rs.get("rule_id")
        sid = rs.get("source_id")
        if rid and rid not in store.rules_by_id:
            errors.append(f"rule_sources 引用了不存在的 rule_id：{rid}")
        if sid and sid not in src_ids:
            errors.append(f"rule_sources 引用了不存在的 source_id：{sid}")
    for p in store.rule_platforms:
        rid = p.get("rule_id")
        if rid and rid not in store.rules_by_id:
            errors.append(f"rule_platforms 引用了不存在的 rule_id：{rid}")
    # 必填字段
    for r in store.rules:
        if not r.get("rule_id") or not r.get("rule_name"):
            errors.append(f"规则缺少 rule_id/rule_name：{r.get('rule_id')}")

    if not store.rules:
        errors.append("规则库为空，无法进行检测。")

    return {
        "valid": len(errors) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "rule_count": len(store.rules),
        "variant_count": len(store.variants),
        "source_count": len(store.sources),
        "semantic_count": len(store.semantic_rules),
    }

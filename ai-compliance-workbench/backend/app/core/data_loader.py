"""规则库加载与索引服务。

从 data/compliance 读取权威 JSON（只读），构建内存索引供检测引擎与 API 使用。
支持热重载、引用完整性校验、正则校验与质量警告。
"""
from __future__ import annotations

import datetime
import json
import os
import re
import threading
from dataclasses import dataclass, field
from typing import Any

from app.core import config

_REQUIRED_FILES = (
    "rules.json",
    "rule_variants.json",
    "sources.json",
    "rule_sources.json",
    "rule_platforms.json",
    "semantic_rules.json",
)


def _read_json(path: str) -> Any:
    if not os.path.exists(path):
        raise FileNotFoundError(f"未找到数据文件：{os.path.basename(path)}")
    try:
        with open(path, encoding="utf-8-sig") as file:
            return json.load(file)
    except json.JSONDecodeError as exc:
        filename = os.path.basename(path)
        raise ValueError(
            f"数据文件 {filename} 解析失败（第 {exc.lineno} 行，第 {exc.colno} 列）：{exc.msg}。"
        ) from exc


def _read_optional(directory: str, filename: str, default: Any) -> Any:
    path = os.path.join(directory, filename)
    return _read_json(path) if os.path.exists(path) else default


def _as_list(data: Any) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("rules", "items", "data", "records"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def _duplicates(values: list[Any]) -> set[Any]:
    seen: set[Any] = set()
    duplicate: set[Any] = set()
    for value in values:
        if not value:
            continue
        if value in seen:
            duplicate.add(value)
        seen.add(value)
    return duplicate


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
    visual_manual_checks: list = field(default_factory=list)
    risk_scoring: dict = field(default_factory=dict)

    rules_by_id: dict = field(default_factory=dict)
    sources_by_id: dict = field(default_factory=dict)
    variants_by_rule: dict = field(default_factory=dict)
    sources_by_rule: dict = field(default_factory=dict)
    platforms_by_rule: dict = field(default_factory=dict)
    examples_by_rule: dict = field(default_factory=dict)
    semantic_by_id: dict = field(default_factory=dict)
    semantic_sources_by_rule: dict = field(default_factory=dict)
    semantic_examples_by_rule: dict = field(default_factory=dict)

    loaded_at: str = ""
    validation: dict = field(default_factory=dict)


_STORE: DataStore | None = None
_LOCK = threading.RLock()


def load_data() -> DataStore:
    global _STORE
    with _LOCK:
        directory = str(config.COMPLIANCE_DIR)
        for filename in _REQUIRED_FILES:
            if not os.path.exists(os.path.join(directory, filename)):
                raise FileNotFoundError(f"规则库缺少必要文件：{filename}")

        store = DataStore()
        store.metadata = _read_optional(directory, "metadata.json", {})
        store.rules = _as_list(_read_json(os.path.join(directory, "rules.json")))
        store.variants = _as_list(_read_json(os.path.join(directory, "rule_variants.json")))
        store.sources = _as_list(_read_json(os.path.join(directory, "sources.json")))
        store.rule_sources = _as_list(_read_json(os.path.join(directory, "rule_sources.json")))
        store.rule_platforms = _as_list(_read_json(os.path.join(directory, "rule_platforms.json")))
        store.rule_channels = _as_list(_read_optional(directory, "rule_channels.json", []))
        store.rule_examples = _as_list(_read_optional(directory, "rule_examples.json", []))
        store.semantic_rules = _as_list(_read_json(os.path.join(directory, "semantic_rules.json")))
        store.semantic_rule_sources = _as_list(_read_optional(directory, "semantic_rule_sources.json", []))
        store.semantic_rule_examples = _as_list(_read_optional(directory, "semantic_rule_examples.json", []))
        store.manual_review_issues = _as_list(_read_optional(directory, "manual_review_issues.json", []))
        store.ad_classification_rules = _as_list(_read_optional(directory, "ad_classification_rules.json", []))
        store.enforcement_cases = _as_list(_read_optional(directory, "enforcement_cases.json", []))
        store.test_cases = _as_list(_read_optional(directory, "test_cases.json", []))
        store.visual_manual_checks = _as_list(_read_optional(directory, "visual_manual_checks.json", []))
        risk_scoring = _read_optional(directory, "risk_scoring.json", {})
        store.risk_scoring = risk_scoring if isinstance(risk_scoring, dict) else {}

        store.rules_by_id = {rule["rule_id"]: rule for rule in store.rules if rule.get("rule_id")}
        store.sources_by_id = {source["source_id"]: source for source in store.sources if source.get("source_id")}
        for variant in store.variants:
            store.variants_by_rule.setdefault(variant.get("rule_id"), []).append(variant)
        for relation in store.rule_sources:
            rule_id = relation.get("rule_id")
            source_id = relation.get("source_id")
            if rule_id and source_id:
                current = store.sources_by_rule.setdefault(rule_id, [])
                if source_id not in current:
                    current.append(source_id)
        for relation in store.rule_platforms:
            store.platforms_by_rule.setdefault(relation.get("rule_id"), []).append(relation)
        for example in store.rule_examples:
            store.examples_by_rule.setdefault(example.get("rule_id"), []).append(example)
        store.semantic_by_id = {
            rule.get("semantic_rule_id"): rule
            for rule in store.semantic_rules
            if rule.get("semantic_rule_id")
        }
        for relation in store.semantic_rule_sources:
            store.semantic_sources_by_rule.setdefault(relation.get("semantic_rule_id"), []).append(relation)
        for example in store.semantic_rule_examples:
            store.semantic_examples_by_rule.setdefault(example.get("semantic_rule_id"), []).append(example)

        store.loaded_at = datetime.datetime.now().isoformat(timespec="seconds")
        store.validation = validate_store(store)
        _STORE = store
        return store


def get_store() -> DataStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = load_data()
        return _STORE


def reload() -> DataStore:
    return load_data()


def validate_store(store: DataStore) -> dict:
    """执行结构、引用、正则与基础质量校验。"""
    errors: list[str] = []
    warnings: list[str] = []

    rule_ids = [rule.get("rule_id") for rule in store.rules]
    source_ids = [source.get("source_id") for source in store.sources]
    variant_ids = [variant.get("variant_id") for variant in store.variants]
    semantic_ids = [rule.get("semantic_rule_id") for rule in store.semantic_rules]

    for label, values in (
        ("rule_id", rule_ids),
        ("source_id", source_ids),
        ("variant_id", variant_ids),
        ("semantic_rule_id", semantic_ids),
    ):
        duplicate = _duplicates(values)
        if duplicate:
            errors.append(f"存在重复 {label}：{sorted(duplicate)}")

    rule_id_set = set(filter(None, rule_ids))
    source_id_set = set(filter(None, source_ids))
    semantic_id_set = set(filter(None, semantic_ids))

    for rule in store.rules:
        if not rule.get("rule_id") or not rule.get("rule_name"):
            errors.append(f"规则缺少 rule_id/rule_name：{rule.get('rule_id')}")
        if rule.get("risk_level") not in config.RISK_PRIORITY:
            errors.append(f"规则 {rule.get('rule_id')} 使用了非法 risk_level：{rule.get('risk_level')}")
        if str(rule.get("effective_status") or "active") == "pending_review":
            warnings.append(f"规则 {rule.get('rule_id')} 尚待人工复核。")

    for variant in store.variants:
        rule_id = variant.get("rule_id")
        if rule_id not in rule_id_set:
            errors.append(f"variant {variant.get('variant_id')} 引用了不存在的 rule_id：{rule_id}")
        pattern = variant.get("regex_pattern")
        if pattern:
            try:
                re.compile(pattern)
            except re.error as exc:
                errors.append(f"variant {variant.get('variant_id')} 正则无效：{exc}")
        if not variant.get("variant_text") and not pattern and variant.get("matching_method") != "semantic":
            warnings.append(f"variant {variant.get('variant_id')} 没有可执行的文本或正则。")

    for relation in store.rule_sources:
        rule_id, source_id = relation.get("rule_id"), relation.get("source_id")
        if rule_id not in rule_id_set:
            errors.append(f"rule_sources 引用了不存在的 rule_id：{rule_id}")
        if source_id not in source_id_set:
            errors.append(f"rule_sources 引用了不存在的 source_id：{source_id}")

    for relation in store.rule_platforms:
        rule_id, source_id = relation.get("rule_id"), relation.get("source_id")
        if rule_id not in rule_id_set:
            errors.append(f"rule_platforms 引用了不存在的 rule_id：{rule_id}")
        if source_id and source_id not in source_id_set:
            errors.append(f"rule_platforms 引用了不存在的 source_id：{source_id}")

    for example in store.rule_examples:
        if example.get("rule_id") not in rule_id_set:
            errors.append(f"rule_examples {example.get('example_id')} 引用了不存在的 rule_id：{example.get('rule_id')}")

    for relation in store.semantic_rule_sources:
        semantic_id, source_id = relation.get("semantic_rule_id"), relation.get("source_id")
        if semantic_id not in semantic_id_set:
            errors.append(f"semantic_rule_sources 引用了不存在的 semantic_rule_id：{semantic_id}")
        if source_id and source_id not in source_id_set:
            errors.append(f"semantic_rule_sources 引用了不存在的 source_id：{source_id}")

    for example in store.semantic_rule_examples:
        if example.get("semantic_rule_id") not in semantic_id_set:
            errors.append(
                f"semantic_rule_examples {example.get('semantic_example_id') or example.get('example_id')} "
                f"引用了不存在的 semantic_rule_id：{example.get('semantic_rule_id')}"
            )

    for rule in store.rules:
        if rule.get("risk_level") in {"critical", "high"} and not store.sources_by_rule.get(rule.get("rule_id")):
            warnings.append(f"高风险规则 {rule.get('rule_id')} 尚未关联正式来源。")

    if not store.rules:
        errors.append("规则库为空，无法进行检测。")
    if not store.variants:
        errors.append("表达变体为空，确定性检测无法运行。")
    if not store.semantic_rules:
        warnings.append("语义规则为空，系统只能进行确定性检测。")

    warning_total = len(warnings)
    pending_review_count = sum(
        1 for rule in store.rules
        if str(rule.get("effective_status") or "active") == "pending_review"
    )
    warning_preview = warnings[:100]
    if warning_total > len(warning_preview):
        warning_preview.append(f"另有 {warning_total - len(warning_preview)} 条警告未展开。")

    return {
        "valid": not errors,
        "error_count": len(errors),
        "warning_count": warning_total,
        "errors": errors,
        "warnings": warning_preview,
        "rule_count": len(store.rules),
        "variant_count": len(store.variants),
        "source_count": len(store.sources),
        "semantic_count": len(store.semantic_rules),
        "example_count": len(store.rule_examples),
        "platform_relation_count": len(store.rule_platforms),
        "test_case_count": len(store.test_cases),
        "visual_check_count": len(store.visual_manual_checks),
        "pending_review_count": pending_review_count,
    }

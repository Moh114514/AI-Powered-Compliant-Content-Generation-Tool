"""小红书专项违禁/敏感词匹配与语境分级。"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.core.text_normalize import map_span, normalize_text

VERSION = "v1.0"
SUPPORTED_RISK_LEVELS = {"违禁", "敏感"}

_NEGATION_MARKERS = (
    "不含", "并非", "不是", "不能", "不可", "不得", "不存在", "没有",
    "避免", "禁止", "切勿", "勿", "不代表", "不等于", "不承诺",
)
_NEUTRAL_MARKERS = (
    "科普", "原理", "属于", "须由", "需由", "需要由", "应由", "医师", "医生",
    "专业评估", "资质", "风险", "注意事项", "规范", "合规", "告知", "可能",
    "因人而异", "处方", "诊疗", "医疗行为", "监管", "说明",
)
_PROMOTIONAL_MARKERS = (
    "立即", "马上", "预约", "到店", "私信", "购买", "下单", "优惠", "折扣",
    "限时", "福利", "活动", "推荐", "种草", "体验", "效果", "改善", "变美",
    "年轻", "保证", "承诺", "全网", "排名", "第一", "首选",
)
_STRICT_DOMAINS = {"引流", "极限词", "功效承诺"}
_RISKY_SUPERLATIVES = (
    "最好", "最佳", "最高", "最低", "最强", "最大", "最小", "最优", "最先",
    "最早", "最晚", "最便宜", "最有效", "最安全", "最先进", "最专业",
    "最权威", "最值得", "最受欢迎", "最划算", "最年轻", "最美", "最白", "最瘦",
)
_SAFE_SUPERLATIVE_PREFIXES = (
    "最近", "最后", "最初", "最终", "至少", "至多", "最少", "最多", "最新版",
    "最重要", "最常见", "最基本", "最主要",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_records(records: Any, *, file_present: bool = True) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if not file_present:
        warnings.append("未找到 xhs_banned_words.json，小红书专项违禁词检测不可用。")
        return {
            "valid": True,
            "errors": errors,
            "warnings": warnings,
            "record_count": 0,
            "variant_count": 0,
            "unique_term_count": 0,
        }
    if not isinstance(records, list):
        errors.append("xhs_banned_words.json 顶层必须是数组。")
        records = []

    seen_ids: set[str] = set()
    terms: set[str] = set()
    variant_count = 0
    for index, item in enumerate(records, 1):
        if not isinstance(item, dict):
            errors.append(f"小红书词库第 {index} 条不是对象。")
            continue
        source_id = str(item.get("id") or "").strip()
        word = str(item.get("word") or "").strip()
        if not source_id or not word:
            errors.append(f"小红书词库第 {index} 条缺少 id/word。")
        elif source_id in seen_ids:
            errors.append(f"小红书词库存在重复 id：{source_id}")
        seen_ids.add(source_id)
        risk = str(item.get("risk_level") or "").strip()
        if risk not in SUPPORTED_RISK_LEVELS:
            errors.append(f"小红书词库 {source_id or index} 使用未知风险等级：{risk or '空'}")
        if not str(item.get("replacement") or "").strip():
            errors.append(f"小红书词库 {source_id or index} 缺少 replacement。")
        variants = item.get("variants") or []
        if not isinstance(variants, list):
            errors.append(f"小红书词库 {source_id or index} 的 variants 必须是数组。")
            variants = []
        variant_count += len(variants)
        for term in [word, *variants]:
            normalized = normalize_text(str(term or "").strip())[0]
            if normalized:
                terms.add(normalized)
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "record_count": len(records),
        "variant_count": variant_count,
        "unique_term_count": len(terms),
    }


def build_term_index(records: list[dict]) -> list[dict]:
    """按归一化词聚合重复来源，保留每条原始建议。"""
    grouped: dict[str, dict] = {}
    for record in records:
        canonical = str(record.get("word") or "").strip()
        for raw_term in [canonical, *(record.get("variants") or [])]:
            term = str(raw_term or "").strip()
            normalized = normalize_text(term)[0]
            if not normalized:
                continue
            entry = grouped.setdefault(normalized, {
                "normalized_term": normalized,
                "display_terms": [],
                "records": [],
            })
            if term not in entry["display_terms"]:
                entry["display_terms"].append(term)
            if record not in entry["records"]:
                entry["records"].append(record)
    return sorted(
        grouped.values(),
        key=lambda item: (-len(item["normalized_term"]), item["normalized_term"]),
    )


def is_xhs_scope(platform: str, content_type: str) -> bool:
    if str(platform or "").strip() == "小红书":
        return True
    try:
        from app.services.prompts.catalog import rule_mapping
        mapped_platforms, _ = rule_mapping(platform, content_type)
        return bool(mapped_platforms and "小红书" in mapped_platforms)
    except (RuntimeError, ValueError):
        return False


def _is_single_superlative_match(normalized_text: str, start: int, end: int, term: str) -> bool:
    if term not in {"最", "蕞", "zui", "zeui", "最d"}:
        return True
    window = normalized_text[max(0, start - 1):min(len(normalized_text), end + 6)]
    if any(safe in window for safe in _SAFE_SUPERLATIVE_PREFIXES):
        return False
    if term in {"最", "蕞"}:
        candidate = normalized_text[start:min(len(normalized_text), start + 6)]
        return any(candidate.startswith(item) for item in _RISKY_SUPERLATIVES)
    before = normalized_text[start - 1] if start > 0 else ""
    after = normalized_text[end] if end < len(normalized_text) else ""
    return not (before.isascii() and before.isalnum()) and not (after.isascii() and after.isalnum())


def _has_local_negation(text: str, start: int, end: int) -> bool:
    before = text[max(0, start - 7):start]
    after = text[end:min(len(text), end + 7)]
    return (
        any(before.endswith(marker) or marker in before[-4:] for marker in _NEGATION_MARKERS)
        or any(after.startswith(marker) or marker in after[:5] for marker in ("并不存在", "不存在", "并非", "不成立"))
    )


def _classify_context(
    original: str,
    start: int,
    end: int,
    domains: list[str],
    source_risks: list[str],
) -> tuple[str, str, list[str], bool]:
    window = (
        original[max(0, start - 32):start]
        + original[end:min(len(original), end + 32)]
    )
    if _has_local_negation(original, start, end):
        return "neutral", "medium", ["mandatory_human_review"], True
    has_neutral = any(marker in window for marker in _NEUTRAL_MARKERS)
    has_promotional = any(marker in window for marker in _PROMOTIONAL_MARKERS)
    if has_neutral and not has_promotional:
        return "neutral", "medium", ["mandatory_human_review"], True
    if "违禁" not in source_risks:
        return (
            "promotional" if has_promotional else "ambiguous",
            "medium",
            ["mandatory_human_review"],
            True,
        )
    if has_promotional or any(domain in _STRICT_DOMAINS for domain in domains):
        return "promotional", "high", ["block"], False
    return "ambiguous", "medium", ["mandatory_human_review"], True


def _dedupe_overlaps(candidates: list[dict]) -> list[dict]:
    """同区间合并，交叠区间仅保留最长命中。"""
    by_span: dict[tuple[int, int], dict] = {}
    for item in candidates:
        key = (item["norm_start"], item["norm_end"])
        current = by_span.get(key)
        if not current:
            by_span[key] = item
            continue
        existing_ids = {record.get("id") for record in current["records"]}
        current["records"].extend(
            record for record in item["records"] if record.get("id") not in existing_ids
        )

    selected: list[dict] = []
    for item in sorted(
        by_span.values(),
        key=lambda value: (
            -(value["norm_end"] - value["norm_start"]),
            value["norm_start"],
            value["normalized_term"],
        ),
    ):
        if any(
            item["norm_start"] < kept["norm_end"] and item["norm_end"] > kept["norm_start"]
            for kept in selected
        ):
            continue
        selected.append(item)
    return sorted(selected, key=lambda value: (value["norm_start"], value["norm_end"]))


def match_banned_words(
    *,
    original: str,
    normalized_text: str,
    index_map: list[int],
    terms: list[dict],
    platform: str,
    content_type: str,
) -> tuple[list[dict], list[dict]]:
    if not terms or not is_xhs_scope(platform, content_type):
        return [], []

    candidates: list[dict] = []
    for term_entry in terms:
        needle = term_entry["normalized_term"]
        offset = 0
        while True:
            start = normalized_text.find(needle, offset)
            if start < 0:
                break
            end = start + len(needle)
            offset = end
            if _is_single_superlative_match(normalized_text, start, end, needle):
                candidates.append({
                    **term_entry,
                    "norm_start": start,
                    "norm_end": end,
                })

    hits: list[dict] = []
    highlights: list[dict] = []
    for ordinal, candidate in enumerate(_dedupe_overlaps(candidates), 1):
        start, end = map_span(index_map, candidate["norm_start"], candidate["norm_end"])
        records = candidate["records"]
        source_ids = list(dict.fromkeys(str(item.get("id") or "") for item in records if item.get("id")))
        canonical_words = list(dict.fromkeys(str(item.get("word") or "") for item in records if item.get("word")))
        domains = list(dict.fromkeys(str(item.get("domain") or "") for item in records if item.get("domain")))
        replacements = list(dict.fromkeys(
            str(item.get("replacement") or "").strip()
            for item in records
            if str(item.get("replacement") or "").strip()
        ))
        reasons = list(dict.fromkeys(
            str(item.get("reason") or "").strip()
            for item in records
            if str(item.get("reason") or "").strip()
        ))
        sources = list(dict.fromkeys(
            str(item.get("source") or "").strip()
            for item in records
            if str(item.get("source") or "").strip()
        ))
        source_risks = list(dict.fromkeys(
            str(item.get("risk_level") or "")
            for item in records
            if item.get("risk_level")
        ))
        context, risk_level, actions, requires_review = _classify_context(
            original, start, end, domains, source_risks
        )
        hit_id = f"xhs-bw:{'+'.join(source_ids)}:{start}:{end}"
        matched_text = original[start:end]
        hit = {
            "hit_id": hit_id,
            "matched_text": matched_text,
            "canonical_word": " / ".join(canonical_words),
            "start": start,
            "end": end,
            "domain": " / ".join(domains),
            "risk_level": risk_level,
            "source_risk_levels": source_risks,
            "reason": "；".join(reasons),
            "replacements": replacements,
            "sources": sources,
            "source_ids": source_ids,
            "context_classification": context,
            "requires_review": requires_review,
            "system_action": actions,
        }
        hits.append(hit)
        highlights.append({
            "rule_id": hit_id,
            "hit_id": hit_id,
            "variant_id": candidate["normalized_term"],
            "matched_text": matched_text,
            "start_index": start,
            "end_index": end,
            "matching_method": "xhs_banned_word",
            "source_type": "xhs_banned_word",
            "ordinal": ordinal,
        })
    return hits, highlights


def as_rewrite_rules(hits: list[dict]) -> list[dict]:
    """把专项命中转换为现有 Provider 可消费的改写约束。"""
    output: list[dict] = []
    for hit in hits:
        output.append({
            "rule_id": "/".join(hit.get("source_ids") or ["XHS-BW"]),
            "rule_name": f"小红书专项词：{hit.get('canonical_word', '')}",
            "replacement_strategy": hit.get("replacements") or [],
            "auto_rewrite_allowed": True,
            "spans": [{
                "start_index": hit.get("start", 0),
                "end_index": hit.get("end", 0),
            }],
        })
    return output


def prompt_guardrail(records: list[dict], limit: int = 1400) -> str:
    if not records or limit <= 0:
        return ""
    lines = [
        "【小红书专项词库约束】",
        "避免使用下列平台违禁或敏感表达及其变体；不得用谐音、拆字或符号规避。生成后系统仍会执行完整词库检测。",
    ]
    for item in records:
        word = str(item.get("word") or "").strip()
        replacement = str(item.get("replacement") or "").strip()
        line = f"- {word} → {replacement}"
        if sum(len(value) + 1 for value in lines) + len(line) > limit:
            lines.append("- 其余词条及全部变体由生成后的完整检测执行。")
            break
        lines.append(line)
    return "\n".join(lines)

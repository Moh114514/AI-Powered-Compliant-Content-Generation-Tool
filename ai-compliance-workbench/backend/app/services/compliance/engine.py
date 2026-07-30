"""合规检测引擎。

流程：文本标准化 → 适用规则筛选 → 确定性检测 → 语义检测 → 风险聚合。
引擎只负责判定和报告组装；规则库保持只读，模型失败时确定性检测仍可用。
"""
from __future__ import annotations

import time
from typing import Any

from app.core import config
from app.core.matching import match_variant
from app.core.text_normalize import map_span, normalize_text
from app.services.compliance.banned_words import as_rewrite_rules, match_banned_words

_DISABLED_STATUSES = {"suspended", "superseded", "abolished", "inactive", "disabled"}


def _norm_actions(value: Any) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
    else:
        raw = str(value or "").strip()
        if not raw:
            return ["pass"]
        for delimiter in (";", "；", ",", "，", "|"):
            raw = raw.replace(delimiter, " ")
        items = [item for item in raw.split() if item]

    known = set(config.ACTION_PRIORITY)
    normalized: list[str] = []
    legacy_letters = {
        "b": "block", "e": "request_evidence", "o": "pass", "c": "warning",
        "k": "mandatory_human_review", "l": "request_qualification",
        "q": "request_qualification", "r": "request_evidence", "w": "warning",
        "n": "pass", "m": "mandatory_human_review",
    }
    for item in items:
        if item in known:
            normalized.append(item)
        elif len(item) > 1 and all(char in legacy_letters for char in item):
            normalized.extend(legacy_letters[char] for char in item)
        elif item in legacy_letters:
            normalized.append(legacy_letters[item])
        else:
            normalized.append("mandatory_human_review")
    return list(dict.fromkeys(normalized)) or ["pass"]


def _recommend_contact(rule: dict) -> str:
    category = str(rule.get("category_name") or "")
    if any(key in category for key in ("资质", "医生", "机构", "诊断", "器械", "药品")):
        return "法务或医疗专业人员"
    if any(key in category for key in ("数据", "排名", "价格", "优惠")):
        return "法务或项目负责人"
    if any(key in category for key in ("广告", "平台", "隐私", "肖像")):
        return "法务"
    if "伪科学" in category:
        return "医疗专业人员"
    return "法务或项目负责人"


def _rule_enabled(rule: dict) -> bool:
    return str(rule.get("effective_status") or "active").lower() not in _DISABLED_STATUSES


def _filter_applicable_rules(store, platform: str, content_type: str) -> tuple[list[dict], bool]:
    """返回适用规则与平台专项覆盖不足标记。"""
    from app.services.prompts.catalog import rule_mapping
    mapped_platforms, mapped_content_types = rule_mapping(platform, content_type)
    if mapped_platforms is None:
        mapped_platforms = config.PLATFORM_TO_RULE_PLATFORM.get(platform, [])
    if mapped_content_types is None:
        mapped_content_types = config.map_content_type_to_rule_ct(content_type)
    applicable: list[dict] = []
    platform_scoped_total = 0
    platform_scoped_matched = 0

    for rule in store.rules:
        if not _rule_enabled(rule):
            continue
        rule_id = rule.get("rule_id")
        entries = store.platforms_by_rule.get(rule_id, [])
        if not entries:
            applicable.append(rule)
            continue

        enabled_entries = [
            entry for entry in entries
            if str(entry.get("effective_status") or "active").lower() not in _DISABLED_STATUSES
        ]
        if not enabled_entries:
            continue
        platform_entries = [entry for entry in enabled_entries if entry.get("platform") in mapped_platforms]
        if platform_entries:
            platform_scoped_total += 1

        matched = False
        for entry in platform_entries:
            entry_content_type = str(entry.get("content_type") or "").strip()
            if not mapped_content_types or not entry_content_type or entry_content_type in mapped_content_types:
                matched = True
                break
        if matched:
            applicable.append(rule)
            platform_scoped_matched += 1

    incomplete = bool(mapped_platforms) and platform_scoped_total == 0
    if platform_scoped_total > 0 and platform_scoped_matched == 0:
        incomplete = True
    return applicable, incomplete


def get_applicable_rules(store, platform: str, content_type: str) -> tuple[list[dict], bool]:
    """Public selector shared by generation guardrails and the detection engine."""
    return _filter_applicable_rules(store, platform, content_type)


def _dedup_matches(matches: list[dict]) -> list[dict]:
    """仅去除完全重复命中，保留不同规则的重叠命中。"""
    unique: dict[tuple, dict] = {}
    for item in matches:
        key = (
            item.get("rule_id"), item.get("variant_id"),
            item.get("norm_start"), item.get("norm_end"),
        )
        unique.setdefault(key, item)
    return sorted(
        unique.values(),
        key=lambda item: (item.get("norm_start", 0), item.get("norm_end", 0), item.get("rule_id") or ""),
    )


def _normalize_semantic_findings(
    findings: Any,
    semantic_by_id: dict[str, dict],
    original_text: str = "",
) -> tuple[list[dict], list[str]]:
    if not isinstance(findings, list):
        return [], []
    grouped: dict[str, dict] = {}
    unknown_ids: list[str] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        semantic_id = str(finding.get("semantic_rule_id") or "")
        canonical = semantic_by_id.get(semantic_id)
        if not canonical:
            if semantic_id:
                unknown_ids.append(semantic_id)
            continue
        risk_level = str(
            canonical.get("expected_risk_level")
            or finding.get("risk_level")
            or "medium"
        ).lower()
        if risk_level not in config.RISK_PRIORITY:
            risk_level = "medium"
        actions = _norm_actions(canonical.get("system_action") or finding.get("system_action"))
        manual_review = bool(
            finding.get(
                "manual_review",
                risk_level in {"critical", "high"} or "mandatory_human_review" in actions,
            )
        )
        if manual_review and actions == ["pass"]:
            actions = ["mandatory_human_review"]
        matched_text = str(finding.get("matched_text") or "").strip()
        risk_reason = str(finding.get("risk_reason") or "检测到需要结合上下文判断的语义风险。")
        existing = grouped.get(semantic_id)
        if existing is None:
            existing = {
                **finding,
                "semantic_rule_id": semantic_id,
                "semantic_rule_name": canonical.get("semantic_rule_name") or finding.get("semantic_rule_name") or "",
                "risk_level": risk_level,
                "manual_review": manual_review,
                "system_action": actions,
                "risk_reason": risk_reason,
                "matched_text": matched_text,
                "matched_texts": [matched_text] if matched_text else [],
                "_risk_reasons": [risk_reason],
            }
            grouped[semantic_id] = existing
        else:
            if matched_text and matched_text not in existing["matched_texts"]:
                existing["matched_texts"].append(matched_text)
            if risk_reason not in existing["_risk_reasons"]:
                existing["_risk_reasons"].append(risk_reason)
            if config.RISK_PRIORITY.get(risk_level, 0) > config.RISK_PRIORITY.get(existing["risk_level"], 0):
                existing["risk_level"] = risk_level
            existing["manual_review"] = bool(existing["manual_review"] or manual_review)
            existing["system_action"] = list(dict.fromkeys([*existing["system_action"], *actions]))

    normalized: list[dict] = []
    for finding in grouped.values():
        spans: list[dict] = []
        for matched_text in finding["matched_texts"]:
            offset = 0
            while matched_text:
                start = original_text.find(matched_text, offset)
                if start < 0:
                    break
                end = start + len(matched_text)
                spans.append({"start": start, "end": end, "matched_text": matched_text})
                offset = end
        spans.sort(key=lambda span: (span["start"], span["end"]))
        finding["spans"] = spans
        finding["occurrence_count"] = len(spans) or max(1, len(finding["matched_texts"]))
        finding["risk_reason"] = "；".join(finding.pop("_risk_reasons"))
        normalized.append(finding)
    return normalized, list(dict.fromkeys(unknown_ids))


def _highest_risk(
    matched_rules: list[dict],
    semantic_findings: list[dict],
    banned_word_hits: list[dict] | None = None,
) -> str:
    levels = [item.get("risk_level", "none") for item in matched_rules]
    levels.extend(item.get("risk_level", "none") for item in semantic_findings)
    levels.extend(item.get("risk_level", "none") for item in (banned_word_hits or []))
    return max(levels or ["none"], key=lambda level: config.RISK_PRIORITY.get(level, 0))


def _highest_review_level(matched_rules: list[dict]) -> str:
    levels = [item.get("review_level") for item in matched_rules if item.get("review_level")]
    return max(levels, key=lambda level: config.REVIEW_PRIORITY.get(level, 0)) if levels else ""


def _count_marked_occurrences(highlights: list[dict]) -> int:
    """Count visible non-overlapping annotations while preserving all risk records."""
    selected: list[tuple[int, int]] = []
    ordered = sorted(
        highlights,
        key=lambda item: (
            -config.RISK_PRIORITY.get(str(item.get("risk_level") or "none"), 0),
            -(int(item.get("end_index") or 0) - int(item.get("start_index") or 0)),
            int(item.get("start_index") or 0),
        ),
    )
    for highlight in ordered:
        start = int(highlight.get("start_index") or 0)
        end = int(highlight.get("end_index") or start)
        if end <= start:
            continue
        if any(start < kept_end and end > kept_start for kept_start, kept_end in selected):
            continue
        selected.append((start, end))
    return len(selected)


def run_compliance_check(
    *,
    text: str,
    platform: str,
    content_type: str,
    brand: str | None = None,
    publisher_identity: str | None = None,
    business_domain: str | None = None,
    content_legal_nature: str | None = None,
    is_paid_ad: bool = False,
    context_note: str | None = None,
    store=None,
    provider=None,
    settings: dict | None = None,
) -> dict:
    total_started = time.perf_counter()
    store = store or _store()
    settings = settings or {}
    original = text or ""
    if not original.strip():
        raise ValueError("待检测文本不能为空。")

    enable_keyword = bool(settings.get("enable_keyword_detection", True))
    enable_regex = bool(settings.get("enable_regex_detection", True))
    enable_semantic = bool(settings.get("enable_semantic_detection", True))
    auto_revision = bool(settings.get("auto_generate_revision", False))

    deterministic_started = time.perf_counter()
    normalized_text, index_map = normalize_text(original)
    applicable_rules, platform_incomplete = _filter_applicable_rules(store, platform, content_type)

    raw_matches: list[dict] = []
    for rule in applicable_rules:
        rule_id = rule.get("rule_id")
        for variant in store.variants_by_rule.get(rule_id, []):
            method = str(variant.get("matching_method") or "contains").lower()
            if method == "semantic":
                continue
            is_regex = method == "regex" or bool(variant.get("regex_pattern"))
            if is_regex and not enable_regex:
                continue
            if not is_regex and not enable_keyword:
                continue
            for start, end, matched_text in match_variant(normalized_text, variant):
                raw_matches.append({
                    "rule_id": rule_id,
                    "variant_id": variant.get("variant_id"),
                    "norm_start": start,
                    "norm_end": end,
                    "matched_norm": matched_text,
                    "method": "regex" if is_regex else method,
                })

    matches = _dedup_matches(raw_matches)
    grouped: dict[str, dict] = {}
    highlights: list[dict] = []
    for match in matches:
        rule_id = match["rule_id"]
        rule = store.rules_by_id.get(rule_id, {})
        original_start, original_end = map_span(index_map, match["norm_start"], match["norm_end"])
        matched_text = original[original_start:original_end]
        span = {
            "rule_id": rule_id,
            "variant_id": match.get("variant_id"),
            "matched_text": matched_text,
            "start_index": original_start,
            "end_index": original_end,
            "matching_method": match.get("method"),
            "risk_level": rule.get("risk_level", "low"),
        }
        highlights.append(span)

        if rule_id not in grouped:
            source_ids = list(dict.fromkeys(store.sources_by_rule.get(rule_id, []) or []))
            replacement = rule.get("replacement_strategy") or ""
            replacement_list = [part.strip() for part in str(replacement).replace("；", ";").split(";") if part.strip()]
            effective_status = str(rule.get("effective_status") or "active")
            actions = _norm_actions(rule.get("system_action"))
            pending_review = effective_status == "pending_review"
            if pending_review and "mandatory_human_review" not in actions:
                actions.append("mandatory_human_review")
            grouped[rule_id] = {
                "rule_id": rule_id,
                "rule_name": rule.get("rule_name", ""),
                "variant_id": match.get("variant_id"),
                "matched_text": matched_text,
                "start_index": original_start,
                "end_index": original_end,
                "matching_method": match.get("method"),
                "risk_level": rule.get("risk_level", "low"),
                "legal_conclusion": rule.get("legal_conclusion", ""),
                "system_action": actions,
                "risk_reason": rule.get("rule_description", ""),
                "replacement_strategy": replacement_list,
                "source_ids": source_ids,
                "source_names": [store.sources_by_id.get(source_id, {}).get("source_name", "") for source_id in source_ids],
                "category_name": rule.get("category_name", ""),
                "prohibited_context": rule.get("prohibited_context", ""),
                "allowed_context": rule.get("allowed_context", ""),
                "evidence_requirement": rule.get("evidence_requirement", ""),
                "qualification_requirement": rule.get("qualification_requirement", ""),
                "auto_rewrite_allowed": bool(rule.get("auto_rewrite_allowed", False)),
                "manual_review_required": bool(rule.get("manual_review_required", False) or pending_review),
                "review_level": rule.get("review_level", ""),
                "effective_status": effective_status,
                "occurrence_count": 1,
                "spans": [span],
            }
        else:
            grouped[rule_id]["spans"].append(span)
            grouped[rule_id]["occurrence_count"] = len(grouped[rule_id]["spans"])

    matched_rules = list(grouped.values())
    banned_word_hits: list[dict] = []
    banned_highlights: list[dict] = []
    if enable_keyword:
        banned_word_hits, banned_highlights = match_banned_words(
            original=original,
            normalized_text=normalized_text,
            index_map=index_map,
            terms=store.xhs_banned_terms,
            platform=platform,
            content_type=content_type,
        )
        highlights.extend(banned_highlights)

    deterministic_ms = round((time.perf_counter() - deterministic_started) * 1000, 2)
    semantic_findings: list[dict] = []
    semantic_ms = 0.0
    semantic_failed = False
    semantic_failure_reason = ""
    needs_manual_review = False
    manual_review_reason = ""
    if enable_semantic and provider is not None:
        mapped_platforms = config.PLATFORM_TO_RULE_PLATFORM.get(platform, [])
        semantic_rules = []
        for semantic_rule in store.semantic_rules:
            applicable_platform = str(semantic_rule.get("applicable_platform") or "")
            if not applicable_platform or any(mapped in applicable_platform for mapped in mapped_platforms):
                semantic_rules.append(semantic_rule)
        try:
            semantic_started = time.perf_counter()
            semantic_result = provider.semantic_check(
                text=original,
                platform=platform,
                content_type=content_type,
                semantic_rules=semantic_rules,
                matched_rules=matched_rules,
            ) or {}
            semantic_ms = round((time.perf_counter() - semantic_started) * 1000, 2)
            semantic_catalog = store.semantic_by_id or {
                str(item.get("semantic_rule_id") or ""): item
                for item in store.semantic_rules
                if item.get("semantic_rule_id")
            }
            semantic_findings, unknown_semantic_ids = _normalize_semantic_findings(
                semantic_result.get("semantic_findings"),
                semantic_catalog,
                original,
            )
            needs_manual_review = bool(semantic_result.get("needs_manual_review", False))
            manual_review_reason = str(semantic_result.get("manual_review_reason") or "")
            semantic_failed = bool(semantic_result.get("analysis_failed", False))
            semantic_failure_reason = str(semantic_result.get("failure_reason") or "")
            if unknown_semantic_ids:
                semantic_failed = True
                unknown_text = "、".join(unknown_semantic_ids)
                semantic_failure_reason = (
                    f"模型返回了规则库中不存在的语义规则 ID：{unknown_text}。"
                )
        except Exception as exc:
            semantic_ms = round((time.perf_counter() - semantic_started) * 1000, 2) if "semantic_started" in locals() else 0.0
            semantic_failed = True
            semantic_failure_reason = f"语义检测失败：{exc}"

    overall_risk = _highest_risk(matched_rules, semantic_findings, banned_word_hits)
    review_level = _highest_review_level(matched_rules)

    actions: list[str] = []
    for matched_rule in matched_rules:
        actions.extend(matched_rule.get("system_action", []))
    for finding in semantic_findings:
        actions.extend(finding.get("system_action", []))
    for hit in banned_word_hits:
        actions.extend(hit.get("system_action", []))
    if needs_manual_review or semantic_failed:
        actions.append("mandatory_human_review")
    actions = list(dict.fromkeys(actions))
    top_action = max(actions, key=lambda action: config.ACTION_PRIORITY.get(action, 0)) if actions else "pass"
    publish_recommendation = config.ACTION_TO_RECOMMENDATION.get(top_action, "manual_review")

    manual_review_required = (
        any(item.get("manual_review_required") for item in matched_rules)
        or any(item.get("manual_review") for item in semantic_findings)
        or any(item.get("requires_review") for item in banned_word_hits)
        or needs_manual_review
        or semantic_failed
        or "mandatory_human_review" in actions
    )

    platform_findings = []
    if platform_incomplete:
        platform_findings.append({
            "type": "platform_coverage_incomplete",
            "risk_level": "low",
            "message": "当前平台或内容类型的专项规则覆盖可能不完整，已继续使用通用法律规则检测。",
        })

    manual_review_issues = _build_review_issues(
        matched_rules=matched_rules,
        semantic_findings=semantic_findings,
        needs_manual_review=needs_manual_review,
        reason=manual_review_reason,
        semantic_failed=semantic_failed,
        semantic_failure_reason=semantic_failure_reason,
        banned_word_hits=banned_word_hits,
    )

    suggested_revision = ""
    rewrite_ms = 0.0
    if auto_revision and provider is not None and (matched_rules or banned_word_hits):
        try:
            rewrite_started = time.perf_counter()
            revision = provider.rewrite(
                text=original,
                matched_rules=[*matched_rules, *as_rewrite_rules(banned_word_hits)],
                platform=platform,
                content_type=content_type,
            ) or {}
            rewrite_ms = round((time.perf_counter() - rewrite_started) * 1000, 2)
            suggested_revision = str(revision.get("suggested_revision") or "")
        except Exception:
            rewrite_ms = round((time.perf_counter() - rewrite_started) * 1000, 2) if "rewrite_started" in locals() else 0.0
            suggested_revision = ""

    result = {
        "input_text": original,
        "normalized_text": normalized_text,
        "platform": platform,
        "content_type": content_type,
        "brand": brand,
        "publisher_identity": publisher_identity,
        "business_domain": business_domain,
        "content_legal_nature": content_legal_nature,
        "is_paid_ad": is_paid_ad,
        "context_note": context_note,
        "overall_risk_level": overall_risk,
        "review_level": review_level,
        "publish_recommendation": publish_recommendation,
        "manual_review_required": manual_review_required,
        "matched_rules": matched_rules,
        "banned_word_hits": banned_word_hits,
        "semantic_findings": semantic_findings,
        "semantic_analysis_failed": semantic_failed,
        "semantic_failure_reason": semantic_failure_reason,
        "platform_findings": platform_findings,
        "manual_review_issues": manual_review_issues,
        "suggested_revision": suggested_revision,
        "review_summary": "",
        "disclaimer": config.DISCLAIMER,
        "highlights": highlights,
        "offset_encoding": "unicode_codepoint",
        "platform_rules_incomplete": platform_incomplete,
        "stats": {
            "applicable_rule_count": len(applicable_rules),
            "matched_rule_count": len(matched_rules),
            "matched_span_count": len(highlights),
            "unique_risk_count": (
                len(matched_rules) + len(banned_word_hits) + len(semantic_findings)
            ),
            "marked_occurrence_count": _count_marked_occurrences(highlights),
            "banned_word_hit_count": len(banned_word_hits),
            "banned_word_unique_count": len(banned_word_hits),
            "banned_word_occurrence_count": sum(
                int(hit.get("occurrence_count") or 1) for hit in banned_word_hits
            ),
            "semantic_finding_count": len(semantic_findings),
        },
        "timings_ms": {
            "deterministic": deterministic_ms,
            "semantic": semantic_ms,
            "rewrite": rewrite_ms,
            "total": round((time.perf_counter() - total_started) * 1000, 2),
        },
    }
    result["review_summary"] = _build_review_summary(result)
    return result


def _build_review_issues(
    *,
    matched_rules: list[dict],
    semantic_findings: list[dict],
    needs_manual_review: bool,
    reason: str,
    semantic_failed: bool,
    semantic_failure_reason: str,
    banned_word_hits: list[dict] | None = None,
) -> list[dict]:
    issues: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for matched_rule in matched_rules:
        if not (
            matched_rule.get("manual_review_required")
            or "mandatory_human_review" in matched_rule.get("system_action", [])
        ):
            continue
        question = f"请确认“{matched_rule.get('matched_text', '')}”是否符合当前发布场景的合规要求。"
        evidence = matched_rule.get("evidence_requirement") or matched_rule.get("qualification_requirement") or ""
        key = (matched_rule.get("rule_id", ""), question)
        if key in seen:
            continue
        seen.add(key)
        issues.append({
            "issue_type": matched_rule.get("category_name", ""),
            "rule_id": matched_rule.get("rule_id", ""),
            "question": question,
            "required_evidence": evidence,
            "recommended_contact": _recommend_contact(matched_rule),
        })

    for finding in semantic_findings:
        if not finding.get("manual_review"):
            continue
        question = finding.get("risk_reason") or "请确认该语义风险在当前上下文中是否成立。"
        key = (finding.get("semantic_rule_id", ""), question)
        if key in seen:
            continue
        seen.add(key)
        issues.append({
            "issue_type": "语义风险",
            "semantic_rule_id": finding.get("semantic_rule_id", ""),
            "question": question,
            "required_evidence": finding.get("required_evidence", ""),
            "recommended_contact": "法务或医疗专业人员",
        })

    for hit in banned_word_hits or []:
        if not hit.get("requires_review"):
            continue
        question = (
            f"请确认小红书专项词“{hit.get('matched_text', '')}”在当前语境下是否属于"
            "科普、否定、风险告知或具备资质的合规说明。"
        )
        key = (hit.get("hit_id", ""), question)
        if key in seen:
            continue
        seen.add(key)
        issues.append({
            "issue_type": "小红书违禁/敏感词",
            "banned_word_hit_id": hit.get("hit_id", ""),
            "question": question,
            "required_evidence": "",
            "recommended_contact": "法务或平台运营负责人",
        })

    if needs_manual_review and not semantic_findings:
        issues.append({
            "issue_type": "语义风险",
            "question": reason or "文案存在需要结合上下文判断的语义风险。",
            "required_evidence": "",
            "recommended_contact": "法务或医疗专业人员",
        })
    if semantic_failed:
        issues.append({
            "issue_type": "检测能力降级",
            "question": semantic_failure_reason or "语义检测未成功完成，请勿仅依据关键词结果直接发布。",
            "required_evidence": "",
            "recommended_contact": "法务或系统维护人员",
        })
    return issues


def _build_review_summary(result: dict) -> str:
    risk_label = config.RISK_LABELS.get(result.get("overall_risk_level"), result.get("overall_risk_level"))
    recommendation_label = {
        "block": "暂停发布",
        "manual_review": "人工复核后发布",
        "request_evidence": "补充材料后发布",
        "warning": "修改后发布",
        "pass": "未发现明显风险，仍需核验事实材料",
    }.get(result.get("publish_recommendation"), result.get("publish_recommendation"))
    lines = [
        "【医美文案人工复核摘要】",
        f"平台：{result.get('platform', '')}",
        f"内容类型：{result.get('content_type', '')}",
        f"总体风险：{risk_label}",
        f"处理建议：{recommendation_label}",
        "",
    ]
    issues = result.get("manual_review_issues") or []
    if issues:
        lines.append("需要确认：")
        for index, issue in enumerate(issues, 1):
            evidence = issue.get("required_evidence")
            suffix = f"（需材料：{evidence}）" if evidence else ""
            lines.append(f"{index}. {issue.get('question', '')}{suffix}")
        lines.append("")
    rules = result.get("matched_rules") or []
    if rules:
        lines.append("命中规则：")
        lines.extend(f"- {rule.get('rule_id')} {rule.get('rule_name')}" for rule in rules)
        lines.append("")
    banned_hits = result.get("banned_word_hits") or []
    if banned_hits:
        lines.append("小红书专项词：")
        lines.extend(
            f"- {hit.get('matched_text')}：{'；'.join(hit.get('replacements') or []) or '请删除或改写'}"
            for hit in banned_hits
        )
        lines.append("")
    contacts = sorted({
        issue.get("recommended_contact")
        for issue in issues
        if issue.get("recommended_contact")
    })
    if contacts:
        lines.append("建议对接：" + "、".join(contacts) + "。")
    lines.extend(["", "本工具不记录复核结果。", config.DISCLAIMER])
    return "\n".join(lines)


def _store():
    from app.core.data_loader import get_store
    return get_store()

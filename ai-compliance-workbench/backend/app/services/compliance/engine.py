"""合规检测引擎：五步流程 + 风险聚合。
文本标准化 → 适用规则筛选 → 确定性检测 → 语义检测 → 风险聚合。
返回结构遵循规范第十六节（并附带前端高亮所需的 spans 字段）。
"""
from typing import Any
from app.core import config
from app.core.text_normalize import normalize_text, map_span
from app.core.matching import match_variant


def _norm_actions(val: Any) -> list[str]:
    if isinstance(val, list):
        return [str(x) for x in val]
    s = str(val or "")
    if s in config.ACTION_TO_RECOMMENDATION:
        return [s]
    # 兼容旧式单字母拼接
    letter_map = {
        "b": "block", "e": "request_evidence", "o": "pass", "c": "warning",
        "k": "mandatory_human_review", "l": "request_qualification", "q": "request_qualification",
        "r": "request_evidence", "w": "warning", "n": "pass", "m": "mandatory_human_review",
    }
    if len(s) > 1 and all(c in letter_map for c in s):
        return [letter_map[c] for c in s]
    return [s] if s else ["pass"]


def _recommend_contact(rule: dict) -> str:
    cat = rule.get("category_name", "") or ""
    if "资质" in cat or "医生" in cat or "机构" in cat:
        return "法务或医疗专业人员"
    if "数据" in cat or "排名" in cat:
        return "项目负责人"
    if "广告" in cat:
        return "法务"
    if "伪科学" in cat:
        return "医疗专业人员"
    return "法务或项目负责人"


def _filter_applicable_rules(store, platform: str, content_type: str) -> tuple[list[dict], bool]:
    """返回 (适用规则列表, 平台专项规则是否覆盖不完整)。"""
    mapped_platforms = config.PLATFORM_TO_RULE_PLATFORM.get(platform, [])
    mapped_cts = config.map_content_type_to_rule_ct(content_type)
    applicable = []
    restricted_matched = 0
    for rule in store.rules:
        rid = rule.get("rule_id")
        entries = store.platforms_by_rule.get(rid)
        if not entries:
            applicable.append(rule)  # 无平台限制，通用规则
            continue
        ok = False
        for e in entries:
            ep = e.get("platform")
            ect = e.get("content_type") or ""
            if ep in mapped_platforms:
                if not ect or ect in mapped_cts:
                    ok = True
                    break
        if ok:
            applicable.append(rule)
            restricted_matched += 1
    # 平台专项覆盖：若映射到的规则平台在库中存在、但本次无专项规则命中 -> 不完整
    platform_rules_incomplete = bool(mapped_platforms) and restricted_matched == 0
    return applicable, platform_rules_incomplete


def _dedup_spans(spans: list[dict]) -> list[dict]:
    """去除重叠区间（保留先出现者）。spans 含 norm_start/norm_end。"""
    spans_sorted = sorted(spans, key=lambda x: (x["norm_start"], -(x["norm_end"] - x["norm_start"])))
    result = []
    last_end = -1
    for s in spans_sorted:
        if s["norm_start"] >= last_end:
            result.append(s)
            last_end = s["norm_end"]
    return result


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
    store = store or _store()
    settings = settings or {}
    enable_kw = settings.get("enable_keyword_detection", True)
    enable_rx = settings.get("enable_regex_detection", True)
    enable_sem = settings.get("enable_semantic_detection", True)
    auto_rev = settings.get("auto_generate_revision", True)

    norm_text, index_map = normalize_text(text)
    original = text or ""

    applicable_rules, platform_incomplete = _filter_applicable_rules(store, platform, content_type)

    # ---- 第三步：确定性检测 ----
    raw_spans: list[dict] = []
    for rule in applicable_rules:
        rid = rule.get("rule_id")
        variants = store.variants_by_rule.get(rid, [])
        for v in variants:
            method = (v.get("matching_method") or "contains").lower()
            if method == "semantic":
                continue
            if method == "regex" or v.get("regex_pattern"):
                if not enable_rx:
                    continue
            else:
                if not enable_kw:
                    continue
            for (s, e, mtext) in match_variant(norm_text, v):
                raw_spans.append({
                    "rule_id": rid, "variant_id": v.get("variant_id"),
                    "norm_start": s, "norm_end": e,
                    "matched_norm": mtext, "method": method,
                })

    deduped = _dedup_spans(raw_spans)

    # 分组到规则
    matched_rules: list[dict] = []
    highlight_spans: list[dict] = []
    for sp in deduped:
        rid = sp["rule_id"]
        rule = store.rules_by_id.get(rid, {})
        os, oe = map_span(index_map, sp["norm_start"], sp["norm_end"])
        matched_text = original[os:oe]
        span_info = {
            "rule_id": rid, "variant_id": sp["variant_id"],
            "matched_text": matched_text, "start_index": os, "end_index": oe,
            "matching_method": sp["method"],
        }
        highlight_spans.append(span_info)
        # 聚合到该规则的 matched_rules 条目（取首个命中作为代表）
        existing = next((m for m in matched_rules if m["rule_id"] == rid), None)
        if existing is None:
            src_ids = store.sources_by_rule.get(rid, []) or []
            src_names = [store.sources_by_id.get(sid, {}).get("source_name", "") for sid in src_ids]
            replace = rule.get("replacement_strategy") or ""
            replace_list = [x for x in str(replace).split(";") if x.strip()]
            entry = {
                "rule_id": rid,
                "rule_name": rule.get("rule_name", ""),
                "variant_id": sp["variant_id"],
                "matched_text": matched_text,
                "start_index": os,
                "end_index": oe,
                "matching_method": sp["method"],
                "risk_level": rule.get("risk_level", "low"),
                "legal_conclusion": rule.get("legal_conclusion", ""),
                "system_action": _norm_actions(rule.get("system_action")),
                "risk_reason": rule.get("rule_description", ""),
                "replacement_strategy": replace_list,
                "source_ids": src_ids,
                "source_names": src_names,
                "category_name": rule.get("category_name", ""),
                "prohibited_context": rule.get("prohibited_context", ""),
                "allowed_context": rule.get("allowed_context", ""),
                "evidence_requirement": rule.get("evidence_requirement", ""),
                "qualification_requirement": rule.get("qualification_requirement", ""),
                "auto_rewrite_allowed": bool(rule.get("auto_rewrite_allowed", False)),
                "manual_review_required": bool(rule.get("manual_review_required", False)),
                "review_level": rule.get("review_level", ""),
                "spans": [span_info],
            }
            matched_rules.append(entry)
        else:
            existing["spans"].append(span_info)

    # ---- 第四步：语义检测 ----
    semantic_findings = []
    needs_manual_review = False
    manual_review_reason = ""
    if enable_sem and provider is not None:
        # 筛选适用语义规则
        mapped_platforms = config.PLATFORM_TO_RULE_PLATFORM.get(platform, [])
        sem_rules = []
        for sr in store.semantic_rules:
            ap = sr.get("applicable_platform", "") or ""
            if not ap or any(mp in ap for mp in mapped_platforms):
                sem_rules.append(sr)
        try:
            sem_result = provider.semantic_check(
                text=text, platform=platform, content_type=content_type,
                semantic_rules=sem_rules, matched_rules=matched_rules,
            )
            semantic_findings = sem_result.get("semantic_findings", [])
            needs_manual_review = bool(sem_result.get("needs_manual_review", False))
            manual_review_reason = sem_result.get("manual_review_reason", "")
        except Exception:
            # 语义检测失败不应阻断确定性结果
            needs_manual_review = needs_manual_review or any(
                m.get("manual_review_required") for m in matched_rules
            )

    # ---- 第五步：风险聚合 ----
    if matched_rules:
        overall_risk = max(matched_rules, key=lambda m: config.RISK_PRIORITY.get(m["risk_level"], 0))["risk_level"]
    else:
        overall_risk = "none"

    # review_level 取最大 L 值
    rl_vals = [m["review_level"] for m in matched_rules if m.get("review_level")]
    if rl_vals:
        review_level = max(rl_vals, key=lambda x: int(x[1:]) if x[1:].isdigit() else 0)
    else:
        review_level = ""

    # 发布建议：最高优先级动作
    all_actions = []
    for m in matched_rules:
        all_actions.extend(m["system_action"])
    for sf in semantic_findings:
        if sf.get("manual_review"):
            all_actions.append("mandatory_human_review")
    if all_actions:
        top_action = max(all_actions, key=lambda a: config.ACTION_PRIORITY.get(a, 0))
        publish_recommendation = config.ACTION_TO_RECOMMENDATION.get(top_action, "warning")
    else:
        publish_recommendation = "pass"

    manual_review_required = (
        any(m.get("manual_review_required") for m in matched_rules)
        or any(a == "mandatory_human_review" for a in all_actions)
        or needs_manual_review
    )

    # 人工复核事项
    manual_review_issues = _build_review_issues(
        matched_rules, needs_manual_review, manual_review_reason, store
    )

    # 建议修改稿
    suggested_revision = ""
    if auto_rev and provider is not None and matched_rules:
        try:
            rev = provider.rewrite(
                text=text, matched_rules=matched_rules,
                platform=platform, content_type=content_type,
            )
            suggested_revision = rev.get("suggested_revision", "")
        except Exception:
            suggested_revision = ""

    result = {
        "input_text": original,
        "normalized_text": norm_text,
        "platform": platform,
        "content_type": content_type,
        "overall_risk_level": overall_risk,
        "review_level": review_level,
        "publish_recommendation": publish_recommendation,
        "manual_review_required": manual_review_required,
        "matched_rules": matched_rules,
        "semantic_findings": semantic_findings,
        "platform_findings": [],
        "manual_review_issues": manual_review_issues,
        "suggested_revision": suggested_revision,
        "review_summary": "",
        "disclaimer": config.DISCLAIMER,
        "highlights": highlight_spans,
        "platform_rules_incomplete": platform_incomplete,
    }
    result["review_summary"] = _build_review_summary(result)
    return result


def _build_review_issues(matched_rules, needs_manual_review, reason, store) -> list[dict]:
    issues = []
    for m in matched_rules:
        if m.get("manual_review_required") or "mandatory_human_review" in m.get("system_action", []):
            issues.append({
                "issue_type": m.get("category_name", ""),
                "question": (f"请确认“{m.get('matched_text','')}”是否符合合规要求。"
                             + (f"（{m.get('evidence_requirement')}）" if m.get("evidence_requirement") else "")),
                "required_evidence": m.get("evidence_requirement") or m.get("qualification_requirement") or "",
                "recommended_contact": _recommend_contact(m),
            })
    if needs_manual_review:
        issues.append({
            "issue_type": "语义风险",
            "question": reason or "文案存在需要人工判断的语义风险，建议复核。",
            "required_evidence": "",
            "recommended_contact": "法务或医疗专业人员",
        })
    return issues


def _build_review_summary(result: dict) -> str:
    lines = []
    lines.append("【医美文案人工复核摘要】")
    lines.append(f"平台：{result.get('platform','')}")
    lines.append(f"内容类型：{result.get('content_type','')}")
    risk_label = config.RISK_LABELS.get(result.get("overall_risk_level"), result.get("overall_risk_level"))
    rec = result.get("publish_recommendation")
    rec_label = {"block": "暂停发布", "manual_review": "人工复核后发布",
                 "request_evidence": "补充材料后发布", "warning": "修改后发布", "pass": "可发布"}.get(rec, rec)
    lines.append(f"总体风险：{risk_label}")
    lines.append(f"处理建议：{rec_label}")
    lines.append("")
    if result.get("manual_review_issues"):
        lines.append("需要确认：")
        for i, iss in enumerate(result["manual_review_issues"], 1):
            q = iss.get("question", "")
            ev = iss.get("required_evidence")
            extra = f"（需材料：{ev}）" if ev else ""
            lines.append(f"{i}. {q}{extra}")
        lines.append("")
    if result.get("matched_rules"):
        lines.append("命中规则：")
        for m in result["matched_rules"]:
            lines.append(f"- {m['rule_id']} {m['rule_name']}")
        lines.append("")
    contacts = sorted({iss.get("recommended_contact") for iss in result.get("manual_review_issues", []) if iss.get("recommended_contact")})
    if contacts:
        lines.append("建议对接：" + "、".join(contacts) + "。")
    lines.append("")
    lines.append("本工具不记录复核结果。")
    return "\n".join(lines)


def _store():
    from app.core.data_loader import get_store
    return get_store()

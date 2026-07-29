"""规则库回归测试执行器。使用 test_cases.json 验证当前检测引擎。"""
from __future__ import annotations

import json
from collections import Counter
from typing import Any

from app.core import config
from app.services.compliance.engine import run_compliance_check
from app.services.llm.provider import MockProvider


def _as_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except json.JSONDecodeError:
                pass
        return [part.strip() for part in text.replace("；", ";").split(";") if part.strip()]
    return [str(value)]


def _normalize_action(value: Any) -> str:
    actions = _as_list(value)
    if not actions:
        return ""
    return max(actions, key=lambda action: config.ACTION_PRIORITY.get(action, 0))


def _risk_matches(expected: str, actual: str) -> bool:
    """规则库用 low 表示合规基线；运行时用 none 表示未发现风险。"""
    if not expected:
        return True
    if expected == "low" and actual == "none":
        return True
    return expected == actual


def run_test_suite(store, *, limit: int | None = None, include_passed: bool = False) -> dict:
    cases = list(store.test_cases)
    if limit and limit > 0:
        cases = cases[:limit]

    provider = MockProvider()
    settings = {
        "enable_keyword_detection": True,
        "enable_regex_detection": True,
        "enable_semantic_detection": True,
        "auto_generate_revision": False,
    }

    details: list[dict] = []
    failure_types: Counter[str] = Counter()
    category_totals: Counter[str] = Counter()
    category_passed: Counter[str] = Counter()
    failed_rows = 0
    expected_risky_cases = 0
    detected_risky_cases = 0
    expected_clean_cases = 0
    false_positive_cases = 0
    expected_rule_total = 0
    matched_expected_rule_total = 0
    risk_level_correct = 0
    action_correct = 0

    for case in cases:
        test_id = str(case.get("test_id") or "")
        text = str(case.get("input_text") or "")
        platform = str(case.get("platform") or "小红书")
        content_type = str(case.get("content_type") or case.get("content_context") or "项目介绍")
        expected_ids = set(_as_list(case.get("expected_rule_ids")))
        expected_risk = str(case.get("expected_risk_level") or "")
        expected_action = _normalize_action(case.get("expected_system_action"))
        category = str(case.get("notes") or case.get("content_context") or "未分类")
        category_totals[category] += 1

        try:
            actual = run_compliance_check(
                text=text,
                platform=platform,
                content_type=content_type,
                publisher_identity=case.get("publisher_identity"),
                business_domain=case.get("business_domain"),
                content_legal_nature=case.get("expected_content_legal_nature"),
                store=store,
                provider=provider,
                settings=settings,
            )
            actual_ids = {
                item.get("rule_id")
                for item in actual.get("matched_rules", [])
                if item.get("rule_id")
            }
            actual_ids.update(
                item.get("semantic_rule_id")
                for item in actual.get("semantic_findings", [])
                if item.get("semantic_rule_id")
            )
            actual_risk = str(actual.get("overall_risk_level") or "")
            actual_action = str(actual.get("publish_recommendation") or "")

            missing_ids = sorted(expected_ids - actual_ids)
            unexpected_high_risk = not expected_ids and actual_risk in {"critical", "high"}
            risk_ok = _risk_matches(expected_risk, actual_risk)
            expected_recommendation = config.ACTION_TO_RECOMMENDATION.get(expected_action, expected_action)
            action_ok = not expected_recommendation or actual_action == expected_recommendation
            ids_ok = not missing_ids and not unexpected_high_risk

            problems: list[str] = []
            if not ids_ok:
                problems.append("rule_mismatch")
            if not risk_ok:
                problems.append("risk_mismatch")
            if not action_ok:
                problems.append("action_mismatch")
            passed = not problems
            if expected_ids or expected_risk in {"critical", "high", "medium"}:
                expected_risky_cases += 1
                if actual_risk in {"critical", "high", "medium"}:
                    detected_risky_cases += 1
            else:
                expected_clean_cases += 1
                if actual_risk in {"critical", "high"}:
                    false_positive_cases += 1
            expected_rule_total += len(expected_ids)
            matched_expected_rule_total += len(expected_ids & actual_ids)
            risk_level_correct += int(risk_ok)
            action_correct += int(action_ok)
            if passed:
                category_passed[category] += 1
            else:
                failed_rows += 1
                failure_types.update(problems)

            row = {
                "test_id": test_id,
                "passed": passed,
                "input_text": text,
                "platform": platform,
                "content_type": content_type,
                "expected_rule_ids": sorted(expected_ids),
                "actual_rule_ids": sorted(actual_ids),
                "missing_rule_ids": missing_ids,
                "expected_risk_level": expected_risk,
                "actual_risk_level": actual_risk,
                "expected_action": expected_recommendation,
                "actual_action": actual_action,
                "problems": problems,
            }
        except Exception as exc:
            passed = False
            failed_rows += 1
            failure_types["execution_error"] += 1
            row = {
                "test_id": test_id,
                "passed": False,
                "input_text": text,
                "platform": platform,
                "content_type": content_type,
                "problems": ["execution_error"],
                "error": str(exc),
            }

        if include_passed or not passed:
            details.append(row)

    total = len(cases)
    passed_count = total - failed_rows
    category_metrics = [
        {
            "category": category,
            "total": count,
            "passed": category_passed[category],
            "pass_rate": round(category_passed[category] / count, 4) if count else 0,
        }
        for category, count in category_totals.most_common()
    ]

    return {
        "total": total,
        "passed": passed_count,
        "failed": failed_rows,
        "pass_rate": round(passed_count / total, 4) if total else 0,
        "failure_type_counts": dict(failure_types),
        "category_metrics": category_metrics,
        "details": details[:200],
        "details_truncated": len(details) > 200,
        "engine_mode": "deterministic+mock_semantic",
        "quality_metrics": {
            "risk_detection_recall": round(detected_risky_cases / expected_risky_cases, 4) if expected_risky_cases else 1.0,
            "high_risk_false_positive_rate": round(false_positive_cases / expected_clean_cases, 4) if expected_clean_cases else 0.0,
            "expected_rule_id_recall": round(matched_expected_rule_total / expected_rule_total, 4) if expected_rule_total else 1.0,
            "risk_level_accuracy": round(risk_level_correct / total, 4) if total else 1.0,
            "action_accuracy": round(action_correct / total, 4) if total else 1.0,
            "expected_risky_cases": expected_risky_cases,
            "expected_clean_cases": expected_clean_cases,
        },
        "note": "该结果用于规则回归测试，不等同于法务准确率认证。",
    }

"""合规检测、规则查询、数据校验与回归测试路由。"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.core import config
from app.core.data_loader import get_store, reload, validate_store
from app.core.responses import fail, ok
from app.repositories import db
from app.schemas.models import ComplianceCheckRequest
from app.services.compliance import engine
from app.services.compliance.evaluator import run_test_suite
from app.services.llm.provider import build_provider

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


@router.post("/check")
def check(req: ComplianceCheckRequest):
    try:
        store = get_store()
        settings = db.load_settings()
        provider = build_provider(settings)
        result = engine.run_compliance_check(
            text=req.text,
            platform=req.platform,
            content_type=req.content_type,
            brand=req.brand,
            publisher_identity=req.publisher_identity,
            business_domain=req.business_domain,
            content_legal_nature=req.content_legal_nature,
            is_paid_ad=req.is_paid_ad,
            context_note=req.context_note,
            store=store,
            provider=provider,
            settings=settings,
        )
        result["history_saved"] = False
        if settings.get("save_history"):
            try:
                result["history_saved"] = True
                result["history_record_id"] = db.add_record(
                    operation_type="check",
                    brand=req.brand,
                    platform=req.platform,
                    input_data=req.model_dump(),
                    generated=None,
                    detection=result,
                    risk_level=result.get("overall_risk_level", ""),
                )
            except Exception as exc:
                result["history_saved"] = False
                result["history_error"] = f"自动保存最近记录失败：{exc}"
        return ok(result)
    except ValueError as exc:
        return fail(str(exc), "COMPLIANCE_INPUT_INVALID")
    except Exception as exc:
        return fail(f"检测失败：{exc}", "COMPLIANCE_CHECK_FAILED")


@router.get("/rules")
def list_rules(
    category: str | None = Query(None),
    risk_level: str | None = Query(None),
    platform: str | None = Query(None),
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    store = get_store()
    mapped = config.PLATFORM_TO_RULE_PLATFORM.get(platform, None) if platform else None
    search_text = (keyword or "").strip().lower()
    rows = []

    for rule in store.rules:
        if category and rule.get("category_name") != category and rule.get("category_code") != category:
            continue
        if risk_level and rule.get("risk_level") != risk_level:
            continue
        if status and str(rule.get("effective_status") or "active") != status:
            continue
        if mapped is not None:
            entries = store.platforms_by_rule.get(rule.get("rule_id"), [])
            if entries and not any(entry.get("platform") in mapped for entry in entries):
                continue
        if search_text:
            variants = store.variants_by_rule.get(rule.get("rule_id"), [])
            haystack = " ".join(
                str(rule.get(key, ""))
                for key in ("rule_id", "rule_name", "rule_description", "category_name", "semantic_rule")
            )
            haystack += " " + " ".join(str(variant.get("variant_text") or "") for variant in variants[:50])
            if search_text not in haystack.lower():
                continue
        actions = rule.get("system_action")
        rows.append({
            "rule_id": rule.get("rule_id"),
            "rule_name": rule.get("rule_name"),
            "category_code": rule.get("category_code"),
            "category_name": rule.get("category_name"),
            "risk_level": rule.get("risk_level"),
            "review_level": rule.get("review_level"),
            "legal_conclusion": rule.get("legal_conclusion"),
            "system_action": [actions] if isinstance(actions, str) else (actions or []),
            "effective_status": rule.get("effective_status") or "active",
            "updated_at": rule.get("updated_at"),
            "variant_count": len(store.variants_by_rule.get(rule.get("rule_id"), [])),
            "source_count": len(store.sources_by_rule.get(rule.get("rule_id"), [])),
        })

    total = len(rows)
    return ok({"total": total, "offset": offset, "limit": limit, "rules": rows[offset:offset + limit]})


@router.get("/rules/{rule_id}")
def rule_detail(rule_id: str):
    store = get_store()
    rule = store.rules_by_id.get(rule_id)
    if not rule:
        return fail("未找到该规则", "RULE_NOT_FOUND")
    source_ids = store.sources_by_rule.get(rule_id, []) or []
    sources = [store.sources_by_id.get(source_id, {}) for source_id in source_ids]
    return ok({
        "rule": rule,
        "source_ids": source_ids,
        "source_names": [source.get("source_name", "") for source in sources],
        "sources": sources,
        "variants": store.variants_by_rule.get(rule_id, []),
        "platforms": store.platforms_by_rule.get(rule_id, []),
        "examples": store.examples_by_rule.get(rule_id, []),
    })


@router.get("/sources/{source_id}")
def source_detail(source_id: str):
    source = get_store().sources_by_id.get(source_id)
    if not source:
        return fail("未找到该来源", "SOURCE_NOT_FOUND")
    return ok(source)


@router.post("/reload")
def reload_rules():
    try:
        store = reload()
        return ok({
            "loaded_at": store.loaded_at,
            "rule_count": len(store.rules),
            "variant_count": len(store.variants),
            "source_count": len(store.sources),
            "semantic_count": len(store.semantic_rules),
            "validation_valid": store.validation.get("valid"),
            "validation_error_count": store.validation.get("error_count"),
            "validation_warning_count": store.validation.get("warning_count"),
            "pending_review_count": store.validation.get("pending_review_count", 0),
        })
    except Exception as exc:
        return fail(f"重新加载失败：{exc}", "COMPLIANCE_DATA_INVALID")


@router.post("/validate")
def validate_rules():
    try:
        return ok(validate_store(get_store()))
    except Exception as exc:
        return fail(f"校验失败：{exc}", "COMPLIANCE_DATA_INVALID")


@router.post("/test-suite")
def execute_test_suite(
    limit: int | None = Query(None, ge=1, le=2000),
    include_passed: bool = Query(False),
):
    """运行 test_cases.json 回归测试；不会调用外部模型。"""
    try:
        store = get_store()
        if not store.test_cases:
            return fail("规则库中没有 test_cases.json 测试数据。", "TEST_CASES_EMPTY")
        return ok(run_test_suite(store, limit=limit, include_passed=include_passed))
    except Exception as exc:
        return fail(f"回归测试失败：{exc}", "TEST_SUITE_FAILED")

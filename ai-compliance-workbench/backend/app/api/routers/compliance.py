"""合规检测与规则查询路由。"""
from fastapi import APIRouter, Query
from app.schemas.models import ComplianceCheckRequest
from app.core.data_loader import get_store, reload, validate_store
from app.services.compliance import engine
from app.services.llm.provider import build_provider
from app.repositories import db
from app.core import config
from app.core.responses import ok, fail

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


@router.post("/check")
def check(req: ComplianceCheckRequest):
    try:
        store = get_store()
        settings = db.load_settings()
        provider = build_provider(settings)
        result = engine.run_compliance_check(
            text=req.text, platform=req.platform, content_type=req.content_type,
            brand=req.brand, publisher_identity=req.publisher_identity,
            business_domain=req.business_domain, content_legal_nature=req.content_legal_nature,
            is_paid_ad=req.is_paid_ad, context_note=req.context_note,
            store=store, provider=provider, settings=settings,
        )
        if settings.get("save_history"):
            db.add_record(
                operation_type="check", brand=req.brand, platform=req.platform,
                input_data=req.model_dump(), generated=None, detection=result,
                risk_level=result.get("overall_risk_level", ""),
            )
        return ok(result)
    except ValueError as e:
        return fail(str(e), "COMPLIANCE_DATA_INVALID")
    except Exception as e:
        return fail(f"检测失败：{e}", "COMPLIANCE_CHECK_FAILED")


@router.get("/rules")
def list_rules(
    category: str = Query(None),
    risk_level: str = Query(None),
    platform: str = Query(None),
    status: str = Query(None),
    keyword: str = Query(None),
):
    store = get_store()
    mapped = config.PLATFORM_TO_RULE_PLATFORM.get(platform, None) if platform else None
    kw = (keyword or "").lower()
    out = []
    for r in store.rules:
        if category and r.get("category_name") != category:
            continue
        if risk_level and r.get("risk_level") != risk_level:
            continue
        if status and r.get("effective_status") != status:
            continue
        if mapped is not None:
            entries = store.platforms_by_rule.get(r.get("rule_id"), [])
            if entries and not any(e.get("platform") in mapped for e in entries):
                continue
        if kw:
            hay = " ".join(str(r.get(k, "")) for k in ("rule_id", "rule_name", "rule_description", "category_name")).lower()
            if kw not in hay:
                continue
        out.append({
            "rule_id": r.get("rule_id"),
            "rule_name": r.get("rule_name"),
            "category_code": r.get("category_code"),
            "category_name": r.get("category_name"),
            "risk_level": r.get("risk_level"),
            "legal_conclusion": r.get("legal_conclusion"),
            "system_action": [r.get("system_action")] if isinstance(r.get("system_action"), str) else r.get("system_action"),
            "effective_status": r.get("effective_status"),
            "updated_at": r.get("updated_at"),
        })
    return ok({"total": len(out), "rules": out})


@router.get("/rules/{rule_id}")
def rule_detail(rule_id: str):
    store = get_store()
    r = store.rules_by_id.get(rule_id)
    if not r:
        return fail("未找到该规则", "RULE_NOT_FOUND")
    src_ids = store.sources_by_rule.get(rule_id, []) or []
    src_names = [store.sources_by_id.get(sid, {}).get("source_name", "") for sid in src_ids]
    variants = store.variants_by_rule.get(rule_id, [])
    platforms = store.platforms_by_rule.get(rule_id, [])
    return ok({
        "rule": r,
        "source_ids": src_ids,
        "source_names": src_names,
        "variants": variants,
        "platforms": platforms,
    })


@router.get("/sources/{source_id}")
def source_detail(source_id: str):
    store = get_store()
    s = store.sources_by_id.get(source_id)
    if not s:
        return fail("未找到该来源", "SOURCE_NOT_FOUND")
    return ok(s)


@router.post("/reload")
def reload_rules():
    try:
        store = reload()
        return ok({
            "loaded_at": store.loaded_at,
            "rule_count": len(store.rules),
            "validation_valid": store.validation.get("valid"),
            "validation_error_count": store.validation.get("error_count"),
        })
    except Exception as e:
        return fail(f"重新加载失败：{e}", "COMPLIANCE_DATA_INVALID")


@router.post("/validate")
def validate_rules():
    try:
        store = get_store()
        v = validate_store(store)
        return ok(v)
    except Exception as e:
        return fail(f"校验失败：{e}", "COMPLIANCE_DATA_INVALID")

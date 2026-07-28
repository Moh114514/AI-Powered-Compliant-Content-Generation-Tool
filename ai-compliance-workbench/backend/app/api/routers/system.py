"""系统状态路由：健康检查与规则库运行状态。"""
from fastapi import APIRouter

from app.core import config
from app.core.data_loader import get_store
from app.core.responses import fail, ok
from app.repositories import db

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health():
    return ok({"status": "ok"})


@router.get("/status")
def status():
    try:
        store = get_store()
        settings = db.load_settings()
        configured_provider = settings.get("model_provider", "mock")
        demo_mode = configured_provider == "mock" or not bool(config.LLM_API_KEY)
        validation = store.validation
        return ok({
            "data_version": store.metadata.get("version", "unknown"),
            "library_name": store.metadata.get("library_name", ""),
            "rule_count": len(store.rules),
            "variant_count": len(store.variants),
            "source_count": len(store.sources),
            "semantic_count": len(store.semantic_rules),
            "test_case_count": len(store.test_cases),
            "visual_check_count": len(store.visual_manual_checks),
            "platform_relation_count": len(store.rule_platforms),
            "example_count": len(store.rule_examples),
            "loaded_at": store.loaded_at,
            "validation_valid": validation.get("valid", False),
            "validation_error_count": validation.get("error_count", 0),
            "validation_warning_count": validation.get("warning_count", 0),
            "pending_review_count": validation.get("pending_review_count", 0),
            "demo_mode": demo_mode,
            "configured_provider": configured_provider,
            "platforms": config.PLATFORMS,
        })
    except Exception as exc:
        return fail(f"加载规则库失败：{exc}", "COMPLIANCE_DATA_INVALID")

"""系统状态路由：健康检查与规则库运行状态。"""
from fastapi import APIRouter

from app.core import config
from app.core.data_loader import get_store
from app.core.responses import fail, ok
from app.repositories import db
from app.services.prompts.catalog import active_platform_names, catalog_stats

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
        api_key_configured = bool(config.get_llm_api_key())
        demo_mode = configured_provider == "mock"
        provider_ready = demo_mode or api_key_configured
        provider_error = ""
        if configured_provider != "mock" and not api_key_configured:
            provider_error = "已选择真实模型，但未读取到 LLM_API_KEY。"
        validation = store.validation
        configured_default = db.get_setting_override("default_platform")
        active_platforms = active_platform_names()
        default_platform_warning = ""
        if configured_default and configured_default not in active_platforms:
            default_platform_warning = (
                f"原默认平台“{configured_default}”已停用，当前已回退为“{settings.get('default_platform')}”。"
            )
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
            "active_provider": configured_provider if provider_ready else "unavailable",
            "provider_ready": provider_ready,
            "provider_error": provider_error,
            "api_key_configured": api_key_configured,
            "model_name": settings.get("model_name") or config.LLM_MODEL,
            "platforms": active_platforms,
            "default_platform_warning": default_platform_warning,
            **catalog_stats(),
        })
    except Exception as exc:
        return fail(f"加载规则库失败：{exc}", "COMPLIANCE_DATA_INVALID")

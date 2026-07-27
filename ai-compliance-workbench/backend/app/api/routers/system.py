"""系统状态路由：健康检查、数据状态。"""
from fastapi import APIRouter
from app.core import config
from app.core.data_loader import get_store
from app.core.responses import ok, fail

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health():
    return ok({"status": "ok"})


@router.get("/status")
def status():
    try:
        store = get_store()
        demo = not bool(config.LLM_API_KEY)
        return ok({
            "data_version": store.metadata.get("version", "unknown"),
            "library_name": store.metadata.get("library_name", ""),
            "rule_count": len(store.rules),
            "variant_count": len(store.variants),
            "source_count": len(store.sources),
            "semantic_count": len(store.semantic_rules),
            "loaded_at": store.loaded_at,
            "validation_valid": store.validation.get("valid", False),
            "validation_error_count": store.validation.get("error_count", 0),
            "demo_mode": demo,
            "platforms": config.PLATFORMS,
        })
    except Exception as e:
        return fail(f"加载规则库失败：{e}", "COMPLIANCE_DATA_INVALID")

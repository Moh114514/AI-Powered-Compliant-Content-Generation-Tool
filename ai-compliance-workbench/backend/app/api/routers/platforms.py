"""品牌与平台路由。"""
from fastapi import APIRouter
from app.services.brands.loader import list_brands, get_brand
from app.services.prompts.catalog import active_content_types, active_platform_names, get_catalog
from app.core.responses import ok, fail

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/brands")
def brands():
    return ok(list_brands())


@router.get("/brands/{brand_id}")
def brand_detail(brand_id: str):
    b = get_brand(brand_id)
    if not b:
        return fail("未找到该品牌", "BRAND_NOT_FOUND")
    return ok(b)


@router.get("/platforms")
def platforms():
    return ok(active_platform_names())


@router.get("/content-types")
def content_types():
    return ok(active_content_types())


@router.get("/prompt-templates")
def prompt_templates():
    catalog = get_catalog(False)
    # Preserve the old list response while exposing platform-level effective prompts.
    return ok([
        {
            "platform": platform["name"],
            "platform_id": platform["id"],
            "file": "",
            "content": platform["effective_prompt"],
            "scenes": platform["scenes"],
        }
        for platform in catalog["platforms"]
    ])

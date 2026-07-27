"""品牌与平台路由。"""
from fastapi import APIRouter
from app.services.brands.loader import list_brands, get_brand
from app.services.prompts.loader import list_prompt_templates
from app.core import config
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
    return ok(config.PLATFORMS)


@router.get("/content-types")
def content_types():
    return ok(config.CONTENT_TYPES)


@router.get("/prompt-templates")
def prompt_templates():
    return ok(list_prompt_templates())

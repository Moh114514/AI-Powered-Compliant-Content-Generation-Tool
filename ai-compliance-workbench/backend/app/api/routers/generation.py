"""内容生成路由。"""
from fastapi import APIRouter, HTTPException
from app.schemas.models import GenerateRequest, RewriteRequest, AdjustRequest
from app.repositories import db
from app.services.generation import service as gen_service
from app.core.responses import ok, fail

router = APIRouter(prefix="/api/generation", tags=["generation"])


@router.post("/generate")
def generate(req: GenerateRequest):
    try:
        settings = db.load_settings()
        result = gen_service.generate(req.model_dump(), settings)
        return ok(result)
    except ValueError as e:
        return fail(str(e), "COMPLIANCE_DATA_INVALID")
    except Exception as e:
        return fail(f"生成失败：{e}", "GENERATION_FAILED")


@router.post("/rewrite")
def rewrite(req: RewriteRequest):
    try:
        settings = db.load_settings()
        return ok(gen_service.rewrite(req.model_dump(), settings))
    except Exception as e:
        return fail(f"改写失败：{e}", "REWRITE_FAILED")


@router.post("/adjust")
def adjust(req: AdjustRequest):
    try:
        settings = db.load_settings()
        return ok(gen_service.adjust(req.model_dump(), settings))
    except Exception as e:
        return fail(f"调整失败：{e}", "ADJUST_FAILED")

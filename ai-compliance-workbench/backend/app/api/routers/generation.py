"""内容生成、改写与调整路由。"""
from fastapi import APIRouter

from app.core.responses import fail, ok
from app.repositories import db
from app.schemas.models import AdjustRequest, GenerateRequest, RewriteRequest
from app.services.generation import service as generation_service

router = APIRouter(prefix="/api/generation", tags=["generation"])


@router.post("/generate")
def generate(req: GenerateRequest):
    try:
        return ok(generation_service.generate(req.model_dump(), db.load_settings()))
    except ValueError as exc:
        return fail(str(exc), "GENERATION_INPUT_INVALID")
    except Exception as exc:
        return fail(f"生成失败：{exc}", "GENERATION_FAILED")


@router.post("/rewrite")
def rewrite(req: RewriteRequest):
    try:
        return ok(generation_service.rewrite(req.model_dump(), db.load_settings()))
    except ValueError as exc:
        return fail(str(exc), "REWRITE_INPUT_INVALID")
    except Exception as exc:
        return fail(f"改写失败：{exc}", "REWRITE_FAILED")


@router.post("/adjust")
def adjust(req: AdjustRequest):
    try:
        return ok(generation_service.adjust(req.model_dump(), db.load_settings()))
    except ValueError as exc:
        return fail(str(exc), "ADJUST_INPUT_INVALID")
    except Exception as exc:
        return fail(f"调整失败：{exc}", "ADJUST_FAILED")

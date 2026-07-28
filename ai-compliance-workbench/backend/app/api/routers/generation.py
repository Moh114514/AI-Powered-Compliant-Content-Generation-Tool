"""内容生成、改写与调整路由。"""
from fastapi import APIRouter

from app.core import config
from app.core.responses import fail, ok
from app.repositories import db
from app.schemas.models import AdjustRequest, GenerateRequest, RewriteRequest
from app.services.generation import service as generation_service

router = APIRouter(prefix="/api/generation", tags=["generation"])


@router.post("/generate")
def generate(req: GenerateRequest):
    try:
        settings = db.load_settings()
        result = generation_service.generate(req.model_dump(), settings)
        result["history_saved"] = False
        if settings.get("save_history"):
            try:
                risks = [
                    str(version.get("overall_risk_level") or "none")
                    for version in result.get("versions", [])
                ]
                risk_level = max(
                    risks or ["none"],
                    key=lambda level: config.RISK_PRIORITY.get(level, 0),
                )
                result["history_saved"] = True
                result["history_record_id"] = db.add_record(
                    operation_type="generation",
                    brand=req.brand,
                    platform=req.platform,
                    input_data=req.model_dump(),
                    generated=result,
                    detection=None,
                    risk_level=risk_level,
                )
            except Exception as exc:
                result["history_saved"] = False
                result["history_error"] = f"自动保存最近记录失败：{exc}"
        return ok(result)
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

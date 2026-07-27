"""导出路由：人工复核摘要、检测报告。"""
from fastapi import APIRouter
from app.schemas.models import ExportRequest
from app.services.export import service as export_svc
from app.core.responses import ok, fail

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/review-summary")
def review_summary(req: ExportRequest):
    try:
        text = export_svc.build_review_summary(req.result)
        return ok({"format": req.format, "content": text})
    except Exception as e:
        return fail(f"生成复核摘要失败：{e}", "EXPORT_FAILED")


@router.post("/report")
def report(req: ExportRequest):
    try:
        if req.format == "json":
            content = export_svc.build_report_json(req.result)
            return ok({"format": "json", "content": content})
        content = export_svc.build_report_markdown(req.result)
        return ok({"format": req.format or "md", "content": content})
    except Exception as e:
        return fail(f"生成报告失败：{e}", "EXPORT_FAILED")

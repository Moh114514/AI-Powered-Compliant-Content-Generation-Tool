"""最近记录路由。"""
from fastapi import APIRouter, Query
from app.repositories import db
from app.core.responses import ok, fail

router = APIRouter(prefix="/api", tags=["history"])


@router.get("/history")
def list_history(limit: int = Query(100)):
    try:
        return ok(db.list_records(limit=limit))
    except Exception as e:
        return fail(f"读取记录失败：{e}", "HISTORY_READ_FAILED")


@router.get("/history/{record_id}")
def get_history(record_id: str):
    rec = db.get_record(record_id)
    if not rec:
        return fail("未找到该记录", "RECORD_NOT_FOUND")
    return ok(rec)


@router.post("/history")
def create_history(payload: dict):
    try:
        rid = db.add_record(
            operation_type=payload.get("operation_type", "manual"),
            brand=payload.get("brand"),
            platform=payload.get("platform"),
            input_data=payload.get("input", {}),
            generated=payload.get("generated"),
            detection=payload.get("detection"),
            risk_level=payload.get("risk_level", ""),
        )
        return ok({"id": rid})
    except Exception as e:
        return fail(f"保存记录失败：{e}", "HISTORY_WRITE_FAILED")


@router.delete("/history/{record_id}")
def delete_history(record_id: str):
    ok_del = db.delete_record(record_id)
    if not ok_del:
        return fail("未找到该记录", "RECORD_NOT_FOUND")
    return ok({"deleted": True})


@router.delete("/history")
def clear_all():
    db.clear_records()
    return ok({"cleared": True})

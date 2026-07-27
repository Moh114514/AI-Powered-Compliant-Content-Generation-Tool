"""设置路由。"""
from fastapi import APIRouter
from app.schemas.models import SettingsPatch
from app.repositories import db
from app.core.responses import ok, fail

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings")
def get_settings():
    return ok(db.load_settings())


@router.patch("/settings")
def patch_settings(req: SettingsPatch):
    try:
        merged = db.save_settings(req.patch)
        return ok(merged)
    except Exception as e:
        return fail(f"保存设置失败：{e}", "SETTINGS_WRITE_FAILED")

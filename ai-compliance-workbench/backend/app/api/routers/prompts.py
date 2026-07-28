"""Prompt catalog management and AI-assisted prompt drafting."""
from fastapi import APIRouter, Body

from app.core.responses import fail, ok
from app.repositories import db
from app.services.prompts import catalog

router = APIRouter(prefix="/api", tags=["prompts"])


def _run(action, *args):
    try:
        return ok(action(*args))
    except ValueError as exc:
        return fail(str(exc), "PROMPT_CATALOG_INVALID")
    except Exception as exc:
        return fail(f"提示词目录操作失败：{exc}", "PROMPT_CATALOG_FAILED")


@router.get("/prompt-catalog")
def prompt_catalog(include_inactive: bool = True):
    return _run(catalog.get_catalog, include_inactive)


@router.put("/prompt-templates/base")
def save_base(payload: dict = Body(...)):
    return _run(catalog.save_base_prompt, payload.get("prompt_text"))


@router.delete("/prompt-templates/base")
def reset_base():
    return _run(catalog.reset_base_prompt)


@router.delete("/prompt-templates/reset-builtins")
def reset_builtin_prompts():
    return _run(catalog.reset_all_builtin_prompts)


@router.post("/prompt-templates/ai-draft")
def ai_draft(payload: dict = Body(...)):
    return _run(catalog.generate_ai_draft, payload, db.load_settings())


@router.post("/prompt-platforms")
def create_platform(payload: dict = Body(...)):
    return _run(catalog.create_platform, payload)


@router.put("/prompt-platforms/{platform_id}")
def update_platform(platform_id: str, payload: dict = Body(...)):
    return _run(catalog.update_platform, platform_id, payload)


@router.delete("/prompt-platforms/{platform_id}")
def deactivate_platform(platform_id: str):
    return _run(catalog.set_platform_active, platform_id, False)


@router.post("/prompt-platforms/{platform_id}/activate")
def activate_platform(platform_id: str):
    return _run(catalog.set_platform_active, platform_id, True)


@router.delete("/prompt-platforms/{platform_id}/prompt")
def reset_platform_prompt(platform_id: str):
    return _run(catalog.reset_platform_prompt, platform_id)


@router.post("/prompt-platforms/{platform_id}/scenes")
def create_scene(platform_id: str, payload: dict = Body(...)):
    return _run(catalog.create_scene, platform_id, payload)


@router.put("/prompt-scenes/{scene_id}")
def update_scene(scene_id: str, payload: dict = Body(...)):
    return _run(catalog.update_scene, scene_id, payload)


@router.delete("/prompt-scenes/{scene_id}")
def deactivate_scene(scene_id: str):
    return _run(catalog.set_scene_active, scene_id, False)


@router.post("/prompt-scenes/{scene_id}/activate")
def activate_scene(scene_id: str):
    return _run(catalog.set_scene_active, scene_id, True)


@router.delete("/prompt-scenes/{scene_id}/prompt")
def reset_scene_prompt(scene_id: str):
    return _run(catalog.reset_scene_prompt, scene_id)

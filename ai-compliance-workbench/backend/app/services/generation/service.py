"""内容生成服务：组装平台 Prompt、品牌配置、Provider 与合规检测。"""
from __future__ import annotations

import datetime
import time
from concurrent.futures import ThreadPoolExecutor

from app.core import config
from app.core.data_loader import get_store
from app.services.brands.loader import get_brand
from app.services.compliance.engine import run_compliance_check
from app.services.llm.provider import build_provider
from app.services.prompts.catalog import compose_prompt, resolve_scene


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _detection_settings(settings: dict) -> dict:
    """生成/调整阶段只检测，不自动再调用一次改写模型。"""
    copied = dict(settings or {})
    copied["auto_generate_revision"] = False
    copied["enable_semantic_detection"] = bool(
        copied.get("enable_semantic_detection", True)
        and copied.get("auto_semantic_check", True)
    )
    return copied


def _validate_scene(platform: str, content_type: str, platform_id=None, scene_id=None) -> tuple[dict, dict]:
    return resolve_scene(platform, content_type, platform_id, scene_id)


def generate(request: dict, settings: dict) -> dict:
    total_started = time.perf_counter()
    store = get_store()
    platform = str(request.get("platform") or "")
    content_type = str(request.get("content_type") or "")
    platform_item, scene = _validate_scene(
        platform, content_type, request.get("platform_id"), request.get("scene_id")
    )
    platform, content_type = platform_item["name"], scene["name"]

    topic = str(request.get("topic") or "").strip()
    selling_points = str(request.get("selling_points") or "").strip()
    if not topic and not selling_points:
        raise ValueError("请至少填写主题或核心卖点。")

    brand_id = request.get("brand")
    use_brand = bool(request.get("use_brand_profile", True))
    versions = max(1, min(int(request.get("versions") or settings.get("default_versions", 3) or 3), 5))
    brand_profile = get_brand(brand_id) if use_brand and brand_id else None
    prompt_started = time.perf_counter()
    prompt_template, platform_item, scene = compose_prompt(
        platform, content_type, platform_item["id"], scene["id"]
    )
    prompt_ms = round((time.perf_counter() - prompt_started) * 1000, 2)
    provider = build_provider(settings)
    model_name = str(getattr(provider, "model", provider.name))

    generation_started = time.perf_counter()
    copies = provider.generate(
        platform=platform,
        content_type=content_type,
        inputs=request,
        prompt_template=prompt_template,
        brand_profile=brand_profile,
        versions=versions,
    )
    model_generation_ms = round((time.perf_counter() - generation_started) * 1000, 2)
    copies = [str(text).strip() for text in copies if str(text).strip()]
    if not copies:
        raise ValueError("模型没有返回可用文案，请检查模型配置或稍后重试。")

    detection_settings = _detection_settings(settings)
    def check_copy(text: str) -> dict:
        return run_compliance_check(
            text=text,
            platform=platform,
            content_type=content_type,
            brand=brand_id,
            store=store,
            provider=provider,
            settings=detection_settings,
        )

    compliance_started = time.perf_counter()
    if len(copies) > 1:
        with ThreadPoolExecutor(
            max_workers=min(len(copies), 3),
            thread_name_prefix="compliance",
        ) as executor:
            compliance_results = list(executor.map(check_copy, copies))
    else:
        compliance_results = [check_copy(copies[0])]
    compliance_ms = round((time.perf_counter() - compliance_started) * 1000, 2)

    result_versions = []
    for index, (text, compliance) in enumerate(zip(copies, compliance_results), 1):
        result_versions.append({
            "version_index": index,
            "text": text,
            "platform": platform,
            "content_type": content_type,
            "platform_id": platform_item["id"],
            "scene_id": scene["id"],
            "char_count": len(text),
            "generated_at": _now(),
            "model": model_name,
            "provider": provider.name,
            "overall_risk_level": compliance["overall_risk_level"],
            "matched_count": len(compliance["matched_rules"]),
            "manual_review_required": compliance["manual_review_required"],
            "compliance": compliance,
        })

    return {
        "platform": platform,
        "content_type": content_type,
        "platform_id": platform_item["id"],
        "scene_id": scene["id"],
        "brand": brand_id,
        "model": model_name,
        "provider": provider.name,
        "demo_mode": provider.name == "mock",
        "requested_versions": versions,
        "returned_versions": len(result_versions),
        "versions": result_versions,
        "timings_ms": {
            "prompt_assembly": prompt_ms,
            "model_generation": model_generation_ms,
            "compliance_all_versions": compliance_ms,
            "total": round((time.perf_counter() - total_started) * 1000, 2),
        },
        "disclaimer": config.DISCLAIMER,
    }


def rewrite(request: dict, settings: dict) -> dict:
    store = get_store()
    text = str(request.get("text") or "").strip()
    platform = str(request.get("platform") or "")
    content_type = str(request.get("content_type") or "")
    platform_item, scene = _validate_scene(
        platform, content_type, request.get("platform_id"), request.get("scene_id")
    )
    platform, content_type = platform_item["name"], scene["name"]
    if not text:
        raise ValueError("待改写文本不能为空。")

    provider = build_provider(settings)
    model_name = str(getattr(provider, "model", provider.name))
    detection_settings = _detection_settings(settings)
    original_compliance = run_compliance_check(
        text=text,
        platform=platform,
        content_type=content_type,
        brand=request.get("brand"),
        store=store,
        provider=provider,
        settings=detection_settings,
    )

    if not original_compliance["matched_rules"] and not original_compliance["semantic_findings"]:
        return {
            "suggested_revision": text,
            "auto_rewrite": True,
            "unresolved_items": [],
            "original_compliance": original_compliance,
            "revised_compliance": original_compliance,
            "demo_mode": provider.name == "mock",
            "model": model_name,
            "provider": provider.name,
            "platform_id": platform_item["id"],
            "scene_id": scene["id"],
            "disclaimer": config.DISCLAIMER,
            "message": "未发现需要自动改写的明显风险。",
        }

    revision = provider.rewrite(
        text=text,
        matched_rules=original_compliance["matched_rules"],
        platform=platform,
        content_type=content_type,
    ) or {}
    suggested = str(revision.get("suggested_revision") or "").strip()
    revised_compliance = None
    if suggested:
        revised_compliance = run_compliance_check(
            text=suggested,
            platform=platform,
            content_type=content_type,
            brand=request.get("brand"),
            store=store,
            provider=provider,
            settings=detection_settings,
        )

    return {
        "suggested_revision": suggested,
        "auto_rewrite": bool(revision.get("auto_rewrite", False)),
        "unresolved_items": revision.get("unresolved_items", []),
        "original_compliance": original_compliance,
        "revised_compliance": revised_compliance,
        "compliance": original_compliance,
        "demo_mode": provider.name == "mock",
        "model": model_name,
        "provider": provider.name,
        "platform_id": platform_item["id"],
        "scene_id": scene["id"],
        "disclaimer": config.DISCLAIMER,
    }


def adjust(request: dict, settings: dict) -> dict:
    store = get_store()
    text = str(request.get("text") or "").strip()
    platform = str(request.get("platform") or "")
    content_type = str(request.get("content_type") or "")
    platform_item, scene = _validate_scene(
        platform, content_type, request.get("platform_id"), request.get("scene_id")
    )
    platform, content_type = platform_item["name"], scene["name"]
    if not text:
        raise ValueError("待调整文本不能为空。")

    adjust_type = str(request.get("adjust_type") or "缩短")
    if adjust_type not in {"缩短", "扩写", "调整语气"}:
        raise ValueError(f"不支持的调整类型：{adjust_type}")

    provider = build_provider(settings)
    model_name = str(getattr(provider, "model", provider.name))
    new_text = provider.adjust(
        text=text,
        adjust_type=adjust_type,
        platform=platform,
        content_type=content_type,
        tone=str(request.get("tone") or settings.get("default_tone", "亲切专业")),
    )
    new_text = str(new_text or "").strip()
    if not new_text:
        raise ValueError("调整服务没有返回有效文案。")
    compliance = run_compliance_check(
        text=new_text,
        platform=platform,
        content_type=content_type,
        brand=request.get("brand"),
        store=store,
        provider=provider,
        settings=_detection_settings(settings),
    )
    return {
        "text": new_text,
        "original_text": text,
        "adjust_type": adjust_type,
        "platform": platform,
        "content_type": content_type,
        "platform_id": platform_item["id"],
        "scene_id": scene["id"],
        "model": model_name,
        "provider": provider.name,
        "demo_mode": provider.name == "mock",
        "compliance": compliance,
        "disclaimer": config.DISCLAIMER,
    }


def compliance_disclaimer() -> str:
    return config.DISCLAIMER

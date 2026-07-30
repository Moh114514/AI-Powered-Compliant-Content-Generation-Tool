"""Database-backed prompt catalog and runtime prompt composition."""
from __future__ import annotations

import re
import uuid
from copy import deepcopy
from functools import lru_cache
from typing import Any

from app.core import config
from app.core.data_loader import get_store
from app.repositories import db
from app.services.prompts.defaults import load_builtin_defaults

MAX_PROMPT_LENGTH = 30000
RULE_PROFILES = ["通用", "微信", "小红书", "抖音"]
CONTENT_RULE_PROFILES = [
    "通用", "广告", "文章", "朋友圈", "客服话术", "笔记", "直播", "直播口播",
    "短视频", "账号资料", "图文/私信", "图文/视频", "图文/视频/直播",
    "商品/直播", "标题/口播/画面文字", "标题/正文/评论", "直播/视频",
    "短视频/直播", "社群/私信", "笔记/广告", "群消息/私信",
    "视频/直播/私信", "评论/私信", "评论/私信/口播", "评论/私信/直播",
]


def _clean_name(value: Any, label: str) -> str:
    name = re.sub(r"\s+", " ", str(value or "")).strip()
    if not name:
        raise ValueError(f"{label}不能为空。")
    if len(name) > 60:
        raise ValueError(f"{label}不能超过 60 个字符。")
    return name


def _clean_prompt(value: Any, required: bool = True) -> str:
    prompt = str(value or "").strip()
    if required and not prompt:
        raise ValueError("提示词不能为空。")
    if len(prompt) > MAX_PROMPT_LENGTH:
        raise ValueError(f"提示词不能超过 {MAX_PROMPT_LENGTH} 个字符。")
    return prompt


def seed_builtins() -> None:
    defaults = load_builtin_defaults()
    db.seed_prompt_catalog(defaults)
    invalidate_catalog_cache()


@lru_cache(maxsize=2)
def _load_catalog_cached(include_inactive: bool) -> dict:
    defaults = load_builtin_defaults()
    rows = db.load_prompt_catalog(include_inactive=include_inactive)
    base_override = db.get_prompt_override("base", "global")
    platforms = []
    for platform in rows:
        default_platform = defaults["platforms"].get(platform["name"], {})
        platform_default = default_platform.get("prompt", "") if platform["is_builtin"] else ""
        platform_override = db.get_prompt_override("platform", platform["id"])
        scenes = []
        for scene in platform["scenes"]:
            default_scene = default_platform.get("scenes", {}).get(scene["name"], "") if scene["is_builtin"] else ""
            scene_override = db.get_prompt_override("scene", scene["id"])
            scenes.append({
                **scene,
                "default_prompt": default_scene,
                "effective_prompt": scene_override if scene_override is not None else scene["prompt_text"] or default_scene,
                "is_overridden": scene_override is not None,
            })
        platforms.append({
            **platform,
            "default_prompt": platform_default,
            "effective_prompt": platform_override if platform_override is not None else platform["prompt_text"] or platform_default,
            "is_overridden": platform_override is not None,
            "scenes": scenes,
        })
    return {
        "version": defaults["version"],
        "source": defaults["source"],
        "base_prompt": {
            "default": defaults["base_prompt"],
            "effective": base_override if base_override is not None else defaults["base_prompt"],
            "is_overridden": base_override is not None,
        },
        "self_check_prompt": defaults["self_check_prompt"],
        "rule_profiles": RULE_PROFILES,
        "content_rule_profiles": CONTENT_RULE_PROFILES,
        "platforms": platforms,
    }


def invalidate_catalog_cache() -> None:
    _load_catalog_cached.cache_clear()


def get_catalog(include_inactive: bool = True) -> dict:
    """Return a defensive copy of the read-only in-memory catalog snapshot."""
    return deepcopy(_load_catalog_cached(bool(include_inactive)))


def _catalog_snapshot(include_inactive: bool = True) -> dict:
    """Internal immutable snapshot; callers must never mutate the returned object."""
    return _load_catalog_cached(bool(include_inactive))


def active_platform_names() -> list[str]:
    return [item["name"] for item in _catalog_snapshot(False)["platforms"] if item["scenes"]]


def active_content_types() -> dict[str, list[str]]:
    return {
        item["name"]: [scene["name"] for scene in item["scenes"] if scene["active"]]
        for item in _catalog_snapshot(False)["platforms"] if item["scenes"]
    }


def resolve_scene(
    platform: str = "",
    content_type: str = "",
    platform_id: str | None = None,
    scene_id: str | None = None,
    *,
    include_inactive: bool = False,
) -> tuple[dict, dict]:
    catalog = _catalog_snapshot(include_inactive)
    selected_platform = next(
        (
            item for item in catalog["platforms"]
            if (platform_id and item["id"] == platform_id)
            or (not platform_id and item["name"] == platform)
        ),
        None,
    )
    if not selected_platform:
        raise ValueError(f"不支持的发布平台：{platform or platform_id or '未填写'}")
    selected_scene = next(
        (
            item for item in selected_platform["scenes"]
            if (scene_id and item["id"] == scene_id)
            or (not scene_id and item["name"] == content_type)
        ),
        None,
    )
    if not selected_scene:
        raise ValueError(
            f"“{content_type or scene_id or '未填写'}”不属于“{selected_platform['name']}”的可选内容类型。"
        )
    return selected_platform, selected_scene


def rule_mapping(platform: str, content_type: str) -> tuple[list[str] | None, list[str] | None]:
    try:
        platform_item, scene = resolve_scene(platform, content_type, include_inactive=True)
    except ValueError:
        return None, None
    rule_platforms = [] if platform_item["rule_profile"] == "通用" else [platform_item["rule_profile"]]
    if scene["rule_content_type"] == "自动":
        rule_content_types = config.map_content_type_to_rule_ct(scene["name"])
    else:
        rule_content_types = [] if scene["rule_content_type"] == "通用" else [scene["rule_content_type"]]
    return rule_platforms, rule_content_types


def platform_rule_mapping(platform: str) -> list[str] | None:
    item = next(
        (entry for entry in _catalog_snapshot(True)["platforms"] if entry["name"] == platform),
        None,
    )
    if not item:
        return None
    return [] if item["rule_profile"] == "通用" else [item["rule_profile"]]


def _compliance_guardrail(platform: str, content_type: str, limit: int = 4500) -> str:
    from app.services.compliance.engine import get_applicable_rules
    from app.services.compliance.banned_words import is_xhs_scope, prompt_guardrail

    store = get_store()
    rules, _ = get_applicable_rules(store, platform, content_type)
    xhs_enabled = is_xhs_scope(platform, content_type)
    rules_limit = min(limit, 3000) if xhs_enabled else limit
    lines = [
        "【动态合规约束（系统锁定）】",
        "以下内容来自当前合规规则库。不得绕过、弱化或用近义表达规避；无法确认事实时删除相关主张。",
    ]
    for rule in sorted(
        rules,
        key=lambda item: ({"critical": 0, "high": 1, "medium": 2, "low": 3}.get(str(item.get("risk_level")), 4), str(item.get("rule_id"))),
    ):
        strategies = rule.get("replacement_strategy") or []
        if isinstance(strategies, str):
            strategies = [strategies]
        line = (
            f"- {rule.get('rule_id')} {rule.get('rule_name')}："
            f"{rule.get('prohibited_context') or rule.get('legal_conclusion') or '避免相关风险表达'}"
        )
        if strategies:
            line += f"；建议：{'；'.join(str(item) for item in strategies[:2])}"
        if sum(len(item) + 1 for item in lines) + len(line) > rules_limit:
            lines.append("- 其余适用规则由生成后的完整合规检测继续执行。")
            break
        lines.append(line)
    if xhs_enabled:
        remaining = max(0, limit - sum(len(item) + 1 for item in lines) - 2)
        banned_guardrail = prompt_guardrail(
            store.xhs_banned_words,
            limit=min(1400, remaining),
        )
        if banned_guardrail:
            lines.extend(["", banned_guardrail])
    return "\n".join(lines)


def compose_prompt(platform: str, content_type: str, platform_id: str | None = None, scene_id: str | None = None) -> tuple[str, dict, dict]:
    catalog = _catalog_snapshot(True)
    platform_item, scene = resolve_scene(
        platform, content_type, platform_id, scene_id, include_inactive=False
    )
    prompt = "\n\n".join(filter(None, [
        catalog["base_prompt"]["effective"],
        platform_item["effective_prompt"],
        scene["effective_prompt"],
        catalog["self_check_prompt"],
        _compliance_guardrail(platform_item["name"], scene["name"]),
    ]))
    return prompt, platform_item, scene


def save_base_prompt(prompt: str) -> dict:
    db.set_prompt_override("base", "global", _clean_prompt(prompt))
    invalidate_catalog_cache()
    return get_catalog()


def reset_base_prompt() -> dict:
    db.delete_prompt_override("base", "global")
    invalidate_catalog_cache()
    return get_catalog()


def create_platform(payload: dict) -> dict:
    name = _clean_name(payload.get("name"), "平台名称")
    profile = str(payload.get("rule_profile") or "通用")
    if profile not in RULE_PROFILES:
        raise ValueError("无效的合规规则画像。")
    platform_id = "platform-" + uuid.uuid4().hex
    db.create_prompt_platform(
        platform_id, name, str(payload.get("description") or "").strip(),
        _clean_prompt(payload.get("prompt_text")), profile, int(payload.get("sort_order") or 100),
    )
    invalidate_catalog_cache()
    return next(item for item in get_catalog()["platforms"] if item["id"] == platform_id)


def update_platform(platform_id: str, payload: dict) -> dict:
    current = db.get_prompt_platform(platform_id)
    if not current:
        raise ValueError("未找到该平台。")
    fields: dict[str, Any] = {}
    if "name" in payload:
        if current["is_builtin"] and _clean_name(payload["name"], "平台名称") != current["name"]:
            raise ValueError("系统内置平台不能改名。")
        fields["name"] = _clean_name(payload["name"], "平台名称")
    for key in ("description", "sort_order", "rule_profile"):
        if key in payload:
            fields[key] = payload[key]
    if "rule_profile" in fields and fields["rule_profile"] not in RULE_PROFILES:
        raise ValueError("无效的合规规则画像。")
    if "prompt_text" in payload:
        db.set_prompt_override("platform", platform_id, _clean_prompt(payload["prompt_text"]))
    if fields:
        db.update_prompt_platform(platform_id, fields)
    invalidate_catalog_cache()
    return next(item for item in get_catalog()["platforms"] if item["id"] == platform_id)


def reset_platform_prompt(platform_id: str) -> dict:
    current = db.get_prompt_platform(platform_id)
    if not current:
        raise ValueError("未找到该平台。")
    if current["is_builtin"]:
        db.delete_prompt_override("platform", platform_id)
    else:
        raise ValueError("自定义平台没有可恢复的系统默认提示词。")
    invalidate_catalog_cache()
    return next(item for item in get_catalog()["platforms"] if item["id"] == platform_id)


def set_platform_active(platform_id: str, active: bool) -> dict:
    current = db.get_prompt_platform(platform_id)
    if not current:
        raise ValueError("未找到该平台。")
    if current["is_builtin"] and not active:
        raise ValueError("系统内置平台不能停用。")
    db.update_prompt_platform(platform_id, {"active": bool(active)})
    invalidate_catalog_cache()
    return next(item for item in get_catalog()["platforms"] if item["id"] == platform_id)


def create_scene(platform_id: str, payload: dict) -> dict:
    if not db.get_prompt_platform(platform_id):
        raise ValueError("未找到所属平台。")
    rule_type = str(payload.get("rule_content_type") or "通用")
    if rule_type not in CONTENT_RULE_PROFILES:
        raise ValueError("无效的合规内容类型映射。")
    scene_id = "scene-" + uuid.uuid4().hex
    db.create_prompt_scene(
        scene_id, platform_id, _clean_name(payload.get("name"), "场景名称"),
        str(payload.get("description") or "").strip(), _clean_prompt(payload.get("prompt_text")),
        rule_type, int(payload.get("sort_order") or 100),
    )
    invalidate_catalog_cache()
    _, scene = resolve_scene(platform_id=platform_id, scene_id=scene_id, include_inactive=True)
    return scene


def update_scene(scene_id: str, payload: dict) -> dict:
    current = db.get_prompt_scene(scene_id)
    if not current:
        raise ValueError("未找到该场景。")
    fields: dict[str, Any] = {}
    if "name" in payload:
        if current["is_builtin"] and _clean_name(payload["name"], "场景名称") != current["name"]:
            raise ValueError("系统内置场景不能改名。")
        fields["name"] = _clean_name(payload["name"], "场景名称")
    for key in ("description", "sort_order", "rule_content_type"):
        if key in payload:
            fields[key] = payload[key]
    if "rule_content_type" in fields and fields["rule_content_type"] not in CONTENT_RULE_PROFILES:
        raise ValueError("无效的合规内容类型映射。")
    if "prompt_text" in payload:
        db.set_prompt_override("scene", scene_id, _clean_prompt(payload["prompt_text"]))
    if fields:
        db.update_prompt_scene(scene_id, fields)
    invalidate_catalog_cache()
    platform = db.get_prompt_platform(current["platform_id"])
    _, scene = resolve_scene(platform_id=platform["id"], scene_id=scene_id, include_inactive=True)
    return scene


def reset_scene_prompt(scene_id: str) -> dict:
    current = db.get_prompt_scene(scene_id)
    if not current:
        raise ValueError("未找到该场景。")
    if not current["is_builtin"]:
        raise ValueError("自定义场景没有可恢复的系统默认提示词。")
    db.delete_prompt_override("scene", scene_id)
    invalidate_catalog_cache()
    _, scene = resolve_scene(platform_id=current["platform_id"], scene_id=scene_id, include_inactive=True)
    return scene


def set_scene_active(scene_id: str, active: bool) -> dict:
    current = db.get_prompt_scene(scene_id)
    if not current:
        raise ValueError("未找到该场景。")
    if current["is_builtin"] and not active:
        raise ValueError("系统内置场景不能停用。")
    db.update_prompt_scene(scene_id, {"active": bool(active)})
    invalidate_catalog_cache()
    _, scene = resolve_scene(platform_id=current["platform_id"], scene_id=scene_id, include_inactive=True)
    return scene


def reset_all_builtin_prompts() -> dict:
    db.delete_builtin_prompt_overrides()
    invalidate_catalog_cache()
    return get_catalog()


def catalog_stats() -> dict:
    catalog = get_catalog()
    platforms = catalog["platforms"]
    scenes = [scene for platform in platforms for scene in platform["scenes"]]
    return {
        "prompt_version": catalog["version"],
        "prompt_platform_count": len(platforms),
        "prompt_scene_count": len(scenes),
        "prompt_active_platform_count": sum(bool(item["active"] and any(scene["active"] for scene in item["scenes"])) for item in platforms),
        "prompt_active_scene_count": sum(bool(item["active"]) for item in scenes),
        "prompt_custom_platform_count": sum(not item["is_builtin"] for item in platforms),
        "prompt_custom_scene_count": sum(not item["is_builtin"] for item in scenes),
        "prompt_override_count": int(catalog["base_prompt"]["is_overridden"])
        + sum(bool(item["is_overridden"]) for item in platforms)
        + sum(bool(scene["is_overridden"]) for item in platforms for scene in item["scenes"]),
    }


def generate_ai_draft(payload: dict, settings: dict) -> dict:
    from app.services.llm.provider import build_provider

    target_type = str(payload.get("target_type") or "")
    if target_type not in {"base", "platform", "scene"}:
        raise ValueError("target_type 必须是 base、platform 或 scene。")
    requirements = str(payload.get("requirements") or "").strip()
    if not requirements:
        raise ValueError("请填写希望 AI 遵循的需求约束。")
    if len(requirements) > 5000:
        raise ValueError("需求约束不能超过 5000 个字符。")

    context = dict(payload)
    context["requirements"] = requirements
    catalog = get_catalog(True)
    platform_item = None
    if payload.get("platform_id"):
        platform_item = next(
            (item for item in catalog["platforms"] if item["id"] == payload["platform_id"]),
            None,
        )
        if not platform_item:
            raise ValueError("未找到指定平台。")
        context.update({
            "platform_name": platform_item["name"],
            "platform_description": platform_item["description"],
            "rule_profile": platform_item["rule_profile"],
        })
    if target_type == "scene" and payload.get("scene_id"):
        scene = next(
            (
                scene for item in catalog["platforms"] for scene in item["scenes"]
                if scene["id"] == payload["scene_id"]
            ),
            None,
        )
        if not scene:
            raise ValueError("未找到指定场景。")
        context.update({
            "scene_name": scene["name"],
            "scene_description": scene["description"],
            "rule_content_type": scene["rule_content_type"],
        })
    if target_type == "scene" and platform_item:
        context["parent_prompt"] = platform_item["effective_prompt"]
    elif target_type == "platform":
        context["parent_prompt"] = catalog["base_prompt"]["effective"]

    current_prompt = str(context.get("current_prompt") or "")
    if len(current_prompt) > MAX_PROMPT_LENGTH:
        raise ValueError(f"待优化提示词不能超过 {MAX_PROMPT_LENGTH} 个字符。")
    provider = build_provider(settings)
    if provider.name == "mock":
        raise ValueError("AI 生成提示词仅支持真实模型。请先在设置中启用并配置真实 LLM。")
    draft = _clean_prompt(provider.prompt_draft(context))
    return {
        "draft": draft,
        "target_type": target_type,
        "provider": provider.name,
        "model": str(getattr(provider, "model", provider.name)),
        "saved": False,
    }

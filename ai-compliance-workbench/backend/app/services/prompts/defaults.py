"""Built-in generation prompt catalog sourced from the v1.0 prompt collection."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from app.core import config

PROMPT_VERSION = "v1.0"
SOURCE_FILENAME = "医美内容生成_全场景提示词合集_v1.0.md"

BUILTIN_PLATFORM_IDS = {
    "朋友圈": "builtin-moments",
    "微信社群": "builtin-community",
    "小红书": "builtin-xiaohongshu",
    "微信公众号": "builtin-wechat-article",
    "客服话术": "builtin-customer-service",
}

LEGACY_PLATFORM_FILES = {
    "朋友圈": "moments.md",
    "微信社群": "community.md",
    "小红书": "xiaohongshu.md",
    "微信公众号": "wechat_article.md",
    "客服话术": "customer_service.md",
}

DEFAULT_RULE_PROFILES = {
    "朋友圈": "微信",
    "微信社群": "微信",
    "小红书": "小红书",
    "微信公众号": "微信",
    "客服话术": "微信",
}

LOCKED_SELF_CHECK_FALLBACK = """提交答案前自行检查：
1. 是否符合当前平台和场景的表达习惯。
2. 是否虚构了用户未提供的品牌、资质、价格、数据、案例或活动条件。
3. 是否存在效果、时间、安全或排名保证。
4. 是否只输出最终文案，未附加创作说明。
发现问题时先修正，再输出最终文案。"""

BASE_FALLBACK = """你是一名熟悉中国大陆医美内容传播习惯的资深内容编辑。
请根据系统单独提供的结构化输入写出自然、具体、可直接使用的中文文案。
不得虚构品牌、机构、医生、项目、价格、资质、荣誉、数据、案例或活动条件。
只输出最终文案，不解释写作过程。"""


def _source_path() -> Path | None:
    candidates = [
        config.PROJECT_ROOT.parent / SOURCE_FILENAME,
        config.PROJECT_ROOT / SOURCE_FILENAME,
        config.PROMPTS_DIR / SOURCE_FILENAME,
    ]
    return next((path for path in candidates if path.exists()), None)


def _code_block(section: str) -> str:
    match = re.search(r"```text\s*\n(.*?)\n```", section, flags=re.DOTALL)
    return match.group(1).strip() if match else ""


def _normalize_base(text: str) -> str:
    if not text:
        return BASE_FALLBACK
    text = re.sub(
        r"【输入变量】.*?(?=【去 AI 味规则】)",
        "【输入信息】\n品牌、平台、场景、主题、卖点、受众等信息由系统以结构化用户消息单独提供。\n\n",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"【真实性与合规底线】.*?(?=【输出原则】)",
        "【真实性与合规】\n必须遵循系统在运行时提供的动态合规规则；不得绕过、弱化或改写这些约束。\n\n",
        text,
        flags=re.DOTALL,
    )
    return text.strip()


def _legacy_platform_prompt(platform: str) -> str:
    return (
        f"【平台：{platform}】\n"
        f"请遵循{platform}的真实内容表达习惯。平台共性在本层控制，"
        "具体结构、篇幅和语气以随后提供的场景提示词为准。"
    )


@lru_cache(maxsize=1)
def load_builtin_defaults() -> dict:
    source = _source_path()
    markdown = source.read_text(encoding="utf-8") if source else ""

    base_match = re.search(
        r"^# 二、通用基础提示词\s*(.*?)(?=^# 三、)",
        markdown,
        flags=re.MULTILINE | re.DOTALL,
    )
    base_prompt = _normalize_base(_code_block(base_match.group(1)) if base_match else "")

    self_check_match = re.search(
        r"^# 八、模型输出的统一自检提示词\s*(.*?)(?=^# 九、|\Z)",
        markdown,
        flags=re.MULTILINE | re.DOTALL,
    )
    self_check = _code_block(self_check_match.group(1)) if self_check_match else ""

    platforms: dict[str, dict] = {}
    headings = list(re.finditer(
        r"^# [三四五六七]、(.+?)场景提示词\s*$",
        markdown,
        flags=re.MULTILINE,
    ))
    for index, heading in enumerate(headings):
        platform = heading.group(1).strip()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(markdown)
        section = markdown[heading.end():end]
        scenes: dict[str, str] = {}
        scene_headings = list(re.finditer(r"^## \d+\.\d+\s+(.+?)\s*$", section, flags=re.MULTILINE))
        for scene_index, scene_heading in enumerate(scene_headings):
            scene_end = scene_headings[scene_index + 1].start() if scene_index + 1 < len(scene_headings) else len(section)
            scene_section = section[scene_heading.end():scene_end]
            prompt = _code_block(scene_section)
            if prompt:
                scenes[scene_heading.group(1).strip()] = prompt
        platforms[platform] = {
            "id": BUILTIN_PLATFORM_IDS.get(platform, f"builtin-{len(platforms) + 1}"),
            "prompt": _legacy_platform_prompt(platform),
            "rule_profile": DEFAULT_RULE_PROFILES.get(platform, "通用"),
            "scenes": scenes,
        }

    # Keep the application operable if the source document was not packaged.
    for platform, content_types in config.CONTENT_TYPES.items():
        entry = platforms.setdefault(platform, {
            "id": BUILTIN_PLATFORM_IDS[platform],
            "prompt": _legacy_platform_prompt(platform),
            "rule_profile": DEFAULT_RULE_PROFILES[platform],
            "scenes": {},
        })
        for content_type in content_types:
            entry["scenes"].setdefault(
                content_type,
                f"【场景：{platform}—{content_type}】\n请围绕该场景输出自然、清晰且信息完整的内容。",
            )

    return {
        "version": PROMPT_VERSION,
        "source": source.name if source else "",
        "base_prompt": base_prompt,
        "self_check_prompt": self_check or LOCKED_SELF_CHECK_FALLBACK,
        "platforms": platforms,
    }

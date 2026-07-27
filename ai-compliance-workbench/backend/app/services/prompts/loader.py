"""Prompt 模板加载：从 data/prompts 读取平台与检测模板。"""
import os
from app.core import config

PLATFORM_FILES = {
    "朋友圈": "moments.md",
    "微信社群": "community.md",
    "小红书": "xiaohongshu.md",
    "微信公众号": "wechat_article.md",
    "客服话术": "customer_service.md",
}


def load_prompt_template(platform: str) -> str:
    fname = PLATFORM_FILES.get(platform)
    if not fname:
        return ""
    path = os.path.join(config.PROMPTS_DIR, fname)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return ""


def list_prompt_templates() -> list[dict]:
    out = []
    for plat, fname in PLATFORM_FILES.items():
        path = os.path.join(config.PROMPTS_DIR, fname)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                out.append({"platform": plat, "file": fname, "content": f.read()})
    return out

"""全局配置：路径、运行参数、平台与内容类型定义、风险/动作优先级。"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录：backend/app/core/config.py -> parents[3] = ai-compliance-workbench
_BACKEND = Path(__file__).resolve().parents[2]
PROJECT_ROOT = _BACKEND.parent
DATA_DIR = PROJECT_ROOT / "data"
COMPLIANCE_DIR = DATA_DIR / "compliance"
PROMPTS_DIR = DATA_DIR / "prompts"
BRAND_DIR = DATA_DIR / "brand_profiles"
DEMO_DIR = DATA_DIR / "demo"
DB_PATH = PROJECT_ROOT / "data" / "workbench.db"

load_dotenv(PROJECT_ROOT / ".env")

# ---- 平台与内容类型（权威来源：后端，前端通过 API 获取）----
PLATFORMS = ["朋友圈", "微信社群", "小红书", "微信公众号", "客服话术"]

CONTENT_TYPES: dict[str, list[str]] = {
    "朋友圈": ["日常宣传", "活动预热", "活动通知", "项目介绍", "节日营销"],
    "微信社群": ["群公告", "活动通知", "预约提醒", "用户答疑", "转化话术"],
    "小红书": ["科普笔记", "项目介绍", "体验分享框架", "活动种草", "问答型笔记"],
    "微信公众号": ["科普文章", "活动文章", "品牌文章", "项目说明", "用户须知"],
    "客服话术": ["首次咨询", "项目介绍", "价格咨询", "风险咨询", "预约跟进", "投诉安抚"],
}

# 本工具平台 -> 规则库中 rule_platforms.platform 的取值（用于平台专项规则匹配）
PLATFORM_TO_RULE_PLATFORM = {
    "朋友圈": ["微信"],
    "微信社群": ["微信"],
    "微信公众号": ["微信"],
    "小红书": ["小红书"],
    "客服话术": ["微信"],
}

# 本工具内容类型 -> 规则库中 rule_platforms.content_type 的取值
def map_content_type_to_rule_ct(content_type: str) -> list[str]:
    ct = content_type or ""
    targets = []
    if any(k in ct for k in ("活动", "种草", "营销", "预热")):
        targets.append("广告")
    if any(k in ct for k in ("文章", "科普", "品牌", "须知", "说明")):
        targets.append("文章")
    if any(k in ct for k in ("笔记", "分享", "问答")):
        targets.append("笔记")
    if "项目介绍" in ct or "朋友圈" in ct:
        targets.append("朋友圈")
    if any(k in ct for k in ("直播", "口播")):
        targets.append("直播口播")
    return targets


# ---- 风险与动作优先级 ----
RISK_PRIORITY = {"critical": 4, "high": 3, "medium": 2, "low": 1, "none": 0}

ACTION_PRIORITY = {
    "block": 6,
    "mandatory_human_review": 5,
    "request_qualification": 4,
    "request_evidence": 3,
    "warning": 2,
    "pass": 1,
}

# system_action（规则库字符串） -> 发布建议枚举
ACTION_TO_RECOMMENDATION = {
    "block": "block",
    "mandatory_human_review": "manual_review",
    "request_qualification": "request_evidence",
    "request_evidence": "request_evidence",
    "warning": "warning",
    "pass": "pass",
}

SYSTEM_ACTION_LABELS = {
    "block": "禁止发布",
    "mandatory_human_review": "需人工复核",
    "request_qualification": "需补充资质",
    "request_evidence": "需补充证明",
    "warning": "警示",
    "pass": "通过",
}

RISK_LABELS = {
    "critical": "严重风险",
    "high": "高风险",
    "medium": "中等风险",
    "low": "低风险",
    "none": "未发现明显风险",
}

REVIEW_LEVEL_LABELS = {"L1": "L1", "L2": "L2", "L3": "L3", "L4": "L4"}

DISCLAIMER = "本结果仅用于内容风险筛查，不替代律师、法务、医疗专业人员或监管部门的正式意见。"

# ---- 大模型配置 ----
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1200"))

# ---- 默认工具设置（可被数据库覆盖）----
DEFAULT_SETTINGS = {
    "model_provider": "mock",
    "model_name": LLM_MODEL,
    "api_base": LLM_BASE_URL,
    "temperature": LLM_TEMPERATURE,
    "max_tokens": LLM_MAX_TOKENS,
    "default_brand": "guangnian18",
    "default_platform": "小红书",
    "default_versions": 3,
    "default_tone": "亲切专业",
    "default_length": "中",
    "auto_semantic_check": True,
    "enable_keyword_detection": True,
    "enable_regex_detection": True,
    "enable_semantic_detection": True,
    "auto_generate_revision": True,
    "force_disclaimer": True,
    "save_history": True,
    "max_history": 100,
    "history_retention_days": 90,
}

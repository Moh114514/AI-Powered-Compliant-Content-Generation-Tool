"""全局配置：路径、运行参数、平台与内容类型定义、风险/动作优先级。"""
import os
import shutil
import sys
from pathlib import Path
from dotenv import dotenv_values, load_dotenv

_BACKEND = Path(__file__).resolve().parents[2]
IS_BUNDLED = bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", _BACKEND.parent))

if IS_BUNDLED:
    _default_user_root = Path(
        os.getenv("LOCALAPPDATA")
        or (Path.home() / "AppData" / "Local")
    ) / "AIComplianceWorkbench"
    PROJECT_ROOT = Path(os.getenv("AI_COMPLIANCE_USER_DIR") or _default_user_root)
else:
    PROJECT_ROOT = _BACKEND.parent

DATA_DIR = PROJECT_ROOT / "data"
COMPLIANCE_DIR = DATA_DIR / "compliance"
PROMPTS_DIR = DATA_DIR / "prompts"
BRAND_DIR = DATA_DIR / "brand_profiles"
DEMO_DIR = DATA_DIR / "demo"
DB_PATH = DATA_DIR / "workbench.db"
ENV_PATH = PROJECT_ROOT / ".env"
FRONTEND_DIST_DIR = (
    RESOURCE_ROOT / "frontend_dist"
    if IS_BUNDLED
    else PROJECT_ROOT / "frontend" / "dist"
)
BUNDLED_DATA_DIR = RESOURCE_ROOT / "data"
BUNDLED_ENV_PATH = RESOURCE_ROOT / ".env"


def _materialize_bundled_env() -> bool:
    """Install the internal default environment on first bundled launch only."""
    if not IS_BUNDLED or ENV_PATH.exists() or not BUNDLED_ENV_PATH.is_file():
        return False
    PROJECT_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUNDLED_ENV_PATH, ENV_PATH)
    return True


_materialize_bundled_env()
_PROCESS_LLM_API_KEY = os.getenv("LLM_API_KEY", "")
load_dotenv(ENV_PATH)

def prepare_runtime_files() -> None:
    """Materialize bundled read-only assets into the user's writable data folder."""
    if not IS_BUNDLED:
        return
    PROJECT_ROOT.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if BUNDLED_DATA_DIR.exists():
        shutil.copytree(BUNDLED_DATA_DIR, DATA_DIR, dirs_exist_ok=True)
    _materialize_bundled_env()
    bundled_env_example = RESOURCE_ROOT / ".env.example"
    user_env_example = PROJECT_ROOT / ".env.example"
    if bundled_env_example.exists() and not user_env_example.exists():
        shutil.copy2(bundled_env_example, user_env_example)

PLATFORMS = ["朋友圈", "微信社群", "小红书", "微信公众号", "客服话术"]

CONTENT_TYPES: dict[str, list[str]] = {
    "朋友圈": ["日常宣传", "活动预热", "活动通知", "项目介绍", "节日营销"],
    "微信社群": ["群公告", "活动通知", "预约提醒", "用户答疑", "转化话术"],
    "小红书": ["科普笔记", "项目介绍", "体验分享框架", "活动种草", "问答型笔记"],
    "微信公众号": ["科普文章", "活动文章", "品牌文章", "项目说明", "用户须知"],
    "客服话术": ["首次咨询", "项目介绍", "价格咨询", "风险咨询", "预约跟进", "投诉安抚"],
}

PLATFORM_TO_RULE_PLATFORM = {
    "朋友圈": ["微信"],
    "微信社群": ["微信"],
    "微信公众号": ["微信"],
    "小红书": ["小红书"],
    "客服话术": ["微信"],
    # 规则库回归样本使用平台族名称，而产品 UI 使用具体内容场景。
    "微信": ["微信"],
    "抖音": ["抖音"],
}

PLATFORM_PRODUCT_LINE_HINTS = {
    "朋友圈": ["朋友圈个人内容", "朋友圈付费广告"],
    "微信社群": ["微信社群", "私信及客服"],
    "微信公众号": ["微信公众号自然内容"],
    "小红书": ["自然笔记", "商业合作", "聚光广告", "电商", "直播"],
    "客服话术": ["私信及客服", "微信社群"],
}


def map_content_type_to_rule_ct(content_type: str) -> list[str]:
    """将产品侧内容类型映射到规则库 content_type。

    历史规则粒度不完全统一；无法可靠映射时返回空数组，检测引擎将退化为仅按平台筛选。
    """
    content_type = (content_type or "").strip()
    targets: list[str] = []
    if any(key in content_type for key in ("活动", "营销", "种草", "预热", "转化", "节日")):
        targets.extend(["广告", "推广", "活动"])
    if any(key in content_type for key in ("文章", "科普", "品牌", "须知", "说明")):
        targets.extend(["文章", "科普"])
    if any(key in content_type for key in ("笔记", "分享", "问答")):
        targets.extend(["笔记", "内容"])
    if any(key in content_type for key in ("群公告", "预约提醒", "用户答疑", "社群")):
        targets.extend(["社群消息", "群聊", "客服话术"])
    if any(key in content_type for key in ("咨询", "跟进", "投诉", "话术")):
        targets.extend(["客服话术", "私信", "咨询"])
    if "项目介绍" in content_type:
        targets.extend(["朋友圈", "文章", "笔记", "广告"])
    if any(key in content_type for key in ("直播", "口播")):
        targets.extend(["直播", "直播口播"])
    return list(dict.fromkeys(targets))


RISK_PRIORITY = {"critical": 4, "high": 3, "medium": 2, "low": 1, "none": 0}
# L1 最严格，不能按字符串中的数字直接取最大值。
REVIEW_PRIORITY = {"L1": 4, "L2": 3, "L3": 2, "L4": 1, "": 0}

ACTION_PRIORITY = {
    "block": 6,
    "mandatory_human_review": 5,
    "request_qualification": 4,
    "request_evidence": 3,
    "warning": 2,
    "pass": 1,
}

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

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))


def get_llm_api_key() -> str:
    """Return the current key without requiring a backend restart after .env changes."""
    if _PROCESS_LLM_API_KEY:
        return _PROCESS_LLM_API_KEY
    values = dotenv_values(ENV_PATH)
    return str(values.get("LLM_API_KEY") or "").strip()

DEFAULT_SETTINGS = {
    "model_provider": "openai_compatible" if get_llm_api_key() else "mock",
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
    # 改写应由用户显式触发，避免每次检测额外调用模型。
    "auto_generate_revision": False,
    "force_disclaimer": True,
    "save_history": True,
    "max_history": 100,
    "history_retention_days": 90,
}

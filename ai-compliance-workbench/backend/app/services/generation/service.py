"""生成服务：组装 平台Prompt + 品牌配置 + Provider + 合规检测。
流程：用户输入 → 加载平台Prompt → 加载品牌配置 → 筛选规则(引擎内) → 调用生成 → 关键词/正则/语义检测 → 聚合 → 返回版本列表。
"""
import datetime
from app.core.data_loader import get_store
from app.services.prompts.loader import load_prompt_template
from app.services.brands.loader import get_brand
from app.services.compliance.engine import run_compliance_check
from app.services.llm.provider import build_provider


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def generate(request: dict, settings: dict) -> dict:
    store = get_store()
    platform = request.get("platform")
    content_type = request.get("content_type")
    brand_id = request.get("brand")
    use_brand = request.get("use_brand_profile", True)
    versions = int(request.get("versions") or settings.get("default_versions", 3) or 3)

    brand_profile = get_brand(brand_id) if use_brand else None
    prompt_template = load_prompt_template(platform)
    provider = build_provider(settings)

    copies = provider.generate(
        platform=platform, content_type=content_type, inputs=request,
        prompt_template=prompt_template, brand_profile=brand_profile, versions=versions,
    )

    result_versions = []
    for i, text in enumerate(copies, 1):
        compliance = run_compliance_check(
            text=text, platform=platform, content_type=content_type,
            brand=brand_id, store=store, provider=provider, settings=settings,
        )
        result_versions.append({
            "version_index": i,
            "text": text,
            "platform": platform,
            "content_type": content_type,
            "char_count": len(text),
            "generated_at": _now(),
            "model": provider.name,
            "overall_risk_level": compliance["overall_risk_level"],
            "matched_count": len(compliance["matched_rules"]),
            "manual_review_required": compliance["manual_review_required"],
            "compliance": compliance,
        })

    return {
        "platform": platform,
        "content_type": content_type,
        "brand": brand_id,
        "model": provider.name,
        "demo_mode": provider.name == "mock",
        "versions": result_versions,
        "disclaimer": compliance_disclaimer(),
    }


def rewrite(request: dict, settings: dict) -> dict:
    store = get_store()
    text = request.get("text", "")
    platform = request.get("platform")
    content_type = request.get("content_type")
    provider = build_provider(settings)
    compliance = run_compliance_check(
        text=text, platform=platform, content_type=content_type,
        brand=request.get("brand"), store=store, provider=provider, settings=settings,
    )
    rev = provider.rewrite(
        text=text, matched_rules=compliance["matched_rules"],
        platform=platform, content_type=content_type,
    )
    rev["compliance"] = compliance
    rev["demo_mode"] = provider.name == "mock"
    rev["disclaimer"] = compliance_disclaimer()
    return rev


def adjust(request: dict, settings: dict) -> dict:
    store = get_store()
    text = request.get("text", "")
    platform = request.get("platform")
    content_type = request.get("content_type")
    adjust_type = request.get("adjust_type", "缩短")
    provider = build_provider(settings)

    inputs = {
        "topic": request.get("topic", ""),
        "selling_points": text,
        "target_audience": request.get("target_audience", ""),
        "campaign_info": request.get("campaign_info", ""),
        "tone": request.get("tone", settings.get("default_tone", "亲切专业")),
        "length": request.get("length", settings.get("default_length", "中")),
        "extra_requirements": request.get("extra_requirements", ""),
    }
    if adjust_type == "缩短":
        inputs["length"] = "短"
    elif adjust_type == "扩写":
        inputs["length"] = "长"
    # 调整语气：在补充要求中提示
    inputs["extra_requirements"] = (inputs["extra_requirements"] + f"；语气调整为：{request.get('tone', '专业温和')}").strip("；")

    copies = provider.generate(
        platform=platform, content_type=content_type, inputs=inputs,
        prompt_template=load_prompt_template(platform),
        brand_profile=get_brand(request.get("brand")), versions=1,
    )
    new_text = copies[0] if copies else text
    compliance = run_compliance_check(
        text=new_text, platform=platform, content_type=content_type,
        brand=request.get("brand"), store=store, provider=provider, settings=settings,
    )
    return {
        "text": new_text,
        "platform": platform,
        "content_type": content_type,
        "model": provider.name,
        "demo_mode": provider.name == "mock",
        "compliance": compliance,
        "disclaimer": compliance_disclaimer(),
    }


def compliance_disclaimer() -> str:
    from app.core import config
    return config.DISCLAIMER

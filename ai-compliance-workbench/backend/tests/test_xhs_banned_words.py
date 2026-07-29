"""小红书专项违禁词库接入、语境分级与替换建议测试。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.data_loader import load_data
from app.main import app
from app.services.compliance.engine import run_compliance_check


SETTINGS = {
    "enable_keyword_detection": True,
    "enable_regex_detection": True,
    "enable_semantic_detection": False,
    "auto_generate_revision": False,
}


def check(text: str, platform: str = "小红书", content_type: str = "项目介绍") -> dict:
    return run_compliance_check(
        text=text,
        platform=platform,
        content_type=content_type,
        store=load_data(),
        settings=SETTINGS,
    )


def test_banned_word_library_counts_and_replacements():
    store = load_data()
    assert store.xhs_banned_word_stats["valid"]
    assert store.xhs_banned_word_stats["record_count"] == 174
    assert store.xhs_banned_word_stats["variant_count"] == 193
    assert store.xhs_banned_word_stats["unique_term_count"] == 311
    assert all(str(item.get("replacement") or "").strip() for item in store.xhs_banned_words)
    assert len(store.xhs_banned_words_sha256) == 64


def test_strict_terms_affect_risk_and_expose_replacements():
    result = check("全网最低，零风险，还可以加V领取优惠。")
    assert result["overall_risk_level"] in {"critical", "high"}
    assert result["publish_recommendation"] == "block"
    hits = result["banned_word_hits"]
    assert {item["matched_text"] for item in hits} >= {"全网最低", "零风险", "加V"}
    assert all(item["replacements"] for item in hits)
    assert all(item["sources"] and item["source_ids"] for item in hits)


def test_neutral_context_is_reviewed_instead_of_blocked_by_banned_word_layer():
    samples = [
        "处方药须由执业医师评估后使用。",
        "本次免费皮肤检测不含治疗。",
        "热玛吉通过射频原理作用于皮肤，以下仅作项目原理科普。",
    ]
    for text in samples:
        result = check(text)
        assert result["banned_word_hits"], text
        assert all(item["risk_level"] == "medium" for item in result["banned_word_hits"])
        assert all(item["requires_review"] for item in result["banned_word_hits"])
        assert all(item["context_classification"] == "neutral" for item in result["banned_word_hits"])
        assert result["publish_recommendation"] != "block"


def test_single_character_superlative_does_not_match_common_words():
    for text in ("最近天气不错。", "最后说明注意事项。", "最初需要进行专业评估。"):
        result = check(text)
        assert not any("BW0120" in item["source_ids"] for item in result["banned_word_hits"])


def test_risky_superlative_still_matches():
    result = check("这是全城最好的项目。")
    hit = next(item for item in result["banned_word_hits"] if item["matched_text"] == "最好")
    assert hit["risk_level"] == "high"


def test_exact_duplicate_terms_merge_sources_and_longest_span_wins():
    duplicate = check("加V领取资料。")["banned_word_hits"]
    hit = next(item for item in duplicate if item["matched_text"] == "加V")
    assert {"BW0098", "BW0114"} <= set(hit["source_ids"])

    longest = check("水光针项目需由医生评估。")["banned_word_hits"]
    assert any(item["matched_text"] == "水光针" for item in longest)
    assert not any(item["matched_text"] == "水光" for item in longest)


def test_xhs_library_is_platform_scoped():
    assert check("加V领取资料。", platform="朋友圈", content_type="项目介绍")["banned_word_hits"] == []
    assert check("加V领取资料。", platform="小红书", content_type="项目介绍")["banned_word_hits"]


def test_custom_platform_mapped_to_xhs_uses_library(monkeypatch):
    from app.services.prompts import catalog

    monkeypatch.setattr(
        catalog,
        "rule_mapping",
        lambda platform, content_type: (["小红书"], []) if platform == "自定义社区" else ([], []),
    )
    result = run_compliance_check(
        text="欢迎加V领取资料。",
        platform="自定义社区",
        content_type="项目介绍",
        store=load_data(),
        settings=SETTINGS,
    )
    assert result["banned_word_hits"]


def test_sensitive_source_level_remains_medium():
    result = check("推荐体验光子嫩肤活动。")
    hit = next(item for item in result["banned_word_hits"] if item["matched_text"] == "光子嫩肤")
    assert hit["source_risk_levels"] == ["敏感"]
    assert hit["risk_level"] == "medium"
    assert hit["requires_review"] is True


def test_status_and_api_contract_include_banned_word_data():
    with TestClient(app) as client:
        status = client.get("/api/status").json()["data"]
        assert status["xhs_banned_words_version"] == "v1.0"
        assert status["xhs_banned_word_count"] == 174
        assert status["xhs_banned_variant_count"] == 193
        assert status["xhs_banned_unique_term_count"] == 311

        result = client.post("/api/compliance/check", json={
            "text": "全网最低，欢迎加V。",
            "platform": "小红书",
            "content_type": "项目介绍",
        }).json()["data"]
        assert result["banned_word_hits"]
        hit = result["banned_word_hits"][0]
        for field in (
            "hit_id", "matched_text", "canonical_word", "start", "end", "domain",
            "risk_level", "reason", "replacements", "sources", "source_ids",
            "context_classification", "requires_review",
        ):
            assert field in hit


class RecordingProvider:
    name = "recording"

    def __init__(self):
        self.rewrite_rules: list[dict] = []

    def semantic_check(self, **_kwargs):
        return {"semantic_findings": [], "analysis_failed": False}

    def rewrite(self, text, matched_rules, platform, content_type):
        self.rewrite_rules = matched_rules
        return {"suggested_revision": "欢迎阅读项目介绍。"}


def test_auto_rewrite_receives_banned_word_replacements():
    provider = RecordingProvider()
    settings = dict(SETTINGS, auto_generate_revision=True)
    result = run_compliance_check(
        text="欢迎加V领取资料。",
        platform="小红书",
        content_type="项目介绍",
        store=load_data(),
        provider=provider,
        settings=settings,
    )
    assert result["suggested_revision"]
    xhs_rules = [item for item in provider.rewrite_rules if item["rule_name"].startswith("小红书专项词")]
    assert xhs_rules
    assert xhs_rules[0]["replacement_strategy"]

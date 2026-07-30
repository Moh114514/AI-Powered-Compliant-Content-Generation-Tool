"""API 输入约束与响应契约测试。"""
import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.main import app
from app.repositories import db
from app.services.llm.provider import MockProvider, OpenAICompatibleProvider, build_provider


def mock_settings(**overrides):
    settings = dict(config.DEFAULT_SETTINGS)
    settings.update({"model_provider": "mock", "save_history": False})
    settings.update(overrides)
    return settings


def test_empty_compliance_text_is_rejected():
    with TestClient(app) as client:
        response = client.post("/api/compliance/check", json={
            "text": "   ",
            "platform": "小红书",
            "content_type": "项目介绍",
        })
        assert response.status_code == 422


def test_invalid_platform_content_type_pair_is_rejected():
    with TestClient(app) as client:
        response = client.post("/api/generation/generate", json={
            "platform": "朋友圈",
            "content_type": "科普笔记",
            "topic": "测试",
            "versions": 1,
        })
        assert response.status_code == 422


def test_status_exposes_quality_counts():
    with TestClient(app) as client:
        payload = client.get("/api/status").json()
        assert payload["success"] is True
        for key in (
            "rule_count",
            "variant_count",
            "test_case_count",
            "validation_warning_count",
            "pending_review_count",
            "thinking_enabled",
        ):
            assert key in payload["data"]
        assert payload["data"]["pending_review_count"] == 56


def test_rule_list_supports_pagination():
    with TestClient(app) as client:
        payload = client.get("/api/compliance/rules?offset=0&limit=2").json()
        assert payload["success"] is True
        assert len(payload["data"]["rules"]) <= 2
        assert payload["data"]["limit"] == 2


@pytest.mark.parametrize("adjust_type", ["缩短", "扩写"])
def test_adjust_only_transforms_current_copy(adjust_type, monkeypatch):
    monkeypatch.setattr(db, "load_settings", lambda: mock_settings())
    source = (
        "这是一段当前版本文案，用于介绍项目的基本流程。"
        "发布前需要确认适用条件与注意事项。"
        "具体方案应结合个人情况进行专业评估。"
    )
    with TestClient(app) as client:
        payload = client.post("/api/generation/adjust", json={
            "text": source,
            "platform": "小红书",
            "content_type": "项目介绍",
            "brand": "guangnian18",
            "adjust_type": adjust_type,
            "topic": "不应混入调整稿的旧主题",
            "target_audience": "不应混入调整稿的旧人群",
            "campaign_info": "不应混入调整稿的旧活动",
            "tone": "亲切专业",
        }).json()

    assert payload["success"] is True
    adjusted = payload["data"]["text"]
    assert payload["data"]["original_text"] == source
    assert payload["data"]["adjust_type"] == adjust_type
    assert "不应混入调整稿" not in adjusted
    if adjust_type == "缩短":
        assert len(adjusted) < len(source)
        assert source not in adjusted
    else:
        assert len(adjusted) > len(source)
        assert adjusted.count(source) == 1


def test_real_provider_never_silently_falls_back_to_mock(monkeypatch):
    monkeypatch.setattr(config, "get_llm_api_key", lambda: "")
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        build_provider(mock_settings(model_provider="openai_compatible"))

    monkeypatch.setattr(config, "get_llm_api_key", lambda: "test-key")
    provider = build_provider(mock_settings(
        model_provider="openai_compatible",
        api_base="https://example.invalid/v1",
        model_name="test-model",
        enable_thinking=True,
    ))
    assert isinstance(provider, OpenAICompatibleProvider)
    assert not isinstance(provider, MockProvider)
    assert provider.enable_thinking is True


def test_generation_is_automatically_saved_when_history_is_enabled(monkeypatch):
    captured = {}

    def fake_add_record(**kwargs):
        captured.update(kwargs)
        return "R-AUTO-001"

    monkeypatch.setattr(db, "load_settings", lambda: mock_settings(save_history=True))
    monkeypatch.setattr(db, "add_record", fake_add_record)

    with TestClient(app) as client:
        payload = client.post("/api/generation/generate", json={
            "platform": "小红书",
            "content_type": "项目介绍",
            "topic": "自动保存测试",
            "versions": 1,
        }).json()

    assert payload["success"] is True
    assert payload["data"]["history_saved"] is True
    assert payload["data"]["history_record_id"] == "R-AUTO-001"
    assert captured["operation_type"] == "generation"
    assert captured["generated"]["versions"]

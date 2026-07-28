"""API 输入约束与响应契约测试。"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


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
def test_adjust_only_transforms_current_copy(adjust_type):
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

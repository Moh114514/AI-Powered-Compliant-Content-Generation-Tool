"""API 输入约束与响应契约测试。"""
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

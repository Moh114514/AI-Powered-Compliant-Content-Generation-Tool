"""针对聚合、降级与回归接口的补充测试。"""
from __future__ import annotations

import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.data_loader import DataStore
from app.main import app
from app.services.compliance.engine import run_compliance_check
from app.services.compliance.evaluator import _risk_matches


BASE_SETTINGS = {
    "enable_keyword_detection": True,
    "enable_regex_detection": True,
    "enable_semantic_detection": False,
    "auto_generate_revision": False,
}


def synthetic_store(*, pending=False) -> DataStore:
    status = "pending_review" if pending else "active"
    store = DataStore(
        rules=[
            {
                "rule_id": "R-TEST-001", "rule_name": "无风险承诺", "category_name": "安全承诺",
                "risk_level": "critical", "review_level": "L1", "system_action": "block",
                "effective_status": status, "manual_review_required": False,
            },
            {
                "rule_id": "R-TEST-002", "rule_name": "绝对化表达", "category_name": "绝对化表达",
                "risk_level": "high", "review_level": "L4", "system_action": "warning",
                "effective_status": "active", "manual_review_required": False,
            },
        ],
        variants=[
            {"variant_id": "V-TEST-001", "rule_id": "R-TEST-001", "variant_text": "零风险", "matching_method": "exact"},
            {"variant_id": "V-TEST-002", "rule_id": "R-TEST-002", "variant_text": "零风险", "matching_method": "contains"},
        ],
    )
    store.rules_by_id = {rule["rule_id"]: rule for rule in store.rules}
    store.variants_by_rule = {
        "R-TEST-001": [store.variants[0]],
        "R-TEST-002": [store.variants[1]],
    }
    return store


def test_overlapping_rules_are_preserved_and_l1_is_highest():
    result = run_compliance_check(
        text="本项目零风险", platform="小红书", content_type="项目介绍",
        store=synthetic_store(), provider=None, settings=BASE_SETTINGS,
    )
    assert {item["rule_id"] for item in result["matched_rules"]} == {"R-TEST-001", "R-TEST-002"}
    assert result["review_level"] == "L1"
    assert result["overall_risk_level"] == "critical"
    assert result["publish_recommendation"] == "block"


def test_pending_review_rule_forces_manual_review():
    result = run_compliance_check(
        text="本项目零风险", platform="小红书", content_type="项目介绍",
        store=synthetic_store(pending=True), provider=None, settings=BASE_SETTINGS,
    )
    hit = next(item for item in result["matched_rules"] if item["rule_id"] == "R-TEST-001")
    assert hit["manual_review_required"] is True
    assert "mandatory_human_review" in hit["system_action"]
    assert result["manual_review_required"] is True


class SemanticOnlyProvider:
    def semantic_check(self, **kwargs):
        return {
            "semantic_findings": [{
                "semantic_rule_id": "SR-TEST", "semantic_rule_name": "隐含效果保证",
                "risk_level": "high", "matched_text": "效果很惊人",
                "risk_reason": "存在隐含效果保证", "manual_review": True,
            }],
            "needs_manual_review": True,
            "manual_review_reason": "需确认效果依据",
        }

    def rewrite(self, **kwargs):
        return {}


class FailingSemanticProvider:
    def semantic_check(self, **kwargs):
        raise RuntimeError("provider unavailable")

    def rewrite(self, **kwargs):
        return {}


def test_semantic_only_finding_affects_risk_and_action():
    store = DataStore(semantic_rules=[{"semantic_rule_id": "SR-TEST", "semantic_rule_name": "隐含效果保证"}])
    result = run_compliance_check(
        text="做完以后效果很惊人", platform="小红书", content_type="项目介绍",
        store=store, provider=SemanticOnlyProvider(),
        settings={**BASE_SETTINGS, "enable_semantic_detection": True},
    )
    assert result["overall_risk_level"] == "high"
    assert result["publish_recommendation"] == "manual_review"
    assert result["manual_review_required"] is True


def test_semantic_failure_never_silently_passes():
    store = DataStore(semantic_rules=[{"semantic_rule_id": "SR-TEST", "semantic_rule_name": "测试"}])
    result = run_compliance_check(
        text="普通待检测文本", platform="小红书", content_type="项目介绍",
        store=store, provider=FailingSemanticProvider(),
        settings={**BASE_SETTINGS, "enable_semantic_detection": True},
    )
    assert result["semantic_analysis_failed"] is True
    assert result["manual_review_required"] is True
    assert result["publish_recommendation"] == "manual_review"
    assert any(issue["issue_type"] == "检测能力降级" for issue in result["manual_review_issues"])


def test_regression_suite_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/compliance/test-suite?limit=2")
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["data"]["total"] == 2
        assert "pass_rate" in payload["data"]


def test_regression_low_risk_accepts_runtime_none():
    assert _risk_matches("low", "none") is True
    assert _risk_matches("critical", "none") is False

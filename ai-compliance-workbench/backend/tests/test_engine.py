"""后端测试：覆盖规则加载、ID完整性、各类匹配、平台筛选、聚合、API、MockProvider、历史、校验。"""
import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.data_loader import load_data, get_store, validate_store
from app.services.compliance import engine
from app.services.llm.provider import MockProvider
from app.repositories import db
from app.main import app
from app.core import config

SETTINGS = {
    "enable_keyword_detection": True,
    "enable_regex_detection": True,
    "enable_semantic_detection": True,
    "auto_generate_revision": True,
}


@pytest.fixture(scope="module")
def store():
    return load_data()


@pytest.fixture(scope="module")
def provider():
    return MockProvider()


@pytest.fixture
def isolated_history_db(tmp_path, monkeypatch):
    db.close_db()
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "history-test.db")
    db.init_db()
    yield
    db.close_db()


def _check(text, platform="小红书", content_type="项目介绍", provider=None, store=None):
    store = store or get_store()
    provider = provider or MockProvider()
    return engine.run_compliance_check(
        text=text, platform=platform, content_type=content_type,
        store=store, provider=provider, settings=SETTINGS,
    )


def _unrestricted_variant(store, method=None, has_source=False, risk_level=None):
    """选取一个非平台受限规则的变体（确保适用于测试平台）。"""
    for v in store.variants:
        rid = v.get("rule_id")
        if rid in store.platforms_by_rule:
            continue
        if method and v.get("matching_method") != method:
            continue
        if has_source and not store.sources_by_rule.get(rid):
            continue
        if risk_level and store.rules_by_id.get(rid, {}).get("risk_level") != risk_level:
            continue
        if v.get("regex_pattern"):
            continue
        if v.get("variant_text"):
            return v
    return None


# 1. 规则 JSON 加载
def test_rule_load(store):
    assert len(store.rules) > 0
    assert len(store.variants) > 0


# 2. ID 引用完整性
def test_id_integrity(store):
    v = validate_store(store)
    assert v["valid"], v["errors"]


# 3. 精确关键词匹配
def test_exact_match(store, provider):
    v = _unrestricted_variant(store, method="exact")
    assert v, "无可用 exact 变体"
    text = f"这是{v['variant_text']}的示例"
    res = _check(text, store=store, provider=provider)
    assert any(m["rule_id"] == v["rule_id"] for m in res["matched_rules"])


# 4. 包含匹配
def test_contains_match(store, provider):
    v = _unrestricted_variant(store, method="contains")
    assert v, "无可用 contains 变体"
    text = f"我们觉得{v['variant_text']}真的很好"
    res = _check(text, store=store, provider=provider)
    assert any(m["rule_id"] == v["rule_id"] for m in res["matched_rules"])


@pytest.mark.parametrize("text", [
    "在决定尝试任何光电项目前，到店评估是必要的第一步。",
    "术后护理第一天：按医嘱冰敷、避免沾水。",
    "第一次咨询会先说明流程、风险和注意事项。",
    "该设备按照第一类医疗器械相关要求管理。",
    "方案第一部分介绍适用情况，第二部分说明注意事项。",
])
def test_ordinal_first_is_not_treated_as_top_rank(text, store, provider):
    res = _check(text, store=store, provider=provider)
    assert not any(item["rule_id"] == "R-A01-002" for item in res["matched_rules"])


@pytest.mark.parametrize("text", [
    "我们是行业第一的医美机构。",
    "本市排名第一，值得所有人选择。",
    "这是一家第一品牌医美机构。",
])
def test_first_still_matches_when_used_as_rank_claim(text, store, provider):
    res = _check(text, store=store, provider=provider)
    assert any(item["rule_id"] == "R-A01-002" for item in res["matched_rules"])


@pytest.mark.parametrize(("text", "platform", "content_type", "rule_id"), [
    ("不是所有人都适合注射玻尿酸，需经医生评估", "抖音", "适应证提示", "R-A01-005"),
    ("术前请如实告知过敏史、用药史及既往手术史", "微信", "术前提醒", "R-A15-104"),
    ("如需了解项目是否适合您，可先预约一次免费面诊", "微信", "预约引导", "R-A08-103"),
    ("请根据皮肤耐受度选择最佳舒适度档位", "微信", "使用提示", "R-A01-001"),
    (
        "本院与XX大学附属医院签订合作协议，合作期限：2024-2027",
        "小红书",
        "合作展示",
        "R-A06-007",
    ),
])
def test_reviewed_safe_context_does_not_trigger_keyword_rule(
    text, platform, content_type, rule_id, store, provider
):
    res = _check(text, platform=platform, content_type=content_type, store=store, provider=provider)
    assert not any(item["rule_id"] == rule_id for item in res["matched_rules"])


@pytest.mark.parametrize(("text", "rule_id"), [
    ("我们的项目所有人都适合，无需评估。", "R-A01-005"),
    ("这项治疗可以带来最佳效果。", "R-A01-001"),
    ("限时免费面诊，先到先得。", "R-A08-103"),
    ("公开展示顾客过敏史作为案例。", "R-A15-104"),
    ("本院与XX大学附属医院战略合作。", "R-A06-007"),
])
def test_context_exclusions_do_not_hide_real_risk(text, rule_id, store, provider):
    platform = "微信" if rule_id == "R-A15-104" else "小红书"
    content_type = "图文" if rule_id == "R-A15-104" else "项目介绍"
    res = _check(text, platform=platform, content_type=content_type, store=store, provider=provider)
    assert any(item["rule_id"] == rule_id for item in res["matched_rules"])


# 5. 正则匹配
def test_regex_match(store, provider):
    v = next((x for x in store.variants if x.get("regex_pattern")), None)
    assert v
    text = "我们就是 No.1 的选择"
    res = _check(text, store=store, provider=provider)
    assert any(m["rule_id"] == v["rule_id"] for m in res["matched_rules"])


# 6. 多规则同时命中
def test_multi_rule(store, provider):
    v1 = _unrestricted_variant(store, method="exact")
    assert v1
    v2 = None
    for v in store.variants:
        rid = v.get("rule_id")
        if rid in store.platforms_by_rule or v.get("regex_pattern"):
            continue
        if v.get("matching_method") != "contains" or not v.get("variant_text"):
            continue
        if rid == v1["rule_id"]:
            continue
        v2 = v
        break
    assert v2, "无第二规则的可匹配 contains 变体"
    text = f"{v1['variant_text']}并且{v2['variant_text']}确实不错"
    res = _check(text, store=store, provider=provider)
    assert len(res["matched_rules"]) >= 2, [(m["rule_id"], m["matched_text"]) for m in res["matched_rules"]]


# 7. 平台筛选（受限规则不污染没有任何平台交集的场景）
def test_platform_filter(store, provider):
    restricted = [r for r in store.rules if store.platforms_by_rule.get(r["rule_id"])]
    if not restricted:
        pytest.skip("无平台受限规则")

    selected = None
    target = None
    for rule in restricted:
        entries = store.platforms_by_rule[rule["rule_id"]]
        rule_platforms = {
            entry.get("platform")
            for entry in entries
            if entry.get("platform")
            and str(entry.get("effective_status") or "active").lower()
            not in {"suspended", "superseded", "abolished", "inactive", "disabled"}
        }
        candidate = next(
            (
                platform
                for platform in config.PLATFORMS
                if not set(config.PLATFORM_TO_RULE_PLATFORM.get(platform, [])) & rule_platforms
            ),
            None,
        )
        variant = next(
            (x for x in store.variants_by_rule.get(rule["rule_id"], []) if x.get("variant_text")),
            None,
        )
        if candidate and variant:
            selected = (rule, variant)
            target = candidate
            break

    if not selected or not target:
        pytest.skip("没有可构造的无平台交集对照样本")

    rule, variant = selected
    res = _check(f"示例{variant['variant_text']}示例", platform=target, store=store, provider=provider)
    assert not any(m["rule_id"] == rule["rule_id"] for m in res["matched_rules"])


# 8. 来源关联
def test_source_association(store, provider):
    v = _unrestricted_variant(store, method="exact", has_source=True)
    assert v, "无带来源的 exact 变体"
    res = _check(f"包含{v['variant_text']}的文本", store=store, provider=provider)
    hit = next((m for m in res["matched_rules"] if m["rule_id"] == v["rule_id"]), None)
    assert hit and hit["source_ids"], "命中规则应有关联来源"


# 9. 严重风险聚合
def test_critical_aggregation(store, provider):
    v = _unrestricted_variant(store, method="exact", risk_level="critical")
    assert v, "无 critical 的 exact 变体"
    res = _check(f"文本{v['variant_text']}文本", store=store, provider=provider)
    assert res["overall_risk_level"] == "critical"


# 10. 无命中结果：使用不含广告动作词的中性说明，避免把边界场景误当作纯净样本
def test_no_hit(store, provider):
    res = _check(
        "项目流程、适用人群与注意事项需由专业医师结合个人情况评估。",
        store=store,
        provider=provider,
    )
    assert res["overall_risk_level"] == "none"
    assert res["manual_review_required"] is False
    assert not res["matched_rules"]
    assert not res["semantic_findings"]


# 11. Unicode 与中文标点
def test_chinese_punctuation(store, provider):
    v = _unrestricted_variant(store, method="exact")
    assert v
    text = f"这里，{v['variant_text']}！真的很好。"
    res = _check(text, store=store, provider=provider)
    assert any(m["rule_id"] == v["rule_id"] for m in res["matched_rules"])
    hit = next(m for m in res["matched_rules"] if m["rule_id"] == v["rule_id"])
    assert hit["matched_text"] == v["variant_text"]


# 12. 重复命中去重
def test_dedup(store, provider):
    v = _unrestricted_variant(store, method="exact")
    assert v
    text = f"{v['variant_text']}重复{v['variant_text']}"
    res = _check(text, store=store, provider=provider)
    cnt = sum(1 for m in res["matched_rules"] if m["rule_id"] == v["rule_id"])
    assert cnt == 1
    hit = next(m for m in res["matched_rules"] if m["rule_id"] == v["rule_id"])
    assert len(hit["spans"]) >= 2
    assert hit["occurrence_count"] == len(hit["spans"])


# 13. API 正常响应
def test_api_health():
    c = TestClient(app)
    r = c.get("/api/health")
    assert r.status_code == 200 and r.json()["success"]


# 14. API 错误响应（非法请求体）
def test_api_error():
    c = TestClient(app)
    r = c.post("/api/compliance/check", json={"text": "x"})
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        assert r.json()["success"] is False


# 15. MockProvider
def test_mock_provider():
    p = MockProvider()
    copies = p.generate("小红书", "项目介绍", {"topic": "t", "selling_points": "最好"}, "", {}, 3)
    assert len(copies) == 3
    res = p.semantic_check("保证效果零风险", "小红书", "项目介绍", [], [])
    assert isinstance(res["semantic_findings"], list)


# 16. 历史保存
def test_history_save(isolated_history_db):
    rid = db.add_record("check", "guangnian18", "小红书", {"text": "t"}, None, {"overall_risk_level": "low"}, "low")
    assert rid
    rec = db.get_record(rid)
    assert rec and rec["id"] == rid


# 17. 历史删除
def test_history_delete(isolated_history_db):
    rid = db.add_record("check", "vyno", "朋友圈", {"text": "t2"}, None, {}, "none")
    assert db.delete_record(rid)
    assert db.get_record(rid) is None


# 18. 复核摘要生成
def test_review_summary(store, provider):
    from app.services.export import service as es
    res = _check("国家级保证零风险", store=store, provider=provider)
    summary = es.build_review_summary(res)
    assert "人工复核摘要" in summary
    assert res["manual_review_required"]


# 19. 规则库重新加载
def test_reload():
    from app.core.data_loader import reload
    s = reload()
    assert s.validation["valid"]


# 20. 数据校验结果
def test_validation_result():
    s = get_store()
    v = validate_store(s)
    assert "valid" in v and "error_count" in v


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

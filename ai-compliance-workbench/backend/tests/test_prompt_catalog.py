import pytest
import time

from app.core import config
from app.repositories import db
from app.services.generation import service as generation_service
from app.services.prompts import catalog
from app.services.prompts.defaults import load_builtin_defaults


@pytest.fixture
def prompt_db(monkeypatch):
    db.close_db()
    monkeypatch.setattr(config, "DB_PATH", ":memory:")
    db.init_db()
    yield
    db.close_db()


def test_v1_prompt_collection_has_all_builtin_scenes():
    defaults = load_builtin_defaults()
    assert defaults["version"] == "v1.0"
    assert len(defaults["platforms"]) == 5
    assert sum(len(item["scenes"]) for item in defaults["platforms"].values()) == 26
    assert "{{brand}}" not in defaults["base_prompt"]
    assert "动态合规规则" in defaults["base_prompt"]


def test_catalog_seed_is_idempotent_and_builtin_structure_is_locked(prompt_db):
    catalog.seed_builtins()
    first = catalog.get_catalog()
    catalog.seed_builtins()
    second = catalog.get_catalog()
    assert len(first["platforms"]) == len(second["platforms"]) == 5
    assert sum(len(item["scenes"]) for item in second["platforms"]) == 26

    builtin = second["platforms"][0]
    with pytest.raises(ValueError, match="不能改名"):
        catalog.update_platform(builtin["id"], {"name": "改名"})
    with pytest.raises(ValueError, match="不能停用"):
        catalog.set_platform_active(builtin["id"], False)


def test_custom_platform_scene_lifecycle_and_rule_mapping(prompt_db):
    platform = catalog.create_platform({
        "name": "视频号",
        "description": "短视频内容",
        "prompt_text": "使用适合视频号的自然表达。",
        "rule_profile": "微信",
    })
    scene = catalog.create_scene(platform["id"], {
        "name": "口播",
        "description": "短视频口播",
        "prompt_text": "输出可以直接朗读的口播稿。",
        "rule_content_type": "直播口播",
    })
    assert catalog.rule_mapping("视频号", "口播") == (["微信"], ["直播口播"])
    resolved_platform, resolved_scene = catalog.resolve_scene(
        platform_id=platform["id"], scene_id=scene["id"]
    )
    assert resolved_platform["name"] == "视频号"
    assert resolved_scene["name"] == "口播"

    catalog.set_scene_active(scene["id"], False)
    with pytest.raises(ValueError):
        catalog.resolve_scene("视频号", "口播")
    assert catalog.resolve_scene("视频号", "口播", include_inactive=True)[1]["active"] is False


def test_mock_cannot_generate_prompt_draft(prompt_db):
    with pytest.raises(ValueError, match="真实模型"):
        catalog.generate_ai_draft(
            {"target_type": "base", "requirements": "语气自然"},
            {"model_provider": "mock"},
        )


def test_ai_draft_is_returned_without_being_saved(prompt_db, monkeypatch):
    class FakeProvider:
        name = "openai_compatible"
        model = "test-model"

        def prompt_draft(self, context):
            assert context["requirements"] == "面向新用户，语气克制"
            return "这是一份尚未保存的候选提示词。"

    monkeypatch.setattr(
        "app.services.llm.provider.build_provider",
        lambda settings: FakeProvider(),
    )
    before = catalog.get_catalog()["base_prompt"]["effective"]
    result = catalog.generate_ai_draft(
        {"target_type": "base", "requirements": "面向新用户，语气克制"},
        {"model_provider": "openai_compatible"},
    )
    assert result["draft"] == "这是一份尚未保存的候选提示词。"
    assert result["saved"] is False
    assert catalog.get_catalog()["base_prompt"]["effective"] == before


def test_catalog_reads_do_not_reseed_database(prompt_db, monkeypatch):
    calls = []
    monkeypatch.setattr(db, "seed_prompt_catalog", lambda defaults: calls.append(defaults))
    catalog.invalidate_catalog_cache()
    catalog.get_catalog()
    catalog.get_catalog()
    assert calls == []


def test_multi_version_compliance_checks_run_concurrently(monkeypatch):
    class Provider:
        name = "fake"
        model = "fake-model"

        def generate(self, **kwargs):
            return ["版本一", "版本二", "版本三"]

    monkeypatch.setattr(
        generation_service,
        "_validate_scene",
        lambda *args, **kwargs: ({"id": "p", "name": "平台"}, {"id": "s", "name": "场景"}),
    )
    monkeypatch.setattr(
        generation_service,
        "compose_prompt",
        lambda *args, **kwargs: ("prompt", {"id": "p", "name": "平台"}, {"id": "s", "name": "场景"}),
    )
    monkeypatch.setattr(generation_service, "build_provider", lambda settings: Provider())
    monkeypatch.setattr(generation_service, "get_store", lambda: object())

    def slow_check(**kwargs):
        time.sleep(0.08)
        return {
            "overall_risk_level": "none",
            "matched_rules": [],
            "manual_review_required": False,
        }

    monkeypatch.setattr(generation_service, "run_compliance_check", slow_check)
    started = time.perf_counter()
    result = generation_service.generate(
        {"platform": "平台", "content_type": "场景", "topic": "主题", "versions": 3},
        {"default_versions": 3},
    )
    elapsed = time.perf_counter() - started
    assert elapsed < 0.18
    assert [item["text"] for item in result["versions"]] == ["版本一", "版本二", "版本三"]
    assert result["timings_ms"]["compliance_all_versions"] < 180

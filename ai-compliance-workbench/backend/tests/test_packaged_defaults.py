"""内部 EXE 默认环境与设置初始化测试。"""
from __future__ import annotations

from pathlib import Path
import json
import sqlite3

from dotenv import dotenv_values

from app.core import config
from app.repositories import db


def test_default_model_settings_follow_current_env():
    values = dotenv_values(config.ENV_PATH)
    assert values.get("LLM_API_KEY")
    assert config.DEFAULT_SETTINGS["model_provider"] == "openai_compatible"
    assert config.DEFAULT_SETTINGS["model_name"] == values.get("LLM_MODEL")
    assert config.DEFAULT_SETTINGS["api_base"] == values.get("LLM_BASE_URL")
    assert config.DEFAULT_SETTINGS["temperature"] == float(values["LLM_TEMPERATURE"])
    assert config.DEFAULT_SETTINGS["max_tokens"] == int(values["LLM_MAX_TOKENS"])


def test_bundled_env_is_installed_once_and_user_copy_is_preserved(tmp_path, monkeypatch):
    bundled = tmp_path / "bundle" / ".env"
    target = tmp_path / "user" / ".env"
    bundled.parent.mkdir()
    bundled.write_text("LLM_API_KEY=internal-default\nLLM_MODEL=default-model\n", encoding="utf-8")

    monkeypatch.setattr(config, "IS_BUNDLED", True)
    monkeypatch.setattr(config, "BUNDLED_ENV_PATH", bundled)
    monkeypatch.setattr(config, "PROJECT_ROOT", target.parent)
    monkeypatch.setattr(config, "ENV_PATH", target)

    assert config._materialize_bundled_env() is True
    assert target.read_text(encoding="utf-8") == bundled.read_text(encoding="utf-8")

    target.write_text("LLM_API_KEY=user-customized\n", encoding="utf-8")
    assert config._materialize_bundled_env() is False
    assert target.read_text(encoding="utf-8") == "LLM_API_KEY=user-customized\n"


def test_windows_spec_embeds_real_env_without_database():
    spec = (
        Path(__file__).resolve().parents[2]
        / "packaging"
        / "windows_onefile.spec"
    ).read_text(encoding="utf-8")
    assert 'ROOT / ".env"' in spec
    assert 'ROOT / "data" / "compliance"' in spec
    assert '(str(ROOT / "data"), "data")' not in spec


def test_legacy_database_model_overrides_are_ignored(tmp_path, monkeypatch):
    db.close_db()
    database = tmp_path / "workbench.db"
    monkeypatch.setattr(config, "DB_PATH", database)
    db.init_db()

    connection = sqlite3.connect(database)
    for key, value in {
        "model_provider": "openai_compatible",
        "model_name": "qwen3.7-flash",
        "api_base": "https://legacy.example/v1",
        "temperature": 1.8,
        "max_tokens": 9999,
    }.items():
        connection.execute(
            "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
            (key, json.dumps(value)),
        )
    connection.commit()
    connection.close()

    settings = db.load_settings()
    assert settings["model_provider"] == "openai_compatible"
    assert settings["model_name"] == config.LLM_MODEL
    assert settings["api_base"] == config.LLM_BASE_URL
    assert settings["temperature"] == config.LLM_TEMPERATURE
    assert settings["max_tokens"] == config.LLM_MAX_TOKENS

    saved = db.save_settings({
        "model_name": "another-ignored-model",
        "api_base": "https://ignored.example/v1",
        "default_versions": 2,
    })
    assert saved["model_name"] == config.LLM_MODEL
    assert saved["api_base"] == config.LLM_BASE_URL
    assert saved["default_versions"] == 2
    db.close_db()

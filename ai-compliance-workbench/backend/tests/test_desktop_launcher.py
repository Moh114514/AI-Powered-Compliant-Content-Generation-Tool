"""Desktop launcher startup diagnostic tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "desktop_launcher",
    ROOT / "packaging" / "desktop_launcher.py",
)
assert SPEC and SPEC.loader
desktop_launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(desktop_launcher)


def test_write_startup_log_contains_diagnostics_and_redacts_key_value(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "must-not-be-written")
    log_path = tmp_path / "startup.log"

    result = desktop_launcher.write_startup_log(
        "test failure",
        details="server thread traceback",
        user_data_dir=tmp_path / "user-data",
        log_path=log_path,
    )

    assert result == log_path
    content = log_path.read_text(encoding="utf-8")
    assert "reason: test failure" in content
    assert "server thread traceback" in content
    assert "llm_api_key_present: True" in content
    assert "must-not-be-written" not in content

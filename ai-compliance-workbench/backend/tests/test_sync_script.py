"""Tests for the standalone compliance-library sync script."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "sync_compliance_library.py"
SPEC = importlib.util.spec_from_file_location("sync_compliance_library", SCRIPT_PATH)
assert SPEC and SPEC.loader
sync_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_module)


def test_current_runtime_library_is_structurally_valid():
    source = PROJECT_ROOT / "data" / "compliance"
    result = sync_module.validate_source(source, enforce_v12=False)
    assert result["valid"], result["errors"]
    assert result["counts"]["rules.json"] > 0
    assert result["counts"]["rule_variants.json"] > 0


def test_apply_sync_creates_manifest_and_preserves_counts(tmp_path):
    source = PROJECT_ROOT / "data" / "compliance"
    destination = tmp_path / "runtime"
    validation = sync_module.validate_source(source, enforce_v12=False)
    assert validation["valid"], validation["errors"]

    backup = sync_module.apply_sync(
        source=source,
        destination=destination,
        validation=validation,
        no_backup=False,
    )

    assert backup.exists()
    manifest_path = destination / "sync_manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["counts"]["rules.json"] == validation["counts"]["rules.json"]
    assert manifest["files"]["rules.json"]["sha256"]
    assert not Path(manifest["source_directory"]).is_absolute()
    assert not Path(manifest["destination_directory"]).is_absolute()
    assert not Path(manifest["backup_directory"]).is_absolute()

    post = sync_module.validate_source(destination, enforce_v12=False)
    assert post["valid"], post["errors"]


def test_cli_validate_only_uses_safe_default(tmp_path):
    source = PROJECT_ROOT / "data" / "compliance"
    destination = tmp_path / "must-not-be-created"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--source",
            str(source),
            "--destination",
            str(destination),
            "--allow-pre-v1.2",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "当前为只检查模式" in result.stdout
    assert not destination.exists()

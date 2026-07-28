"""本地 SQLite 存储：仅最近记录与工具设置。原始规则 JSON 保持只读。"""
from __future__ import annotations

import datetime
import json
import os
import sqlite3
import threading
import uuid
from typing import Any

from app.core import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS content_records (
    id TEXT PRIMARY KEY,
    operation_type TEXT NOT NULL,
    brand TEXT,
    platform TEXT,
    input_json TEXT,
    generated_json TEXT,
    detection_json TEXT,
    risk_level TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_content_records_created_at ON content_records(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_content_records_platform ON content_records(platform);
CREATE INDEX IF NOT EXISTS idx_content_records_risk ON content_records(risk_level);
"""

_ALLOWED_SETTING_KEYS = set(config.DEFAULT_SETTINGS)
_CONN: sqlite3.Connection | None = None
_LOCK = threading.RLock()


def _get_conn() -> sqlite3.Connection:
    global _CONN
    with _LOCK:
        if _CONN is None:
            os.makedirs(os.path.dirname(str(config.DB_PATH)), exist_ok=True)
            _CONN = sqlite3.connect(str(config.DB_PATH), check_same_thread=False, timeout=10)
            _CONN.row_factory = sqlite3.Row
            _CONN.execute("PRAGMA journal_mode=WAL")
            _CONN.execute("PRAGMA busy_timeout=10000")
        return _CONN


def init_db() -> None:
    with _LOCK:
        connection = _get_conn()
        connection.executescript(_SCHEMA)
        connection.commit()


def close_db() -> None:
    global _CONN
    with _LOCK:
        if _CONN is not None:
            _CONN.close()
            _CONN = None


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _coerce(value: str) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def load_settings() -> dict:
    with _LOCK:
        rows = _get_conn().execute("SELECT key, value FROM settings").fetchall()
    overrides = {row["key"]: _coerce(row["value"]) for row in rows if row["key"] in _ALLOWED_SETTING_KEYS}
    merged = dict(config.DEFAULT_SETTINGS)
    merged.update(overrides)
    return merged


def _sanitize_setting(key: str, value: Any) -> Any:
    if key not in _ALLOWED_SETTING_KEYS:
        raise ValueError(f"不支持的设置项：{key}")
    if key == "default_versions":
        return max(1, min(int(value), 5))
    if key == "max_history":
        return max(1, min(int(value), 5000))
    if key == "history_retention_days":
        return max(1, min(int(value), 3650))
    if key == "temperature":
        return max(0.0, min(float(value), 2.0))
    if key == "max_tokens":
        return max(128, min(int(value), 32000))
    if key == "default_platform" and value not in config.PLATFORMS:
        raise ValueError(f"不支持的默认平台：{value}")
    if key == "default_length" and value not in {"短", "中", "长"}:
        raise ValueError(f"不支持的默认长度：{value}")
    return value


def save_settings(patch: dict) -> dict:
    if not isinstance(patch, dict):
        raise ValueError("设置内容必须是对象。")
    sanitized = {key: _sanitize_setting(key, value) for key, value in patch.items()}
    with _LOCK:
        connection = _get_conn()
        for key, value in sanitized.items():
            connection.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value, ensure_ascii=False)),
            )
        connection.commit()
    return load_settings()


def add_record(operation_type, brand, platform, input_data, generated, detection, risk_level) -> str:
    record_id = "R" + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:6]
    now = _now()
    with _LOCK:
        connection = _get_conn()
        connection.execute(
            """INSERT INTO content_records(
                   id, operation_type, brand, platform, input_json, generated_json,
                   detection_json, risk_level, created_at, updated_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                record_id,
                str(operation_type or ""),
                brand,
                platform,
                json.dumps(input_data, ensure_ascii=False),
                json.dumps(generated, ensure_ascii=False) if generated is not None else None,
                json.dumps(detection, ensure_ascii=False) if detection is not None else None,
                risk_level,
                now,
                now,
            ),
        )
        connection.commit()
    _enforce_retention(load_settings())
    return record_id


def list_records(limit: int = 100) -> list[dict]:
    safe_limit = max(1, min(int(limit), 1000))
    with _LOCK:
        rows = _get_conn().execute(
            "SELECT * FROM content_records ORDER BY created_at DESC LIMIT ?", (safe_limit,)
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_record(record_id: str) -> dict | None:
    with _LOCK:
        row = _get_conn().execute("SELECT * FROM content_records WHERE id=?", (record_id,)).fetchone()
    return _row_to_dict(row) if row else None


def delete_record(record_id: str) -> bool:
    with _LOCK:
        connection = _get_conn()
        cursor = connection.execute("DELETE FROM content_records WHERE id=?", (record_id,))
        connection.commit()
        return cursor.rowcount > 0


def clear_records() -> None:
    with _LOCK:
        connection = _get_conn()
        connection.execute("DELETE FROM content_records")
        connection.commit()


def _enforce_retention(settings: dict) -> None:
    days = max(1, int(settings.get("history_retention_days", 90)))
    max_records = max(1, int(settings.get("max_history", 100)))
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat(timespec="seconds")
    with _LOCK:
        connection = _get_conn()
        connection.execute("DELETE FROM content_records WHERE created_at < ?", (cutoff,))
        connection.execute(
            """DELETE FROM content_records
               WHERE id IN (
                   SELECT id FROM content_records
                   ORDER BY created_at DESC
                   LIMIT -1 OFFSET ?
               )""",
            (max_records,),
        )
        connection.commit()


def _load_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {
        "id": row["id"],
        "operation_type": row["operation_type"],
        "brand": row["brand"],
        "platform": row["platform"],
        "input": _load_json(row["input_json"], {}),
        "generated": _load_json(row["generated_json"], None),
        "detection": _load_json(row["detection_json"], None),
        "risk_level": row["risk_level"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }

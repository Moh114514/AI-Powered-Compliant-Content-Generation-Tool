"""本地存储：SQLite（仅最近记录与工具设置，不存储用户/权限/审核等）。
原始规则 JSON 保持只读，不在此库。
"""
import json
import os
import sqlite3
import datetime
import uuid
import threading
from app.core import config
from app.core.data_loader import get_store

_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS content_records (
    id TEXT PRIMARY KEY,
    operation_type TEXT,
    brand TEXT,
    platform TEXT,
    input_json TEXT,
    generated_json TEXT,
    detection_json TEXT,
    risk_level TEXT,
    created_at TEXT,
    updated_at TEXT
);
"""

_conn = None
_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            os.makedirs(os.path.dirname(str(config.DB_PATH)), exist_ok=True)
            _conn = sqlite3.connect(str(config.DB_PATH), check_same_thread=False)
            _conn.row_factory = sqlite3.Row
        return _conn


def init_db():
    conn = _get_conn()
    conn.executescript(_SCHEMA)
    conn.commit()


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


# ---------- 设置 ----------
def load_settings() -> dict:
    conn = _get_conn()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    overrides = {r["key"]: _coerce(r["value"]) for r in rows}
    merged = dict(config.DEFAULT_SETTINGS)
    merged.update(overrides)
    return merged


def _coerce(v: str):
    try:
        return json.loads(v)
    except Exception:
        return v


def save_settings(patch: dict) -> dict:
    conn = _get_conn()
    now = _now()
    for k, val in patch.items():
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (k, json.dumps(val, ensure_ascii=False)),
        )
    conn.commit()
    return load_settings()


# ---------- 最近记录 ----------
def add_record(operation_type, brand, platform, input_data, generated, detection, risk_level) -> str:
    conn = _get_conn()
    rid = "R" + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:6]
    now = _now()
    conn.execute(
        """INSERT INTO content_records(id, operation_type, brand, platform, input_json, generated_json, detection_json, risk_level, created_at, updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (rid, operation_type, brand, platform, json.dumps(input_data, ensure_ascii=False),
         json.dumps(generated, ensure_ascii=False), json.dumps(detection, ensure_ascii=False),
         risk_level, now, now),
    )
    conn.commit()
    _enforce_retention(load_settings())
    return rid


def list_records(limit: int = 100) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM content_records ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_record(rid: str) -> dict | None:
    conn = _get_conn()
    r = conn.execute("SELECT * FROM content_records WHERE id=?", (rid,)).fetchone()
    return _row_to_dict(r) if r else None


def delete_record(rid: str) -> bool:
    conn = _get_conn()
    cur = conn.execute("DELETE FROM content_records WHERE id=?", (rid,))
    conn.commit()
    return cur.rowcount > 0


def clear_records():
    conn = _get_conn()
    conn.execute("DELETE FROM content_records")
    conn.commit()


def _enforce_retention(settings: dict):
    days = int(settings.get("history_retention_days", 90))
    max_n = int(settings.get("max_history", 100))
    conn = _get_conn()
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat(timespec="seconds")
    conn.execute("DELETE FROM content_records WHERE created_at < ?", (cutoff,))
    # 超过最大条数保留最新
    rows = conn.execute("SELECT id FROM content_records ORDER BY created_at DESC").fetchall()
    if len(rows) > max_n:
        excess = [r["id"] for r in rows[max_n:]]
        for eid in excess:
            conn.execute("DELETE FROM content_records WHERE id=?", (eid,))
    conn.commit()


def _row_to_dict(r) -> dict:
    if r is None:
        return {}
    return {
        "id": r["id"],
        "operation_type": r["operation_type"],
        "brand": r["brand"],
        "platform": r["platform"],
        "input": json.loads(r["input_json"]) if r["input_json"] else {},
        "generated": json.loads(r["generated_json"]) if r["generated_json"] else None,
        "detection": json.loads(r["detection_json"]) if r["detection_json"] else None,
        "risk_level": r["risk_level"],
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }

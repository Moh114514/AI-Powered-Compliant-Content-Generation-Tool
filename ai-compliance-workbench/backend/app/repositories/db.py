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
CREATE TABLE IF NOT EXISTS prompt_platforms (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    prompt_text TEXT NOT NULL DEFAULT '',
    rule_profile TEXT NOT NULL DEFAULT '通用',
    sort_order INTEGER NOT NULL DEFAULT 100,
    is_builtin INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prompt_scenes (
    id TEXT PRIMARY KEY,
    platform_id TEXT NOT NULL,
    name TEXT NOT NULL COLLATE NOCASE,
    description TEXT NOT NULL DEFAULT '',
    prompt_text TEXT NOT NULL DEFAULT '',
    rule_content_type TEXT NOT NULL DEFAULT '通用',
    sort_order INTEGER NOT NULL DEFAULT 100,
    is_builtin INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(platform_id) REFERENCES prompt_platforms(id),
    UNIQUE(platform_id, name)
);
CREATE INDEX IF NOT EXISTS idx_prompt_scenes_platform ON prompt_scenes(platform_id, sort_order);
CREATE TABLE IF NOT EXISTS prompt_overrides (
    scope TEXT NOT NULL,
    target_id TEXT NOT NULL,
    content TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(scope, target_id)
);
"""

_ALLOWED_SETTING_KEYS = set(config.DEFAULT_SETTINGS)
ENV_MANAGED_MODEL_KEYS = {
    "model_provider",
    "model_name",
    "api_base",
    "temperature",
    "max_tokens",
}
_CONN: sqlite3.Connection | None = None
_LOCK = threading.RLock()


def _get_conn() -> sqlite3.Connection:
    global _CONN
    with _LOCK:
        if _CONN is None:
            parent = os.path.dirname(str(config.DB_PATH))
            if parent:
                os.makedirs(parent, exist_ok=True)
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
    # Import lazily to avoid a repository/service import cycle during module load.
    from app.services.prompts.catalog import seed_builtins
    seed_builtins()


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
    # 模型连接配置由 .env 强制托管，历史 SQLite 值不得覆盖。
    merged.update({
        "model_provider": "openai_compatible" if config.get_llm_api_key() else "mock",
        "model_name": config.LLM_MODEL,
        "api_base": config.LLM_BASE_URL,
        "temperature": config.LLM_TEMPERATURE,
        "max_tokens": config.LLM_MAX_TOKENS,
    })
    try:
        from app.services.prompts.catalog import active_platform_names
        active_platforms = active_platform_names()
        if active_platforms and merged.get("default_platform") not in active_platforms:
            merged["default_platform"] = "小红书" if "小红书" in active_platforms else active_platforms[0]
    except sqlite3.OperationalError:
        # Catalog tables may not exist yet during first-time database initialization.
        pass
    return merged


def get_setting_override(key: str) -> Any:
    with _LOCK:
        row = _get_conn().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return _coerce(row["value"]) if row else None


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
    if key == "model_provider" and value not in {"mock", "openai_compatible"}:
        raise ValueError(f"不支持的模型 Provider：{value}")
    if key == "default_platform":
        from app.services.prompts.catalog import active_platform_names
        if value not in active_platform_names():
            raise ValueError(f"不支持的默认平台：{value}")
    if key == "default_length" and value not in {"短", "中", "长"}:
        raise ValueError(f"不支持的默认长度：{value}")
    return value


def save_settings(patch: dict) -> dict:
    if not isinstance(patch, dict):
        raise ValueError("设置内容必须是对象。")
    sanitized = {
        key: _sanitize_setting(key, value)
        for key, value in patch.items()
        if key not in ENV_MANAGED_MODEL_KEYS
    }
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


def seed_prompt_catalog(defaults: dict) -> None:
    """Idempotently seed the immutable built-in catalog structure."""
    now = _now()
    with _LOCK:
        connection = _get_conn()
        for platform_order, (platform_name, platform) in enumerate(defaults["platforms"].items(), 1):
            connection.execute(
                """INSERT INTO prompt_platforms(
                       id, name, description, prompt_text, rule_profile, sort_order,
                       is_builtin, active, created_at, updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                       name=excluded.name, rule_profile=excluded.rule_profile,
                       sort_order=excluded.sort_order, is_builtin=1, active=1,
                       updated_at=excluded.updated_at""",
                (
                    platform["id"], platform_name, f"系统内置平台：{platform_name}", "",
                    platform["rule_profile"], platform_order * 10, 1, 1, now, now,
                ),
            )
            for scene_order, scene_name in enumerate(platform["scenes"], 1):
                scene_id = f"{platform['id']}-scene-{scene_order:02d}"
                rule_content_type = "自动"
                connection.execute(
                    """INSERT INTO prompt_scenes(
                           id, platform_id, name, description, prompt_text,
                           rule_content_type, sort_order, is_builtin, active,
                           created_at, updated_at
                       ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(id) DO UPDATE SET
                           platform_id=excluded.platform_id, name=excluded.name,
                           rule_content_type=excluded.rule_content_type,
                           sort_order=excluded.sort_order, is_builtin=1, active=1,
                           updated_at=excluded.updated_at""",
                    (
                        scene_id, platform["id"], scene_name,
                        f"系统内置场景：{platform_name}—{scene_name}", "",
                        rule_content_type, scene_order * 10, 1, 1, now, now,
                    ),
                )
        connection.commit()


def _prompt_platform_dict(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "prompt_text": row["prompt_text"],
        "rule_profile": row["rule_profile"],
        "sort_order": row["sort_order"],
        "is_builtin": bool(row["is_builtin"]),
        "active": bool(row["active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _prompt_scene_dict(row) -> dict:
    return {
        "id": row["id"],
        "platform_id": row["platform_id"],
        "name": row["name"],
        "description": row["description"],
        "prompt_text": row["prompt_text"],
        "rule_content_type": row["rule_content_type"],
        "sort_order": row["sort_order"],
        "is_builtin": bool(row["is_builtin"]),
        "active": bool(row["active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def load_prompt_catalog(include_inactive: bool = True) -> list[dict]:
    platform_where = "" if include_inactive else "WHERE active=1"
    scene_active = "" if include_inactive else "AND active=1"
    with _LOCK:
        connection = _get_conn()
        platform_rows = connection.execute(
            f"SELECT * FROM prompt_platforms {platform_where} ORDER BY sort_order, name"
        ).fetchall()
        output = []
        for platform_row in platform_rows:
            platform = _prompt_platform_dict(platform_row)
            scene_rows = connection.execute(
                f"""SELECT * FROM prompt_scenes
                    WHERE platform_id=? {scene_active}
                    ORDER BY sort_order, name""",
                (platform["id"],),
            ).fetchall()
            platform["scenes"] = [_prompt_scene_dict(row) for row in scene_rows]
            output.append(platform)
    return output


def get_prompt_platform(platform_id: str) -> dict | None:
    with _LOCK:
        row = _get_conn().execute("SELECT * FROM prompt_platforms WHERE id=?", (platform_id,)).fetchone()
    return _prompt_platform_dict(row) if row else None


def get_prompt_scene(scene_id: str) -> dict | None:
    with _LOCK:
        row = _get_conn().execute("SELECT * FROM prompt_scenes WHERE id=?", (scene_id,)).fetchone()
    return _prompt_scene_dict(row) if row else None


def create_prompt_platform(
    platform_id: str, name: str, description: str, prompt_text: str,
    rule_profile: str, sort_order: int,
) -> None:
    now = _now()
    try:
        with _LOCK:
            connection = _get_conn()
            connection.execute(
                """INSERT INTO prompt_platforms(
                       id,name,description,prompt_text,rule_profile,sort_order,
                       is_builtin,active,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,0,1,?,?)""",
                (platform_id, name, description, prompt_text, rule_profile, sort_order, now, now),
            )
            connection.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError("平台名称已存在。") from exc


def update_prompt_platform(platform_id: str, fields: dict) -> None:
    allowed = {"name", "description", "rule_profile", "sort_order", "active"}
    values = {key: value for key, value in fields.items() if key in allowed}
    if not values:
        return
    if "active" in values:
        values["active"] = int(bool(values["active"]))
    values["updated_at"] = _now()
    assignments = ", ".join(f"{key}=?" for key in values)
    try:
        with _LOCK:
            connection = _get_conn()
            connection.execute(
                f"UPDATE prompt_platforms SET {assignments} WHERE id=?",
                (*values.values(), platform_id),
            )
            connection.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError("平台名称已存在。") from exc


def create_prompt_scene(
    scene_id: str, platform_id: str, name: str, description: str,
    prompt_text: str, rule_content_type: str, sort_order: int,
) -> None:
    now = _now()
    try:
        with _LOCK:
            connection = _get_conn()
            connection.execute(
                """INSERT INTO prompt_scenes(
                       id,platform_id,name,description,prompt_text,rule_content_type,
                       sort_order,is_builtin,active,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,0,1,?,?)""",
                (
                    scene_id, platform_id, name, description, prompt_text,
                    rule_content_type, sort_order, now, now,
                ),
            )
            connection.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError("该平台下已存在同名场景。") from exc


def update_prompt_scene(scene_id: str, fields: dict) -> None:
    allowed = {"name", "description", "rule_content_type", "sort_order", "active"}
    values = {key: value for key, value in fields.items() if key in allowed}
    if not values:
        return
    if "active" in values:
        values["active"] = int(bool(values["active"]))
    values["updated_at"] = _now()
    assignments = ", ".join(f"{key}=?" for key in values)
    try:
        with _LOCK:
            connection = _get_conn()
            connection.execute(
                f"UPDATE prompt_scenes SET {assignments} WHERE id=?",
                (*values.values(), scene_id),
            )
            connection.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError("该平台下已存在同名场景。") from exc


def get_prompt_override(scope: str, target_id: str) -> str | None:
    with _LOCK:
        row = _get_conn().execute(
            "SELECT content FROM prompt_overrides WHERE scope=? AND target_id=?",
            (scope, target_id),
        ).fetchone()
    return str(row["content"]) if row else None


def set_prompt_override(scope: str, target_id: str, content: str) -> None:
    with _LOCK:
        connection = _get_conn()
        connection.execute(
            """INSERT INTO prompt_overrides(scope,target_id,content,updated_at)
               VALUES(?,?,?,?)
               ON CONFLICT(scope,target_id) DO UPDATE SET
                   content=excluded.content, updated_at=excluded.updated_at""",
            (scope, target_id, content, _now()),
        )
        connection.commit()


def delete_prompt_override(scope: str, target_id: str) -> None:
    with _LOCK:
        connection = _get_conn()
        connection.execute(
            "DELETE FROM prompt_overrides WHERE scope=? AND target_id=?",
            (scope, target_id),
        )
        connection.commit()


def delete_builtin_prompt_overrides() -> None:
    with _LOCK:
        connection = _get_conn()
        connection.execute("DELETE FROM prompt_overrides WHERE scope='base' AND target_id='global'")
        connection.execute(
            """DELETE FROM prompt_overrides
               WHERE scope='platform' AND target_id IN
                     (SELECT id FROM prompt_platforms WHERE is_builtin=1)"""
        )
        connection.execute(
            """DELETE FROM prompt_overrides
               WHERE scope='scene' AND target_id IN
                     (SELECT id FROM prompt_scenes WHERE is_builtin=1)"""
        )
        connection.commit()

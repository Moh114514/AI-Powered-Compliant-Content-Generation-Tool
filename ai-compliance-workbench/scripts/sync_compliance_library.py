"""Validate and sync the maintained compliance library into Web runtime data.

Usage examples:

Validate only:
    python scripts/sync_compliance_library.py --source "../医美内容合规规则库_v1.1/02_系统调用数据"

Validate and apply:
    python scripts/sync_compliance_library.py --source "../医美内容合规规则库_v1.1/02_系统调用数据" --apply

The script never reads supplement or backup directories. It copies only the explicit
runtime/reference JSON allowlist, validates IDs and references, creates a local backup,
and writes sync_manifest.json with counts and SHA-256 hashes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

REQUIRED_FILES = (
    "metadata.json",
    "rules.json",
    "rule_variants.json",
    "sources.json",
    "rule_sources.json",
    "rule_platforms.json",
    "semantic_rules.json",
)

OPTIONAL_FILES = (
    "rule_channels.json",
    "rule_examples.json",
    "semantic_rule_sources.json",
    "semantic_rule_examples.json",
    "ad_classification_rules.json",
    "enforcement_cases.json",
    "case_leads.json",
    "test_cases.json",
    "visual_manual_checks.json",
    "manual_review_issues.json",
    "risk_scoring.json",
    "changelog.json",
    "compliance_rules.schema.json",
)

AUXILIARY_FILES = ("xhs_banned_words.json",)

V12_MINIMUMS = {
    "sources.json": 20,
    "rules.json": 150,
    "rule_variants.json": 500,
    "rule_platforms.json": 60,
    "rule_examples.json": 200,
    "semantic_rules.json": 25,
    "ad_classification_rules.json": 10,
    "test_cases.json": 300,
    "visual_manual_checks.json": 10,
}

ID_FIELDS = {
    "rules.json": "rule_id",
    "rule_variants.json": "variant_id",
    "sources.json": "source_id",
    "semantic_rules.json": "semantic_rule_id",
    "rule_examples.json": "example_id",
}


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ValueError(f"缺少文件：{path.name}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{path.name} JSON 解析失败：第 {exc.lineno} 行，第 {exc.colno} 列，{exc.msg}"
        ) from exc


def as_list(data: Any) -> list[dict]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("rules", "items", "data", "records"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def duplicate_values(records: list[dict], field: str) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for record in records:
        value = str(record.get(field) or "").strip()
        if not value:
            continue
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def validate_xhs_banned_words(data: Any) -> dict:
    errors: list[str] = []
    records = as_list(data)
    if not isinstance(data, list):
        errors.append("xhs_banned_words.json 顶层必须是数组")
    ids: set[str] = set()
    unique_terms: set[str] = set()
    variant_count = 0
    for index, item in enumerate(records, 1):
        item_id = str(item.get("id") or "").strip()
        word = str(item.get("word") or "").strip()
        if not item_id or not word:
            errors.append(f"xhs_banned_words.json 第 {index} 条缺少 id/word")
        if item_id in ids:
            errors.append(f"xhs_banned_words.json 存在重复 id：{item_id}")
        ids.add(item_id)
        if str(item.get("risk_level") or "") not in {"违禁", "敏感"}:
            errors.append(f"xhs_banned_words.json {item_id or index} 风险等级无效")
        if not str(item.get("replacement") or "").strip():
            errors.append(f"xhs_banned_words.json {item_id or index} 缺少 replacement")
        variants = item.get("variants") or []
        if not isinstance(variants, list):
            errors.append(f"xhs_banned_words.json {item_id or index} 的 variants 必须是数组")
            variants = []
        variant_count += len(variants)
        unique_terms.update(
            str(term or "").strip().lower()
            for term in [word, *variants]
            if str(term or "").strip()
        )
    return {
        "valid": not errors,
        "errors": errors,
        "counts": {
            "xhs_banned_words.json": len(records),
            "xhs_banned_word_variants": variant_count,
            "xhs_banned_unique_terms": len(unique_terms),
        },
    }


def validate_source(source: Path, enforce_v12: bool) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}
    loaded: dict[str, Any] = {}

    if not source.is_dir():
        errors.append(f"来源目录不存在：{source}")
        return {"valid": False, "errors": errors, "warnings": warnings, "counts": counts}

    for filename in REQUIRED_FILES:
        if not (source / filename).is_file():
            errors.append(f"缺少必要文件：{filename}")

    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings, "counts": counts}

    for filename in (*REQUIRED_FILES, *OPTIONAL_FILES, *AUXILIARY_FILES):
        path = source / filename
        if not path.is_file():
            continue
        try:
            loaded[filename] = read_json(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if filename not in {"metadata.json", "risk_scoring.json", "compliance_rules.schema.json"}:
            counts[filename] = len(as_list(loaded[filename]))

    if "xhs_banned_words.json" in loaded:
        banned_validation = validate_xhs_banned_words(loaded["xhs_banned_words.json"])
        errors.extend(banned_validation["errors"])
        counts.update(banned_validation["counts"])

    for filename, field in ID_FIELDS.items():
        if filename not in loaded:
            continue
        records = as_list(loaded[filename])
        missing = [index + 1 for index, item in enumerate(records) if not item.get(field)]
        duplicates = duplicate_values(records, field)
        if missing:
            errors.append(f"{filename} 有 {len(missing)} 条记录缺少 {field}")
        if duplicates:
            errors.append(f"{filename} 存在重复 {field}：{duplicates[:10]}")

    rules = as_list(loaded.get("rules.json", []))
    variants = as_list(loaded.get("rule_variants.json", []))
    sources = as_list(loaded.get("sources.json", []))
    semantic_rules = as_list(loaded.get("semantic_rules.json", []))
    rule_ids = {str(item.get("rule_id")) for item in rules if item.get("rule_id")}
    source_ids = {str(item.get("source_id")) for item in sources if item.get("source_id")}
    semantic_ids = {
        str(item.get("semantic_rule_id")) for item in semantic_rules if item.get("semantic_rule_id")
    }

    for variant in variants:
        rule_id = str(variant.get("rule_id") or "")
        if rule_id not in rule_ids:
            errors.append(
                f"variant {variant.get('variant_id')} 引用了不存在的 rule_id：{rule_id}"
            )
        pattern = variant.get("regex_pattern")
        if pattern:
            try:
                re.compile(str(pattern))
            except re.error as exc:
                errors.append(f"variant {variant.get('variant_id')} 正则无效：{exc}")

    for filename in ("rule_sources.json", "rule_platforms.json"):
        for relation in as_list(loaded.get(filename, [])):
            rule_id = str(relation.get("rule_id") or "")
            source_id = str(relation.get("source_id") or "")
            if rule_id and rule_id not in rule_ids:
                errors.append(f"{filename} 引用了不存在的 rule_id：{rule_id}")
            if source_id and source_id not in source_ids:
                errors.append(f"{filename} 引用了不存在的 source_id：{source_id}")

    for relation in as_list(loaded.get("semantic_rule_sources.json", [])):
        semantic_id = str(relation.get("semantic_rule_id") or "")
        source_id = str(relation.get("source_id") or "")
        if semantic_id and semantic_id not in semantic_ids:
            errors.append(
                f"semantic_rule_sources.json 引用了不存在的 semantic_rule_id：{semantic_id}"
            )
        if source_id and source_id not in source_ids:
            errors.append(
                f"semantic_rule_sources.json 引用了不存在的 source_id：{source_id}"
            )

    for example in as_list(loaded.get("rule_examples.json", [])):
        rule_id = str(example.get("rule_id") or "")
        if rule_id and rule_id not in rule_ids:
            errors.append(
                f"rule_examples.json {example.get('example_id')} 引用了不存在的 rule_id：{rule_id}"
            )

    for example in as_list(loaded.get("semantic_rule_examples.json", [])):
        semantic_id = str(example.get("semantic_rule_id") or "")
        if semantic_id and semantic_id not in semantic_ids:
            errors.append(
                "semantic_rule_examples.json "
                f"{example.get('semantic_example_id') or example.get('example_id')} "
                f"引用了不存在的 semantic_rule_id：{semantic_id}"
            )

    if enforce_v12:
        for filename, minimum in V12_MINIMUMS.items():
            actual = counts.get(filename, 0)
            if actual < minimum:
                errors.append(f"{filename} 数量不足：{actual}，v1.2 最低要求为 {minimum}")

    metadata = loaded.get("metadata.json") if isinstance(loaded.get("metadata.json"), dict) else {}
    version = str(metadata.get("version") or "")
    if enforce_v12 and not version.startswith("v1.2"):
        warnings.append(f"metadata.version 当前为 {version or '空'}，建议更新为 v1.2-dev 或 v1.2")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": counts,
        "version": version,
    }


def runtime_files(source: Path) -> list[Path]:
    allowed = set(REQUIRED_FILES) | set(OPTIONAL_FILES) | set(AUXILIARY_FILES)
    return sorted(
        path for path in source.iterdir()
        if path.is_file() and path.name in allowed
    )


def apply_sync(
    source: Path,
    destination: Path,
    validation: dict,
    no_backup: bool,
    auxiliary_files: list[Path] | None = None,
) -> Path:
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    destination.mkdir(parents=True, exist_ok=True)

    backup_dir = destination.parent / f"_backup_before_compliance_sync_{timestamp}"
    if not no_backup:
        backup_dir.mkdir(parents=True, exist_ok=False)
        for path in destination.iterdir():
            if path.is_file():
                shutil.copy2(path, backup_dir / path.name)

    files = runtime_files(source)
    for path in auxiliary_files or []:
        if path.is_file() and path.name in AUXILIARY_FILES and all(
            existing.name != path.name for existing in files
        ):
            files.append(path)
    files = sorted(files, key=lambda path: path.name)
    source_names = {path.name for path in files}
    managed_names = set(REQUIRED_FILES) | set(OPTIONAL_FILES) | {"sync_manifest.json"}
    managed_names.update(name for name in AUXILIARY_FILES if name in source_names)

    for existing in destination.iterdir():
        if existing.is_file() and existing.name in managed_names and existing.name not in source_names:
            existing.unlink()

    for path in files:
        temporary = destination / f".{path.name}.tmp"
        shutil.copy2(path, temporary)
        temporary.replace(destination / path.name)

    project_root = destination.parent.parent

    def portable_path(path: Path) -> str:
        try:
            return Path(os.path.relpath(path.resolve(), project_root.resolve())).as_posix()
        except ValueError:
            return path.name

    manifest = {
        "synced_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_directory": portable_path(source),
        "destination_directory": portable_path(destination),
        "library_version": validation.get("version"),
        "counts": validation.get("counts", {}),
        "files": {
            path.name: {
                "sha256": sha256(destination / path.name),
                "size_bytes": (destination / path.name).stat().st_size,
            }
            for path in files
        },
        "backup_directory": portable_path(backup_dir) if not no_backup else None,
    }
    (destination / "sync_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return backup_dir


def build_parser() -> argparse.ArgumentParser:
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    parser = argparse.ArgumentParser(description="校验并同步医美内容合规规则库。")
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="权威规则库的 02_系统调用数据 目录。",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=project_root / "data" / "compliance",
        help="Web 工具运行时规则目录。",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="验证通过后实际覆盖目标目录；未提供时仅检查。",
    )
    parser.add_argument(
        "--allow-pre-v1.2",
        dest="allow_pre_v1_2",
        action="store_true",
        help="不执行 v1.2 最低数据量检查，仅检查结构和引用。",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="同步前不生成本地备份，不推荐。",
    )
    parser.add_argument(
        "--xhs-banned-words",
        type=Path,
        default=None,
        help="小红书专项词库 JSON；默认读取 02_系统调用数据 同级的 07_小红书违禁词库。",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source = args.source.expanduser().resolve()
    destination = args.destination.expanduser().resolve()
    xhs_source = (
        args.xhs_banned_words.expanduser().resolve()
        if args.xhs_banned_words
        else (source.parent / "07_小红书违禁词库" / "xhs_banned_words.json").resolve()
    )
    validation = validate_source(source, enforce_v12=not args.allow_pre_v1_2)
    auxiliary_files: list[Path] = []
    if xhs_source.is_file() and not (source / "xhs_banned_words.json").is_file():
        banned_data = read_json(xhs_source)
        xhs_validation = validate_xhs_banned_words(banned_data)
        validation["errors"].extend(xhs_validation["errors"])
        auxiliary_files.append(xhs_source)
        validation["counts"].update(xhs_validation["counts"])
        validation["valid"] = not validation["errors"]
    elif not (source / "xhs_banned_words.json").is_file():
        validation["warnings"].append(
            f"未找到小红书专项词库：{xhs_source}；应用同步时将保留目标目录中的现有词库。"
        )

    print(json.dumps(validation, ensure_ascii=False, indent=2))
    if not validation["valid"]:
        print("\n校验失败，未修改运行时规则目录。", file=sys.stderr)
        return 1

    if not args.apply:
        print("\n校验通过。当前为只检查模式；添加 --apply 后执行同步。")
        return 0

    backup_dir = apply_sync(
        source,
        destination,
        validation,
        args.no_backup,
        auxiliary_files=auxiliary_files,
    )
    post_validation = validate_source(destination, enforce_v12=not args.allow_pre_v1_2)
    if not post_validation["valid"]:
        print(json.dumps(post_validation, ensure_ascii=False, indent=2), file=sys.stderr)
        print("同步后校验失败，请从备份目录恢复。", file=sys.stderr)
        return 2

    print(f"\n同步完成：{destination}")
    if not args.no_backup:
        print(f"备份目录：{backup_dir}")
    print("已生成：sync_manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

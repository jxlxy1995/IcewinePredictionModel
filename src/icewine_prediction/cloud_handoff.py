"""Create and restore checked data handoff bundles for short cloud runs."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


class HandoffError(RuntimeError):
    """Raised when a handoff bundle is unsafe or cannot be restored."""


DATABASE_RELATIVE = Path("local_data/icewine_prediction.sqlite3")
MANIFEST_NAME = "manifest.json"
_WRITABLE_CONFIG = {
    "display_names.yaml",
    "display_translation_status.yaml",
    "external_aliases.yaml",
    "paper_automation.yaml",
}
_PATH_COLUMNS = (
    "dataset_path",
    "dataset_report_path",
    "qa_report_path",
    "market_baseline_report_path",
    "feature_path",
    "feature_report_path",
    "dynamic_feature_path",
    "dynamic_feature_report_path",
    "away_cover_stability_report_path",
    "away_cover_bucket_threshold_report_path",
    "away_cover_bucket_sandbox_report_path",
    "total_goals_edge_stability_report_path",
    "total_goals_bucket_sandbox_report_path",
)


def prepare_initial(project_root: Path, output_dir: Path) -> Path:
    """Build the first, self-contained handoff bundle."""
    project_root = project_root.resolve()
    bundle = _new_bundle(output_dir, "initial")
    source_db = _required_file(project_root / DATABASE_RELATIVE)
    files: list[dict[str, Any]] = []
    _backup_database(source_db, bundle / "payload" / DATABASE_RELATIVE)
    files.append(_file_entry(DATABASE_RELATIVE, "sqlite-backup", bundle))

    latest_paths = _latest_training_paths(source_db, project_root)
    selected_training = {path for path in latest_paths if path.suffix.lower() == ".csv"}
    selected_training.update(_previous_baseline_csvs(project_root, selected_training))
    for relative in sorted(selected_training, key=lambda item: item.as_posix()):
        _add_existing_file(project_root, bundle, files, relative, "training")
    for relative in latest_paths:
        if relative.parts[0:1] == ("docs",):
            _add_existing_file(project_root, bundle, files, relative, "training-report")

    for relative in _code_files(project_root):
        if relative in selected_training or relative in latest_paths:
            continue
        _add_existing_file(project_root, bundle, files, relative, "code")
    _write_manifest(bundle, "initial", files, source_database_sha256=_sha256(source_db))
    return bundle


def prepare_return(project_root: Path, output_dir: Path, initial_manifest: Path) -> Path:
    """Build a return bundle containing cloud data and files absent from the initial bundle."""
    project_root = project_root.resolve()
    initial = _read_manifest(initial_manifest)
    initial_by_path = {item["path"]: item for item in initial["files"]}
    bundle = _new_bundle(output_dir, "return")
    files: list[dict[str, Any]] = []
    source_db = _required_file(project_root / DATABASE_RELATIVE)
    _backup_database(source_db, bundle / "payload" / DATABASE_RELATIVE)
    files.append(_file_entry(DATABASE_RELATIVE, "sqlite-backup", bundle))

    candidates: list[tuple[Path, str]] = []
    training_root = project_root / "local_data" / "training"
    if training_root.exists():
        for path in sorted(training_root.glob("*.csv")):
            candidates.append((path.relative_to(project_root), "training"))
    for root_name, role in (("docs/数据审计", "training-report"), ("docs/模型实验", "training-report")):
        root = project_root / Path(root_name)
        if root.exists():
            candidates.extend((path.relative_to(project_root), role) for path in root.rglob("*"))
    config_root = project_root / "config"
    for path in config_root.glob("*.yaml") if config_root.exists() else ():
        if path.name in _WRITABLE_CONFIG:
            candidates.append((path.relative_to(project_root), "writable-config"))
    logs_root = project_root / "logs" / "odds"
    if logs_root.exists():
        candidates.extend((path.relative_to(project_root), "odds-log") for path in logs_root.rglob("*"))

    for relative, role in candidates:
        if not (project_root / relative).is_file():
            continue
        normalized = _normalize_relative(relative)
        current_hash = _sha256(project_root / normalized)
        old = initial_by_path.get(normalized.as_posix())
        if normalized != DATABASE_RELATIVE and old is not None and old.get("sha256") == current_hash:
            continue
        _add_existing_file(project_root, bundle, files, normalized, role)
    _write_manifest(bundle, "return", files, initial_manifest_sha256=_sha256(Path(initial_manifest)))
    return bundle


def verify_bundle(bundle_dir: Path) -> None:
    """Verify every listed file and reject unsafe relative paths."""
    bundle_dir = Path(bundle_dir).resolve()
    manifest = _read_manifest(bundle_dir / MANIFEST_NAME)
    payload_root = bundle_dir / "payload"
    if not payload_root.is_dir():
        raise HandoffError("交接包缺少 payload 目录")
    seen: set[str] = set()
    for item in manifest["files"]:
        relative = _validate_relative(item.get("path"))
        if relative.as_posix() in seen:
            raise HandoffError(f"清单包含重复路径：{relative.as_posix()}")
        seen.add(relative.as_posix())
        path = payload_root / Path(*relative.parts)
        if not path.is_file():
            raise HandoffError(f"校验失败：缺少文件 {relative.as_posix()}")
        actual_size = path.stat().st_size
        actual_hash = _sha256(path)
        if actual_size != item.get("size") or actual_hash != item.get("sha256"):
            raise HandoffError(f"校验失败：文件已改变 {relative.as_posix()}")


def restore_return(project_root: Path, bundle_dir: Path, initial_manifest: Path) -> None:
    """Restore a verified return bundle without overwriting changed local data."""
    project_root = Path(project_root).resolve()
    bundle_dir = Path(bundle_dir).resolve()
    verify_bundle(bundle_dir)
    initial = _read_manifest(initial_manifest)
    initial_db = next((item for item in initial["files"] if item["path"] == DATABASE_RELATIVE.as_posix()), None)
    if initial_db is None:
        raise HandoffError("首次清单缺少主数据库")
    local_db = _required_file(project_root / DATABASE_RELATIVE)
    if _sha256(local_db) != initial.get("source_database_sha256", initial_db["sha256"]):
        raise HandoffError("本机主数据库在首次交接后发生变化，拒绝覆盖")
    manifest = _read_manifest(bundle_dir / MANIFEST_NAME)
    if manifest.get("kind") != "return" or manifest.get("initial_manifest_sha256") != _sha256(Path(initial_manifest)):
        raise HandoffError("回迁包与首次交接清单不匹配")
    if not any(item["path"] == DATABASE_RELATIVE.as_posix() for item in manifest["files"]):
        raise HandoffError("回迁包缺少主数据库")
    initial_by_path = {item["path"]: item for item in initial["files"]}
    for item in manifest["files"]:
        relative = _validate_relative(item["path"])
        if relative.parts[0] != "config" or relative.name not in _WRITABLE_CONFIG:
            continue
        previous = initial_by_path.get(relative.as_posix())
        local = project_root / Path(*relative.parts)
        if previous and (not local.is_file() or _sha256(local) != previous["sha256"]):
            raise HandoffError(f"本机可写配置已变化，拒绝覆盖：{relative.as_posix()}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_root = project_root / ".web" / "cloud-handoff" / f"restore-backup-{stamp}"
    staging_root = project_root / ".web" / "cloud-handoff" / f"restore-stage-{stamp}"
    backup_root.mkdir(parents=True, exist_ok=False)
    staging_root.mkdir(parents=True, exist_ok=False)
    entries = manifest["files"]
    try:
        for item in entries:
            relative = _validate_relative(item["path"])
            source = bundle_dir / "payload" / Path(*relative.parts)
            staged = staging_root / Path(*relative.parts)
            staged.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, staged)
            if relative == DATABASE_RELATIVE:
                _check_sqlite_integrity(staged)
        for item in entries:
            relative = _validate_relative(item["path"])
            destination = project_root / Path(*relative.parts)
            if destination.exists():
                backup = backup_root / Path(*relative.parts)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, backup)
        for item in entries:
            relative = _validate_relative(item["path"])
            destination = project_root / Path(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staging_root / Path(*relative.parts), destination)
    except Exception as error:  # noqa: BLE001
        for item in entries:
            relative = _validate_relative(item["path"])
            destination = project_root / Path(*relative.parts)
            backup = backup_root / Path(*relative.parts)
            if backup.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, destination)
        raise HandoffError(f"回迁失败，已保留并恢复原文件：{error}") from error
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


def _new_bundle(output_dir: Path, kind: str) -> Path:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    bundle = output_dir / f"{kind}-{stamp}"
    suffix = 1
    while bundle.exists():
        bundle = output_dir / f"{kind}-{stamp}-{suffix}"
        suffix += 1
    (bundle / "payload").mkdir(parents=True)
    return bundle


def _write_manifest(bundle: Path, kind: str, files: list[dict[str, Any]], **extra: Any) -> None:
    manifest = {
        "version": 1,
        "kind": kind,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": sorted(files, key=lambda item: item["path"]),
        **extra,
    }
    (bundle / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HandoffError(f"无法读取交接清单：{path}") from error
    if manifest.get("version") != 1 or not isinstance(manifest.get("files"), list):
        raise HandoffError("交接清单格式无效")
    for item in manifest["files"]:
        _validate_relative(item.get("path"))
        if not isinstance(item.get("sha256"), str) or not isinstance(item.get("size"), int):
            raise HandoffError("交接清单文件条目无效")
    return manifest


def _validate_relative(value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise HandoffError("清单中的路径无效")
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or ":" in path.parts[0] or normalized != path.as_posix():
        raise HandoffError(f"清单包含绝对路径或越界路径：{value}")
    return path


def _normalize_relative(value: Path | str) -> Path:
    normalized = str(value).replace("\\", "/")
    safe = _validate_relative(normalized)
    return Path(*safe.parts)


def _required_file(path: Path) -> Path:
    if not path.is_file():
        raise HandoffError(f"缺少必需文件：{path}")
    return path


def _file_entry(relative: Path, role: str, bundle: Path) -> dict[str, Any]:
    normalized = _normalize_relative(relative)
    path = bundle / "payload" / normalized
    return {"path": normalized.as_posix(), "role": role, "size": path.stat().st_size, "sha256": _sha256(path)}


def _add_existing_file(project_root: Path, bundle: Path, files: list[dict[str, Any]], relative: Path, role: str) -> None:
    normalized = _normalize_relative(relative)
    source = _required_file(project_root / normalized)
    if source.resolve().is_relative_to(project_root) is False:
        raise HandoffError(f"源文件越界：{normalized.as_posix()}")
    destination = bundle / "payload" / normalized
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    files.append(_file_entry(normalized, role, bundle))


def _backup_database(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(source)
    destination_connection = sqlite3.connect(destination)
    try:
        source_connection.backup(destination_connection)
    finally:
        destination_connection.close()
        source_connection.close()
    _check_sqlite_integrity(destination)


def _check_sqlite_integrity(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()
    finally:
        connection.close()
    if not result or result[0] != "ok":
        raise HandoffError(f"SQLite 完整性检查失败：{path}")


def _latest_training_paths(database: Path, project_root: Path) -> set[Path]:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM training_runs WHERE run_type = 'full_refresh' "
            "AND status = 'success' AND dynamic_feature_path IS NOT NULL "
            "ORDER BY started_at DESC, id DESC LIMIT 1"
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise HandoffError("数据库中没有成功的完整训练记录")
    selected: set[Path] = set()
    for column in _PATH_COLUMNS:
        value = row[column] if column in row.keys() else None
        if not value:
            continue
        relative = _normalize_relative(value)
        if not (project_root / relative).is_file():
            raise HandoffError(f"训练记录引用的文件不存在：{relative.as_posix()}")
        selected.add(relative)
    return selected


def _previous_baseline_csvs(project_root: Path, selected: set[Path]) -> set[Path]:
    training_root = project_root / "local_data" / "training"
    result: set[Path] = set()
    prefixes = (
        "baseline_main_leagues_",
        "baseline_features_main_leagues_",
        "baseline_dynamic_features_main_leagues_",
    )
    for prefix in prefixes:
        candidates = [
            path for path in training_root.glob(f"{prefix}*.csv")
            if path.relative_to(project_root) not in selected
        ]
        if candidates:
            result.add(max(candidates, key=lambda path: path.stat().st_mtime).relative_to(project_root))
    return result


def _code_files(project_root: Path) -> set[Path]:
    result: set[Path] = set()
    for root_name in ("src", "scripts", "deploy/cloud", "web/src", "web/dist"):
        root = project_root / Path(root_name)
        if root.exists():
            result.update(
                path.relative_to(project_root) for path in root.rglob("*")
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
            )
    for relative in (
        "pyproject.toml",
        "start_web.ps1",
        "start_web.sh",
        "web/package.json",
        "web/package-lock.json",
        "web/tsconfig.json",
        "web/vite.config.ts",
        "README.md",
    ):
        path = project_root / relative
        if path.is_file():
            result.add(Path(relative))
    for path in (project_root / "config").glob("*.yaml") if (project_root / "config").exists() else ():
        result.add(path.relative_to(project_root))
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

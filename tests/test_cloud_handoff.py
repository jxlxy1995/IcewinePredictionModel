import json
import sqlite3
from pathlib import Path

import pytest

from icewine_prediction.cloud_handoff import (
    HandoffError,
    prepare_code,
    prepare_initial,
    prepare_return,
    restore_return,
    verify_bundle,
)


def _make_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "local_data").mkdir(parents=True)
    (root / "local_data" / "training").mkdir()
    (root / "docs" / "数据审计").mkdir(parents=True)
    (root / "docs" / "模型实验").mkdir(parents=True)
    (root / "config").mkdir()
    (root / "src").mkdir()
    (root / "deploy" / "cloud").mkdir(parents=True)
    (root / "web" / "dist").mkdir(parents=True)
    (root / "web" / "node_modules").mkdir()
    connection = sqlite3.connect(root / "local_data" / "icewine_prediction.sqlite3")
    connection.executescript(
        """
        CREATE TABLE training_runs (
            id INTEGER PRIMARY KEY,
            run_type TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            dynamic_feature_path TEXT,
            dataset_path TEXT,
            feature_path TEXT,
            dataset_report_path TEXT,
            qa_report_path TEXT,
            dynamic_feature_report_path TEXT,
            away_cover_stability_report_path TEXT
        );
        INSERT INTO training_runs VALUES
        (1, 'full_refresh', 'success', '2026-09-27T10:00:00',
         'local_data\\training\\baseline_dynamic_features_main_leagues_old.csv',
         'local_data/training/baseline_main_leagues_old.csv',
         'local_data/training/baseline_features_main_leagues_old.csv',
         'docs/数据审计/old.md', NULL, NULL, NULL),
        (2, 'full_refresh', 'success', '2026-09-28T10:00:00',
         'local_data/training/baseline_dynamic_features_main_leagues_new.csv',
         'local_data/training/baseline_main_leagues_new.csv',
         'local_data/training/baseline_features_main_leagues_new.csv',
         'docs/数据审计/new.md', 'docs/数据审计/new-qa.md',
         'docs/数据审计/new-dynamic.md', 'docs/模型实验/new-stability.md');
        """
    )
    connection.close()
    for name in (
        "baseline_dynamic_features_main_leagues_old.csv",
        "baseline_main_leagues_old.csv",
        "baseline_features_main_leagues_old.csv",
        "baseline_dynamic_features_main_leagues_new.csv",
        "baseline_main_leagues_new.csv",
        "baseline_features_main_leagues_new.csv",
    ):
        (root / "local_data" / "training" / name).write_text(name, encoding="utf-8")
    for name in ("old.md", "new.md", "new-qa.md", "new-dynamic.md"):
        (root / "docs" / "数据审计" / name).write_text(name, encoding="utf-8")
    (root / "docs" / "模型实验" / "new-stability.md").write_text("report", encoding="utf-8")
    (root / "config" / "display_names.yaml").write_text("teams: {}\n", encoding="utf-8")
    (root / "config" / "display_translation_status.yaml").write_text("status: done\n", encoding="utf-8")
    (root / "src" / "example.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "deploy" / "cloud" / "nginx.conf.template").write_text("listen 8081;", encoding="utf-8")
    (root / "web" / "dist" / "index.html").write_text("<html />", encoding="utf-8")
    (root / "web" / "node_modules" / "ignored.js").write_text("ignored", encoding="utf-8")
    (root / ".env").write_text("SECRET=do-not-copy\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    return root


def test_prepare_initial_uses_latest_successful_training_and_sqlite_backup(tmp_path):
    root = _make_project(tmp_path)
    bundle = prepare_initial(root, tmp_path / "out")

    verify_bundle(bundle)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    paths = {item["path"] for item in manifest["files"]}
    assert "local_data/training/baseline_dynamic_features_main_leagues_new.csv" in paths
    assert "pyproject.toml" in paths
    assert "deploy/cloud/nginx.conf.template" in paths
    assert "local_data/training/baseline_dynamic_features_main_leagues_old.csv" in paths
    assert "local_data/training/baseline_dynamic_features_main_leagues_new.csv" in paths
    assert ".env" not in paths
    assert "web/node_modules/ignored.js" not in paths

    copied_db = bundle / "payload" / "local_data" / "icewine_prediction.sqlite3"
    connection = sqlite3.connect(copied_db)
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    connection.close()


def test_prepare_code_contains_code_but_not_cloud_data_or_secrets(tmp_path):
    root = _make_project(tmp_path)
    (root / "local_data" / "icewine_prediction.sqlite3").write_bytes(b"not a database")
    bundle = prepare_code(root, tmp_path / "code-out")

    verify_bundle(bundle)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    paths = {item["path"] for item in manifest["files"]}

    assert manifest["kind"] == "code"
    assert "src/example.py" in paths
    assert "deploy/cloud/nginx.conf.template" in paths
    assert "web/dist/index.html" in paths
    assert "pyproject.toml" in paths
    assert "config/display_names.yaml" in paths
    assert "local_data/icewine_prediction.sqlite3" not in paths
    assert not any(path.startswith("local_data/") for path in paths)
    assert not any(path.startswith("logs/") for path in paths)
    assert ".env" not in paths


def test_verify_bundle_rejects_tampered_file_and_traversal(tmp_path):
    root = _make_project(tmp_path)
    bundle = prepare_initial(root, tmp_path / "out")
    target = bundle / "payload" / "src" / "example.py"
    target.write_text("tampered", encoding="utf-8")
    with pytest.raises(HandoffError, match="校验失败"):
        verify_bundle(bundle)

    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][0]["path"] = "../outside.txt"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(HandoffError, match="越界|路径"):
        verify_bundle(bundle)

    bundle = prepare_initial(root, tmp_path / "duplicate-out")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"].append(dict(manifest["files"][0]))
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(HandoffError, match="重复路径"):
        verify_bundle(bundle)


def test_restore_return_rejects_changed_local_database(tmp_path):
    root = _make_project(tmp_path)
    initial = prepare_initial(root, tmp_path / "initial")
    return_bundle = prepare_return(root, tmp_path / "return", initial / "manifest.json")
    (root / "local_data" / "icewine_prediction.sqlite3").write_bytes(b"changed")

    with pytest.raises(HandoffError, match="主数据库.*变化"):
        restore_return(root, return_bundle, initial / "manifest.json")


def test_return_restores_cloud_files_and_preserves_local_backup(tmp_path):
    root = _make_project(tmp_path)
    initial = prepare_initial(root, tmp_path / "initial")
    original_db = (root / "local_data" / "icewine_prediction.sqlite3").read_bytes()
    cloud = _make_project(tmp_path / "cloud-parent")
    (cloud / "local_data" / "training" / "cloud-new.csv").write_text("new data", encoding="utf-8")
    (cloud / "config" / "display_names.yaml").write_text("teams: cloud\n", encoding="utf-8")
    connection = sqlite3.connect(cloud / "local_data" / "icewine_prediction.sqlite3")
    connection.execute("CREATE TABLE cloud_updates (id INTEGER)")
    connection.commit()
    connection.close()

    returning = prepare_return(cloud, tmp_path / "return", initial / "manifest.json")
    restore_return(root, returning, initial / "manifest.json")

    assert (root / "local_data" / "training" / "cloud-new.csv").read_text(encoding="utf-8") == "new data"
    assert (root / "config" / "display_names.yaml").read_text(encoding="utf-8") == "teams: cloud\n"
    connection = sqlite3.connect(root / "local_data" / "icewine_prediction.sqlite3")
    assert connection.execute("SELECT name FROM sqlite_master WHERE name = 'cloud_updates'").fetchone()
    connection.close()
    backups = list((root / ".web" / "cloud-handoff").glob("restore-backup-*/local_data/icewine_prediction.sqlite3"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == original_db

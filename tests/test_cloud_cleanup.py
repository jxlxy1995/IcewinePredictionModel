import subprocess
from pathlib import Path

import pytest

from scripts.cloud import cleanup_handoff
from scripts.cloud.cleanup_handoff import (
    CleanupError,
    find_bundles,
    remove_bundles,
    service_is_active,
)


def _make_bundle(root: Path, name: str) -> Path:
    bundle = root / name
    (bundle / "payload").mkdir(parents=True)
    (bundle / "manifest.json").write_text("{}\n", encoding="utf-8")
    return bundle


def test_find_bundles_only_returns_direct_initial_and_return_directories(tmp_path: Path):
    _make_bundle(tmp_path, "initial-20260928-120708")
    _make_bundle(tmp_path, "return-20260929-080000")
    _make_bundle(tmp_path, "other-directory")
    (tmp_path / "initial-incomplete").mkdir()
    nested = tmp_path / "nested" / "initial-20260929-090000"
    nested.mkdir(parents=True)

    assert [path.name for path in find_bundles(tmp_path)] == [
        "initial-20260928-120708",
        "return-20260929-080000",
    ]


def test_remove_bundles_keeps_latest_bundle_per_kind_by_default(tmp_path: Path):
    old_initial = _make_bundle(tmp_path, "initial-20260928-120708")
    latest_initial = _make_bundle(tmp_path, "initial-20260929-120708")
    old_return = _make_bundle(tmp_path, "return-20260928-180000")
    latest_return = _make_bundle(tmp_path, "return-20260929-180000")

    removed = remove_bundles(tmp_path, keep_latest=1)

    assert removed == [old_initial, old_return]
    assert not old_initial.exists()
    assert latest_initial.exists()
    assert not old_return.exists()
    assert latest_return.exists()


def test_remove_requires_handoff_root_and_nonnegative_retention(tmp_path: Path):
    with pytest.raises(CleanupError):
        remove_bundles(tmp_path / "missing", keep_latest=1)
    with pytest.raises(CleanupError):
        remove_bundles(tmp_path, keep_latest=-1)


def test_service_is_active_uses_systemctl_result(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "active\n", ""),
    )
    assert service_is_active("icewine.service") is True

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 3, "inactive\n", ""),
    )
    assert service_is_active("icewine.service") is False

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 4, "unknown\n", ""),
    )
    with pytest.raises(CleanupError):
        service_is_active("icewine.service")


def test_cli_defaults_to_preview_and_keeps_latest_bundle_per_kind(tmp_path: Path, monkeypatch, capsys):
    old_initial = _make_bundle(tmp_path, "initial-20260928-120708")
    _make_bundle(tmp_path, "initial-20260929-120708")
    monkeypatch.setattr(cleanup_handoff, "_HANDOFF_ROOT", tmp_path)

    assert cleanup_handoff.main([]) == 0

    assert old_initial.exists()
    assert "当前为预览模式" in capsys.readouterr().out


def test_cli_apply_requires_stopped_service_and_exact_confirmation(
    tmp_path: Path, monkeypatch, capsys
):
    old_initial = _make_bundle(tmp_path, "initial-20260928-120708")
    _make_bundle(tmp_path, "initial-20260929-120708")
    monkeypatch.setattr(cleanup_handoff, "_HANDOFF_ROOT", tmp_path)
    monkeypatch.setattr(cleanup_handoff, "service_is_active", lambda: True)

    assert cleanup_handoff.main(["--apply"]) == 1

    assert old_initial.exists()
    assert "仍在运行" in capsys.readouterr().err


def test_cli_apply_deletes_only_after_exact_confirmation(tmp_path: Path, monkeypatch, capsys):
    old_initial = _make_bundle(tmp_path, "initial-20260928-120708")
    latest_initial = _make_bundle(tmp_path, "initial-20260929-120708")
    monkeypatch.setattr(cleanup_handoff, "_HANDOFF_ROOT", tmp_path)
    monkeypatch.setattr(cleanup_handoff, "service_is_active", lambda: False)
    monkeypatch.setattr(
        "builtins.input", lambda _: "DELETE OLD ICEWINE HANDOFF BUNDLES"
    )

    assert cleanup_handoff.main(["--apply"]) == 0

    assert not old_initial.exists()
    assert latest_initial.exists()
    assert "已删除 1 个旧交接包" in capsys.readouterr().out

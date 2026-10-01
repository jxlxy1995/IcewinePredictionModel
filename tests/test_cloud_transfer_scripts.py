import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BASH = Path("D:/Program Files/Git/bin/bash.exe")


def _bash_path(path: Path) -> str:
    return f"/{path.drive[0].lower()}{path.as_posix()[2:]}"


@pytest.mark.parametrize("name", ["cloud_upload.sh", "cloud_return.sh"])
def test_transfer_script_has_valid_bash_syntax(name):
    result = subprocess.run(
        [str(BASH), "-n", _bash_path(ROOT / "scripts" / name)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("name", ["cloud_upload.sh", "cloud_return.sh"])
def test_transfer_script_explains_bash_options(name):
    result = subprocess.run(
        [str(BASH), _bash_path(ROOT / "scripts" / name), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--remote-host" in result.stdout
    assert "--ssh-port" in result.stdout


def test_upload_exposes_explicit_code_only_mode():
    result = subprocess.run(
        [
            str(BASH), _bash_path(ROOT / "scripts" / "cloud_upload.sh"), "--help"
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--code-only" in result.stdout


def test_upload_rejects_unsafe_remote_path_before_network():
    result = subprocess.run(
        [
            str(BASH), _bash_path(ROOT / "scripts" / "cloud_upload.sh"),
            "--remote-host", "127.0.0.1",
            "--remote-project-root", "unsafe path",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode != 0
    assert "remote project path" in result.stderr.lower()


def test_return_rejects_missing_initial_manifest_before_network(tmp_path):
    result = subprocess.run(
        [
            str(BASH), _bash_path(ROOT / "scripts" / "cloud_return.sh"),
            "--remote-host", "127.0.0.1",
            "--initial-manifest", _bash_path(tmp_path / "missing.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode != 0
    assert "initial manifest" in result.stderr.lower()

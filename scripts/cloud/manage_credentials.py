#!/usr/bin/env python3
"""Manage short-lived device credentials for the Nginx Basic Auth file."""

from __future__ import annotations

import argparse
import fcntl
import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path


PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
DEFAULT_HTPASSWD_FILE = Path("/etc/nginx/.htpasswd-icewine")


def _password() -> str:
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(12))


def _validate_username(value: str) -> str:
    if not USERNAME_PATTERN.fullmatch(value):
        raise ValueError("设备名需使用 2-32 位小写字母、数字、下划线或短横线，且以字母开头")
    return value


def _file_path() -> Path:
    return Path(os.environ.get("ICEWINE_HTPASSWD_FILE", DEFAULT_HTPASSWD_FILE))


def _locked_file(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=0o640, exist_ok=True)
    os.chmod(path, 0o640)
    handle = path.open("r+")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


def _user_exists(path: Path, username: str) -> bool:
    if not path.exists():
        return False
    prefix = f"{username}:"
    return any(line.startswith(prefix) for line in path.read_text(encoding="utf-8").splitlines())


def add(username: str, path: Path) -> str:
    _validate_username(username)
    htpasswd = shutil.which("htpasswd")
    if htpasswd is None:
        raise RuntimeError("找不到 htpasswd，请先运行 setup.sh")
    with _locked_file(path) as handle:
        try:
            if _user_exists(path, username):
                raise ValueError(f"设备名已存在：{username}")
            password = _password()
            subprocess.run(
                [htpasswd, "-i", "-B", str(path), username],
                input=password + "\n",
                text=True,
                check=True,
                stdout=subprocess.DEVNULL,
            )
            os.chmod(path, 0o640)
            return password
        finally:
            handle.flush()


def remove(username: str, path: Path) -> None:
    _validate_username(username)
    if not path.exists() or not _user_exists(path, username):
        raise ValueError(f"设备名不存在：{username}")
    htpasswd = shutil.which("htpasswd")
    if htpasswd is None:
        raise RuntimeError("找不到 htpasswd，请先运行 setup.sh")
    with _locked_file(path):
        subprocess.run([htpasswd, "-D", str(path), username], check=True, stdout=subprocess.DEVNULL)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="管理 Icewine 云端设备凭据")
    parser.add_argument("--file", type=Path, default=_file_path(), help="htpasswd 文件路径")
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_parser = subparsers.add_parser("add", help="添加设备并生成密码")
    add_parser.add_argument("username")
    remove_parser = subparsers.add_parser("remove", help="撤销设备凭据")
    remove_parser.add_argument("username")
    args = parser.parse_args(argv)
    try:
        if args.command == "add":
            password = add(args.username, args.file)
            print(f"设备名：{args.username}")
            print(f"密码：{password}")
        else:
            remove(args.username, args.file)
            print(f"已撤销：{args.username}")
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"凭据操作失败：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

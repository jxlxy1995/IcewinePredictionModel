#!/usr/bin/env python3
"""Safely remove old cloud handoff bundles after a return is accepted."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


class CleanupError(RuntimeError):
    """Raised when the cleanup target is invalid or unsafe to process."""


_BUNDLE_PATTERN = re.compile(r"^(initial|return)-[A-Za-z0-9._-]+$")
_CONFIRMATION = "DELETE OLD ICEWINE HANDOFF BUNDLES"
_HANDOFF_ROOT = Path("/opt/icewine-handoff")


def find_bundles(handoff_root: Path) -> list[Path]:
    """Return safe, direct child bundle directories in deterministic order."""
    root = Path(handoff_root)
    if root.is_symlink() or not root.is_dir():
        raise CleanupError(f"交接目录不存在或不是目录：{root}")
    return sorted(
        (
            child
            for child in root.iterdir()
            if (
                child.is_dir()
                and not child.is_symlink()
                and _BUNDLE_PATTERN.fullmatch(child.name)
                and (child / "manifest.json").is_file()
                and (child / "payload").is_dir()
            )
        ),
        key=lambda path: path.name,
    )


def bundles_to_remove(bundles: list[Path], keep_latest: int) -> list[Path]:
    if keep_latest < 0:
        raise CleanupError("--keep-latest 不能小于 0")
    by_kind: dict[str, list[Path]] = {"initial": [], "return": []}
    for bundle in bundles:
        kind = bundle.name.split("-", 1)[0]
        by_kind[kind].append(bundle)
    return [
        bundle
        for kind in ("initial", "return")
        for bundle in by_kind[kind][:-keep_latest or None]
    ]


def remove_bundles(handoff_root: Path, keep_latest: int = 1) -> list[Path]:
    """Delete old bundles, retaining the newest N bundles of each kind."""
    bundles = find_bundles(handoff_root)
    removed = bundles_to_remove(bundles, keep_latest)
    for bundle in removed:
        shutil.rmtree(bundle)
    return removed


def service_is_active(service: str = "icewine.service") -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise CleanupError(f"无法检查 {service} 状态：{error}") from error
    state = result.stdout.strip()
    if state == "active":
        return True
    if state in {"inactive", "failed"}:
        return False
    raise CleanupError(f"无法确认 {service} 已停止，当前状态：{state or 'unknown'}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="清理已完成云端交接的旧交接包")
    parser.add_argument(
        "--keep-latest",
        type=int,
        default=1,
        help="每类保留最新包的数量（默认：1；0 表示全部删除）",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="执行删除；省略时只预览",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        bundles = find_bundles(_HANDOFF_ROOT)
        targets = bundles_to_remove(bundles, args.keep_latest)
        print(f"交接包目录：{_HANDOFF_ROOT}")
        print(f"发现交接包：{len(bundles)} 个；保留每类最新：{args.keep_latest} 个")
        if not targets:
            print("没有需要清理的旧交接包。")
            return 0
        print("准备清理：")
        for bundle in targets:
            print(f"  {bundle}")
        if not args.apply:
            print("当前为预览模式；未删除任何文件。需要删除时加 --apply。")
            return 0
        if service_is_active():
            raise CleanupError("icewine.service 仍在运行，请先停止服务后再清理")
        try:
            answer = input(f"请输入 {_CONFIRMATION} 以确认删除：")
        except EOFError as error:
            raise CleanupError("未收到交互确认，未删除任何文件") from error
        if answer.strip() != _CONFIRMATION:
            print("确认短语不匹配，未删除任何文件。")
            return 1
        removed = remove_bundles(_HANDOFF_ROOT, args.keep_latest)
        print(f"已删除 {len(removed)} 个旧交接包。")
        return 0
    except (CleanupError, OSError) as error:
        print(f"清理失败：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

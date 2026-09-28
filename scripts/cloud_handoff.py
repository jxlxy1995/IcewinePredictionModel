"""Command line entry point for cloud data handoff bundles."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from icewine_prediction.cloud_handoff import (  # noqa: E402
    HandoffError,
    prepare_initial,
    prepare_return,
    restore_return,
    verify_bundle,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="云端数据交接工具")
    subparsers = parser.add_subparsers(dest="command", required=True)
    initial = subparsers.add_parser("prepare-initial", help="制作首次上传包")
    initial.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    initial.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / ".web/cloud-handoff")
    returning = subparsers.add_parser("prepare-return", help="制作云端回迁包")
    returning.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    returning.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / ".web/cloud-handoff")
    returning.add_argument("--initial-manifest", type=Path, required=True)
    verify = subparsers.add_parser("verify", help="校验交接包")
    verify.add_argument("--bundle-dir", type=Path, required=True)
    restore = subparsers.add_parser("restore-return", help="回迁到本机")
    restore.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    restore.add_argument("--bundle-dir", type=Path, required=True)
    restore.add_argument("--initial-manifest", type=Path, required=True)
    args = parser.parse_args()

    try:
        if args.command == "prepare-initial":
            bundle = prepare_initial(args.project_root, args.output_dir)
        elif args.command == "prepare-return":
            bundle = prepare_return(args.project_root, args.output_dir, args.initial_manifest)
        elif args.command == "verify":
            verify_bundle(args.bundle_dir)
            print("交接包校验通过")
            return 0
        else:
            restore_return(args.project_root, args.bundle_dir, args.initial_manifest)
            print("回迁完成，原文件已备份在 .web/cloud-handoff")
            return 0
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        total = sum(item["size"] for item in manifest["files"])
        print(f"交接包：{bundle}")
        print(f"文件：{len(manifest['files'])} 个，大小：{total / (1024 ** 3):.3f} GiB")
        return 0
    except (HandoffError, OSError, sqlite3.Error) as error:
        print(f"交接失败：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

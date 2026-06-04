#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash scripts/clear_paper_recommendation_records.sh [--yes] [database_path]

Defaults:
  database_path = local_data/icewine_prediction.sqlite3

This deletes every row from paper_recommendation_records only.
EOF
}

assume_yes=0
database_path=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -y|--yes)
      assume_yes=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -n "$database_path" ]]; then
        echo "Unexpected argument: $1" >&2
        usage >&2
        exit 2
      fi
      database_path="$1"
      shift
      ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -z "$database_path" ]]; then
  database_path="$repo_root/local_data/icewine_prediction.sqlite3"
fi

if [[ ! -f "$database_path" ]]; then
  echo "Database not found: $database_path" >&2
  exit 1
fi

if [[ "$assume_yes" -ne 1 ]]; then
  echo "About to delete all rows from paper_recommendation_records:"
  echo "  $database_path"
  read -r -p "Type DELETE_PAPER_RECORDS to continue: " confirmation
  if [[ "$confirmation" != "DELETE_PAPER_RECORDS" ]]; then
    echo "Aborted."
    exit 0
  fi
fi

python - "$database_path" <<'PY'
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


database_path = Path(sys.argv[1])
with sqlite3.connect(database_path) as connection:
    table_exists = connection.execute(
        "select 1 from sqlite_master where type = 'table' and name = ?",
        ("paper_recommendation_records",),
    ).fetchone()
    if table_exists is None:
        raise SystemExit("Table not found: paper_recommendation_records")

    before_count = connection.execute(
        "select count(*) from paper_recommendation_records"
    ).fetchone()[0]
    connection.execute("delete from paper_recommendation_records")
    try:
        connection.execute(
            "delete from sqlite_sequence where name = ?",
            ("paper_recommendation_records",),
        )
    except sqlite3.OperationalError:
        pass
    connection.commit()

print(f"Deleted {before_count} paper recommendation record(s).")
PY

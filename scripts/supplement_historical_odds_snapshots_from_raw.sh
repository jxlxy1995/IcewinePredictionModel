#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash scripts/supplement_historical_odds_snapshots_from_raw.sh [--match-ids id1,id2] [--source-name oddspapi] [--bookmaker pinnacle]

This supplements historical_odds_snapshots from historical_odds_raw_snapshots
for standard execution timepoints T-60/T-30/T-25/T-20/T-15/T-10.
EOF
}

match_ids=""
source_name="oddspapi"
bookmaker="pinnacle"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --match-ids)
      match_ids="${2:-}"
      shift 2
      ;;
    --source-name)
      source_name="${2:-}"
      shift 2
      ;;
    --bookmaker)
      bookmaker="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unexpected argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
export PYTHONPATH="${PYTHONPATH:-src}"

args=(
  -m icewine_prediction.cli
  odds-source
  oddspapi-supplement-snapshots-from-raw
  --source-name "$source_name"
  --bookmaker "$bookmaker"
)

if [[ -n "$match_ids" ]]; then
  args+=(--match-ids "$match_ids")
fi

python "${args[@]}"

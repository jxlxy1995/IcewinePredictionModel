#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/cloud_return.sh --remote-host HOST [options]

  --remote-host HOST            Server IP or DNS name (required)
  --remote-user USER            SSH user (default: ubuntu)
  --ssh-port PORT               SSH port (default: 22)
  --identity-file PATH          SSH private key path
  --remote-project-root PATH    Server project directory
  --remote-stage-root PATH      Server handoff directory
  --project-root PATH           Local project directory
  --output-dir PATH             Local handoff directory
  --initial-manifest PATH       Initial bundle manifest
EOF
}

die() { printf '%s\n' "$*" >&2; exit 1; }

remote_host=""
remote_user="ubuntu"
ssh_port="22"
identity_file=""
remote_project_root="/opt/icewine-prediction-model"
remote_stage_root="/opt/icewine-handoff"
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir=""
initial_manifest=""

while (($#)); do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --remote-host|--remote-user|--ssh-port|--identity-file|--remote-project-root|--remote-stage-root|--project-root|--output-dir|--initial-manifest)
      (($# >= 2)) || die "Missing value for $1"
      case "$1" in
        --remote-host) remote_host="$2" ;;
        --remote-user) remote_user="$2" ;;
        --ssh-port) ssh_port="$2" ;;
        --identity-file) identity_file="$2" ;;
        --remote-project-root) remote_project_root="$2" ;;
        --remote-stage-root) remote_stage_root="$2" ;;
        --project-root) project_root="$2" ;;
        --output-dir) output_dir="$2" ;;
        --initial-manifest) initial_manifest="$2" ;;
      esac
      shift 2 ;;
    *) die "Unknown option: $1" ;;
  esac
done

[[ -n "$remote_host" ]] || die "--remote-host is required"
[[ "$remote_host" =~ ^[A-Za-z0-9.-]+$ ]] || die "Invalid remote host"
[[ "$remote_user" =~ ^[a-z_][a-z0-9_-]*$ ]] || die "Invalid remote user"
[[ "$ssh_port" =~ ^[0-9]+$ ]] && ((ssh_port >= 1 && ssh_port <= 65535)) || die "Invalid SSH port"
safe_remote_path() {
  [[ "$1" =~ ^/[A-Za-z0-9._/-]+$ && "$1" != *'/../'* && "$1" != */.. && "$1" != *'/./'* ]]
}
safe_remote_path "$remote_project_root" || die "Invalid remote project path: $remote_project_root"
safe_remote_path "$remote_stage_root" || die "Invalid remote stage path: $remote_stage_root"
[[ -d "$project_root" ]] || die "Missing local project directory: $project_root"
project_root="$(cd "$project_root" && pwd)"
output_dir="${output_dir:-$project_root/.web/cloud-handoff}"
[[ -z "$identity_file" || -f "$identity_file" ]] || die "Missing SSH identity file: $identity_file"
if [[ -z "$initial_manifest" ]]; then
  [[ -d "$output_dir" ]] || die "Initial manifest was not found; pass --initial-manifest"
  initial_manifest="$(find "$output_dir" -type f -path '*/initial-*/manifest.json' -print | LC_ALL=C sort | tail -n 1)"
fi
[[ -f "$initial_manifest" ]] || die "Initial manifest was not found: $initial_manifest"

ssh_args=(-p "$ssh_port")
scp_args=(-P "$ssh_port" -r)
if [[ -n "$identity_file" ]]; then
  ssh_args+=(-i "$identity_file")
  scp_args+=(-i "$identity_file")
fi
remote="$remote_user@$remote_host"
remote_run() { ssh "${ssh_args[@]}" "$remote" "$1"; }
remote_copy() { scp "${scp_args[@]}" "$1" "$2"; }

assert_local_idle() {
  local sockets
  sockets="$(netstat -ano -p tcp)" || die "Cannot inspect local TCP ports"
  if awk '$2 ~ /:(8000|5173)$/ && $4 == "LISTENING" { found=1 } END { exit !found }' <<< "$sockets"; then
    die "Local Web is running on 8000 or 5173. Stop it before return. The existing 8080 app is unaffected."
  fi
  if powershell.exe -NoProfile -NonInteractive -Command '$ErrorActionPreference="Stop"; try { $active = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object { $_.ProcessId -ne $PID -and ([string]$_.CommandLine) -match "oddspapi-worker|training_orchestration|icewine_cli.*training" }); if ($active.Count -gt 0) { exit 1 }; exit 0 } catch { exit 2 }' >/dev/null; then
    :
  else
    die "A local training or odds worker is active, or its status could not be checked"
  fi
}

assert_local_idle
python_bin="${PYTHON_BIN:-/c/ProgramData/anaconda3/python}"
[[ -x "$python_bin" ]] || die "Missing required Python: $python_bin"
handoff_cli="$project_root/scripts/cloud_handoff.py"
[[ -f "$handoff_cli" ]] || die "Missing handoff tool: $handoff_cli"
mkdir -p "$output_dir"
export PYTHONPATH="$project_root/src" PYTHONIOENCODING=utf-8

initial_name="$(basename "$(dirname "$initial_manifest")")"
[[ "$initial_name" =~ ^initial-[A-Za-z0-9.-]+$ ]] || die "Initial manifest must belong to an initial bundle"
remote_initial_manifest="$remote_stage_root/$initial_name/manifest.json"
remote_status="$(remote_run 'systemctl is-active icewine.service 2>/dev/null || true')"
[[ "$remote_status" != "active" ]] || die "Cloud Icewine service is still active; stop it before return"

remote_run "python3.11 '$remote_project_root/scripts/cloud_handoff.py' prepare-return --project-root '$remote_project_root' --output-dir '$remote_stage_root' --initial-manifest '$remote_initial_manifest'"
remote_bundle="$(remote_run "find '$remote_stage_root' -maxdepth 1 -type d -name 'return-*' -printf '%f\n' | LC_ALL=C sort | tail -n 1")"
[[ "$remote_bundle" =~ ^return-[A-Za-z0-9.-]+$ ]] || die "Cloud did not return a safe bundle name"
local_bundle="$output_dir/$remote_bundle"
[[ ! -e "$local_bundle" ]] || die "Local return bundle already exists: $local_bundle"
remote_copy "$remote:$remote_stage_root/$remote_bundle" "$output_dir/"
"$python_bin" "$handoff_cli" verify --bundle-dir "$local_bundle"
"$python_bin" "$handoff_cli" restore-return --project-root "$project_root" --bundle-dir "$local_bundle" --initial-manifest "$initial_manifest"

printf 'Return bundle verified and restored: %s\n' "$local_bundle"
printf 'Complete the business check before closing cloud 8081. The existing 8080 app was not changed.\n'

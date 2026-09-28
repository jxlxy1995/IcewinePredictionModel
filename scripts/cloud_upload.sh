#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/cloud_upload.sh --remote-host HOST [options]

  --remote-host HOST            Server IP or DNS name (required)
  --remote-user USER            SSH user (default: ubuntu)
  --service-user USER           systemd user (default: ubuntu)
  --ssh-port PORT               SSH port (default: 22)
  --identity-file PATH          SSH private key path
  --remote-project-root PATH    Server project directory
  --remote-stage-root PATH      Server handoff directory
  --project-root PATH           Local project directory
  --output-dir PATH             Local handoff directory
  --env-file PATH               Local .env file
EOF
}

die() { printf '%s\n' "$*" >&2; exit 1; }

remote_host=""
remote_user="ubuntu"
service_user="ubuntu"
ssh_port="22"
identity_file=""
remote_project_root="/opt/icewine-prediction-model"
remote_stage_root="/opt/icewine-handoff"
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir=""
env_file=""

while (($#)); do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --remote-host|--remote-user|--service-user|--ssh-port|--identity-file|--remote-project-root|--remote-stage-root|--project-root|--output-dir|--env-file)
      (($# >= 2)) || die "Missing value for $1"
      case "$1" in
        --remote-host) remote_host="$2" ;;
        --remote-user) remote_user="$2" ;;
        --service-user) service_user="$2" ;;
        --ssh-port) ssh_port="$2" ;;
        --identity-file) identity_file="$2" ;;
        --remote-project-root) remote_project_root="$2" ;;
        --remote-stage-root) remote_stage_root="$2" ;;
        --project-root) project_root="$2" ;;
        --output-dir) output_dir="$2" ;;
        --env-file) env_file="$2" ;;
      esac
      shift 2 ;;
    *) die "Unknown option: $1" ;;
  esac
done

[[ -n "$remote_host" ]] || die "--remote-host is required"
[[ "$remote_host" =~ ^[A-Za-z0-9.-]+$ ]] || die "Invalid remote host"
[[ "$remote_user" =~ ^[a-z_][a-z0-9_-]*$ ]] || die "Invalid remote user"
[[ "$service_user" =~ ^[a-z_][a-z0-9_-]*$ ]] || die "Invalid service user"
[[ "$ssh_port" =~ ^[0-9]+$ ]] && ((ssh_port >= 1 && ssh_port <= 65535)) || die "Invalid SSH port"

safe_remote_path() {
  [[ "$1" =~ ^/[A-Za-z0-9._/-]+$ && "$1" != *'/../'* && "$1" != */.. && "$1" != *'/./'* ]]
}
safe_remote_path "$remote_project_root" || die "Invalid remote project path: $remote_project_root"
safe_remote_path "$remote_stage_root" || die "Invalid remote stage path: $remote_stage_root"
[[ -d "$project_root" ]] || die "Missing local project directory: $project_root"
project_root="$(cd "$project_root" && pwd)"
output_dir="${output_dir:-$project_root/.web/cloud-handoff}"
env_file="${env_file:-$project_root/.env}"
[[ -f "$env_file" ]] || die "Missing .env file: $env_file"
[[ -z "$identity_file" || -f "$identity_file" ]] || die "Missing SSH identity file: $identity_file"

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
    die "Local Web is running on 8000 or 5173. Stop it before upload. The existing 8080 app is unaffected."
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
marker="$(mktemp "$output_dir/.initial-start.XXXXXX")"
trap 'rm -f "$marker"' EXIT
"$python_bin" "$handoff_cli" prepare-initial --project-root "$project_root" --output-dir "$output_dir"
bundle="$(find "$output_dir" -maxdepth 1 -type d -name 'initial-*' -newer "$marker" -print | LC_ALL=C sort | tail -n 1)"
[[ -n "$bundle" ]] || die "New initial bundle was not found"
"$python_bin" "$handoff_cli" verify --bundle-dir "$bundle"

remote_run "sudo install -d -o '$remote_user' -g '$remote_user' -m 0700 '$remote_stage_root'"
remote_copy "$bundle" "$remote:$remote_stage_root/"
remote_bundle="$remote_stage_root/$(basename "$bundle")"
remote_run "python3.11 '$remote_bundle/payload/scripts/cloud_handoff.py' verify --bundle-dir '$remote_bundle'"

remote_env="$remote_bundle/.env.upload"
remote_copy "$env_file" "$remote:$remote_env"
remote_run "sudo install -d -m 0755 /etc/icewine && sudo install -o root -g '$service_user' -m 0640 '$remote_env' /etc/icewine/icewine.env && rm -f '$remote_env'"
remote_run "sudo install -d -m 0755 '$remote_project_root' && sudo cp -a '$remote_bundle/payload/.' '$remote_project_root/' && sudo env PROJECT_ROOT='$remote_project_root' SERVICE_USER='$service_user' bash '$remote_project_root/scripts/cloud/setup.sh' && sudo systemctl is-active --quiet icewine.service && sudo systemctl is-active --quiet nginx"

printf 'Initial bundle uploaded: %s\n' "$bundle"
printf 'Cloud entrypoint: HTTP 8081. The existing 8080 app was not changed.\n'

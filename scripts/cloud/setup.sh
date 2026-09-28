#!/usr/bin/env bash
set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "请使用 root 运行此脚本" >&2
    exit 1
fi

PROJECT_ROOT="${PROJECT_ROOT:-/opt/icewine-prediction-model}"
SERVICE_USER="${SERVICE_USER:-ubuntu}"
VENV_PATH="${VENV_PATH:-$PROJECT_ROOT/.venv}"
ENV_FILE="${ENV_FILE:-/etc/icewine/icewine.env}"
AUTH_FILE="${AUTH_FILE:-/etc/nginx/.htpasswd-icewine}"
SERVER_NAME="${SERVER_NAME:-_}"

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    echo "不存在服务用户：$SERVICE_USER" >&2
    exit 1
fi
if [ ! -f "$PROJECT_ROOT/pyproject.toml" ]; then
    echo "项目目录缺少 pyproject.toml：$PROJECT_ROOT" >&2
    exit 1
fi
if [ ! -f "$PROJECT_ROOT/web/dist/index.html" ]; then
    echo "项目目录缺少前端构建产物：$PROJECT_ROOT/web/dist/index.html" >&2
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3.11 python3.11-venv python3-pip nginx apache2-utils

install -d -o root -g root -m 0755 /etc/icewine
if [ -f "$PROJECT_ROOT/.env" ] && [ ! -f "$ENV_FILE" ]; then
    install -o root -g "$SERVICE_USER" -m 0640 "$PROJECT_ROOT/.env" "$ENV_FILE"
elif [ ! -f "$ENV_FILE" ]; then
    install -o root -g "$SERVICE_USER" -m 0640 /dev/null "$ENV_FILE"
fi

ENV_FILE="$ENV_FILE" python3.11 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["ENV_FILE"])
data = path.read_bytes()
bom = bytes.fromhex("efbbbf")
if data.startswith(bom):
    path.write_bytes(data[len(bom):])
PY
chown root:"$SERVICE_USER" "$ENV_FILE"
chmod 0640 "$ENV_FILE"

install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0755 \
    "$PROJECT_ROOT/local_data" \
    "$PROJECT_ROOT/logs" \
    "$PROJECT_ROOT/docs" \
    "$PROJECT_ROOT/config" \
    "$PROJECT_ROOT/.web"

if [ ! -x "$VENV_PATH/bin/python" ]; then
    python3.11 -m venv "$VENV_PATH"
fi
"$VENV_PATH/bin/python" -m pip install --upgrade pip
"$VENV_PATH/bin/python" -m pip install --no-cache-dir -e "$PROJECT_ROOT"

service_template="$PROJECT_ROOT/deploy/cloud/icewine.service.template"
nginx_template="$PROJECT_ROOT/deploy/cloud/nginx.conf.template"
[ -f "$service_template" ] && [ -f "$nginx_template" ] || {
    echo "缺少云端配置模板" >&2
    exit 1
}

escape_sed() {
    printf '%s' "$1" | sed 's/[&|]/\\&/g'
}
project_root_escaped=$(escape_sed "$PROJECT_ROOT")
service_user_escaped=$(escape_sed "$SERVICE_USER")
venv_path_escaped=$(escape_sed "$VENV_PATH")
env_file_escaped=$(escape_sed "$ENV_FILE")
auth_file_escaped=$(escape_sed "$AUTH_FILE")
server_name_escaped=$(escape_sed "$SERVER_NAME")

sed \
    -e "s|__PROJECT_ROOT__|$project_root_escaped|g" \
    -e "s|__SERVICE_USER__|$service_user_escaped|g" \
    -e "s|__VENV_PATH__|$venv_path_escaped|g" \
    -e "s|__ENV_FILE__|$env_file_escaped|g" \
    "$service_template" > /etc/systemd/system/icewine.service

install -d -m 0755 /etc/nginx/sites-available /etc/nginx/sites-enabled
sed \
    -e "s|__PROJECT_ROOT__|$project_root_escaped|g" \
    -e "s|__AUTH_FILE__|$auth_file_escaped|g" \
    -e "s|__SERVER_NAME__|$server_name_escaped|g" \
    "$nginx_template" > /etc/nginx/sites-available/icewine.conf
ln -sfn /etc/nginx/sites-available/icewine.conf /etc/nginx/sites-enabled/icewine.conf

if [ ! -f "$AUTH_FILE" ]; then
    install -o root -g www-data -m 0640 /dev/null "$AUTH_FILE"
else
    chown root:www-data "$AUTH_FILE"
    chmod 0640 "$AUTH_FILE"
fi

systemctl daemon-reload
nginx -t
systemctl enable --now icewine.service
systemctl enable --now nginx
systemctl reload nginx

echo "Icewine 云端服务已配置：HTTP 8081，后端仅监听本机 8000。"
echo "请使用 manage_credentials.py add <设备名> 创建访问凭据。"

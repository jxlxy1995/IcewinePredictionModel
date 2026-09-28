from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_systemd_template_runs_one_localhost_backend_worker():
    template = (ROOT / "deploy" / "cloud" / "icewine.service.template").read_text(encoding="utf-8")
    assert "--host 127.0.0.1" in template
    assert "--port 8000" in template
    assert "--workers 1" in template
    assert "Restart=on-failure" in template
    assert "User=__SERVICE_USER__" in template
    assert "8080" not in template


def test_nginx_template_protects_page_and_api_on_8081():
    template = (ROOT / "deploy" / "cloud" / "nginx.conf.template").read_text(encoding="utf-8")
    assert "listen 8081" in template
    assert "auth_basic" in template
    assert "auth_basic_user_file" in template
    assert "location /api/" in template
    assert "127.0.0.1:8000" in template
    assert "8080" not in template


def test_credential_manager_uses_interactive_htpasswd_and_simple_password_alphabet():
    source = (ROOT / "scripts" / "cloud" / "manage_credentials.py").read_text(encoding="utf-8")
    assert "secrets.choice" in source
    assert "range(12)" in source
    assert "htpasswd" in source
    assert "-i" in source
    assert "-B" in source
    assert "-b" not in source


def test_setup_installs_and_validates_only_new_cloud_entrypoint():
    source = (ROOT / "scripts" / "cloud" / "setup.sh").read_text(encoding="utf-8")
    assert "nginx -t" in source
    assert "systemctl daemon-reload" in source
    assert "8081" in source
    assert "8080" not in source
    assert "sites-enabled/default" not in source


def test_setup_prepares_systemd_writable_paths_and_normalizes_env_bom():
    source = (ROOT / "scripts" / "cloud" / "setup.sh").read_text(encoding="utf-8")
    assert '"$PROJECT_ROOT/.web"' in source
    assert '"$PROJECT_ROOT/local_data"' in source
    assert '"$PROJECT_ROOT/logs"' in source
    assert '"$PROJECT_ROOT/docs"' in source
    assert '"$PROJECT_ROOT/config"' in source
    assert 'bytes.fromhex("efbbbf")' in source

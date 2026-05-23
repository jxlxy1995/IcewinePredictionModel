from icewine_prediction.settings import load_project_settings


def test_load_project_settings_reads_yaml_and_env(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "sources.yaml").write_text(
        """
api_football:
  base_url: https://v3.football.api-sports.io
  timeout_seconds: 20
  daily_request_budget: 100
  cache_enabled: true
""",
        encoding="utf-8",
    )
    (config_dir / "leagues.yaml").write_text(
        """
leagues:
  - name: Premier League
    country: England
    api_football_id: 39
    enabled: true
    priority: 100
""",
        encoding="utf-8",
    )
    (config_dir / "sync.yaml").write_text(
        """
default_days: 3
default_source: api_football
sync_odds: true
sync_results: true
budget_guard_enabled: true
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("API_FOOTBALL_KEY", "secret-key")

    settings = load_project_settings(config_dir)

    assert settings.api_football_key == "secret-key"
    assert settings.sources["api_football"].daily_request_budget == 100
    assert settings.leagues[0].name == "Premier League"
    assert settings.sync.default_days == 3


def test_load_project_settings_reads_bom_env_file(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "sources.yaml").write_text(
        """
api_football:
  base_url: https://v3.football.api-sports.io
  timeout_seconds: 20
  daily_request_budget: 100
  cache_enabled: true
""",
        encoding="utf-8",
    )
    (config_dir / "leagues.yaml").write_text("leagues: []\n", encoding="utf-8")
    (config_dir / "sync.yaml").write_text(
        """
default_days: 3
default_source: api_football
sync_odds: true
sync_results: true
budget_guard_enabled: true
""",
        encoding="utf-8",
    )
    env_path = tmp_path / ".env"
    env_path.write_text("API_FOOTBALL_KEY=secret-key\n", encoding="utf-8-sig")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)

    settings = load_project_settings(config_dir)

    assert settings.api_football_key == "secret-key"


def test_default_league_whitelist_contains_mainstream_leagues():
    settings = load_project_settings()
    leagues_by_name = {league.name: league for league in settings.leagues}

    assert leagues_by_name["2. Bundesliga"].api_football_id == 79
    assert leagues_by_name["3. Liga"].api_football_id == 80
    assert leagues_by_name["J1 League"].api_football_id == 98
    assert leagues_by_name["K League 1"].api_football_id == 292

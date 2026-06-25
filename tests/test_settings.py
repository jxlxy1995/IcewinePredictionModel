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
    monkeypatch.setenv("ODDSPAPI_API_KEY", "odds-papi-key")
    monkeypatch.setenv("THE_ODDS_API_KEY", "the-odds-api-key")

    settings = load_project_settings(config_dir)

    assert settings.api_football_key == "secret-key"
    assert settings.odds_papi_key == "odds-papi-key"
    assert settings.the_odds_api_key == "the-odds-api-key"
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
    leagues_by_id = {league.api_football_id: league for league in settings.leagues}
    leagues_by_name = {league.name: league for league in settings.leagues}

    assert leagues_by_name["2. Bundesliga"].api_football_id == 79
    assert leagues_by_name["J1 League"].api_football_id == 98
    assert leagues_by_name["K League 1"].api_football_id == 292
    assert leagues_by_name["Ligue 2"].api_football_id == 62
    assert leagues_by_name["Eerste Divisie"].api_football_id == 89
    assert leagues_by_name["Veikkausliiga"].api_football_id == 244
    assert leagues_by_name["Superettan"].api_football_id == 114
    assert leagues_by_name["Liga I"].api_football_id == 283
    assert leagues_by_name["Ekstraklasa"].api_football_id == 106
    assert leagues_by_name["Primera División"].api_football_id == 265

    newly_promoted_main_league_ids = {104, 1087, 357, 358, 164, 274, 120, 262}
    assert newly_promoted_main_league_ids <= set(leagues_by_id)
    assert all(leagues_by_id[league_id].enabled for league_id in newly_promoted_main_league_ids)
    assert leagues_by_id[164].name == "Úrvalsdeild"
    assert leagues_by_id[164].country == "Iceland"
    assert leagues_by_id[358].name == "First Division"
    assert leagues_by_id[358].country == "Ireland"
    assert leagues_by_id[262].name == "Liga MX"
    assert leagues_by_id[262].country == "Mexico"

    assert leagues_by_id[1].name == "FIFA World Cup"
    assert leagues_by_id[1].country == "World"
    assert leagues_by_id[1].enabled is True

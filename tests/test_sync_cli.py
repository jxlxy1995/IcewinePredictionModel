from typer.testing import CliRunner

from icewine_prediction.cli import app


def test_sync_group_exposes_help():
    runner = CliRunner()

    result = runner.invoke(app, ["sync", "--help"])

    assert result.exit_code == 0
    assert "upcoming" in result.stdout
    assert "odds" in result.stdout
    assert "results" in result.stdout
    assert "history" in result.stdout
    assert "historical-odds" in result.stdout
    assert "backfill-history" in result.stdout


def test_sync_history_accepts_league_id_and_season_options(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.run_sync_history",
        lambda league_id, season: f"history:{league_id}:{season}",
    )

    result = runner.invoke(
        app,
        ["sync", "history", "--league-id", "140", "--season", "2024"],
    )

    assert result.exit_code == 0
    assert "history:140:2024" in result.stdout


def test_sync_historical_odds_accepts_days_option(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.run_sync_historical_odds",
        lambda days: f"historical-odds:{days}",
    )

    result = runner.invoke(app, ["sync", "historical-odds", "--days", "3"])

    assert result.exit_code == 0
    assert "historical-odds:3" in result.stdout


def test_sync_backfill_history_accepts_season_and_limit_options(monkeypatch):
    runner = CliRunner()

    def fake_load_project_settings():
        return type("Settings", (), {"leagues": ["league"]})()

    def fake_run_history_backfill(
        leagues,
        from_season,
        to_season,
        max_leagues,
        historical_odds_days,
    ):
        assert leagues == ["league"]
        return (
            f"backfill:{from_season}:{to_season}:"
            f"{max_leagues}:{historical_odds_days}"
        )

    monkeypatch.setattr("icewine_prediction.cli.load_project_settings", fake_load_project_settings)
    monkeypatch.setattr(
        "icewine_prediction.cli.run_history_backfill",
        fake_run_history_backfill,
    )

    result = runner.invoke(
        app,
        [
            "sync",
            "backfill-history",
            "--from-season",
            "2023",
            "--to-season",
            "2024",
            "--max-leagues",
            "2",
            "--historical-odds-days",
            "3",
        ],
    )

    assert result.exit_code == 0
    assert "backfill:2023:2024:2:3" in result.stdout

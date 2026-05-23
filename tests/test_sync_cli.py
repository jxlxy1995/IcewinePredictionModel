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

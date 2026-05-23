from typer.testing import CliRunner

from icewine_prediction.cli import app


def test_odds_source_group_exposes_oddspapi_commands():
    runner = CliRunner()

    result = runner.invoke(app, ["odds-source", "--help"])

    assert result.exit_code == 0
    assert "oddspapi-plan" in result.stdout
    assert "oddspapi-fetch" in result.stdout
    assert "oddspapi-probe" in result.stdout


def test_oddspapi_plan_accepts_season_and_match_limit(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.build_oddspapi_sync_plan",
        lambda season, max_matches: f"plan:{season}:{max_matches}",
    )

    result = runner.invoke(
        app,
        ["odds-source", "oddspapi-plan", "--season", "2025", "--max-matches", "20"],
    )

    assert result.exit_code == 0
    assert "plan:2025:20" in result.stdout


def test_oddspapi_fetch_accepts_season_match_limit_and_request_budget(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.run_oddspapi_sync",
        lambda season,
        max_matches,
        request_budget,
        timeout_seconds,
        max_snapshots_per_match,
        skip_match_ids=None,
        progress_callback=None: (
            f"fetch:{season}:{max_matches}:{request_budget}:"
            f"{timeout_seconds}:{max_snapshots_per_match}:{skip_match_ids}"
        ),
    )

    result = runner.invoke(
        app,
        [
            "odds-source",
            "oddspapi-fetch",
            "--season",
            "2025",
            "--max-matches",
            "20",
            "--request-budget",
            "50",
            "--timeout-seconds",
            "12",
            "--max-snapshots-per-match",
            "150",
            "--skip-match-ids",
            "1149,1150",
        ],
    )

    assert result.exit_code == 0
    assert "fetch:2025:20:50:12:150:{1149, 1150}" in result.stdout


def test_oddspapi_probe_accepts_season_match_limit_and_request_budget(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.build_oddspapi_probe_report",
        lambda season,
        max_matches,
        request_budget,
        timeout_seconds,
        skip_match_ids=None: (
            f"probe:{season}:{max_matches}:{request_budget}:"
            f"{timeout_seconds}:{skip_match_ids}"
        ),
    )

    result = runner.invoke(
        app,
        [
            "odds-source",
            "oddspapi-probe",
            "--season",
            "2025",
            "--max-matches",
            "20",
            "--request-budget",
            "50",
            "--timeout-seconds",
            "8",
            "--skip-match-ids",
            "1149,1150",
        ],
    )

    assert result.exit_code == 0
    assert "probe:2025:20:50:8:{1149, 1150}" in result.stdout

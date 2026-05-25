from typer.testing import CliRunner

from icewine_prediction.cli import app


def test_odds_source_group_exposes_oddspapi_commands():
    runner = CliRunner()

    result = runner.invoke(app, ["odds-source", "--help"])

    assert result.exit_code == 0
    assert "oddspapi-plan" in result.stdout
    assert "oddspapi-fetch" in result.stdout
    assert "oddspapi-probe" in result.stdout
    assert "oddspapi-audit-live" in result.stdout
    assert "oddspapi-clear-live" in result.stdout
    assert "oddspapi-clear-snapshots" in result.stdout
    assert "oddspapi-match-report" in result.stdout
    assert "oddspapi-batch-backfill" in result.stdout
    assert "oddspapi-batch-worker" in result.stdout
    assert "oddspapi-worker-start" in result.stdout
    assert "oddspapi-worker-status" in result.stdout


def test_oddspapi_plan_accepts_season_and_match_limit(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.build_oddspapi_sync_plan",
        lambda season, max_matches, league_ids=None, from_date=None: (
            f"plan:{season}:{max_matches}:{league_ids}:{from_date}"
        ),
    )

    result = runner.invoke(
        app,
        [
            "odds-source",
            "oddspapi-plan",
            "--season",
            "2025",
            "--max-matches",
            "20",
            "--league-ids",
            "78",
            "--from-date",
            "2026-01-15",
        ],
    )

    assert result.exit_code == 0
    assert "plan:2025:20:{'78'}:2026-01-15" in result.stdout


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
        league_ids=None,
        from_date=None,
        historical_odds_cooldown_seconds=5,
        progress_callback=None: (
            f"fetch:{season}:{max_matches}:{request_budget}:"
            f"{timeout_seconds}:{max_snapshots_per_match}:{skip_match_ids}:"
            f"{league_ids}:{from_date}:{historical_odds_cooldown_seconds}"
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
            "--league-ids",
            "135,140",
            "--from-date",
            "2026-01-15",
            "--historical-odds-cooldown-seconds",
            "3",
        ],
    )

    assert result.exit_code == 0
    assert "fetch:2025:20:50:12:150:{1149, 1150}:" in result.stdout
    assert "'135'" in result.stdout
    assert "'140'" in result.stdout
    assert ":2026-01-15:3.0" in result.stdout


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


def test_oddspapi_match_report_accepts_match_id(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.build_oddspapi_match_report",
        lambda match_id: f"match-report:{match_id}",
    )

    result = runner.invoke(
        app,
        ["odds-source", "oddspapi-match-report", "--match-id", "1141"],
    )

    assert result.exit_code == 0
    assert "match-report:1141" in result.stdout


def test_oddspapi_batch_backfill_accepts_controller_options(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.run_oddspapi_batch_backfill",
        lambda season,
        mode,
        chunk_size,
        request_budget_per_league,
        timeout_seconds,
        max_snapshots_per_match,
        max_rounds_per_league,
        stop_after_empty_matches,
        stop_after_failed_rounds,
        round_timeout_seconds,
        league_ids=None,
        from_date=None,
        skip_match_ids=None: (
            f"batch:{season}:{mode}:{chunk_size}:{request_budget_per_league}:"
            f"{timeout_seconds}:{max_snapshots_per_match}:{max_rounds_per_league}:"
            f"{stop_after_empty_matches}:{stop_after_failed_rounds}:"
            f"{round_timeout_seconds}:{league_ids}:{from_date}:{skip_match_ids}"
        ),
    )

    result = runner.invoke(
        app,
        [
            "odds-source",
            "oddspapi-batch-backfill",
            "--season",
            "2025",
            "--mode",
            "balanced",
            "--chunk-size",
            "20",
            "--request-budget-per-league",
            "800",
            "--timeout-seconds",
            "20",
            "--max-snapshots-per-match",
            "120",
            "--max-rounds-per-league",
            "12",
            "--stop-after-empty-matches",
            "8",
            "--stop-after-failed-rounds",
            "2",
            "--round-timeout-seconds",
            "60",
            "--league-ids",
            "62,89",
            "--from-date",
            "2026-01-15",
            "--skip-match-ids",
            "8328,8600",
        ],
    )

    assert result.exit_code == 0
    assert "batch:2025:balanced:20:800:20:120:12:8:2:60.0:" in result.stdout
    assert "'62'" in result.stdout
    assert "'89'" in result.stdout
    assert "'8328'" in result.stdout or "8328" in result.stdout
    assert "'8600'" in result.stdout or "8600" in result.stdout
    assert ":2026-01-15" in result.stdout


def test_oddspapi_batch_worker_accepts_log_options(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.run_oddspapi_batch_worker",
        lambda season,
        mode,
        chunk_size,
        request_budget_per_league,
        timeout_seconds,
        max_snapshots_per_match,
        max_rounds_per_league,
        stop_after_empty_matches,
        stop_after_failed_rounds,
        round_timeout_seconds,
        hard_timeout_seconds,
        log_dir,
        league_ids=None,
        from_date=None,
        skip_match_ids=None,
        notify_on_complete=False,
        output_callback=None: (
            f"worker:{season}:{mode}:{chunk_size}:{request_budget_per_league}:"
            f"{timeout_seconds}:{max_snapshots_per_match}:{max_rounds_per_league}:"
            f"{stop_after_empty_matches}:{stop_after_failed_rounds}:{round_timeout_seconds}:"
            f"{hard_timeout_seconds}:"
            f"{log_dir}:{league_ids}:{from_date}:"
            f"{skip_match_ids}:{notify_on_complete}:{output_callback is not None}"
        ),
    )

    result = runner.invoke(
        app,
        [
            "odds-source",
            "oddspapi-batch-worker",
            "--season",
            "2025",
            "--mode",
            "balanced",
            "--chunk-size",
            "10",
            "--request-budget-per-league",
            "500",
            "--timeout-seconds",
            "20",
            "--max-snapshots-per-match",
            "120",
            "--max-rounds-per-league",
            "2",
            "--stop-after-empty-matches",
            "8",
            "--stop-after-failed-rounds",
            "2",
            "--round-timeout-seconds",
            "60",
            "--hard-timeout-seconds",
            "3600",
            "--log-dir",
            "logs/odds",
            "--league-ids",
            "41,89",
            "--from-date",
            "2026-01-15",
            "--skip-match-ids",
            "8328,8600",
            "--notify-on-complete",
        ],
    )

    assert result.exit_code == 0
    assert "worker:2025:balanced:10:500:20:120:2:8:2:60.0:3600.0:logs/odds:" in result.stdout
    assert "'41'" in result.stdout
    assert "'89'" in result.stdout
    assert "'8328'" in result.stdout or "8328" in result.stdout
    assert "'8600'" in result.stdout or "8600" in result.stdout
    assert ":2026-01-15:" in result.stdout
    assert ":True:True" in result.stdout


def test_oddspapi_worker_start_accepts_background_options(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.start_oddspapi_batch_worker_process",
        lambda season,
        mode,
        chunk_size,
        request_budget_per_league,
        timeout_seconds,
        max_snapshots_per_match,
        max_rounds_per_league,
        stop_after_empty_matches,
        stop_after_failed_rounds,
        round_timeout_seconds,
        hard_timeout_seconds,
        log_dir,
        league_ids=None,
        from_date=None,
        skip_match_ids=None,
        notify_on_complete=False: type(
            "FakeResult",
            (),
            {
                "to_text": lambda self: (
                    f"start:{season}:{mode}:{chunk_size}:{request_budget_per_league}:"
                    f"{timeout_seconds}:{max_snapshots_per_match}:{max_rounds_per_league}:"
                    f"{stop_after_empty_matches}:{stop_after_failed_rounds}:"
                    f"{round_timeout_seconds}:{hard_timeout_seconds}:{log_dir}:{league_ids}:{from_date}:"
                    f"{skip_match_ids}:{notify_on_complete}"
                )
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "odds-source",
            "oddspapi-worker-start",
            "--season",
            "2025",
            "--mode",
            "fast",
            "--chunk-size",
            "12",
            "--request-budget-per-league",
            "900",
            "--timeout-seconds",
            "18",
            "--max-snapshots-per-match",
            "100",
            "--max-rounds-per-league",
            "30",
            "--stop-after-empty-matches",
            "10",
            "--stop-after-failed-rounds",
            "3",
            "--round-timeout-seconds",
            "45",
            "--hard-timeout-seconds",
            "3600",
            "--log-dir",
            "logs/odds",
            "--league-ids",
            "62,89",
            "--from-date",
            "2026-01-15",
            "--skip-match-ids",
            "8328,8600",
            "--notify-on-complete",
        ],
    )

    assert result.exit_code == 0
    assert "start:2025:fast:12:900:18:100:30:10:3:45.0:3600.0:logs/odds:" in result.stdout
    assert "'62'" in result.stdout
    assert "'89'" in result.stdout
    assert "'8328'" in result.stdout or "8328" in result.stdout
    assert "'8600'" in result.stdout or "8600" in result.stdout
    assert ":2026-01-15:" in result.stdout
    assert ":True" in result.stdout


def test_oddspapi_worker_status_accepts_log_dir_and_tail(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.build_oddspapi_batch_worker_status",
        lambda log_dir, tail_lines: f"status:{log_dir}:{tail_lines}",
    )

    result = runner.invoke(
        app,
        [
            "odds-source",
            "oddspapi-worker-status",
            "--log-dir",
            "logs/odds",
            "--tail-lines",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert "status:logs/odds:5" in result.stdout

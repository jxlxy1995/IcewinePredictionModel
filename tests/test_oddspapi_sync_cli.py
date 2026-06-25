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
    assert "oddspapi-clear-league-snapshots" in result.stdout
    assert "oddspapi-match-report" in result.stdout
    assert "oddspapi-batch-backfill" in result.stdout
    assert "oddspapi-batch-worker" in result.stdout
    assert "oddspapi-worker-start" in result.stdout
    assert "oddspapi-worker-status" in result.stdout
    assert "oddspapi-diagnose-fixtures" in result.stdout
    assert "oddspapi-audit-backfill" in result.stdout
    assert "oddspapi-suggest-aliases" in result.stdout
    assert "oddspapi-sample-candidates" in result.stdout
    assert "oddspapi-supplement-snapshots-from-raw" in result.stdout


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
        match_ids=None,
        league_ids=None,
        from_date=None,
        historical_odds_cooldown_seconds=5,
        refresh_pre_kickoff_existing=False,
        bookmaker="pinnacle",
        progress_callback=None: (
            f"fetch:{season}:{max_matches}:{request_budget}:"
            f"{timeout_seconds}:{max_snapshots_per_match}:{skip_match_ids}:"
            f"{match_ids}:{league_ids}:{from_date}:{historical_odds_cooldown_seconds}:"
            f"{refresh_pre_kickoff_existing}:{bookmaker}"
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
            "--refresh-pre-kickoff-existing",
            "--bookmaker",
            "sbobet",
        ],
    )

    assert result.exit_code == 0
    assert "fetch:2025:20:50:12:150:{1149, 1150}:" in result.stdout
    assert "'135'" in result.stdout
    assert "'140'" in result.stdout
    assert ":2026-01-15:3.0:True:sbobet" in result.stdout


def test_oddspapi_supplement_snapshots_from_raw_accepts_match_ids(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.supplement_historical_odds_snapshots_from_raw",
        lambda session,
        match_ids=None,
        source_name="oddspapi",
        bookmaker="pinnacle": type(
            "Report",
            (),
            {
                "scanned_match_count": 2,
                "skipped_no_raw_count": 0,
                "supplemented_match_count": 1,
                "added_group_count": 3,
                "added_snapshot_count": 6,
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "odds-source",
            "oddspapi-supplement-snapshots-from-raw",
            "--match-ids",
            "18410,18411",
        ],
    )

    assert result.exit_code == 0
    assert "scanned=2" in result.stdout
    assert "supplemented_matches=1" in result.stdout
    assert "added_groups=3" in result.stdout
    assert "added_snapshots=6" in result.stdout


def test_oddspapi_probe_accepts_season_match_limit_and_request_budget(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.build_oddspapi_probe_report",
        lambda season,
        max_matches,
        request_budget,
        timeout_seconds,
        skip_match_ids=None,
        bookmaker="pinnacle": (
            f"probe:{season}:{max_matches}:{request_budget}:"
            f"{timeout_seconds}:{skip_match_ids}:{bookmaker}"
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
            "--bookmaker",
            "sbobet",
        ],
    )

    assert result.exit_code == 0
    assert "probe:2025:20:50:8:{1149, 1150}:sbobet" in result.stdout


def test_oddspapi_diagnose_fixtures_accepts_background_report_options(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.run_oddspapi_fixture_diagnostics",
        lambda season,
        max_matches,
        request_budget,
        timeout_seconds,
        log_dir,
        league_ids=None,
        from_date=None,
        confidence_threshold="0.75": (
            f"diagnose:{season}:{max_matches}:{request_budget}:{timeout_seconds}:"
            f"{log_dir}:{league_ids}:{from_date}:{confidence_threshold}"
        ),
    )

    result = runner.invoke(
        app,
        [
            "odds-source",
            "oddspapi-diagnose-fixtures",
            "--season",
            "2025",
            "--max-matches",
            "30",
            "--request-budget",
            "60",
            "--timeout-seconds",
            "12",
            "--log-dir",
            "logs/diagnostics",
            "--league-ids",
            "135,140",
            "--from-date",
            "2026-01-15",
            "--confidence-threshold",
            "0.8",
        ],
    )

    assert result.exit_code == 0
    assert "diagnose:2025:30:60:12:logs/diagnostics:" in result.stdout
    assert "'135'" in result.stdout
    assert "'140'" in result.stdout
    assert ":2026-01-15:0.8" in result.stdout


def test_oddspapi_audit_backfill_accepts_season_log_dir_and_top_errors(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.build_oddspapi_backfill_audit",
        lambda season, log_dir, top_errors: f"audit-backfill:{season}:{log_dir}:{top_errors}",
    )

    result = runner.invoke(
        app,
        [
            "odds-source",
            "oddspapi-audit-backfill",
            "--season",
            "2025",
            "--log-dir",
            "logs/odds",
            "--top-errors",
            "7",
        ],
    )

    assert result.exit_code == 0
    assert "audit-backfill:2025:logs/odds:7" in result.stdout


def test_oddspapi_suggest_aliases_accepts_report_and_config_options(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.build_oddspapi_alias_suggestions_text",
        lambda report_dir,
        alias_config_path,
        alias_threshold,
        anchor_threshold: (
            f"suggest-aliases:{report_dir}:{alias_config_path}:"
            f"{alias_threshold}:{anchor_threshold}"
        ),
    )

    result = runner.invoke(
        app,
        [
            "odds-source",
            "oddspapi-suggest-aliases",
            "--report-dir",
            "logs/odds-diagnostics/run-1",
            "--alias-config-path",
            "config/external_aliases.yaml",
            "--alias-threshold",
            "0.75",
            "--anchor-threshold",
            "0.85",
        ],
    )

    assert result.exit_code == 0
    assert (
        "suggest-aliases:logs/odds-diagnostics/run-1:"
        "config/external_aliases.yaml:0.75:0.85"
    ) in result.stdout


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


def test_oddspapi_clear_league_snapshots_accepts_league_ids(monkeypatch):
    runner = CliRunner()
    calls = {}

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeSessionFactory:
        def __call__(self):
            return FakeSession()

    monkeypatch.setattr("icewine_prediction.cli.create_database_engine", lambda: "engine")
    monkeypatch.setattr("icewine_prediction.cli.initialize_database", lambda engine: None)
    monkeypatch.setattr("icewine_prediction.cli.create_session_factory", lambda engine: FakeSessionFactory())

    def fake_clear(session, source_name, league_ids):
        calls["source_name"] = source_name
        calls["league_ids"] = league_ids
        return type(
            "Report",
            (),
            {
                "main_snapshot_count": 12,
                "raw_snapshot_count": 34,
                "reset_source_match_count": 5,
            },
        )()

    monkeypatch.setattr("icewine_prediction.cli.clear_historical_odds_for_leagues", fake_clear)

    result = runner.invoke(
        app,
        [
            "odds-source",
            "oddspapi-clear-league-snapshots",
            "--league-ids",
            "103,113",
        ],
    )

    assert result.exit_code == 0
    assert calls == {"source_name": "oddspapi", "league_ids": {"103", "113"}}
    assert "12" in result.stdout
    assert "34" in result.stdout
    assert "5" in result.stdout


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
        bookmaker="pinnacle",
        league_ids=None,
        from_date=None,
        skip_match_ids=None,
        match_ids=None: (
            f"batch:{season}:{mode}:{chunk_size}:{request_budget_per_league}:"
            f"{timeout_seconds}:{max_snapshots_per_match}:{max_rounds_per_league}:"
            f"{stop_after_empty_matches}:{stop_after_failed_rounds}:"
            f"{round_timeout_seconds}:{bookmaker}:{league_ids}:{from_date}:{skip_match_ids}:{match_ids}"
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
            "--bookmaker",
            "sbobet",
            "--league-ids",
            "62,89",
            "--from-date",
            "2026-01-15",
            "--skip-match-ids",
            "8328,8600",
        ],
    )

    assert result.exit_code == 0
    assert "batch:2025:balanced:20:800:20:120:12:8:2:60.0:sbobet:" in result.stdout
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
        historical_odds_cooldown_seconds,
        hard_timeout_seconds,
        log_dir,
        bookmaker="pinnacle",
        league_ids=None,
        from_date=None,
        skip_match_ids=None,
        match_ids=None,
        notify_on_complete=False,
        output_callback=None: (
            f"worker:{season}:{mode}:{chunk_size}:{request_budget_per_league}:"
            f"{timeout_seconds}:{max_snapshots_per_match}:{max_rounds_per_league}:"
            f"{stop_after_empty_matches}:{stop_after_failed_rounds}:{round_timeout_seconds}:"
            f"{historical_odds_cooldown_seconds}:{hard_timeout_seconds}:"
            f"{log_dir}:{bookmaker}:{league_ids}:{from_date}:"
            f"{skip_match_ids}:{match_ids}:{notify_on_complete}:{output_callback is not None}"
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
            "--historical-odds-cooldown-seconds",
            "7.5",
            "--hard-timeout-seconds",
            "3600",
            "--bookmaker",
            "sbobet",
            "--log-dir",
            "logs/odds",
            "--league-ids",
            "41,89",
            "--from-date",
            "2026-01-15",
            "--skip-match-ids",
            "8328,8600",
            "--match-ids",
            "9001,9002",
            "--notify-on-complete",
        ],
    )

    assert result.exit_code == 0
    assert "worker:2025:balanced:10:500:20:120:2:8:2:60.0:7.5:3600.0:logs/odds:sbobet:" in result.stdout
    assert "'41'" in result.stdout
    assert "'89'" in result.stdout
    assert "'8328'" in result.stdout or "8328" in result.stdout
    assert "'8600'" in result.stdout or "8600" in result.stdout
    assert "'9001'" in result.stdout or "9001" in result.stdout
    assert "'9002'" in result.stdout or "9002" in result.stdout
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
        historical_odds_cooldown_seconds,
        hard_timeout_seconds,
        log_dir,
        bookmaker="pinnacle",
        league_ids=None,
        from_date=None,
        skip_match_ids=None,
        match_ids=None,
        notify_on_complete=False: type(
            "FakeResult",
            (),
            {
                "to_text": lambda self: (
                    f"start:{season}:{mode}:{chunk_size}:{request_budget_per_league}:"
                    f"{timeout_seconds}:{max_snapshots_per_match}:{max_rounds_per_league}:"
                    f"{stop_after_empty_matches}:{stop_after_failed_rounds}:"
                    f"{round_timeout_seconds}:{historical_odds_cooldown_seconds}:"
                    f"{hard_timeout_seconds}:{log_dir}:{bookmaker}:{league_ids}:{from_date}:"
                    f"{skip_match_ids}:{match_ids}:{notify_on_complete}"
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
            "--historical-odds-cooldown-seconds",
            "7.5",
            "--hard-timeout-seconds",
            "3600",
            "--bookmaker",
            "sbobet",
            "--log-dir",
            "logs/odds",
            "--league-ids",
            "62,89",
            "--from-date",
            "2026-01-15",
            "--skip-match-ids",
            "8328,8600",
            "--match-ids",
            "9001,9002",
            "--notify-on-complete",
        ],
    )

    assert result.exit_code == 0
    assert "start:2025:fast:12:900:18:100:30:10:3:45.0:7.5:3600.0:logs/odds:sbobet:" in result.stdout
    assert "'62'" in result.stdout
    assert "'89'" in result.stdout
    assert "'8328'" in result.stdout or "8328" in result.stdout
    assert "'8600'" in result.stdout or "8600" in result.stdout
    assert "'9001'" in result.stdout or "9001" in result.stdout
    assert "'9002'" in result.stdout or "9002" in result.stdout
    assert ":2026-01-15:" in result.stdout
    assert ":True" in result.stdout


def test_oddspapi_sample_candidates_accepts_leagues_and_limits(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.build_oddspapi_sample_candidate_report",
        lambda season, league_ids, from_date, per_league: (
            f"samples:{season}:{league_ids}:{from_date}:{per_league}"
        ),
    )

    result = runner.invoke(
        app,
        [
            "odds-source",
            "oddspapi-sample-candidates",
            "--season",
            "2025",
            "--league-ids",
            "98,292",
            "--from-date",
            "2026-01-15",
            "--per-league",
            "8",
        ],
    )

    assert result.exit_code == 0
    assert "samples:2025:" in result.stdout
    assert "'98'" in result.stdout
    assert "'292'" in result.stdout
    assert ":2026-01-15:8" in result.stdout


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

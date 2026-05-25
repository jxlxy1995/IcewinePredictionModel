from dataclasses import dataclass
from datetime import date
import os
import time

from icewine_prediction.oddspapi_batch_backfill_service import (
    BatchBackfillMode,
    LeagueBackfillJob,
    build_league_backfill_jobs,
    format_batch_backfill_report,
    run_oddspapi_batch_backfill_with_runner,
    run_oddspapi_batch_worker_with_runner,
)
from icewine_prediction.oddspapi_sync_runner import OddsPapiSyncResult
from icewine_prediction.settings import LeagueSettings


def test_build_league_backfill_jobs_orders_enabled_supported_leagues_by_priority():
    leagues = [
        LeagueSettings("Ligue 2", "France", 62, True, 84),
        LeagueSettings("J2 League", "Japan", 99, False, 61),
        LeagueSettings("Premier League", "England", 39, True, 100),
        LeagueSettings("Unsupported", "Nowhere", 9999, True, 101),
    ]

    jobs = build_league_backfill_jobs(leagues, requested_league_ids=None)

    assert jobs == (
        LeagueBackfillJob(league_id="39", league_name="Premier League", priority=100),
        LeagueBackfillJob(league_id="62", league_name="Ligue 2", priority=84),
    )


def test_build_league_backfill_jobs_honors_requested_league_ids():
    leagues = [
        LeagueSettings("Premier League", "England", 39, True, 100),
        LeagueSettings("La Liga", "Spain", 140, True, 98),
        LeagueSettings("Segunda División", "Spain", 141, True, 86),
        LeagueSettings("Ligue 2", "France", 62, True, 84),
        LeagueSettings("Eerste Divisie", "Netherlands", 89, True, 81),
        LeagueSettings("League One", "England", 41, True, 64),
    ]

    jobs = build_league_backfill_jobs(leagues, requested_league_ids={"141", "62", "89", "41"})

    assert [job.league_id for job in jobs] == ["141", "62", "89", "41"]


def test_batch_backfill_stops_league_after_consecutive_empty_rounds():
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return OddsPapiSyncResult(
            processed_match_count=2,
            matched_count=2,
            failed_match_count=0,
            inserted_snapshot_count=0,
            skipped_duplicate_snapshot_count=0,
            skipped_existing_odds_count=0,
            asian_handicap_count=0,
            total_goals_count=0,
            requests_used=6,
        )

    report = run_oddspapi_batch_backfill_with_runner(
        jobs=(LeagueBackfillJob("62", "Ligue 2", 84),),
        runner=fake_runner,
        season=2025,
        from_date=date(2026, 1, 15),
        mode=BatchBackfillMode.SAFE,
        chunk_size=2,
        request_budget_per_league=100,
        timeout_seconds=20,
        max_snapshots_per_match=120,
        max_rounds_per_league=10,
        stop_after_empty_matches=4,
    )

    assert len(calls) == 2
    assert report.league_reports[0].status == "stopped"
    assert report.league_reports[0].stop_reason == "连续空数据达到阈值"
    assert report.league_reports[0].processed_match_count == 4
    assert report.league_reports[0].requests_used == 12


def test_batch_backfill_stops_league_when_round_makes_no_progress():
    def fake_runner(**kwargs):
        return OddsPapiSyncResult(
            processed_match_count=0,
            matched_count=0,
            failed_match_count=0,
            inserted_snapshot_count=0,
            skipped_duplicate_snapshot_count=0,
            skipped_existing_odds_count=5,
            asian_handicap_count=0,
            total_goals_count=0,
            requests_used=0,
        )

    report = run_oddspapi_batch_backfill_with_runner(
        jobs=(LeagueBackfillJob("62", "Ligue 2", 84),),
        runner=fake_runner,
        season=2025,
        from_date=date(2026, 1, 15),
        mode=BatchBackfillMode.SAFE,
        chunk_size=20,
        request_budget_per_league=100,
        timeout_seconds=20,
        max_snapshots_per_match=120,
        max_rounds_per_league=10,
        stop_after_empty_matches=8,
    )

    assert report.league_reports[0].round_count == 1
    assert report.league_reports[0].status == "done"
    assert report.league_reports[0].stop_reason == "无候选或无进展"


def test_batch_backfill_stops_league_when_round_times_out():
    def slow_runner(**kwargs):
        time.sleep(0.2)
        return OddsPapiSyncResult(
            processed_match_count=1,
            matched_count=1,
            failed_match_count=0,
            inserted_snapshot_count=100,
            skipped_duplicate_snapshot_count=0,
            skipped_existing_odds_count=0,
            asian_handicap_count=50,
            total_goals_count=50,
            requests_used=3,
        )

    started_at = time.monotonic()
    report = run_oddspapi_batch_backfill_with_runner(
        jobs=(LeagueBackfillJob("62", "Ligue 2", 84),),
        runner=slow_runner,
        season=2025,
        from_date=date(2026, 1, 15),
        mode=BatchBackfillMode.SAFE,
        chunk_size=1,
        request_budget_per_league=100,
        timeout_seconds=20,
        max_snapshots_per_match=120,
        max_rounds_per_league=3,
        stop_after_empty_matches=8,
        round_timeout_seconds=0.05,
    )

    assert time.monotonic() - started_at < 0.15
    assert report.league_reports[0].round_count == 0
    assert report.league_reports[0].status == "stopped"
    assert "超时" in report.league_reports[0].stop_reason


def test_batch_backfill_stops_league_after_consecutive_failed_rounds():
    calls = []

    def failing_runner(**kwargs):
        calls.append(kwargs)
        return OddsPapiSyncResult(
            processed_match_count=0,
            matched_count=0,
            failed_match_count=3,
            inserted_snapshot_count=0,
            skipped_duplicate_snapshot_count=0,
            skipped_existing_odds_count=0,
            asian_handicap_count=0,
            total_goals_count=0,
            requests_used=3,
            error_message="3 场比赛失败，已跳过继续",
        )

    report = run_oddspapi_batch_backfill_with_runner(
        jobs=(LeagueBackfillJob("62", "Ligue 2", 84),),
        runner=failing_runner,
        season=2025,
        from_date=date(2026, 1, 15),
        mode=BatchBackfillMode.SAFE,
        chunk_size=3,
        request_budget_per_league=100,
        timeout_seconds=20,
        max_snapshots_per_match=120,
        max_rounds_per_league=10,
        stop_after_empty_matches=8,
        stop_after_failed_rounds=2,
    )

    assert len(calls) == 2
    assert report.league_reports[0].round_count == 2
    assert report.league_reports[0].status == "stopped"
    assert "连续失败" in report.league_reports[0].stop_reason


def test_batch_backfill_balanced_mode_reports_two_workers_and_multiple_leagues():
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return OddsPapiSyncResult(
            processed_match_count=1,
            matched_count=1,
            failed_match_count=0,
            inserted_snapshot_count=100,
            skipped_duplicate_snapshot_count=0,
            skipped_existing_odds_count=0,
            asian_handicap_count=50,
            total_goals_count=50,
            requests_used=3,
        )

    report = run_oddspapi_batch_backfill_with_runner(
        jobs=(
            LeagueBackfillJob("39", "Premier League", 100),
            LeagueBackfillJob("62", "Ligue 2", 84),
        ),
        runner=fake_runner,
        season=2025,
        from_date=date(2026, 1, 15),
        mode=BatchBackfillMode.BALANCED,
        chunk_size=1,
        request_budget_per_league=100,
        timeout_seconds=20,
        max_snapshots_per_match=120,
        max_rounds_per_league=1,
        stop_after_empty_matches=8,
    )

    assert report.worker_count == 2
    assert sorted(call["league_ids"] for call in calls) == [{"39"}, {"62"}]
    assert all(call["historical_odds_cooldown_seconds"] == 5 for call in calls)


def test_batch_backfill_passes_skip_match_ids_to_runner():
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return OddsPapiSyncResult(
            processed_match_count=0,
            matched_count=0,
            failed_match_count=0,
            inserted_snapshot_count=0,
            skipped_duplicate_snapshot_count=0,
            skipped_existing_odds_count=0,
            asian_handicap_count=0,
            total_goals_count=0,
            requests_used=0,
        )

    run_oddspapi_batch_backfill_with_runner(
        jobs=(LeagueBackfillJob("283", "Liga I", 71),),
        runner=fake_runner,
        season=2025,
        from_date=date(2026, 1, 15),
        mode=BatchBackfillMode.SAFE,
        chunk_size=1,
        request_budget_per_league=100,
        timeout_seconds=20,
        max_snapshots_per_match=30,
        max_rounds_per_league=1,
        stop_after_empty_matches=8,
        skip_match_ids={8328, 8600},
    )

    assert calls[0]["skip_match_ids"] == {8328, 8600}


def test_format_batch_backfill_report_summarizes_leagues():
    @dataclass(frozen=True)
    class FakeReport:
        mode: str
        worker_count: int
        league_reports: tuple

    @dataclass(frozen=True)
    class FakeLeagueReport:
        league_id: str
        league_name: str
        status: str
        round_count: int
        processed_match_count: int
        inserted_snapshot_count: int
        failed_match_count: int
        requests_used: int
        stop_reason: str

    output = format_batch_backfill_report(
        FakeReport(
            mode="balanced",
            worker_count=2,
            league_reports=(
                FakeLeagueReport("62", "Ligue 2", "done", 3, 20, 1800, 1, 60, "无候选或无进展"),
            ),
        )
    )

    assert "批量回填模式 balanced workers=2" in output
    assert "Ligue 2 id=62 status=done rounds=3 processed=20 snapshots=1800 failed=1 requests=60 reason=无候选或无进展" in output


def test_batch_worker_writes_progress_to_output_and_log_file(tmp_path):
    calls = []
    messages = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return OddsPapiSyncResult(
            processed_match_count=1 if len(calls) == 1 else 0,
            matched_count=1 if len(calls) == 1 else 0,
            failed_match_count=0,
            inserted_snapshot_count=100 if len(calls) == 1 else 0,
            skipped_duplicate_snapshot_count=0,
            skipped_existing_odds_count=0,
            asian_handicap_count=50 if len(calls) == 1 else 0,
            total_goals_count=50 if len(calls) == 1 else 0,
            requests_used=3 if len(calls) == 1 else 0,
        )

    report = run_oddspapi_batch_worker_with_runner(
        jobs=(LeagueBackfillJob("62", "Ligue 2", 84),),
        runner=fake_runner,
        season=2025,
        from_date=date(2026, 1, 15),
        mode=BatchBackfillMode.SAFE,
        chunk_size=1,
        request_budget_per_league=100,
        timeout_seconds=20,
        max_snapshots_per_match=120,
        max_rounds_per_league=3,
        stop_after_empty_matches=8,
        log_dir=tmp_path,
        output_callback=messages.append,
    )

    assert report.league_reports[0].inserted_snapshot_count == 100
    assert any("开始 OddsPapi 后台回填" in message for message in messages)
    assert any("Ligue 2 第1轮 processed=1 snapshots=100 failed=0 requests=3" in message for message in messages)
    assert any("完成 OddsPapi 后台回填" in message for message in messages)
    log_files = list(tmp_path.glob("*.log"))
    assert len(log_files) == 1
    log_text = log_files[0].read_text(encoding="utf-8")
    assert "Ligue 2 第1轮 processed=1 snapshots=100 failed=0 requests=3" in log_text


def test_batch_worker_log_filename_includes_process_id(tmp_path):
    def fake_runner(**kwargs):
        return OddsPapiSyncResult(
            processed_match_count=0,
            matched_count=0,
            failed_match_count=0,
            inserted_snapshot_count=0,
            skipped_duplicate_snapshot_count=0,
            skipped_existing_odds_count=0,
            asian_handicap_count=0,
            total_goals_count=0,
            requests_used=0,
        )

    run_oddspapi_batch_worker_with_runner(
        jobs=(LeagueBackfillJob("62", "Ligue 2", 84),),
        runner=fake_runner,
        season=2025,
        from_date=date(2026, 1, 15),
        mode=BatchBackfillMode.SAFE,
        chunk_size=1,
        request_budget_per_league=100,
        timeout_seconds=20,
        max_snapshots_per_match=120,
        max_rounds_per_league=1,
        stop_after_empty_matches=8,
        log_dir=tmp_path,
        output_callback=None,
    )

    log_files = list(tmp_path.glob("*.log"))
    assert len(log_files) == 1
    assert f"-pid{os.getpid()}-" in log_files[0].name


def test_batch_worker_sends_completion_notification_when_enabled(tmp_path):
    notifications = []

    def fake_runner(**kwargs):
        return OddsPapiSyncResult(
            processed_match_count=0,
            matched_count=0,
            failed_match_count=0,
            inserted_snapshot_count=0,
            skipped_duplicate_snapshot_count=0,
            skipped_existing_odds_count=0,
            asian_handicap_count=0,
            total_goals_count=0,
            requests_used=0,
        )

    run_oddspapi_batch_worker_with_runner(
        jobs=(LeagueBackfillJob("62", "Ligue 2", 84),),
        runner=fake_runner,
        season=2025,
        from_date=date(2026, 1, 15),
        mode=BatchBackfillMode.SAFE,
        chunk_size=1,
        request_budget_per_league=100,
        timeout_seconds=20,
        max_snapshots_per_match=120,
        max_rounds_per_league=1,
        stop_after_empty_matches=8,
        log_dir=tmp_path,
        output_callback=None,
        notify_on_complete=True,
        notification_callback=lambda title, message: notifications.append((title, message)) or True,
    )

    assert len(notifications) == 1
    title, message = notifications[0]
    assert "OddsPapi" in title
    assert "Ligue 2" in message
    assert "requests=0" in message


def test_batch_worker_forces_process_exit_after_completion_when_hard_timeout_is_enabled(
    monkeypatch,
    tmp_path,
):
    exit_codes = []

    def fake_runner(**kwargs):
        return OddsPapiSyncResult(
            processed_match_count=0,
            matched_count=0,
            failed_match_count=0,
            inserted_snapshot_count=0,
            skipped_duplicate_snapshot_count=0,
            skipped_existing_odds_count=0,
            asian_handicap_count=0,
            total_goals_count=0,
            requests_used=0,
        )

    monkeypatch.setattr(
        "icewine_prediction.oddspapi_batch_backfill_service.os._exit",
        exit_codes.append,
    )

    run_oddspapi_batch_worker_with_runner(
        jobs=(LeagueBackfillJob("62", "Ligue 2", 84),),
        runner=fake_runner,
        season=2025,
        from_date=date(2026, 1, 15),
        mode=BatchBackfillMode.SAFE,
        chunk_size=1,
        request_budget_per_league=100,
        timeout_seconds=20,
        max_snapshots_per_match=120,
        max_rounds_per_league=1,
        stop_after_empty_matches=8,
        hard_timeout_seconds=60,
        log_dir=tmp_path,
        output_callback=None,
    )

    assert exit_codes == [0]

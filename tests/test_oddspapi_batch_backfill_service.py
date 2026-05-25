from dataclasses import dataclass
from datetime import date

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
        LeagueSettings("Ligue 2", "France", 62, True, 84),
        LeagueSettings("Eerste Divisie", "Netherlands", 89, True, 81),
        LeagueSettings("League One", "England", 41, True, 64),
    ]

    jobs = build_league_backfill_jobs(leagues, requested_league_ids={"62", "89", "41"})

    assert [job.league_id for job in jobs] == ["62", "89", "41"]


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

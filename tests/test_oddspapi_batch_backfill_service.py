from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import json
import os
import time
from zoneinfo import ZoneInfo

from icewine_prediction.models import (
    HistoricalOddsRawSnapshot,
    HistoricalOddsSnapshot,
    League,
    Match,
    OddsSourceMatch,
    Team,
)
from icewine_prediction.oddspapi_batch_backfill_service import (
    BatchBackfillMode,
    LeagueBackfillJob,
    build_league_backfill_jobs,
    format_batch_backfill_report,
    run_oddspapi_batch_backfill_with_runner,
    run_oddspapi_batch_worker_with_runner,
)
import icewine_prediction.oddspapi_batch_backfill_service as batch_service
from icewine_prediction.oddspapi_sync_runner import OddsPapiSyncResult
from icewine_prediction.settings import LeagueSettings


def _batch_match(
    session,
    *,
    source_match_id: str,
    source_league_id: str = "169",
    season: int = 2026,
) -> Match:
    league = (
        session.query(League)
        .filter_by(source_name="api_football", source_league_id=source_league_id)
        .one_or_none()
    )
    if league is None:
        league = League(
            name=f"Super League {source_league_id}",
            country_or_region="China",
            level=1,
            source_name="api_football",
            source_league_id=source_league_id,
        )
    home_team = Team(canonical_name=f"Home {source_match_id}")
    away_team = Team(canonical_name=f"Away {source_match_id}")
    session.add_all([league, home_team, away_team])
    session.flush()
    match = Match(
        league=league,
        home_team=home_team,
        away_team=away_team,
        kickoff_time=datetime(2026, 5, 20, 19, 35, tzinfo=ZoneInfo("Asia/Shanghai")),
        season=season,
        status="finished",
        home_score=1,
        away_score=0,
        source_name="api_football",
        source_match_id=source_match_id,
    )
    session.add(match)
    session.commit()
    return match


def test_build_league_backfill_jobs_orders_enabled_supported_leagues_by_priority():
    leagues = [
        LeagueSettings("Ligue 2", "France", 62, True, 84),
        LeagueSettings("J2 League", "Japan", 99, False, 61),
        LeagueSettings("Premier League", "England", 39, True, 100),
        LeagueSettings("Unsupported", "Nowhere", 9999, True, 101),
    ]

    jobs = build_league_backfill_jobs(leagues, requested_league_ids=None)

    assert jobs == (
        LeagueBackfillJob(league_id="39", league_name="英超", priority=100),
        LeagueBackfillJob(league_id="62", league_name="法乙", priority=84),
    )


def test_build_league_backfill_jobs_honors_requested_league_ids():
    leagues = [
        LeagueSettings("Premier League", "England", 39, True, 100),
        LeagueSettings("La Liga", "Spain", 140, True, 98),
        LeagueSettings("Segunda Divisi贸n", "Spain", 141, True, 86),
        LeagueSettings("Ligue 2", "France", 62, True, 84),
        LeagueSettings("Eerste Divisie", "Netherlands", 89, True, 81),
        LeagueSettings("League One", "England", 41, True, 64),
    ]

    jobs = build_league_backfill_jobs(leagues, requested_league_ids={"141", "62", "89", "41"})

    assert [job.league_id for job in jobs] == ["141", "62", "89", "41"]


def test_count_candidate_matches_uses_same_filters_as_sync_selector(session):
    empty_match = _batch_match(session, source_match_id="empty")
    raw_only_match = _batch_match(session, source_match_id="raw-only")
    cached_unfilled_match = _batch_match(session, source_match_id="cached-unfilled")
    completed_match = _batch_match(session, source_match_id="completed")
    session.add(
        HistoricalOddsRawSnapshot(
            match_id=raw_only_match.id,
            source_name="oddspapi",
            source_fixture_id="raw-only-fixture",
            bookmaker="pinnacle",
            market_type="asian_handicap",
            market_id="ah-0",
            market_name="Asian Handicap 0",
            market_line=Decimal("0.00"),
            outcome_side="home",
            odds=Decimal("1.90"),
            snapshot_time=datetime(2026, 5, 20, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            period="fulltime",
        )
    )
    session.add(
        OddsSourceMatch(
            match_id=cached_unfilled_match.id,
            source_name="oddspapi",
            source_fixture_id="cached-unfilled-fixture",
            matched_at=datetime(2026, 5, 20, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            match_confidence=Decimal("1.0000"),
            match_reason="cached",
            historical_odds_status=None,
        )
    )
    session.add(
        HistoricalOddsSnapshot(
            match_id=completed_match.id,
            source_name="oddspapi",
            source_fixture_id="completed-fixture",
            bookmaker="pinnacle",
            market_type="asian_handicap",
            market_id="ah-0",
            market_name="Asian Handicap 0",
            market_line=Decimal("0.00"),
            outcome_side="home",
            odds=Decimal("1.90"),
            snapshot_time=datetime(2026, 5, 20, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            period="fulltime",
        )
    )
    session.commit()

    count = batch_service._count_candidate_matches_for_league(
        session=session,
        league_id="169",
        season=2026,
        from_date=datetime(2026, 1, 15, tzinfo=ZoneInfo("Asia/Shanghai")),
        skip_match_ids=None,
    )

    assert count == 3
    assert empty_match.id
    assert raw_only_match.id
    assert cached_unfilled_match.id


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


def test_batch_backfill_ignores_round_timeout_to_avoid_orphan_writer_thread():
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

    assert report.league_reports[0].round_count == 3
    assert report.league_reports[0].processed_match_count == 3
    assert report.league_reports[0].status == "stopped"
    assert "联赛轮次上限" in report.league_reports[0].stop_reason


def test_batch_worker_arms_round_watchdog_for_each_round(monkeypatch, tmp_path):
    calls = []
    canceled = []

    class FakeTimer:
        def cancel(self):
            canceled.append(True)

    def fake_start_round_timeout_timer(timeout_seconds, message, output_callback):
        calls.append((timeout_seconds, message))
        return FakeTimer()

    monkeypatch.setattr(
        batch_service,
        "_start_round_timeout_timer",
        fake_start_round_timeout_timer,
    )

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
        jobs=(LeagueBackfillJob("169", "中超", 50),),
        runner=fake_runner,
        season=2026,
        from_date=date(2026, 1, 15),
        mode=BatchBackfillMode.SAFE,
        chunk_size=4,
        request_budget_per_league=120,
        timeout_seconds=20,
        max_snapshots_per_match=450,
        max_rounds_per_league=1,
        stop_after_empty_matches=8,
        round_timeout_seconds=0.1,
        log_dir=tmp_path,
        output_callback=None,
    )

    assert calls == [(0.1, "中超 第1轮超过 0.1 秒无返回，强制结束 OddsPapi worker")]
    assert canceled == [True]


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
    assert all(call["historical_odds_cooldown_seconds"] == 6 for call in calls)


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


def test_batch_worker_passes_detail_progress_callback_to_runner(tmp_path):
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        kwargs["progress_callback"]("detail: historical_odds_request_start fixture=fixture-1")
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

    assert calls[0]["progress_callback"] is not None
    log_text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.glob("*.log"))
    assert "detail: historical_odds_request_start fixture=fixture-1" in log_text


def test_batch_worker_writes_structured_progress_snapshot(tmp_path):
    calls = []

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
        max_rounds_per_league=3,
        stop_after_empty_matches=8,
        log_dir=tmp_path,
        output_callback=None,
    )

    progress_path = tmp_path / "oddspapi-worker-progress.json"
    assert progress_path.exists()
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    assert progress["status"] == "done"
    assert progress["mode"] == "safe"
    assert progress["season"] == 2025
    assert progress["current_league"]["league_id"] == "62"
    assert progress["current_league"]["league_name"] == "Ligue 2"
    assert progress["current_league"]["round"] == 2
    assert progress["current_league"]["processed_matches"] == 1
    assert progress["current_league"]["inserted_snapshots"] == 100
    assert progress["current_league"]["requests_used"] == 3
    assert progress["current_league"]["last_round"]["processed_matches"] == 0
    assert progress["totals"]["processed_matches"] == 1
    assert progress["totals"]["inserted_snapshots"] == 100
    assert progress["totals"]["requests_used"] == 3


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

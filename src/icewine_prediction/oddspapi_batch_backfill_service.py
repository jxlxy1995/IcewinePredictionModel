from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time
from enum import Enum
import json
import os
from pathlib import Path
from threading import Timer
from typing import Callable, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import func

from icewine_prediction.database import create_database_engine, create_session_factory, initialize_database
from icewine_prediction.oddspapi_sync_runner import (
    API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS,
    OddsPapiSyncResult,
    run_oddspapi_sync_result,
)
from icewine_prediction.display_service import DisplayNameService
from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, OddsSourceMatch
from icewine_prediction.notification_service import notify_local_completion
from icewine_prediction.settings import LeagueSettings, load_project_settings
from icewine_prediction.time_utils import now_beijing


class BatchBackfillMode(str, Enum):
    SAFE = "safe"
    BALANCED = "balanced"
    FAST = "fast"


@dataclass(frozen=True)
class LeagueBackfillJob:
    league_id: str
    league_name: str
    priority: int


@dataclass(frozen=True)
class LeagueBackfillReport:
    league_id: str
    league_name: str
    status: str
    round_count: int
    processed_match_count: int
    matched_count: int
    failed_match_count: int
    inserted_snapshot_count: int
    skipped_duplicate_snapshot_count: int
    skipped_existing_odds_count: int
    asian_handicap_count: int
    total_goals_count: int
    requests_used: int
    stop_reason: str
    match_winner_count: int = 0


@dataclass(frozen=True)
class BatchBackfillReport:
    mode: str
    worker_count: int
    league_reports: tuple[LeagueBackfillReport, ...]


@dataclass(frozen=True)
class WorkerProgressContext:
    progress_path: Path
    mode: str
    season: int
    worker_count: int
    league_count: int
    totals_by_league_id: dict[str, int]


class OddsPapiSyncRunner(Protocol):
    def __call__(
        self,
        *,
        season: int,
        max_matches: int,
        request_budget: int,
        timeout_seconds: int,
        max_snapshots_per_match: int,
        league_ids: set[str],
        from_date: datetime | None,
        skip_match_ids: set[int] | None,
        historical_odds_cooldown_seconds: float,
        progress_callback,
    ) -> OddsPapiSyncResult:
        ...


def run_oddspapi_batch_backfill(
    season: int,
    mode: str = "balanced",
    chunk_size: int = 20,
    request_budget_per_league: int = 800,
    timeout_seconds: int = 20,
    max_snapshots_per_match: int = 151,
    max_rounds_per_league: int = 20,
    stop_after_empty_matches: int = 8,
    stop_after_failed_rounds: int = 2,
    round_timeout_seconds: float | None = 90,
    league_ids: set[str] | None = None,
    from_date: date | datetime | None = None,
    skip_match_ids: set[int] | None = None,
) -> str:
    settings = load_project_settings()
    jobs = build_league_backfill_jobs(settings.leagues, requested_league_ids=league_ids)
    report = run_oddspapi_batch_backfill_with_runner(
        jobs=jobs,
        runner=run_oddspapi_sync_result,
        season=season,
        from_date=from_date,
        mode=BatchBackfillMode(mode),
        chunk_size=chunk_size,
        request_budget_per_league=request_budget_per_league,
        timeout_seconds=timeout_seconds,
        max_snapshots_per_match=max_snapshots_per_match,
        max_rounds_per_league=max_rounds_per_league,
        stop_after_empty_matches=stop_after_empty_matches,
        stop_after_failed_rounds=stop_after_failed_rounds,
        round_timeout_seconds=round_timeout_seconds,
        skip_match_ids=skip_match_ids,
    )
    return format_batch_backfill_report(report)


def run_oddspapi_batch_worker(
    season: int,
    mode: str = "balanced",
    chunk_size: int = 10,
    request_budget_per_league: int = 500,
    timeout_seconds: int = 20,
    max_snapshots_per_match: int = 151,
    max_rounds_per_league: int = 2,
    stop_after_empty_matches: int = 8,
    stop_after_failed_rounds: int = 2,
    round_timeout_seconds: float | None = 90,
    historical_odds_cooldown_seconds: float = 6,
    hard_timeout_seconds: float | None = 0,
    log_dir: str | Path = "logs/odds",
    league_ids: set[str] | None = None,
    from_date: date | datetime | None = None,
    skip_match_ids: set[int] | None = None,
    notify_on_complete: bool = False,
    output_callback: Callable[[str], None] | None = None,
) -> str:
    settings = load_project_settings()
    jobs = build_league_backfill_jobs(settings.leagues, requested_league_ids=league_ids)
    report = run_oddspapi_batch_worker_with_runner(
        jobs=jobs,
        runner=run_oddspapi_sync_result,
        season=season,
        from_date=from_date,
        mode=BatchBackfillMode(mode),
        chunk_size=chunk_size,
        request_budget_per_league=request_budget_per_league,
        timeout_seconds=timeout_seconds,
        max_snapshots_per_match=max_snapshots_per_match,
        max_rounds_per_league=max_rounds_per_league,
        stop_after_empty_matches=stop_after_empty_matches,
        stop_after_failed_rounds=stop_after_failed_rounds,
        round_timeout_seconds=round_timeout_seconds,
        historical_odds_cooldown_seconds=historical_odds_cooldown_seconds,
        hard_timeout_seconds=hard_timeout_seconds,
        skip_match_ids=skip_match_ids,
        log_dir=Path(log_dir),
        notify_on_complete=notify_on_complete,
        notification_callback=notify_local_completion,
        output_callback=output_callback,
    )
    return format_batch_backfill_report(report)


def build_league_backfill_jobs(
    leagues: list[LeagueSettings],
    requested_league_ids: set[str] | None,
) -> tuple[LeagueBackfillJob, ...]:
    display_service = DisplayNameService()
    jobs = []
    for league in leagues:
        league_id = str(league.api_football_id)
        if not league.enabled:
            continue
        if league_id not in API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS:
            continue
        if requested_league_ids is not None and league_id not in requested_league_ids:
            continue
        jobs.append(
            LeagueBackfillJob(
                league_id=league_id,
                league_name=display_service.display_league(
                    f"{league.name} ({league.country})"
                ),
                priority=league.priority,
            )
        )
    return tuple(sorted(jobs, key=lambda job: (-job.priority, job.league_id)))


def run_oddspapi_batch_backfill_with_runner(
    *,
    jobs: tuple[LeagueBackfillJob, ...],
    runner: OddsPapiSyncRunner,
    season: int,
    from_date: date | datetime | None,
    mode: BatchBackfillMode,
    chunk_size: int,
    request_budget_per_league: int,
    timeout_seconds: int,
    max_snapshots_per_match: int,
    max_rounds_per_league: int,
    stop_after_empty_matches: int,
    stop_after_failed_rounds: int = 2,
    round_timeout_seconds: float | None = 90,
    hard_timeout_seconds: float | None = 0,
    historical_odds_cooldown_seconds: float = 6,
    skip_match_ids: set[int] | None = None,
) -> BatchBackfillReport:
    worker_count = min(_worker_count_for_mode(mode), max(len(jobs), 1))
    return _run_batch_backfill(
        jobs=jobs,
        runner=runner,
        season=season,
        from_date=_normalize_from_date(from_date),
        mode=mode,
        chunk_size=chunk_size,
        request_budget_per_league=request_budget_per_league,
        timeout_seconds=timeout_seconds,
        max_snapshots_per_match=max_snapshots_per_match,
        max_rounds_per_league=max_rounds_per_league,
        stop_after_empty_matches=stop_after_empty_matches,
        stop_after_failed_rounds=stop_after_failed_rounds,
        round_timeout_seconds=round_timeout_seconds,
        historical_odds_cooldown_seconds=historical_odds_cooldown_seconds,
        skip_match_ids=skip_match_ids,
        worker_count=worker_count,
        progress_callback=None,
    )


def run_oddspapi_batch_worker_with_runner(
    *,
    jobs: tuple[LeagueBackfillJob, ...],
    runner: OddsPapiSyncRunner,
    season: int,
    from_date: date | datetime | None,
    mode: BatchBackfillMode,
    chunk_size: int,
    request_budget_per_league: int,
    timeout_seconds: int,
    max_snapshots_per_match: int,
    max_rounds_per_league: int,
    stop_after_empty_matches: int,
    stop_after_failed_rounds: int = 2,
    round_timeout_seconds: float | None = 90,
    hard_timeout_seconds: float | None = 0,
    historical_odds_cooldown_seconds: float = 6,
    skip_match_ids: set[int] | None = None,
    log_dir: Path,
    notify_on_complete: bool = False,
    notification_callback: Callable[[str, str], bool] | None = None,
    output_callback: Callable[[str], None] | None,
) -> BatchBackfillReport:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / _build_worker_log_filename()
    progress_path = log_dir / "oddspapi-worker-progress.json"
    logger = _WorkerLogger(log_path=log_path, output_callback=output_callback)
    worker_count = min(_worker_count_for_mode(mode), max(len(jobs), 1))
    progress_context = WorkerProgressContext(
        progress_path=progress_path,
        mode=mode.value,
        season=season,
        worker_count=worker_count,
        league_count=len(jobs),
        totals_by_league_id=_count_candidate_matches_by_league(
            jobs=jobs,
            season=season,
            from_date=_normalize_from_date(from_date),
            skip_match_ids=skip_match_ids,
        ),
    )
    logger.write(
        f"开始 OddsPapi 后台回填 mode={mode.value} workers={worker_count} "
        f"leagues={len(jobs)} log={log_path}"
    )
    _write_worker_progress_snapshot(
        context=progress_context,
        status="running",
        current_league=None,
        totals=_MutableLeagueTotals(),
    )
    hard_timeout_timer = _start_hard_timeout_timer(hard_timeout_seconds, logger.write)
    try:
        report = _run_batch_backfill(
            jobs=jobs,
            runner=runner,
            season=season,
            from_date=_normalize_from_date(from_date),
            mode=mode,
            chunk_size=chunk_size,
            request_budget_per_league=request_budget_per_league,
            timeout_seconds=timeout_seconds,
            max_snapshots_per_match=max_snapshots_per_match,
            max_rounds_per_league=max_rounds_per_league,
            stop_after_empty_matches=stop_after_empty_matches,
            stop_after_failed_rounds=stop_after_failed_rounds,
            round_timeout_seconds=round_timeout_seconds,
            historical_odds_cooldown_seconds=historical_odds_cooldown_seconds,
            skip_match_ids=skip_match_ids,
            worker_count=worker_count,
            progress_callback=logger.write,
            progress_context=progress_context,
        )
    finally:
        if hard_timeout_timer is not None:
            hard_timeout_timer.cancel()
    logger.write("完成 OddsPapi 后台回填")
    logger.write(format_batch_backfill_report(report))
    _write_worker_progress_snapshot(
        context=progress_context,
        status="done",
        current_league=_build_final_progress_league(
            report.league_reports[-1],
            progress_path=progress_path,
        )
        if report.league_reports
        else None,
        totals=_build_progress_totals_from_report(report),
    )
    if notify_on_complete:
        notifier = notification_callback or notify_local_completion
        notification_sent = notifier(
            "OddsPapi 回填完成",
            _build_completion_notification_message(report),
        )
        logger.write(f"通知发送结果 sent={notification_sent}")
    if hard_timeout_seconds is not None and hard_timeout_seconds > 0:
        logger.write("硬超时保护已启用，完成后强制结束 OddsPapi worker")
        os._exit(0)
    return report


def _build_completion_notification_message(report: BatchBackfillReport) -> str:
    league_names = "、".join(league.league_name for league in report.league_reports) or "无联赛"
    requests_used = sum(league.requests_used for league in report.league_reports)
    snapshots = sum(league.inserted_snapshot_count for league in report.league_reports)
    return (
        f"{league_names} 已完成，"
        f"leagues={len(report.league_reports)} snapshots={snapshots} requests={requests_used}"
    )


def _start_hard_timeout_timer(
    hard_timeout_seconds: float | None,
    output_callback: Callable[[str], None],
) -> Timer | None:
    if hard_timeout_seconds is None or hard_timeout_seconds <= 0:
        return None

    def exit_process() -> None:
        output_callback(f"硬超时 {hard_timeout_seconds} 秒，强制结束 OddsPapi worker")
        os._exit(124)

    timer = Timer(hard_timeout_seconds, exit_process)
    timer.daemon = True
    timer.start()
    return timer


def _start_round_timeout_timer(
    timeout_seconds: float | None,
    message: str,
    output_callback: Callable[[str], None] | None,
) -> Timer | None:
    if timeout_seconds is None or timeout_seconds <= 0:
        return None

    def exit_process() -> None:
        if output_callback is not None:
            output_callback(message)
        os._exit(124)

    timer = Timer(timeout_seconds, exit_process)
    timer.daemon = True
    timer.start()
    return timer


def format_batch_backfill_report(report) -> str:
    lines = [
        f"批量回填模式 {report.mode} workers={report.worker_count}",
        f"联赛数 {len(report.league_reports)}",
    ]
    for league_report in report.league_reports:
        lines.append(
            f"{league_report.league_name} id={league_report.league_id} "
            f"status={league_report.status} rounds={league_report.round_count} "
            f"processed={league_report.processed_match_count} "
            f"snapshots={league_report.inserted_snapshot_count} "
            f"failed={league_report.failed_match_count} "
            f"requests={league_report.requests_used} "
            f"reason={league_report.stop_reason} "
            f"match_winner={getattr(league_report, 'match_winner_count', 0)}"
        )
    return "\n".join(lines)


def _run_batch_backfill(
    *,
    jobs: tuple[LeagueBackfillJob, ...],
    runner: OddsPapiSyncRunner,
    season: int,
    from_date: datetime | None,
    mode: BatchBackfillMode,
    chunk_size: int,
    request_budget_per_league: int,
    timeout_seconds: int,
    max_snapshots_per_match: int,
    max_rounds_per_league: int,
    stop_after_empty_matches: int,
    stop_after_failed_rounds: int,
    round_timeout_seconds: float | None,
    historical_odds_cooldown_seconds: float,
    skip_match_ids: set[int] | None,
    worker_count: int,
    progress_callback: Callable[[str], None] | None,
    progress_context: WorkerProgressContext | None = None,
) -> BatchBackfillReport:
    if not jobs:
        return BatchBackfillReport(mode=mode.value, worker_count=worker_count, league_reports=())
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(
                _run_league_backfill,
                job=job,
                runner=runner,
                season=season,
                from_date=from_date,
                chunk_size=chunk_size,
                request_budget_per_league=request_budget_per_league,
                timeout_seconds=timeout_seconds,
                max_snapshots_per_match=max_snapshots_per_match,
                max_rounds_per_league=max_rounds_per_league,
                stop_after_empty_matches=stop_after_empty_matches,
                stop_after_failed_rounds=stop_after_failed_rounds,
                round_timeout_seconds=round_timeout_seconds,
                historical_odds_cooldown_seconds=historical_odds_cooldown_seconds,
                skip_match_ids=skip_match_ids,
                progress_callback=progress_callback,
                progress_context=progress_context,
            )
            for job in jobs
        ]
        reports = [future.result() for future in as_completed(futures)]
    by_league_id = {report.league_id: report for report in reports}
    ordered_reports = tuple(by_league_id[job.league_id] for job in jobs)
    return BatchBackfillReport(
        mode=mode.value,
        worker_count=worker_count,
        league_reports=ordered_reports,
    )


def _count_candidate_matches_by_league(
    *,
    jobs: tuple[LeagueBackfillJob, ...],
    season: int,
    from_date: datetime | None,
    skip_match_ids: set[int] | None,
) -> dict[str, int]:
    if not jobs:
        return {}
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        counts = {}
        for job in jobs:
            counts[job.league_id] = _count_candidate_matches_for_league(
                session=session,
                league_id=job.league_id,
                season=season,
                from_date=from_date,
                skip_match_ids=skip_match_ids,
            )
        return counts


def _count_candidate_matches_for_league(
    *,
    session,
    league_id: str,
    season: int,
    from_date: datetime | None,
    skip_match_ids: set[int] | None,
) -> int:
    query = (
        session.query(func.count(Match.id))
        .join(League, Match.league_id == League.id)
        .outerjoin(
            HistoricalOddsSnapshot,
            (HistoricalOddsSnapshot.match_id == Match.id)
            & (HistoricalOddsSnapshot.source_name == "oddspapi"),
        )
        .outerjoin(
            OddsSourceMatch,
            (OddsSourceMatch.match_id == Match.id)
            & (OddsSourceMatch.source_name == "oddspapi"),
        )
        .filter(League.source_league_id == league_id)
        .filter(Match.season == season)
        .filter(Match.status == "finished")
        .filter(Match.home_score.isnot(None))
        .filter(Match.away_score.isnot(None))
        .filter(HistoricalOddsSnapshot.id.is_(None))
        .filter(
            (OddsSourceMatch.id.is_(None))
            | (OddsSourceMatch.historical_odds_status.is_(None))
            | (~OddsSourceMatch.historical_odds_status.in_({"empty", "unavailable", "unmatched"}))
        )
    )
    if from_date is not None:
        query = query.filter(Match.kickoff_time >= from_date)
    if skip_match_ids:
        query = query.filter(~Match.id.in_(skip_match_ids))
    return int(query.scalar() or 0)


def _run_league_backfill(
    *,
    job: LeagueBackfillJob,
    runner: OddsPapiSyncRunner,
    season: int,
    from_date: datetime | None,
    chunk_size: int,
    request_budget_per_league: int,
    timeout_seconds: int,
    max_snapshots_per_match: int,
    max_rounds_per_league: int,
    stop_after_empty_matches: int,
    stop_after_failed_rounds: int,
    round_timeout_seconds: float | None,
    historical_odds_cooldown_seconds: float,
    skip_match_ids: set[int] | None,
    progress_callback: Callable[[str], None] | None = None,
    progress_context: WorkerProgressContext | None = None,
) -> LeagueBackfillReport:
    totals = _MutableLeagueTotals()
    consecutive_empty_matches = 0
    consecutive_failed_rounds = 0
    stop_reason = "达到联赛轮次上限"
    status = "stopped"
    for round_index in range(1, max_rounds_per_league + 1):
        if progress_callback is not None:
            progress_callback(
                f"{job.league_name} 第{round_index}轮开始 "
                f"chunk_size={chunk_size} request_budget={request_budget_per_league}"
            )
        round_timeout_timer = None
        if progress_context is not None:
            round_timeout_timer = _start_round_timeout_timer(
                round_timeout_seconds,
                (
                    f"{job.league_name} 第{round_index}轮超过 "
                    f"{round_timeout_seconds} 秒无返回，强制结束 OddsPapi worker"
                ),
                progress_callback,
            )
        try:
            result = _run_round_with_timeout(
                runner=runner,
                timeout_seconds=round_timeout_seconds,
                season=season,
                max_matches=chunk_size,
                request_budget=request_budget_per_league,
                request_timeout_seconds=timeout_seconds,
                max_snapshots_per_match=max_snapshots_per_match,
                league_id=job.league_id,
                from_date=from_date,
                skip_match_ids=skip_match_ids,
                historical_odds_cooldown_seconds=historical_odds_cooldown_seconds,
                progress_callback=progress_callback,
            )
        finally:
            if round_timeout_timer is not None:
                round_timeout_timer.cancel()
        totals.add(result)
        _emit_worker_progress(progress_callback, job, round_index, result)
        _write_worker_progress_snapshot(
            context=progress_context,
            status="running",
            current_league=_build_progress_league(
                job,
                round_index,
                totals,
                result,
                progress_context,
            ),
            totals=totals,
        )
        if result.error_message and "budget" in result.error_message.lower():
            stop_reason = result.error_message
            status = "stopped"
            break
        if _made_no_progress(result):
            stop_reason = "无候选或无进展"
            status = "done"
            break
        if _failed_round(result):
            consecutive_failed_rounds += 1
        else:
            consecutive_failed_rounds = 0
        if consecutive_failed_rounds >= stop_after_failed_rounds:
            stop_reason = "连续失败轮次达到阈值"
            status = "stopped"
            break
        if result.inserted_snapshot_count == 0:
            consecutive_empty_matches += result.processed_match_count
        else:
            consecutive_empty_matches = 0
        if consecutive_empty_matches >= stop_after_empty_matches:
            stop_reason = "连续空数据达到阈值"
            status = "stopped"
            break
    return LeagueBackfillReport(
        league_id=job.league_id,
        league_name=job.league_name,
        status=status,
        round_count=totals.round_count,
        processed_match_count=totals.processed_match_count,
        matched_count=totals.matched_count,
        failed_match_count=totals.failed_match_count,
        inserted_snapshot_count=totals.inserted_snapshot_count,
        skipped_duplicate_snapshot_count=totals.skipped_duplicate_snapshot_count,
        skipped_existing_odds_count=totals.skipped_existing_odds_count,
        asian_handicap_count=totals.asian_handicap_count,
        total_goals_count=totals.total_goals_count,
        requests_used=totals.requests_used,
        stop_reason=stop_reason,
        match_winner_count=totals.match_winner_count,
    )


def _build_progress_league(
    job: LeagueBackfillJob,
    round_index: int,
    totals: "_MutableLeagueTotals",
    last_round: OddsPapiSyncResult,
    progress_context: WorkerProgressContext | None = None,
) -> dict:
    total_matches = _progress_total_for_league(progress_context, job.league_id)
    return {
        "league_id": job.league_id,
        "league_name": job.league_name,
        "total_matches": total_matches,
        "progress_percent": _progress_percent(totals.processed_match_count, total_matches),
        "round": round_index,
        "processed_matches": totals.processed_match_count,
        "matched_matches": totals.matched_count,
        "failed_matches": totals.failed_match_count,
        "inserted_snapshots": totals.inserted_snapshot_count,
        "skipped_duplicate_snapshots": totals.skipped_duplicate_snapshot_count,
        "skipped_existing_odds": totals.skipped_existing_odds_count,
        "asian_handicap_snapshots": totals.asian_handicap_count,
        "total_goals_snapshots": totals.total_goals_count,
        "match_winner_snapshots": totals.match_winner_count,
        "requests_used": totals.requests_used,
        "last_round": _build_progress_round(last_round),
    }


def _build_final_progress_league(report: LeagueBackfillReport, *, progress_path: Path) -> dict:
    previous_last_round = _read_previous_last_round(progress_path)
    previous_current_league = _read_previous_current_league(progress_path)
    total_matches = (
        previous_current_league.get("total_matches")
        if isinstance(previous_current_league, dict)
        else None
    )
    return {
        "league_id": report.league_id,
        "league_name": report.league_name,
        "total_matches": total_matches,
        "progress_percent": _progress_percent(report.processed_match_count, total_matches),
        "status": report.status,
        "round": report.round_count,
        "processed_matches": report.processed_match_count,
        "matched_matches": report.matched_count,
        "failed_matches": report.failed_match_count,
        "inserted_snapshots": report.inserted_snapshot_count,
        "skipped_duplicate_snapshots": report.skipped_duplicate_snapshot_count,
        "skipped_existing_odds": report.skipped_existing_odds_count,
        "asian_handicap_snapshots": report.asian_handicap_count,
        "total_goals_snapshots": report.total_goals_count,
        "match_winner_snapshots": report.match_winner_count,
        "requests_used": report.requests_used,
        "stop_reason": report.stop_reason,
        "last_round": previous_last_round,
    }


def _read_previous_last_round(progress_path: Path) -> dict | None:
    current_league = _read_previous_current_league(progress_path)
    if not isinstance(current_league, dict):
        return None
    last_round = current_league.get("last_round")
    return last_round if isinstance(last_round, dict) else None


def _read_previous_current_league(progress_path: Path) -> dict | None:
    if not progress_path.exists():
        return None
    try:
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    current_league = progress.get("current_league")
    if not isinstance(current_league, dict):
        return None
    return current_league


def _build_progress_round(result: OddsPapiSyncResult) -> dict:
    return {
        "processed_matches": result.processed_match_count,
        "matched_matches": result.matched_count,
        "failed_matches": result.failed_match_count,
        "inserted_snapshots": result.inserted_snapshot_count,
        "skipped_duplicate_snapshots": result.skipped_duplicate_snapshot_count,
        "skipped_existing_odds": result.skipped_existing_odds_count,
        "asian_handicap_snapshots": result.asian_handicap_count,
        "total_goals_snapshots": result.total_goals_count,
        "match_winner_snapshots": result.match_winner_count,
        "requests_used": result.requests_used,
        "error_message": result.error_message,
    }


def _build_progress_totals_from_report(report: BatchBackfillReport) -> "_MutableLeagueTotals":
    totals = _MutableLeagueTotals()
    for league in report.league_reports:
        totals.round_count += league.round_count
        totals.processed_match_count += league.processed_match_count
        totals.matched_count += league.matched_count
        totals.failed_match_count += league.failed_match_count
        totals.inserted_snapshot_count += league.inserted_snapshot_count
        totals.skipped_duplicate_snapshot_count += league.skipped_duplicate_snapshot_count
        totals.skipped_existing_odds_count += league.skipped_existing_odds_count
        totals.asian_handicap_count += league.asian_handicap_count
        totals.total_goals_count += league.total_goals_count
        totals.match_winner_count += league.match_winner_count
        totals.requests_used += league.requests_used
    return totals


def _write_worker_progress_snapshot(
    *,
    context: WorkerProgressContext | None,
    status: str,
    current_league: dict | None,
    totals: "_MutableLeagueTotals",
) -> None:
    if context is None:
        return
    total_matches = sum(context.totals_by_league_id.values())
    payload = {
        "status": status,
        "mode": context.mode,
        "season": context.season,
        "worker_count": context.worker_count,
        "league_count": context.league_count,
        "total_matches": total_matches,
        "progress_percent": _progress_percent(totals.processed_match_count, total_matches),
        "updated_at": now_beijing().isoformat(),
        "current_league": current_league,
        "totals": {
            "rounds": totals.round_count,
            "processed_matches": totals.processed_match_count,
            "matched_matches": totals.matched_count,
            "failed_matches": totals.failed_match_count,
            "inserted_snapshots": totals.inserted_snapshot_count,
            "skipped_duplicate_snapshots": totals.skipped_duplicate_snapshot_count,
            "skipped_existing_odds": totals.skipped_existing_odds_count,
            "asian_handicap_snapshots": totals.asian_handicap_count,
            "total_goals_snapshots": totals.total_goals_count,
            "match_winner_snapshots": totals.match_winner_count,
            "requests_used": totals.requests_used,
        },
    }
    context.progress_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _progress_total_for_league(
    context: WorkerProgressContext | None,
    league_id: str,
) -> int | None:
    if context is None:
        return None
    return context.totals_by_league_id.get(league_id)


def _progress_percent(processed_matches: int, total_matches: int | None) -> float | None:
    if total_matches is None or total_matches <= 0:
        return None
    return round(min(processed_matches, total_matches) * 100 / total_matches, 1)


def _run_round_with_timeout(
    *,
    runner: OddsPapiSyncRunner,
    timeout_seconds: float | None,
    season: int,
    max_matches: int,
    request_budget: int,
    request_timeout_seconds: int,
    max_snapshots_per_match: int,
    league_id: str,
    from_date: datetime | None,
    skip_match_ids: set[int] | None,
    historical_odds_cooldown_seconds: float,
    progress_callback: Callable[[str], None] | None,
) -> OddsPapiSyncResult:
    # Do not enforce round timeouts with a thread: Python cannot stop the worker thread,
    # which can leave database writes running after the controller reports stopped.
    kwargs = {
        "season": season,
        "max_matches": max_matches,
        "request_budget": request_budget,
        "timeout_seconds": request_timeout_seconds,
        "max_snapshots_per_match": max_snapshots_per_match,
        "league_ids": {league_id},
        "from_date": from_date,
        "skip_match_ids": skip_match_ids,
        "historical_odds_cooldown_seconds": historical_odds_cooldown_seconds,
        "progress_callback": progress_callback,
    }
    return runner(**kwargs)


@dataclass
class _MutableLeagueTotals:
    round_count: int = 0
    processed_match_count: int = 0
    matched_count: int = 0
    failed_match_count: int = 0
    inserted_snapshot_count: int = 0
    skipped_duplicate_snapshot_count: int = 0
    skipped_existing_odds_count: int = 0
    asian_handicap_count: int = 0
    total_goals_count: int = 0
    match_winner_count: int = 0
    requests_used: int = 0

    def add(self, result: OddsPapiSyncResult) -> None:
        self.round_count += 1
        self.processed_match_count += result.processed_match_count
        self.matched_count += result.matched_count
        self.failed_match_count += result.failed_match_count
        self.inserted_snapshot_count += result.inserted_snapshot_count
        self.skipped_duplicate_snapshot_count += result.skipped_duplicate_snapshot_count
        self.skipped_existing_odds_count += result.skipped_existing_odds_count
        self.asian_handicap_count += result.asian_handicap_count
        self.total_goals_count += result.total_goals_count
        self.match_winner_count += result.match_winner_count
        self.requests_used += result.requests_used


def _made_no_progress(result: OddsPapiSyncResult) -> bool:
    return (
        result.processed_match_count == 0
        and result.failed_match_count == 0
        and result.inserted_snapshot_count == 0
    )


def _failed_round(result: OddsPapiSyncResult) -> bool:
    return (
        result.inserted_snapshot_count == 0
        and result.processed_match_count == 0
        and result.failed_match_count > 0
    )


def _worker_count_for_mode(mode: BatchBackfillMode) -> int:
    if mode == BatchBackfillMode.SAFE:
        return 1
    if mode == BatchBackfillMode.FAST:
        return 3
    return 2


def _normalize_from_date(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, datetime_time.min, tzinfo=ZoneInfo("Asia/Shanghai"))


def _emit_worker_progress(
    progress_callback: Callable[[str], None] | None,
    job: LeagueBackfillJob,
    round_index: int,
    result: OddsPapiSyncResult,
) -> None:
    if progress_callback is None:
        return
    progress_callback(
        f"{job.league_name} 第{round_index}轮 "
        f"processed={result.processed_match_count} "
        f"snapshots={result.inserted_snapshot_count} "
        f"failed={result.failed_match_count} "
        f"requests={result.requests_used}"
    )


def _build_worker_log_filename() -> str:
    return f"{now_beijing().strftime('%Y%m%d-%H%M%S')}-pid{os.getpid()}-oddspapi-batch-worker.log"


@dataclass
class _WorkerLogger:
    log_path: Path
    output_callback: Callable[[str], None] | None

    def write(self, message: str) -> None:
        line = f"{now_beijing().strftime('%Y-%m-%d %H:%M:%S')} {message}"
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(line + "\n")
        if self.output_callback is not None:
            self.output_callback(message)

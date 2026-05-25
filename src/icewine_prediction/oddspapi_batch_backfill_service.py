from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time
from enum import Enum
import os
from pathlib import Path
from typing import Callable, Protocol
from zoneinfo import ZoneInfo

from icewine_prediction.oddspapi_sync_runner import (
    API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS,
    OddsPapiSyncResult,
    run_oddspapi_sync_result,
)
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


@dataclass(frozen=True)
class BatchBackfillReport:
    mode: str
    worker_count: int
    league_reports: tuple[LeagueBackfillReport, ...]


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
    max_snapshots_per_match: int = 120,
    max_rounds_per_league: int = 20,
    stop_after_empty_matches: int = 8,
    league_ids: set[str] | None = None,
    from_date: date | datetime | None = None,
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
    )
    return format_batch_backfill_report(report)


def run_oddspapi_batch_worker(
    season: int,
    mode: str = "balanced",
    chunk_size: int = 10,
    request_budget_per_league: int = 500,
    timeout_seconds: int = 20,
    max_snapshots_per_match: int = 120,
    max_rounds_per_league: int = 2,
    stop_after_empty_matches: int = 8,
    log_dir: str | Path = "logs/odds",
    league_ids: set[str] | None = None,
    from_date: date | datetime | None = None,
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
                league_name=league.name,
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
    log_dir: Path,
    notify_on_complete: bool = False,
    notification_callback: Callable[[str, str], bool] | None = None,
    output_callback: Callable[[str], None] | None,
) -> BatchBackfillReport:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / _build_worker_log_filename()
    logger = _WorkerLogger(log_path=log_path, output_callback=output_callback)
    worker_count = min(_worker_count_for_mode(mode), max(len(jobs), 1))
    logger.write(
        f"开始 OddsPapi 后台回填 mode={mode.value} workers={worker_count} "
        f"leagues={len(jobs)} log={log_path}"
    )
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
        worker_count=worker_count,
        progress_callback=logger.write,
    )
    logger.write("完成 OddsPapi 后台回填")
    logger.write(format_batch_backfill_report(report))
    if notify_on_complete:
        notifier = notification_callback or notify_local_completion
        notification_sent = notifier(
            "OddsPapi 回填完成",
            _build_completion_notification_message(report),
        )
        logger.write(f"通知发送结果 sent={notification_sent}")
    return report


def _build_completion_notification_message(report: BatchBackfillReport) -> str:
    league_names = "、".join(league.league_name for league in report.league_reports) or "无联赛"
    requests_used = sum(league.requests_used for league in report.league_reports)
    snapshots = sum(league.inserted_snapshot_count for league in report.league_reports)
    return (
        f"{league_names} 已完成，"
        f"leagues={len(report.league_reports)} snapshots={snapshots} requests={requests_used}"
    )


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
            f"reason={league_report.stop_reason}"
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
    worker_count: int,
    progress_callback: Callable[[str], None] | None,
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
                progress_callback=progress_callback,
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
    progress_callback: Callable[[str], None] | None = None,
) -> LeagueBackfillReport:
    totals = _MutableLeagueTotals()
    consecutive_empty_matches = 0
    stop_reason = "达到联赛轮次上限"
    status = "stopped"
    for round_index in range(1, max_rounds_per_league + 1):
        result = runner(
            season=season,
            max_matches=chunk_size,
            request_budget=request_budget_per_league,
            timeout_seconds=timeout_seconds,
            max_snapshots_per_match=max_snapshots_per_match,
            league_ids={job.league_id},
            from_date=from_date,
            historical_odds_cooldown_seconds=5,
            progress_callback=None,
        )
        totals.add(result)
        _emit_worker_progress(progress_callback, job, round_index, result)
        if result.error_message and "budget" in result.error_message.lower():
            stop_reason = result.error_message
            status = "stopped"
            break
        if _made_no_progress(result):
            stop_reason = "无候选或无进展"
            status = "done"
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
    )


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
        self.requests_used += result.requests_used


def _made_no_progress(result: OddsPapiSyncResult) -> bool:
    return (
        result.processed_match_count == 0
        and result.failed_match_count == 0
        and result.inserted_snapshot_count == 0
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

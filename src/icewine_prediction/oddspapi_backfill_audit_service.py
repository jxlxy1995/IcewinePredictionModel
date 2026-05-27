from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from icewine_prediction.database import create_database_engine, create_session_factory, initialize_database
from icewine_prediction.display_service import DisplayNameService
from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, OddsSourceMatch

ODDSPAPI_SOURCE_NAME = "oddspapi"


@dataclass(frozen=True)
class OddsPapiWorkerProgressAudit:
    status: str | None
    mode: str | None
    season: int | None
    updated_at: str | None
    current_league_id: str | None
    current_league_name: str | None
    current_league_display_name: str | None
    round: int | None
    processed_matches: int | None
    inserted_snapshots: int | None
    failed_matches: int | None
    requests_used: int | None
    total_processed_matches: int | None
    total_inserted_snapshots: int | None
    total_failed_matches: int | None
    total_requests_used: int | None


@dataclass(frozen=True)
class OddsPapiLeagueBackfillAudit:
    league_name: str
    league_display_name: str
    source_league_id: str | None
    finished_matches: int
    matched_matches: int
    snapshot_matches: int
    snapshot_count: int
    asian_handicap_snapshot_count: int
    total_goals_snapshot_count: int
    status_counts: dict[str, int]
    error_counts: dict[str, int]


@dataclass(frozen=True)
class OddsPapiBackfillAuditReport:
    season: int
    log_dir: Path
    worker_progress: OddsPapiWorkerProgressAudit | None
    league_summaries: tuple[OddsPapiLeagueBackfillAudit, ...]
    top_errors: int


def build_oddspapi_backfill_audit(
    season: int,
    log_dir: str | Path = "logs/odds",
    top_errors: int = 5,
) -> str:
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = build_oddspapi_backfill_audit_for_session(
            session=session,
            season=season,
            log_dir=log_dir,
            top_errors=top_errors,
        )
    return format_oddspapi_backfill_audit_report(report)


def build_oddspapi_backfill_audit_for_session(
    session: Session,
    season: int,
    log_dir: str | Path = "logs/odds",
    top_errors: int = 5,
    display_service: DisplayNameService | None = None,
) -> OddsPapiBackfillAuditReport:
    display_service = display_service or DisplayNameService()
    log_dir = Path(log_dir)
    matches = (
        session.query(Match)
        .join(League)
        .filter(Match.season == season)
        .filter(Match.status == "finished")
        .order_by(League.priority.desc(), League.name.asc(), Match.kickoff_time.asc())
        .all()
    )
    match_ids = [match.id for match in matches]
    source_matches = _load_source_matches(session, match_ids)
    snapshots = _load_snapshots(session, match_ids)
    league_summaries = _build_league_summaries(
        matches=matches,
        source_matches=source_matches,
        snapshots=snapshots,
        display_service=display_service,
    )
    worker_progress = _load_worker_progress(
        log_dir / "oddspapi-worker-progress.json",
        display_service=display_service,
    )
    return OddsPapiBackfillAuditReport(
        season=season,
        log_dir=log_dir,
        worker_progress=worker_progress,
        league_summaries=tuple(league_summaries),
        top_errors=top_errors,
    )


def format_oddspapi_backfill_audit_report(report: OddsPapiBackfillAuditReport) -> str:
    lines = [
        "OddsPapi 回填审计",
        f"season={report.season} log_dir={report.log_dir}",
        "",
        "Worker 进度",
    ]
    if report.worker_progress is None:
        lines.append("- 暂无 worker 进度快照")
    else:
        lines.extend(_format_worker_progress(report.worker_progress))
    lines.extend(["", "联赛汇总"])
    if not report.league_summaries:
        lines.append("- 暂无已完赛比赛")
    for summary in report.league_summaries:
        lines.append(_format_league_summary(summary))
        if summary.error_counts:
            lines.append("  失败原因 Top")
            for reason, count in Counter(summary.error_counts).most_common(report.top_errors):
                lines.append(f"  - {reason} x{count}")
    return "\n".join(lines)


def _load_source_matches(
    session: Session,
    match_ids: list[int],
) -> dict[int, OddsSourceMatch]:
    if not match_ids:
        return {}
    rows = (
        session.query(OddsSourceMatch)
        .filter(OddsSourceMatch.match_id.in_(match_ids))
        .filter(OddsSourceMatch.source_name == ODDSPAPI_SOURCE_NAME)
        .all()
    )
    return {row.match_id: row for row in rows}


def _load_snapshots(
    session: Session,
    match_ids: list[int],
) -> list[HistoricalOddsSnapshot]:
    if not match_ids:
        return []
    return (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id.in_(match_ids))
        .filter(HistoricalOddsSnapshot.source_name == ODDSPAPI_SOURCE_NAME)
        .all()
    )


def _build_league_summaries(
    matches: list[Match],
    source_matches: dict[int, OddsSourceMatch],
    snapshots: list[HistoricalOddsSnapshot],
    display_service: DisplayNameService,
) -> list[OddsPapiLeagueBackfillAudit]:
    snapshots_by_match_id: dict[int, list[HistoricalOddsSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        snapshots_by_match_id[snapshot.match_id].append(snapshot)
    matches_by_league: dict[int, list[Match]] = defaultdict(list)
    for match in matches:
        matches_by_league[match.league_id].append(match)
    summaries = []
    for league_matches in matches_by_league.values():
        league = league_matches[0].league
        match_ids = [match.id for match in league_matches]
        league_source_matches = [
            source_matches[match_id] for match_id in match_ids if match_id in source_matches
        ]
        league_snapshots = [
            snapshot for match_id in match_ids for snapshot in snapshots_by_match_id.get(match_id, [])
        ]
        status_counts = Counter(
            source_match.historical_odds_status or "unknown"
            for source_match in league_source_matches
        )
        error_counts = Counter(
            source_match.historical_odds_error
            for source_match in league_source_matches
            if source_match.historical_odds_error
        )
        summaries.append(
            OddsPapiLeagueBackfillAudit(
                league_name=league.name,
                league_display_name=display_service.display_league(league.name),
                source_league_id=str(league.source_league_id)
                if league.source_league_id is not None
                else None,
                finished_matches=len(league_matches),
                matched_matches=len(
                    [
                        source_match
                        for source_match in league_source_matches
                        if source_match.source_fixture_id
                    ]
                ),
                snapshot_matches=len({snapshot.match_id for snapshot in league_snapshots}),
                snapshot_count=len(league_snapshots),
                asian_handicap_snapshot_count=len(
                    [
                        snapshot
                        for snapshot in league_snapshots
                        if snapshot.market_type == "asian_handicap"
                    ]
                ),
                total_goals_snapshot_count=len(
                    [
                        snapshot
                        for snapshot in league_snapshots
                        if snapshot.market_type == "total_goals"
                    ]
                ),
                status_counts=dict(status_counts),
                error_counts=dict(error_counts),
            )
        )
    return summaries


def _load_worker_progress(
    path: Path,
    display_service: DisplayNameService,
) -> OddsPapiWorkerProgressAudit | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    current_league = payload.get("current_league") or {}
    totals = payload.get("totals") or {}
    current_league_name = _str_or_none(current_league.get("league_name"))
    current_display_name = (
        display_service.display_league(current_league_name)
        if current_league_name is not None
        else None
    )
    return OddsPapiWorkerProgressAudit(
        status=_str_or_none(payload.get("status")),
        mode=_str_or_none(payload.get("mode")),
        season=_int_or_none(payload.get("season")),
        updated_at=_str_or_none(payload.get("updated_at")),
        current_league_id=_str_or_none(current_league.get("league_id")),
        current_league_name=current_league_name,
        current_league_display_name=current_display_name,
        round=_int_or_none(current_league.get("round")),
        processed_matches=_int_or_none(current_league.get("processed_matches")),
        inserted_snapshots=_int_or_none(current_league.get("inserted_snapshots")),
        failed_matches=_int_or_none(current_league.get("failed_matches")),
        requests_used=_int_or_none(current_league.get("requests_used")),
        total_processed_matches=_int_or_none(totals.get("processed_matches")),
        total_inserted_snapshots=_int_or_none(totals.get("inserted_snapshots")),
        total_failed_matches=_int_or_none(totals.get("failed_matches")),
        total_requests_used=_int_or_none(totals.get("requests_used")),
    )


def _format_worker_progress(progress: OddsPapiWorkerProgressAudit) -> list[str]:
    lines = [
        f"- 状态 {progress.status or '-'} updated_at={progress.updated_at or '-'}",
        f"- 模式 {progress.mode or '-'} season={progress.season or '-'}",
    ]
    if progress.current_league_name:
        lines.append(
            "- 当前 "
            f"{_display_with_original(progress.current_league_display_name, progress.current_league_name)} "
            f"id={progress.current_league_id or '-'} "
            f"round={progress.round or 0} "
            f"processed={progress.processed_matches or 0} "
            f"snapshots={progress.inserted_snapshots or 0} "
            f"failed={progress.failed_matches or 0} "
            f"requests={progress.requests_used or 0}"
        )
    lines.append(
        "- 总计 "
        f"processed={progress.total_processed_matches or 0} "
        f"snapshots={progress.total_inserted_snapshots or 0} "
        f"failed={progress.total_failed_matches or 0} "
        f"requests={progress.total_requests_used or 0}"
    )
    return lines


def _format_league_summary(summary: OddsPapiLeagueBackfillAudit) -> str:
    status_text = " ".join(
        f"{status}={count}" for status, count in sorted(summary.status_counts.items())
    )
    if not status_text:
        status_text = "-"
    return (
        f"- {_display_with_original(summary.league_display_name, summary.league_name)} "
        f"id={summary.source_league_id or '-'} "
        f"finished={summary.finished_matches} "
        f"matched={summary.matched_matches} "
        f"snapshot_matches={summary.snapshot_matches} "
        f"snapshots={summary.snapshot_count} "
        f"asian={summary.asian_handicap_snapshot_count} "
        f"total_goals={summary.total_goals_snapshot_count} "
        f"status {status_text}"
    )


def _display_with_original(display_name: str | None, original_name: str) -> str:
    if not display_name or display_name == original_name:
        return original_name
    return f"{display_name} ({original_name})"


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)

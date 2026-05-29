from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
import csv
import json
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from icewine_prediction.config import BEIJING_TIMEZONE
from icewine_prediction.baseline_training_dataset_market_baseline_service import (
    build_baseline_training_dataset_market_baseline_report,
    write_baseline_training_dataset_market_baseline_report,
)
from icewine_prediction.baseline_training_dataset_qa_service import (
    build_baseline_training_dataset_qa_report,
    write_baseline_training_dataset_qa_report,
)
from icewine_prediction.baseline_training_dataset_service import (
    build_baseline_training_dataset,
    write_baseline_training_dataset_csv,
    write_baseline_training_dataset_report,
)
from icewine_prediction.database import create_database_engine, create_session_factory
from icewine_prediction.display_service import (
    DisplayNameService,
    load_display_names,
    save_team_display_names,
)
from icewine_prediction.display_translation_status_service import DisplayTranslationStatusService
from icewine_prediction.models import (
    HistoricalOddsSnapshot,
    League,
    Match,
    OddsSourceMatch,
    RecommendationRecord,
    Team,
)
from icewine_prediction.oddspapi_backfill_audit_service import (
    OddsPapiBackfillAuditReport,
    build_oddspapi_backfill_audit_for_session,
)
from icewine_prediction.oddspapi_worker_process_service import _is_process_running
from icewine_prediction.paper_recommendation_queue_service import (
    PaperQueueScore,
    build_paper_recommendation_queue,
)
from icewine_prediction.time_utils import now_beijing


def create_web_app(
    *,
    session_factory: Callable[[], Session] | None = None,
    log_dir: str | Path = "logs/odds",
    process_running_checker: Callable[[int], bool] = _is_process_running,
    display_name_service: DisplayNameService | None = None,
    display_translation_status_service: DisplayTranslationStatusService | None = None,
    display_names_path: Path = Path("config/display_names.yaml"),
    baseline_dataset_path: Path = Path("local_data/training/baseline_main_leagues_20260529.csv"),
    baseline_dataset_report_path: Path = Path(
        "docs/数据审计/20260529-baseline-training-dataset.md"
    ),
    baseline_qa_report_path: Path = Path(
        "docs/数据审计/20260529-baseline-training-dataset-qa.md"
    ),
    baseline_market_report_path: Path = Path(
        "docs/模型实验/20260529-close-market-baseline-evaluation.md"
    ),
    paper_queue_scorer: Callable[[dict[str, str]], PaperQueueScore | None] | None = None,
    clock: Callable[[], datetime] = now_beijing,
) -> FastAPI:
    if session_factory is None:
        engine = create_database_engine()
        session_factory = create_session_factory(engine)
    log_dir = Path(log_dir)
    display_name_service = display_name_service or DisplayNameService(load_display_names(display_names_path))
    display_translation_status_service = (
        display_translation_status_service or DisplayTranslationStatusService()
    )

    app = FastAPI(title="Icewine Prediction Console API")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/dashboard/summary")
    def dashboard_summary() -> dict[str, int]:
        with session_factory() as session:
            return build_dashboard_summary(session)

    @app.get("/api/display/translation-status")
    def display_translation_status() -> dict[str, Any]:
        return {
            "done_league_seasons": sorted(
                display_translation_status_service.list_done_keys()
            )
        }

    @app.get("/api/leagues/coverage")
    def league_coverage() -> list[dict[str, Any]]:
        with session_factory() as session:
            return build_league_coverage(session, display_name_service=display_name_service)

    @app.get("/api/workers")
    def workers() -> list[dict[str, Any]]:
        return build_worker_statuses(log_dir, process_running_checker=process_running_checker)

    @app.get("/api/oddspapi/backfill-audit")
    def oddspapi_backfill_audit(season: int = 2025, top_errors: int = 5) -> dict[str, Any]:
        with session_factory() as session:
            report = build_oddspapi_backfill_audit_for_session(
                session=session,
                season=season,
                log_dir=log_dir,
                top_errors=top_errors,
                display_service=display_name_service,
            )
            return build_oddspapi_backfill_audit_payload(report)

    @app.get("/api/unmatched")
    def unmatched() -> list[dict[str, Any]]:
        with session_factory() as session:
            return build_unmatched_matches(session, display_name_service=display_name_service)

    @app.get("/api/display/missing-team-names")
    def missing_team_names() -> list[dict[str, Any]]:
        with session_factory() as session:
            return build_missing_team_display_names(
                session,
                display_name_service=display_name_service,
            )

    @app.get("/api/display/team-name-workspace")
    def team_name_workspace(league_id: int, season: int) -> dict[str, Any]:
        with session_factory() as session:
            payload = build_team_display_name_workspace(
                session,
                league_id=league_id,
                season=season,
                display_name_service=display_name_service,
                display_translation_status_service=display_translation_status_service,
            )
            if payload is None:
                raise HTTPException(status_code=404, detail="联赛或赛季不存在")
            return payload

    @app.post("/api/display/team-name-workspace/done")
    def mark_team_name_workspace_done(payload: dict[str, int]) -> dict[str, Any]:
        league_id = int(payload["league_id"])
        season = int(payload["season"])
        display_translation_status_service.mark_done(league_id=league_id, season=season)
        return {
            "league_id": league_id,
            "season": season,
            "is_translation_done": True,
        }

    @app.post("/api/display/team-names")
    def save_display_team_names(payload: dict[str, dict[str, str]]) -> dict[str, int]:
        team_names = {
            team_name: display_name.strip()
            for team_name, display_name in payload.get("teams", {}).items()
            if display_name.strip()
        }
        save_team_display_names(team_names, path=display_names_path)
        display_name_service.display_names = load_display_names(display_names_path)
        return {"saved_count": len(team_names)}

    @app.get("/api/matches/with-odds")
    def matches_with_odds() -> list[dict[str, Any]]:
        with session_factory() as session:
            return build_matches_with_odds(session, display_name_service=display_name_service)

    @app.get("/api/matches/{match_id}/odds-trends")
    def match_odds_trends(match_id: int) -> dict[str, Any]:
        with session_factory() as session:
            payload = build_match_odds_trends(
                session,
                match_id=match_id,
                display_name_service=display_name_service,
            )
            if payload is None:
                raise HTTPException(status_code=404, detail="比赛不存在")
            return payload

    @app.get("/api/recommendation-records")
    def recommendation_records() -> list[dict[str, Any]]:
        with session_factory() as session:
            return build_recommendation_records(session, display_name_service=display_name_service)

    @app.get("/api/paper-recommendations/queue")
    def paper_recommendation_queue(
        hours: int = 72,
        near_start_hours: int = 6,
        edge_threshold: str = "0.10",
    ) -> dict[str, Any]:
        with session_factory() as session:
            report = build_paper_recommendation_queue(
                session,
                now=clock(),
                hours=hours,
                near_start_hours=near_start_hours,
                edge_threshold=edge_threshold,
                scorer=paper_queue_scorer,
                display_name_service=display_name_service,
            )
            return build_paper_recommendation_queue_payload(
                report,
                display_name_service=display_name_service,
            )

    @app.get("/api/training/workspace")
    def training_workspace() -> dict[str, Any]:
        return build_training_workspace_payload(
            baseline_dataset_path=baseline_dataset_path,
            baseline_dataset_report_path=baseline_dataset_report_path,
            baseline_qa_report_path=baseline_qa_report_path,
            baseline_market_report_path=baseline_market_report_path,
        )

    @app.post("/api/training/baseline-dataset")
    def run_training_baseline_dataset() -> dict[str, Any]:
        with session_factory() as session:
            dataset = build_baseline_training_dataset(session)
        write_baseline_training_dataset_csv(dataset, baseline_dataset_path)
        write_baseline_training_dataset_report(dataset.audit, baseline_dataset_report_path)
        return build_training_workspace_payload(
            baseline_dataset_path=baseline_dataset_path,
            baseline_dataset_report_path=baseline_dataset_report_path,
            baseline_qa_report_path=baseline_qa_report_path,
            baseline_market_report_path=baseline_market_report_path,
        )

    @app.post("/api/training/baseline-dataset-qa")
    def run_training_baseline_dataset_qa() -> dict[str, Any]:
        if not baseline_dataset_path.exists():
            raise HTTPException(status_code=404, detail="baseline dataset csv not found")
        report = build_baseline_training_dataset_qa_report(baseline_dataset_path)
        write_baseline_training_dataset_qa_report(report, baseline_qa_report_path)
        return build_training_workspace_payload(
            baseline_dataset_path=baseline_dataset_path,
            baseline_dataset_report_path=baseline_dataset_report_path,
            baseline_qa_report_path=baseline_qa_report_path,
            baseline_market_report_path=baseline_market_report_path,
        )

    @app.post("/api/training/market-baseline")
    def run_training_market_baseline() -> dict[str, Any]:
        if not baseline_dataset_path.exists():
            raise HTTPException(status_code=404, detail="baseline dataset csv not found")
        report = build_baseline_training_dataset_market_baseline_report(baseline_dataset_path)
        write_baseline_training_dataset_market_baseline_report(report, baseline_market_report_path)
        return build_training_workspace_payload(
            baseline_dataset_path=baseline_dataset_path,
            baseline_dataset_report_path=baseline_dataset_report_path,
            baseline_qa_report_path=baseline_qa_report_path,
            baseline_market_report_path=baseline_market_report_path,
        )

    return app


def build_dashboard_summary(session: Session) -> dict[str, int]:
    total_matches = session.query(func.count(Match.id)).scalar() or 0
    finished_matches = (
        session.query(func.count(Match.id)).filter(Match.status == "finished").scalar() or 0
    )
    matches_with_historical_odds = (
        session.query(func.count(func.distinct(HistoricalOddsSnapshot.match_id))).scalar() or 0
    )
    historical_odds_snapshots = session.query(func.count(HistoricalOddsSnapshot.id)).scalar() or 0
    unmatched_matches = (
        session.query(func.count(OddsSourceMatch.id))
        .filter(OddsSourceMatch.historical_odds_status == "unmatched")
        .scalar()
        or 0
    )
    return {
        "total_matches": total_matches,
        "finished_matches": finished_matches,
        "matches_with_historical_odds": matches_with_historical_odds,
        "historical_odds_snapshots": historical_odds_snapshots,
        "unmatched_matches": unmatched_matches,
    }


def build_league_coverage(
    session: Session,
    *,
    display_name_service: DisplayNameService | None = None,
) -> list[dict[str, Any]]:
    display_name_service = display_name_service or DisplayNameService()
    rows = (
        session.query(
            League.id,
            League.name,
            League.country_or_region,
            Match.season,
            func.count(func.distinct(Match.id)).label("finished_matches"),
            func.count(func.distinct(HistoricalOddsSnapshot.match_id)).label(
                "matches_with_historical_odds"
            ),
        )
        .join(Match, Match.league_id == League.id)
        .outerjoin(HistoricalOddsSnapshot, HistoricalOddsSnapshot.match_id == Match.id)
        .filter(Match.status == "finished")
        .group_by(League.id, League.name, League.country_or_region, Match.season)
        .order_by(League.name.asc(), Match.season.desc())
        .all()
    )
    unmatched_rows = dict(
        session.query(League.id, func.count(OddsSourceMatch.id))
        .join(Match, Match.league_id == League.id)
        .join(OddsSourceMatch, OddsSourceMatch.match_id == Match.id)
        .filter(OddsSourceMatch.historical_odds_status == "unmatched")
        .group_by(League.id)
        .all()
    )
    return [
        {
            "league_id": league_id,
            "league_name": league_name,
            "league_display_name": display_name_service.display_league(league_name),
            "country_or_region": country_or_region,
            "season": season,
            "finished_matches": finished_matches,
            "matches_with_historical_odds": matches_with_historical_odds,
            "coverage_ratio": _format_ratio(matches_with_historical_odds, finished_matches),
            "unmatched_matches": unmatched_rows.get(league_id, 0),
        }
        for (
            league_id,
            league_name,
            country_or_region,
            season,
            finished_matches,
            matches_with_historical_odds,
        ) in rows
    ]


def build_worker_statuses(
    log_dir: Path,
    *,
    process_running_checker: Callable[[int], bool] = _is_process_running,
) -> list[dict[str, Any]]:
    statuses = []
    for status_path in sorted((log_dir / "workers").glob("*.json")):
        try:
            payload = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        statuses.append(_normalize_worker_status(payload, process_running_checker))
    current_status_path = log_dir / "oddspapi-worker-current.json"
    if current_status_path.exists() and not statuses:
        try:
            statuses.append(
                _normalize_worker_status(
                    json.loads(current_status_path.read_text(encoding="utf-8")),
                    process_running_checker,
                )
            )
        except (OSError, json.JSONDecodeError):
            pass
    return statuses


def build_oddspapi_backfill_audit_payload(
    report: OddsPapiBackfillAuditReport,
) -> dict[str, Any]:
    return {
        "season": report.season,
        "log_dir": str(report.log_dir),
        "worker_progress": (
            asdict(report.worker_progress) if report.worker_progress is not None else None
        ),
        "league_summaries": [asdict(summary) for summary in report.league_summaries],
    }


def build_unmatched_matches(
    session: Session,
    *,
    display_name_service: DisplayNameService | None = None,
) -> list[dict[str, Any]]:
    display_name_service = display_name_service or DisplayNameService()
    rows = (
        session.query(OddsSourceMatch)
        .options(
            joinedload(OddsSourceMatch.match).joinedload(Match.league),
            joinedload(OddsSourceMatch.match).joinedload(Match.home_team),
            joinedload(OddsSourceMatch.match).joinedload(Match.away_team),
        )
        .filter(OddsSourceMatch.historical_odds_status == "unmatched")
        .order_by(OddsSourceMatch.historical_odds_checked_at.desc().nullslast())
        .limit(200)
        .all()
    )
    return [
        {
            **_format_match_names(row.match, display_name_service),
            "source_name": row.source_name,
            "match_reason": row.match_reason,
            "historical_odds_error": row.historical_odds_error,
        }
        for row in rows
    ]


def build_missing_team_display_names(
    session: Session,
    *,
    display_name_service: DisplayNameService | None = None,
    limit: int = 300,
) -> list[dict[str, Any]]:
    display_name_service = display_name_service or DisplayNameService()
    return _build_team_display_rows(
        session,
        display_name_service=display_name_service,
        missing_only=True,
        limit=limit,
    )


def _build_team_display_rows(
    session: Session,
    *,
    display_name_service: DisplayNameService,
    league_id: int | None = None,
    season: int | None = None,
    missing_only: bool,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    rows_by_key: dict[tuple[int, int | None, int], dict[str, Any]] = {}

    for side in ("home", "away"):
        team_id_column = Match.home_team_id if side == "home" else Match.away_team_id
        query = (
            session.query(
                League.id.label("league_id"),
                League.name.label("league_name"),
                Match.season.label("season"),
                Team.id.label("team_id"),
                Team.canonical_name.label("team_name"),
                Team.logo_url.label("team_logo_url"),
                func.count(Match.id).label("match_count"),
                func.max(Match.kickoff_time).label("latest_kickoff_time"),
            )
            .join(Match, Match.league_id == League.id)
            .join(Team, Team.id == team_id_column)
        )
        if league_id is not None:
            query = query.filter(League.id == league_id)
        if season is not None:
            query = query.filter(Match.season == season)
        rows = query.group_by(
            League.id,
            League.name,
            Match.season,
            Team.id,
            Team.canonical_name,
            Team.logo_url,
        ).all()
        for row in rows:
            team_display_name = display_name_service.display_team(row.team_name)
            is_missing_display_name = team_display_name == row.team_name
            if missing_only and not is_missing_display_name:
                continue
            key = (row.league_id, row.season, row.team_id)
            item = rows_by_key.setdefault(
                key,
                {
                    "league_id": row.league_id,
                    "league_name": row.league_name,
                    "league_display_name": display_name_service.display_league(row.league_name),
                    "season": row.season,
                    "team_id": row.team_id,
                    "team_name": row.team_name,
                    "team_display_name": None if is_missing_display_name else team_display_name,
                    "team_logo_url": row.team_logo_url,
                    "is_missing_display_name": is_missing_display_name,
                    "match_count": 0,
                    "latest_kickoff_time": None,
                    "rank": None,
                    "points": None,
                },
            )
            item["match_count"] += row.match_count
            if item["latest_kickoff_time"] is None or row.latest_kickoff_time > item["latest_kickoff_time"]:
                item["latest_kickoff_time"] = row.latest_kickoff_time

    items = sorted(
        rows_by_key.values(),
        key=lambda item: (
            item["league_display_name"],
            -(item["season"] or 0),
            item["rank"] or 9999,
            -item["match_count"],
            item["team_name"],
        ),
    )
    if limit is not None:
        items = items[:limit]
    return [
        {
            **item,
            "latest_kickoff_time": _format_datetime(item["latest_kickoff_time"]),
        }
        for item in items
    ]


def build_team_display_name_workspace(
    session: Session,
    *,
    league_id: int,
    season: int,
    display_name_service: DisplayNameService | None = None,
    display_translation_status_service: DisplayTranslationStatusService | None = None,
) -> dict[str, Any] | None:
    display_name_service = display_name_service or DisplayNameService()
    display_translation_status_service = (
        display_translation_status_service or DisplayTranslationStatusService()
    )
    league = session.query(League).filter(League.id == league_id).one_or_none()
    if league is None:
        return None
    items = _build_team_display_rows(
        session,
        display_name_service=display_name_service,
        league_id=league_id,
        season=season,
        missing_only=False,
    )
    if not items:
        return None
    return {
        "league_id": league.id,
        "league_name": league.name,
        "league_display_name": display_name_service.display_league(league.name),
        "season": season,
        "is_translation_done": display_translation_status_service.is_done(
            league_id=league_id,
            season=season,
        ),
        "teams": items,
    }


def build_matches_with_odds(
    session: Session,
    *,
    limit: int = 100,
    display_name_service: DisplayNameService | None = None,
) -> list[dict[str, Any]]:
    display_name_service = display_name_service or DisplayNameService()
    snapshot_counts = (
        session.query(
            HistoricalOddsSnapshot.match_id.label("match_id"),
            func.count(HistoricalOddsSnapshot.id).label("snapshot_count"),
        )
        .group_by(HistoricalOddsSnapshot.match_id)
        .subquery()
    )
    rows = (
        session.query(Match, snapshot_counts.c.snapshot_count)
        .options(
            joinedload(Match.league),
            joinedload(Match.home_team),
            joinedload(Match.away_team),
        )
        .join(snapshot_counts, snapshot_counts.c.match_id == Match.id)
        .order_by(Match.kickoff_time.desc(), Match.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            **_format_match_names(match, display_name_service),
            "snapshot_count": snapshot_count,
        }
        for match, snapshot_count in rows
    ]


def build_match_odds_trends(
    session: Session,
    *,
    match_id: int,
    display_name_service: DisplayNameService | None = None,
) -> dict[str, Any] | None:
    display_name_service = display_name_service or DisplayNameService()
    match = (
        session.query(Match)
        .options(joinedload(Match.league), joinedload(Match.home_team), joinedload(Match.away_team))
        .filter(Match.id == match_id)
        .one_or_none()
    )
    if match is None:
        return None
    snapshots = (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id == match_id)
        .order_by(HistoricalOddsSnapshot.snapshot_time.asc(), HistoricalOddsSnapshot.outcome_side.asc())
        .all()
    )
    return {
        **_format_match_names(match, display_name_service),
        "asian_handicap": _build_market_points(snapshots, market_type="asian_handicap"),
        "total_goals": _build_market_points(snapshots, market_type="total_goals"),
        "match_winner": _build_market_points(snapshots, market_type="match_winner"),
    }


def build_recommendation_records(
    session: Session,
    *,
    display_name_service: DisplayNameService | None = None,
) -> list[dict[str, Any]]:
    display_name_service = display_name_service or DisplayNameService()
    records = (
        session.query(RecommendationRecord)
        .order_by(RecommendationRecord.created_at.desc(), RecommendationRecord.id.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": record.id,
            "match_id": record.match_id,
            "league_name": record.league_name,
            "league_display_name": display_name_service.display_league(record.league_name),
            "home_team_name": record.home_team_name,
            "home_team_display_name": display_name_service.display_team(record.home_team_name),
            "away_team_name": record.away_team_name,
            "away_team_display_name": display_name_service.display_team(record.away_team_name),
            "kickoff_time": _format_datetime(record.kickoff_time),
            "market_type": record.market_type,
            "side": record.side,
            "market_line": _format_decimal(record.market_line, "0.00"),
            "odds": _format_decimal(record.odds, "0.000"),
            "confidence_grade": record.confidence_grade,
            "stake_units": _format_decimal(record.stake_units, "0.00"),
            "status": record.status,
            "settlement_result": record.settlement_result,
            "profit_units": (
                _format_decimal(record.profit_units, "0.000")
                if record.profit_units is not None
                else None
            ),
        }
        for record in records
    ]


def build_paper_recommendation_queue_payload(
    report,
    *,
    display_name_service: DisplayNameService | None = None,
) -> dict[str, Any]:
    display_name_service = display_name_service or DisplayNameService()
    return {
        "generated_at": report.generated_at,
        "window_start": report.window_start,
        "window_end": report.window_end,
        "hours": report.hours,
        "near_start_hours": report.near_start_hours,
        "edge_threshold": str(report.edge_threshold),
        "model_name": report.model_name,
        "total_matches": report.total_matches,
        "candidate_count": report.candidate_count,
        "status_counts": report.status_counts,
        "prefetch_requested": report.prefetch_requested,
        "near_start_fixture_ids": report.near_start_fixture_ids,
        "prefetch_result": report.prefetch_result,
        "rows": [
            {
                "match_id": row.match_id,
                "source_match_id": row.source_match_id,
                "kickoff_time": row.kickoff_time,
                "league_name": row.league_name,
                "league_display_name": row.league_display_name,
                "home_team_name": row.home_team_name,
                "home_team_display_name": row.home_team_display_name,
                "away_team_name": row.away_team_name,
                "away_team_display_name": row.away_team_display_name,
                "status": row.status,
                "market_type": row.market_type,
                "line": _format_optional_decimal(row.line, "0.00"),
                "side": row.side,
                "recommended_handicap": row.recommended_handicap,
                "odds": _format_optional_decimal(row.odds, "0.000"),
                "model_probability": _format_optional_decimal(row.model_probability, "0.0000"),
                "market_probability": _format_optional_decimal(row.market_probability, "0.0000"),
                "edge": _format_optional_decimal(row.edge, "0.0000"),
                "line_bucket": row.line_bucket,
                "risk_tags": list(row.risk_tags),
            }
            for row in report.rows
        ],
    }


def build_training_workspace_payload(
    *,
    baseline_dataset_path: Path,
    baseline_dataset_report_path: Path,
    baseline_qa_report_path: Path,
    baseline_market_report_path: Path,
) -> dict[str, Any]:
    dataset_payload = _build_training_dataset_file_payload(baseline_dataset_path)
    qa_payload: dict[str, Any] = {"exists": False, "path": str(baseline_qa_report_path)}
    if baseline_dataset_path.exists():
        qa_report = build_baseline_training_dataset_qa_report(baseline_dataset_path)
        qa_payload = {
            "exists": baseline_qa_report_path.exists(),
            "path": str(baseline_qa_report_path),
            "updated_at": _format_file_mtime(baseline_qa_report_path),
            "empty_required_cells": sum(qa_report.empty_required_cells.values()),
            "invalid_odds_cells": sum(qa_report.invalid_odds_cells.values()),
            "invalid_probability_cells": sum(qa_report.invalid_probability_cells.values()),
            "invalid_overround_cells": sum(qa_report.invalid_overround_cells.values()),
            "thin_history_count": qa_report.thin_history_count,
            "thin_history_ratio": qa_report.thin_history_ratio,
            "low_sample_leagues": qa_report.low_sample_leagues,
        }

    market_payload: dict[str, Any] = {
        "exists": False,
        "path": str(baseline_market_report_path),
    }
    if baseline_dataset_path.exists():
        market_report = build_baseline_training_dataset_market_baseline_report(
            baseline_dataset_path
        )
        market_payload = {
            "exists": baseline_market_report_path.exists(),
            "path": str(baseline_market_report_path),
            "updated_at": _format_file_mtime(baseline_market_report_path),
            "market_samples": market_report.total_market_samples,
            "evaluated_market_samples": market_report.total_evaluated_market_samples,
            "skipped_market_samples": market_report.total_skipped_market_samples,
            "market_reports": {
                market_type: {
                    "evaluated_count": report.evaluated_count,
                    "skipped_count": report.skipped_count,
                    "accuracy": str(report.accuracy),
                    "log_loss": str(report.average_log_loss),
                    "brier": str(report.average_brier_score),
                    "overround": str(report.average_overround),
                    "flat_bet_profit_units": str(report.flat_bet_profit_units),
                    "flat_bet_roi": str(report.flat_bet_roi),
                    "predicted_side_counts": report.predicted_side_counts,
                }
                for market_type, report in market_report.market_reports.items()
            },
        }

    return {
        "dataset": dataset_payload,
        "dataset_report": _build_report_file_payload(baseline_dataset_report_path),
        "qa": qa_payload,
        "market_baseline": market_payload,
    }


def _build_training_dataset_file_payload(path: Path) -> dict[str, Any]:
    payload = _build_report_file_payload(path)
    payload.update({"row_count": 0, "column_count": 0})
    if not path.exists():
        return payload
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        row_count = sum(1 for _ in reader)
        column_count = len(reader.fieldnames or [])
    payload.update({"row_count": row_count, "column_count": column_count})
    return payload


def _build_report_file_payload(path: Path) -> dict[str, Any]:
    return {
        "exists": path.exists(),
        "path": str(path),
        "updated_at": _format_file_mtime(path),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }


def _format_file_mtime(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat()


def _build_market_points(
    snapshots: list[HistoricalOddsSnapshot],
    *,
    market_type: str,
) -> list[dict[str, str]]:
    grouped: dict[tuple[datetime, Decimal, str], dict[str, str]] = defaultdict(dict)
    for snapshot in snapshots:
        if snapshot.market_type != market_type:
            continue
        key = (snapshot.snapshot_time, snapshot.market_line, snapshot.bookmaker)
        point = grouped[key]
        point["snapshot_time"] = _format_historical_odds_datetime(snapshot.snapshot_time)
        point["bookmaker"] = snapshot.bookmaker
        point["market_line"] = _format_decimal(snapshot.market_line, "0.00")
        if market_type == "asian_handicap":
            if snapshot.outcome_side == "home":
                point["home_odds"] = _format_decimal(snapshot.odds, "0.000")
            if snapshot.outcome_side == "away":
                point["away_odds"] = _format_decimal(snapshot.odds, "0.000")
        if market_type == "total_goals":
            if snapshot.outcome_side == "over":
                point["over_odds"] = _format_decimal(snapshot.odds, "0.000")
            if snapshot.outcome_side == "under":
                point["under_odds"] = _format_decimal(snapshot.odds, "0.000")
        if market_type == "match_winner":
            if snapshot.outcome_side == "home":
                point["home_odds"] = _format_decimal(snapshot.odds, "0.000")
            if snapshot.outcome_side == "draw":
                point["draw_odds"] = _format_decimal(snapshot.odds, "0.000")
            if snapshot.outcome_side == "away":
                point["away_odds"] = _format_decimal(snapshot.odds, "0.000")
    return list(grouped.values())


def _normalize_worker_status(
    payload: dict[str, Any],
    process_running_checker: Callable[[int], bool],
) -> dict[str, Any]:
    pid = int(payload.get("pid") or 0)
    return {
        "pid": pid,
        "started_at": payload.get("started_at"),
        "status": payload.get("status", "unknown"),
        "runtime_status": "running" if process_running_checker(pid) else "stopped",
        "mode": payload.get("mode"),
        "season": payload.get("season"),
        "league_ids": payload.get("league_ids") or [],
        "process_log_path": payload.get("process_log_path"),
        "worker_log_dir": payload.get("worker_log_dir"),
        "notify_on_complete": bool(payload.get("notify_on_complete", False)),
    }


def _format_match_names(match: Match, display_name_service: DisplayNameService) -> dict[str, Any]:
    league_name = match.league.name
    home_team_name = match.home_team.canonical_name
    away_team_name = match.away_team.canonical_name
    return {
        "match_id": match.id,
        "league_name": league_name,
        "league_display_name": display_name_service.display_league(league_name),
        "home_team_name": home_team_name,
        "home_team_display_name": display_name_service.display_team(home_team_name),
        "away_team_name": away_team_name,
        "away_team_display_name": display_name_service.display_team(away_team_name),
        "kickoff_time": _format_datetime(match.kickoff_time),
    }


def _format_ratio(count: int, total: int) -> str:
    if total == 0:
        return "0.0000"
    return str((Decimal(count) / Decimal(total)).quantize(Decimal("0.0000")))


def _format_decimal(value: Decimal, pattern: str) -> str:
    return str(Decimal(value).quantize(Decimal(pattern)))


def _format_optional_decimal(value: Decimal | None, pattern: str) -> str | None:
    if value is None:
        return None
    return _format_decimal(value, pattern)


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _format_historical_odds_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("UTC"))
    return value.astimezone(ZoneInfo(BEIJING_TIMEZONE)).isoformat()

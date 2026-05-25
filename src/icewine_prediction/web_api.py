from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from icewine_prediction.database import create_database_engine, create_session_factory
from icewine_prediction.display_service import DisplayNameService
from icewine_prediction.models import (
    HistoricalOddsSnapshot,
    League,
    Match,
    OddsSourceMatch,
    RecommendationRecord,
    Team,
)
from icewine_prediction.oddspapi_worker_process_service import _is_process_running


def create_web_app(
    *,
    session_factory: Callable[[], Session] | None = None,
    log_dir: str | Path = "logs/odds",
    process_running_checker: Callable[[int], bool] = _is_process_running,
    display_name_service: DisplayNameService | None = None,
) -> FastAPI:
    if session_factory is None:
        engine = create_database_engine()
        session_factory = create_session_factory(engine)
    log_dir = Path(log_dir)
    display_name_service = display_name_service or DisplayNameService()

    app = FastAPI(title="Icewine Prediction Console API")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/dashboard/summary")
    def dashboard_summary() -> dict[str, int]:
        with session_factory() as session:
            return build_dashboard_summary(session)

    @app.get("/api/leagues/coverage")
    def league_coverage() -> list[dict[str, Any]]:
        with session_factory() as session:
            return build_league_coverage(session, display_name_service=display_name_service)

    @app.get("/api/workers")
    def workers() -> list[dict[str, Any]]:
        return build_worker_statuses(log_dir, process_running_checker=process_running_checker)

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
    rows_by_key: dict[tuple[int, int | None, int], dict[str, Any]] = {}

    for side in ("home", "away"):
        team_id_column = Match.home_team_id if side == "home" else Match.away_team_id
        rows = (
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
            .group_by(
                League.id,
                League.name,
                Match.season,
                Team.id,
                Team.canonical_name,
                Team.logo_url,
            )
            .all()
        )
        for row in rows:
            if display_name_service.display_team(row.team_name) != row.team_name:
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
                    "team_logo_url": row.team_logo_url,
                    "match_count": 0,
                    "latest_kickoff_time": None,
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
            -item["match_count"],
            item["team_name"],
        ),
    )
    return [
        {
            **item,
            "latest_kickoff_time": _format_datetime(item["latest_kickoff_time"]),
        }
        for item in items[:limit]
    ]


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
        point["snapshot_time"] = _format_datetime(snapshot.snapshot_time)
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


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()

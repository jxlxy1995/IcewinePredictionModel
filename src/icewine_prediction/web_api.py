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
from icewine_prediction.models import (
    HistoricalOddsSnapshot,
    League,
    Match,
    OddsSourceMatch,
    RecommendationRecord,
)


def create_web_app(
    *,
    session_factory: Callable[[], Session] | None = None,
    log_dir: str | Path = "logs/odds",
) -> FastAPI:
    if session_factory is None:
        engine = create_database_engine()
        session_factory = create_session_factory(engine)
    log_dir = Path(log_dir)

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
            return build_league_coverage(session)

    @app.get("/api/workers")
    def workers() -> list[dict[str, Any]]:
        return build_worker_statuses(log_dir)

    @app.get("/api/unmatched")
    def unmatched() -> list[dict[str, Any]]:
        with session_factory() as session:
            return build_unmatched_matches(session)

    @app.get("/api/matches/{match_id}/odds-trends")
    def match_odds_trends(match_id: int) -> dict[str, Any]:
        with session_factory() as session:
            payload = build_match_odds_trends(session, match_id=match_id)
            if payload is None:
                raise HTTPException(status_code=404, detail="比赛不存在")
            return payload

    @app.get("/api/recommendation-records")
    def recommendation_records() -> list[dict[str, Any]]:
        with session_factory() as session:
            return build_recommendation_records(session)

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


def build_league_coverage(session: Session) -> list[dict[str, Any]]:
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


def build_worker_statuses(log_dir: Path) -> list[dict[str, Any]]:
    statuses = []
    for status_path in sorted((log_dir / "workers").glob("*.json")):
        try:
            payload = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        statuses.append(_normalize_worker_status(payload))
    current_status_path = log_dir / "oddspapi-worker-current.json"
    if current_status_path.exists() and not statuses:
        try:
            statuses.append(
                _normalize_worker_status(
                    json.loads(current_status_path.read_text(encoding="utf-8"))
                )
            )
        except (OSError, json.JSONDecodeError):
            pass
    return statuses


def build_unmatched_matches(session: Session) -> list[dict[str, Any]]:
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
            "match_id": row.match_id,
            "league_name": row.match.league.name,
            "home_team_name": row.match.home_team.canonical_name,
            "away_team_name": row.match.away_team.canonical_name,
            "kickoff_time": _format_datetime(row.match.kickoff_time),
            "source_name": row.source_name,
            "match_reason": row.match_reason,
            "historical_odds_error": row.historical_odds_error,
        }
        for row in rows
    ]


def build_match_odds_trends(session: Session, *, match_id: int) -> dict[str, Any] | None:
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
        "match_id": match.id,
        "league_name": match.league.name,
        "home_team_name": match.home_team.canonical_name,
        "away_team_name": match.away_team.canonical_name,
        "kickoff_time": _format_datetime(match.kickoff_time),
        "asian_handicap": _build_market_points(snapshots, market_type="asian_handicap"),
        "total_goals": _build_market_points(snapshots, market_type="total_goals"),
    }


def build_recommendation_records(session: Session) -> list[dict[str, Any]]:
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
            "home_team_name": record.home_team_name,
            "away_team_name": record.away_team_name,
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


def _normalize_worker_status(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "pid": int(payload.get("pid") or 0),
        "started_at": payload.get("started_at"),
        "status": payload.get("status", "unknown"),
        "mode": payload.get("mode"),
        "season": payload.get("season"),
        "league_ids": payload.get("league_ids") or [],
        "process_log_path": payload.get("process_log_path"),
        "worker_log_dir": payload.get("worker_log_dir"),
        "notify_on_complete": bool(payload.get("notify_on_complete", False)),
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

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from icewine_prediction.historical_odds_service import (
    store_historical_odds_raw_snapshots,
    store_historical_odds_snapshots,
)
from icewine_prediction.models import Match
from icewine_prediction.sources.zqcf918_client import ZQCF918Client
from icewine_prediction.sources.zqcf918_odds_mapper import map_zqcf918_timelines
from icewine_prediction.zqcf918_match_service import get_zqcf918_match_id


UTC = ZoneInfo("UTC")
SyncResultPayload = dict[str, list[dict[str, Any]] | int]


def run_zqcf918_sync_for_session(
    *,
    session: Session,
    match_ids: list[int] | set[int],
    client: ZQCF918Client | Any | None = None,
) -> SyncResultPayload:
    client = client or ZQCF918Client()
    ordered_match_ids = list(match_ids)
    matches = session.query(Match).filter(Match.id.in_(ordered_match_ids)).all()
    matches_by_id = {match.id: match for match in matches}
    success: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    requests = 0

    for match_id in ordered_match_ids:
        match = matches_by_id.get(match_id)
        if match is None:
            skipped.append({"match_id": match_id, "message": "match not found"})
            continue
        source_match = get_zqcf918_match_id(session, match.id)
        if source_match is None or not source_match.source_fixture_id:
            skipped.append({"match_id": match.id, "message": "missing zqcf918 match ID"})
            continue
        try:
            payloads = client.fetch_all_timelines(source_match.source_fixture_id)
            requests += len(payloads)
            mapped = map_zqcf918_timelines(
                match_id=match.id,
                source_fixture_id=source_match.source_fixture_id,
                payloads=payloads,
            )
            if not mapped:
                _mark_source_match(
                    session,
                    source_match,
                    status="empty",
                    error="no usable zqcf918 odds",
                )
                failed.append({"match_id": match.id, "message": "no usable zqcf918 odds"})
                continue
            raw_result = store_historical_odds_raw_snapshots(
                session,
                mapped,
                kickoff_time=match.kickoff_time,
                max_snapshots_per_match=450,
                max_snapshots_per_market_type=150,
            )
            store_result = store_historical_odds_snapshots(
                session,
                mapped,
                kickoff_time=match.kickoff_time,
                max_snapshots_per_match=200,
                max_snapshots_per_market_type=50,
                execution_timepoint_source_snapshots=mapped,
            )
            _mark_source_match(session, source_match, status="stored", error=None)
            success.append(
                {
                    "match_id": match.id,
                    "message": "zqcf918 odds synced",
                    "created_count": store_result.inserted_count,
                    "updated_count": 0,
                    "skipped_count": raw_result.skipped_duplicate_count
                    + store_result.skipped_duplicate_count,
                    "requests_used": len(payloads),
                    "source_fixture_id": source_match.source_fixture_id,
                    "snapshot_count": len(mapped),
                }
            )
        except Exception as error:
            _mark_source_match(session, source_match, status="failed", error=str(error))
            failed.append({"match_id": match.id, "message": str(error)})

    return {"success": success, "failed": failed, "skipped": skipped, "requests": requests, "credits": 0}


def _mark_source_match(session: Session, source_match, *, status: str, error: str | None) -> None:
    source_match.historical_odds_status = status
    source_match.historical_odds_checked_at = datetime.now(tz=UTC)
    source_match.historical_odds_error = error
    session.commit()

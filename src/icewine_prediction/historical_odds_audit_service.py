from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from icewine_prediction.models import HistoricalOddsRawSnapshot, HistoricalOddsSnapshot, League, Match, OddsSourceMatch

BEIJING_TIMEZONE = ZoneInfo("Asia/Shanghai")
UTC_TIMEZONE = ZoneInfo("UTC")


@dataclass(frozen=True)
class LiveHistoricalOddsAuditReport:
    match_count: int
    snapshot_count: int


@dataclass(frozen=True)
class HistoricalOddsClearReport:
    main_snapshot_count: int
    raw_snapshot_count: int
    reset_source_match_count: int


def audit_live_historical_odds(session: Session) -> LiveHistoricalOddsAuditReport:
    rows = _live_snapshot_ids(session)
    match_ids = {match_id for _, match_id in rows}
    return LiveHistoricalOddsAuditReport(
        match_count=len(match_ids),
        snapshot_count=len(rows),
    )


def delete_live_historical_odds(session: Session) -> int:
    rows = _live_snapshot_ids(session)
    snapshot_ids = [snapshot_id for snapshot_id, _ in rows]
    if not snapshot_ids:
        return 0
    deleted = (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.id.in_(snapshot_ids))
        .delete(synchronize_session=False)
    )
    session.commit()
    return int(deleted or 0)


def clear_historical_odds_snapshots(session: Session, source_name: str) -> int:
    deleted = (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.source_name == source_name)
        .delete(synchronize_session=False)
    )
    session.commit()
    return int(deleted or 0)


def clear_historical_odds_for_leagues(
    session: Session,
    *,
    source_name: str,
    league_ids: set[str],
) -> HistoricalOddsClearReport:
    match_ids = [
        match_id
        for (match_id,) in (
            session.query(Match.id)
            .join(League, Match.league_id == League.id)
            .filter(League.source_league_id.in_(league_ids))
            .all()
        )
    ]
    if not match_ids:
        return HistoricalOddsClearReport(
            main_snapshot_count=0,
            raw_snapshot_count=0,
            reset_source_match_count=0,
        )
    main_deleted = (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.source_name == source_name)
        .filter(HistoricalOddsSnapshot.match_id.in_(match_ids))
        .delete(synchronize_session=False)
    )
    raw_deleted = (
        session.query(HistoricalOddsRawSnapshot)
        .filter(HistoricalOddsRawSnapshot.source_name == source_name)
        .filter(HistoricalOddsRawSnapshot.match_id.in_(match_ids))
        .delete(synchronize_session=False)
    )
    reset_count = (
        session.query(OddsSourceMatch)
        .filter(OddsSourceMatch.source_name == source_name)
        .filter(OddsSourceMatch.match_id.in_(match_ids))
        .update(
            {
                OddsSourceMatch.historical_odds_status: None,
                OddsSourceMatch.historical_odds_checked_at: None,
                OddsSourceMatch.historical_odds_error: None,
            },
            synchronize_session=False,
        )
    )
    session.commit()
    return HistoricalOddsClearReport(
        main_snapshot_count=int(main_deleted or 0),
        raw_snapshot_count=int(raw_deleted or 0),
        reset_source_match_count=int(reset_count or 0),
    )


def _live_snapshot_ids(session: Session) -> list[tuple[int, int]]:
    rows = (
        session.query(
            HistoricalOddsSnapshot.id,
            HistoricalOddsSnapshot.match_id,
            HistoricalOddsSnapshot.snapshot_time,
            Match.kickoff_time,
        )
        .join(Match, HistoricalOddsSnapshot.match_id == Match.id)
        .all()
    )
    live_rows = []
    for snapshot_id, match_id, snapshot_time, kickoff_time in rows:
        if _snapshot_as_utc(snapshot_time) > _kickoff_as_utc(kickoff_time):
            live_rows.append((snapshot_id, match_id))
    return live_rows


def _snapshot_as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC_TIMEZONE)
    return value.astimezone(UTC_TIMEZONE)


def _kickoff_as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=BEIJING_TIMEZONE)
    return value.astimezone(UTC_TIMEZONE)

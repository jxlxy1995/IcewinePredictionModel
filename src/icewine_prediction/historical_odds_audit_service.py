from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from icewine_prediction.models import HistoricalOddsSnapshot, Match

BEIJING_TIMEZONE = ZoneInfo("Asia/Shanghai")
UTC_TIMEZONE = ZoneInfo("UTC")


@dataclass(frozen=True)
class LiveHistoricalOddsAuditReport:
    match_count: int
    snapshot_count: int


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

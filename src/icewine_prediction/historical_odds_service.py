from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from icewine_prediction.models import HistoricalOddsSnapshot, Match
from icewine_prediction.sources.oddspapi_odds_mapper import MappedHistoricalOddsSnapshot


@dataclass(frozen=True)
class HistoricalOddsSnapshotInput:
    match_id: int
    source_name: str
    source_fixture_id: str
    bookmaker: str
    market_type: str
    market_id: str
    market_name: str
    market_line: Decimal
    outcome_side: str
    odds: Decimal
    snapshot_time: datetime
    period: str
    raw_payload: str | None = None


@dataclass(frozen=True)
class HistoricalOddsStoreResult:
    inserted_count: int
    skipped_duplicate_count: int


@dataclass(frozen=True)
class HistoricalOddsCoverageReport:
    match_count: int
    snapshot_count: int
    asian_handicap_count: int
    total_goals_count: int


def store_historical_odds_snapshots(
    session: Session,
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
) -> HistoricalOddsStoreResult:
    inserted = 0
    skipped = 0
    seen_keys = set()
    for snapshot in snapshots:
        snapshot_key = _snapshot_unique_key(snapshot)
        if snapshot_key in seen_keys:
            skipped += 1
            continue
        existing = (
            session.query(HistoricalOddsSnapshot)
            .filter_by(
                match_id=snapshot.match_id,
                source_name=snapshot.source_name,
                bookmaker=snapshot.bookmaker,
                market_type=snapshot.market_type,
                market_id=snapshot.market_id,
                outcome_side=snapshot.outcome_side,
                snapshot_time=snapshot.snapshot_time,
            )
            .one_or_none()
        )
        if existing is not None:
            skipped += 1
            continue
        seen_keys.add(snapshot_key)
        session.add(
            HistoricalOddsSnapshot(
                match_id=snapshot.match_id,
                source_name=snapshot.source_name,
                source_fixture_id=snapshot.source_fixture_id,
                bookmaker=snapshot.bookmaker,
                market_type=snapshot.market_type,
                market_id=snapshot.market_id,
                market_name=snapshot.market_name,
                market_line=snapshot.market_line,
                outcome_side=snapshot.outcome_side,
                odds=snapshot.odds,
                snapshot_time=snapshot.snapshot_time,
                period=snapshot.period,
                raw_payload=snapshot.raw_payload,
            )
        )
        inserted += 1
    session.commit()
    return HistoricalOddsStoreResult(
        inserted_count=inserted,
        skipped_duplicate_count=skipped,
    )


def _snapshot_unique_key(
    snapshot: HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot,
) -> tuple:
    return (
        snapshot.match_id,
        snapshot.source_name,
        snapshot.bookmaker,
        snapshot.market_type,
        snapshot.market_id,
        snapshot.outcome_side,
        snapshot.snapshot_time,
    )


def build_historical_odds_coverage_report(
    session: Session,
    season: int | None = None,
) -> HistoricalOddsCoverageReport:
    query = session.query(HistoricalOddsSnapshot)
    if season is not None:
        query = query.join(Match).filter(Match.season == season)

    match_count = query.with_entities(
        func.count(func.distinct(HistoricalOddsSnapshot.match_id))
    ).scalar()
    snapshot_count = query.with_entities(func.count(HistoricalOddsSnapshot.id)).scalar()
    asian_handicap_count = (
        query.filter(HistoricalOddsSnapshot.market_type == "asian_handicap")
        .with_entities(func.count(HistoricalOddsSnapshot.id))
        .scalar()
    )
    total_goals_count = (
        query.filter(HistoricalOddsSnapshot.market_type == "total_goals")
        .with_entities(func.count(HistoricalOddsSnapshot.id))
        .scalar()
    )
    return HistoricalOddsCoverageReport(
        match_count=match_count or 0,
        snapshot_count=snapshot_count or 0,
        asian_handicap_count=asian_handicap_count or 0,
        total_goals_count=total_goals_count or 0,
    )

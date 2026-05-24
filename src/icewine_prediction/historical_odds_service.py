from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

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


def sample_historical_odds_snapshots(
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
    max_snapshots_per_match: int = 200,
    kickoff_time: datetime | None = None,
    max_snapshots_per_market_type: int | None = None,
) -> list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot]:
    if kickoff_time is not None:
        snapshots = _filter_snapshots_before_kickoff(snapshots, kickoff_time)
    if max_snapshots_per_market_type is not None:
        snapshots = _sample_snapshots_by_market_type(snapshots, max_snapshots_per_market_type)
        if len(snapshots) <= max_snapshots_per_match:
            return snapshots
        return _sample_snapshot_group(snapshots, max_snapshots_per_match)
    if len(snapshots) <= max_snapshots_per_match:
        return sorted(snapshots, key=lambda snapshot: snapshot.snapshot_time)
    grouped = {}
    for snapshot in snapshots:
        key = (
            snapshot.bookmaker,
            snapshot.market_type,
            snapshot.market_id,
            snapshot.outcome_side,
        )
        grouped.setdefault(key, []).append(snapshot)
    group_count = len(grouped)
    if group_count == 0:
        return []
    per_group_limit = max(1, max_snapshots_per_match // group_count)
    sampled = []
    for group_snapshots in grouped.values():
        sampled.extend(_sample_snapshot_group(group_snapshots, per_group_limit))
    sampled = sorted(sampled, key=lambda snapshot: snapshot.snapshot_time)
    if len(sampled) <= max_snapshots_per_match:
        return sampled
    return _sample_snapshot_group(sampled, max_snapshots_per_match)


def _sample_snapshot_group(
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
    limit: int,
) -> list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot]:
    sorted_snapshots = sorted(snapshots, key=lambda snapshot: snapshot.snapshot_time)
    if limit <= 0:
        return []
    if len(sorted_snapshots) <= limit:
        return sorted_snapshots
    if limit == 1:
        return [sorted_snapshots[-1]]
    last_index = len(sorted_snapshots) - 1
    indexes = {
        round(index * last_index / (limit - 1))
        for index in range(limit)
    }
    return [sorted_snapshots[index] for index in sorted(indexes)]


def _filter_snapshots_before_kickoff(
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
    kickoff_time: datetime,
) -> list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot]:
    kickoff_time = _as_utc(kickoff_time)
    window_start = kickoff_time - timedelta(hours=24)
    return [
        snapshot
        for snapshot in snapshots
        if window_start <= _as_utc(snapshot.snapshot_time) <= kickoff_time
    ]


def _sample_snapshots_by_market_type(
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
    max_snapshots_per_market_type: int,
) -> list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot]:
    grouped = {}
    for snapshot in snapshots:
        grouped.setdefault(snapshot.market_type, []).append(snapshot)
    sampled = []
    for group_snapshots in grouped.values():
        sampled.extend(
            _sample_market_type_pairs(group_snapshots, max_snapshots_per_market_type)
        )
    return sorted(sampled, key=lambda snapshot: snapshot.snapshot_time)


def _sample_market_type_pairs(
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
    limit: int,
) -> list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot]:
    pair_groups = {}
    for snapshot in snapshots:
        key = (
            snapshot.bookmaker,
            snapshot.market_type,
            snapshot.market_line,
            snapshot.snapshot_time,
        )
        pair_groups.setdefault(key, []).append(snapshot)
    complete_pairs = [
        sorted(group, key=lambda snapshot: snapshot.outcome_side)
        for group in pair_groups.values()
        if len({snapshot.outcome_side for snapshot in group}) >= 2
    ]
    complete_pairs = sorted(
        complete_pairs,
        key=lambda group: group[0].snapshot_time,
    )
    if not complete_pairs:
        return _sample_snapshot_group(snapshots, limit)
    pair_limit = max(1, limit // 2)
    sampled_pairs = _sample_pair_group(complete_pairs, pair_limit)
    sampled = []
    for pair in sampled_pairs:
        sampled.extend(pair[:2])
    return sampled


def _sample_pair_group(
    pairs: list[list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot]],
    limit: int,
) -> list[list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot]]:
    if limit <= 0:
        return []
    if len(pairs) <= limit:
        return pairs
    if limit == 1:
        return [pairs[-1]]
    last_index = len(pairs) - 1
    indexes = {
        round(index * last_index / (limit - 1))
        for index in range(limit)
    }
    return [pairs[index] for index in sorted(indexes)]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=ZoneInfo("Asia/Shanghai")).astimezone(ZoneInfo("UTC"))
    return value.astimezone(ZoneInfo("UTC"))


def store_historical_odds_snapshots(
    session: Session,
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
    max_snapshots_per_match: int = 200,
    kickoff_time: datetime | None = None,
    max_snapshots_per_market_type: int | None = None,
) -> HistoricalOddsStoreResult:
    snapshots = sample_historical_odds_snapshots(
        snapshots,
        max_snapshots_per_match=max_snapshots_per_match,
        kickoff_time=kickoff_time,
        max_snapshots_per_market_type=max_snapshots_per_market_type,
    )
    return _store_sampled_historical_odds_snapshots(session, snapshots)


def _store_sampled_historical_odds_snapshots(
    session: Session,
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
) -> HistoricalOddsStoreResult:
    inserted = 0
    skipped = 0
    seen_keys = set()
    existing_keys = _load_existing_snapshot_keys(session, snapshots)
    for snapshot in snapshots:
        snapshot_key = _snapshot_unique_key(snapshot)
        if snapshot_key in seen_keys:
            skipped += 1
            continue
        if snapshot_key in existing_keys:
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


def _load_existing_snapshot_keys(
    session: Session,
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
) -> set[tuple]:
    if not snapshots:
        return set()
    match_ids = {snapshot.match_id for snapshot in snapshots}
    source_names = {snapshot.source_name for snapshot in snapshots}
    rows = (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id.in_(match_ids))
        .filter(HistoricalOddsSnapshot.source_name.in_(source_names))
        .all()
    )
    return {_snapshot_unique_key(row) for row in rows}


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

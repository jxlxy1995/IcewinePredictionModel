from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import math
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from icewine_prediction.models import HistoricalOddsRawSnapshot, HistoricalOddsSnapshot, Match
from icewine_prediction.sources.oddspapi_odds_mapper import MappedHistoricalOddsSnapshot
from icewine_prediction.execution_timepoint_service import select_execution_timepoint_pair
from icewine_prediction.historical_training_sample_service import _pair_market_snapshots

REQUIRED_ODDSPAPI_MARKET_TYPES = ("asian_handicap", "total_goals", "match_winner")


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
    match_winner_count: int


@dataclass(frozen=True)
class HistoricalOddsMarketCoverage:
    total_finished_matches: int
    complete_count: int
    blank_count: int
    missing_asian_handicap_count: int
    missing_total_goals_count: int
    missing_match_winner_count: int
    status_by_match_id: dict[int, str]


@dataclass(frozen=True)
class HistoricalOddsSupplementResult:
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot]
    added_group_count: int
    added_snapshot_count: int


@dataclass(frozen=True)
class HistoricalOddsRawSupplementReport:
    scanned_match_count: int
    skipped_no_raw_count: int
    supplemented_match_count: int
    added_group_count: int
    added_snapshot_count: int


DEFAULT_EXECUTION_SNAPSHOT_TARGETS = (60, 30, 25, 20, 15, 10)
STANDARD_SNAPSHOT_TARGET_MARKET_TYPES = (
    "asian_handicap",
    "total_goals",
    "match_winner",
)
BEIJING_TIMEZONE = ZoneInfo("Asia/Shanghai")


def sample_historical_odds_snapshots(
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
    max_snapshots_per_match: int = 200,
    kickoff_time: datetime | None = None,
    max_snapshots_per_market_type: int | None = None,
) -> list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot]:
    if kickoff_time is not None:
        snapshots = _filter_snapshots_before_kickoff(snapshots, kickoff_time)
    if max_snapshots_per_market_type is not None:
        snapshots = _filter_complete_market_groups(snapshots)
        snapshots = _sample_snapshots_by_market_type(snapshots, max_snapshots_per_market_type)
        if len(snapshots) <= max_snapshots_per_match:
            return snapshots
        return _sample_complete_groups(snapshots, max_snapshots_per_match)
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


def _sample_complete_groups(
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
    limit: int,
) -> list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot]:
    if limit <= 0:
        return []
    grouped = {}
    for snapshot in snapshots:
        key = (
            snapshot.bookmaker,
            snapshot.market_type,
            snapshot.snapshot_time,
            snapshot.market_line,
        )
        grouped.setdefault(key, []).append(snapshot)
    complete_groups = [
        sorted(group, key=_snapshot_group_sort_key)
        for group in grouped.values()
        if _complete_snapshots_in_time_group(group)
    ]
    complete_groups = sorted(
        complete_groups,
        key=lambda group: (
            group[0].snapshot_time,
            group[0].market_type,
            group[0].market_line,
        ),
    )
    if not complete_groups:
        return []
    selected = _take_groups_up_to_limit(
        _sample_pair_group(complete_groups, len(complete_groups)),
        limit,
    )
    if selected:
        return selected
    largest_group_size = max(len(group) for group in complete_groups)
    sampled_group_count = max(1, limit // largest_group_size)
    return _take_groups_up_to_limit(
        _sample_pair_group(complete_groups, sampled_group_count),
        limit,
    )


def _take_groups_up_to_limit(
    groups: list[list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot]],
    limit: int,
) -> list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot]:
    selected = []
    for group in groups:
        if len(selected) + len(group) > limit:
            continue
        selected.extend(group)
    return selected


def sample_oddspapi_training_snapshots(
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
    kickoff_time: datetime,
    max_snapshots_per_match: int | None = None,
    target_snapshots_per_market_type: int = 50,
    fallback_window_hours: int = 4,
    fallback_min_snapshots: int = 30,
) -> list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot]:
    primary_window_candidates = _filter_complete_market_groups(
        _filter_snapshots_before_kickoff(snapshots, kickoff_time)
    )
    primary_target_snapshot_count = _target_snapshot_count_for_market_types(
        primary_window_candidates,
        target_snapshots_per_market_type,
    )
    if max_snapshots_per_match is not None and max_snapshots_per_match < fallback_min_snapshots:
        return sample_historical_odds_snapshots(
            primary_window_candidates,
            max_snapshots_per_match=max_snapshots_per_match,
        )
    primary = sample_historical_odds_snapshots(
        snapshots,
        max_snapshots_per_match=primary_target_snapshot_count,
        kickoff_time=kickoff_time,
        max_snapshots_per_market_type=target_snapshots_per_market_type,
    )
    if len(primary) >= primary_target_snapshot_count or (
        len(primary) >= primary_target_snapshot_count - _max_required_side_count(primary)
        and _has_all_candidate_market_types(primary, primary_window_candidates)
    ):
        return primary
    kickoff_utc = _as_utc(kickoff_time)
    fallback_start = kickoff_utc - timedelta(hours=fallback_window_hours)
    fallback_candidates = [
        snapshot
        for snapshot in snapshots
        if fallback_start <= _as_utc(snapshot.snapshot_time) <= kickoff_utc
    ]
    fallback_candidates = _filter_complete_market_groups(fallback_candidates)
    fallback = _sample_complete_groups(fallback_candidates, fallback_min_snapshots)
    if fallback:
        return fallback
    if primary and _has_all_candidate_market_types(primary, primary_window_candidates):
        return primary
    return fallback


def _has_all_candidate_market_types(
    sampled: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
    candidates: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
) -> bool:
    candidate_market_types = {snapshot.market_type for snapshot in candidates}
    if not candidate_market_types:
        return False
    sampled_market_types = {snapshot.market_type for snapshot in sampled}
    return candidate_market_types.issubset(sampled_market_types)


def _max_required_side_count(
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
) -> int:
    if not snapshots:
        return 0
    return max(_required_side_count(snapshot.market_type) for snapshot in snapshots)


def _target_snapshot_count_for_market_types(
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
    target_snapshots_per_market_type: int,
) -> int:
    market_types = {snapshot.market_type for snapshot in snapshots}
    if not market_types:
        return target_snapshots_per_market_type
    return sum(
        max(1, math.ceil(target_snapshots_per_market_type / _required_side_count(market_type)))
        * _required_side_count(market_type)
        for market_type in market_types
    )


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


def _filter_complete_market_groups(
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
) -> list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot]:
    grouped = {}
    for snapshot in snapshots:
        key = (
            snapshot.bookmaker,
            snapshot.market_type,
            snapshot.snapshot_time,
        )
        grouped.setdefault(key, []).append(snapshot)

    complete_snapshots = []
    for group in grouped.values():
        complete_snapshots.extend(_complete_snapshots_in_time_group(group))
    return sorted(
        complete_snapshots,
        key=lambda snapshot: (
            snapshot.snapshot_time,
            snapshot.bookmaker,
            snapshot.market_type,
            snapshot.market_line,
            snapshot.outcome_side,
        ),
    )


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
    time_groups = _complete_time_groups(snapshots)
    if time_groups:
        sampled_time_groups = _sample_pair_group(time_groups, _time_group_limit(time_groups, limit))
        sampled = []
        for group in sampled_time_groups:
            sampled.extend(group)
        return sampled

    pair_groups = {}
    for snapshot in snapshots:
        key = (
            snapshot.bookmaker,
            snapshot.market_type,
            snapshot.market_line,
            snapshot.snapshot_time,
        )
        pair_groups.setdefault(key, []).append(snapshot)
    required_side_count = _required_side_count(snapshots[0].market_type if snapshots else "")
    complete_pairs = [
        sorted(group, key=lambda snapshot: snapshot.outcome_side)
        for group in pair_groups.values()
        if len({snapshot.outcome_side for snapshot in group}) >= required_side_count
    ]
    complete_pairs = sorted(
        complete_pairs,
        key=lambda group: group[0].snapshot_time,
    )
    if not complete_pairs:
        return []
    pair_limit = max(1, math.ceil(limit / required_side_count))
    sampled_pairs = _sample_pair_group(complete_pairs, pair_limit)
    sampled = []
    for pair in sampled_pairs:
        sampled.extend(pair[:required_side_count])
    return sampled


def _complete_time_groups(
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
) -> list[list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot]]:
    grouped = {}
    for snapshot in snapshots:
        key = (
            snapshot.bookmaker,
            snapshot.market_type,
            snapshot.snapshot_time,
        )
        grouped.setdefault(key, []).append(snapshot)
    groups = []
    for group in grouped.values():
        complete_group = _complete_snapshots_in_time_group(group)
        if complete_group:
            groups.append(sorted(complete_group, key=_snapshot_group_sort_key))
    return sorted(groups, key=lambda group: group[0].snapshot_time)


def _complete_snapshots_in_time_group(
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
) -> list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot]:
    if not snapshots:
        return []
    market_type = snapshots[0].market_type
    required_sides = _required_sides(market_type)
    sides_by_line = {}
    for snapshot in snapshots:
        sides_by_line.setdefault(snapshot.market_line, {})[snapshot.outcome_side] = snapshot

    complete_snapshots = []
    for line_snapshots in sides_by_line.values():
        if not required_sides.issubset(line_snapshots):
            continue
        complete_snapshots.extend(
            line_snapshots[side]
            for side in _side_order(market_type)
            if side in line_snapshots
        )
    return complete_snapshots


def _snapshot_group_sort_key(
    snapshot: HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot,
) -> tuple:
    return (
        snapshot.market_line,
        snapshot.outcome_side,
    )


def _time_group_limit(
    groups: list[list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot]],
    limit: int,
) -> int:
    if not groups:
        return 0
    group_size = max(1, len(groups[0]))
    return max(1, math.ceil(limit / group_size))


def _required_side_count(market_type: str) -> int:
    if market_type == "match_winner":
        return 3
    return 2


def _required_sides(market_type: str) -> set[str]:
    if market_type == "match_winner":
        return {"home", "draw", "away"}
    if market_type == "total_goals":
        return {"over", "under"}
    return {"home", "away"}


def _side_order(market_type: str) -> tuple[str, ...]:
    if market_type == "match_winner":
        return ("home", "draw", "away")
    if market_type == "total_goals":
        return ("over", "under")
    return ("home", "away")


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
    use_oddspapi_training_sampler: bool = False,
    oddspapi_target_snapshots_per_market_type: int = 50,
    execution_timepoint_source_snapshots: list[
        HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot
    ] | None = None,
) -> HistoricalOddsStoreResult:
    if use_oddspapi_training_sampler and kickoff_time is not None:
        snapshots = sample_oddspapi_training_snapshots(
            snapshots,
            kickoff_time=kickoff_time,
            max_snapshots_per_match=max_snapshots_per_match,
            target_snapshots_per_market_type=oddspapi_target_snapshots_per_market_type,
        )
    else:
        snapshots = sample_historical_odds_snapshots(
            snapshots,
            max_snapshots_per_match=max_snapshots_per_match,
            kickoff_time=kickoff_time,
            max_snapshots_per_market_type=max_snapshots_per_market_type,
        )
    if kickoff_time is not None and execution_timepoint_source_snapshots is not None:
        snapshots = supplement_execution_timepoint_snapshots(
            snapshots,
            source_snapshots=execution_timepoint_source_snapshots,
            kickoff_time=kickoff_time,
        ).snapshots
    return _store_sampled_historical_odds_snapshots(session, snapshots)


def store_historical_odds_raw_snapshots(
    session: Session,
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
    max_snapshots_per_match: int = 450,
    kickoff_time: datetime | None = None,
    max_snapshots_per_market_type: int | None = 150,
) -> HistoricalOddsStoreResult:
    snapshots = sample_historical_odds_snapshots(
        snapshots,
        max_snapshots_per_match=max_snapshots_per_match,
        kickoff_time=kickoff_time,
        max_snapshots_per_market_type=max_snapshots_per_market_type,
    )
    return _store_sampled_odds_snapshot_rows(session, snapshots, HistoricalOddsRawSnapshot)


def supplement_execution_timepoint_snapshots(
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
    *,
    source_snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
    kickoff_time: datetime,
    target_minutes_before_kickoff: tuple[int, ...] = DEFAULT_EXECUTION_SNAPSHOT_TARGETS,
    market_types: tuple[str, ...] = STANDARD_SNAPSHOT_TARGET_MARKET_TYPES,
) -> HistoricalOddsSupplementResult:
    existing = [_snapshot_input_from_row(snapshot) for snapshot in snapshots]
    source_snapshots = [_snapshot_input_from_row(snapshot) for snapshot in source_snapshots]
    selected = list(existing)
    added_group_count = 0
    added_snapshot_count = 0
    selected_keys = {_snapshot_unique_key(snapshot) for snapshot in selected}
    source_by_pair_key = _snapshots_by_pair_key(source_snapshots)

    for market_type in market_types:
        for target in target_minutes_before_kickoff:
            existing_pair = _select_execution_pair(existing, market_type, kickoff_time, target)
            if existing_pair is not None:
                continue
            source_pair = _select_execution_pair(source_snapshots, market_type, kickoff_time, target)
            if source_pair is None:
                continue
            pair_snapshots = source_by_pair_key.get(
                (
                    source_pair.snapshot_time,
                    source_pair.bookmaker,
                    source_pair.market_type,
                    source_pair.market_line,
                ),
                [],
            )
            added = [
                snapshot
                for snapshot in pair_snapshots
                if _snapshot_unique_key(snapshot) not in selected_keys
            ]
            if not added:
                continue
            selected.extend(added)
            existing.extend(added)
            selected_keys.update(_snapshot_unique_key(snapshot) for snapshot in added)
            added_group_count += 1
            added_snapshot_count += len(added)

    return HistoricalOddsSupplementResult(
        snapshots=sorted(
            selected,
            key=lambda snapshot: (
                _snapshot_unique_time(snapshot.snapshot_time),
                snapshot.bookmaker,
                snapshot.market_type,
                snapshot.market_line,
                snapshot.outcome_side,
            ),
        ),
        added_group_count=added_group_count,
        added_snapshot_count=added_snapshot_count,
    )


def supplement_historical_odds_snapshots_from_raw(
    session: Session,
    *,
    match_ids: set[int] | None = None,
    source_name: str = "oddspapi",
    bookmaker: str = "pinnacle",
    target_minutes_before_kickoff: tuple[int, ...] = DEFAULT_EXECUTION_SNAPSHOT_TARGETS,
) -> HistoricalOddsRawSupplementReport:
    if match_ids is not None and not match_ids:
        return HistoricalOddsRawSupplementReport(0, 0, 0, 0, 0)
    if match_ids is None:
        query = (
            session.query(Match)
            .join(HistoricalOddsRawSnapshot, HistoricalOddsRawSnapshot.match_id == Match.id)
            .filter(HistoricalOddsRawSnapshot.source_name == source_name)
            .filter(HistoricalOddsRawSnapshot.bookmaker == bookmaker)
            .distinct()
        )
    else:
        query = session.query(Match).filter(Match.id.in_(match_ids))
    query = query.order_by(Match.kickoff_time.asc(), Match.id.asc())

    scanned = 0
    skipped_no_raw = 0
    supplemented = 0
    added_groups = 0
    added_snapshots = 0
    for match in query.all():
        scanned += 1
        raw_snapshots = _load_raw_snapshot_inputs(
            session,
            match.id,
            source_name=source_name,
            bookmaker=bookmaker,
        )
        if not raw_snapshots:
            skipped_no_raw += 1
            continue
        existing_snapshots = _load_snapshot_inputs(
            session,
            match.id,
            source_name=source_name,
            bookmaker=bookmaker,
        )
        kickoff_time = match_snapshot_timeline_kickoff_time(match)
        main_raw_snapshots = _build_dynamic_main_market_snapshots(
            raw_snapshots,
            kickoff_time=kickoff_time,
        )
        result = supplement_execution_timepoint_snapshots(
            existing_snapshots,
            source_snapshots=main_raw_snapshots,
            kickoff_time=kickoff_time,
            target_minutes_before_kickoff=target_minutes_before_kickoff,
        )
        candidate_keys = {_snapshot_unique_key(snapshot) for snapshot in existing_snapshots}
        to_store = [
            snapshot
            for snapshot in result.snapshots
            if _snapshot_unique_key(snapshot) not in candidate_keys
        ]
        if not to_store:
            continue
        store_result = _store_sampled_historical_odds_snapshots(session, to_store)
        if store_result.inserted_count > 0:
            supplemented += 1
            added_groups += result.added_group_count
            added_snapshots += store_result.inserted_count

    return HistoricalOddsRawSupplementReport(
        scanned_match_count=scanned,
        skipped_no_raw_count=skipped_no_raw,
        supplemented_match_count=supplemented,
        added_group_count=added_groups,
        added_snapshot_count=added_snapshots,
    )


def match_snapshot_timeline_kickoff_time(match: Match) -> datetime:
    if match.fixture_timestamp is not None:
        return datetime.fromtimestamp(match.fixture_timestamp, timezone.utc)
    kickoff_time = match.kickoff_time
    if kickoff_time.tzinfo is None:
        return kickoff_time.replace(tzinfo=BEIJING_TIMEZONE).astimezone(timezone.utc)
    return kickoff_time.astimezone(timezone.utc)


def _store_sampled_historical_odds_snapshots(
    session: Session,
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
) -> HistoricalOddsStoreResult:
    return _store_sampled_odds_snapshot_rows(session, snapshots, HistoricalOddsSnapshot)


def _select_execution_pair(
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
    market_type: str,
    kickoff_time: datetime,
    target_minutes_before_kickoff: int,
):
    pairs = _pair_market_snapshots(
        [
            _snapshot_input_from_row(snapshot)
            for snapshot in snapshots
            if snapshot.market_type == market_type
        ],
        market_type=market_type,
    )
    return select_execution_timepoint_pair(
        pairs,
        kickoff_time=kickoff_time,
        target_minutes_before_kickoff=target_minutes_before_kickoff,
    )


def _snapshots_by_pair_key(
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
) -> dict[tuple[datetime, str, str, Decimal], list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot]]:
    grouped = {}
    for snapshot in snapshots:
        key = (
            snapshot.snapshot_time,
            snapshot.bookmaker,
            snapshot.market_type,
            snapshot.market_line,
        )
        grouped.setdefault(key, []).append(snapshot)
    return grouped


def _build_dynamic_main_market_snapshots(
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
    *,
    kickoff_time: datetime,
) -> list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot]:
    from icewine_prediction.dynamic_main_market_service import (
        build_dynamic_main_market_snapshots,
    )

    return build_dynamic_main_market_snapshots(snapshots, kickoff_time=kickoff_time)


def _load_snapshot_inputs(
    session: Session,
    match_id: int,
    *,
    source_name: str,
    bookmaker: str,
) -> list[HistoricalOddsSnapshotInput]:
    return [
        _snapshot_input_from_row(row)
        for row in session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id == match_id)
        .filter(HistoricalOddsSnapshot.source_name == source_name)
        .filter(HistoricalOddsSnapshot.bookmaker == bookmaker)
        .order_by(HistoricalOddsSnapshot.snapshot_time.asc())
        .all()
    ]


def _load_raw_snapshot_inputs(
    session: Session,
    match_id: int,
    *,
    source_name: str,
    bookmaker: str,
) -> list[HistoricalOddsSnapshotInput]:
    return [
        _snapshot_input_from_row(row)
        for row in session.query(HistoricalOddsRawSnapshot)
        .filter(HistoricalOddsRawSnapshot.match_id == match_id)
        .filter(HistoricalOddsRawSnapshot.source_name == source_name)
        .filter(HistoricalOddsRawSnapshot.bookmaker == bookmaker)
        .order_by(HistoricalOddsRawSnapshot.snapshot_time.asc())
        .all()
    ]


def _snapshot_input_from_row(
    snapshot,
) -> HistoricalOddsSnapshotInput:
    if isinstance(snapshot, HistoricalOddsSnapshotInput):
        if snapshot.snapshot_time.tzinfo is None:
            return snapshot
        return HistoricalOddsSnapshotInput(
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
            snapshot_time=snapshot.snapshot_time.astimezone(timezone.utc).replace(tzinfo=None),
            period=snapshot.period,
            raw_payload=snapshot.raw_payload,
        )
    snapshot_time = snapshot.snapshot_time
    if snapshot_time.tzinfo is not None:
        snapshot_time = snapshot_time.astimezone(timezone.utc).replace(tzinfo=None)
    return HistoricalOddsSnapshotInput(
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
        snapshot_time=snapshot_time,
        period=snapshot.period,
        raw_payload=snapshot.raw_payload,
    )


def _store_sampled_odds_snapshot_rows(
    session: Session,
    snapshots: list[HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot],
    model_class,
) -> HistoricalOddsStoreResult:
    inserted = 0
    skipped = 0
    seen_keys = set()
    existing_keys = _load_existing_snapshot_keys(session, snapshots, model_class)
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
            model_class(
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
    model_class=HistoricalOddsSnapshot,
) -> set[tuple]:
    if not snapshots:
        return set()
    match_ids = {snapshot.match_id for snapshot in snapshots}
    source_names = {snapshot.source_name for snapshot in snapshots}
    rows = (
        session.query(model_class)
        .filter(model_class.match_id.in_(match_ids))
        .filter(model_class.source_name.in_(source_names))
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
        Decimal(snapshot.market_line).quantize(Decimal("0.01")),
        snapshot.outcome_side,
        _snapshot_unique_time(snapshot.snapshot_time),
    )


def _snapshot_unique_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


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
    match_winner_count = (
        query.filter(HistoricalOddsSnapshot.market_type == "match_winner")
        .with_entities(func.count(HistoricalOddsSnapshot.id))
        .scalar()
    )
    return HistoricalOddsCoverageReport(
        match_count=match_count or 0,
        snapshot_count=snapshot_count or 0,
        asian_handicap_count=asian_handicap_count or 0,
        total_goals_count=total_goals_count or 0,
        match_winner_count=match_winner_count or 0,
    )


def build_historical_odds_market_coverage(
    session: Session,
    season: int | None = None,
) -> HistoricalOddsMarketCoverage:
    match_query = session.query(Match).filter(Match.status == "finished")
    if season is not None:
        match_query = match_query.filter(Match.season == season)
    matches = match_query.all()
    market_rows = (
        session.query(HistoricalOddsSnapshot.match_id, HistoricalOddsSnapshot.market_type)
        .filter(HistoricalOddsSnapshot.match_id.in_([match.id for match in matches]))
        .distinct()
        .all()
    )
    market_types_by_match_id: dict[int, set[str]] = {}
    for match_id, market_type in market_rows:
        market_types_by_match_id.setdefault(match_id, set()).add(market_type)

    status_by_match_id = {
        match.id: _classify_match_market_coverage(
            market_types_by_match_id.get(match.id, set())
        )
        for match in matches
    }
    return HistoricalOddsMarketCoverage(
        total_finished_matches=len(matches),
        complete_count=sum(1 for status in status_by_match_id.values() if status == "complete"),
        blank_count=sum(1 for status in status_by_match_id.values() if status == "blank"),
        missing_asian_handicap_count=sum(
            1
            for markets in (market_types_by_match_id.get(match.id, set()) for match in matches)
            if "asian_handicap" not in markets
        ),
        missing_total_goals_count=sum(
            1
            for markets in (market_types_by_match_id.get(match.id, set()) for match in matches)
            if "total_goals" not in markets
        ),
        missing_match_winner_count=sum(
            1
            for markets in (market_types_by_match_id.get(match.id, set()) for match in matches)
            if "match_winner" not in markets
        ),
        status_by_match_id=status_by_match_id,
    )


def _classify_match_market_coverage(market_types: set[str]) -> str:
    present = set(market_types)
    if not present:
        return "blank"
    missing = [market_type for market_type in REQUIRED_ODDSPAPI_MARKET_TYPES if market_type not in present]
    if not missing:
        return "complete"
    if len(missing) == 1:
        return f"missing_{missing[0]}"
    return "missing_multiple_markets"

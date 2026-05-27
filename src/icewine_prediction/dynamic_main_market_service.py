from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.historical_odds_service import HistoricalOddsSnapshotInput
from icewine_prediction.sources.oddspapi_odds_mapper import MappedHistoricalOddsSnapshot

BEIJING_TIMEZONE = ZoneInfo("Asia/Shanghai")
UTC_TIMEZONE = ZoneInfo("UTC")

Snapshot = HistoricalOddsSnapshotInput | MappedHistoricalOddsSnapshot


@dataclass(frozen=True)
class DynamicMarketSummary:
    bookmaker: str
    market_type: str
    opening_line: Decimal
    closing_line: Decimal
    min_line: Decimal
    max_line: Decimal
    line_change: Decimal
    line_move_count: int
    snapshot_pair_count: int


def build_dynamic_main_market_snapshots(
    snapshots: list[Snapshot],
    kickoff_time: datetime,
) -> list[Snapshot]:
    filtered = _filter_pre_kickoff_window(snapshots, kickoff_time)
    grouped = {}
    for snapshot in filtered:
        key = (snapshot.bookmaker, snapshot.market_type)
        grouped.setdefault(key, []).append(snapshot)

    selected = []
    for group in grouped.values():
        selected.extend(_build_market_timeline(group))
    return sorted(
        selected,
        key=lambda item: (
            _as_utc(item.snapshot_time),
            item.bookmaker,
            item.market_type,
            item.outcome_side,
        ),
    )


def build_dynamic_neighbor_market_snapshots(
    snapshots: list[Snapshot],
    kickoff_time: datetime,
) -> list[Snapshot]:
    filtered = _filter_pre_kickoff_window(snapshots, kickoff_time)
    grouped = {}
    for snapshot in filtered:
        key = (snapshot.bookmaker, snapshot.market_type)
        grouped.setdefault(key, []).append(snapshot)

    selected = []
    for group in grouped.values():
        if group and group[0].market_type == "match_winner":
            selected.extend(_build_match_winner_timeline(group))
        else:
            selected.extend(_build_neighbor_market_timeline(group))
    return sorted(
        selected,
        key=lambda item: (
            _as_utc(item.snapshot_time),
            item.bookmaker,
            item.market_type,
            item.market_line,
            item.outcome_side,
        ),
    )


def _build_market_timeline(snapshots: list[Snapshot]) -> list[Snapshot]:
    if snapshots and snapshots[0].market_type == "match_winner":
        return _build_match_winner_timeline(snapshots)
    latest_by_line_and_side = {}
    selected = []
    for snapshot_time, time_snapshots in _group_snapshots_by_time(snapshots):
        for snapshot in time_snapshots:
            latest_by_line_and_side[(snapshot.market_line, snapshot.outcome_side)] = snapshot
        selected_pair = _select_balanced_pair(list(latest_by_line_and_side.values()))
        selected.extend(_copy_pair_to_time(selected_pair, snapshot_time))
    return selected


def _build_neighbor_market_timeline(snapshots: list[Snapshot]) -> list[Snapshot]:
    latest_by_line_and_side = {}
    selected = []
    for snapshot_time, time_snapshots in _group_snapshots_by_time(snapshots):
        for snapshot in time_snapshots:
            latest_by_line_and_side[(snapshot.market_line, snapshot.outcome_side)] = snapshot
        selected_lines = _select_balanced_line_with_neighbors(
            list(latest_by_line_and_side.values())
        )
        for line in selected_lines:
            selected.extend(
                _copy_pair_to_time(
                    _complete_pair_for_line(list(latest_by_line_and_side.values()), line),
                    snapshot_time,
                )
            )
    return selected


def _build_match_winner_timeline(snapshots: list[Snapshot]) -> list[Snapshot]:
    latest_by_side = {}
    selected = []
    for snapshot_time, time_snapshots in _group_snapshots_by_time(snapshots):
        for snapshot in time_snapshots:
            latest_by_side[snapshot.outcome_side] = snapshot
        if {"home", "draw", "away"}.issubset(latest_by_side):
            selected.extend(
                _copy_pair_to_time(
                    [
                        latest_by_side["home"],
                        latest_by_side["draw"],
                        latest_by_side["away"],
                    ],
                    snapshot_time,
                )
            )
    return selected


def _select_balanced_line_with_neighbors(snapshots: list[Snapshot]) -> list[Decimal]:
    by_line = _complete_pairs_by_line(snapshots)
    if not by_line:
        return []
    main_line = min(by_line.values(), key=_pair_score)[0].market_line
    sorted_lines = sorted(by_line)
    main_index = sorted_lines.index(main_line)
    start_index = max(0, main_index - 1)
    end_index = min(len(sorted_lines), main_index + 2)
    return sorted_lines[start_index:end_index]


def _complete_pair_for_line(snapshots: list[Snapshot], line: Decimal) -> list[Snapshot]:
    return list(_complete_pairs_by_line(snapshots).get(line, ()))


def _group_snapshots_by_time(snapshots: list[Snapshot]) -> list[tuple[datetime, list[Snapshot]]]:
    grouped = {}
    for snapshot in snapshots:
        grouped.setdefault(_as_utc(snapshot.snapshot_time), []).append(snapshot)
    return sorted(grouped.items(), key=lambda item: item[0])


def _copy_pair_to_time(pair: list[Snapshot], snapshot_time: datetime) -> list[Snapshot]:
    return [
        _copy_snapshot_with_time(snapshot, snapshot_time)
        for snapshot in pair
    ]


def _copy_snapshot_with_time(snapshot: Snapshot, snapshot_time: datetime) -> Snapshot:
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


def summarize_dynamic_main_markets(
    snapshots: list[Snapshot],
) -> dict[tuple[str, str], DynamicMarketSummary]:
    paired_lines = {}
    for snapshot in sorted(snapshots, key=lambda item: _as_utc(item.snapshot_time)):
        key = (snapshot.bookmaker, snapshot.market_type, _as_utc(snapshot.snapshot_time))
        paired_lines.setdefault(key, snapshot.market_line)

    lines_by_market = {}
    for (bookmaker, market_type, _), line in paired_lines.items():
        lines_by_market.setdefault((bookmaker, market_type), []).append(line)

    summaries = {}
    for key, lines in lines_by_market.items():
        bookmaker, market_type = key
        move_count = sum(
            1
            for index in range(1, len(lines))
            if lines[index] != lines[index - 1]
        )
        summaries[key] = DynamicMarketSummary(
            bookmaker=bookmaker,
            market_type=market_type,
            opening_line=lines[0],
            closing_line=lines[-1],
            min_line=min(lines),
            max_line=max(lines),
            line_change=lines[-1] - lines[0],
            line_move_count=move_count,
            snapshot_pair_count=len(lines),
        )
    return summaries


def _filter_pre_kickoff_window(
    snapshots: list[Snapshot],
    kickoff_time: datetime,
) -> list[Snapshot]:
    kickoff_utc = _as_utc(kickoff_time, default_timezone=BEIJING_TIMEZONE)
    start_utc = kickoff_utc - timedelta(hours=24)
    return [
        snapshot
        for snapshot in snapshots
        if start_utc
        <= _as_utc(snapshot.snapshot_time, default_timezone=UTC_TIMEZONE)
        <= kickoff_utc
    ]


def _select_balanced_pair(snapshots: list[Snapshot]) -> list[Snapshot]:
    candidates = list(_complete_pairs_by_line(snapshots).values())
    if not candidates:
        return []
    first, second = min(candidates, key=_pair_score)
    return [first, second]


def _complete_pairs_by_line(snapshots: list[Snapshot]) -> dict[Decimal, tuple[Snapshot, Snapshot]]:
    by_line = {}
    for snapshot in snapshots:
        by_line.setdefault(snapshot.market_line, {})[snapshot.outcome_side] = snapshot

    pairs = {}
    market_type = snapshots[0].market_type if snapshots else ""
    for line, sides in by_line.items():
        first_side, second_side = _required_sides(market_type)
        if first_side not in sides or second_side not in sides:
            continue
        pairs[line] = (sides[first_side], sides[second_side])
    return pairs


def _required_sides(market_type: str) -> tuple[str, str]:
    if market_type == "asian_handicap":
        return "home", "away"
    return "over", "under"


def _pair_score(pair: tuple[Snapshot, Snapshot]) -> tuple[Decimal, Decimal, Decimal]:
    first, second = pair
    odds_gap = abs(first.odds - second.odds)
    average_gap = abs(((first.odds + second.odds) / Decimal("2")) - Decimal("2"))
    if first.market_type == "asian_handicap":
        line_gap = abs(first.market_line)
    else:
        line_gap = abs(first.market_line - Decimal("2.5"))
    return odds_gap, average_gap, line_gap


def _as_utc(value: datetime, default_timezone: ZoneInfo = UTC_TIMEZONE) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=default_timezone)
    return value.astimezone(UTC_TIMEZONE)

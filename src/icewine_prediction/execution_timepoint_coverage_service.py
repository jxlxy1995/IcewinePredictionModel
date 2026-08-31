from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from icewine_prediction.historical_training_sample_service import (
    _pair_market_snapshots,
)
from icewine_prediction.models import HistoricalOddsSnapshot, Match
from icewine_prediction.odds_provider_selection_service import TRUSTED_SNAPSHOT_PRIORITY
from icewine_prediction.execution_timepoint_service import select_execution_timepoint_pair


DEFAULT_EXECUTION_TIMEPOINT_TARGETS = (60, 30, 25, 20, 15, 10)
STANDARD_EXECUTION_TIMEPOINT_MARKETS = (
    "asian_handicap",
    "total_goals",
    "match_winner",
)
CORE_EXECUTION_TIMEPOINT_MARKETS = (
    "asian_handicap",
    "total_goals",
)


@dataclass(frozen=True)
class StandardExecutionTimepointCell:
    market_type: str
    target_minutes: int
    selected_pair: object | None

    @property
    def available(self) -> bool:
        return self.selected_pair is not None

    @property
    def source_name(self) -> str | None:
        return getattr(self.selected_pair, "source_name", None)


@dataclass(frozen=True)
class StandardExecutionTimepointCoverage:
    cells: tuple[StandardExecutionTimepointCell, ...]
    available_count: int
    total_count: int
    missing_cells: tuple[tuple[str, int], ...]
    core_available_count: int
    core_total_count: int
    core_complete: bool
    core_missing_cells: tuple[tuple[str, int], ...]

    def selected_source(self, market_type: str, target_minutes: int) -> str | None:
        for cell in self.cells:
            if cell.market_type == market_type and cell.target_minutes == target_minutes:
                return cell.source_name
        raise KeyError((market_type, target_minutes))

    def cell(self, market_type: str, target_minutes: int) -> StandardExecutionTimepointCell:
        for cell in self.cells:
            if cell.market_type == market_type and cell.target_minutes == target_minutes:
                return cell
        raise KeyError((market_type, target_minutes))


def get_standard_execution_timepoint_coverage(
    session,
    match_id: int,
) -> StandardExecutionTimepointCoverage | None:
    match = session.query(Match).filter(Match.id == match_id).one_or_none()
    if match is None:
        return None
    source_names = tuple(source_name for source_name, _bookmaker in TRUSTED_SNAPSHOT_PRIORITY)
    bookmakers = tuple(bookmaker for _source_name, bookmaker in TRUSTED_SNAPSHOT_PRIORITY)
    snapshots = (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id == match_id)
        .filter(HistoricalOddsSnapshot.source_name.in_(source_names))
        .filter(HistoricalOddsSnapshot.bookmaker.in_(bookmakers))
        .all()
    )
    from icewine_prediction.historical_odds_service import match_snapshot_timeline_kickoff_time

    return evaluate_standard_execution_timepoint_coverage(
        snapshots,
        kickoff_time=match_snapshot_timeline_kickoff_time(match),
    )


def has_complete_standard_execution_timepoint_coverage(
    session,
    match_id: int,
) -> bool:
    coverage = get_standard_execution_timepoint_coverage(session, match_id)
    return coverage is not None and coverage.core_complete


has_complete_core_execution_timepoint_coverage = has_complete_standard_execution_timepoint_coverage


def evaluate_standard_execution_timepoint_coverage(
    snapshots: Iterable[object],
    *,
    kickoff_time: datetime,
    target_minutes: tuple[int, ...] = DEFAULT_EXECUTION_TIMEPOINT_TARGETS,
    market_types: tuple[str, ...] = STANDARD_EXECUTION_TIMEPOINT_MARKETS,
) -> StandardExecutionTimepointCoverage:
    snapshots = list(snapshots)
    cells: list[StandardExecutionTimepointCell] = []
    missing_cells: list[tuple[str, int]] = []

    for market_type in market_types:
        pairs = _pair_market_snapshots(
            [snapshot for snapshot in snapshots if snapshot.market_type == market_type],
            market_type=market_type,
        )
        for target in target_minutes:
            selected = _select_priority_execution_timepoint_pair(
                pairs,
                kickoff_time=kickoff_time,
                target_minutes_before_kickoff=target,
            )
            cell = StandardExecutionTimepointCell(
                market_type=market_type,
                target_minutes=target,
                selected_pair=selected,
            )
            cells.append(cell)
            if selected is None:
                missing_cells.append((market_type, target))

    total_count = len(cells)
    core_cells = [cell for cell in cells if cell.market_type in CORE_EXECUTION_TIMEPOINT_MARKETS]
    core_missing_cells = tuple(
        (cell.market_type, cell.target_minutes)
        for cell in core_cells
        if not cell.available
    )
    core_total_count = len(core_cells)
    return StandardExecutionTimepointCoverage(
        cells=tuple(cells),
        available_count=total_count - len(missing_cells),
        total_count=total_count,
        missing_cells=tuple(missing_cells),
        core_available_count=core_total_count - len(core_missing_cells),
        core_total_count=core_total_count,
        core_complete=core_total_count > 0 and not core_missing_cells,
        core_missing_cells=core_missing_cells,
    )


def _select_priority_execution_timepoint_pair(
    pairs: list[object],
    *,
    kickoff_time: datetime,
    target_minutes_before_kickoff: int,
) -> object | None:
    for source_name, bookmaker in TRUSTED_SNAPSHOT_PRIORITY:
        selected = select_execution_timepoint_pair(
            [
                pair
                for pair in pairs
                if pair.source_name == source_name and pair.bookmaker.lower() == bookmaker
            ],
            kickoff_time=kickoff_time,
            target_minutes_before_kickoff=target_minutes_before_kickoff,
        )
        if selected is not None:
            return selected
    return None

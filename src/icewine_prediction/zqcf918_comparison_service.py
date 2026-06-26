from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from icewine_prediction.models import HistoricalOddsSnapshot
from icewine_prediction.odds_provider_selection_service import (
    PINNACLE_BOOKMAKER,
    THE_ODDS_API_SOURCE_NAME,
    ZQCF918_SOURCE_NAME,
)


@dataclass(frozen=True)
class ZQCF918ComparisonRow:
    match_id: int
    source_name: str
    market_type: str
    market_line: Decimal
    outcome_side: str
    snapshot_time: str
    trusted_odds: Decimal
    zqcf918_odds: Decimal
    absolute_diff: Decimal


@dataclass(frozen=True)
class ZQCF918ComparisonReport:
    match_count: int
    compared_group_count: int
    rows: list[ZQCF918ComparisonRow]


def compare_zqcf918_to_trusted_source(
    session: Session,
    *,
    match_ids: list[int],
    trusted_source_name: str = THE_ODDS_API_SOURCE_NAME,
) -> ZQCF918ComparisonReport:
    if not match_ids:
        return ZQCF918ComparisonReport(match_count=0, compared_group_count=0, rows=[])

    snapshots = (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id.in_(match_ids))
        .filter(HistoricalOddsSnapshot.bookmaker == PINNACLE_BOOKMAKER)
        .filter(HistoricalOddsSnapshot.source_name.in_([trusted_source_name, ZQCF918_SOURCE_NAME]))
        .all()
    )
    by_key: dict[tuple[int, str, Decimal, str, str], dict[str, HistoricalOddsSnapshot]] = {}
    for snapshot in snapshots:
        key = (
            snapshot.match_id,
            snapshot.market_type,
            snapshot.market_line,
            snapshot.outcome_side,
            snapshot.snapshot_time.isoformat(),
        )
        by_key.setdefault(key, {})[snapshot.source_name] = snapshot

    rows: list[ZQCF918ComparisonRow] = []
    for _, grouped_snapshots in sorted(by_key.items(), key=lambda item: _comparison_sort_key(item[0])):
        trusted = grouped_snapshots.get(trusted_source_name)
        zqcf918 = grouped_snapshots.get(ZQCF918_SOURCE_NAME)
        if trusted is None or zqcf918 is None:
            continue
        rows.append(
            ZQCF918ComparisonRow(
                match_id=trusted.match_id,
                source_name=trusted.source_name,
                market_type=trusted.market_type,
                market_line=trusted.market_line,
                outcome_side=trusted.outcome_side,
                snapshot_time=trusted.snapshot_time.isoformat(),
                trusted_odds=trusted.odds,
                zqcf918_odds=zqcf918.odds,
                absolute_diff=abs(trusted.odds - zqcf918.odds),
            )
        )

    return ZQCF918ComparisonReport(
        match_count=len({row.match_id for row in rows}),
        compared_group_count=len(rows),
        rows=rows,
    )


def _comparison_sort_key(key: tuple[int, str, Decimal, str, str]) -> tuple[int, str, Decimal, int, str]:
    match_id, market_type, market_line, outcome_side, snapshot_time = key
    side_order = {"home": 0, "draw": 1, "away": 2, "over": 3, "under": 4}
    return (match_id, market_type, market_line, side_order.get(outcome_side, 99), snapshot_time)

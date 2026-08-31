from datetime import datetime, timedelta
from decimal import Decimal

from icewine_prediction.execution_timepoint_coverage_service import (
    evaluate_standard_execution_timepoint_coverage,
)
from icewine_prediction.models import HistoricalOddsSnapshot


KICKOFF = datetime(2026, 9, 1, 12, 0)


def test_evaluate_standard_execution_timepoint_coverage_counts_all_eighteen_cells():
    snapshots = _snapshots_for_source("oddspapi", targets=(60, 30, 25, 20, 15, 10))

    coverage = evaluate_standard_execution_timepoint_coverage(snapshots, kickoff_time=KICKOFF)

    assert coverage.available_count == 18
    assert coverage.total_count == 18
    assert coverage.core_available_count == 12
    assert coverage.core_total_count == 12
    assert coverage.core_complete is True
    assert coverage.missing_cells == ()


def test_evaluate_standard_execution_timepoint_coverage_reports_missing_cells():
    snapshots = _snapshots_for_source("the_odds_api", targets=(60, 30, 25, 20, 15))

    coverage = evaluate_standard_execution_timepoint_coverage(snapshots, kickoff_time=KICKOFF)

    assert coverage.available_count == 15
    assert coverage.total_count == 18
    assert coverage.core_available_count == 10
    assert coverage.core_total_count == 12
    assert coverage.core_complete is False
    assert set(coverage.missing_cells) == {
        ("asian_handicap", 10),
        ("total_goals", 10),
        ("match_winner", 10),
    }


def test_evaluate_standard_execution_timepoint_coverage_selects_sources_per_cell_in_priority_order():
    oddspapi = _snapshots_for_source("oddspapi", targets=(60,))
    the_odds_api = _snapshots_for_source("the_odds_api", targets=(30,))
    zqcf918 = _snapshots_for_source("zqcf918", targets=(25,))

    coverage = evaluate_standard_execution_timepoint_coverage(
        oddspapi + the_odds_api + zqcf918,
        kickoff_time=KICKOFF,
    )

    assert coverage.selected_source("asian_handicap", 60) == "oddspapi"
    assert coverage.selected_source("asian_handicap", 30) == "the_odds_api"
    assert coverage.selected_source("asian_handicap", 25) == "zqcf918"


def test_evaluate_standard_execution_timepoint_coverage_allows_optional_match_winner_gaps():
    snapshots = _snapshots_for_source(
        "oddspapi",
        targets=(60, 30, 25, 20, 15, 10),
        market_types=("asian_handicap", "total_goals"),
    )

    coverage = evaluate_standard_execution_timepoint_coverage(snapshots, kickoff_time=KICKOFF)

    assert coverage.core_complete is True
    assert coverage.available_count == 12
    assert coverage.total_count == 18
    assert len(coverage.missing_cells) == 6


def _snapshots_for_source(
    source_name: str,
    *,
    targets: tuple[int, ...],
    market_types: tuple[str, ...] = ("asian_handicap", "total_goals", "match_winner"),
) -> list[HistoricalOddsSnapshot]:
    snapshots = []
    markets = {
        "asian_handicap": (("home", "away"), Decimal("-0.25")),
        "total_goals": (("over", "under"), Decimal("2.50")),
        "match_winner": (("home", "draw", "away"), Decimal("0.00")),
    }
    for target in targets:
        snapshot_time = KICKOFF - timedelta(minutes=target)
        for market_type, (sides, line) in markets.items():
            if market_type not in market_types:
                continue
            for side in sides:
                snapshots.append(
                    HistoricalOddsSnapshot(
                        match_id=1,
                        source_name=source_name,
                        source_fixture_id=f"{source_name}-fixture",
                        bookmaker="pinnacle",
                        market_type=market_type,
                        market_id=f"{source_name}-{market_type}-{target}-{side}",
                        market_name=market_type,
                        market_line=line,
                        outcome_side=side,
                        odds=Decimal("1.90"),
                        snapshot_time=snapshot_time,
                        period="fulltime",
                    )
                )
    return snapshots

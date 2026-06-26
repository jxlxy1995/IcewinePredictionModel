from datetime import datetime, timedelta
from decimal import Decimal

from icewine_prediction.execution_timepoint_service import select_execution_timepoint_pair
from icewine_prediction.historical_training_sample_service import _pair_market_snapshots
from icewine_prediction.models import HistoricalOddsSnapshot


def test_select_execution_timepoint_pair_uses_symmetric_tolerance_after_target():
    kickoff_time = datetime(2026, 5, 31, 16, 30)
    snapshots = []
    for seconds_after_target, line, home_odds, away_odds in [
        (12, Decimal("-0.50"), Decimal("2.000"), Decimal("1.900")),
        (120, Decimal("-0.25"), Decimal("1.950"), Decimal("1.950")),
    ]:
        snapshot_time = kickoff_time - timedelta(minutes=30) + timedelta(seconds=seconds_after_target)
        snapshots.extend(
            [
                _snapshot(snapshot_time, line, "home", home_odds),
                _snapshot(snapshot_time, line, "away", away_odds),
            ]
        )

    selected = select_execution_timepoint_pair(
        _pair_market_snapshots(snapshots, market_type="asian_handicap"),
        kickoff_time=kickoff_time,
        target_minutes_before_kickoff=30,
    )

    assert selected is not None
    assert selected.snapshot_time == kickoff_time - timedelta(minutes=30) + timedelta(seconds=12)
    assert selected.market_line == Decimal("-0.50")


def test_select_execution_timepoint_pair_uses_wider_tolerance_for_sbobet():
    kickoff_time = datetime(2026, 5, 31, 16, 30)
    snapshot_time = kickoff_time - timedelta(minutes=36, seconds=24)
    snapshots = [
        _snapshot(snapshot_time, Decimal("0.00"), "home", Decimal("1.900"), bookmaker="sbobet"),
        _snapshot(snapshot_time, Decimal("0.00"), "away", Decimal("1.900"), bookmaker="sbobet"),
    ]

    selected = select_execution_timepoint_pair(
        _pair_market_snapshots(snapshots, market_type="asian_handicap"),
        kickoff_time=kickoff_time,
        target_minutes_before_kickoff=30,
    )

    assert selected is not None
    assert selected.snapshot_time == snapshot_time


def test_select_execution_timepoint_pair_keeps_default_tolerance_for_pinnacle():
    kickoff_time = datetime(2026, 5, 31, 16, 30)
    snapshot_time = kickoff_time - timedelta(minutes=36, seconds=24)
    snapshots = [
        _snapshot(snapshot_time, Decimal("0.00"), "home", Decimal("1.900"), bookmaker="pinnacle"),
        _snapshot(snapshot_time, Decimal("0.00"), "away", Decimal("1.900"), bookmaker="pinnacle"),
    ]

    selected = select_execution_timepoint_pair(
        _pair_market_snapshots(snapshots, market_type="asian_handicap"),
        kickoff_time=kickoff_time,
        target_minutes_before_kickoff=30,
    )

    assert selected is None


def test_select_execution_timepoint_pair_uses_wider_tolerance_for_zqcf918_pinnacle():
    kickoff_time = datetime(2026, 6, 25, 19, 15)
    snapshot_time = kickoff_time - timedelta(minutes=52, seconds=29)
    snapshots = [
        _snapshot(
            snapshot_time,
            Decimal("1.00"),
            "home",
            Decimal("1.840"),
            source_name="zqcf918",
        ),
        _snapshot(
            snapshot_time,
            Decimal("1.00"),
            "away",
            Decimal("1.980"),
            source_name="zqcf918",
        ),
    ]

    selected = select_execution_timepoint_pair(
        _pair_market_snapshots(snapshots, market_type="asian_handicap"),
        kickoff_time=kickoff_time,
        target_minutes_before_kickoff=60,
    )

    assert selected is not None
    assert selected.snapshot_time == snapshot_time


def _snapshot(
    snapshot_time: datetime,
    line: Decimal,
    side: str,
    odds: Decimal,
    bookmaker: str = "pinnacle",
    source_name: str = "oddspapi",
) -> HistoricalOddsSnapshot:
    return HistoricalOddsSnapshot(
        match_id=1,
        source_name=source_name,
        source_fixture_id="fixture-1",
        bookmaker=bookmaker,
        market_type="asian_handicap",
        market_id=f"asian_handicap-{line}-{side}-{snapshot_time.timestamp()}",
        market_name="asian_handicap",
        market_line=line,
        outcome_side=side,
        odds=odds,
        snapshot_time=snapshot_time,
        period="fulltime",
    )

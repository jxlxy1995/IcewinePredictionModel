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


def _snapshot(
    snapshot_time: datetime,
    line: Decimal,
    side: str,
    odds: Decimal,
) -> HistoricalOddsSnapshot:
    return HistoricalOddsSnapshot(
        match_id=1,
        source_name="oddspapi",
        source_fixture_id="fixture-1",
        bookmaker="pinnacle",
        market_type="asian_handicap",
        market_id=f"asian_handicap-{line}-{side}-{snapshot_time.timestamp()}",
        market_name="asian_handicap",
        market_line=line,
        outcome_side=side,
        odds=odds,
        snapshot_time=snapshot_time,
        period="fulltime",
    )

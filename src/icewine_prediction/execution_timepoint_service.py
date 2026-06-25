from __future__ import annotations

from datetime import datetime, timedelta

from icewine_prediction.historical_training_sample_service import (
    _PairedMarketSnapshot,
    _comparable_datetime,
)


DEFAULT_EXECUTION_TIMEPOINT_TOLERANCE_MINUTES = 5
BOOKMAKER_EXECUTION_TIMEPOINT_TOLERANCE_MINUTES = {
    "sbobet": 10,
}


def select_execution_timepoint_pair(
    pairs: list[_PairedMarketSnapshot],
    *,
    kickoff_time: datetime,
    target_minutes_before_kickoff: int,
    tolerance_minutes: int = DEFAULT_EXECUTION_TIMEPOINT_TOLERANCE_MINUTES,
) -> _PairedMarketSnapshot | None:
    if pairs:
        tolerance_minutes = BOOKMAKER_EXECUTION_TIMEPOINT_TOLERANCE_MINUTES.get(
            pairs[0].bookmaker.lower(),
            tolerance_minutes,
        )
    kickoff = _comparable_datetime(kickoff_time)
    target_time = kickoff - timedelta(minutes=target_minutes_before_kickoff)
    tolerance = timedelta(minutes=tolerance_minutes)
    candidates = [
        pair
        for pair in pairs
        if abs(_comparable_datetime(pair.snapshot_time) - target_time) < tolerance
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda pair: (
            abs((_comparable_datetime(pair.snapshot_time) - target_time).total_seconds()),
            pair.balance_gap,
        ),
    )

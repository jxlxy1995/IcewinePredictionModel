from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from icewine_prediction.baseline_recommendation_sandbox_service import SandboxCandidate
from icewine_prediction.baseline_t15_signal_comparison_service import (
    T15SignalComparisonCandidateSet,
    _candidate_set_summary,
    _match_snapshot_timeline_kickoff_time,
    _select_t15_pair,
)
from icewine_prediction.historical_training_sample_service import _pair_market_snapshots
from icewine_prediction.models import HistoricalOddsSnapshot, Match


UTC = ZoneInfo("UTC")


def test_select_t15_pair_uses_closest_snapshot_inside_ten_minute_window():
    kickoff_time = datetime(2026, 5, 20, 20, 0, tzinfo=UTC)
    snapshots = []
    for minutes, line, home_odds, away_odds in [
        (21, Decimal("-0.25"), Decimal("1.91"), Decimal("1.93")),
        (18, Decimal("-0.50"), Decimal("1.92"), Decimal("1.92")),
        (12, Decimal("-0.75"), Decimal("1.95"), Decimal("1.89")),
        (9, Decimal("-1.00"), Decimal("2.00"), Decimal("1.84")),
    ]:
        snapshots.extend(
            [
                _snapshot(kickoff_time, minutes, line, "home", home_odds),
                _snapshot(kickoff_time, minutes, line, "away", away_odds),
            ]
        )

    selected = _select_t15_pair(
        _pair_market_snapshots(snapshots, market_type="asian_handicap"),
        kickoff_time=kickoff_time,
    )

    assert selected is not None
    assert selected.snapshot_time == kickoff_time - timedelta(minutes=18)
    assert selected.market_line == Decimal("-0.50")


def test_select_t15_pair_accepts_snapshot_after_target_inside_tolerance():
    kickoff_time = datetime(2026, 5, 20, 20, 0, tzinfo=UTC)
    snapshots = []
    for minutes, line, home_odds, away_odds in [
        (16, Decimal("-0.25"), Decimal("1.91"), Decimal("1.93")),
        (14, Decimal("-0.50"), Decimal("1.92"), Decimal("1.92")),
    ]:
        snapshots.extend(
            [
                _snapshot(kickoff_time, minutes, line, "home", home_odds),
                _snapshot(kickoff_time, minutes, line, "away", away_odds),
            ]
        )

    selected = _select_t15_pair(
        _pair_market_snapshots(snapshots, market_type="asian_handicap"),
        kickoff_time=kickoff_time,
    )

    assert selected is not None
    assert selected.snapshot_time == kickoff_time - timedelta(minutes=14)
    assert selected.market_line == Decimal("-0.50")


def test_candidate_set_summary_compares_close_and_t15_candidates():
    close_candidates = [
        _candidate("1", "asian_away_cover_hgb_edge_v1", "asian_handicap", "away_cover", "2.10", True),
        _candidate("2", "asian_away_cover_hgb_edge_v1", "asian_handicap", "away_cover", "1.90", False),
    ]
    t15_candidates = [
        _candidate("1", "asian_away_cover_hgb_edge_v1", "asian_handicap", "away_cover", "2.00", True),
        _candidate("3", "asian_away_cover_hgb_edge_v1", "asian_handicap", "away_cover", "1.80", True),
    ]

    summary = _candidate_set_summary(
        T15SignalComparisonCandidateSet(
            strategy_key="asian_away_cover_hgb_edge_v1",
            display_name="Away cover",
            close_candidates=close_candidates,
            t15_candidates=t15_candidates,
        )
    )

    assert summary.close_count == 2
    assert summary.t15_count == 2
    assert summary.overlap_count == 1
    assert summary.close_only_count == 1
    assert summary.t15_only_count == 1
    assert summary.close_profit == Decimal("0.1000")
    assert summary.t15_profit == Decimal("1.8000")
    assert summary.close_roi == Decimal("0.0500")
    assert summary.t15_roi == Decimal("0.9000")


def test_match_snapshot_timeline_kickoff_time_prefers_fixture_timestamp_utc():
    match = Match(
        kickoff_time=datetime(2026, 5, 3, 23, 15, tzinfo=UTC),
        fixture_timestamp=1777821300,
    )

    kickoff_time = _match_snapshot_timeline_kickoff_time(match)

    assert kickoff_time == datetime(2026, 5, 3, 15, 15)


def _snapshot(
    kickoff_time: datetime,
    minutes_before: int,
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
        market_id=f"asian_handicap-{line}-{minutes_before}",
        market_name="asian_handicap",
        market_line=line,
        outcome_side=side,
        odds=odds,
        snapshot_time=kickoff_time - timedelta(minutes=minutes_before),
        period="fulltime",
    )


def _candidate(
    match_id: str,
    strategy_key: str,
    market_type: str,
    side: str,
    odds: str,
    won: bool,
) -> SandboxCandidate:
    return SandboxCandidate(
        match_id=match_id,
        kickoff_time="2026-05-20T20:00:00+00:00",
        league_name="League",
        home_team_name="Home",
        away_team_name="Away",
        market_type=market_type,
        line=Decimal("-0.50"),
        side=side,
        odds=Decimal(odds),
        model_probability=Decimal("0.6000"),
        market_probability=Decimal("0.5000"),
        edge=Decimal("0.1000"),
        actual_side=side if won else "home_cover",
        profit=(Decimal(odds) - Decimal("1")) if won else Decimal("-1"),
    )

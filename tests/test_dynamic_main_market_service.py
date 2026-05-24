from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.dynamic_main_market_service import (
    build_dynamic_main_market_snapshots,
    summarize_dynamic_main_markets,
)
from icewine_prediction.historical_odds_service import HistoricalOddsSnapshotInput


def _snapshot(bookmaker, market_type, market_id, line, side, odds, minutes_before):
    kickoff = datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    return HistoricalOddsSnapshotInput(
        match_id=1,
        source_name="oddspapi",
        source_fixture_id="fixture-1",
        bookmaker=bookmaker,
        market_type=market_type,
        market_id=market_id,
        market_name="market",
        market_line=Decimal(str(line)),
        outcome_side=side,
        odds=Decimal(str(odds)),
        snapshot_time=kickoff.astimezone(ZoneInfo("UTC")) - timedelta(minutes=minutes_before),
        period="fulltime",
    )


def test_dynamic_main_market_selects_balanced_line_per_time_and_bookmaker():
    snapshots = [
        _snapshot("pinnacle", "total_goals", "m25", "2.5", "over", "1.55", 60),
        _snapshot("pinnacle", "total_goals", "m25", "2.5", "under", "2.45", 60),
        _snapshot("pinnacle", "total_goals", "m275", "2.75", "over", "1.92", 60),
        _snapshot("pinnacle", "total_goals", "m275", "2.75", "under", "1.98", 60),
        _snapshot("sbobet", "total_goals", "s25", "2.5", "over", "1.88", 60),
        _snapshot("sbobet", "total_goals", "s25", "2.5", "under", "1.90", 60),
    ]

    selected = build_dynamic_main_market_snapshots(
        snapshots,
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert [(item.bookmaker, item.market_id, item.outcome_side) for item in selected] == [
        ("pinnacle", "m275", "over"),
        ("pinnacle", "m275", "under"),
        ("sbobet", "s25", "over"),
        ("sbobet", "s25", "under"),
    ]


def test_dynamic_main_market_keeps_line_migration_before_kickoff_only():
    kickoff = datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    snapshots = [
        _snapshot("pinnacle", "total_goals", "m25", "2.5", "over", "1.92", 120),
        _snapshot("pinnacle", "total_goals", "m25", "2.5", "under", "1.94", 120),
        _snapshot("pinnacle", "total_goals", "m30", "3.0", "over", "1.91", 10),
        _snapshot("pinnacle", "total_goals", "m30", "3.0", "under", "1.93", 10),
        _snapshot("pinnacle", "total_goals", "live", "3.25", "over", "1.90", -1),
        _snapshot("pinnacle", "total_goals", "live", "3.25", "under", "1.92", -1),
    ]

    selected = build_dynamic_main_market_snapshots(snapshots, kickoff_time=kickoff)
    summary = summarize_dynamic_main_markets(selected)

    assert [item.market_line for item in selected if item.outcome_side == "over"] == [
        Decimal("2.5"),
        Decimal("3.0"),
    ]
    assert summary[("pinnacle", "total_goals")].opening_line == Decimal("2.5")
    assert summary[("pinnacle", "total_goals")].closing_line == Decimal("3.0")
    assert summary[("pinnacle", "total_goals")].line_change == Decimal("0.5")
    assert summary[("pinnacle", "total_goals")].line_move_count == 1

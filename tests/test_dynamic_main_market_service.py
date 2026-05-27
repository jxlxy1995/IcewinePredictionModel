from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.dynamic_main_market_service import (
    build_dynamic_main_market_snapshots,
    build_dynamic_neighbor_market_snapshots,
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


def test_dynamic_neighbor_market_keeps_main_line_and_adjacent_lines():
    snapshots = [
        _snapshot("pinnacle", "total_goals", "m25", "2.5", "over", "1.40", 60),
        _snapshot("pinnacle", "total_goals", "m25", "2.5", "under", "2.90", 60),
        _snapshot("pinnacle", "total_goals", "m275", "2.75", "over", "1.94", 60),
        _snapshot("pinnacle", "total_goals", "m275", "2.75", "under", "1.96", 60),
        _snapshot("pinnacle", "total_goals", "m30", "3.0", "over", "2.35", 60),
        _snapshot("pinnacle", "total_goals", "m30", "3.0", "under", "1.62", 60),
        _snapshot("pinnacle", "total_goals", "m325", "3.25", "over", "2.80", 60),
        _snapshot("pinnacle", "total_goals", "m325", "3.25", "under", "1.44", 60),
    ]

    selected = build_dynamic_neighbor_market_snapshots(
        snapshots,
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert [(item.market_line, item.outcome_side) for item in selected] == [
        (Decimal("2.5"), "over"),
        (Decimal("2.5"), "under"),
        (Decimal("2.75"), "over"),
        (Decimal("2.75"), "under"),
        (Decimal("3.0"), "over"),
        (Decimal("3.0"), "under"),
    ]


def test_dynamic_main_market_keeps_line_migration_before_kickoff_only():
    kickoff = datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    snapshots = [
        _snapshot("pinnacle", "total_goals", "m25", "2.5", "over", "1.92", 120),
        _snapshot("pinnacle", "total_goals", "m25", "2.5", "under", "1.94", 120),
        _snapshot("pinnacle", "total_goals", "m30", "3.0", "over", "1.99", 10),
        _snapshot("pinnacle", "total_goals", "m30", "3.0", "under", "2.00", 10),
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


def test_dynamic_main_market_uses_latest_known_pair_when_outcomes_update_at_different_times():
    kickoff = datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    snapshots = [
        _snapshot("pinnacle", "asian_handicap", "draw", "0", "home", "1.95", 120),
        _snapshot("pinnacle", "asian_handicap", "draw", "0", "away", "1.95", 120),
        _snapshot("pinnacle", "asian_handicap", "wide", "1.25", "home", "1.25", 60),
        _snapshot("pinnacle", "asian_handicap", "wide", "1.25", "away", "4.20", 60),
    ]

    selected = build_dynamic_main_market_snapshots(snapshots, kickoff_time=kickoff)

    latest_time = kickoff.astimezone(ZoneInfo("UTC")) - timedelta(minutes=60)
    latest_selected = [item for item in selected if item.snapshot_time == latest_time]
    assert [(item.market_id, item.outcome_side, item.odds) for item in latest_selected] == [
        ("draw", "away", Decimal("1.95")),
        ("draw", "home", Decimal("1.95")),
    ]


def test_dynamic_neighbor_market_uses_complete_pair_from_latest_known_snapshot_time():
    kickoff = datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    snapshots = [
        _snapshot("pinnacle", "total_goals", "m30", "3.0", "over", "1.91", 120),
        _snapshot("pinnacle", "total_goals", "m30", "3.0", "under", "1.99", 120),
        _snapshot("pinnacle", "total_goals", "m325", "3.25", "over", "1.94", 120),
        _snapshot("pinnacle", "total_goals", "m325", "3.25", "under", "1.96", 120),
        _snapshot("pinnacle", "total_goals", "m35", "3.5", "over", "2.20", 120),
        _snapshot("pinnacle", "total_goals", "m35", "3.5", "under", "1.72", 120),
        _snapshot("pinnacle", "total_goals", "m325", "3.25", "over", "2.01", 60),
    ]

    selected = build_dynamic_neighbor_market_snapshots(snapshots, kickoff_time=kickoff)

    latest_time = kickoff.astimezone(ZoneInfo("UTC")) - timedelta(minutes=60)
    latest_selected = [item for item in selected if item.snapshot_time == latest_time]
    sides_by_line = {}
    for item in latest_selected:
        sides_by_line.setdefault(item.market_line, set()).add(item.outcome_side)
    assert all(sides == {"over", "under"} for sides in sides_by_line.values())

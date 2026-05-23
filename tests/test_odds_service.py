from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.match_service import create_match
from icewine_prediction.odds_service import list_match_odds_snapshots, save_odds_snapshot


def test_same_match_can_store_multiple_odds_snapshots(session):
    match = create_match(
        session,
        league_name="英超",
        country_or_region="英格兰",
        home_team_name="阿森纳",
        away_team_name="切尔西",
        kickoff_time=datetime(2026, 5, 23, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    save_odds_snapshot(
        session,
        match.id,
        captured_at=datetime(2026, 5, 23, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        data_source="sample",
        bookmaker="sample_bookmaker",
        asian_handicap=Decimal("-0.25"),
        home_odds=Decimal("0.92"),
        away_odds=Decimal("0.96"),
        total_line=Decimal("2.50"),
        over_odds=Decimal("0.94"),
        under_odds=Decimal("0.94"),
    )
    save_odds_snapshot(
        session,
        match.id,
        captured_at=datetime(2026, 5, 23, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        data_source="sample",
        bookmaker="sample_bookmaker",
        asian_handicap=Decimal("-0.50"),
        home_odds=Decimal("0.88"),
        away_odds=Decimal("1.00"),
        total_line=Decimal("2.75"),
        over_odds=Decimal("0.90"),
        under_odds=Decimal("0.98"),
    )

    snapshots = list_match_odds_snapshots(session, match.id)

    assert len(snapshots) == 2
    assert snapshots[0].asian_handicap == Decimal("-0.25")
    assert snapshots[1].asian_handicap == Decimal("-0.50")

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, Team
from icewine_prediction.odds_provider_selection_service import (
    PINNACLE_BOOKMAKER,
    THE_ODDS_API_SOURCE_NAME,
    ZQCF918_SOURCE_NAME,
)
from icewine_prediction.zqcf918_comparison_service import compare_zqcf918_to_trusted_source


def test_compare_zqcf918_to_trusted_source_reports_market_differences(session):
    match = _add_match(session)
    session.add_all(
        [
            _snapshot(match.id, THE_ODDS_API_SOURCE_NAME, "asian_handicap", "home", Decimal("-0.50"), Decimal("1.900")),
            _snapshot(match.id, THE_ODDS_API_SOURCE_NAME, "asian_handicap", "away", Decimal("-0.50"), Decimal("1.950")),
            _snapshot(match.id, ZQCF918_SOURCE_NAME, "asian_handicap", "home", Decimal("-0.50"), Decimal("1.910")),
            _snapshot(match.id, ZQCF918_SOURCE_NAME, "asian_handicap", "away", Decimal("-0.50"), Decimal("1.940")),
        ]
    )
    session.commit()

    report = compare_zqcf918_to_trusted_source(session, match_ids=[match.id])

    assert report.match_count == 1
    assert report.compared_group_count == 2
    assert report.rows[0].match_id == match.id
    assert report.rows[0].source_name == THE_ODDS_API_SOURCE_NAME
    assert report.rows[0].zqcf918_odds == Decimal("1.910")
    assert report.rows[0].absolute_diff == Decimal("0.010")


def test_compare_zqcf918_to_trusted_source_ignores_unpaired_snapshots(session):
    match = _add_match(session)
    session.add_all(
        [
            _snapshot(match.id, THE_ODDS_API_SOURCE_NAME, "asian_handicap", "home", Decimal("-0.50"), Decimal("1.900")),
            _snapshot(match.id, ZQCF918_SOURCE_NAME, "asian_handicap", "away", Decimal("-0.50"), Decimal("1.940")),
        ]
    )
    session.commit()

    report = compare_zqcf918_to_trusted_source(session, match_ids=[match.id])

    assert report.match_count == 0
    assert report.compared_group_count == 0
    assert report.rows == []


def _add_match(session):
    league = League(name="J1 League", country_or_region="Japan", level=1)
    home = Team(canonical_name="Home")
    away = Team(canonical_name="Away")
    session.add_all([league, home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 6, 26, 12, 0, tzinfo=ZoneInfo("UTC")),
        season=2026,
        status="finished",
    )
    session.add(match)
    session.commit()
    return match


def _snapshot(match_id, source_name, market_type, side, line, odds):
    return HistoricalOddsSnapshot(
        match_id=match_id,
        source_name=source_name,
        source_fixture_id=f"{source_name}-{match_id}",
        bookmaker=PINNACLE_BOOKMAKER,
        market_type=market_type,
        market_id=f"{source_name}-{market_type}-{side}",
        market_name="Asian Handicap",
        market_line=line,
        outcome_side=side,
        odds=odds,
        snapshot_time=datetime(2026, 6, 26, 10, 0, tzinfo=ZoneInfo("UTC")),
        period="full_time",
    )

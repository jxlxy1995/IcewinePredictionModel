from datetime import datetime
from dataclasses import replace
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.historical_odds_service import (
    HistoricalOddsSnapshotInput,
    build_historical_odds_coverage_report,
    store_historical_odds_snapshots,
)
from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, Team


def _match(session):
    league = League(
        name="La Liga",
        country_or_region="Spain",
        level=1,
        source_name="api_football",
        source_league_id="140",
    )
    home_team = Team(canonical_name="Mallorca")
    away_team = Team(canonical_name="Oviedo")
    session.add_all([league, home_team, away_team])
    session.flush()
    match = Match(
        league=league,
        home_team=home_team,
        away_team=away_team,
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        season=2025,
        status="finished",
        source_name="api_football",
        source_match_id="1391195",
    )
    session.add(match)
    session.commit()
    return match


def _snapshot(match_id: int, odds: Decimal = Decimal("1.91")):
    return HistoricalOddsSnapshotInput(
        match_id=match_id,
        source_name="oddspapi",
        source_fixture_id="fixture-1",
        bookmaker="pinnacle",
        market_type="asian_handicap",
        market_id="1070",
        market_name="Asian Handicap",
        market_line=Decimal("-0.25"),
        outcome_side="home",
        odds=odds,
        snapshot_time=datetime(2026, 5, 23, 18, 0, tzinfo=ZoneInfo("UTC")),
        period="fulltime",
        raw_payload='{"sample": true}',
    )


def test_store_historical_odds_snapshots_inserts_once_for_same_unique_key(session):
    match = _match(session)
    first = _snapshot(match.id, odds=Decimal("1.91"))
    duplicate = _snapshot(match.id, odds=Decimal("1.95"))

    result = store_historical_odds_snapshots(session, [first, duplicate])

    saved = session.query(HistoricalOddsSnapshot).one()
    assert result.inserted_count == 1
    assert result.skipped_duplicate_count == 1
    assert saved.odds == Decimal("1.910")


def test_build_historical_odds_coverage_report_counts_matches_and_market_rows(session):
    match = _match(session)
    store_historical_odds_snapshots(
        session,
        [
            _snapshot(match.id),
            replace(
                _snapshot(match.id),
                market_type="total_goals",
                market_id="10170",
                market_name="Over Under Full Time",
                market_line=Decimal("2.25"),
                outcome_side="over",
                odds=Decimal("1.88"),
            ),
        ],
    )

    report = build_historical_odds_coverage_report(session, season=2025)

    assert report.match_count == 1
    assert report.snapshot_count == 2
    assert report.asian_handicap_count == 1
    assert report.total_goals_count == 1

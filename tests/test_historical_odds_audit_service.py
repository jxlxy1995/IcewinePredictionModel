from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.historical_odds_audit_service import (
    audit_live_historical_odds,
    clear_historical_odds_snapshots,
    delete_live_historical_odds,
)
from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, Team


def _match(session, kickoff_time=None):
    league = League(name="La Liga", country_or_region="Spain", level=1)
    home = Team(canonical_name="Mallorca")
    away = Team(canonical_name="Oviedo")
    session.add_all([league, home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff_time
        or datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        season=2025,
        status="finished",
        home_score=2,
        away_score=1,
    )
    session.add(match)
    session.commit()
    return match


def _snapshot(session, match, snapshot_time):
    session.add(
        HistoricalOddsSnapshot(
            match_id=match.id,
            source_name="oddspapi",
            source_fixture_id="fixture-1",
            bookmaker="pinnacle",
            market_type="total_goals",
            market_id="1010",
            market_name="Over Under Full Time",
            market_line=Decimal("2.50"),
            outcome_side="over",
            odds=Decimal("1.900"),
            snapshot_time=snapshot_time,
            period="fulltime",
        )
    )
    session.commit()


def test_audit_live_historical_odds_counts_only_after_kickoff(session):
    match = _match(session)
    kickoff_utc = match.kickoff_time.astimezone(ZoneInfo("UTC"))
    _snapshot(session, match, kickoff_utc - timedelta(minutes=1))
    _snapshot(session, match, kickoff_utc)
    _snapshot(session, match, kickoff_utc + timedelta(seconds=1))

    report = audit_live_historical_odds(session)

    assert report.snapshot_count == 1
    assert report.match_count == 1


def test_delete_live_historical_odds_removes_only_after_kickoff(session):
    match = _match(session)
    kickoff_utc = match.kickoff_time.astimezone(ZoneInfo("UTC"))
    _snapshot(session, match, kickoff_utc - timedelta(minutes=1))
    _snapshot(session, match, kickoff_utc + timedelta(seconds=1))

    deleted = delete_live_historical_odds(session)

    assert deleted == 1
    remaining = session.query(HistoricalOddsSnapshot).one()
    remaining_time = remaining.snapshot_time
    if remaining_time.tzinfo is None:
        remaining_time = remaining_time.replace(tzinfo=ZoneInfo("UTC"))
    assert remaining_time <= kickoff_utc


def test_clear_historical_odds_snapshots_deletes_source_snapshots_only(session):
    match = _match(session)
    _snapshot(session, match, datetime(2026, 5, 23, 18, 0, tzinfo=ZoneInfo("UTC")))
    session.add(
        HistoricalOddsSnapshot(
            match_id=match.id,
            source_name="api_football",
            source_fixture_id="fixture-2",
            bookmaker="pinnacle",
            market_type="total_goals",
            market_id="1010",
            market_name="Over Under Full Time",
            market_line=Decimal("2.50"),
            outcome_side="over",
            odds=Decimal("1.900"),
            snapshot_time=datetime(2026, 5, 23, 18, 0, tzinfo=ZoneInfo("UTC")),
            period="fulltime",
        )
    )
    session.commit()

    deleted = clear_historical_odds_snapshots(session, source_name="oddspapi")

    assert deleted == 1
    remaining = session.query(HistoricalOddsSnapshot).one()
    assert remaining.source_name == "api_football"

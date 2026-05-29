from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import League, Match, OddsSnapshot
from icewine_prediction.sources.api_football_mapper import ExternalFixture, ExternalOddsSnapshot
from icewine_prediction.sync_service import upsert_fixtures, upsert_odds_snapshots


def test_upsert_fixtures_does_not_duplicate_matches(session):
    fixture = ExternalFixture(
        source_name="api_football",
        source_match_id="1001",
        source_league_id="39",
        league_name="Premier League",
        country="England",
        home_source_team_id="50",
        home_team_name="Manchester City",
        home_team_logo_url="https://media.api-sports.io/football/teams/50.png",
        away_source_team_id="42",
        away_team_name="Arsenal",
        away_team_logo_url="https://media.api-sports.io/football/teams/42.png",
        kickoff_time=datetime(2026, 5, 23, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
        home_score=None,
        away_score=None,
        season=2025,
        league_logo_url="https://media.api-sports.io/football/leagues/39.png",
        league_flag_url="https://media.api-sports.io/flags/gb.svg",
        standings_supported=True,
        league_round="Regular Season - 38",
        referee="Example Referee",
        fixture_timezone="Asia/Shanghai",
        fixture_timestamp=1779554400,
        first_period_started_at=1779554400,
        second_period_started_at=None,
        venue_id=100,
        venue_name="Etihad Stadium",
        venue_city="Manchester",
        status_long="Not Started",
        status_short="NS",
        elapsed=None,
        extra=None,
        home_winner=None,
        away_winner=None,
        halftime_home_score=None,
        halftime_away_score=None,
        fulltime_home_score=None,
        fulltime_away_score=None,
        extratime_home_score=None,
        extratime_away_score=None,
        penalty_home_score=None,
        penalty_away_score=None,
    )

    first = upsert_fixtures(session, [fixture])
    second = upsert_fixtures(session, [fixture])

    assert first.created_matches == 1
    assert second.updated_matches == 1
    assert session.query(Match).count() == 1
    saved = session.query(Match).one()
    assert saved.season == 2025
    assert saved.league.logo_url.endswith("/39.png")
    assert saved.home_team.logo_url.endswith("/50.png")
    assert saved.league_round == "Regular Season - 38"
    assert saved.venue_name == "Etihad Stadium"
    assert saved.status_short == "NS"


def test_upsert_fixtures_disambiguates_same_api_league_name_by_country(session):
    german_fixture = ExternalFixture(
        source_name="api_football",
        source_match_id="2001",
        source_league_id="78",
        league_name="Bundesliga",
        country="Germany",
        home_source_team_id="100",
        home_team_name="Bayern Munich",
        away_source_team_id="101",
        away_team_name="Borussia Dortmund",
        kickoff_time=datetime(2026, 5, 23, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
        home_score=None,
        away_score=None,
        season=2025,
    )
    austrian_fixture = ExternalFixture(
        source_name="api_football",
        source_match_id="2002",
        source_league_id="218",
        league_name="Bundesliga",
        country="Austria",
        home_source_team_id="200",
        home_team_name="Red Bull Salzburg",
        away_source_team_id="201",
        away_team_name="Rapid Vienna",
        kickoff_time=datetime(2026, 5, 23, 23, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
        home_score=None,
        away_score=None,
        season=2025,
    )

    result = upsert_fixtures(session, [german_fixture, austrian_fixture])

    assert result.created_matches == 2
    league_names = {league.name for league in session.query(League).all()}
    assert league_names == {"Bundesliga (Germany)", "Bundesliga (Austria)"}


def test_upsert_odds_snapshots_saves_snapshot_for_existing_match(session):
    fixture = ExternalFixture(
        source_name="api_football",
        source_match_id="1001",
        source_league_id="39",
        league_name="Premier League",
        country="England",
        home_source_team_id="50",
        home_team_name="Manchester City",
        away_source_team_id="42",
        away_team_name="Arsenal",
        kickoff_time=datetime(2026, 5, 23, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
        home_score=None,
        away_score=None,
        season=2025,
    )
    upsert_fixtures(session, [fixture])
    snapshot = ExternalOddsSnapshot(
        source_name="api_football",
        source_match_id="1001",
        captured_at=datetime(2026, 5, 23, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        bookmaker="Sample Bookmaker",
        asian_handicap=Decimal("-0.25"),
        home_odds=Decimal("1.92"),
        away_odds=Decimal("1.96"),
        total_line=Decimal("2.5"),
        over_odds=Decimal("1.94"),
        under_odds=Decimal("1.94"),
        match_winner_home_odds=Decimal("2.10"),
        match_winner_draw_odds=Decimal("3.25"),
        match_winner_away_odds=Decimal("3.40"),
    )

    result = upsert_odds_snapshots(session, [snapshot])

    assert result.created_odds_snapshots == 1
    saved = session.query(OddsSnapshot).one()
    assert saved.asian_handicap == Decimal("-0.25")
    assert saved.match_winner_home_odds == Decimal("2.10")
    assert saved.match_winner_draw_odds == Decimal("3.25")
    assert saved.match_winner_away_odds == Decimal("3.40")

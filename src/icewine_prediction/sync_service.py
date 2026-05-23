from dataclasses import dataclass

from sqlalchemy.orm import Session

from icewine_prediction.models import League, Match, OddsSnapshot, Team
from icewine_prediction.sources.api_football_mapper import ExternalFixture, ExternalOddsSnapshot


@dataclass(frozen=True)
class FixtureSyncResult:
    created_matches: int = 0
    updated_matches: int = 0


@dataclass(frozen=True)
class OddsSyncResult:
    created_odds_snapshots: int = 0
    skipped_odds_snapshots: int = 0


def league_internal_name(league_name: str, country: str) -> str:
    return f"{league_name} ({country})"


def _get_or_create_league(session: Session, fixture: ExternalFixture) -> League:
    league = (
        session.query(League)
        .filter_by(source_name=fixture.source_name, source_league_id=fixture.source_league_id)
        .one_or_none()
    )
    if league is not None:
        return league
    league = League(
        name=league_internal_name(fixture.league_name, fixture.country),
        country_or_region=fixture.country,
        level=1,
        is_enabled=True,
        priority=0,
        source_name=fixture.source_name,
        source_league_id=fixture.source_league_id,
        logo_url=fixture.league_logo_url,
        flag_url=fixture.league_flag_url,
        standings_supported=fixture.standings_supported,
    )
    session.add(league)
    session.flush()
    return league


def _get_or_create_team(
    session: Session,
    source_name: str,
    source_team_id: str,
    team_name: str,
    country: str,
) -> Team:
    team = (
        session.query(Team)
        .filter_by(source_name=source_name, source_team_id=source_team_id)
        .one_or_none()
    )
    if team is not None:
        return team
    team = Team(
        canonical_name=team_name,
        country_or_region=country,
        source_name=source_name,
        source_team_id=source_team_id,
    )
    session.add(team)
    session.flush()
    return team


def _update_league_metadata(league: League, fixture: ExternalFixture) -> None:
    league.logo_url = fixture.league_logo_url
    league.flag_url = fixture.league_flag_url
    league.standings_supported = fixture.standings_supported


def _update_team_metadata(team: Team, logo_url: str | None) -> None:
    team.logo_url = logo_url


def _apply_match_fixture(match: Match, fixture: ExternalFixture, league: League, home_team: Team, away_team: Team) -> None:
    match.league = league
    match.home_team = home_team
    match.away_team = away_team
    match.kickoff_time = fixture.kickoff_time
    match.season = fixture.season
    match.league_round = fixture.league_round
    match.referee = fixture.referee
    match.fixture_timezone = fixture.fixture_timezone
    match.fixture_timestamp = fixture.fixture_timestamp
    match.first_period_started_at = fixture.first_period_started_at
    match.second_period_started_at = fixture.second_period_started_at
    match.venue_id = fixture.venue_id
    match.venue_name = fixture.venue_name
    match.venue_city = fixture.venue_city
    match.status = fixture.status
    match.status_long = fixture.status_long
    match.status_short = fixture.status_short
    match.elapsed = fixture.elapsed
    match.extra = fixture.extra
    match.home_winner = fixture.home_winner
    match.away_winner = fixture.away_winner
    match.home_score = fixture.home_score
    match.away_score = fixture.away_score
    match.halftime_home_score = fixture.halftime_home_score
    match.halftime_away_score = fixture.halftime_away_score
    match.fulltime_home_score = fixture.fulltime_home_score
    match.fulltime_away_score = fixture.fulltime_away_score
    match.extratime_home_score = fixture.extratime_home_score
    match.extratime_away_score = fixture.extratime_away_score
    match.penalty_home_score = fixture.penalty_home_score
    match.penalty_away_score = fixture.penalty_away_score


def upsert_fixtures(session: Session, fixtures: list[ExternalFixture]) -> FixtureSyncResult:
    created = 0
    updated = 0
    for fixture in fixtures:
        league = _get_or_create_league(session, fixture)
        home_team = _get_or_create_team(
            session,
            fixture.source_name,
            fixture.home_source_team_id,
            fixture.home_team_name,
            fixture.country,
        )
        _update_team_metadata(home_team, fixture.home_team_logo_url)
        away_team = _get_or_create_team(
            session,
            fixture.source_name,
            fixture.away_source_team_id,
            fixture.away_team_name,
            fixture.country,
        )
        _update_league_metadata(league, fixture)
        _update_team_metadata(away_team, fixture.away_team_logo_url)
        match = (
            session.query(Match)
            .filter_by(source_name=fixture.source_name, source_match_id=fixture.source_match_id)
            .one_or_none()
        )
        if match is None:
            match = Match(
                source_name=fixture.source_name,
                source_match_id=fixture.source_match_id,
            )
            _apply_match_fixture(match, fixture, league, home_team, away_team)
            session.add(match)
            created += 1
        else:
            _apply_match_fixture(match, fixture, league, home_team, away_team)
            updated += 1
    session.commit()
    return FixtureSyncResult(created_matches=created, updated_matches=updated)


def upsert_odds_snapshots(session: Session, snapshots: list[ExternalOddsSnapshot]) -> OddsSyncResult:
    created = 0
    skipped = 0
    for snapshot in snapshots:
        match = (
            session.query(Match)
            .filter_by(source_name=snapshot.source_name, source_match_id=snapshot.source_match_id)
            .one_or_none()
        )
        if match is None:
            skipped += 1
            continue
        existing = (
            session.query(OddsSnapshot)
            .filter_by(
                match_id=match.id,
                data_source=snapshot.source_name,
                bookmaker=snapshot.bookmaker,
                captured_at=snapshot.captured_at,
            )
            .one_or_none()
        )
        if existing is not None:
            skipped += 1
            continue
        session.add(
            OddsSnapshot(
                match=match,
                captured_at=snapshot.captured_at,
                data_source=snapshot.source_name,
                bookmaker=snapshot.bookmaker,
                asian_handicap=snapshot.asian_handicap,
                home_odds=snapshot.home_odds,
                away_odds=snapshot.away_odds,
                total_line=snapshot.total_line,
                over_odds=snapshot.over_odds,
                under_odds=snapshot.under_odds,
            )
        )
        created += 1
    session.commit()
    return OddsSyncResult(created_odds_snapshots=created, skipped_odds_snapshots=skipped)

from datetime import datetime

from sqlalchemy.orm import Session

from icewine_prediction.models import League, Match, Team


def get_or_create_league(session: Session, name: str, country_or_region: str) -> League:
    league = session.query(League).filter_by(name=name).one_or_none()
    if league is not None:
        return league
    league = League(
        name=name,
        country_or_region=country_or_region,
        level=1,
        is_enabled=True,
        priority=0,
    )
    session.add(league)
    session.flush()
    return league


def get_or_create_team(session: Session, canonical_name: str, country_or_region: str) -> Team:
    team = session.query(Team).filter_by(canonical_name=canonical_name).one_or_none()
    if team is not None:
        return team
    team = Team(canonical_name=canonical_name, country_or_region=country_or_region)
    session.add(team)
    session.flush()
    return team


def create_match(
    session: Session,
    league_name: str,
    country_or_region: str,
    home_team_name: str,
    away_team_name: str,
    kickoff_time: datetime,
) -> Match:
    league = get_or_create_league(session, league_name, country_or_region)
    home_team = get_or_create_team(session, home_team_name, country_or_region)
    away_team = get_or_create_team(session, away_team_name, country_or_region)
    match = Match(
        league=league,
        home_team=home_team,
        away_team=away_team,
        kickoff_time=kickoff_time,
        status="scheduled",
    )
    session.add(match)
    session.commit()
    return match

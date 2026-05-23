from datetime import datetime
from zoneinfo import ZoneInfo

from icewine_prediction.models import League, Match, Team


def test_can_save_league_teams_and_match(session):
    league = League(name="英超", country_or_region="英格兰", level=1, is_enabled=True, priority=10)
    home_team = Team(canonical_name="阿森纳", english_name="Arsenal", country_or_region="英格兰")
    away_team = Team(canonical_name="切尔西", english_name="Chelsea", country_or_region="英格兰")
    match = Match(
        league=league,
        home_team=home_team,
        away_team=away_team,
        kickoff_time=datetime(2026, 5, 23, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
    )

    session.add(match)
    session.commit()

    saved_match = session.query(Match).one()
    assert saved_match.league.name == "英超"
    assert saved_match.home_team.canonical_name == "阿森纳"
    assert saved_match.away_team.canonical_name == "切尔西"

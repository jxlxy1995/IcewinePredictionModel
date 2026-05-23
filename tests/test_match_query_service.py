from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from icewine_prediction.models import League, Match, Team
from icewine_prediction.match_query_service import list_upcoming_matches


def test_list_upcoming_matches_filters_by_status_and_time_window(session):
    tz = ZoneInfo("Asia/Shanghai")
    start = datetime(2026, 5, 23, 20, 0, tzinfo=tz)
    league = League(name="Serie A", country_or_region="Italy", level=1, is_enabled=True, priority=1)
    home = Team(canonical_name="Bologna", country_or_region="Italy")
    away = Team(canonical_name="Inter", country_or_region="Italy")
    later_home = Team(canonical_name="Lazio", country_or_region="Italy")
    later_away = Team(canonical_name="Pisa", country_or_region="Italy")
    past_match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=start - timedelta(hours=1),
        status="scheduled",
    )
    first_match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=start + timedelta(hours=4),
        status="scheduled",
    )
    second_match = Match(
        league=league,
        home_team=later_home,
        away_team=later_away,
        kickoff_time=start + timedelta(hours=6),
        status="scheduled",
    )
    finished_match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=start + timedelta(hours=5),
        status="finished",
    )
    outside_window = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=start + timedelta(hours=25),
        status="scheduled",
    )
    session.add_all([past_match, first_match, second_match, finished_match, outside_window])
    session.commit()

    matches = list_upcoming_matches(session, start_time=start, hours=24)

    assert [match.home_team.canonical_name for match in matches] == ["Bologna", "Lazio"]

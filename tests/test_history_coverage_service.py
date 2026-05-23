from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.history_coverage_service import build_history_coverage_report
from icewine_prediction.models import League, Match, OddsSnapshot, Team


def _create_match(
    league: League,
    home_team: Team,
    away_team: Team,
    kickoff_time: datetime,
    status: str,
    home_score: int | None,
    away_score: int | None,
) -> Match:
    return Match(
        league=league,
        home_team=home_team,
        away_team=away_team,
        kickoff_time=kickoff_time,
        status=status,
        home_score=home_score,
        away_score=away_score,
        season=2025,
    )


def test_build_history_coverage_report_summarizes_local_matches(session):
    league = League(
        name="La Liga",
        country_or_region="Spain",
        level=1,
        priority=98,
    )
    home_team = Team(canonical_name="Barcelona", country_or_region="Spain")
    away_team = Team(canonical_name="Real Madrid", country_or_region="Spain")
    finished_match = _create_match(
        league,
        home_team,
        away_team,
        datetime(2025, 8, 16, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        "finished",
        2,
        1,
    )
    scheduled_match = _create_match(
        league,
        home_team,
        away_team,
        datetime(2025, 8, 23, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        "scheduled",
        None,
        None,
    )
    session.add_all([league, home_team, away_team, finished_match, scheduled_match])
    session.flush()
    session.add(
        OddsSnapshot(
            match=finished_match,
            captured_at=datetime(2025, 8, 15, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            data_source="api_football",
            bookmaker="Example",
            asian_handicap=Decimal("-0.50"),
            home_odds=Decimal("1.90"),
            away_odds=Decimal("1.95"),
            total_line=Decimal("2.50"),
            over_odds=Decimal("1.91"),
            under_odds=Decimal("1.91"),
        )
    )
    session.commit()

    report = build_history_coverage_report(session, season=2025)

    assert len(report) == 1
    summary = report[0]
    assert summary.league_name == "La Liga"
    assert summary.total_matches == 2
    assert summary.finished_matches == 1
    assert summary.scored_matches == 1
    assert summary.matches_with_odds == 1
    assert summary.matches_with_asian_handicap == 1
    assert summary.matches_with_total_goals == 1
    assert summary.odds_coverage_ratio == Decimal("0.5000")
    assert summary.asian_handicap_coverage_ratio == Decimal("0.5000")
    assert summary.total_goals_coverage_ratio == Decimal("0.5000")


def test_build_history_coverage_report_filters_by_api_season_not_kickoff_year(session):
    league = League(
        name="Premier League (England)",
        country_or_region="England",
        level=1,
        priority=100,
    )
    home_team = Team(canonical_name="Liverpool", country_or_region="England")
    away_team = Team(canonical_name="Arsenal", country_or_region="England")
    session.add_all(
        [
            league,
            home_team,
            away_team,
            Match(
                league=league,
                home_team=home_team,
                away_team=away_team,
                kickoff_time=datetime(2026, 5, 23, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                season=2025,
                status="finished",
                home_score=2,
                away_score=1,
            ),
        ]
    )
    session.commit()

    report = build_history_coverage_report(session, season=2025)

    assert len(report) == 1
    assert report[0].total_matches == 1

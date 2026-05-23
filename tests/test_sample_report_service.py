from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import League, Match, OddsSnapshot, Team
from icewine_prediction.sample_report_service import build_training_sample_report


def _add_finished_match(
    session,
    league_name: str,
    source_match_id: str,
    kickoff_time: datetime,
    has_odds: bool,
) -> None:
    league = (
        session.query(League)
        .filter_by(name=league_name)
        .one_or_none()
    )
    if league is None:
        league = League(name=league_name, country_or_region="Test", level=1)
        session.add(league)
        session.flush()
    home = Team(canonical_name=f"{source_match_id} Home")
    away = Team(canonical_name=f"{source_match_id} Away")
    session.add_all([home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff_time,
        status="finished",
        home_score=2,
        away_score=1,
        source_name="api_football",
        source_match_id=source_match_id,
    )
    session.add(match)
    session.flush()
    if has_odds:
        session.add(
            OddsSnapshot(
                match=match,
                captured_at=kickoff_time,
                data_source="api_football",
                bookmaker="Bet365",
                asian_handicap=Decimal("-0.50"),
                home_odds=Decimal("1.90"),
                away_odds=Decimal("1.95"),
                total_line=Decimal("2.50"),
                over_odds=Decimal("1.85"),
                under_odds=Decimal("2.00"),
            )
        )
    session.commit()


def test_build_training_sample_report_counts_distribution_and_odds_ratio(session):
    reference_time = datetime(2026, 5, 23, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    _add_finished_match(
        session,
        league_name="Premier League",
        source_match_id="a",
        kickoff_time=datetime(2026, 5, 20, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        has_odds=True,
    )
    _add_finished_match(
        session,
        league_name="Premier League",
        source_match_id="b",
        kickoff_time=datetime(2025, 5, 20, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        has_odds=False,
    )
    _add_finished_match(
        session,
        league_name="La Liga",
        source_match_id="c",
        kickoff_time=datetime(2024, 5, 20, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        has_odds=True,
    )

    report = build_training_sample_report(session, reference_time=reference_time)

    assert report.total_samples == 3
    assert report.samples_with_odds == 2
    assert report.odds_coverage_ratio == Decimal("0.67")
    assert report.by_league == {"Premier League": 2, "La Liga": 1}
    assert report.by_season == {2026: 1, 2025: 1, 2024: 1}
    assert report.by_weight == {
        Decimal("1.00"): 1,
        Decimal("0.55"): 1,
        Decimal("0.35"): 1,
    }

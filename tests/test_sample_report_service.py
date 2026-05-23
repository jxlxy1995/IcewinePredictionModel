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
    market_type: str | None,
    season: int | None = 2025,
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
        season=season,
        source_name="api_football",
        source_match_id=source_match_id,
    )
    session.add(match)
    session.flush()
    if market_type is not None:
        session.add(
            OddsSnapshot(
                match=match,
                captured_at=kickoff_time,
                data_source="api_football",
                bookmaker="Bet365",
                asian_handicap=Decimal("-0.50") if market_type in {"asian", "both"} else None,
                home_odds=Decimal("1.90") if market_type in {"asian", "both"} else None,
                away_odds=Decimal("1.95") if market_type in {"asian", "both"} else None,
                total_line=Decimal("2.50") if market_type in {"total", "both"} else None,
                over_odds=Decimal("1.85") if market_type in {"total", "both"} else None,
                under_odds=Decimal("2.00") if market_type in {"total", "both"} else None,
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
        market_type="both",
        season=2025,
    )
    _add_finished_match(
        session,
        league_name="Premier League",
        source_match_id="b",
        kickoff_time=datetime(2025, 5, 20, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        market_type=None,
        season=2024,
    )
    _add_finished_match(
        session,
        league_name="La Liga",
        source_match_id="c",
        kickoff_time=datetime(2024, 5, 20, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        market_type="asian",
        season=None,
    )
    _add_finished_match(
        session,
        league_name="La Liga",
        source_match_id="d",
        kickoff_time=datetime(2026, 5, 21, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        market_type="total",
        season=2025,
    )

    report = build_training_sample_report(session, reference_time=reference_time)

    assert report.total_samples == 4
    assert report.samples_with_odds == 3
    assert report.samples_with_asian_handicap == 2
    assert report.samples_with_total_goals == 2
    assert report.odds_coverage_ratio == Decimal("0.75")
    assert report.asian_handicap_coverage_ratio == Decimal("0.50")
    assert report.total_goals_coverage_ratio == Decimal("0.50")
    assert report.by_league["Premier League"].total_samples == 2
    assert report.by_league["Premier League"].samples_with_asian_handicap == 1
    assert report.by_league["La Liga"].samples_with_total_goals == 1
    assert report.by_season == {2025: 2, 2024: 2}
    assert report.by_weight == {
        Decimal("1.00"): 2,
        Decimal("0.55"): 1,
        Decimal("0.35"): 1,
    }


def test_build_training_sample_report_filters_by_api_season(session):
    reference_time = datetime(2026, 5, 23, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    _add_finished_match(
        session,
        league_name="Premier League",
        source_match_id="season-2025",
        kickoff_time=datetime(2026, 5, 20, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        market_type="both",
        season=2025,
    )
    _add_finished_match(
        session,
        league_name="Premier League",
        source_match_id="season-2024",
        kickoff_time=datetime(2025, 5, 20, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        market_type="both",
        season=2024,
    )

    report = build_training_sample_report(session, season=2025, reference_time=reference_time)

    assert report.total_samples == 1
    assert report.by_season == {2025: 1}

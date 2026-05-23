from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.historical_performance_service import (
    HistoricalPerformanceFilters,
    build_historical_performance_report,
)
from icewine_prediction.models import League, Match, RecommendationRecord, Team


def _create_match(session) -> Match:
    league = League(
        name="La Liga",
        country_or_region="Spain",
        level=1,
        priority=10,
    )
    home_team = Team(canonical_name="Barcelona", country_or_region="Spain")
    away_team = Team(canonical_name="Real Madrid", country_or_region="Spain")
    match = Match(
        league=league,
        home_team=home_team,
        away_team=away_team,
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="finished",
        home_score=2,
        away_score=1,
    )
    session.add_all([league, home_team, away_team, match])
    session.commit()
    return match


def _record(
    match: Match,
    market_type: str,
    side: str,
    edge: Decimal,
    confidence_grade: str,
    stake_units: Decimal,
    profit_units: Decimal | None,
    settlement_result: str | None = None,
    status: str = "settled",
) -> RecommendationRecord:
    return RecommendationRecord(
        match=match,
        created_at=datetime(2026, 5, 23, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        league_name=match.league.name,
        home_team_name=match.home_team.canonical_name,
        away_team_name=match.away_team.canonical_name,
        kickoff_time=match.kickoff_time,
        market_type=market_type,
        side=side,
        market_line=Decimal("-0.50") if market_type == "asian_handicap" else Decimal("2.50"),
        odds=Decimal("1.90"),
        model_probability=Decimal("0.6000"),
        market_implied_probability=Decimal("0.5263"),
        edge=edge,
        confidence_grade=confidence_grade,
        stake_units=stake_units,
        home_expected_goals=Decimal("1.40"),
        away_expected_goals=Decimal("1.10"),
        status=status,
        settlement_result=settlement_result,
        profit_units=profit_units,
    )


def test_build_historical_performance_report_filters_settled_records(session):
    match = _create_match(session)
    session.add_all(
        [
            _record(
                match,
                "asian_handicap",
                "home",
                Decimal("0.0800"),
                "A-",
                Decimal("2.00"),
                Decimal("1.800"),
                settlement_result="win",
            ),
            _record(
                match,
                "asian_handicap",
                "away",
                Decimal("0.0500"),
                "B+",
                Decimal("1.00"),
                Decimal("-1.000"),
                settlement_result="loss",
            ),
            _record(
                match,
                "total_goals",
                "over",
                Decimal("0.1200"),
                "A",
                Decimal("1.50"),
                Decimal("0.675"),
                settlement_result="win",
            ),
            _record(
                match,
                "asian_handicap",
                "home",
                Decimal("0.0800"),
                "A-",
                Decimal("3.00"),
                None,
                status="pending",
            ),
        ]
    )
    session.commit()

    report = build_historical_performance_report(
        session,
        HistoricalPerformanceFilters(
            market_type="asian_handicap",
            side="home",
            edge_bucket="0.06-0.10",
        ),
    )

    assert report.total.record_count == 1
    assert report.total.stake_units == Decimal("2.00")
    assert report.total.profit_units == Decimal("1.800")
    assert report.total.roi == Decimal("0.9000")
    assert report.by_settlement_result["win"].record_count == 1
    assert report.by_edge_bucket["0.06-0.10"].record_count == 1
    assert report.by_market_type["asian_handicap"].record_count == 1
    assert report.by_side["home"].record_count == 1
    assert report.by_confidence_grade["A-"].record_count == 1
    assert report.by_league["La Liga"].record_count == 1

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import League, Match, RecommendationRecord, Team
from icewine_prediction.record_service import build_record_report


def _match(session) -> Match:
    league = League(name="La Liga", country_or_region="Spain", level=1)
    home = Team(canonical_name="Real Madrid")
    away = Team(canonical_name="Athletic Club")
    session.add_all([league, home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="finished",
        home_score=2,
        away_score=1,
        source_name="api_football",
        source_match_id="match-1",
    )
    session.add(match)
    session.commit()
    return match


def _record(
    match: Match,
    market_type: str,
    confidence_grade: str,
    stake_units: Decimal,
    profit_units: Decimal | None,
    settlement_result: str | None = None,
    edge: Decimal = Decimal("0.0737"),
    status: str = "settled",
) -> RecommendationRecord:
    return RecommendationRecord(
        match_id=match.id,
        created_at=datetime(2026, 5, 23, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        league_name=match.league.name,
        home_team_name=match.home_team.canonical_name,
        away_team_name=match.away_team.canonical_name,
        kickoff_time=match.kickoff_time,
        market_type=market_type,
        side="home",
        market_line=Decimal("-0.75"),
        odds=Decimal("1.90"),
        model_probability=Decimal("0.6000"),
        market_implied_probability=Decimal("0.5263"),
        edge=edge,
        confidence_grade=confidence_grade,
        stake_units=stake_units,
        home_expected_goals=Decimal("1.40"),
        away_expected_goals=Decimal("1.00"),
        status=status,
        settlement_result=settlement_result,
        profit_units=profit_units,
    )


def test_build_record_report_summarizes_settled_records(session):
    match = _match(session)
    session.add_all(
        [
            _record(
                match,
                "asian_handicap",
                "A+",
                Decimal("2.00"),
                Decimal("1.800"),
                settlement_result="win",
                edge=Decimal("0.0200"),
            ),
            _record(
                match,
                "total_goals",
                "B",
                Decimal("1.00"),
                Decimal("-1.000"),
                settlement_result="loss",
                edge=Decimal("0.0500"),
            ),
            _record(
                match,
                "asian_handicap",
                "B+",
                Decimal("1.50"),
                Decimal("0.750"),
                settlement_result="half_win",
                edge=Decimal("0.0800"),
            ),
            _record(
                match,
                "total_goals",
                "A-",
                Decimal("1.25"),
                Decimal("1.000"),
                settlement_result="win",
                edge=Decimal("0.1200"),
            ),
            _record(match, "total_goals", "B", Decimal("1.50"), None, status="pending"),
        ]
    )
    session.commit()

    report = build_record_report(session)

    assert report.total_records == 5
    assert report.settled_records == 4
    assert report.pending_records == 1
    assert report.total_stake_units == Decimal("5.75")
    assert report.total_profit_units == Decimal("2.550")
    assert report.roi == Decimal("0.4435")
    assert report.by_edge_bucket["0.00-0.03"].record_count == 1
    assert report.by_edge_bucket["0.03-0.06"].record_count == 1
    assert report.by_edge_bucket["0.06-0.10"].record_count == 1
    assert report.by_edge_bucket["0.10+"].record_count == 1
    assert report.by_settlement_result["win"].record_count == 2
    assert report.by_settlement_result["half_win"].record_count == 1
    assert report.by_settlement_result["loss"].record_count == 1
    assert report.by_market_type["asian_handicap"].profit_units == Decimal("2.550")
    assert report.by_market_type["total_goals"].profit_units == Decimal("0.000")
    assert report.by_confidence_grade["A+"].record_count == 1
    assert report.by_confidence_grade["B"].record_count == 1
    assert report.by_league["La Liga"].stake_units == Decimal("5.75")

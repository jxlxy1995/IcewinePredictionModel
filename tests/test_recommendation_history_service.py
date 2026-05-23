from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import League, Match, RecommendationRecord, Team
from icewine_prediction.recommendation_history_service import enrich_recommendations_with_history
from icewine_prediction.recommendation_service import Recommendation


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


def test_enrich_recommendations_with_history_preserves_decision_fields(session):
    match = _create_match(session)
    session.add(
        RecommendationRecord(
            match=match,
            created_at=datetime(2026, 5, 23, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            league_name=match.league.name,
            home_team_name=match.home_team.canonical_name,
            away_team_name=match.away_team.canonical_name,
            kickoff_time=match.kickoff_time,
            market_type="asian_handicap",
            side="home",
            market_line=Decimal("-0.50"),
            odds=Decimal("1.90"),
            model_probability=Decimal("0.6000"),
            market_implied_probability=Decimal("0.5263"),
            edge=Decimal("0.0800"),
            confidence_grade="A-",
            stake_units=Decimal("2.00"),
            home_expected_goals=Decimal("1.40"),
            away_expected_goals=Decimal("1.10"),
            status="settled",
            settlement_result="win",
            profit_units=Decimal("1.800"),
        )
    )
    session.commit()
    recommendation = Recommendation(
        market_type="asian_handicap",
        side="home",
        confidence_grade="B+",
        stake_units=Decimal("1.50"),
        should_bet=True,
        edge=Decimal("0.0810"),
        risk_tags=[],
        model_probability=Decimal("0.6100"),
        market_implied_probability=Decimal("0.5290"),
        similar_backtest_roi=Decimal("0.0500"),
        market_line=Decimal("-0.50"),
    )

    enriched = enrich_recommendations_with_history(session, [recommendation])[0]

    assert enriched.confidence_grade == "B+"
    assert enriched.stake_units == Decimal("1.50")
    assert enriched.should_bet is True
    assert enriched.similar_backtest_roi == Decimal("0.0500")
    assert enriched.historical_sample_count == 1
    assert enriched.historical_roi == Decimal("0.9000")

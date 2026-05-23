from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.feature_service import MatchOddsFeatures, OddsMarketAggregate
from icewine_prediction.models import League, Match, Team
from icewine_prediction.recommendation_service import Recommendation
from icewine_prediction.record_service import (
    list_pending_records,
    record_recommendations_for_match,
)


def _aggregate(mean: Decimal | None) -> OddsMarketAggregate:
    return OddsMarketAggregate(
        sample_count=1 if mean is not None else 0,
        mean=mean,
        median=mean,
        minimum=mean,
        maximum=mean,
        disagreement=Decimal("0.00") if mean is not None else None,
    )


def _features() -> MatchOddsFeatures:
    return MatchOddsFeatures(
        match_id=1,
        bookmaker_count=8,
        asian_handicap=_aggregate(Decimal("-0.75")),
        home_odds=_aggregate(Decimal("1.90")),
        away_odds=_aggregate(Decimal("1.95")),
        total_line=_aggregate(Decimal("2.50")),
        over_odds=_aggregate(Decimal("1.88")),
        under_odds=_aggregate(Decimal("1.98")),
    )


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
        status="scheduled",
        source_name="api_football",
        source_match_id="match-1",
    )
    session.add(match)
    session.commit()
    return match


def _recommendation(
    market_type: str = "asian_handicap",
    side: str = "away",
    should_bet: bool = True,
) -> Recommendation:
    return Recommendation(
        market_type=market_type,
        side=side,
        confidence_grade="A+",
        stake_units=Decimal("2.25"),
        should_bet=should_bet,
        edge=Decimal("0.1234"),
        risk_tags=[],
        model_probability=Decimal("0.6500"),
        market_implied_probability=Decimal("0.5263"),
        similar_backtest_roi=Decimal("0.05"),
        home_expected_goals=Decimal("1.10"),
        away_expected_goals=Decimal("0.86"),
        market_line=Decimal("-0.75"),
    )


def test_record_recommendations_stores_only_bettable_recommendations(session):
    match = _match(session)

    inserted = record_recommendations_for_match(
        session=session,
        match=match,
        recommendations=[
            _recommendation(),
            _recommendation(market_type="total_goals", side="watch", should_bet=False),
        ],
        features=_features(),
        recorded_at=datetime(2026, 5, 23, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    records = list_pending_records(session)

    assert inserted == 1
    assert len(records) == 1
    record = records[0]
    assert record.match_id == match.id
    assert record.league_name == "La Liga"
    assert record.home_team_name == "Real Madrid"
    assert record.away_team_name == "Athletic Club"
    assert record.market_type == "asian_handicap"
    assert record.side == "away"
    assert record.market_line == Decimal("-0.75")
    assert record.odds == Decimal("1.95")
    assert record.model_probability == Decimal("0.6500")
    assert record.market_implied_probability == Decimal("0.5263")
    assert record.edge == Decimal("0.1234")
    assert record.confidence_grade == "A+"
    assert record.stake_units == Decimal("2.25")
    assert record.home_expected_goals == Decimal("1.10")
    assert record.away_expected_goals == Decimal("0.86")
    assert record.status == "pending"


def test_record_recommendations_skips_duplicate_pending_record(session):
    match = _match(session)
    kwargs = {
        "session": session,
        "match": match,
        "recommendations": [_recommendation()],
        "features": _features(),
        "recorded_at": datetime(2026, 5, 23, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    }

    first = record_recommendations_for_match(**kwargs)
    second = record_recommendations_for_match(**kwargs)

    assert first == 1
    assert second == 0
    assert len(list_pending_records(session)) == 1

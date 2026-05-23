from decimal import Decimal

from icewine_prediction.feature_service import MatchOddsFeatures, OddsMarketAggregate
from icewine_prediction.recommendation_service import build_rule_recommendations_from_features


def _aggregate(
    mean: str | None,
    sample_count: int = 12,
    disagreement: str | None = "0.25",
) -> OddsMarketAggregate:
    value = Decimal(mean) if mean is not None else None
    return OddsMarketAggregate(
        sample_count=sample_count,
        mean=value,
        median=value,
        minimum=value,
        maximum=value,
        disagreement=Decimal(disagreement) if disagreement is not None else None,
    )


def _features(
    bookmaker_count: int = 12,
    home_odds: str = "1.80",
    away_odds: str = "2.05",
    over_odds: str = "1.86",
    under_odds: str = "2.05",
    handicap_disagreement: str = "0.50",
    total_disagreement: str = "0.25",
) -> MatchOddsFeatures:
    return MatchOddsFeatures(
        match_id=1,
        bookmaker_count=bookmaker_count,
        asian_handicap=_aggregate("-0.50", disagreement=handicap_disagreement),
        home_odds=_aggregate(home_odds),
        away_odds=_aggregate(away_odds),
        total_line=_aggregate("2.50", disagreement=total_disagreement),
        over_odds=_aggregate(over_odds),
        under_odds=_aggregate(under_odds),
    )


def test_rule_recommendations_generate_handicap_and_total_lean():
    recommendations = build_rule_recommendations_from_features(_features())

    assert len(recommendations) == 2
    handicap = recommendations[0]
    total = recommendations[1]
    assert handicap.market_type == "asian_handicap"
    assert handicap.side == "home"
    assert handicap.confidence_grade in {"C+", "B-", "B"}
    assert handicap.should_bet is True
    assert handicap.stake_units >= Decimal("0.50")
    assert total.market_type == "total_goals"
    assert total.side == "over"
    assert total.should_bet is True


def test_rule_recommendations_stay_away_when_sample_is_low():
    recommendations = build_rule_recommendations_from_features(_features(bookmaker_count=4))

    assert all(recommendation.side == "watch" for recommendation in recommendations)
    assert all(recommendation.should_bet is False for recommendation in recommendations)
    assert all(recommendation.stake_units == Decimal("0") for recommendation in recommendations)
    assert all("low_bookmaker_count" in recommendation.risk_tags for recommendation in recommendations)


def test_rule_recommendations_stay_away_when_market_disagreement_is_high():
    recommendations = build_rule_recommendations_from_features(
        _features(handicap_disagreement="1.25", total_disagreement="1.00")
    )

    assert recommendations[0].side == "watch"
    assert recommendations[1].side == "watch"
    assert "handicap_disagreement_high" in recommendations[0].risk_tags
    assert "total_disagreement_high" in recommendations[1].risk_tags

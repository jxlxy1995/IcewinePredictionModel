from decimal import Decimal

from icewine_prediction.feature_service import MatchOddsFeatures, OddsMarketAggregate
from icewine_prediction.model_training_service import BaselineResultModel
from icewine_prediction.recommendation_service import build_model_recommendations_from_features


def _aggregate(mean: Decimal | None, disagreement: Decimal | None = Decimal("0.00")):
    return OddsMarketAggregate(
        sample_count=6 if mean is not None else 0,
        mean=mean,
        median=mean,
        minimum=mean,
        maximum=mean,
        disagreement=disagreement,
    )


def _features() -> MatchOddsFeatures:
    return MatchOddsFeatures(
        match_id=1,
        bookmaker_count=8,
        asian_handicap=_aggregate(Decimal("-0.25")),
        home_odds=_aggregate(Decimal("1.95")),
        away_odds=_aggregate(Decimal("1.95")),
        total_line=_aggregate(Decimal("2.5")),
        over_odds=_aggregate(Decimal("2.05")),
        under_odds=_aggregate(Decimal("1.85")),
    )


def test_model_recommendations_generate_handicap_and_total_markets():
    recommendations = build_model_recommendations_from_features(
        features=_features(),
        model=BaselineResultModel(
            home_expected_goals=Decimal("1.80"),
            away_expected_goals=Decimal("1.00"),
        ),
    )

    assert len(recommendations) == 2
    assert recommendations[0].market_type == "asian_handicap"
    assert recommendations[0].side == "home"
    assert recommendations[0].edge > Decimal("0")
    assert recommendations[1].market_type == "total_goals"
    assert recommendations[1].side in {"over", "under", "watch"}


def test_model_recommendations_watch_when_market_line_is_missing():
    features = MatchOddsFeatures(
        match_id=1,
        bookmaker_count=8,
        asian_handicap=_aggregate(None),
        home_odds=_aggregate(None),
        away_odds=_aggregate(None),
        total_line=_aggregate(None),
        over_odds=_aggregate(None),
        under_odds=_aggregate(None),
    )

    recommendations = build_model_recommendations_from_features(
        features=features,
        model=BaselineResultModel(
            home_expected_goals=Decimal("1.30"),
            away_expected_goals=Decimal("1.10"),
        ),
    )

    assert all(recommendation.side == "watch" for recommendation in recommendations)
    assert all("missing_market_odds" in recommendation.risk_tags for recommendation in recommendations)

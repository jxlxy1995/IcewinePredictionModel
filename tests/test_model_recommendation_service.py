from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.feature_service import MatchOddsFeatures, OddsMarketAggregate
from icewine_prediction.model_training_service import (
    BaselineResultModel,
    train_league_team_strength_goal_model,
    train_team_strength_goal_model,
)
from icewine_prediction.recommendation_service import build_model_recommendations_from_features
from icewine_prediction.training_sample_service import TrainingSample


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


def _sample(
    match_id: int,
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    league_name: str = "La Liga",
) -> TrainingSample:
    if home_score > away_score:
        match_result = "home_win"
    elif home_score < away_score:
        match_result = "away_win"
    else:
        match_result = "draw"
    return TrainingSample(
        match_id=match_id,
        source_match_id=str(match_id),
        league_name=league_name,
        home_team_name=home_team,
        away_team_name=away_team,
        kickoff_time=datetime(2025, 5, match_id, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_score=home_score,
        away_score=away_score,
        match_result=match_result,
        total_goals=home_score + away_score,
        asian_handicap_line=None,
        home_handicap_result=None,
        away_handicap_result=None,
        total_line=None,
        over_result=None,
        under_result=None,
        has_odds_snapshot=False,
        sample_age_days=300,
        time_decay_weight=Decimal("1.00"),
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
    assert recommendations[0].home_expected_goals == Decimal("1.80")
    assert recommendations[0].away_expected_goals == Decimal("1.00")
    assert recommendations[0].market_line == Decimal("-0.25")
    assert recommendations[0].model_probability is not None
    assert recommendations[0].market_implied_probability is not None
    assert recommendations[1].market_type == "total_goals"
    assert recommendations[1].side in {"over", "under", "watch"}
    assert recommendations[1].market_line == Decimal("2.5")


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


def test_model_recommendations_can_use_team_specific_model():
    team_model = train_team_strength_goal_model(
        [
            _sample(1, "Strong", "Weak", 3, 0),
            _sample(2, "Weak", "Strong", 0, 2),
            _sample(3, "Strong", "Average", 2, 0),
        ]
    )

    recommendations = build_model_recommendations_from_features(
        features=_features(),
        model=team_model,
        home_team_name="Strong",
        away_team_name="Weak",
    )

    assert recommendations[0].side == "home"


def test_model_recommendations_can_use_league_specific_model():
    league_model = train_league_team_strength_goal_model(
        [
            _sample(1, "Strong", "Weak", 4, 0, league_name="League A"),
            _sample(2, "Weak", "Strong", 0, 3, league_name="League A"),
            _sample(3, "Strong", "Weak", 1, 1, league_name="League B"),
            _sample(4, "Weak", "Strong", 1, 1, league_name="League B"),
        ]
    )

    recommendations = build_model_recommendations_from_features(
        features=_features(),
        model=league_model,
        league_name="League A",
        home_team_name="Strong",
        away_team_name="Weak",
    )

    assert recommendations[0].side == "home"

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.dixon_coles_model_service import (
    DixonColesGoalModel,
    train_dixon_coles_goal_model,
)
from icewine_prediction.goal_distribution_service import build_goal_distribution_prediction
from icewine_prediction.training_sample_service import TrainingSample


def _sample(match_id, home_score, away_score, weight="1.00"):
    return TrainingSample(
        match_id=match_id,
        source_match_id=str(match_id),
        league_name="League",
        home_team_name=f"Home {match_id}",
        away_team_name=f"Away {match_id}",
        kickoff_time=datetime(2025, 5, match_id, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_score=home_score,
        away_score=away_score,
        match_result="home_win" if home_score > away_score else "draw",
        total_goals=home_score + away_score,
        asian_handicap_line=None,
        home_handicap_result=None,
        away_handicap_result=None,
        total_line=None,
        over_result=None,
        under_result=None,
        has_odds_snapshot=False,
        sample_age_days=300,
        time_decay_weight=Decimal(weight),
    )


def test_dixon_coles_model_adjusts_low_score_probabilities():
    model = DixonColesGoalModel(
        home_expected_goals=Decimal("1.20"),
        away_expected_goals=Decimal("0.90"),
        rho=Decimal("-0.1000"),
    )
    poisson = build_goal_distribution_prediction(
        home_expected_goals=Decimal("1.20"),
        away_expected_goals=Decimal("0.90"),
    )

    prediction = model.predict_goal_distribution()

    assert prediction.score_probability(0, 0) > poisson.score_probability(0, 0)
    assert prediction.score_probability(1, 1) > poisson.score_probability(1, 1)
    assert sum(prediction.score_probabilities.values()) == Decimal("1.0000")


def test_train_dixon_coles_goal_model_returns_bounded_rho():
    model = train_dixon_coles_goal_model(
        [
            _sample(1, 0, 0),
            _sample(2, 1, 1),
            _sample(3, 1, 0),
            _sample(4, 0, 1),
            _sample(5, 2, 1),
            _sample(6, 1, 2),
        ]
    )

    prediction = model.predict_goal_distribution()

    assert Decimal("-0.2500") <= model.rho <= Decimal("0.2500")
    assert model.home_expected_goals > Decimal("0")
    assert model.away_expected_goals > Decimal("0")
    assert sum(prediction.score_probabilities.values()) == Decimal("1.0000")

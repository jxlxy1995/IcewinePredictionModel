from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from icewine_prediction.dixon_coles_model_service import (
    train_dixon_coles_attack_defense_model,
)
from icewine_prediction.model_training_service import (
    BaselineResultModel,
    train_league_team_strength_goal_model,
    train_team_strength_goal_model,
)
from icewine_prediction.score_model_service import (
    ScoreModelContext,
    predict_goal_distribution_from_model,
)
from icewine_prediction.training_sample_service import TrainingSample


def _sample(match_id, league, home_team, away_team, home_score, away_score):
    return TrainingSample(
        match_id=match_id,
        source_match_id=str(match_id),
        league_name=league,
        home_team_name=home_team,
        away_team_name=away_team,
        kickoff_time=datetime(2025, 5, match_id, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_score=home_score,
        away_score=away_score,
        match_result="home_win" if home_score > away_score else "away_win",
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


def test_predict_goal_distribution_from_baseline_model():
    model = BaselineResultModel(
        home_expected_goals=Decimal("1.40"),
        away_expected_goals=Decimal("1.10"),
    )

    prediction = predict_goal_distribution_from_model(model)

    assert prediction.home_expected_goals == Decimal("1.40")
    assert prediction.away_expected_goals == Decimal("1.10")
    assert (
        prediction.home_win_probability
        + prediction.draw_probability
        + prediction.away_win_probability
    ) == Decimal("1.0000")


def test_predict_goal_distribution_from_team_strength_model_uses_context():
    model = train_team_strength_goal_model(
        [
            _sample(1, "League", "Strong", "Weak", 3, 0),
            _sample(2, "League", "Strong", "Average", 2, 1),
            _sample(3, "League", "Weak", "Strong", 0, 2),
        ]
    )

    prediction = predict_goal_distribution_from_model(
        model,
        ScoreModelContext(home_team_name="Strong", away_team_name="Weak"),
    )

    assert prediction.home_expected_goals > prediction.away_expected_goals


def test_predict_goal_distribution_from_team_strength_model_requires_context():
    model = train_team_strength_goal_model(
        [_sample(1, "League", "Home", "Away", 2, 1)]
    )

    with pytest.raises(ValueError, match="home and away names"):
        predict_goal_distribution_from_model(model)


def test_predict_goal_distribution_from_league_team_strength_model_uses_league_context():
    model = train_league_team_strength_goal_model(
        [
            _sample(1, "League A", "Strong", "Weak", 4, 0),
            _sample(2, "League A", "Weak", "Strong", 0, 3),
            _sample(3, "League B", "Strong", "Weak", 1, 1),
            _sample(4, "League B", "Weak", "Strong", 1, 1),
        ]
    )

    league_a = predict_goal_distribution_from_model(
        model,
        ScoreModelContext(
            league_name="League A",
            home_team_name="Strong",
            away_team_name="Weak",
        ),
    )
    league_b = predict_goal_distribution_from_model(
        model,
        ScoreModelContext(
            league_name="League B",
            home_team_name="Strong",
            away_team_name="Weak",
        ),
    )

    assert league_a.home_expected_goals > league_b.home_expected_goals


def test_predict_goal_distribution_from_attack_defense_dixon_coles_model():
    model = train_dixon_coles_attack_defense_model(
        [
            _sample(1, "League", "Strong", "Weak", 4, 0),
            _sample(2, "League", "Strong", "Average", 3, 1),
            _sample(3, "League", "Weak", "Strong", 0, 3),
            _sample(4, "League", "Average", "Weak", 2, 0),
        ]
    )

    prediction = predict_goal_distribution_from_model(
        model,
        ScoreModelContext(home_team_name="Strong", away_team_name="Weak"),
    )

    assert prediction.home_expected_goals > prediction.away_expected_goals

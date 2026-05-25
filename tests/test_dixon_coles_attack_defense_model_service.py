from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.dixon_coles_model_service import (
    train_dixon_coles_attack_defense_model,
)
from icewine_prediction.training_sample_service import TrainingSample


def _sample(match_id, home_team, away_team, home_score, away_score):
    return TrainingSample(
        match_id=match_id,
        source_match_id=str(match_id),
        league_name="League",
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


def test_attack_defense_dixon_coles_model_learns_team_strengths():
    model = train_dixon_coles_attack_defense_model(
        [
            _sample(1, "Strong", "Weak", 4, 0),
            _sample(2, "Strong", "Average", 3, 1),
            _sample(3, "Average", "Weak", 2, 0),
            _sample(4, "Weak", "Strong", 0, 3),
            _sample(5, "Average", "Strong", 1, 2),
            _sample(6, "Weak", "Average", 0, 2),
        ]
    )

    strong_home = model.predict_match_goal_distribution("Strong", "Weak")
    weak_home = model.predict_match_goal_distribution("Weak", "Strong")

    assert model.team_count == 3
    assert strong_home.home_expected_goals > strong_home.away_expected_goals
    assert weak_home.away_expected_goals > weak_home.home_expected_goals
    assert strong_home.home_expected_goals > weak_home.home_expected_goals


def test_attack_defense_dixon_coles_model_uses_neutral_unknown_teams():
    model = train_dixon_coles_attack_defense_model(
        [
            _sample(1, "Home", "Away", 2, 1),
            _sample(2, "Away", "Home", 1, 1),
        ]
    )

    prediction = model.predict_match_goal_distribution("Unknown Home", "Unknown Away")

    assert prediction.home_expected_goals > Decimal("0")
    assert prediction.away_expected_goals > Decimal("0")
    assert sum(prediction.score_probabilities.values()) == Decimal("1.0000")

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.model_training_service import train_team_strength_goal_model
from icewine_prediction.training_sample_service import TrainingSample


def _sample(
    match_id: int,
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
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
        league_name="La Liga",
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


def test_team_strength_model_predicts_match_expected_goals():
    model = train_team_strength_goal_model(
        [
            _sample(1, "Strong", "Weak", 3, 0),
            _sample(2, "Strong", "Average", 2, 1),
            _sample(3, "Average", "Weak", 2, 0),
            _sample(4, "Weak", "Strong", 0, 2),
        ]
    )

    match_model = model.predict_match_result_model("Strong", "Weak")

    assert match_model.home_expected_goals > match_model.away_expected_goals
    assert match_model.home_expected_goals >= Decimal("1.50")


def test_team_strength_model_falls_back_for_unknown_team():
    model = train_team_strength_goal_model(
        [
            _sample(1, "Home", "Away", 1, 1),
            _sample(2, "Away", "Home", 0, 1),
        ]
    )

    match_model = model.predict_match_result_model("Unknown", "Away")

    assert match_model.home_expected_goals > Decimal("0")
    assert match_model.away_expected_goals > Decimal("0")


def test_team_strength_model_uses_neutral_strength_for_missing_side_samples():
    model = train_team_strength_goal_model(
        [
            _sample(1, "HomeOnly", "AwayOnly", 2, 1),
            _sample(2, "HomeOnly", "OtherAway", 2, 0),
        ]
    )

    strength = model.team_strengths["HomeOnly"]

    assert strength.away_attack_strength == Decimal("1.00")
    assert strength.away_defense_strength == Decimal("1.00")

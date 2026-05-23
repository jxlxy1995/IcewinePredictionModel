from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.model_training_service import train_league_team_strength_goal_model
from icewine_prediction.training_sample_service import TrainingSample


def _sample(
    match_id: int,
    league: str,
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
        league_name=league,
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


def test_league_team_strength_model_uses_requested_league_context():
    model = train_league_team_strength_goal_model(
        [
            _sample(1, "League A", "Strong", "Weak", 4, 0),
            _sample(2, "League A", "Weak", "Strong", 0, 3),
            _sample(3, "League B", "Strong", "Weak", 1, 1),
            _sample(4, "League B", "Weak", "Strong", 1, 1),
        ]
    )

    league_a = model.predict_match_result_model("League A", "Strong", "Weak")
    league_b = model.predict_match_result_model("League B", "Strong", "Weak")

    assert league_a.home_expected_goals > league_b.home_expected_goals


def test_league_team_strength_model_falls_back_to_global_model_for_unknown_league():
    model = train_league_team_strength_goal_model(
        [
            _sample(1, "League A", "Home", "Away", 2, 1),
            _sample(2, "League A", "Away", "Home", 0, 1),
        ]
    )

    match_model = model.predict_match_result_model("Unknown League", "Home", "Away")

    assert match_model.home_expected_goals > Decimal("0")
    assert match_model.away_expected_goals > Decimal("0")

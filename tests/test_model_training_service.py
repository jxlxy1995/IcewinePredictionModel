from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.model_training_service import (
    BaselineResultProbabilities,
    evaluate_baseline_result_model,
    train_baseline_result_model,
)
from icewine_prediction.training_sample_service import TrainingSample


def _sample(match_id: int, home_score: int, away_score: int, result: str) -> TrainingSample:
    return TrainingSample(
        match_id=match_id,
        source_match_id=str(match_id),
        league_name="La Liga",
        home_team_name="Home",
        away_team_name="Away",
        kickoff_time=datetime(2025, 5, match_id, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_score=home_score,
        away_score=away_score,
        match_result=result,
        total_goals=home_score + away_score,
        asian_handicap_line=None,
        home_handicap_result=None,
        away_handicap_result=None,
        total_line=None,
        over_result=None,
        under_result=None,
        has_odds_snapshot=False,
        sample_age_days=300,
        time_decay_weight=Decimal("0.80"),
    )


def test_train_baseline_result_model_uses_weighted_average_goals():
    model = train_baseline_result_model(
        [
            _sample(1, 2, 1, "home_win"),
            _sample(2, 1, 1, "draw"),
            _sample(3, 0, 2, "away_win"),
        ]
    )

    assert model.home_expected_goals == Decimal("1.00")
    assert model.away_expected_goals == Decimal("1.33")


def test_baseline_result_model_predicts_normalized_probabilities():
    model = train_baseline_result_model(
        [
            _sample(1, 3, 0, "home_win"),
            _sample(2, 2, 1, "home_win"),
            _sample(3, 1, 1, "draw"),
        ]
    )

    probabilities = model.predict_result_probabilities()

    assert isinstance(probabilities, BaselineResultProbabilities)
    assert probabilities.home_win > probabilities.away_win
    assert probabilities.home_win + probabilities.draw + probabilities.away_win == Decimal("1.0000")


def test_baseline_result_model_builds_goal_distribution_for_arbitrary_lines():
    model = train_baseline_result_model(
        [
            _sample(1, 3, 0, "home_win"),
            _sample(2, 2, 1, "home_win"),
            _sample(3, 1, 1, "draw"),
        ]
    )

    prediction = model.predict_goal_distribution()

    assert prediction.home_expected_goals == model.home_expected_goals
    assert prediction.total_goals_probability(Decimal("2.75")).line == Decimal("2.75")
    assert prediction.asian_handicap_probability(Decimal("-0.25")).line == Decimal("-0.25")


def test_evaluate_baseline_result_model_splits_by_time_and_reports_metrics():
    samples = [
        _sample(1, 2, 1, "home_win"),
        _sample(2, 1, 0, "home_win"),
        _sample(3, 0, 1, "away_win"),
        _sample(4, 1, 1, "draw"),
        _sample(5, 2, 0, "home_win"),
    ]

    evaluation = evaluate_baseline_result_model(samples, train_ratio=Decimal("0.80"))

    assert evaluation.train_sample_count == 4
    assert evaluation.validation_sample_count == 1
    assert evaluation.home_expected_goals == Decimal("1.00")
    assert evaluation.away_expected_goals == Decimal("0.75")
    assert Decimal("0.00") <= evaluation.accuracy <= Decimal("1.00")
    assert evaluation.average_log_loss > Decimal("0")

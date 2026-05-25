from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from icewine_prediction.negative_binomial_model_service import (
    NegativeBinomialTotalGoalsModel,
    train_negative_binomial_total_goals_model,
)
from icewine_prediction.training_sample_service import TrainingSample


def _round_probability(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _sample(match_id, total_goals, weight="1.00"):
    home_score = total_goals // 2
    away_score = total_goals - home_score
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
        total_goals=total_goals,
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


def test_negative_binomial_total_goals_probability_decreases_with_line():
    model = NegativeBinomialTotalGoalsModel(
        mean_goals=Decimal("2.60"),
        dispersion=Decimal("0.2500"),
    )

    low_line = model.total_goals_probability(Decimal("1.50"))
    high_line = model.total_goals_probability(Decimal("3.50"))

    assert low_line.over_probability > high_line.over_probability
    assert low_line.under_probability < high_line.under_probability


def test_negative_binomial_total_goals_probability_supports_quarter_lines():
    model = NegativeBinomialTotalGoalsModel(
        mean_goals=Decimal("2.60"),
        dispersion=Decimal("0.2500"),
    )

    quarter = model.total_goals_probability(Decimal("2.25"))
    flat = model.total_goals_probability(Decimal("2.00"))
    half = model.total_goals_probability(Decimal("2.50"))

    assert quarter.over_probability == _round_probability(
        (flat.over_probability + half.over_probability) / Decimal("2")
    )
    assert quarter.under_probability == _round_probability(
        (flat.under_probability + half.under_probability) / Decimal("2")
    )


def test_train_negative_binomial_total_goals_model_estimates_dispersion():
    model = train_negative_binomial_total_goals_model(
        [
            _sample(1, 0),
            _sample(2, 1),
            _sample(3, 2),
            _sample(4, 3),
            _sample(5, 5),
            _sample(6, 7),
        ]
    )

    probability = model.total_goals_probability(Decimal("2.50"))

    assert model.mean_goals > Decimal("0")
    assert model.dispersion >= Decimal("0.0001")
    assert probability.line == Decimal("2.50")
    assert probability.over_probability + probability.under_probability > Decimal("0")

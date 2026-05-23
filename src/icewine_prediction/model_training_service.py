from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from math import exp, factorial, log

from icewine_prediction.training_sample_service import TrainingSample


@dataclass(frozen=True)
class BaselineResultProbabilities:
    home_win: Decimal
    draw: Decimal
    away_win: Decimal


@dataclass(frozen=True)
class BaselineResultModel:
    home_expected_goals: Decimal
    away_expected_goals: Decimal

    def predict_result_probabilities(self) -> BaselineResultProbabilities:
        home_win = Decimal("0")
        draw = Decimal("0")
        away_win = Decimal("0")
        for home_goals in range(9):
            for away_goals in range(9):
                probability = Decimal(
                    str(
                        _poisson_probability(float(self.home_expected_goals), home_goals)
                        * _poisson_probability(float(self.away_expected_goals), away_goals)
                    )
                )
                if home_goals > away_goals:
                    home_win += probability
                elif home_goals == away_goals:
                    draw += probability
                else:
                    away_win += probability
        total = home_win + draw + away_win
        home_win = _round_probability(home_win / total)
        draw = _round_probability(draw / total)
        away_win = Decimal("1.0000") - home_win - draw
        return BaselineResultProbabilities(
            home_win=home_win,
            draw=draw,
            away_win=_round_probability(away_win),
        )


@dataclass(frozen=True)
class BaselineResultEvaluation:
    train_sample_count: int
    validation_sample_count: int
    home_expected_goals: Decimal
    away_expected_goals: Decimal
    accuracy: Decimal
    average_log_loss: Decimal


def _poisson_probability(lam: float, goals: int) -> float:
    return exp(-lam) * lam**goals / factorial(goals)


def _round_decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _round_probability(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def train_baseline_result_model(samples: list[TrainingSample]) -> BaselineResultModel:
    if not samples:
        raise ValueError("baseline result model requires at least one training sample")
    total_weight = sum(sample.time_decay_weight for sample in samples)
    home_goals = sum(Decimal(sample.home_score) * sample.time_decay_weight for sample in samples)
    away_goals = sum(Decimal(sample.away_score) * sample.time_decay_weight for sample in samples)
    return BaselineResultModel(
        home_expected_goals=_round_decimal(home_goals / total_weight),
        away_expected_goals=_round_decimal(away_goals / total_weight),
    )


def _actual_result_key(sample: TrainingSample) -> str:
    if sample.match_result == "home_win":
        return "home_win"
    if sample.match_result == "away_win":
        return "away_win"
    return "draw"


def _probability_for_result(
    probabilities: BaselineResultProbabilities,
    result_key: str,
) -> Decimal:
    if result_key == "home_win":
        return probabilities.home_win
    if result_key == "away_win":
        return probabilities.away_win
    return probabilities.draw


def _predicted_result_key(probabilities: BaselineResultProbabilities) -> str:
    pairs = {
        "home_win": probabilities.home_win,
        "draw": probabilities.draw,
        "away_win": probabilities.away_win,
    }
    return max(pairs, key=pairs.get)


def evaluate_baseline_result_model(
    samples: list[TrainingSample],
    train_ratio: Decimal = Decimal("0.80"),
) -> BaselineResultEvaluation:
    if len(samples) < 2:
        raise ValueError("baseline evaluation requires at least two samples")
    ordered_samples = sorted(samples, key=lambda sample: sample.kickoff_time)
    train_count = max(1, int(len(ordered_samples) * float(train_ratio)))
    if train_count >= len(ordered_samples):
        train_count = len(ordered_samples) - 1
    train_samples = ordered_samples[:train_count]
    validation_samples = ordered_samples[train_count:]
    model = train_baseline_result_model(train_samples)
    probabilities = model.predict_result_probabilities()
    correct = 0
    log_loss_total = 0.0
    predicted_key = _predicted_result_key(probabilities)
    for sample in validation_samples:
        actual_key = _actual_result_key(sample)
        if predicted_key == actual_key:
            correct += 1
        actual_probability = max(
            float(_probability_for_result(probabilities, actual_key)),
            0.000001,
        )
        log_loss_total += -log(actual_probability)
    return BaselineResultEvaluation(
        train_sample_count=len(train_samples),
        validation_sample_count=len(validation_samples),
        home_expected_goals=model.home_expected_goals,
        away_expected_goals=model.away_expected_goals,
        accuracy=_round_probability(Decimal(correct) / Decimal(len(validation_samples))),
        average_log_loss=Decimal(str(log_loss_total / len(validation_samples))).quantize(
            Decimal("0.0001"),
            rounding=ROUND_HALF_UP,
        ),
    )

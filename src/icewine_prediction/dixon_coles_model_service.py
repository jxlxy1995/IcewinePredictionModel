from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from math import exp, factorial, log

from scipy.optimize import minimize_scalar

from icewine_prediction.goal_distribution_service import (
    MAX_GOALS,
    GoalDistributionPrediction,
    build_goal_distribution_prediction_from_scores,
)
from icewine_prediction.training_sample_service import TrainingSample


MIN_RHO = Decimal("-0.2500")
MAX_RHO = Decimal("0.2500")


@dataclass(frozen=True)
class DixonColesGoalModel:
    home_expected_goals: Decimal
    away_expected_goals: Decimal
    rho: Decimal

    def predict_goal_distribution(self) -> GoalDistributionPrediction:
        score_probabilities = {}
        for home_goals in range(MAX_GOALS + 1):
            for away_goals in range(MAX_GOALS + 1):
                probability = Decimal(
                    str(
                        _poisson_probability(float(self.home_expected_goals), home_goals)
                        * _poisson_probability(float(self.away_expected_goals), away_goals)
                        * float(
                            _dixon_coles_tau(
                                home_goals,
                                away_goals,
                                self.home_expected_goals,
                                self.away_expected_goals,
                                self.rho,
                            )
                        )
                    )
                )
                if probability < Decimal("0"):
                    probability = Decimal("0")
                score_probabilities[(home_goals, away_goals)] = probability
        return build_goal_distribution_prediction_from_scores(
            home_expected_goals=self.home_expected_goals,
            away_expected_goals=self.away_expected_goals,
            score_probabilities=score_probabilities,
        )


def train_dixon_coles_goal_model(samples: list[TrainingSample]) -> DixonColesGoalModel:
    if not samples:
        raise ValueError("dixon-coles goal model requires at least one training sample")
    home_expected_goals, away_expected_goals = _weighted_expected_goals(samples)

    def objective(rho: float) -> float:
        return _negative_log_likelihood(
            samples=samples,
            home_expected_goals=home_expected_goals,
            away_expected_goals=away_expected_goals,
            rho=Decimal(str(rho)),
        )

    result = minimize_scalar(
        objective,
        bounds=(float(MIN_RHO), float(MAX_RHO)),
        method="bounded",
    )
    rho = Decimal(str(result.x)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return DixonColesGoalModel(
        home_expected_goals=home_expected_goals,
        away_expected_goals=away_expected_goals,
        rho=max(MIN_RHO, min(MAX_RHO, rho)),
    )


def _weighted_expected_goals(samples: list[TrainingSample]) -> tuple[Decimal, Decimal]:
    total_weight = sum(sample.time_decay_weight for sample in samples)
    home_goals = sum(Decimal(sample.home_score) * sample.time_decay_weight for sample in samples)
    away_goals = sum(Decimal(sample.away_score) * sample.time_decay_weight for sample in samples)
    return (
        _round_expected_goals(home_goals / total_weight),
        _round_expected_goals(away_goals / total_weight),
    )


def _negative_log_likelihood(
    samples: list[TrainingSample],
    home_expected_goals: Decimal,
    away_expected_goals: Decimal,
    rho: Decimal,
) -> float:
    loss = 0.0
    for sample in samples:
        tau = _dixon_coles_tau(
            sample.home_score,
            sample.away_score,
            home_expected_goals,
            away_expected_goals,
            rho,
        )
        if tau <= Decimal("0"):
            return 1_000_000_000.0
        probability = (
            _poisson_probability(float(home_expected_goals), sample.home_score)
            * _poisson_probability(float(away_expected_goals), sample.away_score)
            * float(tau)
        )
        probability = max(probability, 0.000000000001)
        loss += float(sample.time_decay_weight) * -log(probability)
    return loss


def _dixon_coles_tau(
    home_goals: int,
    away_goals: int,
    home_expected_goals: Decimal,
    away_expected_goals: Decimal,
    rho: Decimal,
) -> Decimal:
    if home_goals == 0 and away_goals == 0:
        return Decimal("1") - home_expected_goals * away_expected_goals * rho
    if home_goals == 0 and away_goals == 1:
        return Decimal("1") + home_expected_goals * rho
    if home_goals == 1 and away_goals == 0:
        return Decimal("1") + away_expected_goals * rho
    if home_goals == 1 and away_goals == 1:
        return Decimal("1") - rho
    return Decimal("1")


def _poisson_probability(lam: float, goals: int) -> float:
    return exp(-lam) * lam**goals / factorial(goals)


def _round_expected_goals(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

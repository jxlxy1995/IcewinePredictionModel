from dataclasses import dataclass
from decimal import Decimal
from math import exp, factorial


@dataclass(frozen=True)
class BaselinePrediction:
    home_expected_goals: Decimal
    away_expected_goals: Decimal
    home_asian_handicap_probability: Decimal
    over_probability: Decimal


def _poisson_probability(lam: float, k: int) -> float:
    return exp(-lam) * lam**k / factorial(k)


def _cover_probability(
    home_expected_goals: float,
    away_expected_goals: float,
    asian_handicap: Decimal,
) -> Decimal:
    probability = 0.0
    for home_goals in range(8):
        for away_goals in range(8):
            if home_goals - away_goals + float(asian_handicap) > 0:
                probability += _poisson_probability(
                    home_expected_goals,
                    home_goals,
                ) * _poisson_probability(away_expected_goals, away_goals)
    return Decimal(str(round(probability, 6)))


def _over_probability(
    home_expected_goals: float,
    away_expected_goals: float,
    total_line: Decimal,
) -> Decimal:
    probability = 0.0
    for home_goals in range(8):
        for away_goals in range(8):
            if home_goals + away_goals > float(total_line):
                probability += _poisson_probability(
                    home_expected_goals,
                    home_goals,
                ) * _poisson_probability(away_expected_goals, away_goals)
    return Decimal(str(round(probability, 6)))


def baseline_predict(
    home_attack_strength: Decimal,
    away_attack_strength: Decimal,
    home_defense_strength: Decimal,
    away_defense_strength: Decimal,
    asian_handicap: Decimal,
    total_line: Decimal,
) -> BaselinePrediction:
    home_expected = Decimal("1.35") * home_attack_strength * away_defense_strength
    away_expected = Decimal("1.05") * away_attack_strength * home_defense_strength
    return BaselinePrediction(
        home_expected_goals=home_expected,
        away_expected_goals=away_expected,
        home_asian_handicap_probability=_cover_probability(
            float(home_expected),
            float(away_expected),
            asian_handicap,
        ),
        over_probability=_over_probability(float(home_expected), float(away_expected), total_line),
    )

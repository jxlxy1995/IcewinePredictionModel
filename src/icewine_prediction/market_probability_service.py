from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from math import exp, factorial


@dataclass(frozen=True)
class ScoreProbabilityGrid:
    max_goals: int
    probabilities: dict[tuple[int, int], Decimal]


def _poisson_probability(lam: float, goals: int) -> float:
    return exp(-lam) * lam**goals / factorial(goals)


def _round_probability(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def build_score_probability_grid(
    home_expected_goals: Decimal,
    away_expected_goals: Decimal,
    max_goals: int = 8,
) -> ScoreProbabilityGrid:
    probabilities = {}
    for home_goals in range(max_goals + 1):
        for away_goals in range(max_goals + 1):
            probability = Decimal(
                str(
                    _poisson_probability(float(home_expected_goals), home_goals)
                    * _poisson_probability(float(away_expected_goals), away_goals)
                )
            )
            probabilities[(home_goals, away_goals)] = probability

    total = sum(probabilities.values())
    normalized = {
        score: _round_probability(probability / total)
        for score, probability in probabilities.items()
    }
    rounding_gap = Decimal("1.0000") - sum(normalized.values())
    highest_score = max(normalized, key=normalized.get)
    normalized[highest_score] = _round_probability(normalized[highest_score] + rounding_gap)
    return ScoreProbabilityGrid(max_goals=max_goals, probabilities=normalized)


def _settlement_score(margin: Decimal, line: Decimal) -> Decimal:
    adjusted_margin = margin + line
    if adjusted_margin > Decimal("0"):
        return Decimal("1")
    if adjusted_margin == Decimal("0"):
        return Decimal("0.5")
    return Decimal("0")


def _split_quarter_line(line: Decimal) -> tuple[Decimal, Decimal]:
    doubled = line * Decimal("2")
    lower = doubled.to_integral_value(rounding=ROUND_HALF_UP) / Decimal("2")
    if lower == line:
        return line, line
    if line > lower:
        return lower, lower + Decimal("0.5")
    return lower - Decimal("0.5"), lower


def calculate_asian_handicap_cover_probability(
    grid: ScoreProbabilityGrid,
    line: Decimal,
    side: str,
) -> Decimal:
    first_line, second_line = _split_quarter_line(line)
    if side == "away":
        first_line = -first_line
        second_line = -second_line
    probability = Decimal("0")
    for (home_goals, away_goals), score_probability in grid.probabilities.items():
        margin = Decimal(home_goals - away_goals)
        if side == "away":
            margin = -margin
        settlement = (
            _settlement_score(margin, first_line) + _settlement_score(margin, second_line)
        ) / Decimal("2")
        probability += score_probability * settlement
    return _round_probability(probability)


def calculate_total_goals_probability(
    grid: ScoreProbabilityGrid,
    line: Decimal,
    side: str,
) -> Decimal:
    first_line, second_line = _split_quarter_line(line)
    probability = Decimal("0")
    for (home_goals, away_goals), score_probability in grid.probabilities.items():
        total_goals = Decimal(home_goals + away_goals)
        if side == "over":
            first_settlement = _settlement_score(total_goals, -first_line)
            second_settlement = _settlement_score(total_goals, -second_line)
        else:
            first_settlement = _settlement_score(-total_goals, first_line)
            second_settlement = _settlement_score(-total_goals, second_line)
        probability += score_probability * (first_settlement + second_settlement) / Decimal("2")
    return _round_probability(probability)

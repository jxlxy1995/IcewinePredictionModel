from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from scipy.stats import nbinom

from icewine_prediction.training_sample_service import TrainingSample


MIN_DISPERSION = Decimal("0.0001")
MAX_DISPERSION = Decimal("10.0000")


@dataclass(frozen=True)
class NegativeBinomialTotalGoalsProbability:
    line: Decimal
    over_probability: Decimal
    under_probability: Decimal


@dataclass(frozen=True)
class NegativeBinomialTotalGoalsModel:
    mean_goals: Decimal
    dispersion: Decimal

    def total_goals_probability(self, line: Decimal) -> NegativeBinomialTotalGoalsProbability:
        first_line, second_line = _split_quarter_line(line)
        first = _total_goals_probability(self.mean_goals, self.dispersion, first_line)
        second = _total_goals_probability(self.mean_goals, self.dispersion, second_line)
        return NegativeBinomialTotalGoalsProbability(
            line=line,
            over_probability=_round_probability(
                (first.over_probability + second.over_probability) / Decimal("2")
            ),
            under_probability=_round_probability(
                (first.under_probability + second.under_probability) / Decimal("2")
            ),
        )


def train_negative_binomial_total_goals_model(
    samples: list[TrainingSample],
) -> NegativeBinomialTotalGoalsModel:
    if not samples:
        raise ValueError("negative-binomial total goals model requires at least one sample")
    mean_goals = _weighted_mean_total_goals(samples)
    variance = _weighted_variance_total_goals(samples, mean_goals)
    dispersion = _estimate_dispersion(mean_goals, variance)
    return NegativeBinomialTotalGoalsModel(
        mean_goals=_round_goals(mean_goals),
        dispersion=dispersion,
    )


def _total_goals_probability(
    mean_goals: Decimal,
    dispersion: Decimal,
    line: Decimal,
) -> NegativeBinomialTotalGoalsProbability:
    size, probability = _negative_binomial_parameters(mean_goals, dispersion)
    push_goals = line
    if push_goals == push_goals.to_integral_value():
        total_goals = int(push_goals)
        over_probability = Decimal(str(1 - nbinom.cdf(total_goals, size, probability)))
        under_probability = Decimal(str(nbinom.cdf(total_goals - 1, size, probability)))
        push_probability = Decimal(str(nbinom.pmf(total_goals, size, probability)))
        return NegativeBinomialTotalGoalsProbability(
            line=line,
            over_probability=_round_probability(
                over_probability + push_probability * Decimal("0.5")
            ),
            under_probability=_round_probability(
                under_probability + push_probability * Decimal("0.5")
            ),
        )

    threshold = int(line.to_integral_value(rounding=ROUND_HALF_UP))
    if Decimal(threshold) < line:
        threshold += 1
    over_probability = Decimal(str(1 - nbinom.cdf(threshold - 1, size, probability)))
    under_probability = Decimal(str(nbinom.cdf(threshold - 1, size, probability)))
    return NegativeBinomialTotalGoalsProbability(
        line=line,
        over_probability=_round_probability(over_probability),
        under_probability=_round_probability(under_probability),
    )


def _negative_binomial_parameters(mean_goals: Decimal, dispersion: Decimal) -> tuple[float, float]:
    size = Decimal("1") / dispersion
    probability = size / (size + mean_goals)
    return float(size), float(probability)


def _weighted_mean_total_goals(samples: list[TrainingSample]) -> Decimal:
    total_weight = sum(sample.time_decay_weight for sample in samples)
    total_goals = sum(Decimal(sample.total_goals) * sample.time_decay_weight for sample in samples)
    return total_goals / total_weight


def _weighted_variance_total_goals(
    samples: list[TrainingSample],
    mean_goals: Decimal,
) -> Decimal:
    total_weight = sum(sample.time_decay_weight for sample in samples)
    weighted_squared_gap = sum(
        (Decimal(sample.total_goals) - mean_goals) ** 2 * sample.time_decay_weight
        for sample in samples
    )
    return weighted_squared_gap / total_weight


def _estimate_dispersion(mean_goals: Decimal, variance: Decimal) -> Decimal:
    if mean_goals <= Decimal("0"):
        return MIN_DISPERSION
    raw = (variance - mean_goals) / (mean_goals**2)
    if raw < MIN_DISPERSION:
        return MIN_DISPERSION
    if raw > MAX_DISPERSION:
        return MAX_DISPERSION
    return raw.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _split_quarter_line(line: Decimal) -> tuple[Decimal, Decimal]:
    if _is_quarter_line(line):
        return line - Decimal("0.25"), line + Decimal("0.25")
    return line, line


def _is_quarter_line(line: Decimal) -> bool:
    return abs(line * Decimal("100")) % Decimal("50") == Decimal("25")


def _round_goals(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _round_probability(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

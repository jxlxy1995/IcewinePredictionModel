from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from scipy.stats import skellam


@dataclass(frozen=True)
class SkellamHandicapProbability:
    line: Decimal
    home_cover_probability: Decimal
    away_cover_probability: Decimal


@dataclass(frozen=True)
class SkellamMarginModel:
    home_expected_goals: Decimal
    away_expected_goals: Decimal

    def margin_probability(self, margin: int) -> Decimal:
        return _round_probability(
            Decimal(str(skellam.pmf(margin, self._home_mean(), self._away_mean())))
        )

    def home_win_probability(self) -> Decimal:
        return _round_probability(
            Decimal(str(1 - skellam.cdf(0, self._home_mean(), self._away_mean())))
        )

    def away_win_probability(self) -> Decimal:
        return _round_probability(
            Decimal(str(skellam.cdf(-1, self._home_mean(), self._away_mean())))
        )

    def home_cover_probability(self, line: Decimal) -> Decimal:
        first_line, second_line = _split_quarter_line(line)
        first = _cover_probability(
            home_expected_goals=self._home_mean(),
            away_expected_goals=self._away_mean(),
            line=first_line,
            side="home",
        )
        second = _cover_probability(
            home_expected_goals=self._home_mean(),
            away_expected_goals=self._away_mean(),
            line=second_line,
            side="home",
        )
        return _round_probability((first + second) / Decimal("2"))

    def away_cover_probability(self, line: Decimal) -> Decimal:
        first_line, second_line = _split_quarter_line(line)
        first = _cover_probability(
            home_expected_goals=self._home_mean(),
            away_expected_goals=self._away_mean(),
            line=first_line,
            side="away",
        )
        second = _cover_probability(
            home_expected_goals=self._home_mean(),
            away_expected_goals=self._away_mean(),
            line=second_line,
            side="away",
        )
        return _round_probability((first + second) / Decimal("2"))

    def asian_handicap_probability(self, line: Decimal) -> SkellamHandicapProbability:
        return SkellamHandicapProbability(
            line=line,
            home_cover_probability=self.home_cover_probability(line),
            away_cover_probability=self.away_cover_probability(line),
        )

    def _home_mean(self) -> float:
        return float(self.home_expected_goals)

    def _away_mean(self) -> float:
        return float(self.away_expected_goals)


def _cover_probability(
    home_expected_goals: float,
    away_expected_goals: float,
    line: Decimal,
    side: str,
) -> Decimal:
    if side == "home":
        return _settlement_probability(home_expected_goals, away_expected_goals, line)
    return _settlement_probability(away_expected_goals, home_expected_goals, -line)


def _settlement_probability(
    first_expected_goals: float,
    second_expected_goals: float,
    line: Decimal,
) -> Decimal:
    push_margin = -line
    win_threshold = -line
    if push_margin == push_margin.to_integral_value():
        margin = int(push_margin)
        win_probability = Decimal(
            str(1 - skellam.cdf(margin, first_expected_goals, second_expected_goals))
        )
        push_probability = Decimal(str(skellam.pmf(margin, first_expected_goals, second_expected_goals)))
        return _round_probability(win_probability + push_probability * Decimal("0.5"))

    floor_margin = int(win_threshold.to_integral_value(rounding=ROUND_HALF_UP))
    if Decimal(floor_margin) < win_threshold:
        floor_margin += 1
    win_probability = Decimal(
        str(1 - skellam.cdf(floor_margin - 1, first_expected_goals, second_expected_goals))
    )
    return _round_probability(win_probability)


def _split_quarter_line(line: Decimal) -> tuple[Decimal, Decimal]:
    if _is_quarter_line(line):
        return line - Decimal("0.25"), line + Decimal("0.25")
    return line, line


def _is_quarter_line(line: Decimal) -> bool:
    return abs(line * Decimal("100")) % Decimal("50") == Decimal("25")


def _round_probability(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

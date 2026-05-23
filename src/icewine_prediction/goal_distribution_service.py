from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from math import exp, factorial


MAX_GOALS = 10


@dataclass(frozen=True)
class TotalGoalsProbability:
    line: Decimal
    over_probability: Decimal
    under_probability: Decimal


@dataclass(frozen=True)
class AsianHandicapProbability:
    line: Decimal
    home_cover_probability: Decimal
    away_cover_probability: Decimal


@dataclass(frozen=True)
class GoalDistributionPrediction:
    home_expected_goals: Decimal
    away_expected_goals: Decimal
    score_probabilities: dict[tuple[int, int], Decimal]
    home_win_probability: Decimal
    draw_probability: Decimal
    away_win_probability: Decimal

    def score_probability(self, home_goals: int, away_goals: int) -> Decimal:
        return self.score_probabilities.get((home_goals, away_goals), Decimal("0.0000"))

    def total_goals_probability(self, line: Decimal) -> TotalGoalsProbability:
        if _is_quarter_line(line):
            lower_line, upper_line = _split_quarter_line(line)
            lower = self.total_goals_probability(lower_line)
            upper = self.total_goals_probability(upper_line)
            return TotalGoalsProbability(
                line=line,
                over_probability=_round_probability(
                    (lower.over_probability + upper.over_probability) / Decimal("2")
                ),
                under_probability=_round_probability(
                    (lower.under_probability + upper.under_probability) / Decimal("2")
                ),
            )
        over_probability = Decimal("0")
        under_probability = Decimal("0")
        for (home_goals, away_goals), probability in self.score_probabilities.items():
            total_goals = Decimal(home_goals + away_goals)
            if total_goals > line:
                over_probability += probability
            elif total_goals < line:
                under_probability += probability
        return _normalize_total_probability(line, over_probability, under_probability)

    def asian_handicap_probability(self, line: Decimal) -> AsianHandicapProbability:
        if _is_quarter_line(line):
            lower_line, upper_line = _split_quarter_line(line)
            lower = self.asian_handicap_probability(lower_line)
            upper = self.asian_handicap_probability(upper_line)
            return AsianHandicapProbability(
                line=line,
                home_cover_probability=_round_probability(
                    (lower.home_cover_probability + upper.home_cover_probability) / Decimal("2")
                ),
                away_cover_probability=_round_probability(
                    (lower.away_cover_probability + upper.away_cover_probability) / Decimal("2")
                ),
            )
        home_cover_probability = Decimal("0")
        away_cover_probability = Decimal("0")
        for (home_goals, away_goals), probability in self.score_probabilities.items():
            margin = Decimal(home_goals - away_goals) + line
            if margin > 0:
                home_cover_probability += probability
            elif margin < 0:
                away_cover_probability += probability
        return _normalize_handicap_probability(line, home_cover_probability, away_cover_probability)


def build_goal_distribution_prediction(
    home_expected_goals: Decimal,
    away_expected_goals: Decimal,
) -> GoalDistributionPrediction:
    raw_scores = {
        (home_goals, away_goals): Decimal(
            str(
                _poisson_probability(float(home_expected_goals), home_goals)
                * _poisson_probability(float(away_expected_goals), away_goals)
            )
        )
        for home_goals in range(MAX_GOALS + 1)
        for away_goals in range(MAX_GOALS + 1)
    }
    total_probability = sum(raw_scores.values())
    score_probabilities = {
        score: _round_probability(probability / total_probability)
        for score, probability in raw_scores.items()
    }
    home_win = Decimal("0")
    draw = Decimal("0")
    away_win = Decimal("0")
    for (home_goals, away_goals), probability in score_probabilities.items():
        if home_goals > away_goals:
            home_win += probability
        elif home_goals == away_goals:
            draw += probability
        else:
            away_win += probability
    return _build_normalized_prediction(
        home_expected_goals=home_expected_goals,
        away_expected_goals=away_expected_goals,
        score_probabilities=score_probabilities,
        home_win=home_win,
        draw=draw,
        away_win=away_win,
    )


def _build_normalized_prediction(
    home_expected_goals: Decimal,
    away_expected_goals: Decimal,
    score_probabilities: dict[tuple[int, int], Decimal],
    home_win: Decimal,
    draw: Decimal,
    away_win: Decimal,
) -> GoalDistributionPrediction:
    home_win = _round_probability(home_win)
    draw = _round_probability(draw)
    away_win = Decimal("1.0000") - home_win - draw
    return GoalDistributionPrediction(
        home_expected_goals=home_expected_goals,
        away_expected_goals=away_expected_goals,
        score_probabilities=score_probabilities,
        home_win_probability=home_win,
        draw_probability=draw,
        away_win_probability=_round_probability(away_win),
    )


def _poisson_probability(lam: float, goals: int) -> float:
    return exp(-lam) * lam**goals / factorial(goals)


def _round_probability(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _is_quarter_line(line: Decimal) -> bool:
    return abs(line * Decimal("100")) % Decimal("50") == Decimal("25")


def _split_quarter_line(line: Decimal) -> tuple[Decimal, Decimal]:
    if line >= 0:
        return line - Decimal("0.25"), line + Decimal("0.25")
    return line - Decimal("0.25"), line + Decimal("0.25")


def _normalize_total_probability(
    line: Decimal,
    over_probability: Decimal,
    under_probability: Decimal,
) -> TotalGoalsProbability:
    total = over_probability + under_probability
    if total == Decimal("0"):
        return TotalGoalsProbability(line=line, over_probability=Decimal("0"), under_probability=Decimal("0"))
    over_probability = _round_probability(over_probability / total)
    under_probability = Decimal("1.0000") - over_probability
    return TotalGoalsProbability(
        line=line,
        over_probability=over_probability,
        under_probability=_round_probability(under_probability),
    )


def _normalize_handicap_probability(
    line: Decimal,
    home_cover_probability: Decimal,
    away_cover_probability: Decimal,
) -> AsianHandicapProbability:
    total = home_cover_probability + away_cover_probability
    if total == Decimal("0"):
        return AsianHandicapProbability(
            line=line,
            home_cover_probability=Decimal("0"),
            away_cover_probability=Decimal("0"),
        )
    home_cover_probability = _round_probability(home_cover_probability / total)
    away_cover_probability = Decimal("1.0000") - home_cover_probability
    return AsianHandicapProbability(
        line=line,
        home_cover_probability=home_cover_probability,
        away_cover_probability=_round_probability(away_cover_probability),
    )

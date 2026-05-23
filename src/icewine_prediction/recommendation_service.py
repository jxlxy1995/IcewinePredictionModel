from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Recommendation:
    market_type: str
    side: str
    confidence_grade: str
    stake_units: Decimal
    should_bet: bool
    edge: Decimal
    risk_tags: list[str]


GRADE_ORDER = ["D", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+", "S-", "S", "S+"]
GRADE_STAKE_UNITS = {
    "D": Decimal("0"),
    "C-": Decimal("0.50"),
    "C": Decimal("0.50"),
    "C+": Decimal("0.75"),
    "B-": Decimal("1.00"),
    "B": Decimal("1.25"),
    "B+": Decimal("1.50"),
    "A-": Decimal("1.75"),
    "A": Decimal("2.00"),
    "A+": Decimal("2.25"),
    "S-": Decimal("2.50"),
    "S": Decimal("2.75"),
    "S+": Decimal("3.00"),
}


def _base_grade(edge: Decimal, similar_backtest_roi: Decimal) -> str:
    if edge < Decimal("0.025") or similar_backtest_roi < Decimal("0.02"):
        return "D"
    if edge < Decimal("0.045"):
        return "C+"
    if edge < Decimal("0.080"):
        return "B"
    if edge < Decimal("0.115"):
        return "A-"
    return "A+"


def _downgrade_grade(grade: str, steps: int) -> str:
    index = GRADE_ORDER.index(grade)
    return GRADE_ORDER[max(0, index - steps)]


def build_recommendation_from_signal(
    market_type: str,
    side: str,
    model_probability: Decimal,
    market_implied_probability: Decimal,
    similar_backtest_roi: Decimal,
    risk_tags: list[str],
) -> Recommendation:
    edge = model_probability - market_implied_probability
    grade = _base_grade(edge, similar_backtest_roi)
    if risk_tags and grade != "D":
        grade = _downgrade_grade(grade, len(risk_tags))
    stake_units = GRADE_STAKE_UNITS[grade]
    return Recommendation(
        market_type=market_type,
        side=side,
        confidence_grade=grade,
        stake_units=stake_units,
        should_bet=stake_units >= Decimal("0.50"),
        edge=edge,
        risk_tags=risk_tags,
    )

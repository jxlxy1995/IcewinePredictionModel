from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from icewine_prediction.feature_service import MatchOddsFeatures


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


def _watch_recommendation(market_type: str, risk_tags: list[str]) -> Recommendation:
    return Recommendation(
        market_type=market_type,
        side="watch",
        confidence_grade="D",
        stake_units=Decimal("0"),
        should_bet=False,
        edge=Decimal("0"),
        risk_tags=risk_tags,
    )


def _odds_gap_edge(first_odds: Decimal, second_odds: Decimal) -> Decimal:
    gap = abs(first_odds - second_odds)
    return (gap / Decimal("4")).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def _build_market_rule_recommendation(
    market_type: str,
    favored_side: str,
    first_odds: Decimal | None,
    second_odds: Decimal | None,
    disagreement: Decimal | None,
    disagreement_limit: Decimal,
    low_sample: bool,
    high_disagreement_tag: str,
) -> Recommendation:
    risk_tags = []
    if low_sample:
        risk_tags.append("low_bookmaker_count")
    if disagreement is None or disagreement > disagreement_limit:
        risk_tags.append(high_disagreement_tag)
    if first_odds is None or second_odds is None:
        risk_tags.append("missing_market_odds")
    if risk_tags:
        return _watch_recommendation(market_type, risk_tags)

    odds_gap = abs(first_odds - second_odds)
    if odds_gap < Decimal("0.12"):
        return _watch_recommendation(market_type, ["weak_market_signal"])

    edge = _odds_gap_edge(first_odds, second_odds)
    return build_recommendation_from_signal(
        market_type=market_type,
        side=favored_side,
        model_probability=Decimal("0.50") + edge,
        market_implied_probability=Decimal("0.50"),
        similar_backtest_roi=Decimal("0.05"),
        risk_tags=[],
    )


def build_rule_recommendations_from_features(
    features: MatchOddsFeatures,
) -> list[Recommendation]:
    low_sample = features.bookmaker_count < 6
    if features.home_odds.mean is not None and features.away_odds.mean is not None:
        handicap_side = "home" if features.home_odds.mean < features.away_odds.mean else "away"
    else:
        handicap_side = "watch"
    if features.over_odds.mean is not None and features.under_odds.mean is not None:
        total_side = "over" if features.over_odds.mean < features.under_odds.mean else "under"
    else:
        total_side = "watch"

    return [
        _build_market_rule_recommendation(
            market_type="asian_handicap",
            favored_side=handicap_side,
            first_odds=features.home_odds.mean,
            second_odds=features.away_odds.mean,
            disagreement=features.asian_handicap.disagreement,
            disagreement_limit=Decimal("1.00"),
            low_sample=low_sample,
            high_disagreement_tag="handicap_disagreement_high",
        ),
        _build_market_rule_recommendation(
            market_type="total_goals",
            favored_side=total_side,
            first_odds=features.over_odds.mean,
            second_odds=features.under_odds.mean,
            disagreement=features.total_line.disagreement,
            disagreement_limit=Decimal("0.75"),
            low_sample=low_sample,
            high_disagreement_tag="total_disagreement_high",
        ),
    ]

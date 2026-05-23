from decimal import Decimal

from icewine_prediction.recommendation_service import build_recommendation_from_signal


def test_low_edge_does_not_bet():
    recommendation = build_recommendation_from_signal(
        market_type="asian_handicap",
        side="home",
        model_probability=Decimal("0.515"),
        market_implied_probability=Decimal("0.505"),
        similar_backtest_roi=Decimal("0.01"),
        risk_tags=[],
    )

    assert recommendation.confidence_grade == "D"
    assert recommendation.stake_units == Decimal("0")
    assert recommendation.should_bet is False


def test_medium_edge_generates_b_grade_recommendation():
    recommendation = build_recommendation_from_signal(
        market_type="total_goals",
        side="over",
        model_probability=Decimal("0.570"),
        market_implied_probability=Decimal("0.505"),
        similar_backtest_roi=Decimal("0.06"),
        risk_tags=[],
    )

    assert recommendation.confidence_grade == "B"
    assert recommendation.stake_units == Decimal("1.25")
    assert recommendation.should_bet is True


def test_risk_tag_downgrades_recommendation():
    recommendation = build_recommendation_from_signal(
        market_type="asian_handicap",
        side="away",
        model_probability=Decimal("0.610"),
        market_implied_probability=Decimal("0.505"),
        similar_backtest_roi=Decimal("0.08"),
        risk_tags=["sharp_late_line_move"],
    )

    assert recommendation.confidence_grade == "B+"
    assert recommendation.stake_units == Decimal("1.50")

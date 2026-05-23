from decimal import Decimal, ROUND_HALF_UP

from icewine_prediction.goal_distribution_service import build_goal_distribution_prediction


def _round_probability(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def test_goal_distribution_prediction_returns_normalized_result_probabilities():
    prediction = build_goal_distribution_prediction(
        home_expected_goals=Decimal("1.50"),
        away_expected_goals=Decimal("1.00"),
    )

    assert prediction.home_expected_goals == Decimal("1.50")
    assert prediction.away_expected_goals == Decimal("1.00")
    assert prediction.home_win_probability > prediction.away_win_probability
    assert (
        prediction.home_win_probability
        + prediction.draw_probability
        + prediction.away_win_probability
    ) == Decimal("1.0000")
    assert prediction.score_probability(1, 0) > Decimal("0")


def test_goal_distribution_prediction_supports_arbitrary_total_lines():
    prediction = build_goal_distribution_prediction(
        home_expected_goals=Decimal("1.50"),
        away_expected_goals=Decimal("1.00"),
    )

    low_line = prediction.total_goals_probability(Decimal("1.50"))
    high_line = prediction.total_goals_probability(Decimal("3.50"))

    assert low_line.over_probability > high_line.over_probability
    assert low_line.line == Decimal("1.50")
    assert low_line.over_probability + low_line.under_probability == Decimal("1.0000")


def test_goal_distribution_prediction_supports_quarter_total_lines():
    prediction = build_goal_distribution_prediction(
        home_expected_goals=Decimal("1.50"),
        away_expected_goals=Decimal("1.00"),
    )

    quarter = prediction.total_goals_probability(Decimal("2.25"))
    flat = prediction.total_goals_probability(Decimal("2.00"))
    half = prediction.total_goals_probability(Decimal("2.50"))

    assert quarter.over_probability == (flat.over_probability + half.over_probability) / Decimal("2")
    assert quarter.under_probability == (flat.under_probability + half.under_probability) / Decimal("2")


def test_goal_distribution_prediction_supports_arbitrary_asian_handicap_lines():
    prediction = build_goal_distribution_prediction(
        home_expected_goals=Decimal("1.60"),
        away_expected_goals=Decimal("1.10"),
    )

    home_plus_half = prediction.asian_handicap_probability(Decimal("0.50"))
    home_minus_half = prediction.asian_handicap_probability(Decimal("-0.50"))

    assert home_plus_half.home_cover_probability > home_minus_half.home_cover_probability
    assert home_plus_half.away_cover_probability < home_minus_half.away_cover_probability
    assert home_plus_half.line == Decimal("0.50")


def test_goal_distribution_prediction_supports_quarter_asian_handicap_lines():
    prediction = build_goal_distribution_prediction(
        home_expected_goals=Decimal("1.60"),
        away_expected_goals=Decimal("1.10"),
    )

    quarter = prediction.asian_handicap_probability(Decimal("-0.25"))
    level = prediction.asian_handicap_probability(Decimal("0.00"))
    half = prediction.asian_handicap_probability(Decimal("-0.50"))

    assert quarter.home_cover_probability == _round_probability(
        (level.home_cover_probability + half.home_cover_probability) / Decimal("2")
    )
    assert quarter.away_cover_probability == _round_probability(
        (level.away_cover_probability + half.away_cover_probability) / Decimal("2")
    )

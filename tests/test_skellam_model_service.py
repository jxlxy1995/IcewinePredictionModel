from decimal import Decimal, ROUND_HALF_UP

from icewine_prediction.skellam_model_service import SkellamMarginModel


def _round_probability(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def test_skellam_margin_model_favors_stronger_home_team():
    model = SkellamMarginModel(
        home_expected_goals=Decimal("1.70"),
        away_expected_goals=Decimal("0.90"),
    )

    assert model.margin_probability(1) > model.margin_probability(-1)
    assert model.home_win_probability() > model.away_win_probability()


def test_skellam_handicap_probability_supports_half_lines():
    model = SkellamMarginModel(
        home_expected_goals=Decimal("1.50"),
        away_expected_goals=Decimal("1.10"),
    )

    level = model.home_cover_probability(Decimal("0.00"))
    minus_half = model.home_cover_probability(Decimal("-0.50"))

    assert level > minus_half
    assert Decimal("0") < minus_half < Decimal("1")


def test_skellam_handicap_probability_supports_quarter_lines():
    model = SkellamMarginModel(
        home_expected_goals=Decimal("1.50"),
        away_expected_goals=Decimal("1.10"),
    )

    quarter = model.home_cover_probability(Decimal("-0.25"))
    level = model.home_cover_probability(Decimal("0.00"))
    minus_half = model.home_cover_probability(Decimal("-0.50"))

    assert quarter == _round_probability((level + minus_half) / Decimal("2"))


def test_skellam_asian_handicap_probability_returns_both_sides():
    model = SkellamMarginModel(
        home_expected_goals=Decimal("1.50"),
        away_expected_goals=Decimal("1.10"),
    )

    probability = model.asian_handicap_probability(Decimal("-0.25"))

    assert probability.line == Decimal("-0.25")
    assert probability.home_cover_probability == model.home_cover_probability(Decimal("-0.25"))
    assert probability.away_cover_probability == model.away_cover_probability(Decimal("-0.25"))
    assert probability.home_cover_probability + probability.away_cover_probability > Decimal("0")

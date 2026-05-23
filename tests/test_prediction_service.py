from decimal import Decimal

from icewine_prediction.prediction_service import baseline_predict


def test_baseline_prediction_returns_asian_handicap_and_total_probabilities():
    prediction = baseline_predict(
        home_attack_strength=Decimal("1.30"),
        away_attack_strength=Decimal("1.00"),
        home_defense_strength=Decimal("0.95"),
        away_defense_strength=Decimal("1.10"),
        asian_handicap=Decimal("-0.25"),
        total_line=Decimal("2.50"),
    )

    assert Decimal("0") <= prediction.home_asian_handicap_probability <= Decimal("1")
    assert Decimal("0") <= prediction.over_probability <= Decimal("1")
    assert prediction.home_expected_goals > Decimal("0")
    assert prediction.away_expected_goals > Decimal("0")

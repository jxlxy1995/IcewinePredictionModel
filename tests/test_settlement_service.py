from decimal import Decimal

from icewine_prediction.settlement_service import settle_asian_handicap, settle_total_goals


def test_home_minus_half_wins_when_home_team_wins():
    result = settle_asian_handicap(home_score=2, away_score=1, line=Decimal("-0.50"), side="home")

    assert result == "win"


def test_home_minus_quarter_loses_half_when_home_team_draws():
    result = settle_asian_handicap(home_score=1, away_score=1, line=Decimal("-0.25"), side="home")

    assert result == "half_loss"


def test_over_two_and_half_wins_with_three_total_goals():
    result = settle_total_goals(home_score=2, away_score=1, line=Decimal("2.50"), side="over")

    assert result == "win"


def test_over_three_pushes_with_three_total_goals():
    result = settle_total_goals(home_score=2, away_score=1, line=Decimal("3.00"), side="over")

    assert result == "push"

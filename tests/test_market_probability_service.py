from decimal import Decimal

from icewine_prediction.market_probability_service import (
    ScoreProbabilityGrid,
    build_score_probability_grid,
    calculate_asian_handicap_cover_probability,
    calculate_total_goals_probability,
)


def test_score_probability_grid_is_normalized():
    grid = build_score_probability_grid(
        home_expected_goals=Decimal("1.50"),
        away_expected_goals=Decimal("1.10"),
    )

    assert grid.max_goals == 8
    assert sum(grid.probabilities.values()) == Decimal("1.0000")
    assert grid.probabilities[(1, 1)] > Decimal("0")


def test_total_goals_probability_handles_half_line():
    grid = build_score_probability_grid(
        home_expected_goals=Decimal("1.80"),
        away_expected_goals=Decimal("1.20"),
    )

    probability = calculate_total_goals_probability(grid, line=Decimal("2.5"), side="over")

    assert probability > Decimal("0.50")


def test_asian_handicap_cover_probability_handles_quarter_line():
    grid = build_score_probability_grid(
        home_expected_goals=Decimal("1.70"),
        away_expected_goals=Decimal("1.00"),
    )

    probability = calculate_asian_handicap_cover_probability(
        grid,
        line=Decimal("-0.25"),
        side="home",
    )

    assert probability > Decimal("0.50")


def test_asian_handicap_away_side_uses_opposite_line_consistently():
    grid = build_score_probability_grid(
        home_expected_goals=Decimal("1.40"),
        away_expected_goals=Decimal("1.40"),
    )

    home_probability = calculate_asian_handicap_cover_probability(
        grid,
        line=Decimal("-0.5"),
        side="home",
    )
    away_probability = calculate_asian_handicap_cover_probability(
        grid,
        line=Decimal("-0.5"),
        side="away",
    )

    assert home_probability + away_probability == Decimal("1.0000")


def test_asian_handicap_away_side_does_not_mutate_line_between_scores():
    grid = ScoreProbabilityGrid(
        max_goals=1,
        probabilities={
            (1, 0): Decimal("0.5000"),
            (0, 0): Decimal("0.5000"),
        },
    )

    probability = calculate_asian_handicap_cover_probability(
        grid,
        line=Decimal("-0.5"),
        side="away",
    )

    assert probability == Decimal("0.5000")

from decimal import Decimal

from icewine_prediction.baseline_execution_robustness_grid_service import (
    ExecutionRobustnessGridRow,
    ExecutionRobustnessGridRule,
    _grid_row_for_rule,
    _top_grid_rows,
)
from icewine_prediction.baseline_execution_robustness_service import (
    ExecutionRobustnessCandidateProfile,
)
from icewine_prediction.baseline_recommendation_sandbox_service import SandboxCandidate
from icewine_prediction.paper_strategy_registry import DEFAULT_STRATEGY


def test_grid_row_filters_profiles_by_stability_rule():
    profiles = [
        _profile("stable-win", "1.00", seen_count=5, min_edge="0.1000"),
        _profile(
            "bucket-loss",
            "-1.00",
            seen_count=4,
            min_edge="0.0900",
            bucket_changed=True,
        ),
        _profile(
            "side-win",
            "0.80",
            seen_count=5,
            min_edge="0.1200",
            side_changed=True,
        ),
        _profile("low-edge-loss", "-1.00", seen_count=5, min_edge="0.0300"),
    ]

    row = _grid_row_for_rule(
        strategy=DEFAULT_STRATEGY,
        primary_target=15,
        profiles=profiles,
        rule=ExecutionRobustnessGridRule(
            min_seen_count=4,
            min_edge=Decimal("0.0800"),
            allow_bucket_changed=False,
            allow_line_changed=True,
            require_side_unchanged=True,
        ),
    )

    assert row.candidate_count == 1
    assert row.wins == 1
    assert row.profit == Decimal("1.0000")
    assert row.roi == Decimal("1.0000")
    assert row.hit_rate == Decimal("1.0000")
    assert row.average_seen_count == Decimal("5.0000")
    assert row.average_min_edge == Decimal("0.1000")


def test_grid_row_can_allow_side_and_bucket_instability_for_comparison():
    profiles = [
        _profile("stable-win", "1.00", seen_count=5, min_edge="0.1000"),
        _profile(
            "bucket-loss",
            "-1.00",
            seen_count=4,
            min_edge="0.0900",
            bucket_changed=True,
        ),
        _profile(
            "side-win",
            "0.80",
            seen_count=5,
            min_edge="0.1200",
            side_changed=True,
        ),
    ]

    row = _grid_row_for_rule(
        strategy=DEFAULT_STRATEGY,
        primary_target=15,
        profiles=profiles,
        rule=ExecutionRobustnessGridRule(
            min_seen_count=4,
            min_edge=Decimal("0.0800"),
            allow_bucket_changed=True,
            allow_line_changed=True,
            require_side_unchanged=False,
        ),
    )

    assert row.candidate_count == 3
    assert row.wins == 2
    assert row.profit == Decimal("0.8000")
    assert row.roi == Decimal("0.2667")
    assert row.hit_rate == Decimal("0.6667")


def test_top_grid_rows_deduplicates_equivalent_rule_results():
    first = _grid_row(
        min_seen_count=4,
        min_edge="0.0800",
        allow_bucket_changed=False,
        allow_line_changed=True,
    )
    duplicate = _grid_row(
        min_seen_count=4,
        min_edge="0.0800",
        allow_bucket_changed=True,
        allow_line_changed=True,
    )
    second = _grid_row(
        min_seen_count=3,
        min_edge="0.0800",
        allow_bucket_changed=False,
        allow_line_changed=True,
        candidate_count=20,
        profit="3.0000",
        roi="0.1500",
    )

    top_rows = _top_grid_rows(
        [first, duplicate, second],
        min_candidate_count=10,
        top_n_per_strategy=5,
    )

    assert top_rows == [first, second]


def _profile(
    match_id: str,
    profit: str,
    *,
    seen_count: int,
    min_edge: str,
    side_changed: bool = False,
    bucket_changed: bool = False,
    line_changed: bool = False,
) -> ExecutionRobustnessCandidateProfile:
    candidate = SandboxCandidate(
        match_id=match_id,
        kickoff_time="2026-05-20T20:00:00+00:00",
        league_name="League",
        home_team_name="Home",
        away_team_name="Away",
        market_type="asian_handicap",
        line=Decimal("-0.50"),
        side="away_cover",
        odds=Decimal("2.00"),
        model_probability=Decimal("0.6000"),
        market_probability=Decimal("0.5000"),
        edge=Decimal("0.1200"),
        actual_side="away_cover" if Decimal(profit) >= 0 else "home_cover",
        profit=Decimal(profit),
    )
    return ExecutionRobustnessCandidateProfile(
        strategy_key=DEFAULT_STRATEGY.strategy_key,
        match_id=match_id,
        market_type="asian_handicap",
        primary_candidate=candidate,
        level="candidate",
        seen_count=seen_count,
        total_points=5,
        min_edge=Decimal(min_edge),
        max_edge=Decimal("0.1500"),
        edge_range=Decimal("0.0500"),
        side_changed=side_changed,
        line_changed=line_changed,
        bucket_changed=bucket_changed,
        observed_targets=(25, 20, 15, 10, 5),
    )


def _grid_row(
    *,
    min_seen_count: int,
    min_edge: str,
    allow_bucket_changed: bool,
    allow_line_changed: bool,
    candidate_count: int = 12,
    profit: str = "3.0000",
    roi: str = "0.2500",
) -> ExecutionRobustnessGridRow:
    return ExecutionRobustnessGridRow(
        strategy_key=DEFAULT_STRATEGY.strategy_key,
        display_name=DEFAULT_STRATEGY.display_name,
        primary_target=15,
        min_seen_count=min_seen_count,
        min_edge=Decimal(min_edge),
        allow_bucket_changed=allow_bucket_changed,
        allow_line_changed=allow_line_changed,
        require_side_unchanged=True,
        candidate_count=candidate_count,
        wins=8,
        profit=Decimal(profit),
        roi=Decimal(roi),
        hit_rate=Decimal("0.6667"),
        average_seen_count=Decimal("4.5000"),
        average_min_edge=Decimal("0.1000"),
    )

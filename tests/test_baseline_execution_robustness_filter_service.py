from decimal import Decimal

from icewine_prediction.baseline_execution_robustness_filter_service import (
    SelectedExecutionRobustnessRule,
    build_baseline_execution_robustness_filter_report_from_reports,
    format_baseline_execution_robustness_filter_report,
)
from icewine_prediction.baseline_execution_robustness_service import (
    BaselineExecutionRobustnessReport,
    ExecutionRobustnessCandidateProfile,
)
from icewine_prediction.baseline_recommendation_sandbox_service import SandboxCandidate
from icewine_prediction.paper_strategy_registry import DEFAULT_STRATEGY


def test_filter_report_splits_raw_kept_and_filtered_profiles():
    report = _source_report(
        [
            _profile("stable-win", "1.00", seen_count=5, min_edge="0.1000"),
            _profile("low-edge-loss", "-1.00", seen_count=5, min_edge="0.0300"),
            _profile("side-win", "0.80", seen_count=5, min_edge="0.1200", side_changed=True),
        ]
    )

    result = build_baseline_execution_robustness_filter_report_from_reports(
        [report],
        selected_rules={
            DEFAULT_STRATEGY.strategy_key: SelectedExecutionRobustnessRule(
                strategy_key=DEFAULT_STRATEGY.strategy_key,
                primary_target=15,
                min_seen_count=4,
                min_edge=Decimal("0.0800"),
                allow_bucket_changed=False,
                allow_line_changed=True,
                require_side_unchanged=True,
                mode="filter",
            )
        },
    )

    summary = result.strategy_summaries[0]
    assert summary.raw_count == 3
    assert summary.raw_wins == 2
    assert summary.raw_profit == Decimal("0.8000")
    assert summary.raw_roi == Decimal("0.2667")
    assert summary.raw_hit_rate == Decimal("0.6667")
    assert summary.kept_count == 1
    assert summary.kept_wins == 1
    assert summary.kept_profit == Decimal("1.0000")
    assert summary.kept_roi == Decimal("1.0000")
    assert summary.kept_hit_rate == Decimal("1.0000")
    assert summary.filtered_count == 2
    assert summary.filtered_profit == Decimal("-0.2000")
    assert summary.filtered_roi == Decimal("-0.1000")
    assert summary.filtered_hit_rate == Decimal("0.5000")


def test_observe_mode_keeps_all_profiles_without_filtering():
    report = _source_report(
        [
            _profile("stable-win", "1.00", seen_count=5, min_edge="0.1000"),
            _profile("loss", "-1.00", seen_count=1, min_edge="0.0200"),
        ]
    )

    result = build_baseline_execution_robustness_filter_report_from_reports(
        [report],
        selected_rules={
            DEFAULT_STRATEGY.strategy_key: SelectedExecutionRobustnessRule(
                strategy_key=DEFAULT_STRATEGY.strategy_key,
                primary_target=15,
                min_seen_count=4,
                min_edge=Decimal("0.0800"),
                allow_bucket_changed=False,
                allow_line_changed=True,
                require_side_unchanged=True,
                mode="observe",
            )
        },
    )

    summary = result.strategy_summaries[0]
    assert summary.raw_count == 2
    assert summary.kept_count == 2
    assert summary.filtered_count == 0
    assert summary.mode == "observe"


def test_format_filter_report_includes_raw_kept_filtered_metrics():
    report = build_baseline_execution_robustness_filter_report_from_reports(
        [_source_report([_profile("stable-win", "1.00", seen_count=5, min_edge="0.1000")])],
        selected_rules={
            DEFAULT_STRATEGY.strategy_key: SelectedExecutionRobustnessRule(
                strategy_key=DEFAULT_STRATEGY.strategy_key,
                primary_target=15,
                min_seen_count=4,
                min_edge=Decimal("0.0800"),
                allow_bucket_changed=False,
                allow_line_changed=True,
                require_side_unchanged=True,
                mode="filter",
            )
        },
    )

    text = format_baseline_execution_robustness_filter_report(report)

    assert "# Baseline Execution Robustness Filter Comparison" in text
    assert "| Strategy | Mode | Primary | Rule | Raw bets | Raw ROI | Raw hit | Kept bets | Kept ROI | Kept hit | Filtered bets | Filtered ROI | Filtered hit |" in text
    assert "`asian_away_cover_hgb_edge_v1`" in text
    assert "seen>=4 edge>=0.0800" in text


def _source_report(
    profiles: list[ExecutionRobustnessCandidateProfile],
) -> BaselineExecutionRobustnessReport:
    return BaselineExecutionRobustnessReport(
        csv_path="local_data/training/dynamic.csv",
        row_count=100,
        train_rows=80,
        validation_rows=20,
        execution_targets=(25, 20, 15, 10, 5),
        primary_target=15,
        tolerance_minutes=5,
        source_name="oddspapi",
        bookmaker="pinnacle",
        target_available_rows={25: 18, 20: 18, 15: 18, 10: 17, 5: 16},
        strategy_summaries=[],
        profiles_by_strategy={DEFAULT_STRATEGY.strategy_key: profiles},
    )


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

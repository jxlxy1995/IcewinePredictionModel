from decimal import Decimal

from tests.test_baseline_total_goals_edge_stability_service import _total_goals_feature_csv

from icewine_prediction.baseline_total_goals_bucket_sandbox_service import (
    build_baseline_total_goals_bucket_sandbox_report,
    format_baseline_total_goals_bucket_sandbox_report,
)


def test_build_baseline_total_goals_bucket_sandbox_report_compares_v1_and_v2(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_total_goals_feature_csv(), encoding="utf-8")

    report = build_baseline_total_goals_bucket_sandbox_report(
        csv_path,
        v1_edge_threshold="0.10",
        bucket_thresholds={
            "over@mid_2.75": "0.08",
            "under@low_<=2.25": "0.12",
        },
        train_ratio="0.50",
        validation_ratio="0.20",
        fold_count=3,
    )

    assert report.row_count == 64
    assert report.fold_count == 3
    assert {summary.strategy_key for summary in report.strategy_summaries} == {
        "total_goals_hgb_edge_v1",
        "total_goals_hgb_bucket_v2",
    }
    v2 = next(
        summary
        for summary in report.strategy_summaries
        if summary.strategy_key == "total_goals_hgb_bucket_v2"
    )
    assert v2.bucket_thresholds == {
        "over@mid_2.75": Decimal("0.0800"),
        "under@low_<=2.25": Decimal("0.1200"),
    }
    assert all(
        f"{candidate.side}@{bucket_summary.total_line_bucket}" in v2.bucket_thresholds
        for fold in report.fold_reports
        for bucket_summary in fold.bucket_summaries
        for candidate in fold.v2_candidates
        if bucket_summary.total_line_bucket
    )


def test_format_baseline_total_goals_bucket_sandbox_report_includes_comparison_tables(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_total_goals_feature_csv(), encoding="utf-8")

    report = build_baseline_total_goals_bucket_sandbox_report(
        csv_path,
        v1_edge_threshold="0.10",
        bucket_thresholds={"over@mid_2.75": "0.08"},
        train_ratio="0.50",
        validation_ratio="0.20",
        fold_count=2,
    )

    text = format_baseline_total_goals_bucket_sandbox_report(report)

    assert "# Baseline Total Goals Bucket Sandbox v2" in text
    assert "| Strategy | Bets | Positive ROI folds | Profit | ROI |" in text
    assert "| Fold | V1 bets | V1 ROI | V2 bets | V2 ROI | Delta profit |" in text
    assert "| Side bucket | Bets | Positive ROI folds | Profit | ROI |" in text

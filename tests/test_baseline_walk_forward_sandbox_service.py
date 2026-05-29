from decimal import Decimal

from tests.test_baseline_recommendation_sandbox_service import _feature_csv

from icewine_prediction.baseline_walk_forward_sandbox_service import (
    build_baseline_walk_forward_sandbox_report,
    format_baseline_walk_forward_sandbox_report,
)


def test_build_baseline_walk_forward_sandbox_report_summarizes_folds(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_feature_csv(), encoding="utf-8")

    report = build_baseline_walk_forward_sandbox_report(
        csv_path,
        edge_threshold="0.00",
        train_ratio="0.50",
        validation_ratio="0.20",
        fold_count=3,
    )

    assert report.row_count == 24
    assert report.fold_count == 3
    assert report.edge_threshold == Decimal("0.0000")
    assert report.total_candidates > 0
    assert report.roi is not None
    assert report.fold_reports[0].fold_index == 1
    assert report.fold_reports[0].side_summaries
    assert {summary.name for summary in report.side_summaries} <= {"home_cover", "away_cover"}


def test_format_baseline_walk_forward_sandbox_report_includes_side_stability(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_feature_csv(), encoding="utf-8")
    report = build_baseline_walk_forward_sandbox_report(
        csv_path,
        edge_threshold="0.00",
        train_ratio="0.50",
        validation_ratio="0.20",
        fold_count=2,
    )

    text = format_baseline_walk_forward_sandbox_report(report)

    assert "# Baseline Walk-Forward Recommendation Sandbox v1" in text
    assert "asian_handicap raw_hgb_team_form_plus_all_markets" in text
    assert "| Fold | Train | Validation | Bets | Profit | ROI | Positive ROI |" in text
    assert "| Side | Bets | Positive ROI folds | Profit | ROI |" in text

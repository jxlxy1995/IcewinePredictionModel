from decimal import Decimal

from icewine_prediction.baseline_away_cover_bucket_threshold_service import (
    build_baseline_away_cover_bucket_threshold_report,
    format_baseline_away_cover_bucket_threshold_report,
)
from tests.test_baseline_away_cover_stability_service import _away_cover_feature_csv


def test_build_baseline_away_cover_bucket_threshold_report_selects_best_thresholds(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_away_cover_feature_csv(), encoding="utf-8")

    report = build_baseline_away_cover_bucket_threshold_report(
        csv_path,
        thresholds=("0.00", "0.10"),
        train_ratio="0.50",
        validation_ratio="0.20",
        fold_count=3,
    )

    assert report.strategy_key == "asian_away_cover_hgb_bucket_v2"
    assert report.selected_thresholds
    assert {selection.line_bucket for selection in report.selected_thresholds} <= {
        "away_favorite",
        "away_underdog",
        "pickem",
    }
    assert all(selection.threshold in {Decimal("0.0000"), Decimal("0.1000")} for selection in report.selected_thresholds)
    assert all(selection.candidate_count > 0 for selection in report.selected_thresholds)


def test_format_baseline_away_cover_bucket_threshold_report_includes_strategy_summary(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_away_cover_feature_csv(), encoding="utf-8")

    report = build_baseline_away_cover_bucket_threshold_report(
        csv_path,
        thresholds=("0.00", "0.10"),
        train_ratio="0.50",
        validation_ratio="0.20",
        fold_count=2,
    )

    text = format_baseline_away_cover_bucket_threshold_report(report)

    assert "# Baseline Away Cover Bucket Threshold v2" in text
    assert "`asian_away_cover_hgb_bucket_v2`" in text
    assert "| Line bucket | Selected threshold | Bets | Positive ROI folds | Profit | ROI | Worst fold ROI |" in text

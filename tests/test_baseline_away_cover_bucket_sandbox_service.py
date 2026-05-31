from decimal import Decimal

from tests.test_baseline_away_cover_stability_service import _away_cover_feature_csv

from icewine_prediction.baseline_away_cover_bucket_sandbox_service import (
    build_baseline_away_cover_bucket_sandbox_report,
    format_baseline_away_cover_bucket_sandbox_report,
)


def test_build_baseline_away_cover_bucket_sandbox_report_compares_v1_and_v2(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_away_cover_feature_csv(), encoding="utf-8")

    report = build_baseline_away_cover_bucket_sandbox_report(
        csv_path,
        v1_edge_threshold="0.10",
        bucket_thresholds={
            "away_underdog": "0.20",
            "pickem": "0.08",
        },
        train_ratio="0.50",
        validation_ratio="0.20",
        fold_count=3,
        top_n_per_fold=5,
    )

    assert report.row_count == 60
    assert report.fold_count == 3
    assert {summary.strategy_key for summary in report.strategy_summaries} == {
        "asian_away_cover_hgb_edge_v1",
        "asian_away_cover_hgb_bucket_v2",
    }
    v2 = next(
        summary
        for summary in report.strategy_summaries
        if summary.strategy_key == "asian_away_cover_hgb_bucket_v2"
    )
    assert v2.bucket_thresholds == {
        "away_underdog": Decimal("0.2000"),
        "pickem": Decimal("0.0800"),
    }
    assert all(candidate.side == "away_cover" for fold in report.fold_reports for candidate in fold.v2_candidates)


def test_format_baseline_away_cover_bucket_sandbox_report_includes_comparison_tables(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_away_cover_feature_csv(), encoding="utf-8")

    report = build_baseline_away_cover_bucket_sandbox_report(
        csv_path,
        v1_edge_threshold="0.10",
        bucket_thresholds={"away_underdog": "0.20", "pickem": "0.08"},
        train_ratio="0.50",
        validation_ratio="0.20",
        fold_count=2,
    )

    text = format_baseline_away_cover_bucket_sandbox_report(report)

    assert "# Baseline Away Cover Bucket Sandbox v2" in text
    assert "| Strategy | Bets | Positive ROI folds | Profit | ROI |" in text
    assert "| Fold | V1 bets | V1 ROI | V2 bets | V2 ROI | Delta profit |" in text
    assert "| Line bucket | Bets | Positive ROI folds | Profit | ROI |" in text

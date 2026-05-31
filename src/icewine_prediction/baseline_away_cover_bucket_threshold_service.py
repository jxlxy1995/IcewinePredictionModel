from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from icewine_prediction.baseline_away_cover_stability_service import (
    AwayCoverFoldCandidateSet,
    DEFAULT_AWAY_COVER_THRESHOLDS,
    _build_fold_candidates,
    _format_optional,
    _line_bucket,
    _summary_values,
)
from icewine_prediction.baseline_recommendation_sandbox_service import _as_decimal
from icewine_prediction.baseline_walk_forward_edge_service import _walk_forward_folds

import csv


STRATEGY_KEY = "asian_away_cover_hgb_bucket_v2"
STRATEGY_DISPLAY_NAME = "亚盘客队方向 · HGB分盘口桶 v2"
MODEL_NAME = "raw_hgb_team_form_plus_all_markets"


@dataclass(frozen=True)
class BucketThresholdSelection:
    line_bucket: str
    threshold: Decimal
    candidate_count: int
    positive_roi_folds: int
    profit: Decimal
    roi: Decimal | None
    worst_fold_roi: Decimal | None


@dataclass(frozen=True)
class BaselineAwayCoverBucketThresholdReport:
    csv_path: Path
    row_count: int
    fold_count: int
    train_ratio: Decimal
    validation_ratio: Decimal
    thresholds: tuple[Decimal, ...]
    strategy_key: str
    strategy_display_name: str
    market_type: str
    model_name: str
    side: str
    selected_thresholds: list[BucketThresholdSelection]
    bucket_threshold_summaries: dict[str, list[BucketThresholdSelection]]


def build_baseline_away_cover_bucket_threshold_report(
    csv_path: Path,
    *,
    thresholds: tuple[str, ...] = DEFAULT_AWAY_COVER_THRESHOLDS,
    train_ratio: str = "0.60",
    validation_ratio: str = "0.10",
    fold_count: int = 5,
) -> BaselineAwayCoverBucketThresholdReport:
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = sorted(
            list(csv.DictReader(file)),
            key=lambda row: (row.get("kickoff_time", ""), row.get("match_id", "")),
        )
    train_ratio_value = _as_decimal(train_ratio)
    validation_ratio_value = _as_decimal(validation_ratio)
    threshold_values = tuple(_as_decimal(threshold) for threshold in thresholds)
    fold_candidates = [
        _build_fold_candidates(fold_index, train_rows, validation_rows)
        for fold_index, (train_rows, validation_rows) in enumerate(
            _walk_forward_folds(
                rows,
                train_ratio=train_ratio_value,
                validation_ratio=validation_ratio_value,
                fold_count=fold_count,
            ),
            start=1,
        )
    ]
    bucket_names = sorted(
        {
            _line_bucket(candidate)
            for fold in fold_candidates
            for candidate in fold.candidates
        }
    )
    summaries = {
        bucket: [
            _bucket_threshold_selection(bucket, threshold, fold_candidates)
            for threshold in threshold_values
        ]
        for bucket in bucket_names
    }
    return BaselineAwayCoverBucketThresholdReport(
        csv_path=csv_path,
        row_count=len(rows),
        fold_count=len(fold_candidates),
        train_ratio=train_ratio_value,
        validation_ratio=validation_ratio_value,
        thresholds=threshold_values,
        strategy_key=STRATEGY_KEY,
        strategy_display_name=STRATEGY_DISPLAY_NAME,
        market_type="asian_handicap",
        model_name=MODEL_NAME,
        side="away_cover",
        selected_thresholds=[
            _select_threshold(bucket_summaries)
            for bucket_summaries in summaries.values()
            if bucket_summaries
        ],
        bucket_threshold_summaries=summaries,
    )


def write_baseline_away_cover_bucket_threshold_report(
    report: BaselineAwayCoverBucketThresholdReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_baseline_away_cover_bucket_threshold_report(report) + "\n",
        encoding="utf-8",
    )


def format_baseline_away_cover_bucket_threshold_report(
    report: BaselineAwayCoverBucketThresholdReport,
) -> str:
    lines = [
        "# Baseline Away Cover Bucket Threshold v2",
        "",
        f"- Feature CSV: `{report.csv_path}`",
        f"- Strategy: `{report.strategy_key}` / {report.strategy_display_name}",
        f"- Scope: `{report.market_type} {report.model_name} {report.side}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Rows | {report.row_count} |",
        f"| Folds | {report.fold_count} |",
        f"| Train ratio | {report.train_ratio} |",
        f"| Validation ratio | {report.validation_ratio} |",
        f"| Thresholds | {', '.join(str(threshold) for threshold in report.thresholds)} |",
        "",
        "## Selected Thresholds",
        "",
        "| Line bucket | Selected threshold | Bets | Positive ROI folds | Profit | ROI | Worst fold ROI |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines.extend(_selection_lines(report.selected_thresholds))
    lines.extend(
        [
            "",
            "## Bucket Threshold Detail",
            "",
            "| Line bucket | Threshold | Bets | Positive ROI folds | Profit | ROI | Worst fold ROI |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for bucket, summaries in report.bucket_threshold_summaries.items():
        for summary in summaries:
            lines.append(_selection_line(summary, threshold_label=str(summary.threshold), bucket=bucket))
    return "\n".join(lines)


def _bucket_threshold_selection(
    bucket: str,
    threshold: Decimal,
    fold_candidates: list[AwayCoverFoldCandidateSet],
) -> BucketThresholdSelection:
    filtered_folds = [
        [
            candidate
            for candidate in fold.candidates
            if _line_bucket(candidate) == bucket and candidate.edge >= threshold
        ]
        for fold in fold_candidates
    ]
    return BucketThresholdSelection(
        line_bucket=bucket,
        threshold=threshold,
        **_summary_values(filtered_folds),
    )


def _select_threshold(
    summaries: list[BucketThresholdSelection],
) -> BucketThresholdSelection:
    return max(
        summaries,
        key=lambda summary: (
            summary.positive_roi_folds,
            summary.worst_fold_roi or Decimal("-99"),
            summary.roi or Decimal("-99"),
            summary.candidate_count,
            -summary.threshold,
        ),
    )


def _selection_lines(summaries: list[BucketThresholdSelection]) -> list[str]:
    if not summaries:
        return ["| - | - | 0 | 0 | - | - | - |"]
    return [
        _selection_line(summary, threshold_label=str(summary.threshold), bucket=summary.line_bucket)
        for summary in sorted(summaries, key=lambda item: item.line_bucket)
    ]


def _selection_line(
    summary: BucketThresholdSelection,
    *,
    threshold_label: str,
    bucket: str,
) -> str:
    return (
        f"| {bucket} | {threshold_label} | {summary.candidate_count} | "
        f"{summary.positive_roi_folds} | {summary.profit} | "
        f"{_format_optional(summary.roi)} | {_format_optional(summary.worst_fold_roi)} |"
    )

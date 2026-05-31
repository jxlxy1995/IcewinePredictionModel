from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from icewine_prediction.baseline_recommendation_sandbox_service import (
    SandboxCandidate,
    _as_decimal,
    _format_optional,
    _quantize,
)
from icewine_prediction.baseline_total_goals_edge_stability_service import (
    MODEL_NAME,
    _build_total_goals_candidates,
    _target_label,
    _total_line_bucket,
)
from icewine_prediction.baseline_walk_forward_edge_service import _walk_forward_folds


V1_STRATEGY_KEY = "total_goals_hgb_edge_v1"
V1_STRATEGY_DISPLAY_NAME = "大小球方向 · HGB边际 v1"
V2_STRATEGY_KEY = "total_goals_hgb_bucket_v2"
V2_STRATEGY_DISPLAY_NAME = "大小球方向 · HGB分盘口桶 v2"


@dataclass(frozen=True)
class TotalGoalsBucketSandboxStrategySummary:
    strategy_key: str
    display_name: str
    candidate_count: int
    positive_roi_folds: int
    profit: Decimal
    roi: Decimal | None
    bucket_thresholds: dict[str, Decimal]


@dataclass(frozen=True)
class TotalGoalsBucketSandboxBucketSummary:
    side_bucket: str
    total_line_bucket: str
    candidate_count: int
    positive_roi_folds: int
    profit: Decimal
    roi: Decimal | None


@dataclass(frozen=True)
class TotalGoalsBucketSandboxFoldReport:
    fold_index: int
    train_rows: int
    validation_rows: int
    v1_candidates: list[SandboxCandidate]
    v2_candidates: list[SandboxCandidate]
    v1_profit: Decimal
    v2_profit: Decimal
    v1_roi: Decimal | None
    v2_roi: Decimal | None
    bucket_summaries: list[TotalGoalsBucketSandboxBucketSummary]


@dataclass(frozen=True)
class BaselineTotalGoalsBucketSandboxReport:
    csv_path: Path
    row_count: int
    fold_count: int
    train_ratio: Decimal
    validation_ratio: Decimal
    v1_edge_threshold: Decimal
    bucket_thresholds: dict[str, Decimal]
    market_type: str
    model_name: str
    strategy_summaries: list[TotalGoalsBucketSandboxStrategySummary]
    fold_reports: list[TotalGoalsBucketSandboxFoldReport]
    bucket_summaries: list[TotalGoalsBucketSandboxBucketSummary]


def build_baseline_total_goals_bucket_sandbox_report(
    csv_path: Path,
    *,
    v1_edge_threshold: str = "0.10",
    bucket_thresholds: dict[str, str] | None = None,
    train_ratio: str = "0.60",
    validation_ratio: str = "0.10",
    fold_count: int = 5,
) -> BaselineTotalGoalsBucketSandboxReport:
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = sorted(
            list(csv.DictReader(file)),
            key=lambda row: (row.get("kickoff_time", ""), row.get("match_id", "")),
        )
    train_ratio_value = _as_decimal(train_ratio)
    validation_ratio_value = _as_decimal(validation_ratio)
    v1_threshold = _as_decimal(v1_edge_threshold)
    v2_thresholds = _normalize_bucket_thresholds(bucket_thresholds)
    fold_reports = [
        _build_fold_report(
            fold_index,
            train_rows,
            validation_rows,
            v1_threshold=v1_threshold,
            bucket_thresholds=v2_thresholds,
        )
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
    return BaselineTotalGoalsBucketSandboxReport(
        csv_path=csv_path,
        row_count=len(rows),
        fold_count=len(fold_reports),
        train_ratio=train_ratio_value,
        validation_ratio=validation_ratio_value,
        v1_edge_threshold=v1_threshold,
        bucket_thresholds=v2_thresholds,
        market_type="total_goals",
        model_name=MODEL_NAME,
        strategy_summaries=[
            _strategy_summary(
                V1_STRATEGY_KEY,
                V1_STRATEGY_DISPLAY_NAME,
                fold_reports,
                candidate_selector=lambda fold: fold.v1_candidates,
                bucket_thresholds={"all": v1_threshold},
            ),
            _strategy_summary(
                V2_STRATEGY_KEY,
                V2_STRATEGY_DISPLAY_NAME,
                fold_reports,
                candidate_selector=lambda fold: fold.v2_candidates,
                bucket_thresholds=v2_thresholds,
            ),
        ],
        fold_reports=fold_reports,
        bucket_summaries=_bucket_stability(fold_reports),
    )


def write_baseline_total_goals_bucket_sandbox_report(
    report: BaselineTotalGoalsBucketSandboxReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_baseline_total_goals_bucket_sandbox_report(report) + "\n",
        encoding="utf-8",
    )


def format_baseline_total_goals_bucket_sandbox_report(
    report: BaselineTotalGoalsBucketSandboxReport,
) -> str:
    lines = [
        "# Baseline Total Goals Bucket Sandbox v2",
        "",
        f"- Feature CSV: `{report.csv_path}`",
        f"- Scope: `{report.market_type} {report.model_name}`",
        "",
        "## Strategy Summary",
        "",
        "| Strategy | Bets | Positive ROI folds | Profit | ROI |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for summary in report.strategy_summaries:
        lines.append(
            f"| {summary.strategy_key} | {summary.candidate_count} | "
            f"{summary.positive_roi_folds} | {summary.profit} | {_format_optional(summary.roi)} |"
        )
    lines.extend(
        [
            "",
            "## Fold Comparison",
            "",
            "| Fold | V1 bets | V1 ROI | V2 bets | V2 ROI | Delta profit |",
            "| ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for fold in report.fold_reports:
        lines.append(
            f"| {fold.fold_index} | {len(fold.v1_candidates)} | {_format_optional(fold.v1_roi)} | "
            f"{len(fold.v2_candidates)} | {_format_optional(fold.v2_roi)} | "
            f"{_quantize(fold.v2_profit - fold.v1_profit)} |"
        )
    lines.extend(
        [
            "",
            "## V2 Side Bucket Stability",
            "",
            "| Side bucket | Bets | Positive ROI folds | Profit | ROI |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    if not report.bucket_summaries:
        lines.append("| - | 0 | 0 | - | - |")
    for summary in report.bucket_summaries:
        lines.append(
            f"| {summary.side_bucket} | {summary.candidate_count} | "
            f"{summary.positive_roi_folds} | {summary.profit} | {_format_optional(summary.roi)} |"
        )
    return "\n".join(lines)


def _build_fold_report(
    fold_index: int,
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    *,
    v1_threshold: Decimal,
    bucket_thresholds: dict[str, Decimal],
) -> TotalGoalsBucketSandboxFoldReport:
    train_eligible = [row for row in train_rows if _target_label(row) is not None]
    validation_eligible = [row for row in validation_rows if _target_label(row) is not None]
    candidates = _build_total_goals_candidates(train_eligible, validation_eligible)
    v1_candidates = [candidate for candidate in candidates if candidate.edge >= v1_threshold]
    v2_candidates = [
        candidate
        for candidate in candidates
        if _side_bucket(candidate) in bucket_thresholds
        and candidate.edge >= bucket_thresholds[_side_bucket(candidate)]
    ]
    v1_profit = _candidate_profit(v1_candidates)
    v2_profit = _candidate_profit(v2_candidates)
    return TotalGoalsBucketSandboxFoldReport(
        fold_index=fold_index,
        train_rows=len(train_eligible),
        validation_rows=len(validation_eligible),
        v1_candidates=v1_candidates,
        v2_candidates=v2_candidates,
        v1_profit=v1_profit,
        v2_profit=v2_profit,
        v1_roi=_ratio(v1_profit, len(v1_candidates)),
        v2_roi=_ratio(v2_profit, len(v2_candidates)),
        bucket_summaries=_fold_bucket_summaries(v2_candidates),
    )


def _strategy_summary(
    strategy_key: str,
    display_name: str,
    fold_reports: list[TotalGoalsBucketSandboxFoldReport],
    *,
    candidate_selector,
    bucket_thresholds: dict[str, Decimal],
) -> TotalGoalsBucketSandboxStrategySummary:
    fold_candidate_groups = [candidate_selector(fold) for fold in fold_reports]
    candidate_count = sum(len(group) for group in fold_candidate_groups)
    profit = _quantize(
        sum((candidate.profit for group in fold_candidate_groups for candidate in group), Decimal("0"))
    )
    fold_rois = [_ratio(_candidate_profit(group), len(group)) for group in fold_candidate_groups]
    return TotalGoalsBucketSandboxStrategySummary(
        strategy_key=strategy_key,
        display_name=display_name,
        candidate_count=candidate_count,
        positive_roi_folds=sum(1 for roi in fold_rois if roi is not None and roi > 0),
        profit=profit,
        roi=_ratio(profit, candidate_count),
        bucket_thresholds=bucket_thresholds,
    )


def _bucket_stability(
    fold_reports: list[TotalGoalsBucketSandboxFoldReport],
) -> list[TotalGoalsBucketSandboxBucketSummary]:
    bucket_names = sorted(
        {
            summary.side_bucket
            for fold in fold_reports
            for summary in fold.bucket_summaries
        }
    )
    return [
        _bucket_summary(
            bucket,
            [
                [
                    candidate
                    for candidate in fold.v2_candidates
                    if _side_bucket(candidate) == bucket
                ]
                for fold in fold_reports
            ],
        )
        for bucket in bucket_names
    ]


def _fold_bucket_summaries(
    candidates: list[SandboxCandidate],
) -> list[TotalGoalsBucketSandboxBucketSummary]:
    bucket_names = sorted({_side_bucket(candidate) for candidate in candidates})
    return [
        _bucket_summary(
            bucket,
            [[candidate for candidate in candidates if _side_bucket(candidate) == bucket]],
        )
        for bucket in bucket_names
    ]


def _bucket_summary(
    bucket: str,
    candidate_groups: list[list[SandboxCandidate]],
) -> TotalGoalsBucketSandboxBucketSummary:
    candidate_count = sum(len(group) for group in candidate_groups)
    profit = _quantize(
        sum((candidate.profit for group in candidate_groups for candidate in group), Decimal("0"))
    )
    fold_rois = [_ratio(_candidate_profit(group), len(group)) for group in candidate_groups]
    return TotalGoalsBucketSandboxBucketSummary(
        side_bucket=bucket,
        total_line_bucket=bucket.split("@", maxsplit=1)[1] if "@" in bucket else bucket,
        candidate_count=candidate_count,
        positive_roi_folds=sum(1 for roi in fold_rois if roi is not None and roi > 0),
        profit=profit,
        roi=_ratio(profit, candidate_count),
    )


def _normalize_bucket_thresholds(values: dict[str, str] | None) -> dict[str, Decimal]:
    values = values or {
        "over@mid_2.75": "0.08",
        "under@mid_2.75": "0.08",
    }
    return {bucket: _as_decimal(threshold) for bucket, threshold in values.items()}


def _side_bucket(candidate: SandboxCandidate) -> str:
    return f"{candidate.side}@{_total_line_bucket(candidate)}"


def _candidate_profit(candidates: list[SandboxCandidate]) -> Decimal:
    return _quantize(sum((candidate.profit for candidate in candidates), Decimal("0")))


def _ratio(numerator: Decimal, denominator: int) -> Decimal | None:
    if denominator <= 0:
        return None
    return _quantize(numerator / Decimal(denominator))

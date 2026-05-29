from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from icewine_prediction.baseline_edge_backtest_service import (
    DEFAULT_THRESHOLDS,
    EdgeModelBacktest,
    MARKET_CONFIGS,
    _as_decimal,
    _fit_and_backtest,
    _format_optional,
)


METRIC_QUANT = Decimal("0.0001")


@dataclass(frozen=True)
class WalkForwardFoldBacktest:
    fold_index: int
    train_rows: int
    validation_rows: int
    model_report: EdgeModelBacktest


@dataclass(frozen=True)
class WalkForwardThresholdSummary:
    threshold: Decimal
    fold_count: int
    total_bets: int
    positive_roi_folds: int
    average_roi: Decimal | None
    worst_roi: Decimal | None

    @property
    def threshold_label(self) -> str:
        return str(self.threshold)


@dataclass(frozen=True)
class WalkForwardModelBacktest:
    name: str
    threshold_summaries: list[WalkForwardThresholdSummary]
    fold_reports: list[WalkForwardFoldBacktest]


@dataclass(frozen=True)
class WalkForwardMarketBacktest:
    market_type: str
    model_reports: dict[str, WalkForwardModelBacktest]


@dataclass(frozen=True)
class BaselineWalkForwardEdgeReport:
    csv_path: Path
    row_count: int
    fold_count: int
    train_ratio: Decimal
    validation_ratio: Decimal
    thresholds: tuple[Decimal, ...]
    market_reports: dict[str, WalkForwardMarketBacktest]


def build_baseline_walk_forward_edge_report(
    csv_path: Path,
    *,
    thresholds: tuple[str, ...] = DEFAULT_THRESHOLDS,
    train_ratio: str = "0.60",
    validation_ratio: str = "0.10",
    fold_count: int = 5,
) -> BaselineWalkForwardEdgeReport:
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = sorted(
            list(csv.DictReader(file)),
            key=lambda row: (row.get("kickoff_time", ""), row.get("match_id", "")),
        )
    threshold_values = tuple(_as_decimal(threshold) for threshold in thresholds)
    train_ratio_value = _as_decimal(train_ratio)
    validation_ratio_value = _as_decimal(validation_ratio)
    folds = _walk_forward_folds(
        rows,
        train_ratio=train_ratio_value,
        validation_ratio=validation_ratio_value,
        fold_count=fold_count,
    )
    return BaselineWalkForwardEdgeReport(
        csv_path=csv_path,
        row_count=len(rows),
        fold_count=len(folds),
        train_ratio=train_ratio_value,
        validation_ratio=validation_ratio_value,
        thresholds=threshold_values,
        market_reports={
            config.market_type: _build_market_report(config, folds, threshold_values)
            for config in MARKET_CONFIGS
        },
    )


def write_baseline_walk_forward_edge_report(
    report: BaselineWalkForwardEdgeReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_baseline_walk_forward_edge_report(report) + "\n",
        encoding="utf-8",
    )


def format_baseline_walk_forward_edge_report(report: BaselineWalkForwardEdgeReport) -> str:
    lines = [
        "# Baseline Walk-Forward Edge Backtest v1",
        "",
        f"- Feature CSV: `{report.csv_path}`",
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
    ]
    for market_report in report.market_reports.values():
        lines.extend([f"## {market_report.market_type}", ""])
        for model_report in market_report.model_reports.values():
            lines.extend(
                [
                    f"### {model_report.name}",
                    "",
                    "| Threshold | Folds | Bets | Positive ROI folds | Avg ROI | Worst ROI |",
                    "| ---: | ---: | ---: | ---: | ---: | ---: |",
                ]
            )
            for summary in model_report.threshold_summaries:
                lines.append(
                    f"| {summary.threshold} | {summary.fold_count} | "
                    f"{summary.total_bets} | {summary.positive_roi_folds} | "
                    f"{_format_optional(summary.average_roi)} | "
                    f"{_format_optional(summary.worst_roi)} |"
                )
            lines.append("")
            lines.extend(
                [
                    "| Fold | Train | Validation | Accuracy | Log loss | Brier |",
                    "| ---: | ---: | ---: | ---: | ---: | ---: |",
                ]
            )
            for fold_report in model_report.fold_reports:
                model = fold_report.model_report
                lines.append(
                    f"| {fold_report.fold_index} | {fold_report.train_rows} | "
                    f"{fold_report.validation_rows} | {model.accuracy} | "
                    f"{model.log_loss} | {model.brier_score} |"
                )
            lines.append("")
    return "\n".join(lines)


def _walk_forward_folds(
    rows: list[dict[str, str]],
    *,
    train_ratio: Decimal,
    validation_ratio: Decimal,
    fold_count: int,
) -> list[tuple[list[dict[str, str]], list[dict[str, str]]]]:
    row_count = len(rows)
    train_size = max(1, int(row_count * float(train_ratio)))
    validation_size = max(1, int(row_count * float(validation_ratio)))
    remaining = row_count - train_size - validation_size
    if remaining < 0:
        raise ValueError("walk-forward split requires train + validation ratios below 1.0")
    step = max(1, remaining // max(1, fold_count - 1)) if fold_count > 1 else 1
    folds = []
    for fold_index in range(fold_count):
        start = fold_index * step
        train_start = start
        train_end = train_start + train_size
        validation_end = train_end + validation_size
        if validation_end > row_count:
            break
        folds.append((rows[train_start:train_end], rows[train_end:validation_end]))
    if not folds:
        raise ValueError("walk-forward split produced no folds")
    return folds


def _build_market_report(
    config,
    folds: list[tuple[list[dict[str, str]], list[dict[str, str]]]],
    thresholds: tuple[Decimal, ...],
) -> WalkForwardMarketBacktest:
    raw_folds = []
    calibrated_folds = []
    for fold_index, (train_rows, validation_rows) in enumerate(folds, start=1):
        train_eligible = [row for row in train_rows if config.target_label_builder(row) is not None]
        validation_eligible = [row for row in validation_rows if config.target_label_builder(row) is not None]
        if not train_eligible or not validation_eligible:
            continue
        raw_folds.append(
            WalkForwardFoldBacktest(
                fold_index=fold_index,
                train_rows=len(train_eligible),
                validation_rows=len(validation_eligible),
                model_report=_fit_and_backtest(
                    config,
                    train_eligible,
                    validation_eligible,
                    thresholds,
                    name="raw_hgb_team_form_plus_all_markets",
                    calibrated=False,
                ),
            )
        )
        calibrated_folds.append(
            WalkForwardFoldBacktest(
                fold_index=fold_index,
                train_rows=len(train_eligible),
                validation_rows=len(validation_eligible),
                model_report=_fit_and_backtest(
                    config,
                    train_eligible,
                    validation_eligible,
                    thresholds,
                    name="calibrated_hgb_team_form_plus_all_markets",
                    calibrated=True,
                ),
            )
        )
    if not raw_folds or not calibrated_folds:
        raise ValueError(f"{config.market_type} walk-forward backtest produced no eligible folds")
    raw_report = _model_report("raw_hgb_team_form_plus_all_markets", raw_folds, thresholds)
    calibrated_report = _model_report(
        "calibrated_hgb_team_form_plus_all_markets",
        calibrated_folds,
        thresholds,
    )
    return WalkForwardMarketBacktest(
        market_type=config.market_type,
        model_reports={
            raw_report.name: raw_report,
            calibrated_report.name: calibrated_report,
        },
    )


def _model_report(
    name: str,
    fold_reports: list[WalkForwardFoldBacktest],
    thresholds: tuple[Decimal, ...],
) -> WalkForwardModelBacktest:
    return WalkForwardModelBacktest(
        name=name,
        threshold_summaries=[
            _threshold_summary(threshold, fold_reports) for threshold in thresholds
        ],
        fold_reports=fold_reports,
    )


def _threshold_summary(
    threshold: Decimal,
    fold_reports: list[WalkForwardFoldBacktest],
) -> WalkForwardThresholdSummary:
    matching_buckets = [
        bucket
        for fold_report in fold_reports
        for bucket in fold_report.model_report.threshold_buckets
        if bucket.threshold == threshold
    ]
    roi_values = [bucket.roi for bucket in matching_buckets if bucket.roi is not None]
    total_bets = sum(bucket.bet_count for bucket in matching_buckets)
    if roi_values:
        average_roi = _quantize(sum(roi_values, Decimal("0")) / Decimal(len(roi_values)))
        worst_roi = min(roi_values)
        positive_roi_folds = sum(1 for value in roi_values if value > 0)
    else:
        average_roi = None
        worst_roi = None
        positive_roi_folds = 0
    return WalkForwardThresholdSummary(
        threshold=threshold,
        fold_count=len(matching_buckets),
        total_bets=total_bets,
        positive_roi_folds=positive_roi_folds,
        average_roi=average_roi,
        worst_roi=worst_roi,
    )


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(METRIC_QUANT, rounding=ROUND_HALF_UP)

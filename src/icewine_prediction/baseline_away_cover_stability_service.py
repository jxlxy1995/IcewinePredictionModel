from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from icewine_prediction.baseline_asian_handicap_model_service import _target_label
from icewine_prediction.baseline_recommendation_sandbox_service import (
    SandboxCandidate,
    _as_decimal,
    _build_candidates,
    _format_optional,
    _quantize,
)
from icewine_prediction.baseline_walk_forward_edge_service import _walk_forward_folds


DEFAULT_AWAY_COVER_THRESHOLDS = ("0.08", "0.10", "0.12", "0.15", "0.20")
MIN_SEGMENT_BETS = 5


@dataclass(frozen=True)
class AwayCoverFoldCandidateSet:
    fold_index: int
    train_rows: int
    validation_rows: int
    candidates: list[SandboxCandidate]


@dataclass(frozen=True)
class AwayCoverStabilitySummary:
    name: str
    candidate_count: int
    positive_roi_folds: int
    profit: Decimal
    roi: Decimal | None
    worst_fold_roi: Decimal | None


@dataclass(frozen=True)
class AwayCoverThresholdSummary:
    threshold: Decimal
    candidate_count: int
    positive_roi_folds: int
    profit: Decimal
    roi: Decimal | None
    worst_fold_roi: Decimal | None


@dataclass(frozen=True)
class BaselineAwayCoverStabilityReport:
    csv_path: Path
    row_count: int
    fold_count: int
    train_ratio: Decimal
    validation_ratio: Decimal
    thresholds: tuple[Decimal, ...]
    market_type: str
    model_name: str
    side: str
    threshold_summaries: list[AwayCoverThresholdSummary]
    league_summaries: list[AwayCoverStabilitySummary]
    line_bucket_summaries: list[AwayCoverStabilitySummary]


def build_baseline_away_cover_stability_report(
    csv_path: Path,
    *,
    thresholds: tuple[str, ...] = DEFAULT_AWAY_COVER_THRESHOLDS,
    train_ratio: str = "0.60",
    validation_ratio: str = "0.10",
    fold_count: int = 5,
) -> BaselineAwayCoverStabilityReport:
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
    primary_threshold = threshold_values[1] if len(threshold_values) > 1 else threshold_values[0]
    primary_candidates = [
        AwayCoverFoldCandidateSet(
            fold_index=fold.fold_index,
            train_rows=fold.train_rows,
            validation_rows=fold.validation_rows,
            candidates=[candidate for candidate in fold.candidates if candidate.edge >= primary_threshold],
        )
        for fold in fold_candidates
    ]
    return BaselineAwayCoverStabilityReport(
        csv_path=csv_path,
        row_count=len(rows),
        fold_count=len(fold_candidates),
        train_ratio=train_ratio_value,
        validation_ratio=validation_ratio_value,
        thresholds=threshold_values,
        market_type="asian_handicap",
        model_name="raw_hgb_team_form_plus_all_markets",
        side="away_cover",
        threshold_summaries=[
            _threshold_summary(threshold, fold_candidates) for threshold in threshold_values
        ],
        league_summaries=_segment_summaries(
            primary_candidates,
            key_builder=lambda candidate: candidate.league_name,
        ),
        line_bucket_summaries=_segment_summaries(
            primary_candidates,
            key_builder=_line_bucket,
        ),
    )


def write_baseline_away_cover_stability_report(
    report: BaselineAwayCoverStabilityReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_baseline_away_cover_stability_report(report) + "\n",
        encoding="utf-8",
    )


def format_baseline_away_cover_stability_report(
    report: BaselineAwayCoverStabilityReport,
) -> str:
    lines = [
        "# Baseline Away Cover Stability v1",
        "",
        f"- Feature CSV: `{report.csv_path}`",
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
        "## Threshold Stability",
        "",
        "| Threshold | Bets | Positive ROI folds | Profit | ROI | Worst fold ROI |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in report.threshold_summaries:
        lines.append(
            f"| {summary.threshold} | {summary.candidate_count} | "
            f"{summary.positive_roi_folds} | {summary.profit} | "
            f"{_format_optional(summary.roi)} | {_format_optional(summary.worst_fold_roi)} |"
        )
    lines.extend(
        [
            "",
            "## League Stability",
            "",
            "| League | Bets | Positive ROI folds | Profit | ROI | Worst fold ROI |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    lines.extend(_segment_lines(report.league_summaries))
    lines.extend(
        [
            "",
            "## Line Bucket Stability",
            "",
            "| Line bucket | Bets | Positive ROI folds | Profit | ROI | Worst fold ROI |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    lines.extend(_segment_lines(report.line_bucket_summaries))
    return "\n".join(lines)


def _build_fold_candidates(
    fold_index: int,
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
) -> AwayCoverFoldCandidateSet:
    train_eligible = [row for row in train_rows if _target_label(row) is not None]
    validation_eligible = [row for row in validation_rows if _target_label(row) is not None]
    candidates = [
        candidate
        for candidate in _build_candidates(train_eligible, validation_eligible)
        if candidate.side == "away_cover"
    ]
    return AwayCoverFoldCandidateSet(
        fold_index=fold_index,
        train_rows=len(train_eligible),
        validation_rows=len(validation_eligible),
        candidates=candidates,
    )


def _threshold_summary(
    threshold: Decimal,
    fold_candidates: list[AwayCoverFoldCandidateSet],
) -> AwayCoverThresholdSummary:
    filtered_folds = [
        [candidate for candidate in fold.candidates if candidate.edge >= threshold]
        for fold in fold_candidates
    ]
    return AwayCoverThresholdSummary(
        threshold=threshold,
        **_summary_values(filtered_folds),
    )


def _segment_summaries(
    fold_candidates: list[AwayCoverFoldCandidateSet],
    *,
    key_builder,
) -> list[AwayCoverStabilitySummary]:
    segment_names = sorted(
        {
            key_builder(candidate)
            for fold in fold_candidates
            for candidate in fold.candidates
        }
    )
    summaries = []
    for name in segment_names:
        filtered_folds = [
            [candidate for candidate in fold.candidates if key_builder(candidate) == name]
            for fold in fold_candidates
        ]
        values = _summary_values(filtered_folds)
        if values["candidate_count"] < MIN_SEGMENT_BETS:
            continue
        summaries.append(AwayCoverStabilitySummary(name=name, **values))
    return sorted(summaries, key=lambda summary: (-summary.candidate_count, summary.name))


def _summary_values(
    fold_candidate_groups: list[list[SandboxCandidate]],
) -> dict[str, object]:
    candidate_count = sum(len(group) for group in fold_candidate_groups)
    profit = _quantize(
        sum(
            (candidate.profit for group in fold_candidate_groups for candidate in group),
            Decimal("0"),
        )
    )
    fold_rois = [
        _quantize(
            sum((candidate.profit for candidate in group), Decimal("0"))
            / Decimal(len(group))
        )
        for group in fold_candidate_groups
        if group
    ]
    return {
        "candidate_count": candidate_count,
        "positive_roi_folds": sum(1 for roi in fold_rois if roi > 0),
        "profit": profit,
        "roi": _ratio(profit, candidate_count),
        "worst_fold_roi": min(fold_rois) if fold_rois else None,
    }


def _line_bucket(candidate: SandboxCandidate) -> str:
    line = candidate.line
    if line is None:
        return "unknown"
    if line > 0:
        return "away_favorite"
    if line == 0:
        return "pickem"
    return "away_underdog"


def _segment_lines(summaries: list[AwayCoverStabilitySummary]) -> list[str]:
    if not summaries:
        return ["| - | 0 | 0 | - | - | - |"]
    return [
        f"| {summary.name} | {summary.candidate_count} | "
        f"{summary.positive_roi_folds} | {summary.profit} | "
        f"{_format_optional(summary.roi)} | {_format_optional(summary.worst_fold_roi)} |"
        for summary in summaries
    ]


def _ratio(numerator: Decimal, denominator: int) -> Decimal | None:
    if denominator <= 0:
        return None
    return _quantize(numerator / Decimal(denominator))

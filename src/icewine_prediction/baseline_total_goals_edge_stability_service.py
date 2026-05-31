from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from icewine_prediction.baseline_edge_backtest_service import (
    FEATURES,
    _decimal_from_row,
    _market_probabilities,
    _raw_model,
)
from icewine_prediction.baseline_match_winner_model_service import _matrix
from icewine_prediction.baseline_recommendation_sandbox_service import (
    SandboxCandidate,
    _as_decimal,
    _format_optional,
    _profit,
    _quantize,
)
from icewine_prediction.baseline_total_goals_model_service import (
    SIDE_LABELS,
    _align_probabilities,
    _target_label,
)
from icewine_prediction.baseline_walk_forward_edge_service import _walk_forward_folds


DEFAULT_TOTAL_GOALS_THRESHOLDS = ("0.08", "0.10", "0.12", "0.15", "0.20")
TOTAL_GOALS_PROBABILITY_FIELDS = (
    "total_goals_over_implied_probability",
    "total_goals_under_implied_probability",
)
TOTAL_GOALS_ODDS_FIELDS = ("total_goals_over_odds", "total_goals_under_odds")
MODEL_NAME = "raw_hgb_team_form_plus_all_markets"
MIN_SEGMENT_BETS = 5


@dataclass(frozen=True)
class TotalGoalsFoldCandidateSet:
    fold_index: int
    train_rows: int
    validation_rows: int
    candidates: list[SandboxCandidate]


@dataclass(frozen=True)
class TotalGoalsStabilitySummary:
    name: str
    candidate_count: int
    positive_roi_folds: int
    profit: Decimal
    roi: Decimal | None
    worst_fold_roi: Decimal | None


@dataclass(frozen=True)
class TotalGoalsThresholdSummary:
    threshold: Decimal
    candidate_count: int
    positive_roi_folds: int
    profit: Decimal
    roi: Decimal | None
    worst_fold_roi: Decimal | None


@dataclass(frozen=True)
class BaselineTotalGoalsEdgeStabilityReport:
    csv_path: Path
    row_count: int
    fold_count: int
    train_ratio: Decimal
    validation_ratio: Decimal
    thresholds: tuple[Decimal, ...]
    market_type: str
    model_name: str
    threshold_summaries: list[TotalGoalsThresholdSummary]
    side_summaries: list[TotalGoalsStabilitySummary]
    league_summaries: list[TotalGoalsStabilitySummary]
    line_bucket_summaries: list[TotalGoalsStabilitySummary]


def build_baseline_total_goals_edge_stability_report(
    csv_path: Path,
    *,
    thresholds: tuple[str, ...] = DEFAULT_TOTAL_GOALS_THRESHOLDS,
    train_ratio: str = "0.60",
    validation_ratio: str = "0.10",
    fold_count: int = 5,
) -> BaselineTotalGoalsEdgeStabilityReport:
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
        TotalGoalsFoldCandidateSet(
            fold_index=fold.fold_index,
            train_rows=fold.train_rows,
            validation_rows=fold.validation_rows,
            candidates=[candidate for candidate in fold.candidates if candidate.edge >= primary_threshold],
        )
        for fold in fold_candidates
    ]
    return BaselineTotalGoalsEdgeStabilityReport(
        csv_path=csv_path,
        row_count=len(rows),
        fold_count=len(fold_candidates),
        train_ratio=train_ratio_value,
        validation_ratio=validation_ratio_value,
        thresholds=threshold_values,
        market_type="total_goals",
        model_name=MODEL_NAME,
        threshold_summaries=[
            _threshold_summary(threshold, fold_candidates) for threshold in threshold_values
        ],
        side_summaries=_segment_summaries(
            primary_candidates,
            key_builder=lambda candidate: candidate.side,
        ),
        league_summaries=_segment_summaries(
            primary_candidates,
            key_builder=lambda candidate: candidate.league_name,
        ),
        line_bucket_summaries=_segment_summaries(
            primary_candidates,
            key_builder=_total_line_bucket,
        ),
    )


def write_baseline_total_goals_edge_stability_report(
    report: BaselineTotalGoalsEdgeStabilityReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_baseline_total_goals_edge_stability_report(report) + "\n",
        encoding="utf-8",
    )


def format_baseline_total_goals_edge_stability_report(
    report: BaselineTotalGoalsEdgeStabilityReport,
) -> str:
    lines = [
        "# Baseline Total Goals Edge Stability v1",
        "",
        f"- Feature CSV: `{report.csv_path}`",
        f"- Scope: `{report.market_type} {report.model_name}`",
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
            "## Side Stability",
            "",
            "| Side | Bets | Positive ROI folds | Profit | ROI | Worst fold ROI |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    lines.extend(_segment_lines(report.side_summaries))
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
            "## Total Line Bucket Stability",
            "",
            "| Total line bucket | Bets | Positive ROI folds | Profit | ROI | Worst fold ROI |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    lines.extend(_segment_lines(report.line_bucket_summaries))
    return "\n".join(lines)


def _build_fold_candidates(
    fold_index: int,
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
) -> TotalGoalsFoldCandidateSet:
    train_eligible = [row for row in train_rows if _target_label(row) is not None]
    validation_eligible = [row for row in validation_rows if _target_label(row) is not None]
    return TotalGoalsFoldCandidateSet(
        fold_index=fold_index,
        train_rows=len(train_eligible),
        validation_rows=len(validation_eligible),
        candidates=_build_total_goals_candidates(train_eligible, validation_eligible),
    )


def _build_total_goals_candidates(
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
) -> list[SandboxCandidate]:
    if not train_rows or not validation_rows:
        return []
    model = _raw_model()
    model.fit(_matrix(train_rows, FEATURES), [_target_label(row) for row in train_rows])
    probabilities = model.predict_proba(_matrix(validation_rows, FEATURES))
    classes = list(model.named_steps["classifier"].classes_)
    aligned_probabilities = _align_probabilities(probabilities, classes)
    candidates = []
    for row, probability_row in zip(validation_rows, aligned_probabilities, strict=True):
        actual_side = _target_label(row)
        if actual_side is None:
            continue
        market_probabilities = _market_probabilities(row, TOTAL_GOALS_PROBABILITY_FIELDS)
        if market_probabilities is None:
            continue
        side_index = max(
            range(len(SIDE_LABELS)),
            key=lambda index: Decimal(str(probability_row[index])) - market_probabilities[index],
        )
        odds = _decimal_from_row(row, TOTAL_GOALS_ODDS_FIELDS[side_index])
        if odds is None or odds <= Decimal("1.0"):
            continue
        model_probability = _quantize(Decimal(str(probability_row[side_index])))
        market_probability = _quantize(market_probabilities[side_index])
        side = SIDE_LABELS[side_index]
        candidates.append(
            SandboxCandidate(
                match_id=row.get("match_id", ""),
                kickoff_time=row.get("kickoff_time", ""),
                league_name=row.get("league_name", ""),
                home_team_name=row.get("home_team_name", ""),
                away_team_name=row.get("away_team_name", ""),
                market_type="total_goals",
                line=_decimal_from_row(row, "total_goals_close_line"),
                side=side,
                odds=odds,
                model_probability=model_probability,
                market_probability=market_probability,
                edge=_quantize(model_probability - market_probability),
                actual_side=actual_side,
                profit=_profit(side == actual_side, odds),
            )
        )
    return candidates


def _threshold_summary(
    threshold: Decimal,
    fold_candidates: list[TotalGoalsFoldCandidateSet],
) -> TotalGoalsThresholdSummary:
    filtered_folds = [
        [candidate for candidate in fold.candidates if candidate.edge >= threshold]
        for fold in fold_candidates
    ]
    return TotalGoalsThresholdSummary(
        threshold=threshold,
        **_summary_values(filtered_folds),
    )


def _segment_summaries(
    fold_candidates: list[TotalGoalsFoldCandidateSet],
    *,
    key_builder,
) -> list[TotalGoalsStabilitySummary]:
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
        summaries.append(TotalGoalsStabilitySummary(name=name, **values))
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


def _total_line_bucket(candidate: SandboxCandidate) -> str:
    line = candidate.line
    if line is None:
        return "unknown"
    if line <= Decimal("2.25"):
        return "low_<=2.25"
    if line == Decimal("2.50"):
        return "mid_2.50"
    if line == Decimal("2.75"):
        return "mid_2.75"
    return "high_>=3.00"


def _segment_lines(summaries: list[TotalGoalsStabilitySummary]) -> list[str]:
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

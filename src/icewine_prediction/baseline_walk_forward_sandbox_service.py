from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from icewine_prediction.baseline_asian_handicap_model_service import _target_label
from icewine_prediction.baseline_recommendation_sandbox_service import (
    SandboxCandidate,
    SandboxGroupSummary,
    _as_decimal,
    _build_candidates,
    _format_optional,
    _group_summaries,
    _quantize,
)
from icewine_prediction.baseline_walk_forward_edge_service import _walk_forward_folds


METRIC_QUANT = Decimal("0.0001")


@dataclass(frozen=True)
class WalkForwardSandboxFoldReport:
    fold_index: int
    train_rows: int
    validation_rows: int
    candidate_count: int
    profit: Decimal
    roi: Decimal | None
    positive_roi: bool
    side_summaries: list[SandboxGroupSummary]
    displayed_candidates: list[SandboxCandidate]


@dataclass(frozen=True)
class WalkForwardSandboxSideSummary:
    name: str
    candidate_count: int
    positive_roi_folds: int
    profit: Decimal
    roi: Decimal | None


@dataclass(frozen=True)
class BaselineWalkForwardSandboxReport:
    csv_path: Path
    row_count: int
    fold_count: int
    train_ratio: Decimal
    validation_ratio: Decimal
    edge_threshold: Decimal
    top_n_per_fold: int
    market_type: str
    model_name: str
    total_candidates: int
    total_profit: Decimal
    roi: Decimal | None
    positive_roi_folds: int
    fold_reports: list[WalkForwardSandboxFoldReport]
    side_summaries: list[WalkForwardSandboxSideSummary]


def build_baseline_walk_forward_sandbox_report(
    csv_path: Path,
    *,
    edge_threshold: str = "0.10",
    train_ratio: str = "0.60",
    validation_ratio: str = "0.10",
    fold_count: int = 5,
    top_n_per_fold: int = 20,
) -> BaselineWalkForwardSandboxReport:
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = sorted(
            list(csv.DictReader(file)),
            key=lambda row: (row.get("kickoff_time", ""), row.get("match_id", "")),
        )
    train_ratio_value = _as_decimal(train_ratio)
    validation_ratio_value = _as_decimal(validation_ratio)
    threshold = _as_decimal(edge_threshold)
    folds = _walk_forward_folds(
        rows,
        train_ratio=train_ratio_value,
        validation_ratio=validation_ratio_value,
        fold_count=fold_count,
    )
    fold_reports = [
        _build_fold_report(
            fold_index,
            train_rows,
            validation_rows,
            edge_threshold=threshold,
            top_n=top_n_per_fold,
        )
        for fold_index, (train_rows, validation_rows) in enumerate(folds, start=1)
    ]
    total_candidates = sum(fold.candidate_count for fold in fold_reports)
    total_profit = _quantize(sum((fold.profit for fold in fold_reports), Decimal("0")))
    return BaselineWalkForwardSandboxReport(
        csv_path=csv_path,
        row_count=len(rows),
        fold_count=len(fold_reports),
        train_ratio=train_ratio_value,
        validation_ratio=validation_ratio_value,
        edge_threshold=threshold,
        top_n_per_fold=top_n_per_fold,
        market_type="asian_handicap",
        model_name="raw_hgb_team_form_plus_all_markets",
        total_candidates=total_candidates,
        total_profit=total_profit,
        roi=_ratio(total_profit, total_candidates),
        positive_roi_folds=sum(1 for fold in fold_reports if fold.positive_roi),
        fold_reports=fold_reports,
        side_summaries=_side_stability(fold_reports),
    )


def write_baseline_walk_forward_sandbox_report(
    report: BaselineWalkForwardSandboxReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_baseline_walk_forward_sandbox_report(report) + "\n",
        encoding="utf-8",
    )


def format_baseline_walk_forward_sandbox_report(
    report: BaselineWalkForwardSandboxReport,
) -> str:
    lines = [
        "# Baseline Walk-Forward Recommendation Sandbox v1",
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
        f"| Edge threshold | {report.edge_threshold} |",
        f"| Candidates | {report.total_candidates} |",
        f"| Profit | {report.total_profit} |",
        f"| ROI | {_format_optional(report.roi)} |",
        f"| Positive ROI folds | {report.positive_roi_folds} |",
        "",
        "## Fold Summary",
        "",
        "| Fold | Train | Validation | Bets | Profit | ROI | Positive ROI |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for fold in report.fold_reports:
        lines.append(
            f"| {fold.fold_index} | {fold.train_rows} | {fold.validation_rows} | "
            f"{fold.candidate_count} | {fold.profit} | {_format_optional(fold.roi)} | "
            f"{'yes' if fold.positive_roi else 'no'} |"
        )
    lines.extend(
        [
            "",
            "## Side Stability",
            "",
            "| Side | Bets | Positive ROI folds | Profit | ROI |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for summary in report.side_summaries:
        lines.append(
            f"| {summary.name} | {summary.candidate_count} | "
            f"{summary.positive_roi_folds} | {summary.profit} | "
            f"{_format_optional(summary.roi)} |"
        )
    for fold in report.fold_reports:
        lines.extend(
            [
                "",
                f"## Fold {fold.fold_index} Side Summary",
                "",
                "| Side | Bets | Wins | Profit | ROI |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        lines.extend(_summary_lines(fold.side_summaries))
        lines.extend(
            [
                "",
                f"## Fold {fold.fold_index} Candidate Detail",
                "",
                "| Match | Kickoff | League | Fixture | Line | Side | Odds | Model p | Market p | Edge | Actual | Profit |",
                "| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: |",
            ]
        )
        for candidate in fold.displayed_candidates:
            fixture = f"{candidate.home_team_name} vs {candidate.away_team_name}"
            lines.append(
                f"| {candidate.match_id} | {candidate.kickoff_time} | "
                f"{candidate.league_name} | {fixture} | {_format_optional(candidate.line)} | "
                f"{candidate.side} | {candidate.odds} | {candidate.model_probability} | "
                f"{candidate.market_probability} | {candidate.edge} | "
                f"{candidate.actual_side} | {candidate.profit} |"
            )
    return "\n".join(lines)


def _build_fold_report(
    fold_index: int,
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    *,
    edge_threshold: Decimal,
    top_n: int,
) -> WalkForwardSandboxFoldReport:
    train_eligible = [row for row in train_rows if _target_label(row) is not None]
    validation_eligible = [row for row in validation_rows if _target_label(row) is not None]
    candidates = [
        candidate
        for candidate in _build_candidates(train_eligible, validation_eligible)
        if candidate.edge >= edge_threshold
    ]
    candidates.sort(key=lambda candidate: (-candidate.edge, candidate.kickoff_time, candidate.match_id))
    profit = _quantize(sum((candidate.profit for candidate in candidates), Decimal("0")))
    roi = _ratio(profit, len(candidates))
    return WalkForwardSandboxFoldReport(
        fold_index=fold_index,
        train_rows=len(train_eligible),
        validation_rows=len(validation_eligible),
        candidate_count=len(candidates),
        profit=profit,
        roi=roi,
        positive_roi=roi is not None and roi > 0,
        side_summaries=_group_summaries(candidates, lambda candidate: candidate.side),
        displayed_candidates=candidates[:top_n],
    )


def _side_stability(
    fold_reports: list[WalkForwardSandboxFoldReport],
) -> list[WalkForwardSandboxSideSummary]:
    side_names = sorted(
        {
            summary.name
            for fold in fold_reports
            for summary in fold.side_summaries
        }
    )
    summaries = []
    for side_name in side_names:
        side_fold_summaries = [
            summary
            for fold in fold_reports
            for summary in fold.side_summaries
            if summary.name == side_name
        ]
        candidate_count = sum(summary.candidate_count for summary in side_fold_summaries)
        profit = _quantize(sum((summary.profit for summary in side_fold_summaries), Decimal("0")))
        summaries.append(
            WalkForwardSandboxSideSummary(
                name=side_name,
                candidate_count=candidate_count,
                positive_roi_folds=sum(1 for summary in side_fold_summaries if summary.roi > 0),
                profit=profit,
                roi=_ratio(profit, candidate_count),
            )
        )
    return sorted(summaries, key=lambda summary: (-summary.candidate_count, summary.name))


def _summary_lines(summaries: list[SandboxGroupSummary]) -> list[str]:
    if not summaries:
        return ["| - | 0 | 0 | - | - |"]
    return [
        f"| {summary.name} | {summary.candidate_count} | {summary.wins} | "
        f"{summary.profit} | {summary.roi} |"
        for summary in summaries
    ]


def _ratio(numerator: Decimal, denominator: int) -> Decimal | None:
    if denominator <= 0:
        return None
    return _quantize(numerator / Decimal(denominator))

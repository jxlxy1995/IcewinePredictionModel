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


DEFAULT_V3_THRESHOLDS = ("0.06", "0.08", "0.10", "0.12", "0.15", "0.18", "0.20")
DEFAULT_BASELINE_V2_THRESHOLDS = {
    "over@mid_2.75": Decimal("0.0800"),
    "under@mid_2.75": Decimal("0.0800"),
}
MIN_PROMOTABLE_BETS = 30
MIN_PROMOTABLE_POSITIVE_FOLDS = 4
MIN_PROMOTABLE_ROI = Decimal("0.0500")
MIN_PROMOTABLE_WORST_FOLD_ROI = Decimal("-0.2000")
WATCHLIST_MIN_ROI = Decimal("0.0000")


@dataclass(frozen=True)
class TotalGoalsV3FoldCandidateSet:
    fold_index: int
    train_rows: int
    validation_rows: int
    candidates: list[SandboxCandidate]


@dataclass(frozen=True)
class TotalGoalsV3SignalCandidateSummary:
    side_bucket: str
    side: str
    total_line_bucket: str
    threshold: Decimal
    rating: str
    candidate_count: int
    wins: int
    hit_rate: Decimal | None
    positive_roi_folds: int
    profit: Decimal
    roi: Decimal | None
    worst_fold_roi: Decimal | None
    overlap_count: int
    overlap_share: Decimal | None
    incremental_count: int
    incremental_profit: Decimal
    incremental_roi: Decimal | None


@dataclass(frozen=True)
class TotalGoalsV3SideBucketSummary:
    side_bucket: str
    candidate_count: int
    best_rating: str
    best_threshold: Decimal | None
    best_roi: Decimal | None
    best_positive_roi_folds: int


@dataclass(frozen=True)
class BaselineTotalGoalsV3SignalResearchReport:
    csv_path: Path
    row_count: int
    fold_count: int
    train_ratio: Decimal
    validation_ratio: Decimal
    thresholds: tuple[Decimal, ...]
    market_type: str
    model_name: str
    candidate_summaries: list[TotalGoalsV3SignalCandidateSummary]
    side_bucket_summaries: list[TotalGoalsV3SideBucketSummary]
    baseline_v2_count: int
    baseline_v2_profit: Decimal
    baseline_v2_roi: Decimal | None


def build_baseline_total_goals_v3_signal_research_report(
    csv_path: Path,
    *,
    thresholds: tuple[str, ...] = DEFAULT_V3_THRESHOLDS,
    train_ratio: str = "0.60",
    validation_ratio: str = "0.10",
    fold_count: int = 5,
) -> BaselineTotalGoalsV3SignalResearchReport:
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = sorted(
            list(csv.DictReader(file)),
            key=lambda row: (row.get("kickoff_time", ""), row.get("match_id", "")),
        )
    train_ratio_value = _as_decimal(train_ratio)
    validation_ratio_value = _as_decimal(validation_ratio)
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
    return build_total_goals_v3_signal_research_report_from_fold_candidates(
        csv_path,
        row_count=len(rows),
        train_ratio=train_ratio_value,
        validation_ratio=validation_ratio_value,
        fold_candidates=fold_candidates,
        thresholds=thresholds,
    )


def build_total_goals_v3_signal_research_report_from_fold_candidates(
    csv_path: Path,
    *,
    row_count: int,
    train_ratio: Decimal,
    validation_ratio: Decimal,
    fold_candidates: list[TotalGoalsV3FoldCandidateSet],
    thresholds: tuple[str, ...] = DEFAULT_V3_THRESHOLDS,
) -> BaselineTotalGoalsV3SignalResearchReport:
    threshold_values = tuple(_as_decimal(threshold) for threshold in thresholds)
    candidate_summaries = _candidate_summaries(fold_candidates, threshold_values)
    baseline_v2_candidates = _baseline_v2_candidates(fold_candidates)
    baseline_v2_profit = _candidate_profit(baseline_v2_candidates)
    return BaselineTotalGoalsV3SignalResearchReport(
        csv_path=csv_path,
        row_count=row_count,
        fold_count=len(fold_candidates),
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        thresholds=threshold_values,
        market_type="total_goals",
        model_name=MODEL_NAME,
        candidate_summaries=candidate_summaries,
        side_bucket_summaries=_side_bucket_summaries(candidate_summaries),
        baseline_v2_count=len(baseline_v2_candidates),
        baseline_v2_profit=baseline_v2_profit,
        baseline_v2_roi=_ratio(baseline_v2_profit, len(baseline_v2_candidates)),
    )


def write_baseline_total_goals_v3_signal_research_report(
    report: BaselineTotalGoalsV3SignalResearchReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_baseline_total_goals_v3_signal_research_report(report) + "\n",
        encoding="utf-8",
    )


def format_baseline_total_goals_v3_signal_research_report(
    report: BaselineTotalGoalsV3SignalResearchReport,
) -> str:
    rating_counts = {
        rating: sum(1 for summary in report.candidate_summaries if summary.rating == rating)
        for rating in ("promotable", "watchlist", "rejected")
    }
    lines = [
        "# Baseline Total Goals v3 Signal Research",
        "",
        f"- Feature CSV: `{report.csv_path}`",
        f"- Scope: `{report.market_type} {report.model_name}`",
        "- Workflow: research only; no paper strategy registration",
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
        f"| Baseline v2 bets | {report.baseline_v2_count} |",
        f"| Baseline v2 profit | {report.baseline_v2_profit} |",
        f"| Baseline v2 ROI | {_format_optional(report.baseline_v2_roi)} |",
        "",
        "## Rating Counts",
        "",
        "| Rating | Candidates |",
        "| --- | ---: |",
    ]
    for rating in ("promotable", "watchlist", "rejected"):
        lines.append(f"| {rating} | {rating_counts[rating]} |")
    lines.extend(
        [
            "",
            "## Candidate Grid",
            "",
            (
                "| Side bucket | Threshold | Rating | Bets | Wins | Hit rate | Profit | ROI | "
                "Positive ROI folds | Worst fold ROI | Overlap | Overlap share | "
                "Incremental bets | Incremental ROI |"
            ),
            "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    if not report.candidate_summaries:
        lines.append("| - | - | rejected | 0 | 0 | - | 0.0000 | - | 0 | - | 0 | - | 0 | - |")
    for summary in report.candidate_summaries:
        lines.append(
            f"| {summary.side_bucket} | {summary.threshold} | {summary.rating} | "
            f"{summary.candidate_count} | {summary.wins} | {_format_optional(summary.hit_rate)} | "
            f"{summary.profit} | {_format_optional(summary.roi)} | "
            f"{summary.positive_roi_folds} | {_format_optional(summary.worst_fold_roi)} | "
            f"{summary.overlap_count} | {_format_optional(summary.overlap_share)} | "
            f"{summary.incremental_count} | {_format_optional(summary.incremental_roi)} |"
        )
    lines.extend(
        [
            "",
            "## Side Bucket Overview",
            "",
            "| Side bucket | Bets | Best rating | Best threshold | Best ROI | Best positive ROI folds |",
            "| --- | ---: | --- | ---: | ---: | ---: |",
        ]
    )
    for summary in report.side_bucket_summaries:
        lines.append(
            f"| {summary.side_bucket} | {summary.candidate_count} | {summary.best_rating} | "
            f"{_format_optional(summary.best_threshold)} | {_format_optional(summary.best_roi)} | "
            f"{summary.best_positive_roi_folds} |"
        )
    lines.extend(["", "## Promotion Recommendation", ""])
    promotable = [summary for summary in report.candidate_summaries if summary.rating == "promotable"]
    watchlist = [summary for summary in report.candidate_summaries if summary.rating == "watchlist"]
    if promotable:
        lines.append("Promotable candidates:")
        for summary in promotable:
            overlap_note = (
                "baseline-overlap"
                if summary.overlap_share is not None and summary.overlap_share >= Decimal("0.8000")
                else "incremental"
            )
            lines.append(
                f"- `{summary.side_bucket}` at `{summary.threshold}`: ROI {_format_optional(summary.roi)}, "
                f"{summary.positive_roi_folds}/{report.fold_count} positive folds, {overlap_note}."
            )
    else:
        lines.append("No candidate passes the promotion gate.")
    if watchlist:
        lines.extend(["", "Watchlist candidates:"])
        for summary in watchlist[:10]:
            lines.append(
                f"- `{summary.side_bucket}` at `{summary.threshold}`: ROI {_format_optional(summary.roi)}, "
                f"{summary.positive_roi_folds}/{report.fold_count} positive folds."
            )
    return "\n".join(lines)


def _build_fold_candidates(
    fold_index: int,
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
) -> TotalGoalsV3FoldCandidateSet:
    train_eligible = [row for row in train_rows if _target_label(row) is not None]
    validation_eligible = [row for row in validation_rows if _target_label(row) is not None]
    return TotalGoalsV3FoldCandidateSet(
        fold_index=fold_index,
        train_rows=len(train_eligible),
        validation_rows=len(validation_eligible),
        candidates=_build_total_goals_candidates(train_eligible, validation_eligible),
    )


def _candidate_summaries(
    fold_candidates: list[TotalGoalsV3FoldCandidateSet],
    thresholds: tuple[Decimal, ...],
) -> list[TotalGoalsV3SignalCandidateSummary]:
    side_buckets = sorted(
        {_side_bucket(candidate) for fold in fold_candidates for candidate in fold.candidates}
    )
    summaries = [
        _candidate_summary(side_bucket, threshold, fold_candidates)
        for side_bucket in side_buckets
        for threshold in thresholds
    ]
    summaries = [summary for summary in summaries if summary.candidate_count > 0]
    return sorted(
        summaries,
        key=lambda summary: (
            _rating_rank(summary.rating),
            -(summary.roi or Decimal("-999")),
            -summary.positive_roi_folds,
            -summary.candidate_count,
            summary.side_bucket,
            summary.threshold,
        ),
    )


def _candidate_summary(
    side_bucket: str,
    threshold: Decimal,
    fold_candidates: list[TotalGoalsV3FoldCandidateSet],
) -> TotalGoalsV3SignalCandidateSummary:
    candidate_groups = [
        [
            candidate
            for candidate in fold.candidates
            if _side_bucket(candidate) == side_bucket and candidate.edge >= threshold
        ]
        for fold in fold_candidates
    ]
    candidates = [candidate for group in candidate_groups for candidate in group]
    profit = _candidate_profit(candidates)
    roi = _ratio(profit, len(candidates))
    wins = sum(1 for candidate in candidates if candidate.profit > 0)
    fold_rois = [_ratio(_candidate_profit(group), len(group)) for group in candidate_groups]
    worst_fold_roi = _worst_roi(fold_rois)
    positive_roi_folds = sum(1 for fold_roi in fold_rois if fold_roi is not None and fold_roi > 0)
    overlap_candidates = [
        candidate for candidate in candidates if _is_baseline_v2_candidate(candidate)
    ]
    incremental_candidates = [
        candidate for candidate in candidates if not _is_baseline_v2_candidate(candidate)
    ]
    incremental_profit = _candidate_profit(incremental_candidates)
    side, total_line_bucket = _split_side_bucket(side_bucket)
    return TotalGoalsV3SignalCandidateSummary(
        side_bucket=side_bucket,
        side=side,
        total_line_bucket=total_line_bucket,
        threshold=threshold,
        rating=_rating(
            candidate_count=len(candidates),
            roi=roi,
            positive_roi_folds=positive_roi_folds,
            worst_fold_roi=worst_fold_roi,
        ),
        candidate_count=len(candidates),
        wins=wins,
        hit_rate=_ratio(Decimal(wins), len(candidates)),
        positive_roi_folds=positive_roi_folds,
        profit=profit,
        roi=roi,
        worst_fold_roi=worst_fold_roi,
        overlap_count=len(overlap_candidates),
        overlap_share=_ratio(Decimal(len(overlap_candidates)), len(candidates)),
        incremental_count=len(incremental_candidates),
        incremental_profit=incremental_profit,
        incremental_roi=_ratio(incremental_profit, len(incremental_candidates)),
    )


def _side_bucket_summaries(
    candidate_summaries: list[TotalGoalsV3SignalCandidateSummary],
) -> list[TotalGoalsV3SideBucketSummary]:
    side_buckets = sorted({summary.side_bucket for summary in candidate_summaries})
    summaries = []
    for side_bucket in side_buckets:
        matching = [summary for summary in candidate_summaries if summary.side_bucket == side_bucket]
        best = sorted(
            matching,
            key=lambda summary: (
                _rating_rank(summary.rating),
                -(summary.roi or Decimal("-999")),
                -summary.candidate_count,
            ),
        )[0]
        summaries.append(
            TotalGoalsV3SideBucketSummary(
                side_bucket=side_bucket,
                candidate_count=max(summary.candidate_count for summary in matching),
                best_rating=best.rating,
                best_threshold=best.threshold,
                best_roi=best.roi,
                best_positive_roi_folds=best.positive_roi_folds,
            )
        )
    return summaries


def _baseline_v2_candidates(
    fold_candidates: list[TotalGoalsV3FoldCandidateSet],
) -> list[SandboxCandidate]:
    return [
        candidate
        for fold in fold_candidates
        for candidate in fold.candidates
        if _is_baseline_v2_candidate(candidate)
    ]


def _is_baseline_v2_candidate(candidate: SandboxCandidate) -> bool:
    side_bucket = _side_bucket(candidate)
    threshold = DEFAULT_BASELINE_V2_THRESHOLDS.get(side_bucket)
    return threshold is not None and candidate.edge >= threshold


def _side_bucket(candidate: SandboxCandidate) -> str:
    return f"{candidate.side}@{_total_line_bucket(candidate)}"


def _split_side_bucket(side_bucket: str) -> tuple[str, str]:
    if "@" not in side_bucket:
        return side_bucket, "unknown"
    return tuple(side_bucket.split("@", maxsplit=1))  # type: ignore[return-value]


def _candidate_profit(candidates: list[SandboxCandidate]) -> Decimal:
    return _quantize(sum((candidate.profit for candidate in candidates), Decimal("0")))


def _ratio(numerator: Decimal, denominator: int) -> Decimal | None:
    if denominator <= 0:
        return None
    return _quantize(numerator / Decimal(denominator))


def _worst_roi(values: list[Decimal | None]) -> Decimal | None:
    actual_values = [value for value in values if value is not None]
    if not actual_values:
        return None
    return min(actual_values)


def _rating(
    *,
    candidate_count: int,
    roi: Decimal | None,
    positive_roi_folds: int,
    worst_fold_roi: Decimal | None,
) -> str:
    if (
        candidate_count >= MIN_PROMOTABLE_BETS
        and positive_roi_folds >= MIN_PROMOTABLE_POSITIVE_FOLDS
        and roi is not None
        and roi >= MIN_PROMOTABLE_ROI
        and worst_fold_roi is not None
        and worst_fold_roi >= MIN_PROMOTABLE_WORST_FOLD_ROI
    ):
        return "promotable"
    if roi is not None and roi > WATCHLIST_MIN_ROI:
        return "watchlist"
    return "rejected"


def _rating_rank(rating: str) -> int:
    return {"promotable": 0, "watchlist": 1, "rejected": 2}.get(rating, 9)

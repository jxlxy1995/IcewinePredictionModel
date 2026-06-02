from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from icewine_prediction.baseline_asian_handicap_model_service import _target_label
from icewine_prediction.baseline_away_cover_bucket_threshold_service import MODEL_NAME
from icewine_prediction.baseline_recommendation_sandbox_service import (
    SandboxCandidate,
    _as_decimal,
    _build_candidates,
    _format_optional,
    _quantize,
)
from icewine_prediction.baseline_walk_forward_edge_service import _walk_forward_folds


DEFAULT_HOME_COVER_THRESHOLDS = ("0.06", "0.08", "0.10", "0.12", "0.15", "0.18", "0.20")
MIN_PROMOTABLE_BETS = 30
MIN_PROMOTABLE_POSITIVE_FOLDS = 4
MIN_PROMOTABLE_ROI = Decimal("0.0500")
MIN_PROMOTABLE_WORST_FOLD_ROI = Decimal("-0.2000")
WATCHLIST_MIN_ROI = Decimal("0.0000")


@dataclass(frozen=True)
class HomeCoverFoldCandidateSet:
    fold_index: int
    train_rows: int
    validation_rows: int
    candidates: list[SandboxCandidate]


@dataclass(frozen=True)
class HomeCoverSignalCandidateSummary:
    line_bucket: str
    threshold: Decimal
    rating: str
    candidate_count: int
    wins: int
    hit_rate: Decimal | None
    positive_roi_folds: int
    profit: Decimal
    roi: Decimal | None
    worst_fold_roi: Decimal | None


@dataclass(frozen=True)
class HomeCoverLineBucketSummary:
    line_bucket: str
    candidate_count: int
    best_rating: str
    best_threshold: Decimal | None
    best_roi: Decimal | None
    best_positive_roi_folds: int


@dataclass(frozen=True)
class BaselineHomeCoverSignalResearchReport:
    csv_path: Path
    row_count: int
    fold_count: int
    train_ratio: Decimal
    validation_ratio: Decimal
    thresholds: tuple[Decimal, ...]
    market_type: str
    model_name: str
    side: str
    candidate_summaries: list[HomeCoverSignalCandidateSummary]
    line_bucket_summaries: list[HomeCoverLineBucketSummary]


def build_baseline_home_cover_signal_research_report(
    csv_path: Path,
    *,
    thresholds: tuple[str, ...] = DEFAULT_HOME_COVER_THRESHOLDS,
    train_ratio: str = "0.60",
    validation_ratio: str = "0.10",
    fold_count: int = 5,
) -> BaselineHomeCoverSignalResearchReport:
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
    return build_home_cover_signal_research_report_from_fold_candidates(
        csv_path,
        row_count=len(rows),
        train_ratio=train_ratio_value,
        validation_ratio=validation_ratio_value,
        fold_candidates=fold_candidates,
        thresholds=thresholds,
    )


def build_home_cover_signal_research_report_from_fold_candidates(
    csv_path: Path,
    *,
    row_count: int,
    train_ratio: Decimal,
    validation_ratio: Decimal,
    fold_candidates: list[HomeCoverFoldCandidateSet],
    thresholds: tuple[str, ...] = DEFAULT_HOME_COVER_THRESHOLDS,
) -> BaselineHomeCoverSignalResearchReport:
    threshold_values = tuple(_as_decimal(threshold) for threshold in thresholds)
    candidate_summaries = _candidate_summaries(fold_candidates, threshold_values)
    return BaselineHomeCoverSignalResearchReport(
        csv_path=csv_path,
        row_count=row_count,
        fold_count=len(fold_candidates),
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        thresholds=threshold_values,
        market_type="asian_handicap",
        model_name=MODEL_NAME,
        side="home_cover",
        candidate_summaries=candidate_summaries,
        line_bucket_summaries=_line_bucket_summaries(candidate_summaries),
    )


def write_baseline_home_cover_signal_research_report(
    report: BaselineHomeCoverSignalResearchReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_baseline_home_cover_signal_research_report(report) + "\n",
        encoding="utf-8",
    )


def format_baseline_home_cover_signal_research_report(
    report: BaselineHomeCoverSignalResearchReport,
) -> str:
    rating_counts = {
        rating: sum(1 for summary in report.candidate_summaries if summary.rating == rating)
        for rating in ("promotable", "watchlist", "rejected")
    }
    lines = [
        "# Baseline Home Cover Signal Research",
        "",
        f"- Feature CSV: `{report.csv_path}`",
        f"- Scope: `{report.market_type} {report.model_name} {report.side}`",
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
                "| Line bucket | Threshold | Rating | Bets | Wins | Hit rate | Profit | ROI | "
                "Positive ROI folds | Worst fold ROI |"
            ),
            "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    if not report.candidate_summaries:
        lines.append("| - | - | rejected | 0 | 0 | - | 0.0000 | - | 0 | - |")
    for summary in report.candidate_summaries:
        lines.append(
            f"| {summary.line_bucket} | {summary.threshold} | {summary.rating} | "
            f"{summary.candidate_count} | {summary.wins} | {_format_optional(summary.hit_rate)} | "
            f"{summary.profit} | {_format_optional(summary.roi)} | "
            f"{summary.positive_roi_folds} | {_format_optional(summary.worst_fold_roi)} |"
        )
    lines.extend(
        [
            "",
            "## Line Bucket Overview",
            "",
            "| Line bucket | Bets | Best rating | Best threshold | Best ROI | Best positive ROI folds |",
            "| --- | ---: | --- | ---: | ---: | ---: |",
        ]
    )
    for summary in report.line_bucket_summaries:
        lines.append(
            f"| {summary.line_bucket} | {summary.candidate_count} | {summary.best_rating} | "
            f"{_format_optional(summary.best_threshold)} | {_format_optional(summary.best_roi)} | "
            f"{summary.best_positive_roi_folds} |"
        )
    lines.extend(["", "## Promotion Recommendation", ""])
    promotable = [summary for summary in report.candidate_summaries if summary.rating == "promotable"]
    watchlist = [summary for summary in report.candidate_summaries if summary.rating == "watchlist"]
    if promotable:
        lines.append("Promotable candidates:")
        for summary in promotable:
            lines.append(
                f"- `{summary.line_bucket}` at `{summary.threshold}`: ROI {_format_optional(summary.roi)}, "
                f"{summary.positive_roi_folds}/{report.fold_count} positive folds."
            )
    else:
        lines.append("No candidate passes the promotion gate.")
    if watchlist:
        lines.extend(["", "Watchlist candidates:"])
        for summary in watchlist[:10]:
            lines.append(
                f"- `{summary.line_bucket}` at `{summary.threshold}`: ROI {_format_optional(summary.roi)}, "
                f"{summary.positive_roi_folds}/{report.fold_count} positive folds."
            )
    return "\n".join(lines)


def _build_fold_candidates(
    fold_index: int,
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
) -> HomeCoverFoldCandidateSet:
    train_eligible = [row for row in train_rows if _target_label(row) is not None]
    validation_eligible = [row for row in validation_rows if _target_label(row) is not None]
    candidates = [
        candidate
        for candidate in _build_candidates(train_eligible, validation_eligible)
        if candidate.side == "home_cover"
    ]
    return HomeCoverFoldCandidateSet(
        fold_index=fold_index,
        train_rows=len(train_eligible),
        validation_rows=len(validation_eligible),
        candidates=candidates,
    )


def _candidate_summaries(
    fold_candidates: list[HomeCoverFoldCandidateSet],
    thresholds: tuple[Decimal, ...],
) -> list[HomeCoverSignalCandidateSummary]:
    line_buckets = sorted(
        {_line_bucket(candidate) for fold in fold_candidates for candidate in fold.candidates}
    )
    summaries = [
        _candidate_summary(line_bucket, threshold, fold_candidates)
        for line_bucket in line_buckets
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
            summary.line_bucket,
            summary.threshold,
        ),
    )


def _candidate_summary(
    line_bucket: str,
    threshold: Decimal,
    fold_candidates: list[HomeCoverFoldCandidateSet],
) -> HomeCoverSignalCandidateSummary:
    candidate_groups = [
        [
            candidate
            for candidate in fold.candidates
            if _line_bucket(candidate) == line_bucket and candidate.edge >= threshold
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
    return HomeCoverSignalCandidateSummary(
        line_bucket=line_bucket,
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
    )


def _line_bucket_summaries(
    candidate_summaries: list[HomeCoverSignalCandidateSummary],
) -> list[HomeCoverLineBucketSummary]:
    line_buckets = sorted({summary.line_bucket for summary in candidate_summaries})
    summaries = []
    for line_bucket in line_buckets:
        matching = [summary for summary in candidate_summaries if summary.line_bucket == line_bucket]
        best = sorted(
            matching,
            key=lambda summary: (
                _rating_rank(summary.rating),
                -(summary.roi or Decimal("-999")),
                -summary.candidate_count,
            ),
        )[0]
        summaries.append(
            HomeCoverLineBucketSummary(
                line_bucket=line_bucket,
                candidate_count=max(summary.candidate_count for summary in matching),
                best_rating=best.rating,
                best_threshold=best.threshold,
                best_roi=best.roi,
                best_positive_roi_folds=best.positive_roi_folds,
            )
        )
    return summaries


def _line_bucket(candidate: SandboxCandidate) -> str:
    line = candidate.line
    if line is None:
        return "unknown"
    if line < 0:
        return "home_favorite"
    if line == 0:
        return "pickem"
    return "home_underdog"


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

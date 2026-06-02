from __future__ import annotations

import csv
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import numpy as np

from icewine_prediction.baseline_asian_handicap_model_service import (
    SIDE_LABELS as ASIAN_HANDICAP_SIDE_LABELS,
    _align_probabilities as _align_asian_handicap_probabilities,
    _target_label as _asian_handicap_target_label,
)
from icewine_prediction.baseline_edge_backtest_service import (
    FEATURES,
    _calibrated_model,
    _decimal_from_row,
    _market_probabilities,
    _raw_model,
)
from icewine_prediction.baseline_match_winner_model_service import _matrix
from icewine_prediction.baseline_recommendation_sandbox_service import (
    _as_decimal,
    _format_optional,
    _profit,
    _quantize,
)
from icewine_prediction.baseline_total_goals_model_service import (
    SIDE_LABELS as TOTAL_GOALS_SIDE_LABELS,
    _align_probabilities as _align_total_goals_probabilities,
    _target_label as _total_goals_target_label,
)
from icewine_prediction.baseline_walk_forward_edge_service import _walk_forward_folds


DEFAULT_CONSENSUS_THRESHOLDS = ("0.06", "0.08", "0.10", "0.12", "0.15", "0.18", "0.20")
MIN_PROMOTABLE_BETS = 30
MIN_PROMOTABLE_POSITIVE_FOLDS = 4
MIN_PROMOTABLE_ROI = Decimal("0.0500")
MIN_PROMOTABLE_WORST_FOLD_ROI = Decimal("-0.2000")
WATCHLIST_MIN_ROI = Decimal("0.0000")
MODEL_NAME = "raw_hgb_vs_calibrated_hgb_team_form_plus_all_markets"


@dataclass(frozen=True)
class ModelConsensusCandidate:
    match_id: str
    kickoff_time: str
    league_name: str
    home_team_name: str
    away_team_name: str
    market_type: str
    line: Decimal | None
    side: str
    odds: Decimal
    raw_edge: Decimal
    calibrated_side: str
    calibrated_edge_for_raw_side: Decimal
    actual_side: str
    profit: Decimal


@dataclass(frozen=True)
class ModelConsensusFoldCandidateSet:
    fold_index: int
    train_rows: int
    validation_rows: int
    candidates: list[ModelConsensusCandidate]


@dataclass(frozen=True)
class ModelConsensusSignalCandidateSummary:
    signal_bucket: str
    market_type: str
    agreement_bucket: str
    side_bucket: str
    threshold: Decimal
    rating: str
    candidate_count: int
    wins: int
    hit_rate: Decimal | None
    positive_roi_folds: int
    profit: Decimal
    roi: Decimal | None
    worst_fold_roi: Decimal | None
    avg_raw_edge: Decimal | None
    avg_calibrated_edge: Decimal | None


@dataclass(frozen=True)
class ModelConsensusBucketSummary:
    signal_bucket: str
    candidate_count: int
    best_rating: str
    best_threshold: Decimal | None
    best_roi: Decimal | None
    best_positive_roi_folds: int


@dataclass(frozen=True)
class BaselineModelConsensusSignalResearchReport:
    csv_path: Path
    row_count: int
    fold_count: int
    train_ratio: Decimal
    validation_ratio: Decimal
    thresholds: tuple[Decimal, ...]
    confirmation_threshold: Decimal
    model_name: str
    candidate_summaries: list[ModelConsensusSignalCandidateSummary]
    bucket_summaries: list[ModelConsensusBucketSummary]


@dataclass(frozen=True)
class _MarketConfig:
    market_type: str
    side_labels: tuple[str, str]
    odds_fields: tuple[str, str]
    probability_fields: tuple[str, str]
    line_field: str
    target_label_builder: Callable[[dict[str, str]], str | None]
    probability_aligner: Callable[[object, list[str]], list[list[float]]]


MARKET_CONFIGS = (
    _MarketConfig(
        market_type="asian_handicap",
        side_labels=ASIAN_HANDICAP_SIDE_LABELS,
        odds_fields=("asian_handicap_home_odds", "asian_handicap_away_odds"),
        probability_fields=(
            "asian_handicap_home_implied_probability",
            "asian_handicap_away_implied_probability",
        ),
        line_field="asian_handicap_close_line",
        target_label_builder=_asian_handicap_target_label,
        probability_aligner=_align_asian_handicap_probabilities,
    ),
    _MarketConfig(
        market_type="total_goals",
        side_labels=TOTAL_GOALS_SIDE_LABELS,
        odds_fields=("total_goals_over_odds", "total_goals_under_odds"),
        probability_fields=(
            "total_goals_over_implied_probability",
            "total_goals_under_implied_probability",
        ),
        line_field="total_goals_close_line",
        target_label_builder=_total_goals_target_label,
        probability_aligner=_align_total_goals_probabilities,
    ),
)


def build_baseline_model_consensus_signal_research_report(
    csv_path: Path,
    *,
    thresholds: tuple[str, ...] = DEFAULT_CONSENSUS_THRESHOLDS,
    confirmation_threshold: str = "0.00",
    train_ratio: str = "0.60",
    validation_ratio: str = "0.10",
    fold_count: int = 5,
) -> BaselineModelConsensusSignalResearchReport:
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
    return build_model_consensus_signal_research_report_from_fold_candidates(
        csv_path,
        row_count=len(rows),
        train_ratio=train_ratio_value,
        validation_ratio=validation_ratio_value,
        fold_candidates=fold_candidates,
        thresholds=thresholds,
        confirmation_threshold=confirmation_threshold,
    )


def build_model_consensus_signal_research_report_from_fold_candidates(
    csv_path: Path,
    *,
    row_count: int,
    train_ratio: Decimal,
    validation_ratio: Decimal,
    fold_candidates: list[ModelConsensusFoldCandidateSet],
    thresholds: tuple[str, ...] = DEFAULT_CONSENSUS_THRESHOLDS,
    confirmation_threshold: str = "0.00",
) -> BaselineModelConsensusSignalResearchReport:
    threshold_values = tuple(_as_decimal(threshold) for threshold in thresholds)
    confirmation_threshold_value = _as_decimal(confirmation_threshold)
    candidate_summaries = _candidate_summaries(
        fold_candidates,
        threshold_values,
        confirmation_threshold=confirmation_threshold_value,
    )
    return BaselineModelConsensusSignalResearchReport(
        csv_path=csv_path,
        row_count=row_count,
        fold_count=len(fold_candidates),
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        thresholds=threshold_values,
        confirmation_threshold=confirmation_threshold_value,
        model_name=MODEL_NAME,
        candidate_summaries=candidate_summaries,
        bucket_summaries=_bucket_summaries(candidate_summaries),
    )


def write_baseline_model_consensus_signal_research_report(
    report: BaselineModelConsensusSignalResearchReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_baseline_model_consensus_signal_research_report(report) + "\n",
        encoding="utf-8",
    )


def format_baseline_model_consensus_signal_research_report(
    report: BaselineModelConsensusSignalResearchReport,
) -> str:
    rating_counts = {
        rating: sum(1 for summary in report.candidate_summaries if summary.rating == rating)
        for rating in ("promotable", "watchlist", "rejected")
    }
    lines = [
        "# Baseline Model Consensus Signal Research",
        "",
        f"- Feature CSV: `{report.csv_path}`",
        f"- Scope: `{report.model_name}`",
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
        f"| Confirmation threshold | {report.confirmation_threshold} |",
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
                "| Signal bucket | Threshold | Rating | Bets | Wins | Hit rate | Profit | ROI | "
                "Positive ROI folds | Worst fold ROI | Avg raw edge | Avg calibrated edge |"
            ),
            "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    if not report.candidate_summaries:
        lines.append("| - | - | rejected | 0 | 0 | - | 0.0000 | - | 0 | - | - | - |")
    for summary in report.candidate_summaries:
        lines.append(
            f"| {summary.signal_bucket} | {summary.threshold} | {summary.rating} | "
            f"{summary.candidate_count} | {summary.wins} | {_format_optional(summary.hit_rate)} | "
            f"{summary.profit} | {_format_optional(summary.roi)} | "
            f"{summary.positive_roi_folds} | {_format_optional(summary.worst_fold_roi)} | "
            f"{_format_optional(summary.avg_raw_edge)} | {_format_optional(summary.avg_calibrated_edge)} |"
        )
    lines.extend(
        [
            "",
            "## Bucket Overview",
            "",
            "| Signal bucket | Bets | Best rating | Best threshold | Best ROI | Best positive ROI folds |",
            "| --- | ---: | --- | ---: | ---: | ---: |",
        ]
    )
    for summary in report.bucket_summaries:
        lines.append(
            f"| {summary.signal_bucket} | {summary.candidate_count} | {summary.best_rating} | "
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
                f"- `{summary.signal_bucket}` at `{summary.threshold}`: ROI {_format_optional(summary.roi)}, "
                f"{summary.positive_roi_folds}/{report.fold_count} positive folds."
            )
    else:
        lines.append("No candidate passes the promotion gate.")
    if watchlist:
        lines.extend(["", "Watchlist candidates:"])
        for summary in watchlist[:10]:
            lines.append(
                f"- `{summary.signal_bucket}` at `{summary.threshold}`: ROI {_format_optional(summary.roi)}, "
                f"{summary.positive_roi_folds}/{report.fold_count} positive folds."
            )
    return "\n".join(lines)


def _build_fold_candidates(
    fold_index: int,
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
) -> ModelConsensusFoldCandidateSet:
    candidates: list[ModelConsensusCandidate] = []
    train_rows_by_market: list[list[dict[str, str]]] = []
    validation_rows_by_market: list[list[dict[str, str]]] = []
    for config in MARKET_CONFIGS:
        market_train_rows = [row for row in train_rows if config.target_label_builder(row) is not None]
        market_validation_rows = [row for row in validation_rows if config.target_label_builder(row) is not None]
        train_rows_by_market.append(market_train_rows)
        validation_rows_by_market.append(market_validation_rows)
        candidates.extend(_build_market_candidates(config, market_train_rows, market_validation_rows))
    return ModelConsensusFoldCandidateSet(
        fold_index=fold_index,
        train_rows=sum(len(rows) for rows in train_rows_by_market),
        validation_rows=sum(len(rows) for rows in validation_rows_by_market),
        candidates=candidates,
    )


def _build_market_candidates(
    config: _MarketConfig,
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
) -> list[ModelConsensusCandidate]:
    if not train_rows or not validation_rows:
        return []
    train_x = _matrix(train_rows, FEATURES)
    validation_x = _matrix(validation_rows, FEATURES)
    train_y = np.asarray([config.target_label_builder(row) for row in train_rows])
    raw_model = _raw_model()
    raw_model.fit(train_x, train_y)
    calibrated_model = _calibrated_model()
    calibrated_model.fit(train_x, train_y)
    raw_probabilities = config.probability_aligner(
        raw_model.predict_proba(validation_x),
        list(raw_model.named_steps["classifier"].classes_),
    )
    calibrated_probabilities = config.probability_aligner(
        calibrated_model.predict_proba(validation_x),
        list(calibrated_model.classes_),
    )
    candidates = []
    for row, raw_row, calibrated_row in zip(
        validation_rows,
        raw_probabilities,
        calibrated_probabilities,
        strict=True,
    ):
        candidate = _consensus_candidate(config, row, raw_row, calibrated_row)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _consensus_candidate(
    config: _MarketConfig,
    row: dict[str, str],
    raw_probabilities: list[float],
    calibrated_probabilities: list[float],
) -> ModelConsensusCandidate | None:
    actual_side = config.target_label_builder(row)
    if actual_side is None:
        return None
    market_probabilities = _market_probabilities(row, config.probability_fields)
    if market_probabilities is None:
        return None
    raw_edges = [
        Decimal(str(raw_probabilities[index])) - market_probabilities[index]
        for index in range(len(config.side_labels))
    ]
    calibrated_edges = [
        Decimal(str(calibrated_probabilities[index])) - market_probabilities[index]
        for index in range(len(config.side_labels))
    ]
    raw_index = max(range(len(config.side_labels)), key=lambda index: raw_edges[index])
    calibrated_index = max(range(len(config.side_labels)), key=lambda index: calibrated_edges[index])
    odds = _decimal_from_row(row, config.odds_fields[raw_index])
    if odds is None or odds <= Decimal("1.0"):
        return None
    side = config.side_labels[raw_index]
    return ModelConsensusCandidate(
        match_id=row.get("match_id", ""),
        kickoff_time=row.get("kickoff_time", ""),
        league_name=row.get("league_name", ""),
        home_team_name=row.get("home_team_name", ""),
        away_team_name=row.get("away_team_name", ""),
        market_type=config.market_type,
        line=_decimal_from_row(row, config.line_field),
        side=side,
        odds=odds,
        raw_edge=_quantize(raw_edges[raw_index]),
        calibrated_side=config.side_labels[calibrated_index],
        calibrated_edge_for_raw_side=_quantize(calibrated_edges[raw_index]),
        actual_side=actual_side,
        profit=_profit(side == actual_side, odds),
    )


def _candidate_summaries(
    fold_candidates: list[ModelConsensusFoldCandidateSet],
    thresholds: tuple[Decimal, ...],
    *,
    confirmation_threshold: Decimal,
) -> list[ModelConsensusSignalCandidateSummary]:
    signal_buckets = sorted(
        {
            _signal_bucket(candidate, confirmation_threshold=confirmation_threshold)
            for fold in fold_candidates
            for candidate in fold.candidates
        }
    )
    summaries = [
        _candidate_summary(
            signal_bucket,
            threshold,
            fold_candidates,
            confirmation_threshold=confirmation_threshold,
        )
        for signal_bucket in signal_buckets
        for threshold in thresholds
    ]
    summaries = [summary for summary in summaries if summary.candidate_count > 0]
    return sorted(
        summaries,
        key=lambda summary: (
            _rating_rank(summary.rating),
            summary.agreement_bucket != "confirmed",
            -(summary.roi or Decimal("-999")),
            -summary.positive_roi_folds,
            -summary.candidate_count,
            summary.signal_bucket,
            summary.threshold,
        ),
    )


def _candidate_summary(
    signal_bucket: str,
    threshold: Decimal,
    fold_candidates: list[ModelConsensusFoldCandidateSet],
    *,
    confirmation_threshold: Decimal,
) -> ModelConsensusSignalCandidateSummary:
    candidate_groups = [
        [
            candidate
            for candidate in fold.candidates
            if _signal_bucket(candidate, confirmation_threshold=confirmation_threshold) == signal_bucket
            and candidate.raw_edge >= threshold
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
    market_type, agreement_bucket, side_bucket = _split_signal_bucket(signal_bucket)
    return ModelConsensusSignalCandidateSummary(
        signal_bucket=signal_bucket,
        market_type=market_type,
        agreement_bucket=agreement_bucket,
        side_bucket=side_bucket,
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
        avg_raw_edge=_average([candidate.raw_edge for candidate in candidates]),
        avg_calibrated_edge=_average([candidate.calibrated_edge_for_raw_side for candidate in candidates]),
    )


def _bucket_summaries(
    candidate_summaries: list[ModelConsensusSignalCandidateSummary],
) -> list[ModelConsensusBucketSummary]:
    signal_buckets = sorted({summary.signal_bucket for summary in candidate_summaries})
    summaries = []
    for signal_bucket in signal_buckets:
        matching = [summary for summary in candidate_summaries if summary.signal_bucket == signal_bucket]
        best = sorted(
            matching,
            key=lambda summary: (
                _rating_rank(summary.rating),
                -(summary.roi or Decimal("-999")),
                -summary.candidate_count,
            ),
        )[0]
        summaries.append(
            ModelConsensusBucketSummary(
                signal_bucket=signal_bucket,
                candidate_count=max(summary.candidate_count for summary in matching),
                best_rating=best.rating,
                best_threshold=best.threshold,
                best_roi=best.roi,
                best_positive_roi_folds=best.positive_roi_folds,
            )
        )
    return summaries


def _signal_bucket(candidate: ModelConsensusCandidate, *, confirmation_threshold: Decimal) -> str:
    agreement_bucket = (
        "confirmed"
        if candidate.calibrated_side == candidate.side
        and candidate.calibrated_edge_for_raw_side >= confirmation_threshold
        else "diverged"
    )
    return f"{candidate.market_type}:{agreement_bucket}:{candidate.side}@{_line_bucket(candidate)}"


def _line_bucket(candidate: ModelConsensusCandidate) -> str:
    if candidate.market_type == "total_goals":
        return _total_line_bucket(candidate.line)
    return _asian_line_bucket(candidate.line)


def _asian_line_bucket(line: Decimal | None) -> str:
    if line is None:
        return "unknown"
    if line < 0:
        return "home_favorite"
    if line == 0:
        return "pickem"
    return "home_underdog"


def _total_line_bucket(line: Decimal | None) -> str:
    if line is None:
        return "unknown"
    if line <= Decimal("2.25"):
        return "low_<=2.25"
    if line == Decimal("2.50"):
        return "mid_2.50"
    if line == Decimal("2.75"):
        return "mid_2.75"
    return "high_>=3.00"


def _split_signal_bucket(signal_bucket: str) -> tuple[str, str, str]:
    market_type, agreement_bucket, side_bucket = signal_bucket.split(":", maxsplit=2)
    return market_type, agreement_bucket, side_bucket


def _candidate_profit(candidates: list[ModelConsensusCandidate]) -> Decimal:
    return _quantize(sum((candidate.profit for candidate in candidates), Decimal("0")))


def _ratio(numerator: Decimal, denominator: int) -> Decimal | None:
    if denominator <= 0:
        return None
    return _quantize(numerator / Decimal(denominator))


def _average(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return _quantize(sum(values, Decimal("0")) / Decimal(len(values)))


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

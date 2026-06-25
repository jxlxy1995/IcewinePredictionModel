from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy.orm import Session

from icewine_prediction.historical_training_sample_service import (
    HistoricalMarketTrainingSample,
    list_historical_market_training_samples,
)


PROBABILITY_QUANT = Decimal("0.0001")
MARKET_ORDER = ("asian_handicap", "total_goals", "match_winner")


@dataclass(frozen=True)
class BookmakerOverlapMarketRow:
    market_type: str
    baseline_sample_count: int
    candidate_sample_count: int
    overlap_sample_count: int
    avg_abs_line_diff: Decimal
    avg_abs_side_a_devig_probability_diff: Decimal
    avg_abs_side_b_devig_probability_diff: Decimal
    avg_abs_overround_diff: Decimal
    baseline_close_accuracy: Decimal | None
    candidate_close_accuracy: Decimal | None


@dataclass(frozen=True)
class BookmakerOverlapComparisonReport:
    baseline_bookmaker: str
    candidate_bookmaker: str
    season: int | None
    baseline_sample_count: int
    candidate_sample_count: int
    overlap_sample_count: int
    coverage_ratio: Decimal
    market_rows: tuple[BookmakerOverlapMarketRow, ...]


def build_bookmaker_overlap_comparison_report(
    session: Session,
    *,
    baseline_bookmaker: str = "pinnacle",
    candidate_bookmaker: str = "sbobet",
    season: int | None = None,
    limit: int | None = None,
) -> BookmakerOverlapComparisonReport:
    baseline_samples = list_historical_market_training_samples(
        session,
        season=season,
        limit=limit,
        bookmaker=baseline_bookmaker,
    )
    candidate_samples = list_historical_market_training_samples(
        session,
        season=season,
        limit=limit,
        bookmaker=candidate_bookmaker,
    )
    baseline_by_key = _samples_by_key(baseline_samples)
    candidate_by_key = _samples_by_key(candidate_samples)
    overlap_keys = set(baseline_by_key).intersection(candidate_by_key)
    market_rows = tuple(
        _build_market_row(
            market_type=market_type,
            baseline_samples=[
                sample for key, sample in baseline_by_key.items() if key[1] == market_type
            ],
            candidate_samples=[
                sample for key, sample in candidate_by_key.items() if key[1] == market_type
            ],
            overlap_pairs=[
                (baseline_by_key[key], candidate_by_key[key])
                for key in sorted(overlap_keys)
                if key[1] == market_type
            ],
        )
        for market_type in MARKET_ORDER
        if any(key[1] == market_type for key in set(baseline_by_key) | set(candidate_by_key))
    )
    return BookmakerOverlapComparisonReport(
        baseline_bookmaker=baseline_bookmaker,
        candidate_bookmaker=candidate_bookmaker,
        season=season,
        baseline_sample_count=len(baseline_by_key),
        candidate_sample_count=len(candidate_by_key),
        overlap_sample_count=len(overlap_keys),
        coverage_ratio=_ratio(len(overlap_keys), len(baseline_by_key)),
        market_rows=market_rows,
    )


def format_bookmaker_overlap_comparison_report(
    report: BookmakerOverlapComparisonReport,
) -> str:
    season_text = str(report.season) if report.season is not None else "all"
    lines = [
        "# Bookmaker Overlap Comparison",
        "",
        f"- Baseline bookmaker: `{report.baseline_bookmaker}`",
        f"- Candidate bookmaker: `{report.candidate_bookmaker}`",
        f"- Season: `{season_text}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Baseline samples | {report.baseline_sample_count} |",
        f"| Candidate samples | {report.candidate_sample_count} |",
        f"| Overlap samples | {report.overlap_sample_count} |",
        f"| Coverage ratio vs baseline | {_format_decimal(report.coverage_ratio)} |",
        "",
        "## Market Rows",
        "",
        (
            "| Market | Overlap | Avg abs line diff | Avg abs side A devig p diff | "
            "Avg abs side B devig p diff | Avg abs overround diff | "
            "Baseline close acc | Candidate close acc |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report.market_rows:
        lines.append(
            "| "
            f"{row.market_type} | "
            f"{row.overlap_sample_count} | "
            f"{_format_decimal(row.avg_abs_line_diff)} | "
            f"{_format_decimal(row.avg_abs_side_a_devig_probability_diff)} | "
            f"{_format_decimal(row.avg_abs_side_b_devig_probability_diff)} | "
            f"{_format_decimal(row.avg_abs_overround_diff)} | "
            f"{_format_optional(row.baseline_close_accuracy)} | "
            f"{_format_optional(row.candidate_close_accuracy)} |"
        )
    return "\n".join(lines)


def write_bookmaker_overlap_comparison_report(
    report: BookmakerOverlapComparisonReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_bookmaker_overlap_comparison_report(report) + "\n",
        encoding="utf-8",
    )


def _samples_by_key(
    samples: list[HistoricalMarketTrainingSample],
) -> dict[tuple[int, str], HistoricalMarketTrainingSample]:
    return {(sample.match_id, sample.market_type): sample for sample in samples}


def _build_market_row(
    *,
    market_type: str,
    baseline_samples: list[HistoricalMarketTrainingSample],
    candidate_samples: list[HistoricalMarketTrainingSample],
    overlap_pairs: list[tuple[HistoricalMarketTrainingSample, HistoricalMarketTrainingSample]],
) -> BookmakerOverlapMarketRow:
    return BookmakerOverlapMarketRow(
        market_type=market_type,
        baseline_sample_count=len(baseline_samples),
        candidate_sample_count=len(candidate_samples),
        overlap_sample_count=len(overlap_pairs),
        avg_abs_line_diff=_avg_abs(
            [
                _close_anchor(candidate).market_line - _close_anchor(baseline).market_line
                for baseline, candidate in overlap_pairs
            ]
        ),
        avg_abs_side_a_devig_probability_diff=_avg_abs(
            [
                _side_a_devig_probability(_close_anchor(candidate))
                - _side_a_devig_probability(_close_anchor(baseline))
                for baseline, candidate in overlap_pairs
            ]
        ),
        avg_abs_side_b_devig_probability_diff=_avg_abs(
            [
                _side_b_devig_probability(_close_anchor(candidate))
                - _side_b_devig_probability(_close_anchor(baseline))
                for baseline, candidate in overlap_pairs
            ]
        ),
        avg_abs_overround_diff=_avg_abs(
            [
                _close_anchor(candidate).overround - _close_anchor(baseline).overround
                for baseline, candidate in overlap_pairs
            ]
        ),
        baseline_close_accuracy=_close_accuracy(
            [_close_anchor(sample) for sample in baseline_samples]
        ),
        candidate_close_accuracy=_close_accuracy(
            [_close_anchor(sample) for sample in candidate_samples]
        ),
    )


def _close_anchor(sample: HistoricalMarketTrainingSample):
    return sample.anchors[-1]


def _side_a_devig_probability(anchor) -> Decimal:
    return _round_probability(anchor.side_a_implied_probability / anchor.overround)


def _side_b_devig_probability(anchor) -> Decimal:
    return _round_probability(anchor.side_b_implied_probability / anchor.overround)


def _close_accuracy(anchors) -> Decimal | None:
    clear = [
        anchor
        for anchor in anchors
        if anchor.side_a_result in {"win", "loss"}
        and anchor.side_b_result in {"win", "loss"}
    ]
    if not clear:
        return None
    correct = 0
    for anchor in clear:
        predicted_side = (
            "side_a"
            if anchor.side_a_implied_probability >= anchor.side_b_implied_probability
            else "side_b"
        )
        if predicted_side == "side_a" and anchor.side_a_result == "win":
            correct += 1
        if predicted_side == "side_b" and anchor.side_b_result == "win":
            correct += 1
    return _ratio(correct, len(clear))


def _avg_abs(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0.0000")
    return _round_probability(sum(abs(value) for value in values) / Decimal(len(values)))


def _ratio(numerator: int, denominator: int) -> Decimal:
    if denominator == 0:
        return Decimal("0.0000")
    return _round_probability(Decimal(numerator) / Decimal(denominator))


def _round_probability(value: Decimal) -> Decimal:
    return value.quantize(PROBABILITY_QUANT, rounding=ROUND_HALF_UP)


def _format_decimal(value: Decimal) -> str:
    return str(value.quantize(PROBABILITY_QUANT, rounding=ROUND_HALF_UP))


def _format_optional(value: Decimal | None) -> str:
    if value is None:
        return ""
    return _format_decimal(value)

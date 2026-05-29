from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from math import log
from pathlib import Path


METRIC_QUANT = Decimal("0.0001")
MARKET_SPECS = {
    "asian_handicap": {
        "odds": ("asian_handicap_home_odds", "asian_handicap_away_odds"),
        "probabilities": (
            "asian_handicap_home_implied_probability",
            "asian_handicap_away_implied_probability",
        ),
        "results": ("asian_handicap_home_result", "asian_handicap_away_result"),
        "overround": "asian_handicap_overround",
        "sides": ("home", "away"),
    },
    "total_goals": {
        "odds": ("total_goals_over_odds", "total_goals_under_odds"),
        "probabilities": (
            "total_goals_over_implied_probability",
            "total_goals_under_implied_probability",
        ),
        "results": ("total_goals_over_result", "total_goals_under_result"),
        "overround": "total_goals_overround",
        "sides": ("over", "under"),
    },
    "match_winner": {
        "odds": ("match_winner_home_odds", "match_winner_draw_odds", "match_winner_away_odds"),
        "probabilities": (
            "match_winner_home_implied_probability",
            "match_winner_draw_implied_probability",
            "match_winner_away_implied_probability",
        ),
        "results": (
            "match_winner_home_result",
            "match_winner_draw_result",
            "match_winner_away_result",
        ),
        "overround": "match_winner_overround",
        "sides": ("home", "draw", "away"),
    },
}


@dataclass(frozen=True)
class MarketBaselineReport:
    market_type: str
    feature_count: int
    evaluated_count: int
    skipped_count: int
    average_log_loss: Decimal
    average_brier_score: Decimal
    accuracy: Decimal
    average_overround: Decimal
    flat_bet_count: int
    flat_bet_profit_units: Decimal
    flat_bet_roi: Decimal
    predicted_side_counts: dict[str, int]


@dataclass(frozen=True)
class BaselineTrainingDatasetMarketBaselineReport:
    csv_path: Path
    row_count: int
    total_market_samples: int
    total_evaluated_market_samples: int
    total_skipped_market_samples: int
    market_reports: dict[str, MarketBaselineReport]


@dataclass(frozen=True)
class _EvaluatedMarketSample:
    log_loss: Decimal
    brier_score: Decimal
    is_correct: bool
    overround: Decimal
    predicted_side: str
    flat_profit_units: Decimal


def build_baseline_training_dataset_market_baseline_report(
    csv_path: Path,
) -> BaselineTrainingDatasetMarketBaselineReport:
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    market_reports = {
        market_type: _build_market_report(market_type, rows)
        for market_type in MARKET_SPECS
    }
    total_evaluated = sum(report.evaluated_count for report in market_reports.values())
    total_samples = len(rows) * len(MARKET_SPECS)
    return BaselineTrainingDatasetMarketBaselineReport(
        csv_path=csv_path,
        row_count=len(rows),
        total_market_samples=total_samples,
        total_evaluated_market_samples=total_evaluated,
        total_skipped_market_samples=total_samples - total_evaluated,
        market_reports=market_reports,
    )


def format_baseline_training_dataset_market_baseline_report(
    report: BaselineTrainingDatasetMarketBaselineReport,
) -> str:
    lines = [
        "# Close-Market Baseline Evaluation",
        "",
        f"- CSV: `{report.csv_path}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Rows | {report.row_count} |",
        f"| Market samples | {report.total_market_samples} |",
        f"| Evaluated market samples | {report.total_evaluated_market_samples} |",
        f"| Skipped market samples | {report.total_skipped_market_samples} |",
        "",
        "## Market Metrics",
        "",
        (
            "| Market | Evaluated | Skipped | Accuracy | Log loss | Brier | "
            "Overround | Flat bet profit | Flat bet ROI |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for market_type, market_report in report.market_reports.items():
        lines.append(
            f"| {market_type} | {market_report.evaluated_count} | "
            f"{market_report.skipped_count} | {market_report.accuracy} | "
            f"{market_report.average_log_loss} | {market_report.average_brier_score} | "
            f"{market_report.average_overround} | {market_report.flat_bet_profit_units} | "
            f"{market_report.flat_bet_roi} |"
        )
    lines.extend(["", "## Predicted Side Distribution", ""])
    for market_type, market_report in report.market_reports.items():
        lines.extend(
            [
                f"### {market_type}",
                "",
                "| Side | Count |",
                "| --- | ---: |",
            ]
        )
        lines.extend(
            f"| {side} | {count} |"
            for side, count in market_report.predicted_side_counts.items()
        )
        lines.append("")
    return "\n".join(lines)


def write_baseline_training_dataset_market_baseline_report(
    report: BaselineTrainingDatasetMarketBaselineReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_baseline_training_dataset_market_baseline_report(report),
        encoding="utf-8",
    )


def _build_market_report(
    market_type: str,
    rows: list[dict[str, str]],
) -> MarketBaselineReport:
    evaluated_samples = [
        sample
        for row in rows
        if (sample := _evaluate_row_market(row, market_type)) is not None
    ]
    evaluated_count = len(evaluated_samples)
    predicted_side_counts: dict[str, int] = {}
    for sample in evaluated_samples:
        predicted_side_counts[sample.predicted_side] = (
            predicted_side_counts.get(sample.predicted_side, 0) + 1
        )
    profit = _average_sum([sample.flat_profit_units for sample in evaluated_samples])
    return MarketBaselineReport(
        market_type=market_type,
        feature_count=len(rows),
        evaluated_count=evaluated_count,
        skipped_count=len(rows) - evaluated_count,
        average_log_loss=_average([sample.log_loss for sample in evaluated_samples]),
        average_brier_score=_average([sample.brier_score for sample in evaluated_samples]),
        accuracy=_average(
            [Decimal("1") if sample.is_correct else Decimal("0") for sample in evaluated_samples]
        ),
        average_overround=_average([sample.overround for sample in evaluated_samples]),
        flat_bet_count=evaluated_count,
        flat_bet_profit_units=profit,
        flat_bet_roi=_ratio(profit, evaluated_count),
        predicted_side_counts=predicted_side_counts,
    )


def _evaluate_row_market(
    row: dict[str, str],
    market_type: str,
) -> _EvaluatedMarketSample | None:
    spec = MARKET_SPECS[market_type]
    probabilities = _values(row, spec["probabilities"])
    odds = _values(row, spec["odds"])
    overround = _decimal_or_none(row.get(spec["overround"]))
    results = tuple(row.get(column, "") for column in spec["results"])
    sides = spec["sides"]
    if (
        len(probabilities) != len(results)
        or len(odds) != len(results)
        or overround is None
        or any(probability <= 0 for probability in probabilities)
        or any(odd <= Decimal("1") for odd in odds)
    ):
        return None
    normalized = _normalize(probabilities)
    if not normalized:
        return None
    predicted_index = max(range(len(normalized)), key=lambda index: normalized[index])
    predicted_side = sides[predicted_index]
    if len(normalized) == 2:
        return _evaluate_binary_market(
            normalized=normalized,
            results=results,
            odds=odds,
            overround=overround,
            predicted_index=predicted_index,
            predicted_side=predicted_side,
        )
    return _evaluate_multiclass_market(
        normalized=normalized,
        results=results,
        odds=odds,
        overround=overround,
        predicted_index=predicted_index,
        predicted_side=predicted_side,
    )


def _evaluate_binary_market(
    *,
    normalized: tuple[Decimal, ...],
    results: tuple[str, ...],
    odds: tuple[Decimal, ...],
    overround: Decimal,
    predicted_index: int,
    predicted_side: str,
) -> _EvaluatedMarketSample | None:
    side_a_target = _side_a_settlement_target(results)
    if side_a_target is None:
        return None
    actual_index = 0 if side_a_target > Decimal("0.5") else 1
    return _EvaluatedMarketSample(
        log_loss=_binary_soft_log_loss(normalized[0], side_a_target),
        brier_score=_binary_soft_brier_score(normalized[0], side_a_target),
        is_correct=predicted_index == actual_index,
        overround=overround,
        predicted_side=predicted_side,
        flat_profit_units=_settlement_profit(
            results[predicted_index],
            odds[predicted_index],
        ),
    )


def _evaluate_multiclass_market(
    *,
    normalized: tuple[Decimal, ...],
    results: tuple[str, ...],
    odds: tuple[Decimal, ...],
    overround: Decimal,
    predicted_index: int,
    predicted_side: str,
) -> _EvaluatedMarketSample | None:
    actual_index = _actual_win_index(results)
    if actual_index is None:
        return None
    return _EvaluatedMarketSample(
        log_loss=_log_loss(normalized, actual_index),
        brier_score=_brier_score(normalized, actual_index),
        is_correct=predicted_index == actual_index,
        overround=overround,
        predicted_side=predicted_side,
        flat_profit_units=_settlement_profit(
            results[predicted_index],
            odds[predicted_index],
        ),
    )


def _values(row: dict[str, str], columns: tuple[str, ...]) -> tuple[Decimal, ...]:
    values = []
    for column in columns:
        value = _decimal_or_none(row.get(column))
        if value is None:
            return ()
        values.append(value)
    return tuple(values)


def _decimal_or_none(value: str | None) -> Decimal | None:
    try:
        return Decimal((value or "").strip())
    except (InvalidOperation, ValueError):
        return None


def _normalize(probabilities: tuple[Decimal, ...]) -> tuple[Decimal, ...]:
    total = sum(probabilities)
    if total <= 0:
        return ()
    return tuple(probability / total for probability in probabilities)


def _side_a_settlement_target(results: tuple[str, ...]) -> Decimal | None:
    if len(results) != 2:
        return None
    side_a_result, side_b_result = results
    expected_pairs = {
        "win": "loss",
        "half_win": "half_loss",
        "half_loss": "half_win",
        "loss": "win",
    }
    if expected_pairs.get(side_a_result) != side_b_result:
        return None
    return {
        "win": Decimal("1.00"),
        "half_win": Decimal("0.75"),
        "half_loss": Decimal("0.25"),
        "loss": Decimal("0.00"),
    }[side_a_result]


def _actual_win_index(results: tuple[str, ...]) -> int | None:
    win_indexes = [index for index, result in enumerate(results) if result == "win"]
    if len(win_indexes) != 1:
        return None
    if any(result != "loss" for index, result in enumerate(results) if index != win_indexes[0]):
        return None
    return win_indexes[0]


def _settlement_profit(result: str, odds: Decimal) -> Decimal:
    if result == "win":
        return odds - Decimal("1")
    if result == "half_win":
        return (odds - Decimal("1")) / Decimal("2")
    if result == "push":
        return Decimal("0")
    if result == "half_loss":
        return Decimal("-0.5")
    if result == "loss":
        return Decimal("-1")
    return Decimal("0")


def _log_loss(probabilities: tuple[Decimal, ...], actual_index: int) -> Decimal:
    return Decimal(str(-log(float(probabilities[actual_index]))))


def _binary_soft_log_loss(side_a_probability: Decimal, side_a_target: Decimal) -> Decimal:
    side_b_probability = Decimal("1") - side_a_probability
    return -(
        side_a_target * Decimal(str(log(float(side_a_probability))))
        + (Decimal("1") - side_a_target) * Decimal(str(log(float(side_b_probability))))
    )


def _brier_score(probabilities: tuple[Decimal, ...], actual_index: int) -> Decimal:
    total = Decimal("0")
    for index, probability in enumerate(probabilities):
        actual = Decimal("1") if index == actual_index else Decimal("0")
        total += (probability - actual) ** 2
    return total


def _binary_soft_brier_score(side_a_probability: Decimal, side_a_target: Decimal) -> Decimal:
    side_b_probability = Decimal("1") - side_a_probability
    side_b_target = Decimal("1") - side_a_target
    return (
        (side_a_probability - side_a_target) ** 2
        + (side_b_probability - side_b_target) ** 2
    )


def _average(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0.0000")
    return (sum(values) / Decimal(len(values))).quantize(METRIC_QUANT)


def _average_sum(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal("0")).quantize(METRIC_QUANT)


def _ratio(numerator: Decimal, denominator: int) -> Decimal:
    if denominator == 0:
        return Decimal("0.0000")
    return (numerator / Decimal(denominator)).quantize(METRIC_QUANT)

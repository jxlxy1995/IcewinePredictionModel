from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import log

from sqlalchemy.orm import Session

from icewine_prediction.historical_odds_feature_service import (
    HistoricalOddsMarketFeature,
    list_historical_odds_market_features,
)


METRIC_QUANT = Decimal("0.0001")
SUPPORTED_MARKET_TYPES = ("asian_handicap", "total_goals", "match_winner")


@dataclass(frozen=True)
class CloseMarketBaselineMarketReport:
    market_type: str
    feature_count: int
    evaluated_sample_count: int
    skipped_sample_count: int
    average_log_loss: Decimal
    average_brier_score: Decimal
    accuracy: Decimal
    average_overround: Decimal


@dataclass(frozen=True)
class CloseMarketBaselineReport:
    total_feature_count: int
    evaluated_sample_count: int
    skipped_sample_count: int
    market_reports: dict[str, CloseMarketBaselineMarketReport]


@dataclass(frozen=True)
class _EvaluatedSample:
    market_type: str
    log_loss: Decimal
    brier_score: Decimal
    is_correct: bool
    overround: Decimal


def build_close_market_baseline_report_from_session(
    session: Session,
    *,
    season: int | None = None,
    limit: int | None = None,
    bookmaker: str = "pinnacle",
) -> CloseMarketBaselineReport:
    features = list_historical_odds_market_features(
        session,
        season=season,
        limit=limit,
        bookmaker=bookmaker,
    )
    return build_close_market_baseline_report(features)


def build_close_market_baseline_report(
    features: list[HistoricalOddsMarketFeature],
) -> CloseMarketBaselineReport:
    feature_count_by_market = _count_features_by_market(features)
    evaluated_by_market: dict[str, list[_EvaluatedSample]] = {
        market_type: [] for market_type in feature_count_by_market
    }

    for feature in features:
        evaluated = _evaluate_feature(feature)
        if evaluated is not None:
            evaluated_by_market[feature.market_type].append(evaluated)

    market_reports = {
        market_type: _build_market_report(
            market_type,
            feature_count,
            evaluated_by_market[market_type],
        )
        for market_type, feature_count in feature_count_by_market.items()
    }
    evaluated_sample_count = sum(
        report.evaluated_sample_count for report in market_reports.values()
    )
    return CloseMarketBaselineReport(
        total_feature_count=len(features),
        evaluated_sample_count=evaluated_sample_count,
        skipped_sample_count=len(features) - evaluated_sample_count,
        market_reports=market_reports,
    )


def format_close_market_baseline_report(report: CloseMarketBaselineReport) -> str:
    lines = [
        (
            "close market baseline: "
            f"features {report.total_feature_count} "
            f"evaluated {report.evaluated_sample_count} "
            f"skipped {report.skipped_sample_count}"
        )
    ]
    for market_type, market_report in report.market_reports.items():
        lines.append(
            f"{market_type}: "
            f"evaluated {market_report.evaluated_sample_count} "
            f"skipped {market_report.skipped_sample_count} "
            f"accuracy {market_report.accuracy} "
            f"log_loss {market_report.average_log_loss} "
            f"brier {market_report.average_brier_score} "
            f"overround {market_report.average_overround}"
        )
    return "\n".join(lines)


def _count_features_by_market(
    features: list[HistoricalOddsMarketFeature],
) -> dict[str, int]:
    market_types = list(SUPPORTED_MARKET_TYPES)
    for feature in features:
        if feature.market_type not in market_types:
            market_types.append(feature.market_type)
    return {
        market_type: sum(1 for feature in features if feature.market_type == market_type)
        for market_type in market_types
    }


def _build_market_report(
    market_type: str,
    feature_count: int,
    evaluated_samples: list[_EvaluatedSample],
) -> CloseMarketBaselineMarketReport:
    evaluated_count = len(evaluated_samples)
    return CloseMarketBaselineMarketReport(
        market_type=market_type,
        feature_count=feature_count,
        evaluated_sample_count=evaluated_count,
        skipped_sample_count=feature_count - evaluated_count,
        average_log_loss=_average(
            [sample.log_loss for sample in evaluated_samples]
        ),
        average_brier_score=_average(
            [sample.brier_score for sample in evaluated_samples]
        ),
        accuracy=_average(
            [
                Decimal("1") if sample.is_correct else Decimal("0")
                for sample in evaluated_samples
            ]
        ),
        average_overround=_average(
            [sample.overround for sample in evaluated_samples]
        ),
    )


def _evaluate_feature(feature: HistoricalOddsMarketFeature) -> _EvaluatedSample | None:
    probabilities = _close_probabilities(feature)
    results = _close_results(feature, len(probabilities))
    if not probabilities or len(probabilities) != len(results):
        return None
    if any(probability <= 0 for probability in probabilities):
        return None
    actual_index = _actual_win_index(results)
    if actual_index is None:
        return None
    normalized = _normalize(probabilities)
    predicted_index = max(range(len(normalized)), key=lambda index: normalized[index])
    return _EvaluatedSample(
        market_type=feature.market_type,
        log_loss=_log_loss(normalized, actual_index),
        brier_score=_brier_score(normalized, actual_index),
        is_correct=predicted_index == actual_index,
        overround=feature.close_overround,
    )


def _close_probabilities(feature: HistoricalOddsMarketFeature) -> tuple[Decimal, ...]:
    probabilities = (
        feature.close_side_a_implied_probability,
        feature.close_side_b_implied_probability,
    )
    if feature.close_side_c_implied_probability is not None:
        probabilities = (*probabilities, feature.close_side_c_implied_probability)
    return probabilities


def _close_results(
    feature: HistoricalOddsMarketFeature,
    probability_count: int,
) -> tuple[str, ...]:
    results = (feature.close_side_a_result, feature.close_side_b_result)
    if probability_count == 3 and feature.close_side_c_result is not None:
        results = (*results, feature.close_side_c_result)
    return results


def _actual_win_index(results: tuple[str, ...]) -> int | None:
    win_indexes = [
        index for index, result in enumerate(results) if result == "win"
    ]
    if len(win_indexes) != 1:
        return None
    if any(result != "loss" for index, result in enumerate(results) if index != win_indexes[0]):
        return None
    return win_indexes[0]


def _normalize(probabilities: tuple[Decimal, ...]) -> tuple[Decimal, ...]:
    total = sum(probabilities)
    if total <= 0:
        return ()
    return tuple(probability / total for probability in probabilities)


def _log_loss(probabilities: tuple[Decimal, ...], actual_index: int) -> Decimal:
    return Decimal(str(-log(float(probabilities[actual_index]))))


def _brier_score(probabilities: tuple[Decimal, ...], actual_index: int) -> Decimal:
    total = Decimal("0")
    for index, probability in enumerate(probabilities):
        actual = Decimal("1") if index == actual_index else Decimal("0")
        total += (probability - actual) ** 2
    return total


def _average(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0.0000")
    return (sum(values) / Decimal(len(values))).quantize(METRIC_QUANT)

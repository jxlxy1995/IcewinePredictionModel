from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, log_loss
from sklearn.pipeline import Pipeline

from icewine_prediction.baseline_asian_handicap_model_service import (
    SIDE_LABELS as ASIAN_HANDICAP_SIDE_LABELS,
    _align_probabilities as _align_asian_handicap_probabilities,
    _binary_brier_score as _asian_handicap_brier_score,
    _target_label as _asian_handicap_target_label,
)
from icewine_prediction.baseline_match_winner_model_service import (
    ALL_MARKET_FEATURES,
    TEAM_FORM_FEATURES,
    _decimal_metric,
    _matrix,
)
from icewine_prediction.baseline_total_goals_model_service import (
    SIDE_LABELS as TOTAL_GOALS_SIDE_LABELS,
    _align_probabilities as _align_total_goals_probabilities,
    _binary_brier_score as _total_goals_brier_score,
    _target_label as _total_goals_target_label,
)


DEFAULT_THRESHOLDS = ("0.00", "0.02", "0.04", "0.06", "0.08", "0.10")
FEATURES = TEAM_FORM_FEATURES + ALL_MARKET_FEATURES
METRIC_QUANT = Decimal("0.0001")


@dataclass(frozen=True)
class EdgeThresholdBucket:
    threshold: Decimal
    bet_count: int
    accuracy: Decimal | None
    profit: Decimal | None
    roi: Decimal | None


@dataclass(frozen=True)
class EdgeModelBacktest:
    name: str
    estimator_name: str
    calibration_method: str
    feature_count: int
    train_rows: int
    validation_rows: int
    accuracy: Decimal
    log_loss: Decimal
    brier_score: Decimal
    threshold_buckets: list[EdgeThresholdBucket]


@dataclass(frozen=True)
class EdgeMarketBacktest:
    market_type: str
    train_rows: int
    validation_rows: int
    skipped_rows: int
    model_reports: dict[str, EdgeModelBacktest]


@dataclass(frozen=True)
class BaselineEdgeBacktestReport:
    csv_path: Path
    row_count: int
    thresholds: tuple[Decimal, ...]
    market_reports: dict[str, EdgeMarketBacktest]


@dataclass(frozen=True)
class _MarketConfig:
    market_type: str
    side_labels: tuple[str, str]
    odds_fields: tuple[str, str]
    probability_fields: tuple[str, str]
    target_label_builder: object
    probability_aligner: object
    brier_score_builder: object


MARKET_CONFIGS = (
    _MarketConfig(
        market_type="asian_handicap",
        side_labels=ASIAN_HANDICAP_SIDE_LABELS,
        odds_fields=("asian_handicap_home_odds", "asian_handicap_away_odds"),
        probability_fields=(
            "asian_handicap_home_implied_probability",
            "asian_handicap_away_implied_probability",
        ),
        target_label_builder=_asian_handicap_target_label,
        probability_aligner=_align_asian_handicap_probabilities,
        brier_score_builder=_asian_handicap_brier_score,
    ),
    _MarketConfig(
        market_type="total_goals",
        side_labels=TOTAL_GOALS_SIDE_LABELS,
        odds_fields=("total_goals_over_odds", "total_goals_under_odds"),
        probability_fields=(
            "total_goals_over_implied_probability",
            "total_goals_under_implied_probability",
        ),
        target_label_builder=_total_goals_target_label,
        probability_aligner=_align_total_goals_probabilities,
        brier_score_builder=_total_goals_brier_score,
    ),
)


def build_baseline_edge_backtest_report(
    csv_path: Path,
    *,
    thresholds: tuple[str, ...] = DEFAULT_THRESHOLDS,
) -> BaselineEdgeBacktestReport:
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    threshold_values = tuple(_as_decimal(threshold) for threshold in thresholds)
    return BaselineEdgeBacktestReport(
        csv_path=csv_path,
        row_count=len(rows),
        thresholds=threshold_values,
        market_reports={
            config.market_type: _build_market_report(config, rows, threshold_values)
            for config in MARKET_CONFIGS
        },
    )


def write_baseline_edge_backtest_report(
    report: BaselineEdgeBacktestReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_baseline_edge_backtest_report(report) + "\n", encoding="utf-8")


def format_baseline_edge_backtest_report(report: BaselineEdgeBacktestReport) -> str:
    lines = [
        "# Baseline Edge Backtest v1",
        "",
        f"- Feature CSV: `{report.csv_path}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Rows | {report.row_count} |",
        f"| Thresholds | {', '.join(str(threshold) for threshold in report.thresholds)} |",
        "",
    ]
    for market_report in report.market_reports.values():
        lines.extend(
            [
                f"## {market_report.market_type}",
                "",
                "| Metric | Value |",
                "| --- | ---: |",
                f"| Train rows | {market_report.train_rows} |",
                f"| Validation rows | {market_report.validation_rows} |",
                f"| Skipped rows | {market_report.skipped_rows} |",
                "",
            ]
        )
        for model_report in market_report.model_reports.values():
            lines.extend(
                [
                    f"### {model_report.name}",
                    "",
                    "| Metric | Value |",
                    "| --- | ---: |",
                    f"| Estimator | {model_report.estimator_name} |",
                    f"| Calibration | {model_report.calibration_method} |",
                    f"| Features | {model_report.feature_count} |",
                    f"| Accuracy | {model_report.accuracy} |",
                    f"| Log loss | {model_report.log_loss} |",
                    f"| Brier | {model_report.brier_score} |",
                    "",
                    "| Threshold | Bets | Accuracy | Profit | ROI |",
                    "| ---: | ---: | ---: | ---: | ---: |",
                ]
            )
            for bucket in model_report.threshold_buckets:
                lines.append(
                    f"| {bucket.threshold} | {bucket.bet_count} | "
                    f"{_format_optional(bucket.accuracy)} | "
                    f"{_format_optional(bucket.profit)} | "
                    f"{_format_optional(bucket.roi)} |"
                )
            lines.append("")
    return "\n".join(lines)


def _build_market_report(
    config: _MarketConfig,
    rows: list[dict[str, str]],
    thresholds: tuple[Decimal, ...],
) -> EdgeMarketBacktest:
    eligible_rows = [row for row in rows if config.target_label_builder(row) is not None]
    train_rows = [row for row in eligible_rows if row.get("split") == "train"]
    validation_rows = [row for row in eligible_rows if row.get("split") == "validation"]
    if not train_rows or not validation_rows:
        raise ValueError(f"{config.market_type} edge backtest requires both train and validation rows")
    raw_report = _fit_and_backtest(
        config,
        train_rows,
        validation_rows,
        thresholds,
        name="raw_hgb_team_form_plus_all_markets",
        calibrated=False,
    )
    calibrated_report = _fit_and_backtest(
        config,
        train_rows,
        validation_rows,
        thresholds,
        name="calibrated_hgb_team_form_plus_all_markets",
        calibrated=True,
    )
    return EdgeMarketBacktest(
        market_type=config.market_type,
        train_rows=len(train_rows),
        validation_rows=len(validation_rows),
        skipped_rows=len(rows) - len(eligible_rows),
        model_reports={
            raw_report.name: raw_report,
            calibrated_report.name: calibrated_report,
        },
    )


def _fit_and_backtest(
    config: _MarketConfig,
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    thresholds: tuple[Decimal, ...],
    *,
    name: str,
    calibrated: bool,
) -> EdgeModelBacktest:
    train_x = _matrix(train_rows, FEATURES)
    validation_x = _matrix(validation_rows, FEATURES)
    train_y = np.asarray([config.target_label_builder(row) for row in train_rows])
    validation_y = [config.target_label_builder(row) for row in validation_rows]
    model = _calibrated_model() if calibrated else _raw_model()
    model.fit(train_x, train_y)
    predicted = list(model.predict(validation_x))
    probabilities = model.predict_proba(validation_x)
    classes = list(model.classes_) if calibrated else list(model.named_steps["classifier"].classes_)
    aligned_probabilities = config.probability_aligner(probabilities, classes)
    return EdgeModelBacktest(
        name=name,
        estimator_name="HistGradientBoostingClassifier",
        calibration_method="sigmoid" if calibrated else "none",
        feature_count=len(FEATURES),
        train_rows=len(train_rows),
        validation_rows=len(validation_rows),
        accuracy=_decimal_metric(accuracy_score(validation_y, predicted)),
        log_loss=_decimal_metric(log_loss(validation_y, aligned_probabilities, labels=list(config.side_labels))),
        brier_score=_decimal_metric(config.brier_score_builder(validation_y, aligned_probabilities)),
        threshold_buckets=_build_threshold_buckets(
            config,
            validation_rows,
            validation_y,
            aligned_probabilities,
            thresholds,
        ),
    )


def _raw_model() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "classifier",
                HistGradientBoostingClassifier(
                    l2_regularization=0.05,
                    max_iter=100,
                    random_state=42,
                ),
            ),
        ]
    )


def _calibrated_model() -> CalibratedClassifierCV:
    return CalibratedClassifierCV(
        estimator=_raw_model(),
        method="sigmoid",
        cv=3,
        ensemble=True,
    )


def _build_threshold_buckets(
    config: _MarketConfig,
    validation_rows: list[dict[str, str]],
    validation_y: list[str],
    probabilities: list[list[float]],
    thresholds: tuple[Decimal, ...],
) -> list[EdgeThresholdBucket]:
    candidates = [
        candidate
        for row, actual_label, probability_row in zip(validation_rows, validation_y, probabilities, strict=True)
        if (candidate := _edge_candidate(config, row, actual_label, probability_row)) is not None
    ]
    buckets = []
    for threshold in thresholds:
        bets = [candidate for candidate in candidates if candidate["edge"] >= threshold]
        if not bets:
            buckets.append(
                EdgeThresholdBucket(
                    threshold=threshold,
                    bet_count=0,
                    accuracy=None,
                    profit=None,
                    roi=None,
                )
            )
            continue
        wins = sum(1 for bet in bets if bet["won"])
        profit = sum((bet["odds"] - Decimal("1.0")) if bet["won"] else Decimal("-1.0") for bet in bets)
        buckets.append(
            EdgeThresholdBucket(
                threshold=threshold,
                bet_count=len(bets),
                accuracy=_decimal_metric(wins / len(bets)),
                profit=_quantize_metric(profit),
                roi=_decimal_metric(profit / Decimal(len(bets))),
            )
        )
    return buckets


def _edge_candidate(
    config: _MarketConfig,
    row: dict[str, str],
    actual_label: str,
    probabilities: list[float],
) -> dict[str, object] | None:
    market_probabilities = _market_probabilities(row, config.probability_fields)
    if market_probabilities is None:
        return None
    side_index = max(
        range(len(config.side_labels)),
        key=lambda index: Decimal(str(probabilities[index])) - market_probabilities[index],
    )
    odds = _decimal_from_row(row, config.odds_fields[side_index])
    if odds is None or odds <= Decimal("1.0"):
        return None
    edge = Decimal(str(probabilities[side_index])) - market_probabilities[side_index]
    return {
        "edge": edge,
        "odds": odds,
        "won": actual_label == config.side_labels[side_index],
    }


def _market_probabilities(
    row: dict[str, str],
    probability_fields: tuple[str, str],
) -> list[Decimal] | None:
    values = [_decimal_from_row(row, field) for field in probability_fields]
    if any(value is None for value in values):
        return None
    total = sum(values, Decimal("0"))
    if total <= 0:
        return None
    return [value / total for value in values]


def _decimal_from_row(row: dict[str, str], field: str) -> Decimal | None:
    value = row.get(field, "")
    if value == "":
        return None
    return Decimal(value)


def _as_decimal(value: str) -> Decimal:
    return Decimal(value).quantize(METRIC_QUANT, rounding=ROUND_HALF_UP)


def _quantize_metric(value: Decimal) -> Decimal:
    return value.quantize(METRIC_QUANT, rounding=ROUND_HALF_UP)


def _format_optional(value: Decimal | None) -> str:
    return "-" if value is None else str(value)

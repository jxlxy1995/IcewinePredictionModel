from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sklearn.impute import SimpleImputer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from icewine_prediction.baseline_match_winner_model_service import (
    ALL_MARKET_FEATURES,
    ALL_DYNAMIC_CORE_FEATURES,
    ASIAN_HANDICAP_DYNAMIC_CORE_FEATURES,
    CalibrationBucket,
    MARKET_FEATURES,
    TEAM_FORM_FEATURES,
    _build_calibration_bins,
    _decimal_metric,
    _matrix,
)


SIDE_LABELS = ("home_cover", "away_cover")
MODEL_FEATURE_SETS = {
    "team_form_plus_match_winner_market": TEAM_FORM_FEATURES + MARKET_FEATURES,
    "team_form_plus_all_markets": TEAM_FORM_FEATURES + ALL_MARKET_FEATURES,
}


@dataclass(frozen=True)
class AsianHandicapModelEvaluation:
    name: str
    model_name: str
    feature_count: int
    train_rows: int
    validation_rows: int
    accuracy: Decimal
    log_loss: Decimal
    brier_score: Decimal
    predicted_side_counts: dict[str, int]
    calibration_bins: list[CalibrationBucket]


@dataclass(frozen=True)
class CloseMarketAsianHandicapReference:
    evaluated_rows: int
    accuracy: Decimal
    log_loss: Decimal
    brier_score: Decimal
    predicted_side_counts: dict[str, int]
    calibration_bins: list[CalibrationBucket]


@dataclass(frozen=True)
class BaselineAsianHandicapModelReport:
    csv_path: Path
    row_count: int
    train_rows: int
    validation_rows: int
    skipped_rows: int
    close_market_reference: CloseMarketAsianHandicapReference
    model_reports: dict[str, AsianHandicapModelEvaluation]


def build_baseline_asian_handicap_model_report(
    csv_path: Path,
) -> BaselineAsianHandicapModelReport:
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    eligible_rows = [row for row in rows if _target_label(row) is not None]
    train_rows = [row for row in eligible_rows if row.get("split") == "train"]
    validation_rows = [row for row in eligible_rows if row.get("split") == "validation"]
    if not train_rows or not validation_rows:
        raise ValueError("asian handicap model requires both train and validation rows")
    has_dynamic_features = _has_dynamic_features(rows)
    model_feature_sets = _model_feature_sets(rows)
    model_reports = {
        name: _fit_and_evaluate(
            name,
            features,
            train_rows,
            validation_rows,
            estimator_name="LogisticRegression",
        )
        for name, features in model_feature_sets.items()
    }
    if has_dynamic_features:
        model_reports.update(
            {
                f"hgb_{name}": _fit_and_evaluate(
                    f"hgb_{name}",
                    features,
                    train_rows,
                    validation_rows,
                    estimator_name="HistGradientBoostingClassifier",
                )
                for name, features in model_feature_sets.items()
            }
        )
    return BaselineAsianHandicapModelReport(
        csv_path=csv_path,
        row_count=len(rows),
        train_rows=len(train_rows),
        validation_rows=len(validation_rows),
        skipped_rows=len(rows) - len(eligible_rows),
        close_market_reference=_evaluate_close_market_reference(validation_rows),
        model_reports=model_reports,
    )


def _model_feature_sets(rows: list[dict[str, str]]) -> dict[str, tuple[str, ...]]:
    feature_sets = dict(MODEL_FEATURE_SETS)
    available_features = set(rows[0]) if rows else set()
    if _has_features(available_features, ASIAN_HANDICAP_DYNAMIC_CORE_FEATURES):
        feature_sets["team_form_plus_all_markets_plus_asian_handicap_dynamic_core"] = (
            TEAM_FORM_FEATURES
            + ALL_MARKET_FEATURES
            + ASIAN_HANDICAP_DYNAMIC_CORE_FEATURES
        )
    if _has_features(available_features, ALL_DYNAMIC_CORE_FEATURES):
        feature_sets["team_form_plus_all_markets_plus_all_dynamic_core"] = (
            TEAM_FORM_FEATURES + ALL_MARKET_FEATURES + ALL_DYNAMIC_CORE_FEATURES
        )
    return feature_sets


def _has_features(available_features: set[str], required_features: tuple[str, ...]) -> bool:
    return all(feature in available_features for feature in required_features)


def _has_dynamic_features(rows: list[dict[str, str]]) -> bool:
    available_features = set(rows[0]) if rows else set()
    return _has_features(available_features, ASIAN_HANDICAP_DYNAMIC_CORE_FEATURES)


def format_baseline_asian_handicap_model_report(
    report: BaselineAsianHandicapModelReport,
) -> str:
    lines = [
        "# Baseline Asian Handicap Model v1",
        "",
        f"- Feature CSV: `{report.csv_path}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Rows | {report.row_count} |",
        f"| Train rows | {report.train_rows} |",
        f"| Validation rows | {report.validation_rows} |",
        f"| Skipped rows | {report.skipped_rows} |",
        "",
        "## Close-Market Reference",
        "",
        "| Model | Evaluated | Accuracy | Log loss | Brier |",
        "| --- | ---: | ---: | ---: | ---: |",
        (
            "| close_market_asian_handicap | "
            f"{report.close_market_reference.evaluated_rows} | "
            f"{report.close_market_reference.accuracy} | "
            f"{report.close_market_reference.log_loss} | "
            f"{report.close_market_reference.brier_score} |"
        ),
        "",
        "## Model Metrics",
        "",
        "| Model | Estimator | Features | Accuracy | Log loss | Brier |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for model_report in report.model_reports.values():
        lines.append(
            f"| {model_report.name} | {model_report.model_name} | "
            f"{model_report.feature_count} | {model_report.accuracy} | "
            f"{model_report.log_loss} | {model_report.brier_score} |"
        )
    lines.extend(["", "## Predicted Side Distribution", ""])
    _append_side_distribution(
        lines,
        name="close_market_asian_handicap",
        counts=report.close_market_reference.predicted_side_counts,
    )
    for model_report in report.model_reports.values():
        _append_side_distribution(lines, name=model_report.name, counts=model_report.predicted_side_counts)
    lines.extend(["## Calibration Buckets", ""])
    _append_calibration_lines(
        lines,
        name="close_market_asian_handicap",
        buckets=report.close_market_reference.calibration_bins,
    )
    for model_report in report.model_reports.values():
        _append_calibration_lines(lines, name=model_report.name, buckets=model_report.calibration_bins)
    return "\n".join(lines)


def write_baseline_asian_handicap_model_report(
    report: BaselineAsianHandicapModelReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_baseline_asian_handicap_model_report(report) + "\n", encoding="utf-8")


def _fit_and_evaluate(
    name: str,
    features: tuple[str, ...],
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    *,
    estimator_name: str,
) -> AsianHandicapModelEvaluation:
    train_x = _matrix(train_rows, features)
    validation_x = _matrix(validation_rows, features)
    train_y = [_target_label(row) for row in train_rows]
    validation_y = [_target_label(row) for row in validation_rows]
    model = _model_pipeline(estimator_name)
    model.fit(train_x, train_y)
    predicted = list(model.predict(validation_x))
    probabilities = model.predict_proba(validation_x)
    classes = list(model.named_steps["classifier"].classes_)
    aligned_probabilities = _align_probabilities(probabilities, classes)
    return AsianHandicapModelEvaluation(
        name=name,
        model_name=estimator_name,
        feature_count=len(features),
        train_rows=len(train_rows),
        validation_rows=len(validation_rows),
        accuracy=_decimal_metric(accuracy_score(validation_y, predicted)),
        log_loss=_decimal_metric(log_loss(validation_y, aligned_probabilities, labels=list(SIDE_LABELS))),
        brier_score=_decimal_metric(_binary_brier_score(validation_y, aligned_probabilities)),
        predicted_side_counts=_count_labels(predicted),
        calibration_bins=_build_calibration_bins(validation_y, predicted, aligned_probabilities),
    )


def _model_pipeline(estimator_name: str) -> Pipeline:
    if estimator_name == "LogisticRegression":
        return Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        class_weight="balanced",
                        max_iter=1000,
                        random_state=42,
                    ),
                ),
            ]
        )
    if estimator_name == "HistGradientBoostingClassifier":
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
    raise ValueError(f"unsupported estimator: {estimator_name}")


def _evaluate_close_market_reference(
    validation_rows: list[dict[str, str]],
) -> CloseMarketAsianHandicapReference:
    evaluated = [
        (row, probabilities)
        for row in validation_rows
        if (probabilities := _market_probabilities(row)) is not None
    ]
    if not evaluated:
        return CloseMarketAsianHandicapReference(
            evaluated_rows=0,
            accuracy=Decimal("0.0000"),
            log_loss=Decimal("0.0000"),
            brier_score=Decimal("0.0000"),
            predicted_side_counts={},
            calibration_bins=[],
        )
    actual = [_target_label(row) for row, _ in evaluated]
    probabilities = [probability_row for _, probability_row in evaluated]
    predicted = [_predicted_side(probability_row) for probability_row in probabilities]
    return CloseMarketAsianHandicapReference(
        evaluated_rows=len(evaluated),
        accuracy=_decimal_metric(accuracy_score(actual, predicted)),
        log_loss=_decimal_metric(log_loss(actual, probabilities, labels=list(SIDE_LABELS))),
        brier_score=_decimal_metric(_binary_brier_score(actual, probabilities)),
        predicted_side_counts=_count_labels(predicted),
        calibration_bins=_build_calibration_bins(actual, predicted, probabilities),
    )


def _target_label(row: dict[str, str]) -> str | None:
    home_result = row.get("target_asian_handicap_home_result", "")
    away_result = row.get("target_asian_handicap_away_result", "")
    if home_result == "win" and away_result == "loss":
        return "home_cover"
    if home_result == "loss" and away_result == "win":
        return "away_cover"
    return None


def _market_probabilities(row: dict[str, str]) -> list[float] | None:
    values = [
        row.get("asian_handicap_home_implied_probability", ""),
        row.get("asian_handicap_away_implied_probability", ""),
    ]
    if any(value == "" for value in values):
        return None
    probabilities = [float(value) for value in values]
    total = sum(probabilities)
    if total <= 0:
        return None
    return [probability / total for probability in probabilities]


def _align_probabilities(probabilities, classes: list[str]) -> list[list[float]]:
    class_index = {label: index for index, label in enumerate(classes)}
    return [
        [float(row[class_index[label]]) if label in class_index else 0.0 for label in SIDE_LABELS]
        for row in probabilities
    ]


def _predicted_side(probabilities: list[float]) -> str:
    return SIDE_LABELS[max(range(len(probabilities)), key=lambda index: probabilities[index])]


def _count_labels(labels: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    return counts


def _binary_brier_score(actual: list[str], probabilities: list[list[float]]) -> float:
    total = 0.0
    for actual_label, row in zip(actual, probabilities, strict=True):
        total += sum(
            (probability - (1.0 if label == actual_label else 0.0)) ** 2
            for probability, label in zip(row, SIDE_LABELS, strict=True)
        )
    return total / len(actual)


def _append_side_distribution(
    lines: list[str],
    *,
    name: str,
    counts: dict[str, int],
) -> None:
    lines.extend([f"### {name}", "", "| Side | Count |", "| --- | ---: |"])
    lines.extend(f"| {side} | {counts.get(side, 0)} |" for side in SIDE_LABELS)
    lines.append("")


def _append_calibration_lines(
    lines: list[str],
    *,
    name: str,
    buckets: list[CalibrationBucket],
) -> None:
    lines.extend(
        [
            f"### {name}",
            "",
            "| Bucket | Samples | Avg confidence | Accuracy |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    lines.extend(
        f"| {bucket.bucket} | {bucket.sample_count} | "
        f"{bucket.average_confidence} | {bucket.accuracy} |"
        for bucket in buckets
    )
    lines.append("")

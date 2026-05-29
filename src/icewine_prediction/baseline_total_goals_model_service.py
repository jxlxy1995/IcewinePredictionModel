from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from icewine_prediction.baseline_asian_handicap_model_service import _count_labels
from icewine_prediction.baseline_match_winner_model_service import (
    ALL_MARKET_FEATURES,
    CalibrationBucket,
    MARKET_FEATURES,
    TEAM_FORM_FEATURES,
    _build_calibration_bins,
    _decimal_metric,
    _matrix,
)


SIDE_LABELS = ("over", "under")
MODEL_FEATURE_SETS = {
    "team_form_plus_match_winner_market": TEAM_FORM_FEATURES + MARKET_FEATURES,
    "team_form_plus_all_markets": TEAM_FORM_FEATURES + ALL_MARKET_FEATURES,
}


@dataclass(frozen=True)
class TotalGoalsModelEvaluation:
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
class CloseMarketTotalGoalsReference:
    evaluated_rows: int
    accuracy: Decimal
    log_loss: Decimal
    brier_score: Decimal
    predicted_side_counts: dict[str, int]
    calibration_bins: list[CalibrationBucket]


@dataclass(frozen=True)
class BaselineTotalGoalsModelReport:
    csv_path: Path
    row_count: int
    train_rows: int
    validation_rows: int
    skipped_rows: int
    close_market_reference: CloseMarketTotalGoalsReference
    model_reports: dict[str, TotalGoalsModelEvaluation]


def build_baseline_total_goals_model_report(csv_path: Path) -> BaselineTotalGoalsModelReport:
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    eligible_rows = [row for row in rows if _target_label(row) is not None]
    train_rows = [row for row in eligible_rows if row.get("split") == "train"]
    validation_rows = [row for row in eligible_rows if row.get("split") == "validation"]
    if not train_rows or not validation_rows:
        raise ValueError("total goals model requires both train and validation rows")
    model_reports = {
        name: _fit_and_evaluate(name, features, train_rows, validation_rows)
        for name, features in MODEL_FEATURE_SETS.items()
    }
    return BaselineTotalGoalsModelReport(
        csv_path=csv_path,
        row_count=len(rows),
        train_rows=len(train_rows),
        validation_rows=len(validation_rows),
        skipped_rows=len(rows) - len(eligible_rows),
        close_market_reference=_evaluate_close_market_reference(validation_rows),
        model_reports=model_reports,
    )


def format_baseline_total_goals_model_report(report: BaselineTotalGoalsModelReport) -> str:
    lines = [
        "# Baseline Total Goals Model v1",
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
            "| close_market_total_goals | "
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
        name="close_market_total_goals",
        counts=report.close_market_reference.predicted_side_counts,
    )
    for model_report in report.model_reports.values():
        _append_side_distribution(lines, name=model_report.name, counts=model_report.predicted_side_counts)
    lines.extend(["## Calibration Buckets", ""])
    _append_calibration_lines(
        lines,
        name="close_market_total_goals",
        buckets=report.close_market_reference.calibration_bins,
    )
    for model_report in report.model_reports.values():
        _append_calibration_lines(lines, name=model_report.name, buckets=model_report.calibration_bins)
    return "\n".join(lines)


def write_baseline_total_goals_model_report(
    report: BaselineTotalGoalsModelReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_baseline_total_goals_model_report(report) + "\n", encoding="utf-8")


def _fit_and_evaluate(
    name: str,
    features: tuple[str, ...],
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
) -> TotalGoalsModelEvaluation:
    train_x = _matrix(train_rows, features)
    validation_x = _matrix(validation_rows, features)
    train_y = [_target_label(row) for row in train_rows]
    validation_y = [_target_label(row) for row in validation_rows]
    model = Pipeline(
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
    model.fit(train_x, train_y)
    predicted = list(model.predict(validation_x))
    probabilities = model.predict_proba(validation_x)
    classes = list(model.named_steps["classifier"].classes_)
    aligned_probabilities = _align_probabilities(probabilities, classes)
    return TotalGoalsModelEvaluation(
        name=name,
        model_name="LogisticRegression",
        feature_count=len(features),
        train_rows=len(train_rows),
        validation_rows=len(validation_rows),
        accuracy=_decimal_metric(accuracy_score(validation_y, predicted)),
        log_loss=_decimal_metric(log_loss(validation_y, aligned_probabilities, labels=list(SIDE_LABELS))),
        brier_score=_decimal_metric(_binary_brier_score(validation_y, aligned_probabilities)),
        predicted_side_counts=_count_labels(predicted),
        calibration_bins=_build_calibration_bins(validation_y, predicted, aligned_probabilities),
    )


def _evaluate_close_market_reference(
    validation_rows: list[dict[str, str]],
) -> CloseMarketTotalGoalsReference:
    evaluated = [
        (row, probabilities)
        for row in validation_rows
        if (probabilities := _market_probabilities(row)) is not None
    ]
    if not evaluated:
        return CloseMarketTotalGoalsReference(
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
    return CloseMarketTotalGoalsReference(
        evaluated_rows=len(evaluated),
        accuracy=_decimal_metric(accuracy_score(actual, predicted)),
        log_loss=_decimal_metric(log_loss(actual, probabilities, labels=list(SIDE_LABELS))),
        brier_score=_decimal_metric(_binary_brier_score(actual, probabilities)),
        predicted_side_counts=_count_labels(predicted),
        calibration_bins=_build_calibration_bins(actual, predicted, probabilities),
    )


def _target_label(row: dict[str, str]) -> str | None:
    over_result = row.get("target_total_goals_over_result", "")
    under_result = row.get("target_total_goals_under_result", "")
    if over_result == "win" and under_result == "loss":
        return "over"
    if over_result == "loss" and under_result == "win":
        return "under"
    return None


def _market_probabilities(row: dict[str, str]) -> list[float] | None:
    values = [
        row.get("total_goals_over_implied_probability", ""),
        row.get("total_goals_under_implied_probability", ""),
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

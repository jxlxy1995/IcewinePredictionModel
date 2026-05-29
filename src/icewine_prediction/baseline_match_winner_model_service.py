from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


METRIC_QUANT = Decimal("0.0001")
RESULT_LABELS = ("home_win", "draw", "away_win")
CALIBRATION_BUCKETS = (
    (0.0, 0.3, "0.00-0.30"),
    (0.3, 0.4, "0.30-0.40"),
    (0.4, 0.5, "0.40-0.50"),
    (0.5, 0.6, "0.50-0.60"),
    (0.6, 0.7, "0.60-0.70"),
    (0.7, 0.8, "0.70-0.80"),
    (0.8, 0.9, "0.80-0.90"),
    (0.9, 1.01, "0.90-1.00"),
)
TEAM_FORM_FEATURES = (
    "home_prior_matches",
    "home_prior_points_per_match",
    "home_prior_win_rate",
    "home_prior_draw_rate",
    "home_prior_loss_rate",
    "home_prior_goals_for_per_match",
    "home_prior_goals_against_per_match",
    "home_prior_home_matches",
    "home_prior_home_points_per_match",
    "home_rest_days",
    "away_prior_matches",
    "away_prior_points_per_match",
    "away_prior_win_rate",
    "away_prior_draw_rate",
    "away_prior_loss_rate",
    "away_prior_goals_for_per_match",
    "away_prior_goals_against_per_match",
    "away_prior_away_matches",
    "away_prior_away_points_per_match",
    "away_rest_days",
)
MARKET_FEATURES = (
    "match_winner_home_implied_probability",
    "match_winner_draw_implied_probability",
    "match_winner_away_implied_probability",
    "match_winner_overround",
)
ALL_MARKET_FEATURES = MARKET_FEATURES + (
    "asian_handicap_close_line",
    "asian_handicap_home_implied_probability",
    "asian_handicap_away_implied_probability",
    "asian_handicap_overround",
    "total_goals_close_line",
    "total_goals_over_implied_probability",
    "total_goals_under_implied_probability",
    "total_goals_overround",
)
MODEL_FEATURE_SETS = {
    "team_form_only": TEAM_FORM_FEATURES,
    "team_form_plus_market": TEAM_FORM_FEATURES + MARKET_FEATURES,
    "team_form_plus_all_markets": TEAM_FORM_FEATURES + ALL_MARKET_FEATURES,
}


@dataclass(frozen=True)
class CalibrationBucket:
    bucket: str
    sample_count: int
    average_confidence: Decimal
    accuracy: Decimal


@dataclass(frozen=True)
class MatchWinnerModelEvaluation:
    name: str
    model_name: str
    feature_count: int
    train_rows: int
    validation_rows: int
    accuracy: Decimal
    log_loss: Decimal
    brier_score: Decimal
    predicted_result_counts: dict[str, int]
    calibration_bins: list[CalibrationBucket]


@dataclass(frozen=True)
class CloseMarketMatchWinnerReference:
    evaluated_rows: int
    accuracy: Decimal
    log_loss: Decimal
    brier_score: Decimal
    predicted_result_counts: dict[str, int]
    calibration_bins: list[CalibrationBucket]


@dataclass(frozen=True)
class BaselineMatchWinnerModelReport:
    csv_path: Path
    row_count: int
    train_rows: int
    validation_rows: int
    close_market_reference: CloseMarketMatchWinnerReference
    model_reports: dict[str, MatchWinnerModelEvaluation]


def build_baseline_match_winner_model_report(csv_path: Path) -> BaselineMatchWinnerModelReport:
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    train_rows = [row for row in rows if row.get("split") == "train"]
    validation_rows = [row for row in rows if row.get("split") == "validation"]
    if not train_rows or not validation_rows:
        raise ValueError("match winner model requires both train and validation rows")

    model_reports = {
        name: _fit_and_evaluate(name, features, train_rows, validation_rows)
        for name, features in MODEL_FEATURE_SETS.items()
    }
    return BaselineMatchWinnerModelReport(
        csv_path=csv_path,
        row_count=len(rows),
        train_rows=len(train_rows),
        validation_rows=len(validation_rows),
        close_market_reference=_evaluate_close_market_reference(validation_rows),
        model_reports=model_reports,
    )


def format_baseline_match_winner_model_report(
    report: BaselineMatchWinnerModelReport,
) -> str:
    lines = [
        "# Baseline Match Winner Model v1",
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
        "",
        "## Close-Market Reference",
        "",
        "| Model | Evaluated | Accuracy | Log loss | Brier |",
        "| --- | ---: | ---: | ---: | ---: |",
        (
            "| close_market_match_winner | "
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
    lines.extend(["", "## Predicted Result Distribution", ""])
    lines.extend(
        [
            "### close_market_match_winner",
            "",
            "| Result | Count |",
            "| --- | ---: |",
        ]
    )
    lines.extend(
        f"| {result} | {report.close_market_reference.predicted_result_counts.get(result, 0)} |"
        for result in RESULT_LABELS
    )
    lines.append("")
    for model_report in report.model_reports.values():
        lines.extend(
            [
                f"### {model_report.name}",
                "",
                "| Result | Count |",
                "| --- | ---: |",
            ]
        )
        lines.extend(
            f"| {result} | {model_report.predicted_result_counts.get(result, 0)} |"
            for result in RESULT_LABELS
        )
        lines.append("")
    lines.extend(["## Calibration Buckets", ""])
    _append_calibration_lines(
        lines,
        name="close_market_match_winner",
        buckets=report.close_market_reference.calibration_bins,
    )
    for model_report in report.model_reports.values():
        _append_calibration_lines(lines, name=model_report.name, buckets=model_report.calibration_bins)
    return "\n".join(lines)


def write_baseline_match_winner_model_report(
    report: BaselineMatchWinnerModelReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_baseline_match_winner_model_report(report) + "\n", encoding="utf-8")


def _fit_and_evaluate(
    name: str,
    features: tuple[str, ...],
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
) -> MatchWinnerModelEvaluation:
    train_x = _matrix(train_rows, features)
    validation_x = _matrix(validation_rows, features)
    train_y = [row["target_match_result"] for row in train_rows]
    validation_y = [row["target_match_result"] for row in validation_rows]
    model = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1000,
                    multi_class="auto",
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
    predicted_counts: dict[str, int] = {}
    for result in predicted:
        predicted_counts[result] = predicted_counts.get(result, 0) + 1
    return MatchWinnerModelEvaluation(
        name=name,
        model_name="LogisticRegression",
        feature_count=len(features),
        train_rows=len(train_rows),
        validation_rows=len(validation_rows),
        accuracy=_decimal_metric(accuracy_score(validation_y, predicted)),
        log_loss=_decimal_metric(log_loss(validation_y, aligned_probabilities, labels=list(RESULT_LABELS))),
        brier_score=_decimal_metric(_multiclass_brier_score(validation_y, aligned_probabilities)),
        predicted_result_counts=predicted_counts,
        calibration_bins=_build_calibration_bins(validation_y, predicted, aligned_probabilities),
    )


def _evaluate_close_market_reference(
    validation_rows: list[dict[str, str]],
) -> CloseMarketMatchWinnerReference:
    evaluated = [
        (row, probabilities)
        for row in validation_rows
        if (probabilities := _market_probabilities(row)) is not None
    ]
    if not evaluated:
        return CloseMarketMatchWinnerReference(
            evaluated_rows=0,
            accuracy=Decimal("0.0000"),
            log_loss=Decimal("0.0000"),
            brier_score=Decimal("0.0000"),
            predicted_result_counts={},
            calibration_bins=[],
        )
    actual = [row["target_match_result"] for row, _ in evaluated]
    probabilities = [probability_row for _, probability_row in evaluated]
    predicted = [_predicted_result(probability_row) for probability_row in probabilities]
    predicted_counts: dict[str, int] = {}
    for result in predicted:
        predicted_counts[result] = predicted_counts.get(result, 0) + 1
    return CloseMarketMatchWinnerReference(
        evaluated_rows=len(evaluated),
        accuracy=_decimal_metric(accuracy_score(actual, predicted)),
        log_loss=_decimal_metric(log_loss(actual, probabilities, labels=list(RESULT_LABELS))),
        brier_score=_decimal_metric(_multiclass_brier_score(actual, probabilities)),
        predicted_result_counts=predicted_counts,
        calibration_bins=_build_calibration_bins(actual, predicted, probabilities),
    )


def _market_probabilities(row: dict[str, str]) -> list[float] | None:
    values = [
        row.get("match_winner_home_implied_probability", ""),
        row.get("match_winner_draw_implied_probability", ""),
        row.get("match_winner_away_implied_probability", ""),
    ]
    if any(value == "" for value in values):
        return None
    probabilities = [float(value) for value in values]
    total = sum(probabilities)
    if total <= 0:
        return None
    return [probability / total for probability in probabilities]


def _predicted_result(probabilities: list[float]) -> str:
    return RESULT_LABELS[max(range(len(probabilities)), key=lambda index: probabilities[index])]


def _build_calibration_bins(
    actual: list[str],
    predicted: list[str],
    probabilities: list[list[float]],
) -> list[CalibrationBucket]:
    rows_by_bucket: dict[str, list[tuple[float, bool]]] = {}
    for actual_label, predicted_label, probability_row in zip(
        actual,
        predicted,
        probabilities,
        strict=True,
    ):
        confidence = max(probability_row)
        bucket = _bucket_for_confidence(confidence)
        rows_by_bucket.setdefault(bucket, []).append((confidence, predicted_label == actual_label))
    buckets: list[CalibrationBucket] = []
    for _, _, bucket in CALIBRATION_BUCKETS:
        rows = rows_by_bucket.get(bucket, [])
        if not rows:
            continue
        sample_count = len(rows)
        buckets.append(
            CalibrationBucket(
                bucket=bucket,
                sample_count=sample_count,
                average_confidence=_decimal_metric(
                    sum(confidence for confidence, _ in rows) / sample_count
                ),
                accuracy=_decimal_metric(
                    sum(1 for _, is_correct in rows if is_correct) / sample_count
                ),
            )
        )
    return buckets


def _bucket_for_confidence(confidence: float) -> str:
    for lower, upper, label in CALIBRATION_BUCKETS:
        if lower <= confidence < upper:
            return label
    return "0.90-1.00"


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


def _matrix(rows: list[dict[str, str]], features: tuple[str, ...]) -> list[list[float]]:
    return [[_float_or_nan(row.get(feature, "")) for feature in features] for row in rows]


def _align_probabilities(probabilities, classes: list[str]) -> list[list[float]]:
    class_index = {label: index for index, label in enumerate(classes)}
    return [
        [
            float(row[class_index[label]]) if label in class_index else 0.0
            for label in RESULT_LABELS
        ]
        for row in probabilities
    ]


def _multiclass_brier_score(actual: list[str], probabilities: list[list[float]]) -> float:
    total = 0.0
    for actual_label, row in zip(actual, probabilities, strict=True):
        total += sum(
            (probability - (1.0 if label == actual_label else 0.0)) ** 2
            for probability, label in zip(row, RESULT_LABELS, strict=True)
        )
    return total / len(actual)


def _float_or_nan(value: str) -> float:
    if value == "":
        return float("nan")
    return float(value)


def _decimal_metric(value: float) -> Decimal:
    return Decimal(str(value)).quantize(METRIC_QUANT, rounding=ROUND_HALF_UP)

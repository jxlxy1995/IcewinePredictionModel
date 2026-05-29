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
MODEL_FEATURE_SETS = {
    "team_form_only": TEAM_FORM_FEATURES,
    "team_form_plus_market": TEAM_FORM_FEATURES + MARKET_FEATURES,
}
DEFAULT_CLOSE_MARKET_MATCH_WINNER_BASELINE = {
    "accuracy": Decimal("0.5032"),
    "log_loss": Decimal("1.0055"),
    "brier_score": Decimal("0.6015"),
}


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


@dataclass(frozen=True)
class BaselineMatchWinnerModelReport:
    csv_path: Path
    row_count: int
    train_rows: int
    validation_rows: int
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
        "| Model | Accuracy | Log loss | Brier |",
        "| --- | ---: | ---: | ---: |",
        (
            "| close_market_match_winner | "
            f"{DEFAULT_CLOSE_MARKET_MATCH_WINNER_BASELINE['accuracy']} | "
            f"{DEFAULT_CLOSE_MARKET_MATCH_WINNER_BASELINE['log_loss']} | "
            f"{DEFAULT_CLOSE_MARKET_MATCH_WINNER_BASELINE['brier_score']} |"
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
    )


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

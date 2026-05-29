from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


CONFIDENCE_BUCKETS = (
    (0.50, 0.60, "0.50-0.60"),
    (0.60, 0.70, "0.60-0.70"),
    (0.70, 0.80, "0.70-0.80"),
    (0.80, 1.01, "0.80-1.00"),
)
DEFAULT_MIN_SEGMENT_ROWS = 10


@dataclass(frozen=True)
class SegmentDiagnostics:
    segment: str
    rows: int
    accuracy: str
    actual_counts: dict[str, int]
    predicted_counts: dict[str, int]


@dataclass(frozen=True)
class MarketDiagnostics:
    market_name: str
    eligible_rows: int
    skipped_rows: int
    overall: SegmentDiagnostics
    actual_side_counts: dict[str, int]
    predicted_side_counts: dict[str, int]
    by_league: list[SegmentDiagnostics]
    by_line: list[SegmentDiagnostics]
    by_market_confidence: list[SegmentDiagnostics]
    by_actual_side: list[SegmentDiagnostics]


@dataclass(frozen=True)
class BaselineMarketDiagnosticsReport:
    csv_path: Path
    row_count: int
    validation_rows: int
    market_reports: dict[str, MarketDiagnostics]


@dataclass(frozen=True)
class _MarketConfig:
    name: str
    labels: tuple[str, str]
    result_columns: tuple[str, str]
    probability_columns: tuple[str, str]
    line_column: str


MARKET_CONFIGS = (
    _MarketConfig(
        name="asian_handicap",
        labels=("home_cover", "away_cover"),
        result_columns=(
            "target_asian_handicap_home_result",
            "target_asian_handicap_away_result",
        ),
        probability_columns=(
            "asian_handicap_home_implied_probability",
            "asian_handicap_away_implied_probability",
        ),
        line_column="asian_handicap_close_line",
    ),
    _MarketConfig(
        name="total_goals",
        labels=("over", "under"),
        result_columns=(
            "target_total_goals_over_result",
            "target_total_goals_under_result",
        ),
        probability_columns=(
            "total_goals_over_implied_probability",
            "total_goals_under_implied_probability",
        ),
        line_column="total_goals_close_line",
    ),
)


def build_baseline_market_diagnostics_report(
    csv_path: Path,
    *,
    min_segment_rows: int = DEFAULT_MIN_SEGMENT_ROWS,
) -> BaselineMarketDiagnosticsReport:
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    validation_rows = [row for row in rows if row.get("split") == "validation"]
    return BaselineMarketDiagnosticsReport(
        csv_path=csv_path,
        row_count=len(rows),
        validation_rows=len(validation_rows),
        market_reports={
            config.name: _build_market_diagnostics(
                config,
                validation_rows,
                min_segment_rows=min_segment_rows,
            )
            for config in MARKET_CONFIGS
        },
    )


def format_baseline_market_diagnostics_report(
    report: BaselineMarketDiagnosticsReport,
) -> str:
    lines = [
        "# Baseline Market Diagnostics v1",
        "",
        f"- Feature CSV: `{report.csv_path}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Rows | {report.row_count} |",
        f"| Validation rows | {report.validation_rows} |",
        "",
    ]
    _append_market_report(lines, "Asian Handicap", report.market_reports["asian_handicap"])
    _append_market_report(lines, "Total Goals", report.market_reports["total_goals"])
    return "\n".join(lines)


def write_baseline_market_diagnostics_report(
    report: BaselineMarketDiagnosticsReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_baseline_market_diagnostics_report(report) + "\n",
        encoding="utf-8",
    )


def _build_market_diagnostics(
    config: _MarketConfig,
    validation_rows: list[dict[str, str]],
    *,
    min_segment_rows: int,
) -> MarketDiagnostics:
    evaluated = [
        evaluated_row
        for row in validation_rows
        if (evaluated_row := _evaluate_row(config, row)) is not None
    ]
    return MarketDiagnostics(
        market_name=config.name,
        eligible_rows=len(evaluated),
        skipped_rows=len(validation_rows) - len(evaluated),
        overall=_segment_diagnostics("overall", evaluated),
        actual_side_counts=_count_values([row["actual"] for row in evaluated], config.labels),
        predicted_side_counts=_count_values([row["predicted"] for row in evaluated], config.labels),
        by_league=_build_segments(evaluated, "league_name", min_rows=min_segment_rows),
        by_line=_build_segments(evaluated, "line", min_rows=min_segment_rows),
        by_market_confidence=_build_segments(evaluated, "confidence_bucket", min_rows=1),
        by_actual_side=_build_segments(evaluated, "actual", min_rows=1),
    )


def _evaluate_row(
    config: _MarketConfig,
    row: dict[str, str],
) -> dict[str, str | bool] | None:
    actual = _target_label(row, config)
    probabilities = _market_probabilities(row, config)
    if actual is None or probabilities is None:
        return None
    predicted = config.labels[0] if probabilities[0] >= probabilities[1] else config.labels[1]
    confidence = max(probabilities)
    return {
        "league_name": row.get("league_name", ""),
        "line": row.get(config.line_column, ""),
        "confidence_bucket": _confidence_bucket(confidence),
        "actual": actual,
        "predicted": predicted,
        "correct": actual == predicted,
    }


def _target_label(row: dict[str, str], config: _MarketConfig) -> str | None:
    first_result = row.get(config.result_columns[0], "")
    second_result = row.get(config.result_columns[1], "")
    if first_result == "win" and second_result == "loss":
        return config.labels[0]
    if first_result == "loss" and second_result == "win":
        return config.labels[1]
    return None


def _market_probabilities(
    row: dict[str, str],
    config: _MarketConfig,
) -> tuple[float, float] | None:
    values = [row.get(column, "") for column in config.probability_columns]
    if any(value == "" for value in values):
        return None
    probabilities = (float(values[0]), float(values[1]))
    total = sum(probabilities)
    if total <= 0:
        return None
    return probabilities[0] / total, probabilities[1] / total


def _confidence_bucket(confidence: float) -> str:
    for lower, upper, label in CONFIDENCE_BUCKETS:
        if lower <= confidence < upper:
            return label
    return "0.80-1.00"


def _build_segments(
    evaluated: list[dict[str, str | bool]],
    key: str,
    *,
    min_rows: int,
) -> list[SegmentDiagnostics]:
    grouped: dict[str, list[dict[str, str | bool]]] = {}
    for row in evaluated:
        segment = str(row[key])
        grouped.setdefault(segment, []).append(row)
    segments = [
        _segment_diagnostics(segment, rows)
        for segment, rows in grouped.items()
        if len(rows) >= min_rows
    ]
    return sorted(segments, key=lambda segment: (-segment.rows, segment.segment))


def _segment_diagnostics(
    segment: str,
    rows: list[dict[str, str | bool]],
) -> SegmentDiagnostics:
    if not rows:
        return SegmentDiagnostics(
            segment=segment,
            rows=0,
            accuracy="0.0000",
            actual_counts={},
            predicted_counts={},
        )
    return SegmentDiagnostics(
        segment=segment,
        rows=len(rows),
        accuracy=_format_ratio(sum(1 for row in rows if row["correct"]) / len(rows)),
        actual_counts=_count_values([str(row["actual"]) for row in rows]),
        predicted_counts=_count_values([str(row["predicted"]) for row in rows]),
    )


def _count_values(values: list[str], labels: tuple[str, ...] = ()) -> dict[str, int]:
    counts = {label: 0 for label in labels}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return {key: value for key, value in counts.items() if value > 0}


def _format_ratio(value: float) -> str:
    return f"{value:.4f}"


def _append_market_report(
    lines: list[str],
    title: str,
    report: MarketDiagnostics,
) -> None:
    lines.extend(
        [
            f"## {title}",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
            f"| Eligible rows | {report.eligible_rows} |",
            f"| Skipped rows | {report.skipped_rows} |",
            f"| Accuracy | {report.overall.accuracy} |",
            "",
            "### Side Distribution",
            "",
            "| Side | Actual | Predicted |",
            "| --- | ---: | ---: |",
        ]
    )
    sides = sorted(set(report.actual_side_counts) | set(report.predicted_side_counts))
    lines.extend(
        f"| {side} | {report.actual_side_counts.get(side, 0)} | "
        f"{report.predicted_side_counts.get(side, 0)} |"
        for side in sides
    )
    lines.append("")
    _append_segment_table(lines, "By League", report.by_league)
    _append_segment_table(lines, "By Line", report.by_line)
    _append_segment_table(lines, "By Market Confidence", report.by_market_confidence)
    _append_segment_table(lines, "By Actual Side", report.by_actual_side)


def _append_segment_table(
    lines: list[str],
    title: str,
    segments: list[SegmentDiagnostics],
) -> None:
    lines.extend(
        [
            f"### {title}",
            "",
            "| Segment | Rows | Accuracy | Actual counts | Predicted counts |",
            "| --- | ---: | ---: | --- | --- |",
        ]
    )
    lines.extend(
        f"| {segment.segment} | {segment.rows} | {segment.accuracy} | "
        f"{_format_counts(segment.actual_counts)} | {_format_counts(segment.predicted_counts)} |"
        for segment in segments
    )
    lines.append("")


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return ""
    return ", ".join(f"{key}:{value}" for key, value in sorted(counts.items()))

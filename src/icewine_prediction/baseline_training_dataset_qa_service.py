from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


RATIO_QUANT = Decimal("0.0000")
LOW_SAMPLE_THRESHOLD = 30
REQUIRED_COLUMNS = (
    "match_id",
    "season",
    "kickoff_time",
    "league_name",
    "match_result",
    "total_goals",
    "asian_handicap_close_line",
    "asian_handicap_home_odds",
    "asian_handicap_away_odds",
    "asian_handicap_home_implied_probability",
    "asian_handicap_away_implied_probability",
    "asian_handicap_overround",
    "asian_handicap_home_result",
    "asian_handicap_away_result",
    "total_goals_close_line",
    "total_goals_over_odds",
    "total_goals_under_odds",
    "total_goals_over_implied_probability",
    "total_goals_under_implied_probability",
    "total_goals_overround",
    "total_goals_over_result",
    "total_goals_under_result",
    "match_winner_home_odds",
    "match_winner_draw_odds",
    "match_winner_away_odds",
    "match_winner_home_implied_probability",
    "match_winner_draw_implied_probability",
    "match_winner_away_implied_probability",
    "match_winner_overround",
    "match_winner_home_result",
    "match_winner_draw_result",
    "match_winner_away_result",
    "asian_handicap_snapshot_count",
    "total_goals_snapshot_count",
    "match_winner_snapshot_count",
)
ODDS_COLUMNS = (
    "asian_handicap_home_odds",
    "asian_handicap_away_odds",
    "total_goals_over_odds",
    "total_goals_under_odds",
    "match_winner_home_odds",
    "match_winner_draw_odds",
    "match_winner_away_odds",
)
PROBABILITY_COLUMNS = (
    "asian_handicap_home_implied_probability",
    "asian_handicap_away_implied_probability",
    "total_goals_over_implied_probability",
    "total_goals_under_implied_probability",
    "match_winner_home_implied_probability",
    "match_winner_draw_implied_probability",
    "match_winner_away_implied_probability",
)
OVERROUND_COLUMNS_BY_MARKET = {
    "asian_handicap": "asian_handicap_overround",
    "total_goals": "total_goals_overround",
    "match_winner": "match_winner_overround",
}
LINE_COLUMNS = (
    "asian_handicap_close_line",
    "total_goals_close_line",
)
RESULT_COLUMNS = (
    "asian_handicap_home_result",
    "asian_handicap_away_result",
    "total_goals_over_result",
    "total_goals_under_result",
    "match_winner_home_result",
    "match_winner_draw_result",
    "match_winner_away_result",
)
SNAPSHOT_COUNT_COLUMNS = (
    "asian_handicap_snapshot_count",
    "total_goals_snapshot_count",
    "match_winner_snapshot_count",
)


@dataclass(frozen=True)
class BaselineTrainingDatasetQaReport:
    csv_path: Path
    row_count: int
    column_count: int
    empty_required_cells: dict[str, int]
    invalid_odds_cells: dict[str, int]
    invalid_probability_cells: dict[str, int]
    invalid_overround_cells: dict[str, int]
    overround_ranges: dict[str, tuple[str, str]]
    by_season: dict[str, int]
    by_month: dict[str, int]
    league_counts: dict[str, int]
    low_sample_leagues: dict[str, int]
    match_result_counts: dict[str, int]
    result_label_counts: dict[str, dict[str, int]]
    asian_handicap_line_counts: dict[str, int]
    total_goals_line_counts: dict[str, int]
    thin_history_count: int
    thin_history_ratio: str
    snapshot_count_ranges: dict[str, tuple[int, int]]


def build_baseline_training_dataset_qa_report(
    csv_path: Path,
    *,
    low_sample_threshold: int = LOW_SAMPLE_THRESHOLD,
) -> BaselineTrainingDatasetQaReport:
    with csv_path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    empty_required_cells = Counter()
    invalid_odds_cells = Counter()
    invalid_probability_cells = Counter()
    invalid_overround_cells = Counter()
    by_season = Counter()
    by_month = Counter()
    league_counts = Counter()
    match_result_counts = Counter()
    result_label_counts: dict[str, Counter] = {column: Counter() for column in RESULT_COLUMNS}
    line_counts: dict[str, Counter] = {column: Counter() for column in LINE_COLUMNS}
    overround_values: dict[str, list[Decimal]] = {
        market_type: [] for market_type in OVERROUND_COLUMNS_BY_MARKET
    }
    snapshot_values: dict[str, list[int]] = {column: [] for column in SNAPSHOT_COUNT_COLUMNS}
    thin_history_count = 0

    for row in rows:
        for column in REQUIRED_COLUMNS:
            if not (row.get(column) or "").strip():
                empty_required_cells[column] += 1

        for column in ODDS_COLUMNS:
            value = _decimal_or_none(row.get(column))
            if value is None or value <= Decimal("1"):
                invalid_odds_cells[column] += 1

        for column in PROBABILITY_COLUMNS:
            value = _decimal_or_none(row.get(column))
            if value is None or value <= Decimal("0") or value >= Decimal("1"):
                invalid_probability_cells[column] += 1

        for market_type, column in OVERROUND_COLUMNS_BY_MARKET.items():
            value = _decimal_or_none(row.get(column))
            if value is None or value < Decimal("1") or value > Decimal("1.30"):
                invalid_overround_cells[column] += 1
            else:
                overround_values[market_type].append(value)

        season = row.get("season", "")
        if season:
            by_season[season] += 1
        kickoff_time = row.get("kickoff_time", "")
        if len(kickoff_time) >= 7:
            by_month[kickoff_time[:7]] += 1
        league_name = row.get("league_name", "")
        if league_name:
            league_counts[league_name] += 1
        match_result = row.get("match_result", "")
        if match_result:
            match_result_counts[match_result] += 1
        for column in RESULT_COLUMNS:
            value = row.get(column, "")
            if value:
                result_label_counts[column][value] += 1
        for column in LINE_COLUMNS:
            value = row.get(column, "")
            if value:
                line_counts[column][value] += 1
        for column in SNAPSHOT_COUNT_COLUMNS:
            value = _int_or_none(row.get(column))
            if value is not None:
                snapshot_values[column].append(value)
        if "thin_history" in set((row.get("quality_tags") or "").split("|")):
            thin_history_count += 1

    low_sample_leagues = {
        league: count
        for league, count in sorted(league_counts.items(), key=lambda item: (item[1], item[0]))
        if count < low_sample_threshold
    }
    return BaselineTrainingDatasetQaReport(
        csv_path=csv_path,
        row_count=len(rows),
        column_count=len(fieldnames),
        empty_required_cells=dict(empty_required_cells),
        invalid_odds_cells=dict(invalid_odds_cells),
        invalid_probability_cells=dict(invalid_probability_cells),
        invalid_overround_cells=dict(invalid_overround_cells),
        overround_ranges={
            market_type: _decimal_range(values)
            for market_type, values in overround_values.items()
        },
        by_season=dict(by_season),
        by_month=dict(sorted(by_month.items())),
        league_counts=dict(league_counts),
        low_sample_leagues=low_sample_leagues,
        match_result_counts=dict(match_result_counts),
        result_label_counts={
            column: dict(counter) for column, counter in result_label_counts.items()
        },
        asian_handicap_line_counts=dict(line_counts["asian_handicap_close_line"]),
        total_goals_line_counts=dict(line_counts["total_goals_close_line"]),
        thin_history_count=thin_history_count,
        thin_history_ratio=_ratio(thin_history_count, len(rows)),
        snapshot_count_ranges={
            column: (min(values), max(values)) if values else (0, 0)
            for column, values in snapshot_values.items()
        },
    )


def format_baseline_training_dataset_qa_report(
    report: BaselineTrainingDatasetQaReport,
) -> str:
    lines = [
        "# Baseline Training Dataset QA",
        "",
        f"- CSV: `{report.csv_path}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Rows | {report.row_count} |",
        f"| Columns | {report.column_count} |",
        f"| Empty required cells | {sum(report.empty_required_cells.values())} |",
        f"| Invalid odds cells | {sum(report.invalid_odds_cells.values())} |",
        f"| Invalid probability cells | {sum(report.invalid_probability_cells.values())} |",
        f"| Invalid overround cells | {sum(report.invalid_overround_cells.values())} |",
        f"| Thin-history rows | {report.thin_history_count} ({report.thin_history_ratio}) |",
        "",
        "## Overround Ranges",
        "",
        "| Market | Min | Max |",
        "| --- | ---: | ---: |",
    ]
    lines.extend(
        f"| {market_type} | {minimum} | {maximum} |"
        for market_type, (minimum, maximum) in report.overround_ranges.items()
    )
    lines.extend(
        [
            "",
            "## Result Labels",
            "",
            "| Label | Count |",
            "| --- | ---: |",
        ]
    )
    lines.extend(_format_counter_rows(report.match_result_counts))
    for column, counter in report.result_label_counts.items():
        lines.extend(
            [
                "",
                f"### {column}",
                "",
                "| Label | Count |",
                "| --- | ---: |",
            ]
        )
        lines.extend(_format_counter_rows(counter))
    lines.extend(
        [
            "",
            "## By Season",
            "",
            "| Season | Rows |",
            "| --- | ---: |",
        ]
    )
    lines.extend(_format_counter_rows(report.by_season))
    lines.extend(
        [
            "",
            "## By Month",
            "",
            "| Month | Rows |",
            "| --- | ---: |",
        ]
    )
    lines.extend(_format_counter_rows(report.by_month))
    lines.extend(
        [
            "",
            "## Low Sample Leagues",
            "",
            "| League | Rows |",
            "| --- | ---: |",
        ]
    )
    lines.extend(_format_counter_rows(report.low_sample_leagues) or ["| - | 0 |"])
    lines.extend(
        [
            "",
            "## Top Asian Handicap Lines",
            "",
            "| Line | Rows |",
            "| --- | ---: |",
        ]
    )
    lines.extend(_format_counter_rows(_top_counter(report.asian_handicap_line_counts, limit=20)))
    lines.extend(
        [
            "",
            "## Top Total Goals Lines",
            "",
            "| Line | Rows |",
            "| --- | ---: |",
        ]
    )
    lines.extend(_format_counter_rows(_top_counter(report.total_goals_line_counts, limit=20)))
    lines.extend(
        [
            "",
            "## Snapshot Count Ranges",
            "",
            "| Field | Min | Max |",
            "| --- | ---: | ---: |",
        ]
    )
    lines.extend(
        f"| {field} | {minimum} | {maximum} |"
        for field, (minimum, maximum) in report.snapshot_count_ranges.items()
    )
    lines.extend(
        [
            "",
            "## Validation Details",
            "",
            f"- Empty required cells: {_format_issue_counter(report.empty_required_cells)}",
            f"- Invalid odds cells: {_format_issue_counter(report.invalid_odds_cells)}",
            f"- Invalid probability cells: {_format_issue_counter(report.invalid_probability_cells)}",
            f"- Invalid overround cells: {_format_issue_counter(report.invalid_overround_cells)}",
            "",
        ]
    )
    return "\n".join(lines)


def write_baseline_training_dataset_qa_report(
    report: BaselineTrainingDatasetQaReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_baseline_training_dataset_qa_report(report),
        encoding="utf-8",
    )


def _decimal_or_none(value: str | None) -> Decimal | None:
    try:
        return Decimal((value or "").strip())
    except (InvalidOperation, ValueError):
        return None


def _int_or_none(value: str | None) -> int | None:
    try:
        return int((value or "").strip())
    except ValueError:
        return None


def _decimal_range(values: list[Decimal]) -> tuple[str, str]:
    if not values:
        return "0.0000", "0.0000"
    return _format_decimal(min(values)), _format_decimal(max(values))


def _format_decimal(value: Decimal) -> str:
    return str(value.quantize(RATIO_QUANT, rounding=ROUND_HALF_UP))


def _ratio(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return str(RATIO_QUANT)
    return str((Decimal(numerator) / Decimal(denominator)).quantize(RATIO_QUANT))


def _top_counter(counter: dict[str, int], *, limit: int) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit])


def _format_counter_rows(counter: dict[str, int]) -> list[str]:
    return [f"| {key} | {value} |" for key, value in counter.items()]


def _format_issue_counter(counter: dict[str, int]) -> str:
    if not counter:
        return "-"
    return ", ".join(f"{key}:{value}" for key, value in sorted(counter.items()))

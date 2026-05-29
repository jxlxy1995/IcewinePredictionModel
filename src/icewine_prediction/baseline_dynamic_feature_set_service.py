from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy.orm import Session

from icewine_prediction.historical_training_sample_service import (
    HistoricalMarketTrainingSample,
    HistoricalOddsAnchorFeature,
    list_historical_market_training_samples,
)


ANCHOR_LABELS = ("24h", "12h", "6h", "3h", "1h", "close")
CORE_ANCHOR_LABELS = ("6h", "3h", "1h", "close")
ANCHOR_FIELD_LABELS = {"close": "close_anchor"}
MARKET_PREFIXES = {
    "asian_handicap": ("home", "away"),
    "total_goals": ("over", "under"),
}
LINE_QUANT = Decimal("0.01")
PROBABILITY_QUANT = Decimal("0.0001")


@dataclass(frozen=True)
class BaselineDynamicFeatureSetReport:
    source_csv_path: Path
    row_count: int
    rows_with_asian_handicap_dynamic: int
    rows_with_total_goals_dynamic: int
    complete_core_anchor_rows: int


@dataclass(frozen=True)
class BaselineDynamicFeatureSet:
    rows: list[dict[str, str]]
    fieldnames: tuple[str, ...]
    report: BaselineDynamicFeatureSetReport


def build_baseline_dynamic_feature_set(
    session: Session,
    source_csv_path: Path,
    *,
    bookmaker: str = "pinnacle",
) -> BaselineDynamicFeatureSet:
    with source_csv_path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        source_rows = list(reader)
        source_fieldnames = tuple(reader.fieldnames or ())
    samples = list_historical_market_training_samples(session, bookmaker=bookmaker)
    samples_by_match_market = {
        (str(sample.match_id), sample.market_type): sample
        for sample in samples
        if sample.market_type in MARKET_PREFIXES
    }
    rows: list[dict[str, str]] = []
    rows_with_asian = 0
    rows_with_total = 0
    complete_core_rows = 0
    for source_row in source_rows:
        match_id = source_row["match_id"]
        dynamic_values: dict[str, str] = {}
        complete_markets = []
        for market_type in MARKET_PREFIXES:
            sample = samples_by_match_market.get((match_id, market_type))
            market_values = _market_dynamic_values(market_type, sample)
            dynamic_values.update(market_values)
            has_dynamic = sample is not None
            if market_type == "asian_handicap" and has_dynamic:
                rows_with_asian += 1
            if market_type == "total_goals" and has_dynamic:
                rows_with_total += 1
            complete_markets.append(_has_core_anchors(sample))
        if all(complete_markets):
            complete_core_rows += 1
        rows.append({**source_row, **dynamic_values})
    return BaselineDynamicFeatureSet(
        rows=rows,
        fieldnames=source_fieldnames + DYNAMIC_FIELDNAMES,
        report=BaselineDynamicFeatureSetReport(
            source_csv_path=source_csv_path,
            row_count=len(rows),
            rows_with_asian_handicap_dynamic=rows_with_asian,
            rows_with_total_goals_dynamic=rows_with_total,
            complete_core_anchor_rows=complete_core_rows,
        ),
    )


def write_baseline_dynamic_feature_set_csv(
    feature_set: BaselineDynamicFeatureSet,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=feature_set.fieldnames)
        writer.writeheader()
        writer.writerows(feature_set.rows)


def format_baseline_dynamic_feature_set_report(
    report: BaselineDynamicFeatureSetReport,
) -> str:
    lines = [
        "# Baseline Dynamic Feature Set v1",
        "",
        f"- Source CSV: `{report.source_csv_path}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Rows | {report.row_count} |",
        (
            "| Rows with Asian handicap dynamic | "
            f"{report.rows_with_asian_handicap_dynamic} |"
        ),
        (
            "| Rows with total goals dynamic | "
            f"{report.rows_with_total_goals_dynamic} |"
        ),
        f"| Complete core-anchor rows | {report.complete_core_anchor_rows} |",
    ]
    return "\n".join(lines)


def write_baseline_dynamic_feature_set_report(
    report: BaselineDynamicFeatureSetReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_baseline_dynamic_feature_set_report(report) + "\n",
        encoding="utf-8",
    )


def _dynamic_fieldnames() -> tuple[str, ...]:
    fields = []
    for market_type, sides in MARKET_PREFIXES.items():
        for label in ANCHOR_LABELS:
            field_label = _field_label(label)
            fields.extend(
                [
                    f"{market_type}_{field_label}_line",
                    f"{market_type}_{field_label}_{sides[0]}_odds",
                    f"{market_type}_{field_label}_{sides[1]}_odds",
                    f"{market_type}_{field_label}_{sides[0]}_implied_probability",
                    f"{market_type}_{field_label}_{sides[1]}_implied_probability",
                    f"{market_type}_{field_label}_overround",
                    f"{market_type}_{field_label}_to_close_line_movement",
                    f"{market_type}_{field_label}_to_close_{sides[0]}_probability_movement",
                    f"{market_type}_{field_label}_to_close_{sides[1]}_probability_movement",
                ]
            )
        fields.extend(
            [
                f"{market_type}_snapshot_count",
                f"{market_type}_missing_anchor_labels",
            ]
        )
    return tuple(fields)


def _field_label(anchor_label: str) -> str:
    return ANCHOR_FIELD_LABELS.get(anchor_label, anchor_label)


DYNAMIC_FIELDNAMES = _dynamic_fieldnames()
MARKET_FIELDNAMES = {
    market_type: tuple(
        field for field in DYNAMIC_FIELDNAMES if field.startswith(f"{market_type}_")
    )
    for market_type in MARKET_PREFIXES
}


def _market_dynamic_values(
    market_type: str,
    sample: HistoricalMarketTrainingSample | None,
) -> dict[str, str]:
    values = {field: "" for field in _market_fieldnames(market_type)}
    if sample is None:
        return values
    anchors_by_label = {anchor.label: anchor for anchor in sample.anchors}
    close_anchor = anchors_by_label.get("close")
    for label in ANCHOR_LABELS:
        anchor = anchors_by_label.get(label)
        if anchor is None:
            continue
        values.update(_anchor_values(market_type, label, anchor, close_anchor))
    values[f"{market_type}_snapshot_count"] = str(sample.snapshot_count)
    values[f"{market_type}_missing_anchor_labels"] = ",".join(sample.missing_anchor_labels)
    return values


def _market_fieldnames(market_type: str) -> tuple[str, ...]:
    return MARKET_FIELDNAMES[market_type]


def _anchor_values(
    market_type: str,
    label: str,
    anchor: HistoricalOddsAnchorFeature,
    close_anchor: HistoricalOddsAnchorFeature | None,
) -> dict[str, str]:
    sides = MARKET_PREFIXES[market_type]
    field_label = _field_label(label)
    values = {
        f"{market_type}_{field_label}_line": _format_line(anchor.market_line),
        f"{market_type}_{field_label}_{sides[0]}_odds": _format_decimal(anchor.side_a_odds),
        f"{market_type}_{field_label}_{sides[1]}_odds": _format_decimal(anchor.side_b_odds),
        f"{market_type}_{field_label}_{sides[0]}_implied_probability": _format_probability(
            anchor.side_a_implied_probability
        ),
        f"{market_type}_{field_label}_{sides[1]}_implied_probability": _format_probability(
            anchor.side_b_implied_probability
        ),
        f"{market_type}_{field_label}_overround": _format_probability(anchor.overround),
        f"{market_type}_{field_label}_to_close_line_movement": "",
        f"{market_type}_{field_label}_to_close_{sides[0]}_probability_movement": "",
        f"{market_type}_{field_label}_to_close_{sides[1]}_probability_movement": "",
    }
    if close_anchor is not None:
        values[f"{market_type}_{field_label}_to_close_line_movement"] = _format_line(
            close_anchor.market_line - anchor.market_line
        )
        values[f"{market_type}_{field_label}_to_close_{sides[0]}_probability_movement"] = _format_probability(
            close_anchor.side_a_implied_probability - anchor.side_a_implied_probability
        )
        values[f"{market_type}_{field_label}_to_close_{sides[1]}_probability_movement"] = _format_probability(
            close_anchor.side_b_implied_probability - anchor.side_b_implied_probability
        )
    return values


def _has_core_anchors(sample: HistoricalMarketTrainingSample | None) -> bool:
    if sample is None:
        return False
    labels = {anchor.label for anchor in sample.anchors}
    return all(label in labels for label in CORE_ANCHOR_LABELS)


def _format_decimal(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def _format_line(value: Decimal) -> str:
    return str(value.quantize(LINE_QUANT, rounding=ROUND_HALF_UP))


def _format_probability(value: Decimal) -> str:
    return str(value.quantize(PROBABILITY_QUANT, rounding=ROUND_HALF_UP))

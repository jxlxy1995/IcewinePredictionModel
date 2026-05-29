from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from icewine_prediction.baseline_asian_handicap_model_service import (
    SIDE_LABELS,
    _align_probabilities,
    _target_label,
)
from icewine_prediction.baseline_edge_backtest_service import (
    FEATURES,
    _decimal_from_row,
    _market_probabilities,
    _raw_model,
)
from icewine_prediction.baseline_match_winner_model_service import _matrix


METRIC_QUANT = Decimal("0.0001")
ASIAN_HANDICAP_PROBABILITY_FIELDS = (
    "asian_handicap_home_implied_probability",
    "asian_handicap_away_implied_probability",
)
ASIAN_HANDICAP_ODDS_FIELDS = ("asian_handicap_home_odds", "asian_handicap_away_odds")


@dataclass(frozen=True)
class SandboxCandidate:
    match_id: str
    kickoff_time: str
    league_name: str
    home_team_name: str
    away_team_name: str
    market_type: str
    line: Decimal | None
    side: str
    odds: Decimal
    model_probability: Decimal
    market_probability: Decimal
    edge: Decimal
    actual_side: str
    profit: Decimal


@dataclass(frozen=True)
class SandboxGroupSummary:
    name: str
    candidate_count: int
    wins: int
    profit: Decimal
    roi: Decimal


@dataclass(frozen=True)
class BaselineRecommendationSandboxReport:
    csv_path: Path
    row_count: int
    train_rows: int
    validation_rows: int
    skipped_rows: int
    market_type: str
    model_name: str
    edge_threshold: Decimal
    top_n: int
    total_candidates: int
    total_profit: Decimal
    roi: Decimal | None
    displayed_candidates: list[SandboxCandidate]
    candidates: list[SandboxCandidate]
    side_summaries: list[SandboxGroupSummary]
    league_summaries: list[SandboxGroupSummary]


def build_baseline_recommendation_sandbox_report(
    csv_path: Path,
    *,
    edge_threshold: str = "0.10",
    top_n: int = 80,
) -> BaselineRecommendationSandboxReport:
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    eligible_rows = [row for row in rows if _target_label(row) is not None]
    train_rows = [row for row in eligible_rows if row.get("split") == "train"]
    validation_rows = [row for row in eligible_rows if row.get("split") == "validation"]
    if not train_rows or not validation_rows:
        raise ValueError("recommendation sandbox requires both train and validation rows")
    threshold = _as_decimal(edge_threshold)
    candidates = [
        candidate
        for candidate in _build_candidates(train_rows, validation_rows)
        if candidate.edge >= threshold
    ]
    candidates.sort(key=lambda candidate: (-candidate.edge, candidate.kickoff_time, candidate.match_id))
    total_profit = _quantize(sum((candidate.profit for candidate in candidates), Decimal("0")))
    return BaselineRecommendationSandboxReport(
        csv_path=csv_path,
        row_count=len(rows),
        train_rows=len(train_rows),
        validation_rows=len(validation_rows),
        skipped_rows=len(rows) - len(eligible_rows),
        market_type="asian_handicap",
        model_name="raw_hgb_team_form_plus_all_markets",
        edge_threshold=threshold,
        top_n=top_n,
        total_candidates=len(candidates),
        total_profit=total_profit,
        roi=_quantize(total_profit / Decimal(len(candidates))) if candidates else None,
        displayed_candidates=candidates[:top_n],
        candidates=candidates,
        side_summaries=_group_summaries(candidates, lambda candidate: candidate.side),
        league_summaries=_group_summaries(candidates, lambda candidate: candidate.league_name),
    )


def write_baseline_recommendation_sandbox_report(
    report: BaselineRecommendationSandboxReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_baseline_recommendation_sandbox_report(report) + "\n",
        encoding="utf-8",
    )


def format_baseline_recommendation_sandbox_report(
    report: BaselineRecommendationSandboxReport,
) -> str:
    lines = [
        "# Baseline Recommendation Sandbox v1",
        "",
        f"- Feature CSV: `{report.csv_path}`",
        f"- Scope: `{report.market_type} {report.model_name}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Rows | {report.row_count} |",
        f"| Train rows | {report.train_rows} |",
        f"| Validation rows | {report.validation_rows} |",
        f"| Skipped rows | {report.skipped_rows} |",
        f"| Edge threshold | {report.edge_threshold} |",
        f"| Candidates | {report.total_candidates} |",
        f"| Profit | {report.total_profit} |",
        f"| ROI | {_format_optional(report.roi)} |",
        f"| Displayed candidates | {len(report.displayed_candidates)} |",
        "",
        "## Side Summary",
        "",
        "| Side | Bets | Wins | Profit | ROI |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    lines.extend(_summary_lines(report.side_summaries))
    lines.extend(
        [
            "",
            "## League Summary",
            "",
            "| League | Bets | Wins | Profit | ROI |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    lines.extend(_summary_lines(report.league_summaries))
    lines.extend(
        [
            "",
            "## Candidate Detail",
            "",
            "| Match | Kickoff | League | Fixture | Line | Side | Odds | Model p | Market p | Edge | Actual | Profit |",
            "| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: |",
        ]
    )
    for candidate in report.displayed_candidates:
        fixture = f"{candidate.home_team_name} vs {candidate.away_team_name}"
        lines.append(
            f"| {candidate.match_id} | {candidate.kickoff_time} | "
            f"{candidate.league_name} | {fixture} | {_format_optional(candidate.line)} | "
            f"{candidate.side} | {candidate.odds} | {candidate.model_probability} | "
            f"{candidate.market_probability} | {candidate.edge} | "
            f"{candidate.actual_side} | {candidate.profit} |"
        )
    return "\n".join(lines)


def _build_candidates(
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
) -> list[SandboxCandidate]:
    model = _raw_model()
    model.fit(_matrix(train_rows, FEATURES), [_target_label(row) for row in train_rows])
    probabilities = model.predict_proba(_matrix(validation_rows, FEATURES))
    classes = list(model.named_steps["classifier"].classes_)
    aligned_probabilities = _align_probabilities(probabilities, classes)
    candidates = []
    for row, probability_row in zip(validation_rows, aligned_probabilities, strict=True):
        actual_side = _target_label(row)
        if actual_side is None:
            continue
        market_probabilities = _market_probabilities(row, ASIAN_HANDICAP_PROBABILITY_FIELDS)
        if market_probabilities is None:
            continue
        side_index = max(
            range(len(SIDE_LABELS)),
            key=lambda index: Decimal(str(probability_row[index])) - market_probabilities[index],
        )
        odds = _decimal_from_row(row, ASIAN_HANDICAP_ODDS_FIELDS[side_index])
        if odds is None or odds <= Decimal("1.0"):
            continue
        model_probability = _quantize(Decimal(str(probability_row[side_index])))
        market_probability = _quantize(market_probabilities[side_index])
        side = SIDE_LABELS[side_index]
        edge = _quantize(model_probability - market_probability)
        candidates.append(
            SandboxCandidate(
                match_id=row.get("match_id", ""),
                kickoff_time=row.get("kickoff_time", ""),
                league_name=row.get("league_name", ""),
                home_team_name=row.get("home_team_name", ""),
                away_team_name=row.get("away_team_name", ""),
                market_type="asian_handicap",
                line=_decimal_from_row(row, "asian_handicap_close_line"),
                side=side,
                odds=odds,
                model_probability=model_probability,
                market_probability=market_probability,
                edge=edge,
                actual_side=actual_side,
                profit=_profit(side == actual_side, odds),
            )
        )
    return candidates


def _group_summaries(
    candidates: list[SandboxCandidate],
    key_builder,
) -> list[SandboxGroupSummary]:
    groups: dict[str, list[SandboxCandidate]] = {}
    for candidate in candidates:
        groups.setdefault(key_builder(candidate), []).append(candidate)
    summaries = []
    for name, group_candidates in groups.items():
        profit = _quantize(sum((candidate.profit for candidate in group_candidates), Decimal("0")))
        summaries.append(
            SandboxGroupSummary(
                name=name,
                candidate_count=len(group_candidates),
                wins=sum(1 for candidate in group_candidates if candidate.profit > 0),
                profit=profit,
                roi=_quantize(profit / Decimal(len(group_candidates))),
            )
        )
    return sorted(summaries, key=lambda summary: (-summary.candidate_count, summary.name))


def _summary_lines(summaries: list[SandboxGroupSummary]) -> list[str]:
    if not summaries:
        return ["| - | 0 | 0 | - | - |"]
    return [
        f"| {summary.name} | {summary.candidate_count} | {summary.wins} | "
        f"{summary.profit} | {summary.roi} |"
        for summary in summaries
    ]


def _profit(won: bool, odds: Decimal) -> Decimal:
    if won:
        return _quantize(odds - Decimal("1.0"))
    return Decimal("-1.0000")


def _as_decimal(value: str) -> Decimal:
    return Decimal(value).quantize(METRIC_QUANT, rounding=ROUND_HALF_UP)


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(METRIC_QUANT, rounding=ROUND_HALF_UP)


def _format_optional(value: Decimal | None) -> str:
    return "-" if value is None else str(value)

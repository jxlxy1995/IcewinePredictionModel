from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy.orm import Session

from icewine_prediction.baseline_execution_robustness_service import (
    DEFAULT_BOOKMAKER,
    DEFAULT_EXECUTION_TARGETS,
    DEFAULT_PRIMARY_TARGET,
    DEFAULT_TARGET_TOLERANCE_MINUTES,
    BaselineExecutionRobustnessReport,
    ExecutionRobustnessCandidateProfile,
    build_baseline_execution_robustness_report,
)
from icewine_prediction.baseline_recommendation_sandbox_service import _format_optional, _quantize
from icewine_prediction.oddspapi_sync_runner import ODDSPAPI_SOURCE_NAME
from icewine_prediction.paper_recommendation_queue_service import DEFAULT_FEATURE_CSV_PATH
from icewine_prediction.paper_strategy_registry import STRATEGIES, PaperStrategy


METRIC_QUANT = Decimal("0.0001")
DEFAULT_PRIMARY_TARGETS = (15, 10)
DEFAULT_MIN_SEEN_COUNTS = (2, 3, 4, 5)
DEFAULT_MIN_EDGES = (
    Decimal("0.0400"),
    Decimal("0.0600"),
    Decimal("0.0800"),
    Decimal("0.1000"),
    Decimal("0.1200"),
)


@dataclass(frozen=True)
class ExecutionRobustnessGridRule:
    min_seen_count: int
    min_edge: Decimal
    allow_bucket_changed: bool
    allow_line_changed: bool
    require_side_unchanged: bool


@dataclass(frozen=True)
class ExecutionRobustnessGridRow:
    strategy_key: str
    display_name: str
    primary_target: int
    min_seen_count: int
    min_edge: Decimal
    allow_bucket_changed: bool
    allow_line_changed: bool
    require_side_unchanged: bool
    candidate_count: int
    wins: int
    profit: Decimal
    roi: Decimal | None
    hit_rate: Decimal | None
    average_seen_count: Decimal | None
    average_min_edge: Decimal | None


@dataclass(frozen=True)
class BaselineExecutionRobustnessGridReport:
    csv_path: Path
    row_count: int
    train_rows: int
    validation_rows: int
    execution_targets: tuple[int, ...]
    primary_targets: tuple[int, ...]
    tolerance_minutes: int
    source_name: str
    bookmaker: str
    min_candidate_count: int
    grid_rows: list[ExecutionRobustnessGridRow]
    top_rows: list[ExecutionRobustnessGridRow]


def build_baseline_execution_robustness_grid_report(
    session: Session,
    csv_path: Path = DEFAULT_FEATURE_CSV_PATH,
    *,
    execution_targets: tuple[int, ...] = DEFAULT_EXECUTION_TARGETS,
    primary_targets: tuple[int, ...] = DEFAULT_PRIMARY_TARGETS,
    tolerance_minutes: int = DEFAULT_TARGET_TOLERANCE_MINUTES,
    source_name: str = ODDSPAPI_SOURCE_NAME,
    bookmaker: str = DEFAULT_BOOKMAKER,
    min_seen_counts: tuple[int, ...] = DEFAULT_MIN_SEEN_COUNTS,
    min_edges: tuple[Decimal, ...] = DEFAULT_MIN_EDGES,
    min_candidate_count: int = 10,
    top_n_per_strategy: int = 5,
) -> BaselineExecutionRobustnessGridReport:
    source_reports = [
        build_baseline_execution_robustness_report(
            session,
            csv_path,
            execution_targets=execution_targets,
            primary_target=primary_target,
            tolerance_minutes=tolerance_minutes,
            source_name=source_name,
            bookmaker=bookmaker,
        )
        for primary_target in primary_targets
    ]
    return build_baseline_execution_robustness_grid_report_from_reports(
        source_reports,
        min_seen_counts=min_seen_counts,
        min_edges=min_edges,
        min_candidate_count=min_candidate_count,
        top_n_per_strategy=top_n_per_strategy,
    )


def build_baseline_execution_robustness_grid_report_from_reports(
    source_reports: list[BaselineExecutionRobustnessReport],
    *,
    min_seen_counts: tuple[int, ...] = DEFAULT_MIN_SEEN_COUNTS,
    min_edges: tuple[Decimal, ...] = DEFAULT_MIN_EDGES,
    min_candidate_count: int = 10,
    top_n_per_strategy: int = 5,
) -> BaselineExecutionRobustnessGridReport:
    if not source_reports:
        raise ValueError("execution robustness grid requires at least one source report")
    grid_rows = []
    for report in source_reports:
        for strategy in STRATEGIES:
            profiles = report.profiles_by_strategy.get(strategy.strategy_key, [])
            for rule in _grid_rules(min_seen_counts=min_seen_counts, min_edges=min_edges):
                grid_rows.append(
                    _grid_row_for_rule(
                        strategy=strategy,
                        primary_target=report.primary_target,
                        profiles=profiles,
                        rule=rule,
                    )
                )
    return BaselineExecutionRobustnessGridReport(
        csv_path=source_reports[0].csv_path,
        row_count=source_reports[0].row_count,
        train_rows=source_reports[0].train_rows,
        validation_rows=source_reports[0].validation_rows,
        execution_targets=source_reports[0].execution_targets,
        primary_targets=tuple(report.primary_target for report in source_reports),
        tolerance_minutes=source_reports[0].tolerance_minutes,
        source_name=source_reports[0].source_name,
        bookmaker=source_reports[0].bookmaker,
        min_candidate_count=min_candidate_count,
        grid_rows=grid_rows,
        top_rows=_top_grid_rows(
            grid_rows,
            min_candidate_count=min_candidate_count,
            top_n_per_strategy=top_n_per_strategy,
        ),
    )


def write_baseline_execution_robustness_grid_report(
    report: BaselineExecutionRobustnessGridReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_baseline_execution_robustness_grid_report(report) + "\n",
        encoding="utf-8",
    )


def format_baseline_execution_robustness_grid_report(
    report: BaselineExecutionRobustnessGridReport,
) -> str:
    lines = [
        "# Baseline Execution Robustness Grid",
        "",
        f"- Feature CSV: `{report.csv_path}`",
        f"- Historical odds: `{report.source_name}` / `{report.bookmaker}`",
        f"- Targets: `{', '.join(str(target) for target in report.execution_targets)}` minutes",
        f"- Primary targets: `{', '.join(str(target) for target in report.primary_targets)}` minutes",
        f"- Target tolerance: `+/-{report.tolerance_minutes}` minutes",
        f"- Min candidates for top rows: `{report.min_candidate_count}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Rows | {report.row_count} |",
        f"| Train rows | {report.train_rows} |",
        f"| Validation rows | {report.validation_rows} |",
        f"| Grid rows | {len(report.grid_rows)} |",
        "",
        "## Top Grid Rows",
        "",
        (
            "| Strategy | Primary | Seen >= | Min edge | Bucket change | Line change | "
            "Side change | Bets | Wins | Hit rate | Profit | ROI | Avg seen | Avg min edge |"
        ),
        "| --- | ---: | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    if not report.top_rows:
        lines.append("| - | - | - | - | - | - | - | 0 | 0 | - | 0.0000 | - | - | - |")
    for row in report.top_rows:
        lines.append(_format_grid_row(row))
    return "\n".join(lines)


def _grid_row_for_rule(
    *,
    strategy: PaperStrategy,
    primary_target: int,
    profiles: list[ExecutionRobustnessCandidateProfile],
    rule: ExecutionRobustnessGridRule,
) -> ExecutionRobustnessGridRow:
    included = [profile for profile in profiles if _profile_matches_rule(profile, rule)]
    profit = _quantize(
        sum((profile.primary_candidate.profit for profile in included), Decimal("0"))
    )
    wins = sum(1 for profile in included if profile.primary_candidate.profit > 0)
    return ExecutionRobustnessGridRow(
        strategy_key=strategy.strategy_key,
        display_name=strategy.display_name,
        primary_target=primary_target,
        min_seen_count=rule.min_seen_count,
        min_edge=rule.min_edge,
        allow_bucket_changed=rule.allow_bucket_changed,
        allow_line_changed=rule.allow_line_changed,
        require_side_unchanged=rule.require_side_unchanged,
        candidate_count=len(included),
        wins=wins,
        profit=profit,
        roi=_ratio(profit, len(included)),
        hit_rate=_ratio(Decimal(wins), len(included)),
        average_seen_count=_average(
            Decimal(profile.seen_count) for profile in included
        ),
        average_min_edge=_average(profile.min_edge for profile in included),
    )


def _profile_matches_rule(
    profile: ExecutionRobustnessCandidateProfile,
    rule: ExecutionRobustnessGridRule,
) -> bool:
    if profile.seen_count < rule.min_seen_count:
        return False
    if profile.min_edge < rule.min_edge:
        return False
    if profile.bucket_changed and not rule.allow_bucket_changed:
        return False
    if profile.line_changed and not rule.allow_line_changed:
        return False
    if profile.side_changed and rule.require_side_unchanged:
        return False
    return True


def _grid_rules(
    *,
    min_seen_counts: tuple[int, ...],
    min_edges: tuple[Decimal, ...],
) -> list[ExecutionRobustnessGridRule]:
    return [
        ExecutionRobustnessGridRule(
            min_seen_count=min_seen_count,
            min_edge=min_edge,
            allow_bucket_changed=allow_bucket_changed,
            allow_line_changed=allow_line_changed,
            require_side_unchanged=require_side_unchanged,
        )
        for min_seen_count in min_seen_counts
        for min_edge in min_edges
        for allow_bucket_changed in (False, True)
        for allow_line_changed in (False, True)
        for require_side_unchanged in (True, False)
    ]


def _top_grid_rows(
    grid_rows: list[ExecutionRobustnessGridRow],
    *,
    min_candidate_count: int,
    top_n_per_strategy: int,
) -> list[ExecutionRobustnessGridRow]:
    grouped: dict[tuple[str, int], list[ExecutionRobustnessGridRow]] = {}
    for row in grid_rows:
        if row.candidate_count < min_candidate_count:
            continue
        grouped.setdefault((row.strategy_key, row.primary_target), []).append(row)
    top_rows = []
    for rows in grouped.values():
        deduped_rows = []
        seen_fingerprints = set()
        for row in sorted(
            rows,
            key=lambda row: (
                row.roi is None,
                -(row.roi or Decimal("-999")),
                -row.candidate_count,
                row.min_seen_count,
                row.min_edge,
            ),
        ):
            fingerprint = _grid_result_fingerprint(row)
            if fingerprint in seen_fingerprints:
                continue
            seen_fingerprints.add(fingerprint)
            deduped_rows.append(row)
        top_rows.extend(
            deduped_rows[:top_n_per_strategy]
        )
    return sorted(
        top_rows,
        key=lambda row: (
            row.strategy_key,
            row.primary_target,
            row.roi is None,
            -(row.roi or Decimal("-999")),
            -row.candidate_count,
        ),
    )


def _grid_result_fingerprint(row: ExecutionRobustnessGridRow) -> tuple:
    return (
        row.strategy_key,
        row.primary_target,
        row.candidate_count,
        row.wins,
        row.profit,
        row.roi,
        row.hit_rate,
        row.average_seen_count,
        row.average_min_edge,
    )


def _format_grid_row(row: ExecutionRobustnessGridRow) -> str:
    return (
        f"| `{row.strategy_key}` | T-{row.primary_target} | {row.min_seen_count} | "
        f"{row.min_edge} | {_format_bool(row.allow_bucket_changed)} | "
        f"{_format_bool(row.allow_line_changed)} | "
        f"{'disallowed' if row.require_side_unchanged else 'allowed'} | "
        f"{row.candidate_count} | {row.wins} | {_format_optional(row.hit_rate)} | "
        f"{row.profit} | {_format_optional(row.roi)} | "
        f"{_format_optional(row.average_seen_count)} | "
        f"{_format_optional(row.average_min_edge)} |"
    )


def _format_bool(value: bool) -> str:
    return "allowed" if value else "disallowed"


def _ratio(numerator: Decimal, denominator: int) -> Decimal | None:
    if denominator <= 0:
        return None
    return (numerator / Decimal(denominator)).quantize(METRIC_QUANT, rounding=ROUND_HALF_UP)


def _average(values) -> Decimal | None:
    materialized = list(values)
    if not materialized:
        return None
    return (
        sum(materialized, Decimal("0")) / Decimal(len(materialized))
    ).quantize(METRIC_QUANT, rounding=ROUND_HALF_UP)

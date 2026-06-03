from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy.orm import Session

from icewine_prediction.baseline_execution_robustness_grid_service import _profile_matches_rule
from icewine_prediction.baseline_execution_robustness_service import (
    DEFAULT_BOOKMAKER,
    DEFAULT_EXECUTION_TARGETS,
    DEFAULT_TARGET_TOLERANCE_MINUTES,
    BaselineExecutionRobustnessReport,
    ExecutionRobustnessCandidateProfile,
    build_baseline_execution_robustness_report,
)
from icewine_prediction.baseline_recommendation_sandbox_service import _format_optional, _quantize
from icewine_prediction.execution_robustness_rules import (
    DEFAULT_SELECTED_ROBUSTNESS_RULES,
    SelectedExecutionRobustnessRule,
)
from icewine_prediction.oddspapi_sync_runner import ODDSPAPI_SOURCE_NAME
from icewine_prediction.paper_recommendation_queue_service import DEFAULT_FEATURE_CSV_PATH
from icewine_prediction.paper_strategy_registry import STRATEGIES, PaperStrategy


METRIC_QUANT = Decimal("0.0001")


@dataclass(frozen=True)
class ExecutionRobustnessFilterStrategySummary:
    strategy_key: str
    display_name: str
    mode: str
    primary_target: int
    min_seen_count: int
    min_edge: Decimal
    allow_bucket_changed: bool
    allow_line_changed: bool
    require_side_unchanged: bool
    raw_count: int
    raw_wins: int
    raw_profit: Decimal
    raw_roi: Decimal | None
    raw_hit_rate: Decimal | None
    kept_count: int
    kept_wins: int
    kept_profit: Decimal
    kept_roi: Decimal | None
    kept_hit_rate: Decimal | None
    filtered_count: int
    filtered_wins: int
    filtered_profit: Decimal
    filtered_roi: Decimal | None
    filtered_hit_rate: Decimal | None


@dataclass(frozen=True)
class BaselineExecutionRobustnessFilterReport:
    csv_path: Path
    row_count: int
    train_rows: int
    validation_rows: int
    execution_targets: tuple[int, ...]
    primary_targets: tuple[int, ...]
    tolerance_minutes: int
    source_name: str
    bookmaker: str
    strategy_summaries: list[ExecutionRobustnessFilterStrategySummary]


def build_baseline_execution_robustness_filter_report(
    session: Session,
    csv_path: Path = DEFAULT_FEATURE_CSV_PATH,
    *,
    execution_targets: tuple[int, ...] = DEFAULT_EXECUTION_TARGETS,
    tolerance_minutes: int = DEFAULT_TARGET_TOLERANCE_MINUTES,
    source_name: str = ODDSPAPI_SOURCE_NAME,
    bookmaker: str = DEFAULT_BOOKMAKER,
    selected_rules: dict[str, SelectedExecutionRobustnessRule] = DEFAULT_SELECTED_ROBUSTNESS_RULES,
) -> BaselineExecutionRobustnessFilterReport:
    primary_targets = tuple(
        sorted({rule.primary_target for rule in selected_rules.values()}, reverse=True)
    )
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
    return build_baseline_execution_robustness_filter_report_from_reports(
        source_reports,
        selected_rules=selected_rules,
    )


def build_baseline_execution_robustness_filter_report_from_reports(
    source_reports: list[BaselineExecutionRobustnessReport],
    *,
    selected_rules: dict[str, SelectedExecutionRobustnessRule] = DEFAULT_SELECTED_ROBUSTNESS_RULES,
) -> BaselineExecutionRobustnessFilterReport:
    if not source_reports:
        raise ValueError("execution robustness filter comparison requires at least one source report")
    reports_by_primary_target = {report.primary_target: report for report in source_reports}
    first = source_reports[0]
    return BaselineExecutionRobustnessFilterReport(
        csv_path=first.csv_path,
        row_count=first.row_count,
        train_rows=first.train_rows,
        validation_rows=first.validation_rows,
        execution_targets=first.execution_targets,
        primary_targets=tuple(report.primary_target for report in source_reports),
        tolerance_minutes=first.tolerance_minutes,
        source_name=first.source_name,
        bookmaker=first.bookmaker,
        strategy_summaries=[
            _strategy_summary(
                strategy,
                selected_rules[strategy.strategy_key],
                reports_by_primary_target=reports_by_primary_target,
            )
            for strategy in STRATEGIES
            if strategy.strategy_key in selected_rules
        ],
    )


def write_baseline_execution_robustness_filter_report(
    report: BaselineExecutionRobustnessFilterReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_baseline_execution_robustness_filter_report(report) + "\n",
        encoding="utf-8",
    )


def format_baseline_execution_robustness_filter_report(
    report: BaselineExecutionRobustnessFilterReport,
) -> str:
    lines = [
        "# Baseline Execution Robustness Filter Comparison",
        "",
        f"- Feature CSV: `{report.csv_path}`",
        f"- Historical odds: `{report.source_name}` / `{report.bookmaker}`",
        f"- Targets: `{', '.join(str(target) for target in report.execution_targets)}` minutes",
        f"- Primary targets: `{', '.join(str(target) for target in report.primary_targets)}` minutes",
        f"- Target tolerance: `+/-{report.tolerance_minutes}` minutes",
        "",
        "## Data Coverage",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Rows | {report.row_count} |",
        f"| Train rows | {report.train_rows} |",
        f"| Validation rows | {report.validation_rows} |",
        "",
        "## Raw vs Kept vs Filtered",
        "",
        (
            "| Strategy | Mode | Primary | Rule | Raw bets | Raw ROI | Raw hit | "
            "Kept bets | Kept ROI | Kept hit | Filtered bets | Filtered ROI | Filtered hit |"
        ),
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in report.strategy_summaries:
        lines.append(_format_strategy_summary(summary))
    return "\n".join(lines)


def _strategy_summary(
    strategy: PaperStrategy,
    rule: SelectedExecutionRobustnessRule,
    *,
    reports_by_primary_target: dict[int, BaselineExecutionRobustnessReport],
) -> ExecutionRobustnessFilterStrategySummary:
    source_report = reports_by_primary_target.get(rule.primary_target)
    if source_report is None:
        profiles = []
    else:
        profiles = source_report.profiles_by_strategy.get(strategy.strategy_key, [])
    if rule.mode == "observe":
        kept = profiles
        filtered = []
    elif rule.mode == "filter":
        grid_rule = rule.as_grid_rule()
        kept = [profile for profile in profiles if _profile_matches_rule(profile, grid_rule)]
        filtered = [profile for profile in profiles if not _profile_matches_rule(profile, grid_rule)]
    else:
        raise ValueError(f"unknown execution robustness rule mode: {rule.mode}")
    raw_metrics = _profile_metrics(profiles)
    kept_metrics = _profile_metrics(kept)
    filtered_metrics = _profile_metrics(filtered)
    return ExecutionRobustnessFilterStrategySummary(
        strategy_key=strategy.strategy_key,
        display_name=strategy.display_name,
        mode=rule.mode,
        primary_target=rule.primary_target,
        min_seen_count=rule.min_seen_count,
        min_edge=rule.min_edge,
        allow_bucket_changed=rule.allow_bucket_changed,
        allow_line_changed=rule.allow_line_changed,
        require_side_unchanged=rule.require_side_unchanged,
        raw_count=raw_metrics.count,
        raw_wins=raw_metrics.wins,
        raw_profit=raw_metrics.profit,
        raw_roi=raw_metrics.roi,
        raw_hit_rate=raw_metrics.hit_rate,
        kept_count=kept_metrics.count,
        kept_wins=kept_metrics.wins,
        kept_profit=kept_metrics.profit,
        kept_roi=kept_metrics.roi,
        kept_hit_rate=kept_metrics.hit_rate,
        filtered_count=filtered_metrics.count,
        filtered_wins=filtered_metrics.wins,
        filtered_profit=filtered_metrics.profit,
        filtered_roi=filtered_metrics.roi,
        filtered_hit_rate=filtered_metrics.hit_rate,
    )


@dataclass(frozen=True)
class _ProfileMetrics:
    count: int
    wins: int
    profit: Decimal
    roi: Decimal | None
    hit_rate: Decimal | None


def _profile_metrics(profiles: list[ExecutionRobustnessCandidateProfile]) -> _ProfileMetrics:
    profit = _quantize(sum((profile.primary_candidate.profit for profile in profiles), Decimal("0")))
    wins = sum(1 for profile in profiles if profile.primary_candidate.profit > 0)
    return _ProfileMetrics(
        count=len(profiles),
        wins=wins,
        profit=profit,
        roi=_ratio(profit, len(profiles)),
        hit_rate=_ratio(Decimal(wins), len(profiles)),
    )


def _format_strategy_summary(summary: ExecutionRobustnessFilterStrategySummary) -> str:
    return (
        f"| `{summary.strategy_key}` | {summary.mode} | T-{summary.primary_target} | "
        f"{_format_rule(summary)} | "
        f"{summary.raw_count} | {_format_optional(summary.raw_roi)} | "
        f"{_format_optional(summary.raw_hit_rate)} | "
        f"{summary.kept_count} | {_format_optional(summary.kept_roi)} | "
        f"{_format_optional(summary.kept_hit_rate)} | "
        f"{summary.filtered_count} | {_format_optional(summary.filtered_roi)} | "
        f"{_format_optional(summary.filtered_hit_rate)} |"
    )


def _format_rule(summary: ExecutionRobustnessFilterStrategySummary) -> str:
    side = "side=stable" if summary.require_side_unchanged else "side=any"
    bucket = "bucket=any" if summary.allow_bucket_changed else "bucket=stable"
    line = "line=any" if summary.allow_line_changed else "line=stable"
    return (
        f"seen>={summary.min_seen_count} edge>={summary.min_edge} "
        f"{side} {bucket} {line}"
    )


def _ratio(numerator: Decimal, denominator: int) -> Decimal | None:
    if denominator <= 0:
        return None
    return (numerator / Decimal(denominator)).quantize(METRIC_QUANT, rounding=ROUND_HALF_UP)

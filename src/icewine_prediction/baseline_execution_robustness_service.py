from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy.orm import Session

from icewine_prediction.baseline_recommendation_sandbox_service import (
    SandboxCandidate,
    _format_optional,
    _quantize,
)
from icewine_prediction.baseline_t15_signal_comparison_service import (
    DEFAULT_BOOKMAKER,
    _candidates_by_strategy,
    _load_matches_by_id,
    _load_snapshots_by_match_id,
    _match_id_from_row,
    _patch_row_with_t15_markets,
    _row_match_ids,
)
from icewine_prediction.oddspapi_sync_runner import ODDSPAPI_SOURCE_NAME
from icewine_prediction.paper_recommendation_queue_service import (
    DEFAULT_FEATURE_CSV_PATH,
    _home_line_bucket,
    _line_bucket,
    _total_line_bucket,
    train_paper_queue_scorer_from_rows,
)
from icewine_prediction.paper_strategy_registry import STRATEGIES, PaperStrategy


METRIC_QUANT = Decimal("0.0001")
DEFAULT_EXECUTION_TARGETS = (25, 20, 15, 10, 5)
DEFAULT_PRIMARY_TARGET = 15
DEFAULT_TARGET_TOLERANCE_MINUTES = 5
ROBUST_STRONG_MIN_EDGE = Decimal("0.0800")
ROBUST_CANDIDATE_MIN_EDGE = Decimal("0.0500")


@dataclass(frozen=True)
class ExecutionRobustnessCandidateProfile:
    strategy_key: str
    match_id: str
    market_type: str
    primary_candidate: SandboxCandidate
    level: str
    seen_count: int
    total_points: int
    min_edge: Decimal
    max_edge: Decimal
    edge_range: Decimal
    side_changed: bool
    line_changed: bool
    bucket_changed: bool
    observed_targets: tuple[int, ...]


@dataclass(frozen=True)
class ExecutionRobustnessStrategySummary:
    strategy_key: str
    display_name: str
    primary_count: int
    level_counts: dict[str, int]
    level_profit: dict[str, Decimal]
    level_roi: dict[str, Decimal | None]
    average_seen_count: Decimal | None


@dataclass(frozen=True)
class BaselineExecutionRobustnessReport:
    csv_path: Path
    row_count: int
    train_rows: int
    validation_rows: int
    execution_targets: tuple[int, ...]
    primary_target: int
    tolerance_minutes: int
    source_name: str
    bookmaker: str
    target_available_rows: dict[int, int]
    strategy_summaries: list[ExecutionRobustnessStrategySummary]
    profiles_by_strategy: dict[str, list[ExecutionRobustnessCandidateProfile]]


def build_baseline_execution_robustness_report(
    session: Session,
    csv_path: Path = DEFAULT_FEATURE_CSV_PATH,
    *,
    execution_targets: tuple[int, ...] = DEFAULT_EXECUTION_TARGETS,
    primary_target: int = DEFAULT_PRIMARY_TARGET,
    tolerance_minutes: int = DEFAULT_TARGET_TOLERANCE_MINUTES,
    source_name: str = ODDSPAPI_SOURCE_NAME,
    bookmaker: str = DEFAULT_BOOKMAKER,
) -> BaselineExecutionRobustnessReport:
    if primary_target not in execution_targets:
        raise ValueError("primary target must be included in execution targets")
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = sorted(
            list(csv.DictReader(file)),
            key=lambda row: (row.get("kickoff_time", ""), row.get("match_id", "")),
        )
    train_rows = [row for row in rows if row.get("split") == "train"]
    validation_rows = [row for row in rows if row.get("split") == "validation"]
    if not train_rows or not validation_rows:
        raise ValueError("execution robustness requires both train and validation rows")

    scorer = train_paper_queue_scorer_from_rows(train_rows)
    matches_by_id = _load_matches_by_id(session, _row_match_ids(validation_rows))
    snapshots_by_match_id = _load_snapshots_by_match_id(
        session,
        match_ids=list(matches_by_id),
        source_name=source_name,
        bookmaker=bookmaker,
    )

    candidates_by_target: dict[int, dict[str, list[SandboxCandidate]]] = {}
    target_available_rows: dict[int, int] = {}
    for target in execution_targets:
        patched_rows = []
        for row in validation_rows:
            match = matches_by_id.get(_match_id_from_row(row))
            if match is None:
                continue
            patched_row = _patch_row_with_t15_markets(
                row,
                match=match,
                snapshots=snapshots_by_match_id.get(match.id, []),
                target_minutes_before_kickoff=target,
                tolerance_minutes=tolerance_minutes,
            )
            if patched_row is not None:
                patched_rows.append(patched_row)
        target_available_rows[target] = len(patched_rows)
        candidates_by_target[target] = _candidates_by_strategy(patched_rows, scorer)

    profiles_by_strategy = {
        strategy.strategy_key: _strategy_profiles(
            strategy,
            candidates_by_target,
            execution_targets=execution_targets,
            primary_target=primary_target,
        )
        for strategy in STRATEGIES
    }
    return BaselineExecutionRobustnessReport(
        csv_path=csv_path,
        row_count=len(rows),
        train_rows=len(train_rows),
        validation_rows=len(validation_rows),
        execution_targets=execution_targets,
        primary_target=primary_target,
        tolerance_minutes=tolerance_minutes,
        source_name=source_name,
        bookmaker=bookmaker,
        target_available_rows=target_available_rows,
        strategy_summaries=[
            _strategy_robustness_summary(strategy, profiles_by_strategy[strategy.strategy_key])
            for strategy in STRATEGIES
        ],
        profiles_by_strategy=profiles_by_strategy,
    )


def write_baseline_execution_robustness_report(
    report: BaselineExecutionRobustnessReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_baseline_execution_robustness_report(report) + "\n",
        encoding="utf-8",
    )


def format_baseline_execution_robustness_report(
    report: BaselineExecutionRobustnessReport,
) -> str:
    lines = [
        "# Baseline Execution Robustness",
        "",
        f"- Feature CSV: `{report.csv_path}`",
        f"- Historical odds: `{report.source_name}` / `{report.bookmaker}`",
        f"- Targets: `{', '.join(str(target) for target in report.execution_targets)}` minutes",
        f"- Primary target: `{report.primary_target}` minutes",
        f"- Target tolerance: `+/-{report.tolerance_minutes}` minutes",
        "",
        "## Data Coverage",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Rows | {report.row_count} |",
        f"| Train rows | {report.train_rows} |",
        f"| Validation rows | {report.validation_rows} |",
    ]
    for target in report.execution_targets:
        lines.append(f"| T-{target} available rows | {report.target_available_rows.get(target, 0)} |")
    lines.extend(
        [
            "",
            "## Strategy Robustness",
            "",
            (
                "| Strategy | Primary bets | Strong | Candidate | Watch | Rejected | "
                "Strong ROI | Candidate ROI | Watch ROI | Rejected ROI | Avg seen |"
            ),
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for summary in report.strategy_summaries:
        lines.append(
            f"| `{summary.strategy_key}` | {summary.primary_count} | "
            f"{summary.level_counts['strong']} | {summary.level_counts['candidate']} | "
            f"{summary.level_counts['watch']} | {summary.level_counts['rejected']} | "
            f"{_format_optional(summary.level_roi['strong'])} | "
            f"{_format_optional(summary.level_roi['candidate'])} | "
            f"{_format_optional(summary.level_roi['watch'])} | "
            f"{_format_optional(summary.level_roi['rejected'])} | "
            f"{_format_optional(summary.average_seen_count)} |"
        )
    return "\n".join(lines)


def _strategy_profiles(
    strategy: PaperStrategy,
    candidates_by_target: dict[int, dict[str, list[SandboxCandidate]]],
    *,
    execution_targets: tuple[int, ...],
    primary_target: int,
) -> list[ExecutionRobustnessCandidateProfile]:
    primary_candidates = candidates_by_target.get(primary_target, {}).get(strategy.strategy_key, [])
    observations_by_target = {
        target: _candidate_observations(candidates_by_target.get(target, {}).get(strategy.strategy_key, []))
        for target in execution_targets
    }
    profiles = []
    for primary_candidate in primary_candidates:
        key = _candidate_observation_key(primary_candidate)
        observations = {
            target: by_key[key]
            for target, by_key in observations_by_target.items()
            if key in by_key
        }
        profiles.append(
            _build_candidate_profile(
                strategy,
                primary_candidate,
                observations_by_target=observations,
                execution_targets=execution_targets,
            )
        )
    return profiles


def _build_candidate_profile(
    strategy: PaperStrategy,
    primary_candidate: SandboxCandidate,
    *,
    observations_by_target: dict[int, SandboxCandidate],
    execution_targets: tuple[int, ...],
) -> ExecutionRobustnessCandidateProfile:
    observations = list(observations_by_target.values())
    edges = [candidate.edge for candidate in observations]
    min_edge = min(edges) if edges else primary_candidate.edge
    max_edge = max(edges) if edges else primary_candidate.edge
    primary_bucket = _candidate_bucket(primary_candidate)
    side_changed = any(candidate.side != primary_candidate.side for candidate in observations)
    line_changed = any(candidate.line != primary_candidate.line for candidate in observations)
    bucket_changed = any(_candidate_bucket(candidate) != primary_bucket for candidate in observations)
    seen_count = len(observations)
    level = _robustness_level(
        seen_count=seen_count,
        total_points=len(execution_targets),
        min_edge=min_edge,
        side_changed=side_changed,
        bucket_changed=bucket_changed,
    )
    return ExecutionRobustnessCandidateProfile(
        strategy_key=strategy.strategy_key,
        match_id=primary_candidate.match_id,
        market_type=primary_candidate.market_type,
        primary_candidate=primary_candidate,
        level=level,
        seen_count=seen_count,
        total_points=len(execution_targets),
        min_edge=_quantize(min_edge),
        max_edge=_quantize(max_edge),
        edge_range=_quantize(max_edge - min_edge),
        side_changed=side_changed,
        line_changed=line_changed,
        bucket_changed=bucket_changed,
        observed_targets=tuple(sorted(observations_by_target)),
    )


def _strategy_robustness_summary(
    strategy: PaperStrategy,
    profiles: list[ExecutionRobustnessCandidateProfile],
) -> ExecutionRobustnessStrategySummary:
    levels = ("candidate", "rejected", "strong", "watch")
    level_counts = {level: sum(1 for profile in profiles if profile.level == level) for level in levels}
    level_profit = {
        level: _quantize(
            sum(
                (
                    profile.primary_candidate.profit
                    for profile in profiles
                    if profile.level == level
                ),
                Decimal("0"),
            )
        )
        for level in levels
    }
    level_roi = {
        level: _ratio(level_profit[level], level_counts[level])
        for level in levels
    }
    average_seen_count = (
        _ratio(Decimal(sum(profile.seen_count for profile in profiles)), len(profiles))
        if profiles
        else None
    )
    return ExecutionRobustnessStrategySummary(
        strategy_key=strategy.strategy_key,
        display_name=strategy.display_name,
        primary_count=len(profiles),
        level_counts=level_counts,
        level_profit=level_profit,
        level_roi=level_roi,
        average_seen_count=average_seen_count,
    )


def _robustness_level(
    *,
    seen_count: int,
    total_points: int,
    min_edge: Decimal,
    side_changed: bool,
    bucket_changed: bool,
) -> str:
    if (
        seen_count >= min(4, total_points)
        and min_edge >= ROBUST_STRONG_MIN_EDGE
        and not side_changed
        and not bucket_changed
    ):
        return "strong"
    if seen_count >= min(3, total_points) and min_edge >= ROBUST_CANDIDATE_MIN_EDGE and not side_changed:
        return "candidate"
    if seen_count >= 2 and not side_changed:
        return "watch"
    return "rejected"


def _candidate_observations(candidates: list[SandboxCandidate]) -> dict[tuple[str, str], SandboxCandidate]:
    observations = {}
    for candidate in candidates:
        key = _candidate_observation_key(candidate)
        existing = observations.get(key)
        if existing is None or candidate.edge > existing.edge:
            observations[key] = candidate
    return observations


def _candidate_observation_key(candidate: SandboxCandidate) -> tuple[str, str]:
    return (candidate.match_id, candidate.market_type)


def _candidate_bucket(candidate: SandboxCandidate) -> str:
    if candidate.market_type == "total_goals":
        return f"{candidate.side}@{_total_line_bucket(candidate.line)}"
    if candidate.side == "home_cover":
        return _home_line_bucket(candidate.line)
    return _line_bucket(candidate.line)


def _ratio(numerator: Decimal, denominator: int) -> Decimal | None:
    if denominator <= 0:
        return None
    return (numerator / Decimal(denominator)).quantize(METRIC_QUANT, rounding=ROUND_HALF_UP)

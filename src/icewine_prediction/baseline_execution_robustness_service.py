from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
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
    _candidate_from_score,
    _clear_market_fields,
    _load_matches_by_id,
    _load_snapshots_by_match_id,
    _match_id_from_row,
    _match_snapshot_timeline_kickoff_time,
    _patch_market_fields,
    _patch_row_with_t15_markets,
    _actual_side_label,
    _market_line,
    _profit_for_side,
    _row_match_ids,
    _side_odds,
    _strategy_accepts_score,
)
from icewine_prediction.historical_training_sample_service import (
    _PairedMarketSnapshot,
    _comparable_datetime,
    _pair_market_snapshots,
)
from icewine_prediction.execution_timepoint_service import DEFAULT_EXECUTION_TIMEPOINT_TOLERANCE_MINUTES
from icewine_prediction.models import HistoricalOddsSnapshot, Match
from icewine_prediction.oddspapi_sync_runner import ODDSPAPI_SOURCE_NAME
from icewine_prediction.paper_recommendation_queue_service import (
    DEFAULT_FEATURE_CSV_PATH,
    PaperQueueScore,
    PaperQueueRow,
    _home_line_bucket,
    _line_bucket,
    _total_line_bucket,
    _strategy_observation_rows_for_scored,
    train_paper_queue_scorer_from_rows,
)
from icewine_prediction.paper_strategy_registry import DEFAULT_STRATEGY, STRATEGIES, PaperStrategy


METRIC_QUANT = Decimal("0.0001")
DEFAULT_EXECUTION_TARGETS = (60, 30, 25, 20, 15, 10)
DEFAULT_PRIMARY_TARGET = 10
DEFAULT_TARGET_TOLERANCE_MINUTES = DEFAULT_EXECUTION_TIMEPOINT_TOLERANCE_MINUTES
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
    latest_available_rows: int = 0


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

    candidates_by_target: dict[int | None, dict[str, list[SandboxCandidate]]] = {}
    observations_by_target: dict[int, dict[str, list[SandboxCandidate]]] = {}
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
        discovered, observations = _strategy_and_observation_candidates_by_strategy(patched_rows, scorer)
        candidates_by_target[target] = discovered
        observations_by_target[target] = observations
    latest_rows = []
    for row in validation_rows:
        match = matches_by_id.get(_match_id_from_row(row))
        if match is None:
            continue
        latest_row = _patch_row_with_latest_historical_markets(
            row,
            match=match,
            snapshots=snapshots_by_match_id.get(match.id, []),
        )
        if latest_row is not None:
            latest_rows.append(latest_row)
    candidates_by_target[None] = _candidates_by_strategy(latest_rows, scorer)

    profiles_by_strategy = {
        strategy.strategy_key: _strategy_profiles(
            strategy,
            candidates_by_target,
            observations_by_target,
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
        latest_available_rows=len(latest_rows),
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
    lines.append(f"| Latest available rows | {report.latest_available_rows} |")
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
    candidates_by_target: dict[int | None, dict[str, list[SandboxCandidate]]],
    observation_candidates_by_target: dict[int, dict[str, list[SandboxCandidate]]] | None = None,
    *,
    execution_targets: tuple[int, ...],
    primary_target: int,
) -> list[ExecutionRobustnessCandidateProfile]:
    observation_candidates_by_target = observation_candidates_by_target or candidates_by_target
    observations_by_target = {
        target: _candidate_observations(
            observation_candidates_by_target.get(target, {}).get(strategy.strategy_key, [])
        )
        for target in execution_targets
    }
    discovered_by_key: dict[tuple[str, str, str], SandboxCandidate] = {}
    for target in (*execution_targets, None):
        for candidate in candidates_by_target.get(target, {}).get(strategy.strategy_key, []):
            key = _candidate_observation_key(candidate)
            existing = discovered_by_key.get(key)
            if existing is None or candidate.edge > existing.edge:
                discovered_by_key[key] = candidate
    profiles = []
    for key, discovered_candidate in discovered_by_key.items():
        observations = {
            target: by_key[key]
            for target, by_key in observations_by_target.items()
            if key in by_key
        }
        profiles.append(
            _profile_from_discovery(
                strategy,
                discovered_candidate,
                observations_by_target=observations,
                primary_target=primary_target,
                execution_targets=execution_targets,
            )
        )
    return profiles


def _observation_candidates_by_strategy(
    rows: list[dict[str, str]],
    scorer,
) -> dict[str, list[SandboxCandidate]]:
    return _strategy_and_observation_candidates_by_strategy(rows, scorer)[1]


def _strategy_and_observation_candidates_by_strategy(
    rows: list[dict[str, str]],
    scorer,
) -> tuple[dict[str, list[SandboxCandidate]], dict[str, list[SandboxCandidate]]]:
    discovered: dict[str, list[SandboxCandidate]] = defaultdict(list)
    candidates: dict[str, list[SandboxCandidate]] = defaultdict(list)
    for row in rows:
        scores = _normalize_research_scores(scorer(row))
        for score in scores:
            for strategy in STRATEGIES:
                if _strategy_accepts_score(strategy, score, row):
                    candidate = _candidate_from_score(row, score)
                    if candidate is not None:
                        discovered[strategy.strategy_key].append(candidate)
        scored_rows = [
            scored_row
            for score in scores
            if (scored_row := _research_scored_row(row, score)) is not None
        ]
        for scored_row in scored_rows:
            for observation_row in _strategy_observation_rows_for_scored(scored_row):
                candidate = _candidate_from_observation_row(row, observation_row)
                if candidate is not None:
                    candidates[observation_row.strategy_key].append(candidate)
    for strategy_candidates in (*discovered.values(), *candidates.values()):
        strategy_candidates.sort(
            key=lambda candidate: (-candidate.edge, candidate.kickoff_time, candidate.match_id)
        )
    return dict(discovered), dict(candidates)


def _normalize_research_scores(result) -> list[PaperQueueScore]:
    if result is None:
        return []
    if isinstance(result, PaperQueueScore):
        return [result]
    return list(result)


def _research_scored_row(row: dict[str, str], score: PaperQueueScore) -> PaperQueueRow | None:
    odds = _side_odds(row, score.market_type, score.side)
    line = _market_line(row, score.market_type)
    if odds is None or line is None:
        return None
    line_bucket = _total_line_bucket(line) if score.market_type == "total_goals" else _line_bucket(line)
    risk_tags = (f"line_bucket:{line_bucket}",)
    if score.calibrated_side == score.side and score.calibrated_edge is not None and score.calibrated_edge >= Decimal("0"):
        risk_tags = (*risk_tags, "model_consensus:confirmed")
    return PaperQueueRow(
        match_id=_match_id_from_row(row) or 0,
        source_match_id=row.get("source_match_id") or None,
        kickoff_time=row.get("kickoff_time", ""),
        league_name=row.get("league_name", ""),
        league_display_name=row.get("league_name", ""),
        home_team_name=row.get("home_team_name", ""),
        home_team_display_name=row.get("home_team_name", ""),
        away_team_name=row.get("away_team_name", ""),
        away_team_display_name=row.get("away_team_name", ""),
        status="candidate",
        market_type=score.market_type,
        line=line,
        side=score.side,
        recommended_handicap=None,
        odds=odds,
        model_probability=score.model_probability,
        market_probability=score.market_probability,
        edge=score.edge,
        line_bucket=line_bucket,
        risk_tags=risk_tags,
        strategy_key=DEFAULT_STRATEGY.strategy_key,
        strategy_display_name=DEFAULT_STRATEGY.display_name,
        signal_version=DEFAULT_STRATEGY.signal_version,
        odds_source="oddspapi_historical",
    )


def _candidate_from_observation_row(
    source_row: dict[str, str],
    observation_row: PaperQueueRow,
) -> SandboxCandidate | None:
    if observation_row.edge is None or observation_row.odds is None:
        return None
    profit = _profit_for_side(source_row, observation_row.market_type, observation_row.side, observation_row.odds)
    if profit is None:
        return None
    return SandboxCandidate(
        match_id=str(observation_row.match_id),
        kickoff_time=observation_row.kickoff_time,
        league_name=observation_row.league_name,
        home_team_name=observation_row.home_team_name,
        away_team_name=observation_row.away_team_name,
        market_type=observation_row.market_type,
        line=observation_row.line,
        side=observation_row.side or "",
        odds=observation_row.odds,
        model_probability=observation_row.model_probability or Decimal("0"),
        market_probability=observation_row.market_probability or Decimal("0"),
        edge=observation_row.edge,
        actual_side=_actual_side_label(source_row, observation_row.market_type),
        profit=profit,
    )


def _profile_from_discovery(
    strategy: PaperStrategy,
    discovered_candidate: SandboxCandidate,
    *,
    observations_by_target: dict[int, SandboxCandidate],
    primary_target: int,
    execution_targets: tuple[int, ...],
) -> ExecutionRobustnessCandidateProfile:
    primary_candidate = _representative_candidate_for_profile(
        discovered_candidate,
        observations_by_target=observations_by_target,
        primary_target=primary_target,
    )
    return _build_candidate_profile(
        strategy,
        primary_candidate,
        observations_by_target=observations_by_target,
        execution_targets=execution_targets,
    )


def _representative_candidate_for_profile(
    discovered_candidate: SandboxCandidate,
    *,
    observations_by_target: dict[int, SandboxCandidate],
    primary_target: int,
) -> SandboxCandidate:
    primary_candidate = observations_by_target.get(primary_target)
    if primary_candidate is not None:
        return primary_candidate
    if observations_by_target:
        return max(observations_by_target.values(), key=lambda candidate: candidate.edge)
    return discovered_candidate


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


def _candidate_observations(candidates: list[SandboxCandidate]) -> dict[tuple[str, str, str], SandboxCandidate]:
    observations = {}
    for candidate in candidates:
        key = _candidate_observation_key(candidate)
        existing = observations.get(key)
        if existing is None or candidate.edge > existing.edge:
            observations[key] = candidate
    return observations


def _candidate_observation_key(candidate: SandboxCandidate) -> tuple[str, str, str]:
    return (candidate.match_id, candidate.market_type, candidate.side)


def _patch_row_with_latest_historical_markets(
    row: dict[str, str],
    *,
    match: Match,
    snapshots: list[HistoricalOddsSnapshot],
) -> dict[str, str] | None:
    patched = dict(row)
    had_strategy_market = False
    kickoff_time = _match_snapshot_timeline_kickoff_time(match)
    for market_type in ("asian_handicap", "total_goals", "match_winner"):
        pairs = _pair_market_snapshots(
            [snapshot for snapshot in snapshots if snapshot.market_type == market_type],
            market_type=market_type,
        )
        pair = _select_latest_pre_kickoff_pair(pairs, kickoff_time=kickoff_time)
        if pair is None:
            _clear_market_fields(patched, market_type)
            continue
        _patch_market_fields(patched, match=match, pair=pair)
        if market_type in {"asian_handicap", "total_goals"}:
            had_strategy_market = True
    return patched if had_strategy_market else None


def _select_latest_pre_kickoff_pair(
    pairs: list[_PairedMarketSnapshot],
    *,
    kickoff_time: datetime,
) -> _PairedMarketSnapshot | None:
    kickoff = _comparable_datetime(kickoff_time)
    candidates = [
        pair
        for pair in pairs
        if _comparable_datetime(pair.snapshot_time) <= kickoff
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda pair: (
            _comparable_datetime(pair.snapshot_time),
            -pair.balance_gap,
        ),
    )


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

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Callable, Any
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, selectinload

from icewine_prediction.baseline_edge_backtest_service import (
    FEATURES,
    _calibrated_model,
    _market_probabilities,
    _raw_model,
)
from icewine_prediction.baseline_asian_handicap_model_service import (
    SIDE_LABELS as ASIAN_HANDICAP_SIDE_LABELS,
    _align_probabilities as _align_asian_handicap_probabilities,
    _target_label as _asian_handicap_target_label,
)
from icewine_prediction.baseline_match_winner_model_service import _matrix
from icewine_prediction.baseline_total_goals_model_service import (
    SIDE_LABELS as TOTAL_GOALS_SIDE_LABELS,
    _align_probabilities as _align_total_goals_probabilities,
    _target_label as _total_goals_target_label,
)
from icewine_prediction.config import BEIJING_TIMEZONE
from icewine_prediction.display_service import DisplayNameService
from icewine_prediction.feature_service import (
    MatchOddsFeatures,
    OddsMarketAggregate,
    build_match_odds_features,
)
from icewine_prediction.historical_training_sample_service import (
    _PairedMarketSnapshot,
    _comparable_datetime,
    _pair_market_snapshots,
)
from icewine_prediction.execution_robustness_rules import (
    DEFAULT_SELECTED_ROBUSTNESS_RULES,
    SelectedExecutionRobustnessRule,
)
from icewine_prediction.models import HistoricalOddsSnapshot, Match, TrainingRun
from icewine_prediction.oddspapi_sync_runner import (
    COMPLETE_HISTORICAL_ODDS_24H_SNAPSHOT_COUNT,
    COMPLETE_HISTORICAL_ODDS_CLOSE_WINDOW,
    COMPLETE_HISTORICAL_ODDS_REQUIRED_MARKETS,
    ODDSPAPI_SOURCE_NAME,
    _as_utc,
    _historical_snapshot_as_utc,
)
from icewine_prediction.paper_strategy_registry import (
    BUCKET_V2_STRATEGY,
    DEFAULT_STRATEGY,
    HOME_FAVORITE_BUCKET_V1_STRATEGY,
    TOTAL_GOALS_BUCKET_V2_STRATEGY,
    TOTAL_GOALS_CONFIRMED_UNDER_MID_275_V1_STRATEGY,
    TOTAL_GOALS_LOW_LINE_BUCKET_V3_STRATEGY,
)


METRIC_QUANT = Decimal("0.0001")
LINE_QUANT = Decimal("0.00")
ODDS_QUANT = Decimal("0.000")
DEFAULT_FEATURE_CSV_PATH = Path(
    "local_data/training/baseline_dynamic_features_main_leagues_20260529.csv"
)
ASIAN_HANDICAP_PROBABILITY_FIELDS = (
    "asian_handicap_home_implied_probability",
    "asian_handicap_away_implied_probability",
)
ASIAN_HANDICAP_ODDS_FIELDS = ("asian_handicap_home_odds", "asian_handicap_away_odds")
TOTAL_GOALS_PROBABILITY_FIELDS = (
    "total_goals_over_implied_probability",
    "total_goals_under_implied_probability",
)
TOTAL_GOALS_ODDS_FIELDS = ("total_goals_over_odds", "total_goals_under_odds")
MAX_CANDIDATE_ODDS_LEAD_TIME = timedelta(hours=3)
MIN_CANDIDATE_ODDS_LEAD_TIME = timedelta(0)
DEFAULT_EXECUTION_ROBUSTNESS_TARGETS = (25, 20, 15, 10, 5)
DEFAULT_EXECUTION_ROBUSTNESS_TOLERANCE_MINUTES = 5
_SCORER_CACHE: dict[
    tuple[tuple[Path, int | None, int | None], int],
    Callable[[dict[str, str]], PaperQueueScoreResult],
] = {}


@dataclass(frozen=True)
class PaperQueueScore:
    side: str
    model_probability: Decimal
    market_probability: Decimal
    edge: Decimal
    model_name: str
    market_type: str = "asian_handicap"
    calibrated_side: str | None = None
    calibrated_edge: Decimal | None = None


PaperQueueScoreResult = PaperQueueScore | list[PaperQueueScore] | tuple[PaperQueueScore, ...] | None


@dataclass(frozen=True)
class PaperQueueRow:
    match_id: int
    source_match_id: str | None
    kickoff_time: str
    league_name: str
    league_display_name: str
    home_team_name: str
    home_team_display_name: str
    away_team_name: str
    away_team_display_name: str
    status: str
    market_type: str
    line: Decimal | None
    side: str | None
    recommended_handicap: str | None
    odds: Decimal | None
    model_probability: Decimal | None
    market_probability: Decimal | None
    edge: Decimal | None
    line_bucket: str
    risk_tags: tuple[str, ...]
    strategy_key: str = DEFAULT_STRATEGY.strategy_key
    strategy_display_name: str = DEFAULT_STRATEGY.display_name
    signal_version: str = DEFAULT_STRATEGY.signal_version
    odds_source: str = "live_snapshot"
    execution_target: str | None = None
    historical_snapshot_count: int = 0
    robustness_mode: str | None = None
    robustness_status: str | None = None
    robustness_primary_target: int | None = None
    robustness_seen_count: int | None = None
    robustness_min_edge: Decimal | None = None
    robustness_observed_targets: tuple[int, ...] = ()


@dataclass(frozen=True)
class PaperRecommendationQueueReport:
    generated_at: str
    window_start: str
    window_end: str
    hours: int
    near_start_hours: int
    edge_threshold: Decimal
    model_name: str
    total_matches: int
    candidate_count: int
    status_counts: dict[str, int]
    prefetch_requested: bool
    near_start_fixture_ids: list[str]
    prefetch_result: dict[str, Any] | None
    rows: list[PaperQueueRow]


@dataclass(frozen=True)
class _TeamPriorState:
    matches: int
    points: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    venue_matches: int
    venue_points: int
    last_kickoff: datetime | None


@dataclass(frozen=True)
class _ExecutionRobustnessObservation:
    target: int
    side: str | None
    line: Decimal | None
    line_bucket: str
    edge: Decimal


@dataclass(frozen=True)
class _ExecutionRobustnessEvaluation:
    mode: str
    status: str
    primary_target: int
    seen_count: int
    min_edge: Decimal | None
    observed_targets: tuple[int, ...]


def build_paper_recommendation_queue(
    session: Session,
    *,
    now: datetime,
    hours: int = 72,
    near_start_hours: int = 6,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    edge_threshold: str = "0.10",
    prefetch_odds: bool = False,
    odds_prefetcher: Callable[[list[str]], dict[str, Any] | object] | None = None,
    scorer: Callable[[dict[str, str]], PaperQueueScoreResult] | None = None,
    display_name_service: DisplayNameService | None = None,
    feature_csv_path: Path | None = None,
) -> PaperRecommendationQueueReport:
    threshold = _as_decimal(edge_threshold)
    near_start_fixture_ids = _near_start_fixture_ids(
        session,
        now=now,
        near_start_hours=near_start_hours,
    )
    prefetch_result = None
    if prefetch_odds and odds_prefetcher is not None and near_start_fixture_ids:
        prefetch_result = _normalize_prefetch_result(odds_prefetcher(near_start_fixture_ids))
    resolved_feature_csv_path = _resolve_feature_csv_path(session, feature_csv_path)
    model_scorer = scorer or _cached_live_scorer(resolved_feature_csv_path)
    matches = _list_candidate_matches(
        session,
        now=now,
        hours=hours,
        start_time=start_time,
        end_time=end_time,
    )
    team_prior_states = _team_prior_states_by_match(session, matches)
    historical_snapshots_by_match_id = _historical_snapshots_by_match_id(session, matches)
    rows = [
        row
        for match in matches
        for row in _build_queue_rows(
            match,
            scorer=model_scorer,
            edge_threshold=threshold,
            display_name_service=display_name_service,
            historical_snapshots=historical_snapshots_by_match_id.get(match.id, []),
            team_prior_states=team_prior_states,
        )
    ]
    window_start = start_time or now
    window_end = end_time or now + timedelta(hours=hours)
    status_counts = _count_statuses(rows)
    return PaperRecommendationQueueReport(
        generated_at=_format_beijing_datetime(now),
        window_start=_format_beijing_datetime(window_start),
        window_end=_format_beijing_datetime(window_end),
        hours=hours,
        near_start_hours=near_start_hours,
        edge_threshold=threshold,
        model_name="raw_hgb_team_form_plus_all_markets",
        total_matches=len(matches),
        candidate_count=status_counts.get("candidate", 0),
        status_counts=status_counts,
        prefetch_requested=prefetch_odds,
        near_start_fixture_ids=near_start_fixture_ids,
        prefetch_result=prefetch_result,
        rows=rows,
    )


def build_paper_recommendation_rows_for_match(
    match: Match,
    *,
    scorer: Callable[[dict[str, str]], PaperQueueScoreResult],
    edge_threshold: str = "0.10",
    display_name_service: DisplayNameService | None = None,
) -> list[PaperQueueRow]:
    return _build_queue_rows(
        match,
        scorer=scorer,
        edge_threshold=_as_decimal(edge_threshold),
        display_name_service=display_name_service,
    )


def _resolve_feature_csv_path(session: Session, feature_csv_path: Path | None) -> Path:
    if feature_csv_path is not None:
        return feature_csv_path
    latest_successful_run = (
        session.query(TrainingRun)
        .filter(TrainingRun.run_type == "full_refresh")
        .filter(TrainingRun.status == "success")
        .filter(TrainingRun.dynamic_feature_path.isnot(None))
        .order_by(TrainingRun.started_at.desc(), TrainingRun.id.desc())
        .first()
    )
    if latest_successful_run is None or not latest_successful_run.dynamic_feature_path:
        return DEFAULT_FEATURE_CSV_PATH
    return Path(latest_successful_run.dynamic_feature_path)


def write_paper_recommendation_queue_report(
    report: PaperRecommendationQueueReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_paper_recommendation_queue_report(report) + "\n", encoding="utf-8")


def format_paper_recommendation_queue_report(report: PaperRecommendationQueueReport) -> str:
    lines = [
        "# Paper Recommendation Queue v1",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Window: `{report.window_start}` to `{report.window_end}`",
        f"- Model: `{report.model_name}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Total matches | {report.total_matches} |",
        f"| Candidates | {report.candidate_count} |",
        f"| Edge threshold | {report.edge_threshold} |",
        f"| Near-start hours | {report.near_start_hours} |",
        f"| Prefetch requested | {report.prefetch_requested} |",
        f"| Near-start fixtures | {len(report.near_start_fixture_ids)} |",
        "",
        "## Status",
        "",
        "| Status | Count |",
        "| --- | ---: |",
    ]
    lines.extend(
        f"| {status} | {count} |"
        for status, count in sorted(report.status_counts.items())
    )
    if report.prefetch_result is not None:
        lines.extend(["", "## Odds Prefetch", "", "| Field | Value |", "| --- | --- |"])
        lines.extend(f"| {key} | {value} |" for key, value in report.prefetch_result.items())
    lines.extend(
        [
            "",
            "## Queue Detail",
            "",
            "| Match | Kickoff | League | Fixture | Status | Line | Side | Recommended handicap | Odds | Model p | Market p | Edge | Bucket | Risks |",
            "| ---: | --- | --- | --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for row in report.rows:
        fixture = f"{row.home_team_display_name} vs {row.away_team_display_name}"
        lines.append(
            f"| {row.match_id} | {row.kickoff_time} | {row.league_display_name} | {fixture} | "
            f"{row.status} | {_format_optional(row.line)} | {row.side or '-'} | "
            f"{row.recommended_handicap or '-'} | "
            f"{_format_optional(row.odds)} | {_format_optional(row.model_probability)} | "
            f"{_format_optional(row.market_probability)} | {_format_optional(row.edge)} | "
            f"{row.line_bucket} | {', '.join(row.risk_tags) or '-'} |"
        )
    return "\n".join(lines)


def _list_candidate_matches(
    session: Session,
    *,
    now: datetime,
    hours: int,
    start_time: datetime | None,
    end_time: datetime | None,
) -> list[Match]:
    query = (
        session.query(Match)
        .options(
            joinedload(Match.league),
            joinedload(Match.home_team),
            joinedload(Match.away_team),
            selectinload(Match.odds_snapshots),
        )
        .order_by(Match.kickoff_time.asc(), Match.id.asc())
    )
    if start_time is not None or end_time is not None:
        start = start_time or now
        end = end_time or now + timedelta(hours=hours)
        return (
            query.filter(Match.status.in_(("scheduled", "finished")))
            .filter(Match.kickoff_time >= start)
            .filter(Match.kickoff_time <= end)
            .all()
        )
    return (
        query.filter(Match.status == "scheduled")
        .filter(Match.kickoff_time >= now)
        .filter(Match.kickoff_time <= now + timedelta(hours=hours))
        .all()
    )


def _historical_snapshots_by_match_id(
    session: Session,
    matches: list[Match],
) -> dict[int, list[HistoricalOddsSnapshot]]:
    match_ids = [match.id for match in matches]
    if not match_ids:
        return {}
    snapshots = (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id.in_(match_ids))
        .all()
    )
    snapshots_by_match_id: dict[int, list[HistoricalOddsSnapshot]] = {}
    for snapshot in snapshots:
        snapshots_by_match_id.setdefault(snapshot.match_id, []).append(snapshot)
    return snapshots_by_match_id


def _near_start_fixture_ids(session: Session, *, now: datetime, near_start_hours: int) -> list[str]:
    rows = (
        session.query(Match.source_match_id)
        .filter(Match.status == "scheduled")
        .filter(Match.kickoff_time >= now)
        .filter(Match.kickoff_time <= now + timedelta(hours=near_start_hours))
        .filter(Match.source_match_id.isnot(None))
        .order_by(Match.kickoff_time.asc(), Match.id.asc())
        .all()
    )
    return [source_match_id for (source_match_id,) in rows if source_match_id]


def _build_queue_rows(
    match: Match,
    *,
    scorer: Callable[[dict[str, str]], PaperQueueScoreResult],
    edge_threshold: Decimal,
    display_name_service: DisplayNameService | None = None,
    historical_snapshots: list[HistoricalOddsSnapshot] | None = None,
    team_prior_states: dict[tuple[int, str], _TeamPriorState] | None = None,
) -> list[PaperQueueRow]:
    historical_snapshots = (
        historical_snapshots
        if _should_use_historical_snapshots(match, historical_snapshots or [])
        else []
    )
    odds_source = "oddspapi_historical" if historical_snapshots else "live_snapshot"
    execution_target = "latest_historical" if historical_snapshots else None
    historical_snapshot_count = len(historical_snapshots)
    feature_row = _live_feature_row(
        match,
        historical_snapshots=historical_snapshots,
        team_prior_states=team_prior_states,
    )
    diagnostic_rows = []
    asian_line = _decimal_from_row(feature_row, "asian_handicap_close_line")
    asian_odds = _decimal_from_row(feature_row, "asian_handicap_away_odds")
    if asian_line is None or asian_odds is None:
        diagnostic_rows.append(
            _row(
                match,
                status="no_odds",
                line=asian_line,
                odds=asian_odds,
                feature_row=feature_row,
                display_name_service=display_name_service,
                odds_source=odds_source,
                execution_target=execution_target,
                historical_snapshot_count=historical_snapshot_count,
            )
        )
    elif not _has_allowed_candidate_odds_status(match, historical_snapshots=historical_snapshots):
        diagnostic_rows.append(
            _row(
                match,
                status="odds_status_not_ready",
                line=asian_line,
                odds=asian_odds,
                feature_row=feature_row,
                display_name_service=display_name_service,
                odds_source=odds_source,
                execution_target=execution_target,
                historical_snapshot_count=historical_snapshot_count,
            )
        )
    elif not _has_candidate_fresh_odds(match, historical_snapshots=historical_snapshots):
        diagnostic_rows.append(
            _row(
                match,
                status="stale_odds",
                line=asian_line,
                odds=asian_odds,
                feature_row=feature_row,
                display_name_service=display_name_service,
                odds_source=odds_source,
                execution_target=execution_target,
                historical_snapshot_count=historical_snapshot_count,
            )
        )
    scores = _normalize_scores(scorer(feature_row))
    if not scores:
        if diagnostic_rows:
            return diagnostic_rows
        return [
            _row(
                match,
                status="unscored",
                line=asian_line,
                odds=asian_odds,
                feature_row=feature_row,
                display_name_service=display_name_service,
                odds_source=odds_source,
                execution_target=execution_target,
                historical_snapshot_count=historical_snapshot_count,
            )
        ]
    rows = list(diagnostic_rows)
    for score in scores:
        if score.market_type == "asian_handicap" and diagnostic_rows:
            continue
        scored = _scored_row(
            match,
            score=score,
            edge_threshold=edge_threshold,
            feature_row=feature_row,
            display_name_service=display_name_service,
            historical_snapshots=historical_snapshots,
            odds_source=odds_source,
            execution_target=execution_target,
            historical_snapshot_count=historical_snapshot_count,
        )
        if scored is None:
            continue
        bucket_rows = _bucket_strategy_rows(scored)
        if scored.market_type == DEFAULT_STRATEGY.market_type:
            rows.append(scored)
        elif scored.status != "candidate":
            rows.append(scored)
        rows.extend(bucket_rows)
    return _apply_execution_robustness_to_rows(
        rows or diagnostic_rows,
        match=match,
        scorer=scorer,
        edge_threshold=edge_threshold,
        display_name_service=display_name_service,
        historical_snapshots=historical_snapshots,
        team_prior_states=team_prior_states,
    )


def _should_use_historical_snapshots(
    match: Match,
    historical_snapshots: list[HistoricalOddsSnapshot],
) -> bool:
    if not historical_snapshots:
        return False
    if match.status == "finished":
        return True
    return _has_complete_historical_odds_market_pair(
        historical_snapshots,
        market_type="asian_handicap",
    )


def _apply_execution_robustness_to_rows(
    rows: list[PaperQueueRow],
    *,
    match: Match,
    scorer: Callable[[dict[str, str]], PaperQueueScoreResult],
    edge_threshold: Decimal,
    display_name_service: DisplayNameService | None,
    historical_snapshots: list[HistoricalOddsSnapshot],
    team_prior_states: dict[tuple[int, str], _TeamPriorState] | None,
) -> list[PaperQueueRow]:
    if not rows:
        return rows
    return [
        _apply_execution_robustness_to_row(
            row,
            match=match,
            scorer=scorer,
            edge_threshold=edge_threshold,
            display_name_service=display_name_service,
            historical_snapshots=historical_snapshots,
            team_prior_states=team_prior_states,
        )
        for row in rows
    ]


def _apply_execution_robustness_to_row(
    row: PaperQueueRow,
    *,
    match: Match,
    scorer: Callable[[dict[str, str]], PaperQueueScoreResult],
    edge_threshold: Decimal,
    display_name_service: DisplayNameService | None,
    historical_snapshots: list[HistoricalOddsSnapshot],
    team_prior_states: dict[tuple[int, str], _TeamPriorState] | None,
) -> PaperQueueRow:
    if row.status != "candidate":
        return row
    rule = DEFAULT_SELECTED_ROBUSTNESS_RULES.get(row.strategy_key)
    if rule is None or row.odds_source != "oddspapi_historical" or not historical_snapshots:
        return row
    evaluation = _evaluate_execution_robustness(
        row,
        match=match,
        scorer=scorer,
        edge_threshold=edge_threshold,
        display_name_service=display_name_service,
        historical_snapshots=historical_snapshots,
        team_prior_states=team_prior_states,
        rule=rule,
    )
    if evaluation.status == "filtered" and match.status == "scheduled":
        return PaperQueueRow(
            **{
                **row.__dict__,
                "status": "robustness_filtered",
                "risk_tags": (*row.risk_tags, "robustness:filtered"),
                "robustness_mode": evaluation.mode,
                "robustness_status": evaluation.status,
                "robustness_primary_target": evaluation.primary_target,
                "robustness_seen_count": evaluation.seen_count,
                "robustness_min_edge": evaluation.min_edge,
                "robustness_observed_targets": evaluation.observed_targets,
            }
        )
    risk_tags = row.risk_tags
    if evaluation.status == "filtered":
        risk_tags = (*risk_tags, "robustness:filtered")
    elif evaluation.status == "unavailable":
        risk_tags = (*risk_tags, "robustness:unavailable")
    return PaperQueueRow(
        **{
            **row.__dict__,
            "risk_tags": risk_tags,
            "robustness_mode": evaluation.mode,
            "robustness_status": evaluation.status,
            "robustness_primary_target": evaluation.primary_target,
            "robustness_seen_count": evaluation.seen_count,
            "robustness_min_edge": evaluation.min_edge,
            "robustness_observed_targets": evaluation.observed_targets,
        }
    )


def _evaluate_execution_robustness(
    row: PaperQueueRow,
    *,
    match: Match,
    scorer: Callable[[dict[str, str]], PaperQueueScoreResult],
    edge_threshold: Decimal,
    display_name_service: DisplayNameService | None,
    historical_snapshots: list[HistoricalOddsSnapshot],
    team_prior_states: dict[tuple[int, str], _TeamPriorState] | None,
    rule: SelectedExecutionRobustnessRule,
) -> _ExecutionRobustnessEvaluation:
    observations = _execution_robustness_observations(
        row,
        match=match,
        scorer=scorer,
        edge_threshold=edge_threshold,
        display_name_service=display_name_service,
        historical_snapshots=historical_snapshots,
        team_prior_states=team_prior_states,
    )
    primary = next(
        (observation for observation in observations if observation.target == rule.primary_target),
        None,
    )
    if primary is None:
        return _ExecutionRobustnessEvaluation(
            mode=rule.mode,
            status="unavailable",
            primary_target=rule.primary_target,
            seen_count=len(observations),
            min_edge=_min_observed_edge(observations),
            observed_targets=tuple(sorted(observation.target for observation in observations)),
        )
    min_edge = _min_observed_edge(observations)
    if rule.mode == "observe":
        return _ExecutionRobustnessEvaluation(
            mode=rule.mode,
            status="observed",
            primary_target=rule.primary_target,
            seen_count=len(observations),
            min_edge=min_edge,
            observed_targets=tuple(sorted(observation.target for observation in observations)),
        )
    status = (
        "kept"
        if _observations_match_rule(primary, observations, rule)
        else "filtered"
    )
    return _ExecutionRobustnessEvaluation(
        mode=rule.mode,
        status=status,
        primary_target=rule.primary_target,
        seen_count=len(observations),
        min_edge=min_edge,
        observed_targets=tuple(sorted(observation.target for observation in observations)),
    )


def _execution_robustness_observations(
    row: PaperQueueRow,
    *,
    match: Match,
    scorer: Callable[[dict[str, str]], PaperQueueScoreResult],
    edge_threshold: Decimal,
    display_name_service: DisplayNameService | None,
    historical_snapshots: list[HistoricalOddsSnapshot],
    team_prior_states: dict[tuple[int, str], _TeamPriorState] | None,
) -> list[_ExecutionRobustnessObservation]:
    observations = []
    for target in DEFAULT_EXECUTION_ROBUSTNESS_TARGETS:
        target_snapshots = _historical_snapshots_for_execution_target(
            match,
            historical_snapshots=historical_snapshots,
            target_minutes_before_kickoff=target,
            tolerance_minutes=DEFAULT_EXECUTION_ROBUSTNESS_TOLERANCE_MINUTES,
        )
        if not target_snapshots:
            continue
        feature_row = _live_feature_row(
            match,
            historical_snapshots=target_snapshots,
            team_prior_states=team_prior_states,
        )
        target_rows = _strategy_rows_for_feature_row(
            match,
            scorer=scorer,
            edge_threshold=edge_threshold,
            feature_row=feature_row,
            display_name_service=display_name_service,
            historical_snapshots=target_snapshots,
            odds_source="oddspapi_historical",
            execution_target=f"T-{target}",
            historical_snapshot_count=len(historical_snapshots),
        )
        target_row = next(
            (
                candidate
                for candidate in target_rows
                if candidate.status == "candidate"
                and candidate.strategy_key == row.strategy_key
                and candidate.edge is not None
            ),
            None,
        )
        if target_row is None or target_row.edge is None:
            continue
        observations.append(
            _ExecutionRobustnessObservation(
                target=target,
                side=target_row.side,
                line=target_row.line,
                line_bucket=target_row.line_bucket,
                edge=target_row.edge,
            )
        )
    return observations


def _strategy_rows_for_feature_row(
    match: Match,
    *,
    scorer: Callable[[dict[str, str]], PaperQueueScoreResult],
    edge_threshold: Decimal,
    feature_row: dict[str, str],
    display_name_service: DisplayNameService | None,
    historical_snapshots: list[HistoricalOddsSnapshot],
    odds_source: str,
    execution_target: str | None,
    historical_snapshot_count: int,
) -> list[PaperQueueRow]:
    rows = []
    for score in _normalize_scores(scorer(feature_row)):
        scored = _scored_row(
            match,
            score=score,
            edge_threshold=edge_threshold,
            feature_row=feature_row,
            display_name_service=display_name_service,
            historical_snapshots=historical_snapshots,
            odds_source=odds_source,
            execution_target=execution_target,
            historical_snapshot_count=historical_snapshot_count,
        )
        if scored is None:
            continue
        bucket_rows = _bucket_strategy_rows(scored)
        if scored.market_type == DEFAULT_STRATEGY.market_type:
            rows.append(scored)
        elif scored.status != "candidate":
            rows.append(scored)
        rows.extend(bucket_rows)
    return rows


def _observations_match_rule(
    primary: _ExecutionRobustnessObservation,
    observations: list[_ExecutionRobustnessObservation],
    rule: SelectedExecutionRobustnessRule,
) -> bool:
    min_edge = _min_observed_edge(observations)
    if len(observations) < rule.min_seen_count:
        return False
    if min_edge is None or min_edge < rule.min_edge:
        return False
    if rule.require_side_unchanged and any(observation.side != primary.side for observation in observations):
        return False
    if not rule.allow_line_changed and any(observation.line != primary.line for observation in observations):
        return False
    if not rule.allow_bucket_changed and any(
        observation.line_bucket != primary.line_bucket for observation in observations
    ):
        return False
    return True


def _min_observed_edge(
    observations: list[_ExecutionRobustnessObservation],
) -> Decimal | None:
    if not observations:
        return None
    return _quantize(min(observation.edge for observation in observations))


def _historical_snapshots_for_execution_target(
    match: Match,
    *,
    historical_snapshots: list[HistoricalOddsSnapshot],
    target_minutes_before_kickoff: int,
    tolerance_minutes: int,
) -> list[HistoricalOddsSnapshot]:
    selected = []
    for market_type in ("asian_handicap", "total_goals", "match_winner"):
        pairs = _pair_market_snapshots(
            [snapshot for snapshot in historical_snapshots if snapshot.market_type == market_type],
            market_type=market_type,
        )
        pair = _select_execution_pair(
            pairs,
            kickoff_time=_match_snapshot_timeline_kickoff_time(match),
            target_minutes_before_kickoff=target_minutes_before_kickoff,
            tolerance_minutes=tolerance_minutes,
        )
        if pair is not None:
            selected.extend(_snapshots_from_pair(match, pair))
    return selected


def _select_execution_pair(
    pairs: list[_PairedMarketSnapshot],
    *,
    kickoff_time: datetime,
    target_minutes_before_kickoff: int,
    tolerance_minutes: int,
) -> _PairedMarketSnapshot | None:
    kickoff = _comparable_datetime(kickoff_time)
    target_time = kickoff - timedelta(minutes=target_minutes_before_kickoff)
    window_start = kickoff - timedelta(minutes=target_minutes_before_kickoff + tolerance_minutes)
    window_end = kickoff - timedelta(minutes=target_minutes_before_kickoff - tolerance_minutes)
    candidates = [
        pair
        for pair in pairs
        if window_start <= _comparable_datetime(pair.snapshot_time) <= window_end
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda pair: (
            abs((_comparable_datetime(pair.snapshot_time) - target_time).total_seconds()),
            0 if _comparable_datetime(pair.snapshot_time) <= target_time else 1,
            pair.balance_gap,
        ),
    )


def _snapshots_from_pair(
    match: Match,
    pair: _PairedMarketSnapshot,
) -> list[HistoricalOddsSnapshot]:
    sides = [(pair.side_a, pair.side_a_odds), (pair.side_b, pair.side_b_odds)]
    if pair.side_c is not None and pair.side_c_odds is not None:
        sides.append((pair.side_c, pair.side_c_odds))
    return [
        HistoricalOddsSnapshot(
            match_id=match.id,
            source_name=ODDSPAPI_SOURCE_NAME,
            source_fixture_id=match.source_match_id or str(match.id),
            bookmaker=pair.bookmaker,
            market_type=pair.market_type,
            market_id=f"execution-{pair.market_type}-{side}",
            market_name=pair.market_type,
            market_line=pair.market_line,
            outcome_side=side,
            odds=odds,
            snapshot_time=pair.snapshot_time,
            period="fulltime",
        )
        for side, odds in sides
    ]


def _match_snapshot_timeline_kickoff_time(match: Match) -> datetime:
    if match.fixture_timestamp is not None:
        return datetime.fromtimestamp(match.fixture_timestamp, timezone.utc).replace(tzinfo=None)
    return _comparable_datetime(match.kickoff_time)


def _scored_row(
    match: Match,
    *,
    score: PaperQueueScore,
    edge_threshold: Decimal,
    feature_row: dict[str, str],
    display_name_service: DisplayNameService | None,
    historical_snapshots: list[HistoricalOddsSnapshot] | None = None,
    odds_source: str = "live_snapshot",
    execution_target: str | None = None,
    historical_snapshot_count: int = 0,
) -> PaperQueueRow | None:
    if score.market_type == "total_goals":
        line = _decimal_from_row(feature_row, "total_goals_close_line")
        if line is None or not _has_fresh_market_odds(
            match,
            market_type="total_goals",
            historical_snapshots=historical_snapshots,
        ):
            return None
        odds = (
            _decimal_from_row(feature_row, "total_goals_over_odds")
            if score.side == "over"
            else _decimal_from_row(feature_row, "total_goals_under_odds")
        )
        line_bucket = _total_line_bucket(line)
    else:
        line = _decimal_from_row(feature_row, "asian_handicap_close_line")
        odds = (
            _decimal_from_row(feature_row, "asian_handicap_away_odds")
            if score.side == "away_cover"
            else _decimal_from_row(feature_row, "asian_handicap_home_odds")
        )
        line_bucket = _line_bucket(line)
    status = _status_for_score(score, edge_threshold, line_bucket=line_bucket)
    risk_tags = _risk_tags(line_bucket, feature_row)
    if _is_model_consensus_confirmed(score):
        risk_tags = (*risk_tags, "model_consensus:confirmed")
    return _row(
        match,
        status=status,
        market_type=score.market_type,
        line=line,
        side=score.side,
        odds=odds,
        model_probability=score.model_probability,
        market_probability=score.market_probability,
        edge=score.edge,
        line_bucket=line_bucket,
        risk_tags=risk_tags,
        feature_row=feature_row,
        display_name_service=display_name_service,
        odds_source=odds_source,
        execution_target=execution_target,
        historical_snapshot_count=historical_snapshot_count,
    )


def _bucket_strategy_rows(row: PaperQueueRow) -> list[PaperQueueRow]:
    if row.market_type == "total_goals":
        return _total_goals_bucket_rows(row)
    return _asian_handicap_bucket_rows(row)


def _asian_handicap_bucket_rows(row: PaperQueueRow) -> list[PaperQueueRow]:
    rows = []
    away_row = _v2_row(row)
    if away_row is not None:
        rows.append(away_row)
    home_row = _home_favorite_v1_row(row)
    if home_row is not None:
        rows.append(home_row)
    return rows


def _v2_row(row: PaperQueueRow) -> PaperQueueRow | None:
    if row.side != "away_cover" or row.edge is None:
        return None
    bucket_thresholds = BUCKET_V2_STRATEGY.line_bucket_thresholds or {}
    threshold = bucket_thresholds.get(row.line_bucket)
    if threshold is None or row.edge < threshold:
        return None
    return PaperQueueRow(
        **{
            **row.__dict__,
            "status": "candidate",
            "risk_tags": (
                *row.risk_tags,
                *(
                    (BUCKET_V2_STRATEGY.risk_tag,)
                    if BUCKET_V2_STRATEGY.risk_tag is not None
                    else ()
                ),
            ),
            "strategy_key": BUCKET_V2_STRATEGY.strategy_key,
            "strategy_display_name": BUCKET_V2_STRATEGY.display_name,
            "signal_version": BUCKET_V2_STRATEGY.signal_version,
        }
    )


def _home_favorite_v1_row(row: PaperQueueRow) -> PaperQueueRow | None:
    if row.side != "home_cover" or row.edge is None:
        return None
    home_bucket = _home_line_bucket(row.line)
    bucket_thresholds = HOME_FAVORITE_BUCKET_V1_STRATEGY.line_bucket_thresholds or {}
    threshold = bucket_thresholds.get(home_bucket)
    if threshold is None or row.edge < threshold:
        return None
    return PaperQueueRow(
        **{
            **row.__dict__,
            "status": "candidate",
            "line_bucket": home_bucket,
            "risk_tags": (
                f"line_bucket:{home_bucket}",
                *(
                    (HOME_FAVORITE_BUCKET_V1_STRATEGY.risk_tag,)
                    if HOME_FAVORITE_BUCKET_V1_STRATEGY.risk_tag is not None
                    else ()
                ),
            ),
            "strategy_key": HOME_FAVORITE_BUCKET_V1_STRATEGY.strategy_key,
            "strategy_display_name": HOME_FAVORITE_BUCKET_V1_STRATEGY.display_name,
            "signal_version": HOME_FAVORITE_BUCKET_V1_STRATEGY.signal_version,
        }
    )


def _total_goals_bucket_rows(row: PaperQueueRow) -> list[PaperQueueRow]:
    rows = []
    for strategy in (
        TOTAL_GOALS_BUCKET_V2_STRATEGY,
        TOTAL_GOALS_LOW_LINE_BUCKET_V3_STRATEGY,
        TOTAL_GOALS_CONFIRMED_UNDER_MID_275_V1_STRATEGY,
    ):
        strategy_row = _total_goals_strategy_row(row, strategy)
        if strategy_row is not None:
            rows.append(strategy_row)
    return rows


def _total_goals_strategy_row(row: PaperQueueRow, strategy) -> PaperQueueRow | None:
    if row.market_type != "total_goals" or row.side is None or row.edge is None:
        return None
    bucket_thresholds = strategy.line_bucket_thresholds or {}
    threshold = bucket_thresholds.get(f"{row.side}@{row.line_bucket}")
    if threshold is None or row.edge < threshold:
        return None
    risk_tags = row.risk_tags
    if strategy.strategy_key == TOTAL_GOALS_CONFIRMED_UNDER_MID_275_V1_STRATEGY.strategy_key:
        if "model_consensus:confirmed" not in row.risk_tags:
            return None
        risk_tags = tuple(tag for tag in row.risk_tags if not tag.startswith("strategy:"))
    return PaperQueueRow(
        **{
            **row.__dict__,
            "status": "candidate",
            "risk_tags": (
                *risk_tags,
                *(
                    (strategy.risk_tag,)
                    if strategy.risk_tag is not None
                    else ()
                ),
            ),
            "strategy_key": strategy.strategy_key,
            "strategy_display_name": strategy.display_name,
            "signal_version": strategy.signal_version,
        }
    )


def _status_for_score(
    score: PaperQueueScore,
    edge_threshold: Decimal,
    *,
    line_bucket: str,
) -> str:
    if score.market_type == "total_goals":
        if score.side not in {"over", "under"}:
            return "unsupported_side"
        total_goals_threshold = _total_goals_bucket_threshold(score, line_bucket=line_bucket)
        if total_goals_threshold is None:
            return "unsupported_bucket"
        if score.edge < total_goals_threshold:
            return "below_threshold"
        return "candidate"
    if score.side == "home_cover":
        home_favorite_threshold = _home_favorite_threshold(line_bucket=line_bucket)
        if home_favorite_threshold is None:
            return "unsupported_bucket"
        if score.edge < home_favorite_threshold:
            return "below_threshold"
        return "candidate"
    if score.side != "away_cover":
        return "non_away_cover"
    if score.edge < edge_threshold:
        return "below_threshold"
    return "candidate"


def _total_goals_bucket_threshold(
    score: PaperQueueScore,
    *,
    line_bucket: str,
) -> Decimal | None:
    side_bucket = f"{score.side}@{line_bucket}"
    thresholds = [
        threshold
        for strategy in (TOTAL_GOALS_BUCKET_V2_STRATEGY, TOTAL_GOALS_LOW_LINE_BUCKET_V3_STRATEGY)
        if (threshold := (strategy.line_bucket_thresholds or {}).get(side_bucket)) is not None
    ]
    if not thresholds:
        return None
    return min(thresholds)


def _home_favorite_threshold(*, line_bucket: str) -> Decimal | None:
    home_bucket = _home_line_bucket_from_away_bucket(line_bucket)
    return (HOME_FAVORITE_BUCKET_V1_STRATEGY.line_bucket_thresholds or {}).get(home_bucket)


def _normalize_scores(result: PaperQueueScoreResult) -> list[PaperQueueScore]:
    if result is None:
        return []
    if isinstance(result, PaperQueueScore):
        return [result]
    return list(result)


def _row(
    match: Match,
    *,
    status: str,
    market_type: str = "asian_handicap",
    line: Decimal | None,
    odds: Decimal | None,
    side: str | None = None,
    model_probability: Decimal | None = None,
    market_probability: Decimal | None = None,
    edge: Decimal | None = None,
    line_bucket: str | None = None,
    risk_tags: tuple[str, ...] | None = None,
    feature_row: dict[str, str] | None = None,
    display_name_service: DisplayNameService | None = None,
    odds_source: str = "live_snapshot",
    execution_target: str | None = None,
    historical_snapshot_count: int = 0,
    robustness_mode: str | None = None,
    robustness_status: str | None = None,
    robustness_primary_target: int | None = None,
    robustness_seen_count: int | None = None,
    robustness_min_edge: Decimal | None = None,
    robustness_observed_targets: tuple[int, ...] = (),
) -> PaperQueueRow:
    display_name_service = display_name_service or DisplayNameService()
    line_bucket = line_bucket or (_total_line_bucket(line) if market_type == "total_goals" else _line_bucket(line))
    risk_tags = risk_tags or _risk_tags(line_bucket, feature_row or {})
    league_name = match.league.name
    home_team_name = match.home_team.canonical_name
    away_team_name = match.away_team.canonical_name
    return PaperQueueRow(
        match_id=match.id,
        source_match_id=match.source_match_id,
        kickoff_time=_format_beijing_datetime(match.kickoff_time),
        league_name=league_name,
        league_display_name=display_name_service.display_league(league_name),
        home_team_name=home_team_name,
        home_team_display_name=display_name_service.display_team(home_team_name),
        away_team_name=away_team_name,
        away_team_display_name=display_name_service.display_team(away_team_name),
        status=status,
        market_type=market_type,
        line=line,
        side=side,
        recommended_handicap=_recommended_for_market(market_type, side, line),
        odds=odds,
        model_probability=model_probability,
        market_probability=market_probability,
        edge=edge,
        line_bucket=line_bucket,
        risk_tags=risk_tags,
        odds_source=odds_source,
        execution_target=execution_target,
        historical_snapshot_count=historical_snapshot_count,
        robustness_mode=robustness_mode,
        robustness_status=robustness_status,
        robustness_primary_target=robustness_primary_target,
        robustness_seen_count=robustness_seen_count,
        robustness_min_edge=robustness_min_edge,
        robustness_observed_targets=robustness_observed_targets,
    )


def _is_model_consensus_confirmed(score: PaperQueueScore) -> bool:
    return (
        score.calibrated_side == score.side
        and score.calibrated_edge is not None
        and score.calibrated_edge >= Decimal("0.0000")
    )


def _live_feature_row(
    match: Match,
    *,
    historical_snapshots: list[HistoricalOddsSnapshot] | None = None,
    team_prior_states: dict[tuple[int, str], _TeamPriorState] | None = None,
) -> dict[str, str]:
    odds_features = (
        _historical_odds_features(match, historical_snapshots)
        if historical_snapshots
        else build_match_odds_features(match)
    )
    home_state = (
        team_prior_states.get((match.id, "home"))
        if team_prior_states is not None
        else _team_prior_state(match, side="home")
    )
    away_state = (
        team_prior_states.get((match.id, "away"))
        if team_prior_states is not None
        else _team_prior_state(match, side="away")
    )
    if home_state is None:
        home_state = _team_prior_state(match, side="home")
    if away_state is None:
        away_state = _team_prior_state(match, side="away")
    row = {feature: "" for feature in FEATURES}
    row.update(
        {
            "match_id": str(match.id),
            "source_match_id": match.source_match_id or "",
            "league_name": match.league.name,
            "season": str(match.season or ""),
            "kickoff_time": match.kickoff_time.isoformat(),
            "home_team_name": match.home_team.canonical_name,
            "away_team_name": match.away_team.canonical_name,
            **_team_feature_values("home", home_state, match.kickoff_time, venue="home"),
            **_team_feature_values("away", away_state, match.kickoff_time, venue="away"),
            "match_winner_home_implied_probability": _implied_probability(
                odds_features.match_winner_home_odds.mean
            ),
            "match_winner_draw_implied_probability": _implied_probability(
                odds_features.match_winner_draw_odds.mean
            ),
            "match_winner_away_implied_probability": _implied_probability(
                odds_features.match_winner_away_odds.mean
            ),
            "match_winner_overround": _overround(
                odds_features.match_winner_home_odds.mean,
                odds_features.match_winner_draw_odds.mean,
                odds_features.match_winner_away_odds.mean,
            ),
            "asian_handicap_close_line": _format_decimal(odds_features.asian_handicap.mean, LINE_QUANT),
            "asian_handicap_home_odds": _format_decimal(odds_features.home_odds.mean, ODDS_QUANT),
            "asian_handicap_away_odds": _format_decimal(odds_features.away_odds.mean, ODDS_QUANT),
            "asian_handicap_home_implied_probability": _implied_probability(odds_features.home_odds.mean),
            "asian_handicap_away_implied_probability": _implied_probability(odds_features.away_odds.mean),
            "asian_handicap_overround": _overround(odds_features.home_odds.mean, odds_features.away_odds.mean),
            "total_goals_close_line": _format_decimal(odds_features.total_line.mean, LINE_QUANT),
            "total_goals_over_odds": _format_decimal(odds_features.over_odds.mean, ODDS_QUANT),
            "total_goals_under_odds": _format_decimal(odds_features.under_odds.mean, ODDS_QUANT),
            "total_goals_over_implied_probability": _implied_probability(odds_features.over_odds.mean),
            "total_goals_under_implied_probability": _implied_probability(odds_features.under_odds.mean),
            "total_goals_overround": _overround(odds_features.over_odds.mean, odds_features.under_odds.mean),
        }
    )
    return row


def _team_prior_state(match: Match, *, side: str) -> _TeamPriorState:
    target_team_id = match.home_team_id if side == "home" else match.away_team_id
    prior_matches = [
        prior
        for prior in match.league.matches
        if prior.status == "finished"
        and _naive_datetime(prior.kickoff_time) < _naive_datetime(match.kickoff_time)
        and prior.home_score is not None
        and prior.away_score is not None
        and (prior.home_team_id == target_team_id or prior.away_team_id == target_team_id)
    ]
    prior_matches.sort(key=lambda item: (item.kickoff_time, item.id))
    return _team_prior_state_from_matches(
        prior_matches,
        target_team_id=target_team_id,
        side=side,
        kickoff=match.kickoff_time,
    )


def _team_prior_states_by_match(
    session: Session,
    matches: list[Match],
) -> dict[tuple[int, str], _TeamPriorState]:
    if not matches:
        return {}
    league_ids = {match.league_id for match in matches}
    team_ids = {
        team_id
        for match in matches
        for team_id in (match.home_team_id, match.away_team_id)
    }
    max_kickoff = max(match.kickoff_time for match in matches)
    prior_rows = (
        session.query(Match)
        .filter(Match.status == "finished")
        .filter(Match.league_id.in_(league_ids))
        .filter(Match.kickoff_time < max_kickoff)
        .filter(Match.home_score.isnot(None))
        .filter(Match.away_score.isnot(None))
        .filter(or_(Match.home_team_id.in_(team_ids), Match.away_team_id.in_(team_ids)))
        .order_by(Match.kickoff_time.asc(), Match.id.asc())
        .all()
    )
    prior_by_team: dict[tuple[int, int], list[Match]] = {}
    for prior in prior_rows:
        prior_by_team.setdefault((prior.league_id, prior.home_team_id), []).append(prior)
        prior_by_team.setdefault((prior.league_id, prior.away_team_id), []).append(prior)

    states: dict[tuple[int, str], _TeamPriorState] = {}
    for match in matches:
        for side, target_team_id in (
            ("home", match.home_team_id),
            ("away", match.away_team_id),
        ):
            prior_matches = [
                prior
                for prior in prior_by_team.get((match.league_id, target_team_id), [])
                if _naive_datetime(prior.kickoff_time) < _naive_datetime(match.kickoff_time)
            ]
            states[(match.id, side)] = _team_prior_state_from_matches(
                prior_matches,
                target_team_id=target_team_id,
                side=side,
                kickoff=match.kickoff_time,
            )
    return states


def _team_prior_state_from_matches(
    prior_matches: list[Match],
    *,
    target_team_id: int,
    side: str,
    kickoff: datetime,
) -> _TeamPriorState:
    points = wins = draws = losses = goals_for = goals_against = 0
    venue_matches = venue_points = 0
    for prior in prior_matches:
        is_home = prior.home_team_id == target_team_id
        team_score = prior.home_score if is_home else prior.away_score
        opponent_score = prior.away_score if is_home else prior.home_score
        if team_score > opponent_score:
            result_points = 3
            wins += 1
        elif team_score < opponent_score:
            result_points = 0
            losses += 1
        else:
            result_points = 1
            draws += 1
        points += result_points
        goals_for += team_score
        goals_against += opponent_score
        if (side == "home" and is_home) or (side == "away" and not is_home):
            venue_matches += 1
            venue_points += result_points
    return _TeamPriorState(
        matches=len(prior_matches),
        points=points,
        wins=wins,
        draws=draws,
        losses=losses,
        goals_for=goals_for,
        goals_against=goals_against,
        venue_matches=venue_matches,
        venue_points=venue_points,
        last_kickoff=prior_matches[-1].kickoff_time if prior_matches else None,
    )


def _historical_odds_features(
    match: Match,
    snapshots: list[HistoricalOddsSnapshot] | None,
) -> MatchOddsFeatures:
    snapshots = snapshots or []
    asian_pair = _historical_market_pair(snapshots, market_type="asian_handicap")
    total_pair = _historical_market_pair(snapshots, market_type="total_goals")
    winner_pair = _historical_market_pair(snapshots, market_type="match_winner")
    return MatchOddsFeatures(
        match_id=match.id,
        bookmaker_count=len({snapshot.bookmaker for snapshot in snapshots}),
        asian_handicap=_aggregate_one(asian_pair[0] if asian_pair else None),
        home_odds=_aggregate_one(asian_pair[1].get("home") if asian_pair else None),
        away_odds=_aggregate_one(asian_pair[1].get("away") if asian_pair else None),
        total_line=_aggregate_one(total_pair[0] if total_pair else None),
        over_odds=_aggregate_one(total_pair[1].get("over") if total_pair else None),
        under_odds=_aggregate_one(total_pair[1].get("under") if total_pair else None),
        match_winner_home_odds=_aggregate_one(winner_pair[1].get("home") if winner_pair else None),
        match_winner_draw_odds=_aggregate_one(winner_pair[1].get("draw") if winner_pair else None),
        match_winner_away_odds=_aggregate_one(winner_pair[1].get("away") if winner_pair else None),
    )


def _historical_market_pair(
    snapshots: list[HistoricalOddsSnapshot],
    *,
    market_type: str,
) -> tuple[Decimal, dict[str, Decimal]] | None:
    market_snapshots = [snapshot for snapshot in snapshots if snapshot.market_type == market_type]
    if not market_snapshots:
        return None
    latest_time = max(snapshot.snapshot_time for snapshot in market_snapshots)
    latest = [snapshot for snapshot in market_snapshots if snapshot.snapshot_time == latest_time]
    return latest[0].market_line, {snapshot.outcome_side: snapshot.odds for snapshot in latest}


def _aggregate_one(value: Decimal | None) -> OddsMarketAggregate:
    if value is None:
        return OddsMarketAggregate(
            sample_count=0,
            mean=None,
            median=None,
            minimum=None,
            maximum=None,
            disagreement=None,
        )
    return OddsMarketAggregate(
        sample_count=1,
        mean=value,
        median=value,
        minimum=value,
        maximum=value,
        disagreement=Decimal("0.00"),
    )


def _team_feature_values(
    prefix: str,
    state: _TeamPriorState,
    kickoff: datetime,
    *,
    venue: str,
) -> dict[str, str]:
    return {
        f"{prefix}_prior_matches": str(state.matches),
        f"{prefix}_prior_points_per_match": _ratio(state.points, state.matches),
        f"{prefix}_prior_win_rate": _ratio(state.wins, state.matches),
        f"{prefix}_prior_draw_rate": _ratio(state.draws, state.matches),
        f"{prefix}_prior_loss_rate": _ratio(state.losses, state.matches),
        f"{prefix}_prior_goals_for_per_match": _ratio(state.goals_for, state.matches),
        f"{prefix}_prior_goals_against_per_match": _ratio(state.goals_against, state.matches),
        f"{prefix}_prior_{venue}_matches": str(state.venue_matches),
        f"{prefix}_prior_{venue}_points_per_match": _ratio(
            state.venue_points,
            state.venue_matches,
        ),
        f"{prefix}_rest_days": _rest_days(state.last_kickoff, kickoff),
    }


def _train_live_scorer(feature_csv_path: Path) -> Callable[[dict[str, str]], PaperQueueScoreResult]:
    if not feature_csv_path.exists():
        raise FileNotFoundError(f"feature csv not found: {feature_csv_path}")
    with feature_csv_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    return train_paper_queue_scorer_from_rows(rows)


def _cached_live_scorer(feature_csv_path: Path) -> Callable[[dict[str, str]], PaperQueueScoreResult]:
    cache_key = (_feature_file_fingerprint(feature_csv_path), id(_train_live_scorer))
    cached = _SCORER_CACHE.get(cache_key)
    if cached is not None:
        return cached
    scorer = _train_live_scorer(feature_csv_path)
    _SCORER_CACHE.clear()
    _SCORER_CACHE[cache_key] = scorer
    return scorer


def _feature_file_fingerprint(feature_csv_path: Path) -> tuple[Path, int | None, int | None]:
    try:
        stat = feature_csv_path.stat()
    except FileNotFoundError:
        return (feature_csv_path, None, None)
    return (feature_csv_path, stat.st_mtime_ns, stat.st_size)


def train_paper_queue_scorer_from_rows(
    rows: list[dict[str, str]],
) -> Callable[[dict[str, str]], PaperQueueScoreResult]:
    asian_handicap_train_rows = [row for row in rows if _asian_handicap_target_label(row) is not None]
    total_goals_train_rows = [row for row in rows if _total_goals_target_label(row) is not None]
    if not asian_handicap_train_rows:
        raise ValueError("paper queue scorer requires asian handicap training rows")
    asian_handicap_model = _raw_model()
    asian_handicap_model.fit(
        _matrix(asian_handicap_train_rows, FEATURES),
        [_asian_handicap_target_label(row) for row in asian_handicap_train_rows],
    )
    asian_handicap_calibrated_model = _calibrated_model()
    asian_handicap_calibrated_model.fit(
        _matrix(asian_handicap_train_rows, FEATURES),
        np.asarray([_asian_handicap_target_label(row) for row in asian_handicap_train_rows]),
    )
    total_goals_model = None
    total_goals_calibrated_model = None
    if total_goals_train_rows:
        total_goals_model = _raw_model()
        total_goals_model.fit(
            _matrix(total_goals_train_rows, FEATURES),
            [_total_goals_target_label(row) for row in total_goals_train_rows],
        )
        total_goals_calibrated_model = _calibrated_model()
        total_goals_calibrated_model.fit(
            _matrix(total_goals_train_rows, FEATURES),
            np.asarray([_total_goals_target_label(row) for row in total_goals_train_rows]),
        )

    def score(row: dict[str, str]) -> list[PaperQueueScore]:
        scores = []
        asian_handicap_score = _score_market(
            row,
            model=asian_handicap_model,
            calibrated_model=asian_handicap_calibrated_model,
            probability_fields=ASIAN_HANDICAP_PROBABILITY_FIELDS,
            side_labels=ASIAN_HANDICAP_SIDE_LABELS,
            align_probabilities=_align_asian_handicap_probabilities,
            market_type="asian_handicap",
        )
        if asian_handicap_score is not None:
            scores.append(asian_handicap_score)
        if total_goals_model is not None:
            total_goals_score = _score_market(
                row,
                model=total_goals_model,
                calibrated_model=total_goals_calibrated_model,
                probability_fields=TOTAL_GOALS_PROBABILITY_FIELDS,
                side_labels=TOTAL_GOALS_SIDE_LABELS,
                align_probabilities=_align_total_goals_probabilities,
                market_type="total_goals",
            )
            if total_goals_score is not None:
                scores.append(total_goals_score)
        return scores

    return score


def _score_market(
    row: dict[str, str],
    *,
    model,
    calibrated_model=None,
    probability_fields: tuple[str, str],
    side_labels: tuple[str, str],
    align_probabilities,
    market_type: str,
) -> PaperQueueScore | None:
    market_probabilities = _market_probabilities(row, probability_fields)
    if market_probabilities is None:
        return None
    probabilities = model.predict_proba(_matrix([row], FEATURES))
    classes = list(model.named_steps["classifier"].classes_)
    probability_row = align_probabilities(probabilities, classes)[0]
    side_index = max(
        range(len(side_labels)),
        key=lambda index: Decimal(str(probability_row[index])) - market_probabilities[index],
    )
    model_probability = _quantize(Decimal(str(probability_row[side_index])))
    market_probability = _quantize(market_probabilities[side_index])
    calibrated_side = None
    calibrated_edge = None
    if calibrated_model is not None:
        calibrated_probabilities = calibrated_model.predict_proba(_matrix([row], FEATURES))
        calibrated_classes = list(calibrated_model.classes_)
        calibrated_probability_row = align_probabilities(calibrated_probabilities, calibrated_classes)[0]
        calibrated_edges = [
            Decimal(str(calibrated_probability_row[index])) - market_probabilities[index]
            for index in range(len(side_labels))
        ]
        calibrated_index = max(range(len(side_labels)), key=lambda index: calibrated_edges[index])
        calibrated_side = side_labels[calibrated_index]
        calibrated_edge = _quantize(calibrated_edges[side_index])
    return PaperQueueScore(
        market_type=market_type,
        side=side_labels[side_index],
        model_probability=model_probability,
        market_probability=market_probability,
        edge=_quantize(model_probability - market_probability),
        model_name="raw_hgb_team_form_plus_all_markets",
        calibrated_side=calibrated_side,
        calibrated_edge=calibrated_edge,
    )


def _line_bucket(line: Decimal | None) -> str:
    if line is None:
        return "unknown"
    if line > 0:
        return "away_favorite"
    if line == 0:
        return "pickem"
    return "away_underdog"


def _home_line_bucket(line: Decimal | None) -> str:
    if line is None:
        return "unknown"
    if line < 0:
        return "home_favorite"
    if line == 0:
        return "pickem"
    return "home_underdog"


def _home_line_bucket_from_away_bucket(line_bucket: str) -> str:
    mapping = {
        "away_favorite": "home_underdog",
        "away_underdog": "home_favorite",
        "pickem": "pickem",
    }
    return mapping.get(line_bucket, "unknown")


def _recommended_handicap(side: str | None, line: Decimal | None) -> str | None:
    if side is None or line is None:
        return None
    if side == "home_cover":
        return f"主队 {_format_signed_line(line)}"
    if side == "away_cover":
        return f"客队 {_format_signed_line(-line)}"
    return None


def _recommended_for_market(
    market_type: str,
    side: str | None,
    line: Decimal | None,
) -> str | None:
    if market_type == "total_goals":
        return _recommended_total_goals(side, line)
    return _recommended_handicap(side, line)


def _recommended_total_goals(side: str | None, line: Decimal | None) -> str | None:
    if side is None or line is None:
        return None
    if side == "over":
        return f"大 {_format_optional(line)}"
    if side == "under":
        return f"小 {_format_optional(line)}"
    return None


def _format_signed_line(value: Decimal) -> str:
    if value > 0:
        return f"+{_format_optional(value)}"
    return _format_optional(value)


def _risk_tags(line_bucket: str, feature_row: dict[str, str]) -> tuple[str, ...]:
    tags = []
    if any(
        not feature_row.get(field)
        for field in (
            "match_winner_home_implied_probability",
            "match_winner_draw_implied_probability",
            "match_winner_away_implied_probability",
        )
    ):
        tags.append("missing_match_winner_live_odds")
    if line_bucket != "unknown":
        tags.append(f"line_bucket:{line_bucket}")
    return tuple(tags)


def _has_candidate_fresh_odds(
    match: Match,
    *,
    historical_snapshots: list[HistoricalOddsSnapshot] | None = None,
) -> bool:
    return _has_fresh_market_odds(
        match,
        market_type="asian_handicap",
        historical_snapshots=historical_snapshots,
    )


def _has_allowed_candidate_odds_status(
    match: Match,
    *,
    historical_snapshots: list[HistoricalOddsSnapshot] | None = None,
) -> bool:
    if historical_snapshots:
        if match.status == "scheduled":
            return _has_complete_historical_odds_market_pair(
                historical_snapshots,
                market_type="asian_handicap",
            )
        return _has_complete_historical_odds(match, historical_snapshots)
    latest_captured_at = max(
        (
            snapshot.captured_at
            for snapshot in match.odds_snapshots
            if _snapshot_has_market_odds(snapshot, market_type="asian_handicap")
        ),
        default=None,
    )
    if latest_captured_at is None:
        return False
    lead_time = _naive_datetime(match.kickoff_time) - _naive_datetime(latest_captured_at)
    return MIN_CANDIDATE_ODDS_LEAD_TIME <= lead_time <= MAX_CANDIDATE_ODDS_LEAD_TIME


def _has_complete_historical_odds_market_pair(
    snapshots: list[HistoricalOddsSnapshot],
    *,
    market_type: str,
) -> bool:
    pair = _historical_market_pair(snapshots, market_type=market_type)
    if pair is None:
        return False
    sides = set(pair[1])
    required_sides = COMPLETE_HISTORICAL_ODDS_REQUIRED_MARKETS.get(market_type, set())
    return required_sides.issubset(sides)


def _has_complete_historical_odds(
    match: Match,
    snapshots: list[HistoricalOddsSnapshot],
) -> bool:
    kickoff_utc = _as_utc(match.kickoff_time)
    relevant = [
        snapshot
        for snapshot in snapshots
        if snapshot.source_name == ODDSPAPI_SOURCE_NAME
        and kickoff_utc - timedelta(hours=24)
        <= _historical_snapshot_as_utc(snapshot.snapshot_time)
        <= kickoff_utc
    ]
    if len(relevant) < COMPLETE_HISTORICAL_ODDS_24H_SNAPSHOT_COUNT:
        return False
    close_window_start = kickoff_utc - COMPLETE_HISTORICAL_ODDS_CLOSE_WINDOW
    sides_by_market: dict[str, set[str]] = {}
    for snapshot in relevant:
        snapshot_utc = _historical_snapshot_as_utc(snapshot.snapshot_time)
        if close_window_start <= snapshot_utc <= kickoff_utc:
            sides_by_market.setdefault(snapshot.market_type, set()).add(snapshot.outcome_side)
    return all(
        required_sides.issubset(sides_by_market.get(market_type, set()))
        for market_type, required_sides in COMPLETE_HISTORICAL_ODDS_REQUIRED_MARKETS.items()
    )


def _has_fresh_market_odds(
    match: Match,
    *,
    market_type: str,
    historical_snapshots: list[HistoricalOddsSnapshot] | None = None,
) -> bool:
    if historical_snapshots:
        return _historical_market_pair(historical_snapshots, market_type=market_type) is not None
    latest_captured_at = max(
        (
            snapshot.captured_at
            for snapshot in match.odds_snapshots
            if _snapshot_has_market_odds(snapshot, market_type=market_type)
        ),
        default=None,
    )
    if latest_captured_at is None:
        return False
    lead_time = _naive_datetime(match.kickoff_time) - _naive_datetime(latest_captured_at)
    return timedelta(0) <= lead_time <= MAX_CANDIDATE_ODDS_LEAD_TIME


def _snapshot_has_market_odds(snapshot, *, market_type: str) -> bool:
    if market_type == "total_goals":
        return (
            snapshot.total_line is not None
            and snapshot.over_odds is not None
            and snapshot.under_odds is not None
        )
    return (
        snapshot.asian_handicap is not None
        and snapshot.home_odds is not None
        and snapshot.away_odds is not None
    )


def _total_line_bucket(line: Decimal | None) -> str:
    if line is None:
        return "unknown"
    if line <= Decimal("2.25"):
        return "low_<=2.25"
    if line == Decimal("2.50"):
        return "mid_2.50"
    if line == Decimal("2.75"):
        return "mid_2.75"
    return "high_>=3.00"


def _normalize_prefetch_result(result: dict[str, Any] | object) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    return {
        "created": getattr(result, "created_odds_snapshots", None),
        "skipped": getattr(result, "skipped_odds_snapshots", None),
        "failed_fixture_id": getattr(result, "failed_fixture_id", None),
        "error_message": getattr(result, "error_message", None),
    }


def _count_statuses(rows: list[PaperQueueRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
    return counts


def _format_decimal(value: Decimal | None, quant: Decimal) -> str:
    if value is None:
        return ""
    return str(value.quantize(quant, rounding=ROUND_HALF_UP))


def _implied_probability(odds: Decimal | None) -> str:
    if odds is None or odds <= 0:
        return ""
    return str((Decimal("1") / odds).quantize(METRIC_QUANT, rounding=ROUND_HALF_UP))


def _overround(
    first_odds: Decimal | None,
    second_odds: Decimal | None,
    third_odds: Decimal | None = None,
) -> str:
    first = _decimal_or_none(_implied_probability(first_odds))
    second = _decimal_or_none(_implied_probability(second_odds))
    if first is None or second is None:
        return ""
    third = _decimal_or_none(_implied_probability(third_odds)) if third_odds is not None else None
    total = first + second + (third or Decimal("0"))
    return str(total.quantize(METRIC_QUANT, rounding=ROUND_HALF_UP))


def _ratio(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.0000"
    return str((Decimal(numerator) / Decimal(denominator)).quantize(METRIC_QUANT, rounding=ROUND_HALF_UP))


def _rest_days(previous: datetime | None, kickoff: datetime) -> str:
    if previous is None:
        return ""
    days = Decimal(str((_naive_datetime(kickoff) - _naive_datetime(previous)).total_seconds() / 86400))
    return str(days.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP))


def _naive_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=None)


def _format_beijing_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        return value.isoformat()
    return value.astimezone(ZoneInfo(BEIJING_TIMEZONE)).isoformat()


def _decimal_from_row(row: dict[str, str], field: str) -> Decimal | None:
    return _decimal_or_none(row.get(field, ""))


def _decimal_or_none(value: str) -> Decimal | None:
    if value == "":
        return None
    return Decimal(value)


def _as_decimal(value: str) -> Decimal:
    return Decimal(value).quantize(METRIC_QUANT, rounding=ROUND_HALF_UP)


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(METRIC_QUANT, rounding=ROUND_HALF_UP)


def _format_optional(value: Decimal | None) -> str:
    return "-" if value is None else str(value)

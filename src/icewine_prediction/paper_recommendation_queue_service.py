from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Callable, Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, joinedload

from icewine_prediction.baseline_edge_backtest_service import (
    FEATURES,
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
from icewine_prediction.feature_service import build_match_odds_features
from icewine_prediction.models import League, Match, TrainingRun
from icewine_prediction.paper_strategy_registry import (
    BUCKET_V2_STRATEGY,
    DEFAULT_STRATEGY,
    TOTAL_GOALS_BUCKET_V2_STRATEGY,
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


@dataclass(frozen=True)
class PaperQueueScore:
    side: str
    model_probability: Decimal
    market_probability: Decimal
    edge: Decimal
    model_name: str
    market_type: str = "asian_handicap"


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


def build_paper_recommendation_queue(
    session: Session,
    *,
    now: datetime,
    hours: int = 72,
    near_start_hours: int = 6,
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
    model_scorer = scorer or _train_live_scorer(resolved_feature_csv_path)
    rows = [
        row
        for match in _list_upcoming_matches(session, now=now, hours=hours)
        for row in _build_queue_rows(
            match,
            scorer=model_scorer,
            edge_threshold=threshold,
            display_name_service=display_name_service,
        )
    ]
    status_counts = _count_statuses(rows)
    return PaperRecommendationQueueReport(
        generated_at=_format_beijing_datetime(now),
        window_start=_format_beijing_datetime(now),
        window_end=_format_beijing_datetime(now + timedelta(hours=hours)),
        hours=hours,
        near_start_hours=near_start_hours,
        edge_threshold=threshold,
        model_name="raw_hgb_team_form_plus_all_markets",
        total_matches=len(rows),
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


def _list_upcoming_matches(session: Session, *, now: datetime, hours: int) -> list[Match]:
    return (
        session.query(Match)
        .options(
            joinedload(Match.league).joinedload(League.matches),
            joinedload(Match.home_team),
            joinedload(Match.away_team),
            joinedload(Match.odds_snapshots),
        )
        .filter(Match.status == "scheduled")
        .filter(Match.kickoff_time >= now)
        .filter(Match.kickoff_time <= now + timedelta(hours=hours))
        .order_by(Match.kickoff_time.asc(), Match.id.asc())
        .all()
    )


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
) -> list[PaperQueueRow]:
    feature_row = _live_feature_row(match)
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
            )
        )
    elif not _has_candidate_fresh_odds(match):
        diagnostic_rows.append(
            _row(
                match,
                status="stale_odds",
                line=asian_line,
                odds=asian_odds,
                feature_row=feature_row,
                display_name_service=display_name_service,
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
        )
        if scored is None:
            continue
        rows.append(scored)
        rows.extend(row for row in (_bucket_strategy_row(scored),) if row is not None)
    return rows or diagnostic_rows


def _scored_row(
    match: Match,
    *,
    score: PaperQueueScore,
    edge_threshold: Decimal,
    feature_row: dict[str, str],
    display_name_service: DisplayNameService | None,
) -> PaperQueueRow | None:
    if score.market_type == "total_goals":
        line = _decimal_from_row(feature_row, "total_goals_close_line")
        if line is None or not _has_fresh_market_odds(match, market_type="total_goals"):
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
        feature_row=feature_row,
        display_name_service=display_name_service,
    )


def _bucket_strategy_row(row: PaperQueueRow) -> PaperQueueRow | None:
    if row.market_type == "total_goals":
        return _total_goals_bucket_v2_row(row)
    return _v2_row(row)


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


def _total_goals_bucket_v2_row(row: PaperQueueRow) -> PaperQueueRow | None:
    if row.market_type != "total_goals" or row.side is None or row.edge is None:
        return None
    bucket_thresholds = TOTAL_GOALS_BUCKET_V2_STRATEGY.line_bucket_thresholds or {}
    threshold = bucket_thresholds.get(f"{row.side}@{row.line_bucket}")
    if threshold is None or row.edge < threshold:
        return None
    return PaperQueueRow(
        **{
            **row.__dict__,
            "status": "candidate",
            "risk_tags": (
                *row.risk_tags,
                *(
                    (TOTAL_GOALS_BUCKET_V2_STRATEGY.risk_tag,)
                    if TOTAL_GOALS_BUCKET_V2_STRATEGY.risk_tag is not None
                    else ()
                ),
            ),
            "strategy_key": TOTAL_GOALS_BUCKET_V2_STRATEGY.strategy_key,
            "strategy_display_name": TOTAL_GOALS_BUCKET_V2_STRATEGY.display_name,
            "signal_version": TOTAL_GOALS_BUCKET_V2_STRATEGY.signal_version,
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
        if _total_goals_bucket_threshold(score, line_bucket=line_bucket) is None:
            return "unsupported_bucket"
        if score.edge < edge_threshold:
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
    bucket_thresholds = TOTAL_GOALS_BUCKET_V2_STRATEGY.line_bucket_thresholds or {}
    return bucket_thresholds.get(f"{score.side}@{line_bucket}")


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
    feature_row: dict[str, str] | None = None,
    display_name_service: DisplayNameService | None = None,
) -> PaperQueueRow:
    display_name_service = display_name_service or DisplayNameService()
    line_bucket = line_bucket or (_total_line_bucket(line) if market_type == "total_goals" else _line_bucket(line))
    risk_tags = _risk_tags(line_bucket, feature_row or {})
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
    )


def _live_feature_row(match: Match) -> dict[str, str]:
    odds_features = build_match_odds_features(match)
    home_state = _team_prior_state(match, side="home")
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
    total_goals_model = None
    if total_goals_train_rows:
        total_goals_model = _raw_model()
        total_goals_model.fit(
            _matrix(total_goals_train_rows, FEATURES),
            [_total_goals_target_label(row) for row in total_goals_train_rows],
        )

    def score(row: dict[str, str]) -> list[PaperQueueScore]:
        scores = []
        asian_handicap_score = _score_market(
            row,
            model=asian_handicap_model,
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
    return PaperQueueScore(
        market_type=market_type,
        side=side_labels[side_index],
        model_probability=model_probability,
        market_probability=market_probability,
        edge=_quantize(model_probability - market_probability),
        model_name="raw_hgb_team_form_plus_all_markets",
    )


def _line_bucket(line: Decimal | None) -> str:
    if line is None:
        return "unknown"
    if line > 0:
        return "away_favorite"
    if line == 0:
        return "pickem"
    return "away_underdog"


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


def _has_candidate_fresh_odds(match: Match) -> bool:
    return _has_fresh_market_odds(match, market_type="asian_handicap")


def _has_fresh_market_odds(match: Match, *, market_type: str) -> bool:
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

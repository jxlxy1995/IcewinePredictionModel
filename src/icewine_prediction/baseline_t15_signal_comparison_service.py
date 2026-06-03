from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy.orm import Session, joinedload

from icewine_prediction.baseline_recommendation_sandbox_service import (
    SandboxCandidate,
    _format_optional,
    _quantize,
)
from icewine_prediction.historical_training_sample_service import (
    _PairedMarketSnapshot,
    _comparable_datetime,
    _pair_market_snapshots,
)
from icewine_prediction.models import HistoricalOddsSnapshot, Match
from icewine_prediction.oddspapi_sync_runner import ODDSPAPI_SOURCE_NAME
from icewine_prediction.paper_recommendation_queue_service import (
    DEFAULT_FEATURE_CSV_PATH,
    PaperQueueScore,
    _home_line_bucket,
    _line_bucket,
    _total_line_bucket,
    train_paper_queue_scorer_from_rows,
)
from icewine_prediction.paper_strategy_registry import (
    STRATEGIES,
    TOTAL_GOALS_HGB_CONFIRMED_UNDER_MID_275_V1_KEY,
    PaperStrategy,
)
from icewine_prediction.settlement_service import settle_asian_handicap, settle_total_goals


METRIC_QUANT = Decimal("0.0001")
ODDS_QUANT = Decimal("0.000")
LINE_QUANT = Decimal("0.00")
DEFAULT_BOOKMAKER = "pinnacle"
T15_TARGET_MINUTES = 15
T15_TOLERANCE_MINUTES = 5


@dataclass(frozen=True)
class T15SignalComparisonCandidateSet:
    strategy_key: str
    display_name: str
    close_candidates: list[SandboxCandidate]
    t15_candidates: list[SandboxCandidate]


@dataclass(frozen=True)
class T15SignalComparisonStrategySummary:
    strategy_key: str
    display_name: str
    close_count: int
    t15_count: int
    overlap_count: int
    close_only_count: int
    t15_only_count: int
    close_profit: Decimal
    t15_profit: Decimal
    close_roi: Decimal | None
    t15_roi: Decimal | None
    overlap_share: Decimal | None


@dataclass(frozen=True)
class BaselineT15SignalComparisonReport:
    csv_path: Path
    row_count: int
    train_rows: int
    validation_rows: int
    t15_available_rows: int
    missing_t15_rows: int
    source_name: str
    bookmaker: str
    target_minutes_before_kickoff: int
    tolerance_minutes: int
    strategy_summaries: list[T15SignalComparisonStrategySummary]
    candidate_sets: list[T15SignalComparisonCandidateSet]


def build_baseline_t15_signal_comparison_report(
    session: Session,
    csv_path: Path = DEFAULT_FEATURE_CSV_PATH,
    *,
    source_name: str = ODDSPAPI_SOURCE_NAME,
    bookmaker: str = DEFAULT_BOOKMAKER,
    target_minutes_before_kickoff: int = T15_TARGET_MINUTES,
    tolerance_minutes: int = T15_TOLERANCE_MINUTES,
) -> BaselineT15SignalComparisonReport:
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = sorted(
            list(csv.DictReader(file)),
            key=lambda row: (row.get("kickoff_time", ""), row.get("match_id", "")),
        )
    train_rows = [row for row in rows if row.get("split") == "train"]
    validation_rows = [row for row in rows if row.get("split") == "validation"]
    if not train_rows or not validation_rows:
        raise ValueError("T-15 signal comparison requires both train and validation rows")

    scorer = train_paper_queue_scorer_from_rows(train_rows)
    matches_by_id = _load_matches_by_id(session, _row_match_ids(validation_rows))
    snapshots_by_match_id = _load_snapshots_by_match_id(
        session,
        match_ids=list(matches_by_id),
        source_name=source_name,
        bookmaker=bookmaker,
    )

    close_candidates_by_strategy = _candidates_by_strategy(validation_rows, scorer)
    t15_rows = []
    missing_t15_rows = 0
    for row in validation_rows:
        match = matches_by_id.get(_match_id_from_row(row))
        if match is None:
            missing_t15_rows += 1
            continue
        patched_row = _patch_row_with_t15_markets(
            row,
            match=match,
            snapshots=snapshots_by_match_id.get(match.id, []),
            target_minutes_before_kickoff=target_minutes_before_kickoff,
            tolerance_minutes=tolerance_minutes,
        )
        if patched_row is None:
            missing_t15_rows += 1
            continue
        t15_rows.append(patched_row)

    t15_candidates_by_strategy = _candidates_by_strategy(t15_rows, scorer)
    candidate_sets = [
        T15SignalComparisonCandidateSet(
            strategy_key=strategy.strategy_key,
            display_name=strategy.display_name,
            close_candidates=close_candidates_by_strategy.get(strategy.strategy_key, []),
            t15_candidates=t15_candidates_by_strategy.get(strategy.strategy_key, []),
        )
        for strategy in STRATEGIES
    ]
    return BaselineT15SignalComparisonReport(
        csv_path=csv_path,
        row_count=len(rows),
        train_rows=len(train_rows),
        validation_rows=len(validation_rows),
        t15_available_rows=len(t15_rows),
        missing_t15_rows=missing_t15_rows,
        source_name=source_name,
        bookmaker=bookmaker,
        target_minutes_before_kickoff=target_minutes_before_kickoff,
        tolerance_minutes=tolerance_minutes,
        strategy_summaries=[_candidate_set_summary(candidate_set) for candidate_set in candidate_sets],
        candidate_sets=candidate_sets,
    )


def write_baseline_t15_signal_comparison_report(
    report: BaselineT15SignalComparisonReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_baseline_t15_signal_comparison_report(report) + "\n",
        encoding="utf-8",
    )


def format_baseline_t15_signal_comparison_report(
    report: BaselineT15SignalComparisonReport,
) -> str:
    lines = [
        "# Baseline T-15 Signal Comparison",
        "",
        f"- Feature CSV: `{report.csv_path}`",
        f"- Historical odds: `{report.source_name}` / `{report.bookmaker}`",
        (
            f"- T-15 window: target `{report.target_minutes_before_kickoff}` minutes, "
            f"tolerance `+/-{report.tolerance_minutes}` minutes"
        ),
        "",
        "## Data Coverage",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Rows | {report.row_count} |",
        f"| Train rows | {report.train_rows} |",
        f"| Validation rows | {report.validation_rows} |",
        f"| T-15 available rows | {report.t15_available_rows} |",
        f"| Missing T-15 rows | {report.missing_t15_rows} |",
        "",
        "## Strategy Comparison",
        "",
        (
            "| Strategy | Close bets | T-15 bets | Overlap | Close-only | T15-only | "
            "Close profit | T-15 profit | Close ROI | T-15 ROI | Overlap share |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in report.strategy_summaries:
        lines.append(
            f"| `{summary.strategy_key}` | {summary.close_count} | {summary.t15_count} | "
            f"{summary.overlap_count} | {summary.close_only_count} | {summary.t15_only_count} | "
            f"{summary.close_profit} | {summary.t15_profit} | "
            f"{_format_optional(summary.close_roi)} | {_format_optional(summary.t15_roi)} | "
            f"{_format_optional(summary.overlap_share)} |"
        )
    return "\n".join(lines)


def _candidate_set_summary(
    candidate_set: T15SignalComparisonCandidateSet,
) -> T15SignalComparisonStrategySummary:
    close_keys = {_candidate_key(candidate) for candidate in candidate_set.close_candidates}
    t15_keys = {_candidate_key(candidate) for candidate in candidate_set.t15_candidates}
    close_profit = _candidate_profit(candidate_set.close_candidates)
    t15_profit = _candidate_profit(candidate_set.t15_candidates)
    overlap_count = len(close_keys & t15_keys)
    return T15SignalComparisonStrategySummary(
        strategy_key=candidate_set.strategy_key,
        display_name=candidate_set.display_name,
        close_count=len(candidate_set.close_candidates),
        t15_count=len(candidate_set.t15_candidates),
        overlap_count=overlap_count,
        close_only_count=len(close_keys - t15_keys),
        t15_only_count=len(t15_keys - close_keys),
        close_profit=close_profit,
        t15_profit=t15_profit,
        close_roi=_ratio(close_profit, len(candidate_set.close_candidates)),
        t15_roi=_ratio(t15_profit, len(candidate_set.t15_candidates)),
        overlap_share=_ratio(Decimal(overlap_count), len(close_keys)) if close_keys else None,
    )


def _select_t15_pair(
    pairs: list[_PairedMarketSnapshot],
    *,
    kickoff_time: datetime,
    target_minutes_before_kickoff: int = T15_TARGET_MINUTES,
    tolerance_minutes: int = T15_TOLERANCE_MINUTES,
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


def _candidates_by_strategy(
    rows: list[dict[str, str]],
    scorer,
) -> dict[str, list[SandboxCandidate]]:
    candidates: dict[str, list[SandboxCandidate]] = defaultdict(list)
    for row in rows:
        for score in scorer(row) or []:
            for strategy in STRATEGIES:
                if _strategy_accepts_score(strategy, score, row):
                    candidate = _candidate_from_score(row, score)
                    if candidate is not None:
                        candidates[strategy.strategy_key].append(candidate)
    for strategy_candidates in candidates.values():
        strategy_candidates.sort(
            key=lambda candidate: (-candidate.edge, candidate.kickoff_time, candidate.match_id)
        )
    return dict(candidates)


def _strategy_accepts_score(
    strategy: PaperStrategy,
    score: PaperQueueScore,
    row: dict[str, str],
) -> bool:
    if score.market_type != strategy.market_type:
        return False
    if strategy.side is not None and score.side != strategy.side:
        return False
    threshold = strategy.edge_threshold
    if strategy.line_bucket_thresholds is not None:
        bucket_key = _strategy_bucket_key(strategy, score, row)
        if bucket_key not in strategy.line_bucket_thresholds:
            return False
        threshold = strategy.line_bucket_thresholds[bucket_key]
    if score.edge < threshold:
        return False
    if strategy.strategy_key == TOTAL_GOALS_HGB_CONFIRMED_UNDER_MID_275_V1_KEY:
        return score.calibrated_side == "under" and (
            score.calibrated_edge is not None and score.calibrated_edge >= Decimal("0.0000")
        )
    return True


def _strategy_bucket_key(
    strategy: PaperStrategy,
    score: PaperQueueScore,
    row: dict[str, str],
) -> str:
    line = _market_line(row, score.market_type)
    if score.market_type == "total_goals":
        return f"{score.side}@{_total_line_bucket(line)}"
    if score.side == "home_cover":
        return _home_line_bucket(line)
    return _line_bucket(line)


def _candidate_from_score(row: dict[str, str], score: PaperQueueScore) -> SandboxCandidate | None:
    odds = _side_odds(row, score.market_type, score.side)
    line = _market_line(row, score.market_type)
    profit = _profit_for_side(row, score.market_type, score.side, odds)
    if odds is None or odds <= Decimal("1.0") or profit is None:
        return None
    return SandboxCandidate(
        match_id=row.get("match_id", ""),
        kickoff_time=row.get("kickoff_time", ""),
        league_name=row.get("league_name", ""),
        home_team_name=row.get("home_team_name", ""),
        away_team_name=row.get("away_team_name", ""),
        market_type=score.market_type,
        line=line,
        side=score.side,
        odds=odds,
        model_probability=score.model_probability,
        market_probability=score.market_probability,
        edge=score.edge,
        actual_side=_actual_side_label(row, score.market_type),
        profit=profit,
    )


def _patch_row_with_t15_markets(
    row: dict[str, str],
    *,
    match: Match,
    snapshots: list[HistoricalOddsSnapshot],
    target_minutes_before_kickoff: int,
    tolerance_minutes: int,
) -> dict[str, str] | None:
    patched = dict(row)
    had_strategy_market = False
    for market_type in ("asian_handicap", "total_goals", "match_winner"):
        pairs = _pair_market_snapshots(
            [snapshot for snapshot in snapshots if snapshot.market_type == market_type],
            market_type=market_type,
        )
        pair = _select_t15_pair(
            pairs,
            kickoff_time=_match_snapshot_timeline_kickoff_time(match),
            target_minutes_before_kickoff=target_minutes_before_kickoff,
            tolerance_minutes=tolerance_minutes,
        )
        if pair is None:
            _clear_market_fields(patched, market_type)
            continue
        _patch_market_fields(patched, match=match, pair=pair)
        if market_type in {"asian_handicap", "total_goals"}:
            had_strategy_market = True
    return patched if had_strategy_market else None


def _patch_market_fields(
    row: dict[str, str],
    *,
    match: Match,
    pair: _PairedMarketSnapshot,
) -> None:
    if pair.market_type == "asian_handicap":
        row["asian_handicap_close_line"] = _format_line(pair.market_line)
        row["asian_handicap_home_odds"] = _format_odds(pair.side_a_odds)
        row["asian_handicap_away_odds"] = _format_odds(pair.side_b_odds)
        row["asian_handicap_home_implied_probability"] = _format_probability(_implied(pair.side_a_odds))
        row["asian_handicap_away_implied_probability"] = _format_probability(_implied(pair.side_b_odds))
        row["asian_handicap_overround"] = _format_probability(
            _implied(pair.side_a_odds) + _implied(pair.side_b_odds)
        )
        row["target_asian_handicap_home_result"] = settle_asian_handicap(
            match.home_score,
            match.away_score,
            pair.market_line,
            "home",
        )
        row["target_asian_handicap_away_result"] = settle_asian_handicap(
            match.home_score,
            match.away_score,
            pair.market_line,
            "away",
        )
        return
    if pair.market_type == "total_goals":
        row["total_goals_close_line"] = _format_line(pair.market_line)
        row["total_goals_over_odds"] = _format_odds(pair.side_a_odds)
        row["total_goals_under_odds"] = _format_odds(pair.side_b_odds)
        row["total_goals_over_implied_probability"] = _format_probability(_implied(pair.side_a_odds))
        row["total_goals_under_implied_probability"] = _format_probability(_implied(pair.side_b_odds))
        row["total_goals_overround"] = _format_probability(
            _implied(pair.side_a_odds) + _implied(pair.side_b_odds)
        )
        row["target_total_goals_over_result"] = settle_total_goals(
            match.home_score,
            match.away_score,
            pair.market_line,
            "over",
        )
        row["target_total_goals_under_result"] = settle_total_goals(
            match.home_score,
            match.away_score,
            pair.market_line,
            "under",
        )
        return
    if pair.market_type == "match_winner" and pair.side_c_odds is not None:
        row["match_winner_home_implied_probability"] = _format_probability(_implied(pair.side_a_odds))
        row["match_winner_draw_implied_probability"] = _format_probability(_implied(pair.side_b_odds))
        row["match_winner_away_implied_probability"] = _format_probability(_implied(pair.side_c_odds))
        row["match_winner_overround"] = _format_probability(
            _implied(pair.side_a_odds) + _implied(pair.side_b_odds) + _implied(pair.side_c_odds)
        )


def _clear_market_fields(row: dict[str, str], market_type: str) -> None:
    fields = {
        "asian_handicap": (
            "asian_handicap_close_line",
            "asian_handicap_home_odds",
            "asian_handicap_away_odds",
            "asian_handicap_home_implied_probability",
            "asian_handicap_away_implied_probability",
            "asian_handicap_overround",
            "target_asian_handicap_home_result",
            "target_asian_handicap_away_result",
        ),
        "total_goals": (
            "total_goals_close_line",
            "total_goals_over_odds",
            "total_goals_under_odds",
            "total_goals_over_implied_probability",
            "total_goals_under_implied_probability",
            "total_goals_overround",
            "target_total_goals_over_result",
            "target_total_goals_under_result",
        ),
        "match_winner": (
            "match_winner_home_implied_probability",
            "match_winner_draw_implied_probability",
            "match_winner_away_implied_probability",
            "match_winner_overround",
        ),
    }[market_type]
    for field in fields:
        row[field] = ""


def _profit_for_side(
    row: dict[str, str],
    market_type: str,
    side: str,
    odds: Decimal | None,
) -> Decimal | None:
    if odds is None:
        return None
    result = _settlement_result(row, market_type, side)
    if result == "win":
        return _quantize(odds - Decimal("1"))
    if result == "half_win":
        return _quantize((odds - Decimal("1")) / Decimal("2"))
    if result == "push":
        return Decimal("0.0000")
    if result == "half_loss":
        return Decimal("-0.5000")
    if result == "loss":
        return Decimal("-1.0000")
    return None


def _settlement_result(row: dict[str, str], market_type: str, side: str) -> str:
    if market_type == "asian_handicap":
        field = (
            "target_asian_handicap_home_result"
            if side == "home_cover"
            else "target_asian_handicap_away_result"
        )
        return row.get(field, "")
    if market_type == "total_goals":
        field = "target_total_goals_over_result" if side == "over" else "target_total_goals_under_result"
        return row.get(field, "")
    return ""


def _actual_side_label(row: dict[str, str], market_type: str) -> str:
    if market_type == "asian_handicap":
        home_result = row.get("target_asian_handicap_home_result", "")
        away_result = row.get("target_asian_handicap_away_result", "")
        if home_result == "win" and away_result == "loss":
            return "home_cover"
        if home_result == "loss" and away_result == "win":
            return "away_cover"
        return f"home:{home_result}/away:{away_result}"
    over_result = row.get("target_total_goals_over_result", "")
    under_result = row.get("target_total_goals_under_result", "")
    if over_result == "win" and under_result == "loss":
        return "over"
    if over_result == "loss" and under_result == "win":
        return "under"
    return f"over:{over_result}/under:{under_result}"


def _side_odds(row: dict[str, str], market_type: str, side: str) -> Decimal | None:
    field_by_side = {
        ("asian_handicap", "home_cover"): "asian_handicap_home_odds",
        ("asian_handicap", "away_cover"): "asian_handicap_away_odds",
        ("total_goals", "over"): "total_goals_over_odds",
        ("total_goals", "under"): "total_goals_under_odds",
    }
    value = row.get(field_by_side[(market_type, side)], "")
    return Decimal(value) if value else None


def _market_line(row: dict[str, str], market_type: str) -> Decimal | None:
    field = "total_goals_close_line" if market_type == "total_goals" else "asian_handicap_close_line"
    value = row.get(field, "")
    return Decimal(value) if value else None


def _load_matches_by_id(session: Session, match_ids: list[int]) -> dict[int, Match]:
    if not match_ids:
        return {}
    matches = (
        session.query(Match)
        .options(joinedload(Match.league), joinedload(Match.home_team), joinedload(Match.away_team))
        .filter(Match.id.in_(match_ids))
        .all()
    )
    return {match.id: match for match in matches if match.home_score is not None and match.away_score is not None}


def _match_snapshot_timeline_kickoff_time(match: Match) -> datetime:
    if match.fixture_timestamp is not None:
        return datetime.fromtimestamp(match.fixture_timestamp, timezone.utc).replace(tzinfo=None)
    return _comparable_datetime(match.kickoff_time)


def _load_snapshots_by_match_id(
    session: Session,
    *,
    match_ids: list[int],
    source_name: str,
    bookmaker: str,
) -> dict[int, list[HistoricalOddsSnapshot]]:
    if not match_ids:
        return {}
    snapshots = (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id.in_(match_ids))
        .filter(HistoricalOddsSnapshot.source_name == source_name)
        .filter(HistoricalOddsSnapshot.bookmaker == bookmaker)
        .order_by(HistoricalOddsSnapshot.snapshot_time.asc())
        .all()
    )
    by_match_id: dict[int, list[HistoricalOddsSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        by_match_id[snapshot.match_id].append(snapshot)
    return dict(by_match_id)


def _row_match_ids(rows: list[dict[str, str]]) -> list[int]:
    return [match_id for row in rows if (match_id := _match_id_from_row(row)) is not None]


def _match_id_from_row(row: dict[str, str]) -> int | None:
    value = row.get("match_id", "")
    if not value:
        return None
    return int(value)


def _candidate_key(candidate: SandboxCandidate) -> tuple[str, str, str]:
    return (candidate.match_id, candidate.market_type, candidate.side)


def _candidate_profit(candidates: list[SandboxCandidate]) -> Decimal:
    return _quantize(sum((candidate.profit for candidate in candidates), Decimal("0")))


def _ratio(numerator: Decimal, denominator: int) -> Decimal | None:
    if denominator <= 0:
        return None
    return (numerator / Decimal(denominator)).quantize(METRIC_QUANT, rounding=ROUND_HALF_UP)


def _implied(odds: Decimal) -> Decimal:
    return Decimal("1") / odds


def _format_probability(value: Decimal) -> str:
    return str(value.quantize(METRIC_QUANT, rounding=ROUND_HALF_UP))


def _format_odds(value: Decimal) -> str:
    return str(value.quantize(ODDS_QUANT, rounding=ROUND_HALF_UP))


def _format_line(value: Decimal) -> str:
    return str(value.quantize(LINE_QUANT, rounding=ROUND_HALF_UP))

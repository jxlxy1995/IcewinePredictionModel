from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy.orm import Session

from icewine_prediction.baseline_recommendation_sandbox_service import _format_optional, _quantize
from icewine_prediction.baseline_t15_signal_comparison_service import (
    DEFAULT_BOOKMAKER,
    _load_matches_by_id,
    _load_snapshots_by_match_id,
    _match_id_from_row,
    _row_match_ids,
)
from icewine_prediction.display_service import DisplayNameService
from icewine_prediction.oddspapi_sync_runner import ODDSPAPI_SOURCE_NAME
from icewine_prediction.paper_recommendation_queue_service import (
    DEFAULT_FEATURE_CSV_PATH,
    PaperQueueRow,
    build_paper_recommendation_rows_for_match,
    train_paper_queue_scorer_from_rows,
    _team_prior_states_by_match,
)


METRIC_QUANT = Decimal("0.0001")


@dataclass(frozen=True)
class BookmakerReplayComparisonStrategySummary:
    strategy_key: str
    baseline_candidate_count: int
    candidate_candidate_count: int
    overlap_candidate_count: int
    baseline_only_candidate_count: int
    candidate_only_candidate_count: int
    baseline_profit: Decimal
    candidate_profit: Decimal
    baseline_roi: Decimal | None
    candidate_roi: Decimal | None
    overlap_baseline_profit: Decimal
    overlap_candidate_profit: Decimal
    overlap_avg_abs_line_diff: Decimal
    overlap_avg_abs_odds_diff: Decimal


@dataclass(frozen=True)
class BookmakerReplayComparisonReport:
    csv_path: Path
    row_count: int
    train_rows: int
    validation_rows: int
    source_name: str
    baseline_bookmaker: str
    candidate_bookmaker: str
    baseline_snapshot_match_count: int
    candidate_snapshot_match_count: int
    overlap_match_count: int
    baseline_candidate_count: int
    candidate_candidate_count: int
    overlap_candidate_count: int
    baseline_only_candidate_count: int
    candidate_only_candidate_count: int
    strategy_summaries: list[BookmakerReplayComparisonStrategySummary]


def build_bookmaker_replay_comparison_report(
    session: Session,
    csv_path: Path = DEFAULT_FEATURE_CSV_PATH,
    *,
    source_name: str = ODDSPAPI_SOURCE_NAME,
    baseline_bookmaker: str = DEFAULT_BOOKMAKER,
    candidate_bookmaker: str = "sbobet",
    edge_threshold: str = "0.10",
) -> BookmakerReplayComparisonReport:
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = sorted(
            list(csv.DictReader(file)),
            key=lambda row: (row.get("kickoff_time", ""), row.get("match_id", "")),
        )
    train_rows = [row for row in rows if row.get("split") == "train"]
    validation_rows = [row for row in rows if row.get("split") == "validation"]
    if not train_rows or not validation_rows:
        raise ValueError("bookmaker replay comparison requires both train and validation rows")

    scorer = train_paper_queue_scorer_from_rows(train_rows)
    matches_by_id = _load_matches_by_id(session, _row_match_ids(validation_rows))
    baseline_snapshots_by_match_id = _load_snapshots_by_match_id(
        session,
        match_ids=list(matches_by_id),
        source_name=source_name,
        bookmaker=baseline_bookmaker,
    )
    candidate_snapshots_by_match_id = _load_snapshots_by_match_id(
        session,
        match_ids=list(matches_by_id),
        source_name=source_name,
        bookmaker=candidate_bookmaker,
    )
    overlap_match_ids = sorted(
        set(baseline_snapshots_by_match_id).intersection(candidate_snapshots_by_match_id)
    )
    overlap_matches = [matches_by_id[match_id] for match_id in overlap_match_ids if match_id in matches_by_id]
    team_prior_states = _team_prior_states_by_match(session, overlap_matches)
    display_name_service = DisplayNameService()

    baseline_candidates = _collect_candidates(
        validation_rows,
        matches_by_id=matches_by_id,
        snapshots_by_match_id=baseline_snapshots_by_match_id,
        overlap_match_ids=set(overlap_match_ids),
        scorer=scorer,
        edge_threshold=edge_threshold,
        display_name_service=display_name_service,
        team_prior_states=team_prior_states,
    )
    candidate_candidates = _collect_candidates(
        validation_rows,
        matches_by_id=matches_by_id,
        snapshots_by_match_id=candidate_snapshots_by_match_id,
        overlap_match_ids=set(overlap_match_ids),
        scorer=scorer,
        edge_threshold=edge_threshold,
        display_name_service=display_name_service,
        team_prior_states=team_prior_states,
    )

    baseline_by_key = {_candidate_key(row): row for row in baseline_candidates}
    candidate_by_key = {_candidate_key(row): row for row in candidate_candidates}
    overlap_keys = set(baseline_by_key).intersection(candidate_by_key)
    strategy_keys = sorted(
        {row.strategy_key for row in baseline_candidates} | {row.strategy_key for row in candidate_candidates}
    )
    strategy_summaries = [
        _strategy_summary(
            strategy_key,
            baseline_candidates=[row for row in baseline_candidates if row.strategy_key == strategy_key],
            candidate_candidates=[row for row in candidate_candidates if row.strategy_key == strategy_key],
            overlap_pairs=[
                (baseline_by_key[key], candidate_by_key[key])
                for key in sorted(overlap_keys)
                if key[3] == strategy_key
            ],
        )
        for strategy_key in strategy_keys
    ]

    return BookmakerReplayComparisonReport(
        csv_path=csv_path,
        row_count=len(rows),
        train_rows=len(train_rows),
        validation_rows=len(validation_rows),
        source_name=source_name,
        baseline_bookmaker=baseline_bookmaker,
        candidate_bookmaker=candidate_bookmaker,
        baseline_snapshot_match_count=len(baseline_snapshots_by_match_id),
        candidate_snapshot_match_count=len(candidate_snapshots_by_match_id),
        overlap_match_count=len(overlap_match_ids),
        baseline_candidate_count=len(baseline_candidates),
        candidate_candidate_count=len(candidate_candidates),
        overlap_candidate_count=len(overlap_keys),
        baseline_only_candidate_count=len(set(baseline_by_key) - overlap_keys),
        candidate_only_candidate_count=len(set(candidate_by_key) - overlap_keys),
        strategy_summaries=strategy_summaries,
    )


def format_bookmaker_replay_comparison_report(report: BookmakerReplayComparisonReport) -> str:
    lines = [
        "# Bookmaker Replay Comparison",
        "",
        f"- Feature CSV: `{report.csv_path}`",
        f"- Historical odds: `{report.source_name}`",
        f"- Baseline bookmaker: `{report.baseline_bookmaker}`",
        f"- Candidate bookmaker: `{report.candidate_bookmaker}`",
        "",
        "## Coverage",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Rows | {report.row_count} |",
        f"| Train rows | {report.train_rows} |",
        f"| Validation rows | {report.validation_rows} |",
        f"| Baseline snapshot matches | {report.baseline_snapshot_match_count} |",
        f"| Candidate snapshot matches | {report.candidate_snapshot_match_count} |",
        f"| Overlap matches | {report.overlap_match_count} |",
        f"| Baseline candidates | {report.baseline_candidate_count} |",
        f"| Candidate candidates | {report.candidate_candidate_count} |",
        f"| Overlap candidates | {report.overlap_candidate_count} |",
        f"| Baseline-only candidates | {report.baseline_only_candidate_count} |",
        f"| Candidate-only candidates | {report.candidate_only_candidate_count} |",
        "",
        "## Strategy Comparison",
        "",
        (
            "| Strategy | Baseline | Candidate | Overlap | Base-only | Cand-only | "
            "Base profit | Cand profit | Base ROI | Cand ROI | "
            "Overlap base profit | Overlap cand profit | Avg abs line diff | Avg abs odds diff |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in report.strategy_summaries:
        lines.append(
            f"| `{summary.strategy_key}` | "
            f"{summary.baseline_candidate_count} | "
            f"{summary.candidate_candidate_count} | "
            f"{summary.overlap_candidate_count} | "
            f"{summary.baseline_only_candidate_count} | "
            f"{summary.candidate_only_candidate_count} | "
            f"{summary.baseline_profit} | "
            f"{summary.candidate_profit} | "
            f"{_format_optional(summary.baseline_roi)} | "
            f"{_format_optional(summary.candidate_roi)} | "
            f"{summary.overlap_baseline_profit} | "
            f"{summary.overlap_candidate_profit} | "
            f"{summary.overlap_avg_abs_line_diff} | "
            f"{summary.overlap_avg_abs_odds_diff} |"
        )
    return "\n".join(lines)


def write_bookmaker_replay_comparison_report(
    report: BookmakerReplayComparisonReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_bookmaker_replay_comparison_report(report) + "\n", encoding="utf-8")


def _collect_candidates(
    rows: list[dict[str, str]],
    *,
    matches_by_id,
    snapshots_by_match_id,
    overlap_match_ids: set[int],
    scorer,
    edge_threshold: str,
    display_name_service: DisplayNameService,
    team_prior_states,
) -> list[PaperQueueRow]:
    candidates: list[PaperQueueRow] = []
    for row in rows:
        match_id = _match_id_from_row(row)
        if match_id is None or match_id not in overlap_match_ids:
            continue
        match = matches_by_id.get(match_id)
        if match is None:
            continue
        historical_snapshots = snapshots_by_match_id.get(match_id, [])
        if not historical_snapshots:
            continue
        match_rows = build_paper_recommendation_rows_for_match(
            match,
            scorer=scorer,
            edge_threshold=edge_threshold,
            display_name_service=display_name_service,
            historical_snapshots=historical_snapshots,
            team_prior_states=team_prior_states,
        )
        candidates.extend(row for row in match_rows if row.status == "candidate")
    candidates.sort(key=lambda row: (row.strategy_key, row.match_id, row.market_type, row.side or ""))
    return candidates


def _strategy_summary(
    strategy_key: str,
    *,
    baseline_candidates: list[PaperQueueRow],
    candidate_candidates: list[PaperQueueRow],
    overlap_pairs: list[tuple[PaperQueueRow, PaperQueueRow]],
) -> BookmakerReplayComparisonStrategySummary:
    baseline_keys = {_candidate_key(row) for row in baseline_candidates}
    candidate_keys = {_candidate_key(row) for row in candidate_candidates}
    overlap_keys = baseline_keys & candidate_keys
    return BookmakerReplayComparisonStrategySummary(
        strategy_key=strategy_key,
        baseline_candidate_count=len(baseline_candidates),
        candidate_candidate_count=len(candidate_candidates),
        overlap_candidate_count=len(overlap_keys),
        baseline_only_candidate_count=len(baseline_keys - overlap_keys),
        candidate_only_candidate_count=len(candidate_keys - overlap_keys),
        baseline_profit=_candidate_profit(baseline_candidates),
        candidate_profit=_candidate_profit(candidate_candidates),
        baseline_roi=_ratio(_candidate_profit(baseline_candidates), len(baseline_candidates)),
        candidate_roi=_ratio(_candidate_profit(candidate_candidates), len(candidate_candidates)),
        overlap_baseline_profit=_candidate_profit([baseline for baseline, _ in overlap_pairs]),
        overlap_candidate_profit=_candidate_profit([candidate for _, candidate in overlap_pairs]),
        overlap_avg_abs_line_diff=_avg_abs(
            [
                (candidate.line or Decimal("0")) - (baseline.line or Decimal("0"))
                for baseline, candidate in overlap_pairs
                if baseline.line is not None and candidate.line is not None
            ]
        ),
        overlap_avg_abs_odds_diff=_avg_abs(
            [
                (candidate.odds or Decimal("0")) - (baseline.odds or Decimal("0"))
                for baseline, candidate in overlap_pairs
                if baseline.odds is not None and candidate.odds is not None
            ]
        ),
    )


def _candidate_key(row: PaperQueueRow) -> tuple[int, str, str, str]:
    return (row.match_id, row.market_type, row.side or "", row.strategy_key)


def _candidate_profit(candidates: list[PaperQueueRow]) -> Decimal:
    total = Decimal("0")
    for candidate in candidates:
        profit = _row_profit(candidate)
        if profit is not None:
            total += profit
    return _quantize(total)


def _row_profit(row: PaperQueueRow) -> Decimal | None:
    if row.odds is None or row.side is None:
        return None
    if row.market_type == "asian_handicap":
        if row.side == "away_cover":
            return _quantize(row.odds - Decimal("1"))
        if row.side == "home_cover":
            return Decimal("-1.0000")
    if row.market_type == "total_goals":
        if row.side == "under":
            return _quantize(row.odds - Decimal("1"))
        if row.side == "over":
            return Decimal("-1.0000")
    return None


def _avg_abs(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0.0000")
    return (sum(abs(value) for value in values) / Decimal(len(values))).quantize(
        METRIC_QUANT,
        rounding=ROUND_HALF_UP,
    )


def _ratio(numerator: Decimal, denominator: int) -> Decimal | None:
    if denominator <= 0:
        return None
    return (numerator / Decimal(denominator)).quantize(METRIC_QUANT, rounding=ROUND_HALF_UP)

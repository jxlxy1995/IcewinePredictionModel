from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy.orm import Session

from icewine_prediction.baseline_execution_robustness_grid_service import _profile_matches_rule
from icewine_prediction.baseline_execution_robustness_service import (
    DEFAULT_EXECUTION_TARGETS,
    DEFAULT_PRIMARY_TARGET,
    DEFAULT_TARGET_TOLERANCE_MINUTES,
    build_baseline_execution_robustness_report,
)
from icewine_prediction.baseline_recommendation_sandbox_service import (
    SandboxCandidate,
    _format_optional,
    _quantize,
)
from icewine_prediction.baseline_t15_signal_comparison_service import (
    DEFAULT_BOOKMAKER,
    _candidate_key,
    _candidates_by_strategy,
    _clear_market_fields,
    _load_matches_by_id,
    _load_snapshots_by_match_id,
    _match_id_from_row,
    _match_snapshot_timeline_kickoff_time,
    _patch_market_fields,
    _patch_row_with_t15_markets,
    _row_match_ids,
)
from icewine_prediction.execution_robustness_rules import (
    DEFAULT_SELECTED_ROBUSTNESS_RULES,
    SelectedExecutionRobustnessRule,
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
    train_paper_queue_scorer_from_rows,
)
from icewine_prediction.paper_strategy_registry import STRATEGIES


METRIC_QUANT = Decimal("0.0001")


@dataclass(frozen=True)
class PaperDiscoveryCandidateSets:
    strategy_key: str
    display_name: str
    latest_candidates: list[SandboxCandidate]
    t15_candidates: list[SandboxCandidate]
    robust_kept_candidates: list[SandboxCandidate]


@dataclass(frozen=True)
class PaperDiscoveryGroupMetrics:
    count: int
    wins: int
    profit: Decimal
    roi: Decimal | None
    hit_rate: Decimal | None


@dataclass(frozen=True)
class PaperDiscoveryAlignmentStrategySummary:
    strategy_key: str
    display_name: str
    latest: PaperDiscoveryGroupMetrics
    t15_primary: PaperDiscoveryGroupMetrics
    overlap_latest: PaperDiscoveryGroupMetrics
    overlap_t15: PaperDiscoveryGroupMetrics
    latest_only: PaperDiscoveryGroupMetrics
    t15_only: PaperDiscoveryGroupMetrics
    robust_kept: PaperDiscoveryGroupMetrics
    robust_kept_not_latest: PaperDiscoveryGroupMetrics
    latest_t15_overlap_share: Decimal | None


@dataclass(frozen=True)
class BaselinePaperDiscoveryAlignmentReport:
    csv_path: Path
    row_count: int
    train_rows: int
    validation_rows: int
    latest_available_rows: int
    t15_available_rows: int
    missing_latest_rows: int
    missing_t15_rows: int
    source_name: str
    bookmaker: str
    execution_targets: tuple[int, ...]
    primary_target: int
    tolerance_minutes: int
    strategy_summaries: list[PaperDiscoveryAlignmentStrategySummary]
    candidate_sets: list[PaperDiscoveryCandidateSets]


def build_baseline_paper_discovery_alignment_report(
    session: Session,
    csv_path: Path = DEFAULT_FEATURE_CSV_PATH,
    *,
    source_name: str = ODDSPAPI_SOURCE_NAME,
    bookmaker: str = DEFAULT_BOOKMAKER,
    execution_targets: tuple[int, ...] = DEFAULT_EXECUTION_TARGETS,
    primary_target: int = DEFAULT_PRIMARY_TARGET,
    tolerance_minutes: int = DEFAULT_TARGET_TOLERANCE_MINUTES,
    selected_rules: dict[str, SelectedExecutionRobustnessRule] = DEFAULT_SELECTED_ROBUSTNESS_RULES,
) -> BaselinePaperDiscoveryAlignmentReport:
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
        raise ValueError("paper discovery alignment requires both train and validation rows")

    scorer = train_paper_queue_scorer_from_rows(train_rows)
    matches_by_id = _load_matches_by_id(session, _row_match_ids(validation_rows))
    snapshots_by_match_id = _load_snapshots_by_match_id(
        session,
        match_ids=list(matches_by_id),
        source_name=source_name,
        bookmaker=bookmaker,
    )

    latest_rows = []
    t15_rows = []
    missing_latest_rows = 0
    missing_t15_rows = 0
    for row in validation_rows:
        match = matches_by_id.get(_match_id_from_row(row))
        if match is None:
            missing_latest_rows += 1
            missing_t15_rows += 1
            continue
        snapshots = snapshots_by_match_id.get(match.id, [])
        latest_row = _patch_row_with_latest_historical_markets(
            row,
            match=match,
            snapshots=snapshots,
        )
        if latest_row is None:
            missing_latest_rows += 1
        else:
            latest_rows.append(latest_row)
        t15_row = _patch_row_with_t15_markets(
            row,
            match=match,
            snapshots=snapshots,
            target_minutes_before_kickoff=primary_target,
            tolerance_minutes=tolerance_minutes,
        )
        if t15_row is None:
            missing_t15_rows += 1
        else:
            t15_rows.append(t15_row)

    latest_candidates_by_strategy = _candidates_by_strategy(latest_rows, scorer)
    t15_candidates_by_strategy = _candidates_by_strategy(t15_rows, scorer)
    robust_kept_by_strategy = _robust_kept_candidates_by_strategy(
        session,
        csv_path,
        execution_targets=execution_targets,
        primary_target=primary_target,
        tolerance_minutes=tolerance_minutes,
        source_name=source_name,
        bookmaker=bookmaker,
        selected_rules=selected_rules,
    )

    candidate_sets = [
        PaperDiscoveryCandidateSets(
            strategy_key=strategy.strategy_key,
            display_name=strategy.display_name,
            latest_candidates=latest_candidates_by_strategy.get(strategy.strategy_key, []),
            t15_candidates=t15_candidates_by_strategy.get(strategy.strategy_key, []),
            robust_kept_candidates=robust_kept_by_strategy.get(strategy.strategy_key, []),
        )
        for strategy in STRATEGIES
    ]
    return BaselinePaperDiscoveryAlignmentReport(
        csv_path=csv_path,
        row_count=len(rows),
        train_rows=len(train_rows),
        validation_rows=len(validation_rows),
        latest_available_rows=len(latest_rows),
        t15_available_rows=len(t15_rows),
        missing_latest_rows=missing_latest_rows,
        missing_t15_rows=missing_t15_rows,
        source_name=source_name,
        bookmaker=bookmaker,
        execution_targets=execution_targets,
        primary_target=primary_target,
        tolerance_minutes=tolerance_minutes,
        strategy_summaries=[
            _candidate_set_alignment_summary(candidate_set)
            for candidate_set in candidate_sets
        ],
        candidate_sets=candidate_sets,
    )


def write_baseline_paper_discovery_alignment_report(
    report: BaselinePaperDiscoveryAlignmentReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_baseline_paper_discovery_alignment_report(report) + "\n",
        encoding="utf-8",
    )


def format_baseline_paper_discovery_alignment_report(
    report: BaselinePaperDiscoveryAlignmentReport,
) -> str:
    lines = [
        "# Baseline Paper Discovery Alignment",
        "",
        f"- Feature CSV: `{report.csv_path}`",
        f"- Historical odds: `{report.source_name}` / `{report.bookmaker}`",
        f"- Latest: latest pre-kickoff historical snapshot per market",
        f"- T-15 primary: target `{report.primary_target}` minutes, tolerance `+/-{report.tolerance_minutes}` minutes",
        f"- Robust targets: `{', '.join(str(target) for target in report.execution_targets)}` minutes",
        "",
        "## Data Coverage",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Rows | {report.row_count} |",
        f"| Train rows | {report.train_rows} |",
        f"| Validation rows | {report.validation_rows} |",
        f"| Latest available rows | {report.latest_available_rows} |",
        f"| Missing latest rows | {report.missing_latest_rows} |",
        f"| T-15 available rows | {report.t15_available_rows} |",
        f"| Missing T-15 rows | {report.missing_t15_rows} |",
        "",
        "## Strategy Alignment",
        "",
        (
            "| Strategy | Latest bets | Latest ROI | T15 bets | T15 ROI | Overlap | "
            "latest-only | latest-only ROI | T15-only | T15-only ROI | "
            "Robust kept | Robust kept ROI | Robust kept not latest | Robust not latest ROI |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in report.strategy_summaries:
        lines.append(
            f"| `{summary.strategy_key}` | "
            f"{summary.latest.count} | {_format_optional(summary.latest.roi)} | "
            f"{summary.t15_primary.count} | {_format_optional(summary.t15_primary.roi)} | "
            f"{summary.overlap_latest.count} | "
            f"{summary.latest_only.count} | {_format_optional(summary.latest_only.roi)} | "
            f"{summary.t15_only.count} | {_format_optional(summary.t15_only.roi)} | "
            f"{summary.robust_kept.count} | {_format_optional(summary.robust_kept.roi)} | "
            f"{summary.robust_kept_not_latest.count} | {_format_optional(summary.robust_kept_not_latest.roi)} |"
        )
    lines.extend(
        [
            "",
            "## Metric Notes",
            "",
            "- `latest-only` means the candidate appears when using the latest pre-kickoff snapshot, but not under the T-15 primary snapshot.",
            "- `T15-only` means the candidate appears under the T-15 primary snapshot, but not when using the latest pre-kickoff snapshot.",
            "- `Robust kept not latest` means the T-15 primary candidate passes the selected robustness rule but does not appear in latest discovery.",
            "- ROI and hit rate are evaluated with the odds/line from the group being measured.",
        ]
    )
    return "\n".join(lines)


def _candidate_set_alignment_summary(
    candidate_set: PaperDiscoveryCandidateSets,
) -> PaperDiscoveryAlignmentStrategySummary:
    latest_by_key = _best_candidates_by_key(candidate_set.latest_candidates)
    t15_by_key = _best_candidates_by_key(candidate_set.t15_candidates)
    robust_by_key = _best_candidates_by_key(candidate_set.robust_kept_candidates)
    latest_keys = set(latest_by_key)
    t15_keys = set(t15_by_key)
    robust_keys = set(robust_by_key)
    overlap_keys = latest_keys & t15_keys
    latest_only_keys = latest_keys - t15_keys
    t15_only_keys = t15_keys - latest_keys
    robust_not_latest_keys = robust_keys - latest_keys
    return PaperDiscoveryAlignmentStrategySummary(
        strategy_key=candidate_set.strategy_key,
        display_name=candidate_set.display_name,
        latest=_candidate_metrics(list(latest_by_key.values())),
        t15_primary=_candidate_metrics(list(t15_by_key.values())),
        overlap_latest=_candidate_metrics(_candidates_for_keys(latest_by_key, overlap_keys)),
        overlap_t15=_candidate_metrics(_candidates_for_keys(t15_by_key, overlap_keys)),
        latest_only=_candidate_metrics(_candidates_for_keys(latest_by_key, latest_only_keys)),
        t15_only=_candidate_metrics(_candidates_for_keys(t15_by_key, t15_only_keys)),
        robust_kept=_candidate_metrics(list(robust_by_key.values())),
        robust_kept_not_latest=_candidate_metrics(
            _candidates_for_keys(robust_by_key, robust_not_latest_keys)
        ),
        latest_t15_overlap_share=(
            _ratio(Decimal(len(overlap_keys)), len(latest_keys))
            if latest_keys
            else None
        ),
    )


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


def _robust_kept_candidates_by_strategy(
    session: Session,
    csv_path: Path,
    *,
    execution_targets: tuple[int, ...],
    primary_target: int,
    tolerance_minutes: int,
    source_name: str,
    bookmaker: str,
    selected_rules: dict[str, SelectedExecutionRobustnessRule],
) -> dict[str, list[SandboxCandidate]]:
    robustness_report = build_baseline_execution_robustness_report(
        session,
        csv_path,
        execution_targets=execution_targets,
        primary_target=primary_target,
        tolerance_minutes=tolerance_minutes,
        source_name=source_name,
        bookmaker=bookmaker,
    )
    kept_by_strategy: dict[str, list[SandboxCandidate]] = defaultdict(list)
    for strategy in STRATEGIES:
        rule = selected_rules.get(strategy.strategy_key)
        if rule is None or rule.primary_target != primary_target:
            continue
        profiles = robustness_report.profiles_by_strategy.get(strategy.strategy_key, [])
        if rule.mode == "observe":
            kept_profiles = profiles
        elif rule.mode == "filter":
            grid_rule = rule.as_grid_rule()
            kept_profiles = [
                profile for profile in profiles if _profile_matches_rule(profile, grid_rule)
            ]
        else:
            raise ValueError(f"unknown execution robustness rule mode: {rule.mode}")
        kept_by_strategy[strategy.strategy_key].extend(
            profile.primary_candidate for profile in kept_profiles
        )
    return dict(kept_by_strategy)


def _candidate_metrics(candidates: list[SandboxCandidate]) -> PaperDiscoveryGroupMetrics:
    count = len(candidates)
    profit = _quantize(sum((candidate.profit for candidate in candidates), Decimal("0")))
    wins = sum(1 for candidate in candidates if candidate.profit > 0)
    return PaperDiscoveryGroupMetrics(
        count=count,
        wins=wins,
        profit=profit,
        roi=_ratio(profit, count),
        hit_rate=_ratio(Decimal(wins), count),
    )


def _best_candidates_by_key(
    candidates: list[SandboxCandidate],
) -> dict[tuple[str, str, str], SandboxCandidate]:
    by_key: dict[tuple[str, str, str], SandboxCandidate] = {}
    for candidate in candidates:
        key = _candidate_key(candidate)
        existing = by_key.get(key)
        if existing is None or candidate.edge > existing.edge:
            by_key[key] = candidate
    return by_key


def _candidates_for_keys(
    candidates_by_key: dict[tuple[str, str, str], SandboxCandidate],
    keys: set[tuple[str, str, str]],
) -> list[SandboxCandidate]:
    return [candidate for key, candidate in candidates_by_key.items() if key in keys]


def _ratio(numerator: Decimal, denominator: int) -> Decimal | None:
    if denominator <= 0:
        return None
    return (numerator / Decimal(denominator)).quantize(METRIC_QUANT, rounding=ROUND_HALF_UP)

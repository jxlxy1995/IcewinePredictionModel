from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from icewine_prediction.config import BEIJING_TIMEZONE
from icewine_prediction.historical_training_sample_report_service import (
    DEFAULT_HISTORICAL_ODDS_ELIGIBLE_START,
    _beijing_wall_datetime,
    _list_finished_scored_matches,
)
from icewine_prediction.historical_training_sample_service import (
    HistoricalMarketTrainingSample,
    list_historical_market_training_samples,
)


BEIJING = ZoneInfo(BEIJING_TIMEZONE)
CORE_ANCHOR_LABELS = ("24h", "12h", "6h", "3h", "1h", "close")
CORE_MARKET_TYPES = ("asian_handicap", "total_goals")
RATIO_QUANT = Decimal("0.0000")
AVERAGE_QUANT = Decimal("0.01")


@dataclass(frozen=True)
class AnchorCoverage:
    label: str
    sample_count: int
    coverage_ratio: Decimal
    sample_internal_coverage_ratio: Decimal


@dataclass(frozen=True)
class MarketAnchorCoverageReport:
    market_type: str
    eligible_match_count: int
    sample_count: int
    sample_coverage_ratio: Decimal
    complete_core_anchor_sample_count: int
    complete_core_anchor_coverage_ratio: Decimal
    average_snapshot_count: Decimal
    anchor_reports: dict[str, AnchorCoverage]


@dataclass(frozen=True)
class HistoricalOddsAnchorCoverageReport:
    season: int | None
    eligible_start: datetime
    bookmaker: str
    anchor_labels: tuple[str, ...]
    eligible_match_count: int
    market_reports: dict[str, MarketAnchorCoverageReport]


def build_historical_odds_anchor_coverage_report(
    session: Session,
    *,
    season: int | None = None,
    eligible_start: datetime | None = None,
    bookmaker: str = "pinnacle",
    anchor_labels: tuple[str, ...] = CORE_ANCHOR_LABELS,
    market_types: tuple[str, ...] = CORE_MARKET_TYPES,
) -> HistoricalOddsAnchorCoverageReport:
    normalized_eligible_start = _normalize_eligible_start(eligible_start)
    matches = _list_finished_scored_matches(session, season=season)
    eligible_matches = [
        match
        for match in matches
        if _beijing_wall_datetime(match.kickoff_time)
        >= _beijing_wall_datetime(normalized_eligible_start)
    ]
    samples = list_historical_market_training_samples(
        session,
        season=season,
        bookmaker=bookmaker,
    )
    eligible_samples = [
        sample
        for sample in samples
        if sample.market_type in market_types
        and _beijing_wall_datetime(sample.kickoff_time)
        >= _beijing_wall_datetime(normalized_eligible_start)
    ]
    samples_by_market: dict[str, list[HistoricalMarketTrainingSample]] = {}
    for sample in eligible_samples:
        samples_by_market.setdefault(sample.market_type, []).append(sample)
    return HistoricalOddsAnchorCoverageReport(
        season=season,
        eligible_start=normalized_eligible_start,
        bookmaker=bookmaker,
        anchor_labels=anchor_labels,
        eligible_match_count=len(eligible_matches),
        market_reports={
            market_type: _build_market_report(
                market_type=market_type,
                samples=samples_by_market.get(market_type, []),
                eligible_match_count=len(eligible_matches),
                anchor_labels=anchor_labels,
            )
            for market_type in market_types
        },
    )


def format_historical_odds_anchor_coverage_report(
    report: HistoricalOddsAnchorCoverageReport,
) -> str:
    eligible_start = report.eligible_start.astimezone(BEIJING)
    lines = [
        "# Historical Odds Anchor Coverage v1",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Season | {report.season if report.season is not None else '-'} |",
        f"| Bookmaker | {report.bookmaker} |",
        f"| Eligible start | {eligible_start:%Y-%m-%d %H:%M} {BEIJING_TIMEZONE} |",
        f"| Eligible matches | {report.eligible_match_count} |",
        "",
    ]
    for market_type, market_report in report.market_reports.items():
        lines.extend(
            [
                f"## {market_type}",
                "",
                "| Metric | Value |",
                "| --- | ---: |",
                f"| Samples | {market_report.sample_count} |",
                f"| Sample coverage | {market_report.sample_coverage_ratio} |",
                (
                    "| Complete core-anchor samples | "
                    f"{market_report.complete_core_anchor_sample_count} |"
                ),
                (
                    "| Complete core-anchor coverage | "
                    f"{market_report.complete_core_anchor_coverage_ratio} |"
                ),
                f"| Average snapshots | {market_report.average_snapshot_count} |",
                "",
                "### Anchor Coverage",
                "",
                "| Anchor | Samples | Eligible coverage | Sample coverage |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        lines.extend(
            (
                f"| {anchor.label} | {anchor.sample_count} | "
                f"{anchor.coverage_ratio} | "
                f"{anchor.sample_internal_coverage_ratio} |"
            )
            for anchor in market_report.anchor_reports.values()
        )
        lines.append("")
    return "\n".join(lines)


def write_historical_odds_anchor_coverage_report(
    report: HistoricalOddsAnchorCoverageReport,
    output_path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_historical_odds_anchor_coverage_report(report) + "\n",
        encoding="utf-8",
    )


def _build_market_report(
    *,
    market_type: str,
    samples: list[HistoricalMarketTrainingSample],
    eligible_match_count: int,
    anchor_labels: tuple[str, ...],
) -> MarketAnchorCoverageReport:
    anchor_sets = {sample.match_id: {anchor.label for anchor in sample.anchors} for sample in samples}
    anchor_reports = {
        label: AnchorCoverage(
            label=label,
            sample_count=sum(1 for anchors in anchor_sets.values() if label in anchors),
            coverage_ratio=_ratio(
                sum(1 for anchors in anchor_sets.values() if label in anchors),
                eligible_match_count,
            ),
            sample_internal_coverage_ratio=_ratio(
                sum(1 for anchors in anchor_sets.values() if label in anchors),
                len(samples),
            ),
        )
        for label in anchor_labels
    }
    complete_count = sum(
        1
        for anchors in anchor_sets.values()
        if all(label in anchors for label in anchor_labels)
    )
    return MarketAnchorCoverageReport(
        market_type=market_type,
        eligible_match_count=eligible_match_count,
        sample_count=len(samples),
        sample_coverage_ratio=_ratio(len(samples), eligible_match_count),
        complete_core_anchor_sample_count=complete_count,
        complete_core_anchor_coverage_ratio=_ratio(complete_count, eligible_match_count),
        average_snapshot_count=_average(
            [Decimal(sample.snapshot_count) for sample in samples],
        ),
        anchor_reports=anchor_reports,
    )


def _ratio(numerator: int, denominator: int) -> Decimal:
    if denominator == 0:
        return RATIO_QUANT
    return (Decimal(numerator) / Decimal(denominator)).quantize(
        RATIO_QUANT,
        rounding=ROUND_HALF_UP,
    )


def _average(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0").quantize(AVERAGE_QUANT)
    return (sum(values) / Decimal(len(values))).quantize(
        AVERAGE_QUANT,
        rounding=ROUND_HALF_UP,
    )


def _normalize_eligible_start(value: datetime | None) -> datetime:
    if value is None:
        return DEFAULT_HISTORICAL_ODDS_ELIGIBLE_START
    if value.tzinfo is None:
        return value.replace(tzinfo=BEIJING)
    return value.astimezone(BEIJING)

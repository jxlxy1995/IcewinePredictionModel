from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, joinedload

from icewine_prediction.config import BEIJING_TIMEZONE
from icewine_prediction.historical_training_sample_service import (
    DEFAULT_ANCHORS,
    HistoricalMarketTrainingSample,
    list_historical_market_training_samples,
)
from icewine_prediction.models import Match


BEIJING = ZoneInfo(BEIJING_TIMEZONE)
DEFAULT_HISTORICAL_ODDS_ELIGIBLE_START = datetime(2026, 1, 15, tzinfo=BEIJING)
RATIO_QUANT = Decimal("0.0000")
AVERAGE_QUANT = Decimal("0.01")


@dataclass(frozen=True)
class HistoricalOddsMarketSampleReport:
    market_type: str
    sample_count: int
    complete_anchor_sample_count: int
    thin_history_sample_count: int
    average_snapshot_count: Decimal
    average_absolute_line_movement: Decimal
    missing_anchor_counts: dict[str, int]


@dataclass(frozen=True)
class HistoricalOddsLeagueSampleReport:
    league_name: str
    full_season_match_count: int
    eligible_match_count: int
    excluded_before_eligible_start_count: int
    match_with_sample_count: int
    eligible_coverage_ratio: Decimal
    full_season_coverage_ratio: Decimal
    market_reports: dict[str, HistoricalOddsMarketSampleReport]


@dataclass(frozen=True)
class HistoricalOddsSampleQualityReport:
    season: int | None
    eligible_start: datetime
    bookmaker: str
    full_season_match_count: int
    eligible_match_count: int
    excluded_before_eligible_start_count: int
    match_with_sample_count: int
    eligible_coverage_ratio: Decimal
    full_season_coverage_ratio: Decimal
    market_reports: dict[str, HistoricalOddsMarketSampleReport]
    league_reports: dict[str, HistoricalOddsLeagueSampleReport]


def build_historical_odds_sample_quality_report(
    session: Session,
    *,
    season: int | None = None,
    eligible_start: datetime | None = None,
    bookmaker: str = "pinnacle",
) -> HistoricalOddsSampleQualityReport:
    normalized_eligible_start = _normalize_eligible_start(eligible_start)
    matches = _list_finished_scored_matches(session, season=season)
    full_matches_by_league = _count_matches_by_league(matches)
    eligible_matches = [
        match
        for match in matches
        if _beijing_wall_datetime(match.kickoff_time)
        >= _beijing_wall_datetime(normalized_eligible_start)
    ]
    eligible_matches_by_league = _count_matches_by_league(eligible_matches)
    all_samples = list_historical_market_training_samples(
        session,
        season=season,
        bookmaker=bookmaker,
    )
    eligible_samples = [
        sample
        for sample in all_samples
        if _beijing_wall_datetime(sample.kickoff_time)
        >= _beijing_wall_datetime(normalized_eligible_start)
    ]
    match_ids_with_samples = {sample.match_id for sample in eligible_samples}

    return HistoricalOddsSampleQualityReport(
        season=season,
        eligible_start=normalized_eligible_start,
        bookmaker=bookmaker,
        full_season_match_count=len(matches),
        eligible_match_count=len(eligible_matches),
        excluded_before_eligible_start_count=len(matches) - len(eligible_matches),
        match_with_sample_count=len(match_ids_with_samples),
        eligible_coverage_ratio=_ratio(len(match_ids_with_samples), len(eligible_matches)),
        full_season_coverage_ratio=_ratio(len(match_ids_with_samples), len(matches)),
        market_reports=_build_market_reports(eligible_samples),
        league_reports=_build_league_reports(
            full_matches_by_league=full_matches_by_league,
            eligible_matches_by_league=eligible_matches_by_league,
            eligible_samples=eligible_samples,
        ),
    )


def format_historical_odds_sample_quality_report(
    report: HistoricalOddsSampleQualityReport,
) -> str:
    eligible_start = report.eligible_start.astimezone(BEIJING)
    lines = [
        (
            f"historical odds sample report"
            f" season {report.season if report.season is not None else '-'}"
            f" bookmaker {report.bookmaker}"
        ),
        f"eligible start {eligible_start:%Y-%m-%d %H:%M} {BEIJING_TIMEZONE}",
        (
            f"matches full-season {report.full_season_match_count}"
            f" eligible {report.eligible_match_count}"
            f" excluded-before-start {report.excluded_before_eligible_start_count}"
            f" with-sample {report.match_with_sample_count}"
        ),
        (
            f"eligible coverage {report.eligible_coverage_ratio}"
            f" / full-season coverage {report.full_season_coverage_ratio}"
        ),
    ]
    lines.append("markets")
    if report.market_reports:
        lines.extend(
            _format_market_report(market_report)
            for _, market_report in sorted(report.market_reports.items())
        )
    else:
        lines.append("-")
    lines.append("leagues")
    if report.league_reports:
        lines.extend(
            _format_league_report(league_report)
            for _, league_report in sorted(report.league_reports.items())
        )
    else:
        lines.append("-")
    return "\n".join(lines)


def _list_finished_scored_matches(session: Session, *, season: int | None) -> list[Match]:
    query = (
        session.query(Match)
        .options(joinedload(Match.league))
        .filter(Match.status == "finished")
        .filter(Match.home_score.isnot(None))
        .filter(Match.away_score.isnot(None))
        .order_by(Match.kickoff_time.asc(), Match.id.asc())
    )
    if season is not None:
        query = query.filter(Match.season == season)
    return query.all()


def _count_matches_by_league(matches: list[Match]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for match in matches:
        league_name = match.league.name
        counts[league_name] = counts.get(league_name, 0) + 1
    return counts


def _build_league_reports(
    *,
    full_matches_by_league: dict[str, int],
    eligible_matches_by_league: dict[str, int],
    eligible_samples: list[HistoricalMarketTrainingSample],
) -> dict[str, HistoricalOddsLeagueSampleReport]:
    samples_by_league: dict[str, list[HistoricalMarketTrainingSample]] = {}
    match_ids_by_league: dict[str, set[int]] = {}
    for sample in eligible_samples:
        samples_by_league.setdefault(sample.league_name, []).append(sample)
        match_ids_by_league.setdefault(sample.league_name, set()).add(sample.match_id)

    reports = {}
    league_names = set(full_matches_by_league) | set(eligible_matches_by_league) | set(samples_by_league)
    for league_name in league_names:
        full_count = full_matches_by_league.get(league_name, 0)
        eligible_count = eligible_matches_by_league.get(league_name, 0)
        match_with_sample_count = len(match_ids_by_league.get(league_name, set()))
        reports[league_name] = HistoricalOddsLeagueSampleReport(
            league_name=league_name,
            full_season_match_count=full_count,
            eligible_match_count=eligible_count,
            excluded_before_eligible_start_count=full_count - eligible_count,
            match_with_sample_count=match_with_sample_count,
            eligible_coverage_ratio=_ratio(match_with_sample_count, eligible_count),
            full_season_coverage_ratio=_ratio(match_with_sample_count, full_count),
            market_reports=_build_market_reports(samples_by_league.get(league_name, [])),
        )
    return reports


def _build_market_reports(
    samples: list[HistoricalMarketTrainingSample],
) -> dict[str, HistoricalOddsMarketSampleReport]:
    samples_by_market: dict[str, list[HistoricalMarketTrainingSample]] = {}
    for sample in samples:
        samples_by_market.setdefault(sample.market_type, []).append(sample)
    return {
        market_type: _build_market_report(market_type, market_samples)
        for market_type, market_samples in samples_by_market.items()
    }


def _build_market_report(
    market_type: str,
    samples: list[HistoricalMarketTrainingSample],
) -> HistoricalOddsMarketSampleReport:
    missing_anchor_counts = {label: 0 for label, _ in DEFAULT_ANCHORS}
    for sample in samples:
        for label in sample.missing_anchor_labels:
            missing_anchor_counts[label] = missing_anchor_counts.get(label, 0) + 1
    missing_anchor_counts = {
        label: count for label, count in missing_anchor_counts.items() if count > 0
    }
    movements = [
        abs(sample.line_movement)
        for sample in samples
        if sample.line_movement is not None
    ]
    return HistoricalOddsMarketSampleReport(
        market_type=market_type,
        sample_count=len(samples),
        complete_anchor_sample_count=sum(
            1 for sample in samples if not sample.missing_anchor_labels
        ),
        thin_history_sample_count=sum(
            1 for sample in samples if "thin_history" in sample.quality_tags
        ),
        average_snapshot_count=_average(
            [Decimal(sample.snapshot_count) for sample in samples],
            quant=AVERAGE_QUANT,
        ),
        average_absolute_line_movement=_average(movements, quant=AVERAGE_QUANT),
        missing_anchor_counts=missing_anchor_counts,
    )


def _format_market_report(report: HistoricalOddsMarketSampleReport) -> str:
    missing_text = _format_counter(report.missing_anchor_counts)
    return (
        f"{report.market_type}: samples {report.sample_count}"
        f" complete-anchors {report.complete_anchor_sample_count}"
        f" thin-history {report.thin_history_sample_count}"
        f" avg-snapshots {report.average_snapshot_count}"
        f" avg-abs-line-move {report.average_absolute_line_movement}"
        f" missing {missing_text}"
    )


def _format_league_report(report: HistoricalOddsLeagueSampleReport) -> str:
    return (
        f"{report.league_name}: eligible {report.eligible_match_count}"
        f" full-season {report.full_season_match_count}"
        f" excluded-before-start {report.excluded_before_eligible_start_count}"
        f" with-sample {report.match_with_sample_count}"
        f" eligible-coverage {report.eligible_coverage_ratio}"
        f" full-season-coverage {report.full_season_coverage_ratio}"
    )


def _format_counter(counter: dict[str, int]) -> str:
    if not counter:
        return "-"
    return ",".join(f"{key}:{value}" for key, value in sorted(counter.items()))


def _ratio(numerator: int, denominator: int) -> Decimal:
    if denominator == 0:
        return RATIO_QUANT
    return (Decimal(numerator) / Decimal(denominator)).quantize(
        RATIO_QUANT,
        rounding=ROUND_HALF_UP,
    )


def _average(values: list[Decimal], *, quant: Decimal) -> Decimal:
    if not values:
        return quant
    return (sum(values) / Decimal(len(values))).quantize(quant, rounding=ROUND_HALF_UP)


def _normalize_eligible_start(value: datetime | None) -> datetime:
    if value is None:
        return DEFAULT_HISTORICAL_ODDS_ELIGIBLE_START
    if value.tzinfo is None:
        return value.replace(tzinfo=BEIJING)
    return value.astimezone(BEIJING)


def _beijing_wall_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(BEIJING).replace(tzinfo=None)

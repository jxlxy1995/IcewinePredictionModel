from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, joinedload

from icewine_prediction.config import BEIJING_TIMEZONE
from icewine_prediction.historical_training_sample_service import (
    HistoricalMarketTrainingSample,
    list_historical_market_training_samples,
)
from icewine_prediction.models import League, Match


BEIJING = ZoneInfo(BEIJING_TIMEZONE)
DEFAULT_BASELINE_ELIGIBLE_START = datetime(2026, 1, 15, tzinfo=BEIJING)
EXCLUDED_AUXILIARY_LEAGUE_IDS = {"2", "3", "848"}
TRAINING_EXCLUDED_LEAGUE_IDS = EXCLUDED_AUXILIARY_LEAGUE_IDS | {"1"}
REQUIRED_MARKETS = ("asian_handicap", "total_goals", "match_winner")
RATIO_QUANT = Decimal("0.0000")
CSV_FIELDNAMES = (
    "match_id",
    "source_match_id",
    "league_name",
    "league_source_id",
    "season",
    "kickoff_time",
    "home_team_name",
    "away_team_name",
    "home_score",
    "away_score",
    "match_result",
    "total_goals",
    "asian_handicap_close_line",
    "asian_handicap_home_odds",
    "asian_handicap_away_odds",
    "asian_handicap_home_implied_probability",
    "asian_handicap_away_implied_probability",
    "asian_handicap_overround",
    "asian_handicap_home_result",
    "asian_handicap_away_result",
    "total_goals_close_line",
    "total_goals_over_odds",
    "total_goals_under_odds",
    "total_goals_over_implied_probability",
    "total_goals_under_implied_probability",
    "total_goals_overround",
    "total_goals_over_result",
    "total_goals_under_result",
    "match_winner_home_odds",
    "match_winner_draw_odds",
    "match_winner_away_odds",
    "match_winner_home_implied_probability",
    "match_winner_draw_implied_probability",
    "match_winner_away_implied_probability",
    "match_winner_overround",
    "match_winner_home_result",
    "match_winner_draw_result",
    "match_winner_away_result",
    "asian_handicap_snapshot_count",
    "total_goals_snapshot_count",
    "match_winner_snapshot_count",
    "quality_tags",
)


@dataclass(frozen=True)
class BaselineTrainingDatasetAudit:
    eligible_start: datetime
    source_name: str | None
    bookmaker: str
    eligible_match_count: int
    complete_match_count: int
    coverage_ratio: Decimal
    market_sample_counts: dict[str, int]
    missing_market_counts: dict[str, int]
    by_league: dict[str, int]
    by_season: dict[int, int]


@dataclass(frozen=True)
class BaselineTrainingDataset:
    rows: list[dict[str, str]]
    audit: BaselineTrainingDatasetAudit


def build_baseline_training_dataset(
    session: Session,
    *,
    eligible_start: datetime | None = None,
    source_name: str | None = None,
    bookmaker: str = "pinnacle",
) -> BaselineTrainingDataset:
    normalized_start = _normalize_eligible_start(eligible_start)
    eligible_matches = _list_eligible_main_matches(session, eligible_start=normalized_start)
    eligible_match_ids = {match.id for match in eligible_matches}
    samples = list_historical_market_training_samples(
        session,
        source_name=source_name,
        bookmaker=bookmaker,
    )
    eligible_samples = [
        sample
        for sample in samples
        if sample.match_id in eligible_match_ids
        and any(anchor.label == "close" for anchor in sample.anchors)
    ]
    samples_by_match_market: dict[int, dict[str, HistoricalMarketTrainingSample]] = {}
    for sample in eligible_samples:
        samples_by_match_market.setdefault(sample.match_id, {})[sample.market_type] = sample

    rows: list[dict[str, str]] = []
    for match in eligible_matches:
        by_market = samples_by_match_market.get(match.id, {})
        if not all(market_type in by_market for market_type in REQUIRED_MARKETS):
            continue
        rows.append(_build_row(match, by_market))

    market_sample_counts = {
        market_type: sum(
            1
            for by_market in samples_by_match_market.values()
            if market_type in by_market
        )
        for market_type in REQUIRED_MARKETS
    }
    missing_market_counts = {
        market_type: len(eligible_matches) - market_sample_counts[market_type]
        for market_type in REQUIRED_MARKETS
    }
    return BaselineTrainingDataset(
        rows=rows,
        audit=BaselineTrainingDatasetAudit(
            eligible_start=normalized_start,
            source_name=source_name,
            bookmaker=bookmaker,
            eligible_match_count=len(eligible_matches),
            complete_match_count=len(rows),
            coverage_ratio=_ratio(len(rows), len(eligible_matches)),
            market_sample_counts=market_sample_counts,
            missing_market_counts=missing_market_counts,
            by_league=_count_rows_by(rows, "league_name"),
            by_season={int(key): value for key, value in _count_rows_by(rows, "season").items()},
        ),
    )


def write_baseline_training_dataset_csv(
    dataset: BaselineTrainingDataset,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(dataset.rows)


def format_baseline_training_dataset_report(audit: BaselineTrainingDatasetAudit) -> str:
    lines = [
        "baseline training dataset",
        f"eligible start: {audit.eligible_start.astimezone(BEIJING):%Y-%m-%d %H:%M} {BEIJING_TIMEZONE}",
        f"source/bookmaker: {audit.source_name or 'any'}/{audit.bookmaker}",
        f"eligible matches: {audit.eligible_match_count}",
        f"complete three-market rows: {audit.complete_match_count}",
        f"coverage: {audit.coverage_ratio}",
        "market samples:",
    ]
    lines.extend(
        f"- {market_type}: {audit.market_sample_counts.get(market_type, 0)} "
        f"(missing {audit.missing_market_counts.get(market_type, 0)})"
        for market_type in REQUIRED_MARKETS
    )
    lines.append("by season:")
    lines.extend(f"- {season}: {count}" for season, count in sorted(audit.by_season.items()))
    lines.append("by league:")
    lines.extend(
        f"- {league_name}: {count}"
        for league_name, count in sorted(audit.by_league.items(), key=lambda item: (-item[1], item[0]))
    )
    return "\n".join(lines)


def write_baseline_training_dataset_report(
    audit: BaselineTrainingDatasetAudit,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_baseline_training_dataset_report(audit) + "\n", encoding="utf-8")


def _list_eligible_main_matches(
    session: Session,
    *,
    eligible_start: datetime,
) -> list[Match]:
    return (
        session.query(Match)
        .options(
            joinedload(Match.league),
            joinedload(Match.home_team),
            joinedload(Match.away_team),
        )
        .join(League, Match.league_id == League.id)
        .filter(League.is_enabled.is_(True))
        .filter(~League.source_league_id.in_(TRAINING_EXCLUDED_LEAGUE_IDS))
        .filter(Match.status == "finished")
        .filter(Match.home_score.isnot(None))
        .filter(Match.away_score.isnot(None))
        .filter(Match.kickoff_time >= eligible_start.replace(tzinfo=None))
        .order_by(Match.kickoff_time.asc(), Match.id.asc())
        .all()
    )


def _build_row(
    match: Match,
    samples_by_market: dict[str, HistoricalMarketTrainingSample],
) -> dict[str, str]:
    asian = _close_anchor(samples_by_market["asian_handicap"])
    total = _close_anchor(samples_by_market["total_goals"])
    winner = _close_anchor(samples_by_market["match_winner"])
    return {
        "match_id": str(match.id),
        "source_match_id": match.source_match_id or "",
        "league_name": match.league.name,
        "league_source_id": str(match.league.source_league_id or ""),
        "season": str(match.season or ""),
        "kickoff_time": _format_datetime(match.kickoff_time),
        "home_team_name": match.home_team.canonical_name,
        "away_team_name": match.away_team.canonical_name,
        "home_score": str(match.home_score),
        "away_score": str(match.away_score),
        "match_result": _match_result(match),
        "total_goals": str(match.home_score + match.away_score),
        "asian_handicap_close_line": _format_line(asian.market_line),
        "asian_handicap_home_odds": _format_odds(asian.side_a_odds),
        "asian_handicap_away_odds": _format_odds(asian.side_b_odds),
        "asian_handicap_home_implied_probability": _format_probability(
            asian.side_a_implied_probability
        ),
        "asian_handicap_away_implied_probability": _format_probability(
            asian.side_b_implied_probability
        ),
        "asian_handicap_overround": _format_probability(asian.overround),
        "asian_handicap_home_result": asian.side_a_result,
        "asian_handicap_away_result": asian.side_b_result,
        "total_goals_close_line": _format_line(total.market_line),
        "total_goals_over_odds": _format_odds(total.side_a_odds),
        "total_goals_under_odds": _format_odds(total.side_b_odds),
        "total_goals_over_implied_probability": _format_probability(
            total.side_a_implied_probability
        ),
        "total_goals_under_implied_probability": _format_probability(
            total.side_b_implied_probability
        ),
        "total_goals_overround": _format_probability(total.overround),
        "total_goals_over_result": total.side_a_result,
        "total_goals_under_result": total.side_b_result,
        "match_winner_home_odds": _format_odds(winner.side_a_odds),
        "match_winner_draw_odds": _format_odds(winner.side_b_odds),
        "match_winner_away_odds": _format_odds(winner.side_c_odds),
        "match_winner_home_implied_probability": _format_probability(
            winner.side_a_implied_probability
        ),
        "match_winner_draw_implied_probability": _format_probability(
            winner.side_b_implied_probability
        ),
        "match_winner_away_implied_probability": _format_probability(
            winner.side_c_implied_probability
        ),
        "match_winner_overround": _format_probability(winner.overround),
        "match_winner_home_result": winner.side_a_result,
        "match_winner_draw_result": winner.side_b_result,
        "match_winner_away_result": winner.side_c_result or "",
        "asian_handicap_snapshot_count": str(samples_by_market["asian_handicap"].snapshot_count),
        "total_goals_snapshot_count": str(samples_by_market["total_goals"].snapshot_count),
        "match_winner_snapshot_count": str(samples_by_market["match_winner"].snapshot_count),
        "quality_tags": "|".join(
            sorted(
                set(samples_by_market["asian_handicap"].quality_tags)
                | set(samples_by_market["total_goals"].quality_tags)
                | set(samples_by_market["match_winner"].quality_tags)
            )
        ),
    }


def _close_anchor(sample: HistoricalMarketTrainingSample):
    for anchor in reversed(sample.anchors):
        if anchor.label == "close":
            return anchor
    return sample.anchors[-1]


def _match_result(match: Match) -> str:
    if match.home_score > match.away_score:
        return "home_win"
    if match.home_score < match.away_score:
        return "away_win"
    return "draw"


def _count_rows_by(rows: list[dict[str, str]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = row[key]
        counts[value] = counts.get(value, 0) + 1
    return counts


def _ratio(numerator: int, denominator: int) -> Decimal:
    if denominator == 0:
        return RATIO_QUANT
    return (Decimal(numerator) / Decimal(denominator)).quantize(
        RATIO_QUANT,
        rounding=ROUND_HALF_UP,
    )


def _normalize_eligible_start(value: datetime | None) -> datetime:
    if value is None:
        return DEFAULT_BASELINE_ELIGIBLE_START
    if value.tzinfo is None:
        return value.replace(tzinfo=BEIJING)
    return value.astimezone(BEIJING)


def _format_datetime(value: datetime) -> str:
    return value.astimezone(BEIJING).isoformat() if value.tzinfo else value.isoformat()


def _format_line(value: Decimal | None) -> str:
    if value is None:
        return ""
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _format_odds(value: Decimal | None) -> str:
    if value is None:
        return ""
    return str(value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def _format_probability(value: Decimal | None) -> str:
    if value is None:
        return ""
    return str(value.quantize(RATIO_QUANT, rounding=ROUND_HALF_UP))

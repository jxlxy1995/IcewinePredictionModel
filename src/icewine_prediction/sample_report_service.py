from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from icewine_prediction.models import Match
from icewine_prediction.training_sample_service import build_training_sample


@dataclass(frozen=True)
class LeagueTrainingSampleCoverage:
    total_samples: int
    samples_with_odds: int
    samples_with_asian_handicap: int
    samples_with_total_goals: int


@dataclass(frozen=True)
class TrainingSampleReport:
    total_samples: int
    samples_with_odds: int
    samples_with_asian_handicap: int
    samples_with_total_goals: int
    odds_coverage_ratio: Decimal
    asian_handicap_coverage_ratio: Decimal
    total_goals_coverage_ratio: Decimal
    by_league: dict[str, LeagueTrainingSampleCoverage]
    by_season: dict[int, int]
    by_weight: dict[Decimal, int]


def _ratio(numerator: int, denominator: int) -> Decimal:
    if denominator == 0:
        return Decimal("0.00")
    return (Decimal(numerator) / Decimal(denominator)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def _increment(counter: dict, key) -> None:
    counter[key] = counter.get(key, 0) + 1


def _empty_league_coverage() -> LeagueTrainingSampleCoverage:
    return LeagueTrainingSampleCoverage(
        total_samples=0,
        samples_with_odds=0,
        samples_with_asian_handicap=0,
        samples_with_total_goals=0,
    )


def _add_league_coverage(
    current: LeagueTrainingSampleCoverage,
    has_odds: bool,
    has_asian_handicap: bool,
    has_total_goals: bool,
) -> LeagueTrainingSampleCoverage:
    return LeagueTrainingSampleCoverage(
        total_samples=current.total_samples + 1,
        samples_with_odds=current.samples_with_odds + int(has_odds),
        samples_with_asian_handicap=current.samples_with_asian_handicap + int(has_asian_handicap),
        samples_with_total_goals=current.samples_with_total_goals + int(has_total_goals),
    )


def build_training_sample_report(
    session: Session,
    season: int | None = None,
    reference_time: datetime | None = None,
) -> TrainingSampleReport:
    query = (
        session.query(Match)
        .filter(Match.status == "finished")
        .filter(Match.home_score.isnot(None))
        .filter(Match.away_score.isnot(None))
    )
    if season is not None:
        query = query.filter(Match.season == season)
    matches = query.order_by(Match.kickoff_time.desc()).all()
    by_league: dict[str, LeagueTrainingSampleCoverage] = {}
    by_season: dict[int, int] = {}
    by_weight: dict[Decimal, int] = {}
    samples_with_odds = 0
    samples_with_asian_handicap = 0
    samples_with_total_goals = 0
    for match in matches:
        sample = build_training_sample(match, reference_time=reference_time)
        has_odds = sample.has_odds_snapshot
        has_asian_handicap = sample.asian_handicap_line is not None
        has_total_goals = sample.total_line is not None
        if has_odds:
            samples_with_odds += 1
        if has_asian_handicap:
            samples_with_asian_handicap += 1
        if has_total_goals:
            samples_with_total_goals += 1
        by_league[sample.league_name] = _add_league_coverage(
            by_league.get(sample.league_name, _empty_league_coverage()),
            has_odds=has_odds,
            has_asian_handicap=has_asian_handicap,
            has_total_goals=has_total_goals,
        )
        _increment(by_season, match.season if match.season is not None else sample.kickoff_time.year)
        _increment(by_weight, sample.time_decay_weight)
    return TrainingSampleReport(
        total_samples=len(matches),
        samples_with_odds=samples_with_odds,
        samples_with_asian_handicap=samples_with_asian_handicap,
        samples_with_total_goals=samples_with_total_goals,
        odds_coverage_ratio=_ratio(samples_with_odds, len(matches)),
        asian_handicap_coverage_ratio=_ratio(samples_with_asian_handicap, len(matches)),
        total_goals_coverage_ratio=_ratio(samples_with_total_goals, len(matches)),
        by_league=by_league,
        by_season=by_season,
        by_weight=by_weight,
    )

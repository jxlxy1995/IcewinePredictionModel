from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from icewine_prediction.training_sample_service import list_training_samples


@dataclass(frozen=True)
class TrainingSampleReport:
    total_samples: int
    samples_with_odds: int
    odds_coverage_ratio: Decimal
    by_league: dict[str, int]
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


def build_training_sample_report(
    session: Session,
    reference_time: datetime | None = None,
) -> TrainingSampleReport:
    samples = list_training_samples(session, limit=1_000_000, reference_time=reference_time)
    by_league: dict[str, int] = {}
    by_season: dict[int, int] = {}
    by_weight: dict[Decimal, int] = {}
    samples_with_odds = 0
    for sample in samples:
        if sample.has_odds_snapshot:
            samples_with_odds += 1
        _increment(by_league, sample.league_name)
        _increment(by_season, sample.kickoff_time.year)
        _increment(by_weight, sample.time_decay_weight)
    return TrainingSampleReport(
        total_samples=len(samples),
        samples_with_odds=samples_with_odds,
        odds_coverage_ratio=_ratio(samples_with_odds, len(samples)),
        by_league=by_league,
        by_season=by_season,
        by_weight=by_weight,
    )

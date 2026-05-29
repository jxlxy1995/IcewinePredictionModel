from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from statistics import median

from sqlalchemy.orm import Session

from icewine_prediction.models import Match, OddsSnapshot


@dataclass(frozen=True)
class BaseFeatures:
    home_attack_strength: Decimal
    away_attack_strength: Decimal
    home_defense_strength: Decimal
    away_defense_strength: Decimal


@dataclass(frozen=True)
class OddsMarketAggregate:
    sample_count: int
    mean: Decimal | None
    median: Decimal | None
    minimum: Decimal | None
    maximum: Decimal | None
    disagreement: Decimal | None


@dataclass(frozen=True)
class MatchOddsFeatures:
    match_id: int
    bookmaker_count: int
    asian_handicap: OddsMarketAggregate
    home_odds: OddsMarketAggregate
    away_odds: OddsMarketAggregate
    total_line: OddsMarketAggregate
    over_odds: OddsMarketAggregate
    under_odds: OddsMarketAggregate
    match_winner_home_odds: OddsMarketAggregate
    match_winner_draw_odds: OddsMarketAggregate
    match_winner_away_odds: OddsMarketAggregate


@dataclass(frozen=True)
class MatchOddsFeatureRow:
    match: Match
    features: MatchOddsFeatures


def default_base_features() -> BaseFeatures:
    return BaseFeatures(
        home_attack_strength=Decimal("1.00"),
        away_attack_strength=Decimal("1.00"),
        home_defense_strength=Decimal("1.00"),
        away_defense_strength=Decimal("1.00"),
    )


def _round_decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def is_standard_market_line(value: Decimal) -> bool:
    return (value * Decimal("4")) == (value * Decimal("4")).to_integral_value()


def _aggregate_decimal_values(values: list[Decimal]) -> OddsMarketAggregate:
    if not values:
        return OddsMarketAggregate(
            sample_count=0,
            mean=None,
            median=None,
            minimum=None,
            maximum=None,
            disagreement=None,
        )
    minimum = min(values)
    maximum = max(values)
    return OddsMarketAggregate(
        sample_count=len(values),
        mean=_round_decimal(sum(values) / Decimal(len(values))),
        median=_round_decimal(Decimal(str(median(values)))),
        minimum=_round_decimal(minimum),
        maximum=_round_decimal(maximum),
        disagreement=_round_decimal(maximum - minimum),
    )


def _select_main_market_line(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    counts = Counter(values)
    max_count = max(counts.values())
    candidates = [value for value, count in counts.items() if count == max_count]
    market_median = Decimal(str(median(values)))
    return min(candidates, key=lambda value: (abs(value - market_median), abs(value)))


def _aggregate_main_market_line(values: list[Decimal]) -> OddsMarketAggregate:
    main_line = _select_main_market_line(values)
    aggregate = _aggregate_decimal_values(values)
    if main_line is None:
        return aggregate
    return OddsMarketAggregate(
        sample_count=aggregate.sample_count,
        mean=_round_decimal(main_line),
        median=_round_decimal(main_line),
        minimum=aggregate.minimum,
        maximum=aggregate.maximum,
        disagreement=aggregate.disagreement,
    )


def build_match_odds_features(match: Match) -> MatchOddsFeatures:
    snapshots = list(match.odds_snapshots)
    asian_handicap_snapshots = [
        snapshot
        for snapshot in snapshots
        if snapshot.asian_handicap is not None and is_standard_market_line(snapshot.asian_handicap)
    ]
    total_line_snapshots = [
        snapshot
        for snapshot in snapshots
        if snapshot.total_line is not None and is_standard_market_line(snapshot.total_line)
    ]
    main_asian_handicap = _select_main_market_line(
        [snapshot.asian_handicap for snapshot in asian_handicap_snapshots]
    )
    main_total_line = _select_main_market_line(
        [snapshot.total_line for snapshot in total_line_snapshots]
    )
    match_winner_snapshots = [
        snapshot
        for snapshot in snapshots
        if (
            snapshot.match_winner_home_odds is not None
            or snapshot.match_winner_draw_odds is not None
            or snapshot.match_winner_away_odds is not None
        )
    ]
    main_asian_handicap_snapshots = [
        snapshot
        for snapshot in asian_handicap_snapshots
        if snapshot.asian_handicap == main_asian_handicap
    ]
    main_total_line_snapshots = [
        snapshot for snapshot in total_line_snapshots if snapshot.total_line == main_total_line
    ]
    valid_bookmakers = {
        snapshot.bookmaker
        for snapshot in asian_handicap_snapshots + total_line_snapshots + match_winner_snapshots
    }
    return MatchOddsFeatures(
        match_id=match.id,
        bookmaker_count=len(valid_bookmakers),
        asian_handicap=_aggregate_main_market_line(
            [snapshot.asian_handicap for snapshot in asian_handicap_snapshots]
        ),
        home_odds=_aggregate_decimal_values(
            [
                snapshot.home_odds
                for snapshot in main_asian_handicap_snapshots
                if snapshot.home_odds is not None
            ]
        ),
        away_odds=_aggregate_decimal_values(
            [
                snapshot.away_odds
                for snapshot in main_asian_handicap_snapshots
                if snapshot.away_odds is not None
            ]
        ),
        total_line=_aggregate_main_market_line(
            [snapshot.total_line for snapshot in total_line_snapshots]
        ),
        over_odds=_aggregate_decimal_values(
            [
                snapshot.over_odds
                for snapshot in main_total_line_snapshots
                if snapshot.over_odds is not None
            ]
        ),
        under_odds=_aggregate_decimal_values(
            [
                snapshot.under_odds
                for snapshot in main_total_line_snapshots
                if snapshot.under_odds is not None
            ]
        ),
        match_winner_home_odds=_aggregate_decimal_values(
            [
                snapshot.match_winner_home_odds
                for snapshot in snapshots
                if snapshot.match_winner_home_odds is not None
            ]
        ),
        match_winner_draw_odds=_aggregate_decimal_values(
            [
                snapshot.match_winner_draw_odds
                for snapshot in snapshots
                if snapshot.match_winner_draw_odds is not None
            ]
        ),
        match_winner_away_odds=_aggregate_decimal_values(
            [
                snapshot.match_winner_away_odds
                for snapshot in snapshots
                if snapshot.match_winner_away_odds is not None
            ]
        ),
    )


def list_upcoming_match_odds_features(
    session: Session,
    start_time: datetime,
    hours: int,
) -> list[MatchOddsFeatureRow]:
    end_time = start_time + timedelta(hours=hours)
    matches = (
        session.query(Match)
        .join(OddsSnapshot)
        .filter(Match.status == "scheduled")
        .filter(Match.kickoff_time >= start_time)
        .filter(Match.kickoff_time <= end_time)
        .order_by(Match.kickoff_time.asc())
        .distinct()
        .all()
    )
    return [
        MatchOddsFeatureRow(match=match, features=build_match_odds_features(match))
        for match in matches
    ]

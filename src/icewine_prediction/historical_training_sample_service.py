from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session, joinedload

from icewine_prediction.models import HistoricalOddsSnapshot, Match
from icewine_prediction.odds_provider_selection_service import filter_priority_pinnacle_snapshots
from icewine_prediction.settlement_service import settle_asian_handicap, settle_total_goals


DEFAULT_ANCHORS = (
    ("24h", 24 * 60),
    ("12h", 12 * 60),
    ("6h", 6 * 60),
    ("3h", 3 * 60),
    ("1h", 60),
    ("15m", 15),
    ("close", 5),
)
THIN_HISTORY_OUTCOME_THRESHOLD = 30
ODDS_QUANT = Decimal("0.0001")


@dataclass(frozen=True)
class HistoricalOddsAnchorFeature:
    label: str
    target_minutes_before_kickoff: int
    actual_minutes_before_kickoff: int
    snapshot_time: datetime
    bookmaker: str
    market_line: Decimal
    side_a: str
    side_b: str
    side_a_odds: Decimal
    side_b_odds: Decimal
    side_a_implied_probability: Decimal
    side_b_implied_probability: Decimal
    overround: Decimal
    side_a_result: str
    side_b_result: str
    side_c: str | None = None
    side_c_odds: Decimal | None = None
    side_c_implied_probability: Decimal | None = None
    side_c_result: str | None = None


@dataclass(frozen=True)
class HistoricalMarketTrainingSample:
    match_id: int
    source_match_id: str | None
    league_name: str
    home_team_name: str
    away_team_name: str
    kickoff_time: datetime
    home_score: int
    away_score: int
    market_type: str
    bookmaker: str
    snapshot_count: int
    anchors: tuple[HistoricalOddsAnchorFeature, ...]
    missing_anchor_labels: tuple[str, ...]
    quality_tags: tuple[str, ...]
    line_movement: Decimal | None
    side_a_odds_movement: Decimal | None
    side_b_odds_movement: Decimal | None
    side_c_odds_movement: Decimal | None = None


@dataclass(frozen=True)
class _PairedMarketSnapshot:
    snapshot_time: datetime
    bookmaker: str
    market_type: str
    market_line: Decimal
    side_a: str
    side_b: str
    side_a_odds: Decimal
    side_b_odds: Decimal
    side_c: str | None = None
    side_c_odds: Decimal | None = None

    @property
    def balance_gap(self) -> Decimal:
        if self.side_c_odds is not None:
            odds = [self.side_a_odds, self.side_b_odds, self.side_c_odds]
            return max(odds) - min(odds)
        return abs(self.side_a_odds - self.side_b_odds)


def list_historical_market_training_samples(
    session: Session,
    *,
    season: int | None = None,
    limit: int | None = None,
    source_name: str | None = "oddspapi",
    bookmaker: str = "pinnacle",
    use_pinnacle_provider_priority: bool = False,
) -> list[HistoricalMarketTrainingSample]:
    query = (
        session.query(Match)
        .options(
            joinedload(Match.league),
            joinedload(Match.home_team),
            joinedload(Match.away_team),
        )
        .filter(Match.status == "finished")
        .filter(Match.home_score.isnot(None))
        .filter(Match.away_score.isnot(None))
        .order_by(Match.kickoff_time.desc(), Match.id.desc())
    )
    if season is not None:
        query = query.filter(Match.season == season)
    if limit is not None:
        query = query.limit(limit)
    matches = query.all()
    snapshots_by_match_id = _load_historical_snapshots(
        session,
        match_ids=[match.id for match in matches],
        source_name=source_name,
        bookmaker=bookmaker,
        use_pinnacle_provider_priority=use_pinnacle_provider_priority,
    )
    samples: list[HistoricalMarketTrainingSample] = []
    for match in matches:
        match_snapshots = snapshots_by_match_id.get(match.id, [])
        for market_type in ("asian_handicap", "total_goals", "match_winner"):
            sample = _build_market_sample(
                match=match,
                market_type=market_type,
                snapshots=[
                    snapshot
                    for snapshot in match_snapshots
                    if snapshot.market_type == market_type
                ],
                bookmaker=bookmaker,
            )
            if sample is not None:
                samples.append(sample)
    return samples


def _load_historical_snapshots(
    session: Session,
    *,
    match_ids: list[int],
    source_name: str | None,
    bookmaker: str,
    use_pinnacle_provider_priority: bool = False,
) -> dict[int, list[HistoricalOddsSnapshot]]:
    if not match_ids:
        return {}
    query = (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id.in_(match_ids))
        .filter(HistoricalOddsSnapshot.bookmaker == bookmaker)
    )
    if source_name is not None:
        query = query.filter(HistoricalOddsSnapshot.source_name == source_name)
    snapshots = query.order_by(HistoricalOddsSnapshot.snapshot_time.asc()).all()
    if use_pinnacle_provider_priority:
        snapshots = filter_priority_pinnacle_snapshots(snapshots, bookmaker=bookmaker)
    snapshots_by_match_id: dict[int, list[HistoricalOddsSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        snapshots_by_match_id[snapshot.match_id].append(snapshot)
    return snapshots_by_match_id


def _build_market_sample(
    *,
    match: Match,
    market_type: str,
    snapshots: list[HistoricalOddsSnapshot],
    bookmaker: str,
) -> HistoricalMarketTrainingSample | None:
    kickoff_time = _comparable_datetime(match.kickoff_time)
    pre_match_snapshots = [
        snapshot
        for snapshot in snapshots
        if _comparable_datetime(snapshot.snapshot_time)
        <= kickoff_time - timedelta(minutes=DEFAULT_ANCHORS[-1][1])
    ]
    pairs = _pair_market_snapshots(pre_match_snapshots, market_type=market_type)
    if not pairs:
        return None

    anchors: list[HistoricalOddsAnchorFeature] = []
    missing_labels = []
    for label, minutes_before in DEFAULT_ANCHORS:
        target_time = kickoff_time - timedelta(minutes=minutes_before)
        pair = _select_pair_for_anchor(pairs, target_time=target_time)
        if pair is None:
            missing_labels.append(label)
            continue
        anchors.append(
            _build_anchor_feature(
                label=label,
                target_minutes_before_kickoff=minutes_before,
                pair=pair,
                match=match,
            )
        )
    if not anchors:
        return None

    quality_tags = []
    if len(pre_match_snapshots) < THIN_HISTORY_OUTCOME_THRESHOLD:
        quality_tags.append("thin_history")
    first_anchor = anchors[0]
    last_anchor = anchors[-1]
    return HistoricalMarketTrainingSample(
        match_id=match.id,
        source_match_id=match.source_match_id,
        league_name=match.league.name,
        home_team_name=match.home_team.canonical_name,
        away_team_name=match.away_team.canonical_name,
        kickoff_time=match.kickoff_time,
        home_score=match.home_score,
        away_score=match.away_score,
        market_type=market_type,
        bookmaker=bookmaker,
        snapshot_count=len(pre_match_snapshots),
        anchors=tuple(anchors),
        missing_anchor_labels=tuple(missing_labels),
        quality_tags=tuple(quality_tags),
        line_movement=_round_line(last_anchor.market_line - first_anchor.market_line),
        side_a_odds_movement=_round_probability(last_anchor.side_a_odds - first_anchor.side_a_odds),
        side_b_odds_movement=_round_probability(last_anchor.side_b_odds - first_anchor.side_b_odds),
        side_c_odds_movement=(
            _round_probability(last_anchor.side_c_odds - first_anchor.side_c_odds)
            if last_anchor.side_c_odds is not None and first_anchor.side_c_odds is not None
            else None
        ),
    )


def _pair_market_snapshots(
    snapshots: list[HistoricalOddsSnapshot],
    *,
    market_type: str,
) -> list[_PairedMarketSnapshot]:
    sides = _market_sides(market_type)
    grouped: dict[tuple[datetime, str, Decimal], dict[str, HistoricalOddsSnapshot]] = defaultdict(dict)
    for snapshot in snapshots:
        if snapshot.outcome_side in sides:
            grouped[(snapshot.snapshot_time, snapshot.bookmaker, snapshot.market_line)][
                snapshot.outcome_side
            ] = snapshot

    pairs = []
    for (snapshot_time, bookmaker, market_line), by_side in grouped.items():
        side_snapshots = [by_side.get(side) for side in sides]
        if any(snapshot is None for snapshot in side_snapshots):
            continue
        first = side_snapshots[0]
        second = side_snapshots[1]
        third = side_snapshots[2] if len(side_snapshots) == 3 else None
        if first is None or second is None:
            continue
        pairs.append(
            _PairedMarketSnapshot(
                snapshot_time=snapshot_time,
                bookmaker=bookmaker,
                market_type=market_type,
                market_line=market_line,
                side_a=sides[0],
                side_b=sides[1],
                side_a_odds=first.odds,
                side_b_odds=second.odds,
                side_c=sides[2] if third is not None else None,
                side_c_odds=third.odds if third is not None else None,
            )
        )
    return sorted(pairs, key=lambda pair: (pair.snapshot_time, pair.balance_gap))


def _select_pair_for_anchor(
    pairs: list[_PairedMarketSnapshot],
    *,
    target_time: datetime,
) -> _PairedMarketSnapshot | None:
    candidates = [
        pair for pair in pairs if _comparable_datetime(pair.snapshot_time) <= target_time
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda pair: (pair.snapshot_time, -pair.balance_gap))


def _build_anchor_feature(
    *,
    label: str,
    target_minutes_before_kickoff: int,
    pair: _PairedMarketSnapshot,
    match: Match,
) -> HistoricalOddsAnchorFeature:
    side_a_implied = _implied_probability(pair.side_a_odds)
    side_b_implied = _implied_probability(pair.side_b_odds)
    side_c_implied = (
        _implied_probability(pair.side_c_odds)
        if pair.side_c_odds is not None
        else None
    )
    return HistoricalOddsAnchorFeature(
        label=label,
        target_minutes_before_kickoff=target_minutes_before_kickoff,
        actual_minutes_before_kickoff=max(
            0,
            int(
                (
                    _comparable_datetime(match.kickoff_time)
                    - _comparable_datetime(pair.snapshot_time)
                ).total_seconds()
                // 60
            ),
        ),
        snapshot_time=pair.snapshot_time,
        bookmaker=pair.bookmaker,
        market_line=pair.market_line,
        side_a=pair.side_a,
        side_b=pair.side_b,
        side_a_odds=pair.side_a_odds,
        side_b_odds=pair.side_b_odds,
        side_a_implied_probability=side_a_implied,
        side_b_implied_probability=side_b_implied,
        overround=_round_probability(side_a_implied + side_b_implied + (side_c_implied or Decimal("0"))),
        side_a_result=_settle_pair_side(match, pair, pair.side_a),
        side_b_result=_settle_pair_side(match, pair, pair.side_b),
        side_c=pair.side_c,
        side_c_odds=pair.side_c_odds,
        side_c_implied_probability=side_c_implied,
        side_c_result=(
            _settle_pair_side(match, pair, pair.side_c)
            if pair.side_c is not None
            else None
        ),
    )


def _settle_pair_side(match: Match, pair: _PairedMarketSnapshot, side: str) -> str:
    if pair.market_type == "asian_handicap":
        return settle_asian_handicap(
            match.home_score,
            match.away_score,
            pair.market_line,
            side,
        )
    if pair.market_type == "total_goals":
        return settle_total_goals(
            match.home_score,
            match.away_score,
            pair.market_line,
            side,
        )
    if pair.market_type == "match_winner":
        return _settle_match_winner(match, side)
    raise ValueError(f"unsupported historical market type: {pair.market_type}")


def _settle_match_winner(match: Match, side: str) -> str:
    if match.home_score > match.away_score:
        winning_side = "home"
    elif match.home_score < match.away_score:
        winning_side = "away"
    else:
        winning_side = "draw"
    return "win" if side == winning_side else "loss"


def _market_sides(market_type: str) -> tuple[str, ...]:
    if market_type == "asian_handicap":
        return "home", "away"
    if market_type == "total_goals":
        return "over", "under"
    if market_type == "match_winner":
        return "home", "draw", "away"
    raise ValueError(f"unsupported historical market type: {market_type}")


def _implied_probability(odds: Decimal) -> Decimal:
    return _round_probability(Decimal("1") / odds)


def _round_probability(value: Decimal) -> Decimal:
    return value.quantize(ODDS_QUANT, rounding=ROUND_HALF_UP)


def _round_line(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _comparable_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from icewine_prediction.historical_training_sample_service import (
    HistoricalMarketTrainingSample,
    HistoricalOddsAnchorFeature,
    list_historical_market_training_samples,
)


PROBABILITY_QUANT = Decimal("0.0001")


@dataclass(frozen=True)
class HistoricalOddsMarketFeature:
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
    opening_anchor_label: str
    close_anchor_label: str
    opening_market_line: Decimal
    close_market_line: Decimal
    line_movement: Decimal | None
    side_a: str
    side_b: str
    side_c: str | None
    opening_side_a_implied_probability: Decimal
    opening_side_b_implied_probability: Decimal
    opening_side_c_implied_probability: Decimal | None
    close_side_a_implied_probability: Decimal
    close_side_b_implied_probability: Decimal
    close_side_c_implied_probability: Decimal | None
    side_a_implied_probability_movement: Decimal
    side_b_implied_probability_movement: Decimal
    side_c_implied_probability_movement: Decimal | None
    opening_overround: Decimal
    close_overround: Decimal
    side_a_odds_movement: Decimal | None
    side_b_odds_movement: Decimal | None
    side_c_odds_movement: Decimal | None
    close_side_a_result: str
    close_side_b_result: str
    close_side_c_result: str | None
    snapshot_count: int
    missing_anchor_labels: tuple[str, ...]
    quality_tags: tuple[str, ...]


def list_historical_odds_market_features(
    session: Session,
    *,
    season: int | None = None,
    limit: int | None = None,
    source_name: str = "oddspapi",
    bookmaker: str = "pinnacle",
) -> list[HistoricalOddsMarketFeature]:
    samples = list_historical_market_training_samples(
        session,
        season=season,
        limit=limit,
        source_name=source_name,
        bookmaker=bookmaker,
    )
    return build_historical_odds_market_features(samples)


def build_historical_odds_market_features(
    samples: list[HistoricalMarketTrainingSample],
) -> list[HistoricalOddsMarketFeature]:
    features = []
    for sample in samples:
        feature = _build_feature(sample)
        if feature is not None:
            features.append(feature)
    return features


def _build_feature(
    sample: HistoricalMarketTrainingSample,
) -> HistoricalOddsMarketFeature | None:
    if not sample.anchors:
        return None
    opening_anchor = sample.anchors[0]
    close_anchor = sample.anchors[-1]
    return HistoricalOddsMarketFeature(
        match_id=sample.match_id,
        source_match_id=sample.source_match_id,
        league_name=sample.league_name,
        home_team_name=sample.home_team_name,
        away_team_name=sample.away_team_name,
        kickoff_time=sample.kickoff_time,
        home_score=sample.home_score,
        away_score=sample.away_score,
        market_type=sample.market_type,
        bookmaker=sample.bookmaker,
        opening_anchor_label=opening_anchor.label,
        close_anchor_label=close_anchor.label,
        opening_market_line=opening_anchor.market_line,
        close_market_line=close_anchor.market_line,
        line_movement=sample.line_movement,
        side_a=close_anchor.side_a,
        side_b=close_anchor.side_b,
        side_c=close_anchor.side_c,
        opening_side_a_implied_probability=opening_anchor.side_a_implied_probability,
        opening_side_b_implied_probability=opening_anchor.side_b_implied_probability,
        opening_side_c_implied_probability=opening_anchor.side_c_implied_probability,
        close_side_a_implied_probability=close_anchor.side_a_implied_probability,
        close_side_b_implied_probability=close_anchor.side_b_implied_probability,
        close_side_c_implied_probability=close_anchor.side_c_implied_probability,
        side_a_implied_probability_movement=_probability_movement(
            close_anchor.side_a_implied_probability,
            opening_anchor.side_a_implied_probability,
        ),
        side_b_implied_probability_movement=_probability_movement(
            close_anchor.side_b_implied_probability,
            opening_anchor.side_b_implied_probability,
        ),
        side_c_implied_probability_movement=_optional_probability_movement(
            close_anchor,
            opening_anchor,
        ),
        opening_overround=opening_anchor.overround,
        close_overround=close_anchor.overround,
        side_a_odds_movement=sample.side_a_odds_movement,
        side_b_odds_movement=sample.side_b_odds_movement,
        side_c_odds_movement=sample.side_c_odds_movement,
        close_side_a_result=close_anchor.side_a_result,
        close_side_b_result=close_anchor.side_b_result,
        close_side_c_result=close_anchor.side_c_result,
        snapshot_count=sample.snapshot_count,
        missing_anchor_labels=sample.missing_anchor_labels,
        quality_tags=sample.quality_tags,
    )


def _optional_probability_movement(
    close_anchor: HistoricalOddsAnchorFeature,
    opening_anchor: HistoricalOddsAnchorFeature,
) -> Decimal | None:
    if (
        close_anchor.side_c_implied_probability is None
        or opening_anchor.side_c_implied_probability is None
    ):
        return None
    return _probability_movement(
        close_anchor.side_c_implied_probability,
        opening_anchor.side_c_implied_probability,
    )


def _probability_movement(close_probability: Decimal, opening_probability: Decimal) -> Decimal:
    return (close_probability - opening_probability).quantize(
        PROBABILITY_QUANT,
        rounding=ROUND_HALF_UP,
    )

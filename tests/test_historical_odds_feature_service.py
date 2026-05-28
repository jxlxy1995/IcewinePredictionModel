from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.historical_odds_feature_service import (
    build_historical_odds_market_features,
)
from icewine_prediction.historical_training_sample_service import (
    HistoricalMarketTrainingSample,
    HistoricalOddsAnchorFeature,
)


BEIJING = ZoneInfo("Asia/Shanghai")


def test_build_historical_odds_market_features_extracts_opening_and_close_probabilities():
    sample = _sample(
        market_type="match_winner",
        anchors=(
            _anchor(
                "24h",
                side_a="home",
                side_b="draw",
                side_c="away",
                side_a_odds=Decimal("2.00"),
                side_b_odds=Decimal("4.00"),
                side_c_odds=Decimal("4.00"),
                side_a_result="win",
                side_b_result="loss",
                side_c_result="loss",
            ),
            _anchor(
                "close",
                side_a="home",
                side_b="draw",
                side_c="away",
                side_a_odds=Decimal("1.80"),
                side_b_odds=Decimal("4.00"),
                side_c_odds=Decimal("5.00"),
                side_a_result="win",
                side_b_result="loss",
                side_c_result="loss",
            ),
        ),
    )

    features = build_historical_odds_market_features([sample])

    assert len(features) == 1
    feature = features[0]
    assert feature.market_type == "match_winner"
    assert feature.opening_anchor_label == "24h"
    assert feature.close_anchor_label == "close"
    assert feature.side_a == "home"
    assert feature.side_b == "draw"
    assert feature.side_c == "away"
    assert feature.opening_side_a_implied_probability == Decimal("0.5000")
    assert feature.close_side_a_implied_probability == Decimal("0.5556")
    assert feature.side_a_implied_probability_movement == Decimal("0.0556")
    assert feature.opening_overround == Decimal("1.0000")
    assert feature.close_overround == Decimal("1.0056")
    assert feature.close_side_a_result == "win"
    assert feature.close_side_c_result == "loss"
    assert feature.line_movement == Decimal("0.00")
    assert feature.side_a_odds_movement == Decimal("-0.2000")


def test_build_historical_odds_market_features_skips_samples_without_anchors():
    sample = _sample(market_type="asian_handicap", anchors=())

    assert build_historical_odds_market_features([sample]) == []


def _sample(
    *,
    market_type: str,
    anchors: tuple[HistoricalOddsAnchorFeature, ...],
) -> HistoricalMarketTrainingSample:
    return HistoricalMarketTrainingSample(
        match_id=1,
        source_match_id="1001",
        league_name="Premier League",
        home_team_name="Arsenal",
        away_team_name="Chelsea",
        kickoff_time=datetime(2026, 5, 20, 20, 0, tzinfo=BEIJING),
        home_score=2,
        away_score=1,
        market_type=market_type,
        bookmaker="pinnacle",
        snapshot_count=60,
        anchors=anchors,
        missing_anchor_labels=(),
        quality_tags=(),
        line_movement=Decimal("0.00"),
        side_a_odds_movement=Decimal("-0.2000"),
        side_b_odds_movement=Decimal("0.0000"),
        side_c_odds_movement=Decimal("1.0000"),
    )


def _anchor(
    label: str,
    *,
    side_a: str,
    side_b: str,
    side_c: str | None,
    side_a_odds: Decimal,
    side_b_odds: Decimal,
    side_c_odds: Decimal | None,
    side_a_result: str,
    side_b_result: str,
    side_c_result: str | None,
) -> HistoricalOddsAnchorFeature:
    side_a_implied = _implied(side_a_odds)
    side_b_implied = _implied(side_b_odds)
    side_c_implied = _implied(side_c_odds) if side_c_odds is not None else None
    return HistoricalOddsAnchorFeature(
        label=label,
        target_minutes_before_kickoff=1440 if label == "24h" else 5,
        actual_minutes_before_kickoff=1440 if label == "24h" else 7,
        snapshot_time=datetime(2026, 5, 20, 19, 53, tzinfo=BEIJING),
        bookmaker="pinnacle",
        market_line=Decimal("0.00"),
        side_a=side_a,
        side_b=side_b,
        side_a_odds=side_a_odds,
        side_b_odds=side_b_odds,
        side_a_implied_probability=side_a_implied,
        side_b_implied_probability=side_b_implied,
        overround=side_a_implied + side_b_implied + (side_c_implied or Decimal("0")),
        side_a_result=side_a_result,
        side_b_result=side_b_result,
        side_c=side_c,
        side_c_odds=side_c_odds,
        side_c_implied_probability=side_c_implied,
        side_c_result=side_c_result,
    )


def _implied(odds: Decimal) -> Decimal:
    return (Decimal("1") / odds).quantize(Decimal("0.0001"))

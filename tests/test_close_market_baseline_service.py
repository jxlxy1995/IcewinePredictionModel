from datetime import datetime
from decimal import Decimal
from math import log
from zoneinfo import ZoneInfo

from icewine_prediction.close_market_baseline_service import (
    build_close_market_baseline_report,
    format_close_market_baseline_report,
)
from icewine_prediction.historical_odds_feature_service import HistoricalOddsMarketFeature


BEIJING = ZoneInfo("Asia/Shanghai")


def test_build_close_market_baseline_report_evaluates_three_way_and_two_way_markets():
    features = [
        _feature(
            market_type="match_winner",
            probabilities=(Decimal("0.5556"), Decimal("0.2500"), Decimal("0.2000")),
            results=("win", "loss", "loss"),
        ),
        _feature(
            market_type="asian_handicap",
            probabilities=(Decimal("0.6000"), Decimal("0.4000"), None),
            results=("win", "loss", None),
        ),
        _feature(
            market_type="total_goals",
            probabilities=(Decimal("0.5000"), Decimal("0.5000"), None),
            results=("push", "push", None),
        ),
    ]

    report = build_close_market_baseline_report(features)

    assert report.total_feature_count == 3
    assert report.evaluated_sample_count == 2
    assert report.skipped_sample_count == 1
    match_winner = report.market_reports["match_winner"]
    assert match_winner.evaluated_sample_count == 1
    assert match_winner.skipped_sample_count == 0
    assert match_winner.average_log_loss == _log_loss((Decimal("0.5556"), Decimal("0.2500"), Decimal("0.2000")), 0)
    assert match_winner.average_brier_score == _brier((Decimal("0.5556"), Decimal("0.2500"), Decimal("0.2000")), 0)
    assert match_winner.accuracy == Decimal("1.0000")
    asian = report.market_reports["asian_handicap"]
    assert asian.evaluated_sample_count == 1
    assert asian.average_log_loss == _log_loss((Decimal("0.6000"), Decimal("0.4000")), 0)
    assert asian.average_brier_score == _brier((Decimal("0.6000"), Decimal("0.4000")), 0)
    assert report.market_reports["total_goals"].evaluated_sample_count == 0
    assert report.market_reports["total_goals"].skipped_sample_count == 1


def test_build_close_market_baseline_report_scores_half_win_and_half_loss():
    features = [
        _feature(
            market_type="total_goals",
            probabilities=(Decimal("0.6000"), Decimal("0.4000"), None),
            results=("half_win", "half_loss", None),
        ),
        _feature(
            market_type="total_goals",
            probabilities=(Decimal("0.6000"), Decimal("0.4000"), None),
            results=("half_loss", "half_win", None),
        ),
    ]

    report = build_close_market_baseline_report(features)

    total_goals = report.market_reports["total_goals"]
    assert total_goals.evaluated_sample_count == 2
    assert total_goals.skipped_sample_count == 0
    assert total_goals.accuracy == Decimal("0.5000")
    assert total_goals.average_log_loss == _average(
        [
            _binary_soft_log_loss(Decimal("0.6000"), Decimal("0.75")),
            _binary_soft_log_loss(Decimal("0.6000"), Decimal("0.25")),
        ]
    )
    assert total_goals.average_brier_score == _average(
        [
            _binary_soft_brier(Decimal("0.6000"), Decimal("0.75")),
            _binary_soft_brier(Decimal("0.6000"), Decimal("0.25")),
        ]
    )


def test_format_close_market_baseline_report_summarizes_market_metrics():
    report = build_close_market_baseline_report(
        [
            _feature(
                market_type="match_winner",
                probabilities=(Decimal("0.5556"), Decimal("0.2500"), Decimal("0.2000")),
                results=("win", "loss", "loss"),
            )
        ]
    )

    text = format_close_market_baseline_report(report)

    assert "close market baseline" in text
    assert "features 1 evaluated 1 skipped 0" in text
    assert "match_winner: evaluated 1 skipped 0" in text
    assert "accuracy 1.0000" in text
    assert "log_loss" in text
    assert "brier" in text


def _feature(
    *,
    market_type: str,
    probabilities: tuple[Decimal, Decimal, Decimal | None],
    results: tuple[str, str, str | None],
) -> HistoricalOddsMarketFeature:
    side_c = "away" if market_type == "match_winner" else None
    return HistoricalOddsMarketFeature(
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
        opening_anchor_label="24h",
        close_anchor_label="close",
        opening_market_line=Decimal("0.00"),
        close_market_line=Decimal("0.00"),
        line_movement=Decimal("0.00"),
        side_a="home" if market_type != "total_goals" else "over",
        side_b="draw" if market_type == "match_winner" else ("away" if market_type == "asian_handicap" else "under"),
        side_c=side_c,
        opening_side_a_implied_probability=probabilities[0],
        opening_side_b_implied_probability=probabilities[1],
        opening_side_c_implied_probability=probabilities[2],
        close_side_a_implied_probability=probabilities[0],
        close_side_b_implied_probability=probabilities[1],
        close_side_c_implied_probability=probabilities[2],
        side_a_implied_probability_movement=Decimal("0.0000"),
        side_b_implied_probability_movement=Decimal("0.0000"),
        side_c_implied_probability_movement=Decimal("0.0000") if probabilities[2] is not None else None,
        opening_overround=sum(probability for probability in probabilities if probability is not None),
        close_overround=sum(probability for probability in probabilities if probability is not None),
        side_a_odds_movement=Decimal("0.0000"),
        side_b_odds_movement=Decimal("0.0000"),
        side_c_odds_movement=Decimal("0.0000") if probabilities[2] is not None else None,
        close_side_a_result=results[0],
        close_side_b_result=results[1],
        close_side_c_result=results[2],
        snapshot_count=60,
        missing_anchor_labels=(),
        quality_tags=(),
    )


def _log_loss(probabilities: tuple[Decimal, ...], actual_index: int) -> Decimal:
    normalized = _normalize(probabilities)
    return Decimal(str(-log(float(normalized[actual_index])))).quantize(Decimal("0.0001"))


def _brier(probabilities: tuple[Decimal, ...], actual_index: int) -> Decimal:
    normalized = _normalize(probabilities)
    total = Decimal("0")
    for index, probability in enumerate(normalized):
        actual = Decimal("1") if index == actual_index else Decimal("0")
        total += (probability - actual) ** 2
    return total.quantize(Decimal("0.0001"))


def _binary_soft_log_loss(side_a_probability: Decimal, side_a_target: Decimal) -> Decimal:
    side_b_probability = Decimal("1") - side_a_probability
    value = -(
        side_a_target * Decimal(str(log(float(side_a_probability))))
        + (Decimal("1") - side_a_target)
        * Decimal(str(log(float(side_b_probability))))
    )
    return value.quantize(Decimal("0.0001"))


def _binary_soft_brier(side_a_probability: Decimal, side_a_target: Decimal) -> Decimal:
    side_b_probability = Decimal("1") - side_a_probability
    side_b_target = Decimal("1") - side_a_target
    return (
        (side_a_probability - side_a_target) ** 2
        + (side_b_probability - side_b_target) ** 2
    ).quantize(Decimal("0.0001"))


def _average(values: list[Decimal]) -> Decimal:
    return (sum(values) / Decimal(len(values))).quantize(Decimal("0.0001"))


def _normalize(probabilities: tuple[Decimal, ...]) -> tuple[Decimal, ...]:
    total = sum(probabilities)
    return tuple(probability / total for probability in probabilities)

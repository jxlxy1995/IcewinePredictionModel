from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.historical_training_sample_service import (
    list_historical_market_training_samples,
)
from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, Team


UTC = ZoneInfo("UTC")


def test_list_historical_market_training_samples_extracts_fixed_premarket_anchors(session):
    match = _add_finished_match(session)
    kickoff = match.kickoff_time
    for label, minutes, asian_line, total_line in [
        ("24h", 1440, Decimal("-0.25"), Decimal("2.50")),
        ("12h", 720, Decimal("-0.25"), Decimal("2.50")),
        ("6h", 360, Decimal("-0.50"), Decimal("2.50")),
        ("3h", 180, Decimal("-0.50"), Decimal("2.75")),
        ("1h", 60, Decimal("-0.50"), Decimal("2.75")),
        ("15m", 15, Decimal("-0.50"), Decimal("2.75")),
        ("close", 7, Decimal("-0.50"), Decimal("2.75")),
    ]:
        snapshot_time = kickoff - timedelta(minutes=minutes)
        _add_pair(
            session,
            match,
            market_type="asian_handicap",
            market_line=asian_line,
            snapshot_time=snapshot_time,
            side_a="home",
            side_b="away",
            side_a_odds=Decimal("1.90"),
            side_b_odds=Decimal("1.96"),
            market_id=f"ah-{label}",
        )
        _add_pair(
            session,
            match,
            market_type="total_goals",
            market_line=total_line,
            snapshot_time=snapshot_time,
            side_a="over",
            side_b="under",
            side_a_odds=Decimal("1.88"),
            side_b_odds=Decimal("2.00"),
            market_id=f"ou-{label}",
        )
    for index, minutes in enumerate(range(1500, 1620, 15), start=1):
        _add_pair(
            session,
            match,
            market_type="asian_handicap",
            market_line=Decimal("-0.25"),
            snapshot_time=kickoff - timedelta(minutes=minutes),
            side_a="home",
            side_b="away",
            side_a_odds=Decimal("1.92"),
            side_b_odds=Decimal("1.94"),
            market_id=f"ah-extra-{index}",
        )
    _add_pair(
        session,
        match,
        market_type="asian_handicap",
        market_line=Decimal("-0.75"),
        snapshot_time=kickoff + timedelta(minutes=1),
        side_a="home",
        side_b="away",
        side_a_odds=Decimal("1.90"),
        side_b_odds=Decimal("1.90"),
        market_id="ah-live",
    )
    session.commit()

    samples = list_historical_market_training_samples(session, season=2026)

    assert [sample.market_type for sample in samples] == ["asian_handicap", "total_goals"]
    asian_sample = samples[0]
    assert asian_sample.match_id == match.id
    assert asian_sample.snapshot_count == 30
    assert asian_sample.missing_anchor_labels == ()
    assert asian_sample.quality_tags == ()
    assert [anchor.label for anchor in asian_sample.anchors] == [
        "24h",
        "12h",
        "6h",
        "3h",
        "1h",
        "15m",
        "close",
    ]
    assert asian_sample.line_movement == Decimal("-0.25")
    assert asian_sample.anchors[-1].market_line == Decimal("-0.50")
    assert asian_sample.anchors[-1].side_a == "home"
    assert asian_sample.anchors[-1].side_a_result == "win"
    assert asian_sample.anchors[-1].side_b_result == "loss"
    assert asian_sample.anchors[-1].overround == Decimal("1.0365")

    total_sample = samples[1]
    assert total_sample.line_movement == Decimal("0.25")
    assert total_sample.anchors[-1].side_a == "over"
    assert total_sample.anchors[-1].side_a_result == "half_win"
    assert total_sample.anchors[-1].side_b_result == "half_loss"


def test_historical_market_training_sample_marks_sparse_history_and_ignores_post_kickoff(session):
    match = _add_finished_match(session)
    _add_pair(
        session,
        match,
        market_type="asian_handicap",
        market_line=Decimal("0.00"),
        snapshot_time=match.kickoff_time - timedelta(hours=12),
        side_a="home",
        side_b="away",
        side_a_odds=Decimal("1.91"),
        side_b_odds=Decimal("1.93"),
        market_id="ah-12h",
    )
    _add_pair(
        session,
        match,
        market_type="total_goals",
        market_line=Decimal("2.50"),
        snapshot_time=match.kickoff_time + timedelta(minutes=2),
        side_a="over",
        side_b="under",
        side_a_odds=Decimal("1.88"),
        side_b_odds=Decimal("1.98"),
        market_id="ou-live",
    )
    session.commit()

    samples = list_historical_market_training_samples(session, season=2026)

    assert len(samples) == 1
    assert samples[0].market_type == "asian_handicap"
    assert samples[0].snapshot_count == 2
    assert samples[0].missing_anchor_labels == ("24h",)
    assert samples[0].quality_tags == ("thin_history",)
    assert [anchor.label for anchor in samples[0].anchors] == [
        "12h",
        "6h",
        "3h",
        "1h",
        "15m",
        "close",
    ]


def test_historical_market_training_sample_extracts_match_winner_triplets(session):
    match = _add_finished_match(session)
    kickoff = match.kickoff_time
    for label, minutes, home_odds, draw_odds, away_odds in [
        ("24h", 1440, Decimal("2.20"), Decimal("3.10"), Decimal("3.30")),
        ("12h", 720, Decimal("2.10"), Decimal("3.20"), Decimal("3.40")),
        ("6h", 360, Decimal("2.05"), Decimal("3.25"), Decimal("3.50")),
        ("3h", 180, Decimal("2.00"), Decimal("3.30"), Decimal("3.60")),
        ("1h", 60, Decimal("1.95"), Decimal("3.35"), Decimal("3.70")),
        ("15m", 15, Decimal("1.92"), Decimal("3.40"), Decimal("3.80")),
        ("close", 7, Decimal("1.90"), Decimal("3.50"), Decimal("3.90")),
    ]:
        _add_triplet(
            session,
            match,
            snapshot_time=kickoff - timedelta(minutes=minutes),
            home_odds=home_odds,
            draw_odds=draw_odds,
            away_odds=away_odds,
            market_id=f"1x2-{label}",
        )
    session.commit()

    samples = list_historical_market_training_samples(session, season=2026)

    assert [sample.market_type for sample in samples] == ["match_winner"]
    sample = samples[0]
    assert sample.snapshot_count == 21
    assert sample.missing_anchor_labels == ()
    assert sample.quality_tags == ("thin_history",)
    assert sample.line_movement == Decimal("0.00")
    assert sample.side_a_odds_movement == Decimal("-0.3000")
    assert sample.side_b_odds_movement == Decimal("0.4000")
    assert [anchor.label for anchor in sample.anchors] == [
        "24h",
        "12h",
        "6h",
        "3h",
        "1h",
        "15m",
        "close",
    ]
    assert sample.anchors[-1].side_a == "home"
    assert sample.anchors[-1].side_b == "draw"
    assert sample.anchors[-1].side_c == "away"
    assert sample.anchors[-1].side_a_result == "win"
    assert sample.anchors[-1].side_b_result == "loss"
    assert sample.anchors[-1].side_c_result == "loss"


def _add_finished_match(session) -> Match:
    league = League(name="Premier League", country_or_region="England", level=1)
    home = Team(canonical_name="Arsenal")
    away = Team(canonical_name="Chelsea")
    session.add_all([league, home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 5, 20, 20, 0, tzinfo=UTC),
        season=2026,
        status="finished",
        home_score=2,
        away_score=1,
        source_name="api-football",
        source_match_id="1001",
    )
    session.add(match)
    session.flush()
    return match


def _add_pair(
    session,
    match: Match,
    *,
    market_type: str,
    market_line: Decimal,
    snapshot_time: datetime,
    side_a: str,
    side_b: str,
    side_a_odds: Decimal,
    side_b_odds: Decimal,
    market_id: str,
) -> None:
    for side, odds in [(side_a, side_a_odds), (side_b, side_b_odds)]:
        session.add(
            HistoricalOddsSnapshot(
                match_id=match.id,
                source_name="oddspapi",
                source_fixture_id="fixture-1",
                bookmaker="pinnacle",
                market_type=market_type,
                market_id=market_id,
                market_name=market_type,
                market_line=market_line,
                outcome_side=side,
                odds=odds,
                snapshot_time=snapshot_time,
                period="fulltime",
            )
        )


def _add_triplet(
    session,
    match: Match,
    *,
    snapshot_time: datetime,
    home_odds: Decimal,
    draw_odds: Decimal,
    away_odds: Decimal,
    market_id: str,
) -> None:
    for side, odds in [
        ("home", home_odds),
        ("draw", draw_odds),
        ("away", away_odds),
    ]:
        session.add(
            HistoricalOddsSnapshot(
                match_id=match.id,
                source_name="oddspapi",
                source_fixture_id="fixture-1",
                bookmaker="pinnacle",
                market_type="match_winner",
                market_id=market_id,
                market_name="Match Winner",
                market_line=Decimal("0.00"),
                outcome_side=side,
                odds=odds,
                snapshot_time=snapshot_time,
                period="fulltime",
            )
        )

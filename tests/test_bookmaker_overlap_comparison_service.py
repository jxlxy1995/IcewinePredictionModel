from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.bookmaker_overlap_comparison_service import (
    build_bookmaker_overlap_comparison_report,
    format_bookmaker_overlap_comparison_report,
)
from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, Team


UTC = ZoneInfo("UTC")


def test_build_bookmaker_overlap_comparison_report_compares_close_anchors(session):
    match = _add_finished_match(session)
    close_time = match.kickoff_time - timedelta(minutes=7)
    _add_pair(
        session,
        match,
        bookmaker="pinnacle",
        market_type="asian_handicap",
        market_line=Decimal("-0.50"),
        snapshot_time=close_time,
        side_a="home",
        side_b="away",
        side_a_odds=Decimal("1.900"),
        side_b_odds=Decimal("1.960"),
        market_id="pin-ah-close",
    )
    _add_pair(
        session,
        match,
        bookmaker="sbobet",
        market_type="asian_handicap",
        market_line=Decimal("-0.50"),
        snapshot_time=close_time,
        side_a="home",
        side_b="away",
        side_a_odds=Decimal("1.920"),
        side_b_odds=Decimal("1.940"),
        market_id="sbo-ah-close",
    )
    _add_pair(
        session,
        match,
        bookmaker="pinnacle",
        market_type="total_goals",
        market_line=Decimal("3.50"),
        snapshot_time=close_time,
        side_a="over",
        side_b="under",
        side_a_odds=Decimal("1.880"),
        side_b_odds=Decimal("2.000"),
        market_id="pin-tg-close",
    )
    _add_pair(
        session,
        match,
        bookmaker="sbobet",
        market_type="total_goals",
        market_line=Decimal("3.75"),
        snapshot_time=close_time,
        side_a="over",
        side_b="under",
        side_a_odds=Decimal("1.930"),
        side_b_odds=Decimal("1.930"),
        market_id="sbo-tg-close",
    )
    session.commit()

    report = build_bookmaker_overlap_comparison_report(
        session,
        baseline_bookmaker="pinnacle",
        candidate_bookmaker="sbobet",
        season=2026,
    )

    assert report.baseline_bookmaker == "pinnacle"
    assert report.candidate_bookmaker == "sbobet"
    assert report.baseline_sample_count == 2
    assert report.candidate_sample_count == 2
    assert report.overlap_sample_count == 2
    assert report.coverage_ratio == Decimal("1.0000")
    asian = report.market_rows[0]
    assert asian.market_type == "asian_handicap"
    assert asian.overlap_sample_count == 1
    assert asian.avg_abs_line_diff == Decimal("0.0000")
    assert asian.avg_abs_side_a_devig_probability_diff == Decimal("0.0052")
    assert asian.baseline_close_accuracy == Decimal("1.0000")
    assert asian.candidate_close_accuracy == Decimal("1.0000")
    total = report.market_rows[1]
    assert total.market_type == "total_goals"
    assert total.avg_abs_line_diff == Decimal("0.2500")
    assert total.baseline_close_accuracy == Decimal("0.0000")
    assert total.candidate_close_accuracy == Decimal("0.0000")

    output = format_bookmaker_overlap_comparison_report(report)

    assert "# Bookmaker Overlap Comparison" in output
    assert "| asian_handicap | 1 | 0.0000 |" in output
    assert "| total_goals | 1 | 0.2500 |" in output


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
    bookmaker: str,
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
                bookmaker=bookmaker,
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

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.historical_odds_anchor_coverage_service import (
    CORE_ANCHOR_LABELS,
    build_historical_odds_anchor_coverage_report,
    format_historical_odds_anchor_coverage_report,
)
from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, Team


UTC = ZoneInfo("UTC")


def test_build_historical_odds_anchor_coverage_report_counts_core_anchors(session):
    league = League(name="Premier League", country_or_region="England", level=1)
    session.add(league)
    session.flush()
    complete_match = _add_match(
        session,
        league,
        kickoff_time=datetime(2026, 1, 20, 20, 0, tzinfo=UTC),
    )
    sparse_match = _add_match(
        session,
        league,
        kickoff_time=datetime(2026, 1, 21, 20, 0, tzinfo=UTC),
    )
    for label, minutes in [
        ("24h", 1440),
        ("12h", 720),
        ("6h", 360),
        ("3h", 180),
        ("1h", 60),
        ("close", 7),
    ]:
        _add_pair(
            session,
            complete_match,
            market_type="asian_handicap",
            market_line=Decimal("-0.25"),
            snapshot_time=complete_match.kickoff_time - timedelta(minutes=minutes),
            side_a="home",
            side_b="away",
            market_id=f"complete-ah-{label}",
        )
    for label, minutes in [
        ("12h", 720),
        ("6h", 360),
        ("3h", 180),
        ("1h", 60),
        ("close", 7),
    ]:
        _add_pair(
            session,
            sparse_match,
            market_type="asian_handicap",
            market_line=Decimal("0.00"),
            snapshot_time=sparse_match.kickoff_time - timedelta(minutes=minutes),
            side_a="home",
            side_b="away",
            market_id=f"sparse-ah-{label}",
        )
        _add_pair(
            session,
            sparse_match,
            market_type="total_goals",
            market_line=Decimal("2.50"),
            snapshot_time=sparse_match.kickoff_time - timedelta(minutes=minutes),
            side_a="over",
            side_b="under",
            market_id=f"sparse-ou-{label}",
        )
    session.commit()

    report = build_historical_odds_anchor_coverage_report(session, season=2026)

    assert report.eligible_match_count == 2
    assert report.anchor_labels == CORE_ANCHOR_LABELS
    asian = report.market_reports["asian_handicap"]
    assert asian.sample_count == 2
    assert asian.complete_core_anchor_sample_count == 1
    assert asian.complete_core_anchor_coverage_ratio == Decimal("0.5000")
    assert asian.anchor_reports["24h"].sample_count == 1
    assert asian.anchor_reports["24h"].coverage_ratio == Decimal("0.5000")
    assert asian.anchor_reports["24h"].sample_internal_coverage_ratio == Decimal("0.5000")
    assert asian.anchor_reports["12h"].sample_count == 2
    assert asian.anchor_reports["12h"].sample_internal_coverage_ratio == Decimal("1.0000")
    assert asian.anchor_reports["close"].coverage_ratio == Decimal("1.0000")
    total = report.market_reports["total_goals"]
    assert total.sample_count == 1
    assert total.anchor_reports["24h"].sample_count == 0
    assert total.anchor_reports["12h"].sample_count == 1


def test_format_historical_odds_anchor_coverage_report_outputs_markdown(session):
    league = League(name="La Liga", country_or_region="Spain", level=1)
    session.add(league)
    session.flush()
    match = _add_match(
        session,
        league,
        kickoff_time=datetime(2026, 1, 20, 20, 0, tzinfo=UTC),
    )
    _add_pair(
        session,
        match,
        market_type="total_goals",
        market_line=Decimal("2.50"),
        snapshot_time=match.kickoff_time - timedelta(hours=12),
        side_a="over",
        side_b="under",
        market_id="ou-12h",
    )
    session.commit()

    text = format_historical_odds_anchor_coverage_report(
        build_historical_odds_anchor_coverage_report(session, season=2026)
    )

    assert "# Historical Odds Anchor Coverage v1" in text
    assert "## total_goals" in text
    assert "| 12h | 1 | 1.0000 | 1.0000 |" in text
    assert "| 24h | 0 | 0.0000 | 0.0000 |" in text


def _add_match(session, league: League, *, kickoff_time: datetime) -> Match:
    suffix = kickoff_time.strftime("%Y%m%d%H%M")
    home = Team(canonical_name=f"Home {suffix}")
    away = Team(canonical_name=f"Away {suffix}")
    session.add_all([home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff_time,
        season=2026,
        status="finished",
        home_score=2,
        away_score=1,
        source_name="api-football",
        source_match_id=f"match-{suffix}",
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
    market_id: str,
) -> None:
    for side, odds in [(side_a, Decimal("1.90")), (side_b, Decimal("1.96"))]:
        session.add(
            HistoricalOddsSnapshot(
                match_id=match.id,
                source_name="oddspapi",
                source_fixture_id=f"fixture-{match.id}",
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

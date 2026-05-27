from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.historical_training_sample_report_service import (
    build_historical_odds_sample_quality_report,
    format_historical_odds_sample_quality_report,
)
from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, Team


BEIJING = ZoneInfo("Asia/Shanghai")


def test_historical_odds_sample_report_uses_eligible_start_denominator(session):
    league = League(name="Premier League", country_or_region="England", level=1)
    session.add(league)
    session.flush()
    _add_match(session, league, kickoff_time=datetime(2026, 1, 10, 20, 0, tzinfo=BEIJING))
    match_with_samples = _add_match(
        session,
        league,
        kickoff_time=datetime(2026, 1, 20, 20, 0, tzinfo=BEIJING),
    )
    _add_match(session, league, kickoff_time=datetime(2026, 1, 21, 20, 0, tzinfo=BEIJING))
    _add_pair(
        session,
        match_with_samples,
        market_type="asian_handicap",
        market_line=Decimal("-0.25"),
        side_a="home",
        side_b="away",
    )
    _add_pair(
        session,
        match_with_samples,
        market_type="total_goals",
        market_line=Decimal("2.50"),
        side_a="over",
        side_b="under",
    )
    session.commit()

    report = build_historical_odds_sample_quality_report(session, season=2026)

    assert report.full_season_match_count == 3
    assert report.eligible_match_count == 2
    assert report.excluded_before_eligible_start_count == 1
    assert report.match_with_sample_count == 1
    assert report.eligible_coverage_ratio == Decimal("0.5000")
    assert report.full_season_coverage_ratio == Decimal("0.3333")
    assert report.market_reports["asian_handicap"].sample_count == 1
    assert report.market_reports["asian_handicap"].thin_history_sample_count == 1
    assert report.market_reports["asian_handicap"].missing_anchor_counts["24h"] == 1
    assert report.market_reports["total_goals"].sample_count == 1
    assert report.league_reports["Premier League"].eligible_match_count == 2
    assert report.league_reports["Premier League"].match_with_sample_count == 1


def test_format_historical_odds_sample_quality_report_summarizes_denominators(session):
    league = League(name="La Liga", country_or_region="Spain", level=1)
    session.add(league)
    session.flush()
    match = _add_match(session, league, kickoff_time=datetime(2026, 1, 20, 20, 0, tzinfo=BEIJING))
    _add_pair(
        session,
        match,
        market_type="asian_handicap",
        market_line=Decimal("0.00"),
        side_a="home",
        side_b="away",
    )
    session.commit()

    report = build_historical_odds_sample_quality_report(session, season=2026)
    text = format_historical_odds_sample_quality_report(report)

    assert "eligible start 2026-01-15 00:00 Asia/Shanghai" in text
    assert "eligible coverage 1.0000" in text
    assert "full-season coverage 1.0000" in text
    assert "asian_handicap: samples 1" in text
    assert "La Liga: eligible 1" in text


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
    side_a: str,
    side_b: str,
) -> None:
    snapshot_time = match.kickoff_time - timedelta(hours=12)
    for side, odds in [(side_a, Decimal("1.90")), (side_b, Decimal("1.96"))]:
        session.add(
            HistoricalOddsSnapshot(
                match_id=match.id,
                source_name="oddspapi",
                source_fixture_id=f"fixture-{match.id}",
                bookmaker="pinnacle",
                market_type=market_type,
                market_id=f"{market_type}-{match.id}",
                market_name=market_type,
                market_line=market_line,
                outcome_side=side,
                odds=odds,
                snapshot_time=snapshot_time,
                period="fulltime",
            )
        )

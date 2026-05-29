from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.baseline_training_dataset_service import (
    build_baseline_training_dataset,
    format_baseline_training_dataset_report,
)
from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, Team


UTC = ZoneInfo("UTC")


def test_build_baseline_training_dataset_keeps_complete_enabled_main_league_matches(session):
    eligible = _add_match(session, league_name="Premier League", source_league_id="39")
    _add_complete_three_market_close_snapshots(session, eligible)

    disabled = _add_match(
        session,
        league_name="J2 League",
        source_league_id="99",
        is_enabled=False,
    )
    _add_complete_three_market_close_snapshots(session, disabled)

    uefa = _add_match(session, league_name="UEFA Champions League", source_league_id="2")
    _add_complete_three_market_close_snapshots(session, uefa)

    before_start = _add_match(
        session,
        league_name="La Liga",
        source_league_id="140",
        kickoff_time=datetime(2026, 1, 14, 15, 0, tzinfo=UTC),
    )
    _add_complete_three_market_close_snapshots(session, before_start)

    incomplete = _add_match(session, league_name="Serie A", source_league_id="135")
    _add_pair(
        session,
        incomplete,
        market_type="asian_handicap",
        market_line=Decimal("-0.25"),
        side_a="home",
        side_b="away",
        side_a_odds=Decimal("1.91"),
        side_b_odds=Decimal("1.97"),
    )
    session.commit()

    dataset = build_baseline_training_dataset(
        session,
        eligible_start=datetime(2026, 1, 15, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert dataset.audit.eligible_match_count == 2
    assert dataset.audit.complete_match_count == 1
    assert dataset.audit.coverage_ratio == Decimal("0.5000")
    assert dataset.audit.missing_market_counts == {
        "asian_handicap": 0,
        "total_goals": 1,
        "match_winner": 1,
    }
    assert len(dataset.rows) == 1
    row = dataset.rows[0]
    assert row["match_id"] == str(eligible.id)
    assert row["league_source_id"] == "39"
    assert row["match_result"] == "home_win"
    assert row["total_goals"] == "3"
    assert row["asian_handicap_close_line"] == "-0.25"
    assert row["asian_handicap_home_result"] == "win"
    assert row["total_goals_close_line"] == "2.50"
    assert row["total_goals_over_result"] == "win"
    assert row["match_winner_home_odds"] == "2.100"
    assert row["match_winner_home_result"] == "win"


def test_format_baseline_training_dataset_report_summarizes_counts(session):
    match = _add_match(session, league_name="Premier League", source_league_id="39")
    _add_complete_three_market_close_snapshots(session, match)
    session.commit()

    dataset = build_baseline_training_dataset(
        session,
        eligible_start=datetime(2026, 1, 15, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    text = format_baseline_training_dataset_report(dataset.audit)

    assert "baseline training dataset" in text
    assert "eligible matches: 1" in text
    assert "complete three-market rows: 1" in text
    assert "coverage: 1.0000" in text
    assert "Premier League" in text


def test_build_baseline_training_dataset_uses_database_wall_time_start_boundary(session):
    before_start = _add_match(
        session,
        league_name="Pro League",
        source_league_id="307",
        kickoff_time=datetime(2026, 1, 14, 22, 45, tzinfo=UTC),
    )
    _add_complete_three_market_close_snapshots(session, before_start)
    at_start = _add_match(
        session,
        league_name="Premier League",
        source_league_id="39",
        kickoff_time=datetime(2026, 1, 15, 0, 0, tzinfo=UTC),
    )
    _add_complete_three_market_close_snapshots(session, at_start)
    session.commit()

    dataset = build_baseline_training_dataset(
        session,
        eligible_start=datetime(2026, 1, 15, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert dataset.audit.eligible_match_count == 1
    assert [row["match_id"] for row in dataset.rows] == [str(at_start.id)]


def _add_match(
    session,
    *,
    league_name: str,
    source_league_id: str,
    is_enabled: bool = True,
    kickoff_time: datetime = datetime(2026, 5, 20, 20, 0, tzinfo=UTC),
) -> Match:
    league = League(
        name=league_name,
        country_or_region="World" if source_league_id in {"2", "3", "848"} else "England",
        level=1,
        is_enabled=is_enabled,
        source_name="api_football",
        source_league_id=source_league_id,
    )
    home = Team(canonical_name=f"{league_name} Home")
    away = Team(canonical_name=f"{league_name} Away")
    session.add_all([league, home, away])
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
        source_match_id=f"fixture-{source_league_id}",
    )
    session.add(match)
    session.flush()
    return match


def _add_complete_three_market_close_snapshots(session, match: Match) -> None:
    _add_pair(
        session,
        match,
        market_type="asian_handicap",
        market_line=Decimal("-0.25"),
        side_a="home",
        side_b="away",
        side_a_odds=Decimal("1.910"),
        side_b_odds=Decimal("1.970"),
    )
    _add_pair(
        session,
        match,
        market_type="total_goals",
        market_line=Decimal("2.50"),
        side_a="over",
        side_b="under",
        side_a_odds=Decimal("1.880"),
        side_b_odds=Decimal("2.000"),
    )
    for side, odds in [
        ("home", Decimal("2.100")),
        ("draw", Decimal("3.300")),
        ("away", Decimal("3.500")),
    ]:
        _add_snapshot(
            session,
            match,
            market_type="match_winner",
            market_line=Decimal("0.00"),
            side=side,
            odds=odds,
        )


def _add_pair(
    session,
    match: Match,
    *,
    market_type: str,
    market_line: Decimal,
    side_a: str,
    side_b: str,
    side_a_odds: Decimal,
    side_b_odds: Decimal,
) -> None:
    _add_snapshot(
        session,
        match,
        market_type=market_type,
        market_line=market_line,
        side=side_a,
        odds=side_a_odds,
    )
    _add_snapshot(
        session,
        match,
        market_type=market_type,
        market_line=market_line,
        side=side_b,
        odds=side_b_odds,
    )


def _add_snapshot(
    session,
    match: Match,
    *,
    market_type: str,
    market_line: Decimal,
    side: str,
    odds: Decimal,
) -> None:
    session.add(
        HistoricalOddsSnapshot(
            match_id=match.id,
            source_name="oddspapi",
            source_fixture_id=f"odds-{match.id}",
            bookmaker="pinnacle",
            market_type=market_type,
            market_id=f"{market_type}-{market_line}",
            market_name=market_type,
            market_line=market_line,
            outcome_side=side,
            odds=odds,
            snapshot_time=match.kickoff_time - timedelta(minutes=7),
            period="fulltime",
        )
    )

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import League, Match, RecommendationRecord, Team
from icewine_prediction.record_service import profit_units_for_result, settle_pending_records


def _match(session, home_score: int, away_score: int) -> Match:
    league = League(name="La Liga", country_or_region="Spain", level=1)
    home = Team(canonical_name="Real Madrid")
    away = Team(canonical_name="Athletic Club")
    session.add_all([league, home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="finished",
        home_score=home_score,
        away_score=away_score,
        source_name="api_football",
        source_match_id="match-1",
    )
    session.add(match)
    session.commit()
    return match


def _record(
    match: Match,
    market_type: str,
    side: str,
    market_line: Decimal,
    odds: Decimal = Decimal("1.90"),
    stake_units: Decimal = Decimal("2.00"),
) -> RecommendationRecord:
    return RecommendationRecord(
        match_id=match.id,
        created_at=datetime(2026, 5, 23, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        league_name=match.league.name,
        home_team_name=match.home_team.canonical_name,
        away_team_name=match.away_team.canonical_name,
        kickoff_time=match.kickoff_time,
        market_type=market_type,
        side=side,
        market_line=market_line,
        odds=odds,
        model_probability=Decimal("0.6000"),
        market_implied_probability=Decimal("0.5263"),
        edge=Decimal("0.0737"),
        confidence_grade="B",
        stake_units=stake_units,
        home_expected_goals=Decimal("1.40"),
        away_expected_goals=Decimal("1.00"),
        status="pending",
    )


def test_profit_units_for_result_uses_odds_and_stake():
    assert profit_units_for_result("win", Decimal("2.00"), Decimal("1.90")) == Decimal("1.800")
    assert profit_units_for_result("half_win", Decimal("2.00"), Decimal("1.90")) == Decimal("0.900")
    assert profit_units_for_result("push", Decimal("2.00"), Decimal("1.90")) == Decimal("0.000")
    assert profit_units_for_result("half_loss", Decimal("2.00"), Decimal("1.90")) == Decimal("-1.000")
    assert profit_units_for_result("loss", Decimal("2.00"), Decimal("1.90")) == Decimal("-2.000")


def test_settle_pending_records_settles_asian_handicap(session):
    match = _match(session, home_score=2, away_score=1)
    record = _record(match, market_type="asian_handicap", side="home", market_line=Decimal("-0.75"))
    session.add(record)
    session.commit()

    settled = settle_pending_records(session)

    assert settled == 1
    assert record.status == "settled"
    assert record.settlement_result == "half_win"
    assert record.profit_units == Decimal("0.900")


def test_settle_pending_records_settles_total_goals(session):
    match = _match(session, home_score=1, away_score=1)
    record = _record(match, market_type="total_goals", side="under", market_line=Decimal("2.25"))
    session.add(record)
    session.commit()

    settled = settle_pending_records(session)

    assert settled == 1
    assert record.status == "settled"
    assert record.settlement_result == "half_win"
    assert record.profit_units == Decimal("0.900")

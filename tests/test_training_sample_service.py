from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import League, Match, OddsSnapshot, Team
from icewine_prediction.training_sample_service import (
    build_training_sample,
    list_training_samples,
    time_decay_weight_for_age,
)


def _create_finished_match(session) -> Match:
    league = League(name="La Liga", country_or_region="Spain", level=1)
    home = Team(canonical_name="Real Madrid")
    away = Team(canonical_name="Barcelona")
    session.add_all([league, home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2025, 5, 25, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="finished",
        home_score=2,
        away_score=1,
        source_name="api_football",
        source_match_id="3001",
    )
    session.add(match)
    session.flush()
    session.add(
        OddsSnapshot(
            match=match,
            captured_at=datetime(2025, 5, 24, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            data_source="api_football",
            bookmaker="Bet365",
            asian_handicap=Decimal("-0.50"),
            home_odds=Decimal("1.90"),
            away_odds=Decimal("1.95"),
            total_line=Decimal("2.50"),
            over_odds=Decimal("1.85"),
            under_odds=Decimal("2.00"),
        )
    )
    session.commit()
    return match


def test_build_training_sample_generates_result_and_settlement_labels(session):
    match = _create_finished_match(session)

    sample = build_training_sample(
        match,
        reference_time=datetime(2026, 5, 23, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert sample.match_id == match.id
    assert sample.league_name == "La Liga"
    assert sample.home_team_name == "Real Madrid"
    assert sample.away_team_name == "Barcelona"
    assert sample.home_score == 2
    assert sample.away_score == 1
    assert sample.match_result == "home_win"
    assert sample.total_goals == 3
    assert sample.asian_handicap_line == Decimal("-0.50")
    assert sample.home_handicap_result == "win"
    assert sample.away_handicap_result == "loss"
    assert sample.total_line == Decimal("2.50")
    assert sample.over_result == "win"
    assert sample.under_result == "loss"
    assert sample.has_odds_snapshot is True
    assert sample.sample_age_days == 363
    assert sample.time_decay_weight == Decimal("0.80")


def test_list_training_samples_filters_finished_matches(session):
    finished = _create_finished_match(session)
    scheduled = Match(
        league=finished.league,
        home_team=finished.home_team,
        away_team=finished.away_team,
        kickoff_time=datetime(2026, 5, 25, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
        source_name="api_football",
        source_match_id="future",
    )
    session.add(scheduled)
    session.commit()

    samples = list_training_samples(
        session,
        limit=10,
        reference_time=datetime(2026, 5, 23, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert len(samples) == 1
    assert samples[0].source_match_id == "3001"


def test_time_decay_weight_for_age_uses_near_high_far_low_policy():
    assert time_decay_weight_for_age(30) == Decimal("1.00")
    assert time_decay_weight_for_age(200) == Decimal("0.80")
    assert time_decay_weight_for_age(500) == Decimal("0.55")
    assert time_decay_weight_for_age(900) == Decimal("0.35")
    assert time_decay_weight_for_age(1300) == Decimal("0.15")

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.feature_service import (
    build_match_odds_features,
    default_base_features,
    list_upcoming_match_odds_features,
)
from icewine_prediction.models import League, Match, OddsSnapshot, Team


def _create_match_with_odds(session) -> Match:
    league = League(name="Serie A", country_or_region="Italy", level=1)
    home = Team(canonical_name="Bologna")
    away = Team(canonical_name="Inter")
    session.add_all([league, home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 5, 24, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
        source_name="api_football",
        source_match_id="1378234",
    )
    session.add(match)
    session.flush()
    session.add_all(
        [
            OddsSnapshot(
                match=match,
                captured_at=datetime(2026, 5, 23, 17, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                data_source="api_football",
                bookmaker="Bet365",
                asian_handicap=Decimal("0.25"),
                home_odds=Decimal("1.98"),
                away_odds=Decimal("1.88"),
                total_line=Decimal("2.50"),
                over_odds=Decimal("1.57"),
                under_odds=Decimal("2.38"),
            ),
            OddsSnapshot(
                match=match,
                captured_at=datetime(2026, 5, 23, 17, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                data_source="api_football",
                bookmaker="Pinnacle",
                asian_handicap=Decimal("0.50"),
                home_odds=Decimal("1.75"),
                away_odds=Decimal("2.00"),
                total_line=Decimal("3.00"),
                over_odds=Decimal("1.95"),
                under_odds=Decimal("1.79"),
            ),
            OddsSnapshot(
                match=match,
                captured_at=datetime(2026, 5, 23, 17, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                data_source="api_football",
                bookmaker="888Sport",
                asian_handicap=None,
                home_odds=None,
                away_odds=None,
                total_line=Decimal("2.50"),
                over_odds=Decimal("1.62"),
                under_odds=Decimal("2.25"),
            ),
            OddsSnapshot(
                match=match,
                captured_at=datetime(2026, 5, 23, 17, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                data_source="api_football",
                bookmaker="BadLineBook",
                asian_handicap=Decimal("-0.80"),
                home_odds=Decimal("1.90"),
                away_odds=Decimal("1.90"),
                total_line=Decimal("2.63"),
                over_odds=Decimal("1.90"),
                under_odds=Decimal("1.90"),
            ),
        ]
    )
    session.commit()
    return match


def test_default_base_features_returns_neutral_strengths():
    features = default_base_features()

    assert features.home_attack_strength == Decimal("1.00")
    assert features.away_attack_strength == Decimal("1.00")


def test_build_match_odds_features_aggregates_handicap_and_total_lines(session):
    match = _create_match_with_odds(session)

    features = build_match_odds_features(match)

    assert features.match_id == match.id
    assert features.bookmaker_count == 3
    assert features.asian_handicap.sample_count == 2
    assert features.asian_handicap.mean == Decimal("0.25")
    assert features.asian_handicap.median == Decimal("0.25")
    assert features.asian_handicap.disagreement == Decimal("0.25")
    assert features.home_odds.mean == Decimal("1.98")
    assert features.away_odds.mean == Decimal("1.88")
    assert features.total_line.sample_count == 3
    assert features.total_line.mean == Decimal("2.50")
    assert features.total_line.median == Decimal("2.50")
    assert features.total_line.disagreement == Decimal("0.50")
    assert features.over_odds.mean == Decimal("1.60")
    assert features.under_odds.mean == Decimal("2.32")


def test_list_upcoming_match_odds_features_filters_window_and_requires_odds(session):
    inside = _create_match_with_odds(session)
    league = inside.league
    home = inside.home_team
    away = inside.away_team
    session.add_all(
        [
            Match(
                league=league,
                home_team=home,
                away_team=away,
                kickoff_time=datetime(2026, 5, 25, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                status="scheduled",
                source_name="api_football",
                source_match_id="outside",
            ),
            Match(
                league=league,
                home_team=home,
                away_team=away,
                kickoff_time=datetime(2026, 5, 23, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                status="scheduled",
                source_name="api_football",
                source_match_id="no-odds",
            ),
        ]
    )
    session.commit()

    rows = list_upcoming_match_odds_features(
        session,
        start_time=datetime(2026, 5, 23, 17, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        hours=24,
    )

    assert len(rows) == 1
    assert rows[0].match.source_match_id == "1378234"
    assert rows[0].features.bookmaker_count == 3

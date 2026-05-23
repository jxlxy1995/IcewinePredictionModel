from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import League, Match, OddsSnapshot, Team
from icewine_prediction.sources.api_football_client import ApiFootballApiError
from icewine_prediction.sources.api_football_mapper import ExternalOddsSnapshot
from icewine_prediction.sync_runner import (
    build_sync_summary,
    fetch_and_store_odds_snapshots,
    select_upcoming_fixture_ids_for_odds,
)


def test_build_sync_summary_formats_counts():
    summary = build_sync_summary(
        operation="upcoming",
        created=2,
        updated=3,
        skipped=1,
        requests_used=4,
    )

    assert "upcoming" in summary
    assert "created=2" in summary
    assert "updated=3" in summary
    assert "requests=4" in summary


def test_select_upcoming_fixture_ids_for_odds_uses_beijing_window(session):
    league = League(name="Serie A", country_or_region="Italy", level=1)
    home = Team(canonical_name="Bologna")
    away = Team(canonical_name="Inter")
    session.add_all([league, home, away])
    session.flush()
    start_time = datetime(2026, 5, 23, 17, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    session.add_all(
        [
            Match(
                league=league,
                home_team=home,
                away_team=away,
                kickoff_time=datetime(2026, 5, 24, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                status="scheduled",
                source_name="api_football",
                source_match_id="inside",
            ),
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
                status="finished",
                source_name="api_football",
                source_match_id="finished",
            ),
        ]
    )
    session.commit()

    fixture_ids = select_upcoming_fixture_ids_for_odds(session, days=1, start_time=start_time)

    assert fixture_ids == ["inside"]


class PartiallyFailingProvider:
    def __init__(self):
        self.client = type("Client", (), {"request_count": 2})()

    def fetch_odds_for_fixtures(self, fixture_ids):
        fixture_id = fixture_ids[0]
        if fixture_id == "second":
            raise ApiFootballApiError("API-Football HTTP error 429")
        return [
            ExternalOddsSnapshot(
                source_name="api_football",
                source_match_id=fixture_id,
                captured_at=datetime(2026, 5, 23, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                bookmaker="Bet365",
                asian_handicap=Decimal("0.25"),
                home_odds=Decimal("1.98"),
                away_odds=Decimal("1.88"),
                total_line=Decimal("3.0"),
                over_odds=Decimal("1.95"),
                under_odds=Decimal("1.79"),
            )
        ]


def test_fetch_and_store_odds_snapshots_persists_partial_results_before_api_error(session):
    league = League(name="Serie A", country_or_region="Italy", level=1)
    home = Team(canonical_name="Bologna")
    away = Team(canonical_name="Inter")
    session.add_all([league, home, away])
    session.flush()
    for fixture_id in ["first", "second"]:
        session.add(
            Match(
                league=league,
                home_team=home,
                away_team=away,
                kickoff_time=datetime(2026, 5, 24, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                status="scheduled",
                source_name="api_football",
                source_match_id=fixture_id,
            )
        )
    session.commit()

    result = fetch_and_store_odds_snapshots(session, PartiallyFailingProvider(), ["first", "second"])

    assert result.created_odds_snapshots == 1
    assert result.failed_fixture_id == "second"
    assert "429" in result.error_message
    assert session.query(OddsSnapshot).count() == 1

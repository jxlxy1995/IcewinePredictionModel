from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import League, Match, OddsSnapshot, Team
from icewine_prediction.sources.api_football_client import ApiFootballApiError
from icewine_prediction.sources.api_football_mapper import ExternalFixture
from icewine_prediction.sources.api_football_mapper import ExternalOddsSnapshot
from icewine_prediction.settings import LeagueSettings
from icewine_prediction.sync_runner import (
    build_sync_summary,
    build_history_backfill_tasks,
    run_history_backfill,
    fetch_and_store_odds_snapshots,
    fetch_and_store_historical_fixtures,
    select_recent_finished_fixture_ids_for_odds,
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


def test_build_history_backfill_tasks_orders_recent_seasons_and_priority_leagues():
    leagues = [
        LeagueSettings("Low Priority", "A", 1, True, 10),
        LeagueSettings("Disabled", "B", 2, False, 999),
        LeagueSettings("High Priority", "C", 3, True, 100),
        LeagueSettings("Medium Priority", "D", 4, True, 50),
    ]

    tasks = build_history_backfill_tasks(
        leagues,
        from_season=2022,
        to_season=2024,
        max_leagues=2,
    )

    assert [(task.league_id, task.season) for task in tasks] == [
        (3, 2024),
        (4, 2024),
        (3, 2023),
        (4, 2023),
        (3, 2022),
        (4, 2022),
    ]


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


def test_select_recent_finished_fixture_ids_for_odds_uses_days_window_and_recent_first(session):
    league = League(name="Serie A", country_or_region="Italy", level=1)
    home = Team(canonical_name="Bologna")
    away = Team(canonical_name="Inter")
    session.add_all([league, home, away])
    session.flush()
    end_time = datetime(2026, 5, 23, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    session.add_all(
        [
            Match(
                league=league,
                home_team=home,
                away_team=away,
                kickoff_time=datetime(2026, 5, 23, 2, 45, tzinfo=ZoneInfo("Asia/Shanghai")),
                status="finished",
                source_name="api_football",
                source_match_id="recent",
            ),
            Match(
                league=league,
                home_team=home,
                away_team=away,
                kickoff_time=datetime(2026, 5, 21, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                status="finished",
                source_name="api_football",
                source_match_id="older",
            ),
            Match(
                league=league,
                home_team=home,
                away_team=away,
                kickoff_time=datetime(2026, 5, 20, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                status="finished",
                source_name="api_football",
                source_match_id="outside",
            ),
            Match(
                league=league,
                home_team=home,
                away_team=away,
                kickoff_time=datetime(2026, 5, 23, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                status="scheduled",
                source_name="api_football",
                source_match_id="scheduled",
            ),
        ]
    )
    session.commit()

    fixture_ids = select_recent_finished_fixture_ids_for_odds(
        session,
        days=2,
        end_time=end_time,
    )

    assert fixture_ids == ["recent", "older"]


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


class HistoricalProvider:
    def __init__(self):
        self.client = type("Client", (), {"request_count": 1})()

    def fetch_historical_fixtures(self, league_id: int, season: int):
        assert league_id == 140
        assert season == 2024
        return [
            ExternalFixture(
                source_name="api_football",
                source_match_id="3001",
                source_league_id="140",
                league_name="La Liga",
                country="Spain",
                home_source_team_id="541",
                home_team_name="Real Madrid",
                away_source_team_id="529",
                away_team_name="Barcelona",
                kickoff_time=datetime(2025, 5, 25, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                status="finished",
                home_score=2,
                away_score=1,
            )
        ]


def test_fetch_and_store_historical_fixtures_upserts_matches(session):
    result = fetch_and_store_historical_fixtures(
        session,
        HistoricalProvider(),
        league_id=140,
        season=2024,
    )

    assert result.created_matches == 1
    assert session.query(Match).one().source_match_id == "3001"


def test_run_history_backfill_returns_per_task_and_historical_odds_summaries(monkeypatch):
    calls = []

    def fake_run_sync_history(league_id: int, season: int) -> str:
        calls.append(("history", league_id, season))
        return f"history:{league_id}:{season}: created=1, updated=0, skipped=0, requests=1"

    def fake_run_sync_historical_odds(days: int) -> str:
        calls.append(("historical-odds", days))
        return f"historical-odds:{days}: created=2, updated=0, skipped=0, requests=1"

    monkeypatch.setattr("icewine_prediction.sync_runner.run_sync_history", fake_run_sync_history)
    monkeypatch.setattr(
        "icewine_prediction.sync_runner.run_sync_historical_odds",
        fake_run_sync_historical_odds,
    )
    leagues = [
        LeagueSettings("La Liga", "Spain", 140, True, 95),
        LeagueSettings("Serie A", "Italy", 135, True, 90),
    ]

    summary = run_history_backfill(
        leagues=leagues,
        from_season=2024,
        to_season=2024,
        max_leagues=1,
        historical_odds_days=3,
    )

    assert calls == [("history", 140, 2024), ("historical-odds", 3)]
    assert "history:140:2024" in summary
    assert "historical-odds:3" in summary
